from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(data: dict):
    """
    Create a new access token.

    This function takes a dictionary of data and creates a JWT (JSON Web Token) access token.
    It adds an expiration time to the token based on the ACCESS_TOKEN_EXPIRE_MINUTES 
    setting and encodes the token using the SECRET_KEY and specified algorithm.

    Args:
        data (dict): A dictionary containing the data to be encoded in the token.

    Returns:
        str: The encoded JWT access token.

    Note:
        The token expiration time is set to the current UTC time plus the number of minutes
        specified in ACCESS_TOKEN_EXPIRE_MINUTES from the settings.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str):
    """
    Verify a plain password against a hashed password.

    This function uses the pwd_context to verify if the provided plain password
    matches the given hashed password.

    Args:
        plain_password (str): The plain text password to be verified.
        hashed_password (str): The hashed password to compare against.

    Returns:
        bool: True if the plain password matches the hashed password, False otherwise.

    Note:
        This function relies on the pwd_context object, which should be initialized
        with the appropriate hashing scheme (e.g., bcrypt).
    """
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str):
    """
    Generate a hash for the given password.

    This function takes a plain text password and returns its hashed version
    using the pwd_context object, which should be initialized with an
    appropriate hashing scheme (e.g., bcrypt).

    Args:
        password (str): The plain text password to be hashed.

    Returns:
        str: The hashed version of the input password.

    Note:
        The hashing algorithm used depends on the configuration of the pwd_context object.
        Ensure that the same pwd_context is used for both hashing and verification.
    """
    return pwd_context.hash(password)