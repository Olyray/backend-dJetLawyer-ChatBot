import pytest
from app.models.user import User
from app.services.auth import get_password_hash, create_verification_token
from app.services.email import send_verification_email
from app.core.config import settings
from app.core.security import create_refresh_token

def test_user_registration_and_login(client, db):
    # Test user registration
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "password": "testpassword"}
    )
    assert response.status_code == 200

    # Test user login
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "test@example.com", "password": "testpassword"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"


def test_email_verification(client, db, mocker):
    # Mock send_verification_email function
    mocker.patch('app.services.email.send_verification_email', return_value=True)

    # Register a new user
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "verify@example.com", "password": "testpassword"}
    )
    assert response.status_code == 200

    # Get the user from the database
    user = db.query(User).filter(User.email == "verify@example.com").first()
    assert user is not None
    assert user.is_verified == False

    # Create a verification token
    token = create_verification_token(db, user)

    # Test email verification
    response = client.get(f"/api/v1/auth/verify-email?token={token}")
    assert response.status_code == 200
    assert "access_token" in response.json()

    # Check if the user is now verified
    # New Addition: Fetch the user again from the database
    updated_user = db.query(User).filter(User.email == "verify@example.com").first()
    
    # Check if the user is now verified
    assert updated_user.is_verified == True
    assert updated_user.verification_token is None
    assert updated_user.verification_token_expiry is None


def test_invalid_verification_token(client, db):
    response = client.get("/api/v1/auth/verify-email?token=invalid_token")
    assert response.status_code == 400
    assert "Invalid or expired verification token" in response.json()["detail"]


def test_refresh_token(client, db):
    # Register a new user
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "refresh@example.com", "password": "testpassword"}
    )
    assert response.status_code == 200
    refresh_token = response.json()["refresh_token"]

    # Test refresh token endpoint
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()
    assert response.json()["token_type"] == "bearer"


def test_invalid_refresh_token(client, db):
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid_refresh_token"}
    )
    assert response.status_code == 401


"""
def test_google_login(client, db, mocker):
    # Mock Google token verification
    mocker.patch('app.services.auth.id_token.verify_oauth2_token', return_value={
        "email": "google@example.com",
        "sub": "google123"
    })

    response = client.post(
        "/api/v1/auth/google-login",
        json={"token": "fake_google_token"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"

    # Verify user was created in the database
    user = db.query(User).filter(User.email == "google@example.com").first()
    assert user is not None
    assert user.google_id == "google123"
"""