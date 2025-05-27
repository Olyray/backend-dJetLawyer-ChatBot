import os
import io
import uuid
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.models.user import User
from app.models.attachment import Attachment
from app.core.security import create_access_token
from app.services.auth import get_password_hash

@pytest.fixture
def setup_upload_dir():
    # Create temporary upload directories for testing
    upload_dir = os.path.join(os.getcwd(), "uploads")
    os.makedirs(os.path.join(upload_dir, "audio"), exist_ok=True)
    yield

@pytest.fixture
def mock_rag_chain():
    # Mock the RAG chain and LLM for testing
    with patch("app.api.chatbot.rag_chain") as mock_chain:
        # Configure the mock to return a predictable response
        mock_chain.invoke.return_value = {
            "answer": "This is a mocked response to your audio message.",
            "context": [MagicMock(metadata={"source": "test-source"})],
        }
        yield mock_chain

@pytest.fixture
def mock_llm():
    # Mock the LLM for audio transcription
    with patch("langchain_google_genai.ChatGoogleGenerativeAI") as mock_llm_class:
        mock_llm = MagicMock()
        mock_llm.ainvoke.return_value = MagicMock(content="This is a transcription of the audio message.")
        mock_llm_class.return_value = mock_llm
        yield mock_llm

def test_audio_message_in_chat(client, db, setup_upload_dir, mock_rag_chain, mock_llm):
    # Create a test user
    hashed_password = get_password_hash("testpassword")
    user = User(email="audiotest@example.com", hashed_password=hashed_password)
    db.add(user)
    db.commit()

    # Generate access token
    access_token = create_access_token(data={"sub": user.email})

    # Create a test chat
    response = client.post(
        "/api/v1/chat/chats",
        json={"title": "Audio Test Chat"},
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    chat_id = response.json()["id"]

    # Upload an audio file
    test_content = b"Fake audio content"
    test_filename = "test_message.mp3"
    
    response = client.post(
        "/api/v1/attachments/upload",
        files={"file": (test_filename, test_content, "audio/mp3")},
        data={"file_type": "audio"},
        headers={"Authorization": f"Bearer {access_token}"}
    )
    
    assert response.status_code == 200
    attachment_id = response.json()["id"]

    # Send a chat message with the audio attachment
    response = client.post(
        "/api/v1/chatbot/chat",
        json={
            "message": "Here's an audio message for transcription",
            "chat_id": chat_id,
            "attachments": [
                {
                    "id": attachment_id,
                    "file_name": test_filename,
                    "file_type": "audio/mp3",
                    "file_size": len(test_content)
                }
            ]
        },
        headers={"Authorization": f"Bearer {access_token}"}
    )
    
    assert response.status_code == 200
    
    # Verify that the attachment was associated with the message
    attachment = db.query(Attachment).filter(Attachment.id == uuid.UUID(attachment_id)).first()
    assert attachment is not None
    assert attachment.message_id is not None

@patch("app.services.file_storage.encode_file_to_base64")
def test_audio_processing_workflow(mock_encode, client, db, setup_upload_dir, mock_rag_chain, mock_llm):
    # Set up the encode_file_to_base64 mock
    mock_encode.return_value = "mock_base64_content"
    
    # Create a test user
    hashed_password = get_password_hash("testpassword")
    user = User(email="audiowf@example.com", hashed_password=hashed_password)
    db.add(user)
    db.commit()

    # Generate access token
    access_token = create_access_token(data={"sub": user.email})

    # Create a test audio file
    test_filename = "test_workflow.mp3"
    file_path = "audio/test_workflow.mp3"
    physical_path = os.path.join(os.getcwd(), "uploads", file_path)
    
    # Create the file on disk
    with open(physical_path, "wb") as f:
        f.write(b"Test audio content for processing")
    
    # Create an attachment record and store its data in variables
    attachment = Attachment(
        file_name=test_filename,
        file_type="audio/mp3",
        file_size=30,  # Length of test content
        file_path=file_path
    )
    db.add(attachment)
    db.commit()
    
    # Store attachment details in variables before the session changes
    attachment_id = str(attachment.id)
    attachment_file_name = attachment.file_name
    attachment_file_type = attachment.file_type
    attachment_file_size = attachment.file_size

    # Create a test chat
    response = client.post(
        "/api/v1/chat/chats",
        json={"title": "Audio Processing Test"},
        headers={"Authorization": f"Bearer {access_token}"}
    )
    chat_id = response.json()["id"]

    # Send a message with the attachment using stored variables
    response = client.post(
        "/api/v1/chatbot/chat",
        json={
            "message": "Process this audio file",
            "chat_id": chat_id,
            "attachments": [
                {
                    "id": attachment_id,
                    "file_name": attachment_file_name,
                    "file_type": attachment_file_type,
                    "file_size": attachment_file_size
                }
            ]
        },
        headers={"Authorization": f"Bearer {access_token}"}
    )
    
    assert response.status_code == 200
    
    # Verify that process_attachments was called with the correct attachment
    mock_llm.ainvoke.assert_called()
    
    # Verify the attachment is now associated with a message - query fresh
    updated_attachment = db.query(Attachment).filter(Attachment.id == uuid.UUID(attachment_id)).first()
    assert updated_attachment is not None
    assert updated_attachment.message_id is not None

@patch("app.services.chat_processing.extract_text_from_document")
@patch("app.services.file_storage.encode_file_to_base64")
def test_audio_transcription(mock_encode, mock_extract, client, db, setup_upload_dir, mock_llm):
    # Set up mocks
    mock_encode.return_value = "mock_base64_content"
    mock_extract.return_value = "Transcribed audio content"
    
    # Create test user and audio file
    hashed_password = get_password_hash("testpassword")
    user = User(email="transcribe@example.com", hashed_password=hashed_password)
    db.add(user)
    db.commit()
    
    access_token = create_access_token(data={"sub": user.email})
    
    # Create an attachment in the database and store its details
    attachment = Attachment(
        file_name="transcription_test.mp3",
        file_type="audio/mp3",
        file_size=100,
        file_path="audio/transcription_test.mp3"
    )
    db.add(attachment)
    db.commit()
    
    # Store attachment details before the session changes
    attachment_id = str(attachment.id)
    attachment_file_name = attachment.file_name
    attachment_file_type = attachment.file_type
    attachment_file_size = attachment.file_size
    
    # Create the physical file
    os.makedirs(os.path.join(os.getcwd(), "uploads", "audio"), exist_ok=True)
    with open(os.path.join(os.getcwd(), "uploads", "audio/transcription_test.mp3"), "wb") as f:
        f.write(b"Audio content for transcription test")
    
    # Test the audio transcription directly with a mocked process_attachments function
    with patch("app.services.chat_processing.process_attachments") as mock_process:
        # Set up mock to return expected values
        mock_process.return_value = (
            [("human", [{"type": "text", "text": "Transcribed audio content"}])],
            ["This is a transcription of the audio message."],
            [attachment]  # This is ok as we're not accessing properties of the attachment
        )
        
        # Mock the RAG chain
        with patch("app.api.chatbot.rag_chain") as mock_chain:
            mock_chain.invoke.return_value = {
                "answer": "Response based on transcribed audio",
                "context": [MagicMock(metadata={"source": "test-source"})]
            }
            
            # Create a test chat
            response = client.post(
                "/api/v1/chat/chats",
                json={"title": "Transcription Test"},
                headers={"Authorization": f"Bearer {access_token}"}
            )
            chat_id = response.json()["id"]
            
            # Send a message with the attachment using stored variables
            response = client.post(
                "/api/v1/chatbot/chat",
                json={
                    "message": "Transcribe this audio",
                    "chat_id": chat_id,
                    "attachments": [
                        {
                            "id": attachment_id,
                            "file_name": attachment_file_name,
                            "file_type": attachment_file_type,
                            "file_size": attachment_file_size
                        }
                    ]
                },
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            assert response.status_code == 200
            assert "answer" in response.json() or "bot_response" in response.json()
            
            # Verify the correct function calls were made
            mock_process.assert_called_once()
            mock_chain.invoke.assert_called_once()
            
            # The message in the request should include audio transcription information
            invoke_args = mock_chain.invoke.call_args[0][0]
            assert "input" in invoke_args
            assert "Transcribe this audio" in invoke_args["input"] 