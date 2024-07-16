import secrets
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.core.security import verify_password, get_password_hash, create_access_token
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin
from google.oauth2 import id_token
from google.auth.transport import requests
from app.core.config import settings

def authenticate_user(db: Session, email: str, password: str):
    """
    Authenticates a user using their email and password.

    Args:
        db (Session): The database session.
        email (str): The user's email address.
        password (str): The user's password.
    Returns:
        User or False: If the email and password are valid, returns the User object.
                       Otherwise, returns False.
    """
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        return False
    return user

def create_user(db: Session, user: UserCreate):
    """
    Creates a new user in the database.

    Args:
        db (Session): The database session.
        user (UserCreate): The user data to create a new user with.

    Returns:
        User: The newly created User object.
    """
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    db_user = User(email=user.email, hashed_password=get_password_hash(user.password))
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def google_authenticate(db: Session, token: str):
    try:
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), settings.GOOGLE_CLIENT_ID)
        email = idinfo['email']
        google_id = idinfo['sub']
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid token")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email, google_id=google_id)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

def create_verification_token(db: Session, user: User) -> str:
    """
    Creates a verification token for a user.

    Args:
        db (Session): The database session.
        user (User): The user to create a verification token for.

    Returns:
        str: The verification token.
    """
    token = secrets.token_urlsafe(32)
    expiration = datetime.utcnow() + timedelta(hours=24)
    
    user.verification_token = token
    user.verification_token_expiry = expiration
    
    db.commit()
    return token

def verify_email_token(db: Session, token: str) -> User:
    """
    Verifies an email verification token.

    Args:
        db (Session): The database session.
        token (str): The verification token.

    Returns:
        User: The user associated with the token if valid, None otherwise.
    """
    user = db.query(User).filter(
        User.verification_token == token,
        User.verification_token_expiry > datetime.utcnow()
    ).first()
    
    if user:
        user.is_verified = True
        user.verification_token = None
        user.verification_token_expiry = None
        db.commit()
    
    return user
