from fastapi import Depends, HTTPException, status, Request, Response, Header
from fastapi.security import OAuth2PasswordBearer
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.user import User, SubscriptionPlanType
from typing import Optional
from app.services.subscription import is_user_premium
from datetime import datetime
import asyncio
import logging

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user

async def setup_rate_limiter():
    import redis.asyncio as redis
    from redis.asyncio.connection import ConnectionPool
    
    # Create connection pool with keepalive and health checks
    pool = ConnectionPool.from_url(
        settings.REDISCLOUD_URL,
        encoding="utf-8",
        decode_responses=True,
        ssl_cert_reqs=None,
        max_connections=20,
        socket_keepalive=True,
        health_check_interval=30,
        retry_on_timeout=True,
        socket_connect_timeout=5,
    )
    
    redis_instance = redis.Redis(connection_pool=pool)
    await FastAPILimiter.init(redis_instance)
    logger.info("Rate limiter initialized with connection pooling")

# New Addition: Rate limiter dependency
def get_rate_limiter():
    async def rate_limit(request: Request, response: Response):
        limiter = RateLimiter(times=settings.RATE_LIMIT_TIMES, seconds=settings.RATE_LIMIT_SECONDS)
        await limiter(request, response)
    return rate_limit


def expire_subscriptions():
    """Downgrade users whose subscription_expiry_date is more than 5 days past."""
    db = SessionLocal()
    try:
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=5)
        expired_users = db.query(User).filter(
            User.subscription_plan == SubscriptionPlanType.PREMIUM,
            User.subscription_expiry_date < cutoff
        ).all()

        if expired_users:
            for user in expired_users:
                logger.info(
                    f"Expiring subscription for {user.email} "
                    f"(expired: {user.subscription_expiry_date})"
                )
                user.subscription_plan = SubscriptionPlanType.FREE
            db.commit()
            logger.info(f"Downgraded {len(expired_users)} expired subscription(s).")
        else:
            logger.debug("No expired subscriptions found.")
    except Exception as e:
        logger.error(f"Error during subscription expiry check: {e}")
        db.rollback()
    finally:
        db.close()


async def run_subscription_expiry_job(interval_seconds: int = 86400):
    """Background loop that checks for expired subscriptions once a day."""
    logger.info("Subscription expiry background job started.")
    while True:
        await asyncio.sleep(interval_seconds)
        expire_subscriptions()

def optional_oauth2_scheme(
    authorization: Optional[str] = Header(None)
) -> Optional[str]:
    if not authorization:
        return None
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            return None
        return token
    except ValueError:
        return None

async def get_optional_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(optional_oauth2_scheme)
) -> Optional[User]:
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
    except JWTError:
        return None
    
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        return None
    return user

# Add the premium check dependency after the get_current_user dependency

async def get_premium_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    """
    Check if the current user has a premium subscription.
    Returns the current user if they have a premium subscription, otherwise raises an HTTPException.
    Used to protect premium-only endpoints.
    """
    is_premium = is_user_premium(db, current_user.id)
    if not is_premium:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Premium subscription required for this feature",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user

