import pytest
from app.models.user import User
from app.services.auth import get_password_hash, create_verification_token
from app.services.email_service import send_verification_email
from app.core.config import settings
from app.core.security import create_refresh_token
from unittest.mock import patch
from app.services import auth as auth_service
from google.oauth2 import id_token

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
    mocker.patch('app.services.email_service.send_verification_email', return_value=True)

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

import pytest
from unittest.mock import patch

def test_google_login(client, db, mocker):
    # Mock the google_authenticate function
    mock_user = User(email="google_user@example.com", google_id="123456789")
    mocker.patch('app.services.auth.google_authenticate', return_value=mock_user)

    # Mock the id_token.verify_oauth2_token function
    mock_idinfo = {
        'email': 'google_user@example.com',
        'sub': '123456789'
    }
    mocker.patch('google.oauth2.id_token.verify_oauth2_token', return_value=mock_idinfo)

    # Test Google login
    response = client.post(
        "/api/v1/auth/google-login",
        json={"token": "mock_google_token"}
    )

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()
    assert response.json()["token_type"] == "bearer"
    assert response.json()["user"]["email"] == "google_user@example.com"
    assert response.json()["user"]["password"] == ""


    # Verify that id_token.verify_oauth2_token was called
    id_token.verify_oauth2_token.assert_called_once_with(
        "mock_google_token", 
        mocker.ANY,  # This represents the requests.Request() object
        settings.GOOGLE_CLIENT_ID
    )
