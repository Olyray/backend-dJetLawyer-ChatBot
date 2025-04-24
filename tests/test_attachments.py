import os
import pytest
import io
import uuid
from unittest.mock import patch, MagicMock
from app.models.user import User
from app.models.attachment import Attachment
from app.core.security import create_access_token
from app.services.auth import get_password_hash
from fastapi import UploadFile

@pytest.fixture
def setup_upload_dir():
    # Create temporary upload directories for testing
    upload_dir = os.path.join(os.getcwd(), "uploads")
    os.makedirs(os.path.join(upload_dir, "documents"), exist_ok=True)
    os.makedirs(os.path.join(upload_dir, "images"), exist_ok=True)
    os.makedirs(os.path.join(upload_dir, "audio"), exist_ok=True)
    yield
    # Note: We don't clean up after tests to avoid interfering with other tests

def test_document_upload(client, db, setup_upload_dir):
    # Create a test user
    hashed_password = get_password_hash("testpassword")
    user = User(email="attachtest@example.com", hashed_password=hashed_password)
    db.add(user)
    db.commit()

    # Generate access token
    access_token = create_access_token(data={"sub": user.email})

    # Create a test PDF file
    test_content = b"%PDF-1.5\nTest PDF content"
    test_filename = "test_document.pdf"
    
    response = client.post(
        "/api/v1/attachments/upload",
        files={"file": (test_filename, test_content, "application/pdf")},
        data={"file_type": "document"},
        headers={"Authorization": f"Bearer {access_token}"}
    )
    
    assert response.status_code == 200
    assert "id" in response.json()
    assert response.json()["file_name"] == test_filename
    assert response.json()["file_type"] == "application/pdf"
    
    # Verify attachment was saved in DB
    attachment_id = uuid.UUID(response.json()["id"])
    attachment = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    assert attachment is not None
    assert attachment.file_name == test_filename
    assert attachment.file_path.startswith("documents/")

def test_image_upload(client, db, setup_upload_dir):
    # Create a test user
    hashed_password = get_password_hash("testpassword")
    user = User(email="imagetest@example.com", hashed_password=hashed_password)
    db.add(user)
    db.commit()

    # Generate access token
    access_token = create_access_token(data={"sub": user.email})

    # Create a test image file
    test_content = b"Fake JPEG content"
    test_filename = "test_image.jpg"
    
    response = client.post(
        "/api/v1/attachments/upload",
        files={"file": (test_filename, test_content, "image/jpeg")},
        data={"file_type": "image"},
        headers={"Authorization": f"Bearer {access_token}"}
    )
    
    assert response.status_code == 200
    assert "id" in response.json()
    assert response.json()["file_name"] == test_filename
    assert response.json()["file_type"] == "image/jpeg"
    
    # Verify attachment was saved in DB
    attachment_id = uuid.UUID(response.json()["id"])
    attachment = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    assert attachment is not None
    assert attachment.file_name == test_filename
    assert attachment.file_path.startswith("images/")

def test_audio_upload(client, db, setup_upload_dir):
    # Create a test user
    hashed_password = get_password_hash("testpassword")
    user = User(email="audiotest@example.com", hashed_password=hashed_password)
    db.add(user)
    db.commit()

    # Generate access token
    access_token = create_access_token(data={"sub": user.email})

    # Create a test audio file
    test_content = b"Fake MP3 content"
    test_filename = "test_audio.mp3"
    
    response = client.post(
        "/api/v1/attachments/upload",
        files={"file": (test_filename, test_content, "audio/mp3")},
        data={"file_type": "audio"},
        headers={"Authorization": f"Bearer {access_token}"}
    )
    
    assert response.status_code == 200
    assert "id" in response.json()
    assert response.json()["file_name"] == test_filename
    assert response.json()["file_type"] == "audio/mp3"
    
    # Verify attachment was saved in DB
    attachment_id = uuid.UUID(response.json()["id"])
    attachment = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    assert attachment is not None
    assert attachment.file_name == test_filename
    assert attachment.file_path.startswith("audio/")

def test_file_validation(client, db, setup_upload_dir):
    # Create a test user
    hashed_password = get_password_hash("testpassword")
    user = User(email="validatetest@example.com", hashed_password=hashed_password)
    db.add(user)
    db.commit()

    # Generate access token
    access_token = create_access_token(data={"sub": user.email})

    # Test invalid file type
    test_content = b"Executable content"
    test_filename = "malicious.exe"
    
    response = client.post(
        "/api/v1/attachments/upload",
        files={"file": (test_filename, test_content, "application/x-msdownload")},
        data={"file_type": "document"},
        headers={"Authorization": f"Bearer {access_token}"}
    )
    
    assert response.status_code == 400
    assert "Invalid file type" in response.json()["detail"]

def test_serve_file(client, db, setup_upload_dir):
    # Create a test user and test file
    hashed_password = get_password_hash("testpassword")
    user = User(email="servetest@example.com", hashed_password=hashed_password)
    db.add(user)
    db.commit()

    # Create a test file in the database and on disk
    test_filename = "test_serve.txt"
    file_path = "documents/test_serve.txt"
    physical_path = os.path.join(os.getcwd(), "uploads", file_path)
    
    # Create the file on disk
    with open(physical_path, "w") as f:
        f.write("Test content for serving")
    
    # Create an attachment record
    attachment = Attachment(
        file_name=test_filename,
        file_type="text/plain",
        file_size=22,  # Length of "Test content for serving"
        file_path=file_path
    )
    db.add(attachment)
    db.commit()
    
    # Generate access token
    access_token = create_access_token(data={"sub": user.email})
    
    # Test serving the file
    response = client.get(
        f"/api/v1/attachments/file/{attachment.id}",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert f'filename="{test_filename}"' in response.headers["content-disposition"]
    assert response.content == b"Test content for serving" 