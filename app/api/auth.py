import secrets
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_rate_limiter
from app.schemas.user import Token, UserCreate, RefreshToken, GoogleLoginRequest, GoogleToken
from app.services.auth import authenticate_user, create_user, google_authenticate, create_verification_token, verify_email_token
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.services.email_service import send_verification_email
from app.core.config import settings
from app.models.user import User
from fastapi_limiter.depends import RateLimiter
from jose import JWTError

router = APIRouter()

@router.post("/register", response_model=Token)
async def register(
    user: UserCreate, 
    background_tasks: BackgroundTasks, 
    request: Request, 
    response: Response,
    db: Session = Depends(get_db), 
    rate_limiter = Depends(get_rate_limiter)
):
    await rate_limiter(request, response)
    db_user = create_user(db, user)
    access_token = create_access_token(data={"sub": db_user.email})
    refresh_token = create_refresh_token(data={"sub": db_user.email})
    verification_token = create_verification_token(db, db_user)
    background_tasks.add_task(send_verification_email, db_user.email, verification_token)
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

@router.get("/verify-email")
async def verify_email(
    token: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    rate_limiter: RateLimiter = Depends(get_rate_limiter)
):
    await rate_limiter(request, response)

    user = verify_email_token(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )
    
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login", response_model=Token)
async def login(
    request: Request, 
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db), 
    rate_limiter: RateLimiter = Depends(get_rate_limiter)
):
    await rate_limiter(request, response)
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(data={"sub": user.email})
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: Request,
    response: Response,
    refresh_token: RefreshToken,
    db: Session = Depends(get_db),
    rate_limiter: RateLimiter = Depends(get_rate_limiter)
):
    await rate_limiter(request, response)
    try:
        payload = decode_token(refresh_token, settings.SECRET_KEY)
        email = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=400, detail="Invalid refresh token")
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        access_token = create_access_token(data={"sub": email})
        return {"access_token": access_token, "refresh_token": refresh_token.refresh_token, "token_type": "bearer"}
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid refresh token")


@router.post("/google-login", response_model=GoogleToken)
async def google_login(token: GoogleLoginRequest, db: Session = Depends(get_db)):
    user = google_authenticate(db, token.token)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid token or user not found")
    
    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(data={"sub": user.email})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "email": user.email,
            "password": ""
        },
        "token_type": "bearer"
    }


@router.post("/logout")
def logout():
    # In a stateless JWT-based auth system, logout is typically handled client-side
    # by removing the token. Here we can add any server-side logout logic if needed.
    return {"message": "Successfully logged out"}
