from app.models.user import User
from app.models.chat import Chat, Message
from app.core.security import create_access_token
from app.services.auth import get_password_hash
from uuid import UUID
import pytest
import uuid
from datetime import datetime
import os
from unittest.mock import patch, MagicMock
from app.models.attachment import Attachment

def test_chatbot_interaction(client, db, mocker):
    # Create a test user and chat
    user = User(email="bottest@example.com", hashed_password=get_password_hash("testpassword"))
    db.add(user)
    db.commit()
    
    chat = Chat(user_id=user.id, title="Bot Test Chat")
    db.add(chat)
    db.commit()

    access_token = create_access_token(data={"sub": user.email})

    # Mock the entire rag_chain
    mock_rag_chain = mocker.Mock()
    mock_rag_chain.invoke.return_value = {
        "answer": "This is a mocked response from the AI.",
        "context": [mocker.Mock(metadata={"source": "https://example.com"})]
    }
    mocker.patch('app.api.chatbot.rag_chain', mock_rag_chain)

    chat_id_str = str(chat.id)

    # Send a message to the chatbot
    response = client.post(
        "/api/v1/chatbot/chat",
        json={"message": "What is the meaning of life?", "chat_id": chat_id_str},
        headers={"Authorization": f"Bearer {access_token}"}
    )
    print(f"Response status code: {response.status_code}")
    print(f"Response content: {response.content}")

    assert response.status_code == 200
    assert "answer" in response.json()
    assert "sources" in response.json()

    # Verify the message was saved in the database
    messages = db.query(Message).filter(Message.chat_id == UUID(chat_id_str)).all()
    assert len(messages) == 2  # User message and AI response
    assert messages[0].role == "human"
    assert messages[0].content == "What is the meaning of life?"
    assert messages[1].role == "assistant"
    assert messages[1].content == "This is a mocked response from the AI."

@pytest.mark.asyncio
async def test_share_anonymous_chat(client, monkeypatch):
    # Mock the anonymous chat service functions
    async def mock_get_anonymous_messages(*args, **kwargs):
        return [
            {
                "id": str(uuid.uuid4()),
                "chat_id": str(uuid.uuid4()),
                "role": "human",
                "content": "This is an anonymous message",
                "created_at": datetime.utcnow().isoformat()
            },
            {
                "id": str(uuid.uuid4()),
                "chat_id": str(uuid.uuid4()),
                "role": "assistant",
                "content": "This is a response to the anonymous message",
                "created_at": datetime.utcnow().isoformat(),
                "sources": [{"url": "https://example.com"}]
            }
        ]

    # Add a sync version for your mock
    def mock_get_anonymous_messages_sync(*args, **kwargs):
        return [
            {
                "id": str(uuid.uuid4()),
                "chat_id": str(uuid.uuid4()),
                "role": "human",
                "content": "This is an anonymous message",
                "created_at": datetime.utcnow().isoformat()
            },
            {
                "id": str(uuid.uuid4()),
                "chat_id": str(uuid.uuid4()),
                "role": "assistant",
                "content": "This is a response to the anonymous message",
                "created_at": datetime.utcnow().isoformat(),
                "sources": [{"url": "https://example.com"}]
            }
        ]

    def mock_save_anonymous_chat_to_db(*args, **kwargs):
        mock_chat_id = uuid.uuid4()
        return {
            "id": mock_chat_id,
            "title": args[1],
            "created_at": datetime.utcnow().isoformat(),
            "messages": mock_get_anonymous_messages_sync(None, None)  # Use the sync version
        }

    # Apply the mocks
    monkeypatch.setattr("app.api.chatbot.get_anonymous_chat_messages", mock_get_anonymous_messages)
    monkeypatch.setattr("app.api.chatbot.save_anonymous_chat_to_db", mock_save_anonymous_chat_to_db)

    # Test sharing an anonymous chat
    response = client.post(
        "/api/v1/chatbot/share-anonymous-chat",
        json={
            "session_id": "test-session",
            "chat_id": "test-chat-id",
            "title": "Anonymous Chat Title"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify the response
    assert data["title"] == "Anonymous Chat Title"
    assert len(data["messages"]) == 2
    assert data["messages"][0]["content"] == "This is an anonymous message"
    assert data["messages"][1]["content"] == "This is a response to the anonymous message"
    assert data["messages"][1]["sources"][0]["url"] == "https://example.com"

@patch("app.api.chatbot.rag_chain")
def test_chatbot_with_attachment(mock_rag_chain, client, db):
    # Set up mock RAG chain response
    mock_rag_chain.invoke.return_value = {
        "answer": "I've analyzed the attachment you sent.",
        "context": [MagicMock(metadata={"source": "test-source"})]
    }
    
    # Create a test user
    hashed_password = get_password_hash("testpassword")
    user = User(email="attachment_integration@example.com", hashed_password=hashed_password)
    db.add(user)
    db.commit()

    # Generate access token
    access_token = create_access_token(data={"sub": user.email})
    
    # Create test directories
    upload_dir = os.path.join(os.getcwd(), "uploads")
    os.makedirs(os.path.join(upload_dir, "documents"), exist_ok=True)
    
    # Create a test document file
    test_filename = "test_doc.txt"
    file_path = "documents/test_doc.txt"
    physical_path = os.path.join(upload_dir, file_path)
    
    # Create the file on disk
    with open(physical_path, "w") as f:
        f.write("This is test document content")
    
    # Create attachment record
    attachment = Attachment(
        file_name=test_filename,
        file_type="text/plain",
        file_size=28,
        file_path=file_path
    )
    db.add(attachment)
    db.commit()
    
    # Store attachment details in variables before the session changes
    attachment_id = str(attachment.id)
    attachment_file_name = attachment.file_name
    attachment_file_type = attachment.file_type
    attachment_file_size = attachment.file_size
    
    # Create a chat
    response = client.post(
        "/api/v1/chat/chats",
        json={"title": "Attachment Integration Test"},
        headers={"Authorization": f"Bearer {access_token}"}
    )
    chat_id = response.json()["id"]
    
    # Send a message with the attachment
    with patch("app.services.chat_processing.extract_text_from_document") as mock_extract:
        mock_extract.return_value = "Extracted document content"
        
        response = client.post(
            "/api/v1/chatbot/chat",
            json={
                "message": "Please analyze this document",
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
        assert response.json()["answer"] == "I've analyzed the attachment you sent."
        
        # Verify RAG chain was called with attachment content
        mock_rag_chain.invoke.assert_called_once()
        
        # Verify attachment is now associated with a message - query fresh
        updated_attachment = db.query(Attachment).filter(Attachment.id == UUID(attachment_id)).first()
        assert updated_attachment is not None
        assert updated_attachment.message_id is not None

@patch("app.api.chatbot.rag_chain")
def test_chatbot_with_multiple_attachments(mock_rag_chain, client, db):
    # Set up mock RAG chain response
    mock_rag_chain.invoke.return_value = {
        "answer": "I've analyzed all the attachments you sent.",
        "context": [MagicMock(metadata={"source": "test-source"})]
    }
    
    # Create a test user
    hashed_password = get_password_hash("testpassword")
    user = User(email="multi_attachment@example.com", hashed_password=hashed_password)
    db.add(user)
    db.commit()

    # Generate access token
    access_token = create_access_token(data={"sub": user.email})
    
    # Set up test directories
    upload_dir = os.path.join(os.getcwd(), "uploads")
    os.makedirs(os.path.join(upload_dir, "documents"), exist_ok=True)
    os.makedirs(os.path.join(upload_dir, "images"), exist_ok=True)
    
    # Create test files
    doc_path = os.path.join(upload_dir, "documents/test_multi_doc.txt")
    with open(doc_path, "w") as f:
        f.write("Document content for multiple attachments test")
        
    img_path = os.path.join(upload_dir, "images/test_multi_img.jpg")
    with open(img_path, "wb") as f:
        f.write(b"Fake image data for testing")
    
    # Create attachment records
    doc_attachment = Attachment(
        file_name="test_multi_doc.txt",
        file_type="text/plain",
        file_size=44,
        file_path="documents/test_multi_doc.txt"
    )
    
    img_attachment = Attachment(
        file_name="test_multi_img.jpg",
        file_type="image/jpeg",
        file_size=24,
        file_path="images/test_multi_img.jpg"
    )
    
    db.add(doc_attachment)
    db.add(img_attachment)
    db.commit()
    
    # Store attachment details in variables before the session changes
    doc_attachment_id = str(doc_attachment.id)
    doc_attachment_file_name = doc_attachment.file_name
    doc_attachment_file_type = doc_attachment.file_type
    doc_attachment_file_size = doc_attachment.file_size
    
    img_attachment_id = str(img_attachment.id)
    img_attachment_file_name = img_attachment.file_name
    img_attachment_file_type = img_attachment.file_type
    img_attachment_file_size = img_attachment.file_size
    
    # Create a chat
    response = client.post(
        "/api/v1/chat/chats",
        json={"title": "Multiple Attachments Test"},
        headers={"Authorization": f"Bearer {access_token}"}
    )
    chat_id = response.json()["id"]
    
    # Mock necessary functions
    with patch("app.services.chat_processing.extract_text_from_document") as mock_extract, \
         patch("app.services.file_storage.encode_file_to_base64") as mock_encode:
        
        mock_extract.return_value = "Extracted document content for multi-test"
        mock_encode.return_value = "base64_encoded_content"
        
        # Send a message with multiple attachments
        response = client.post(
            "/api/v1/chatbot/chat",
            json={
                "message": "Please analyze these files",
                "chat_id": chat_id,
                "attachments": [
                    {
                        "id": doc_attachment_id,
                        "file_name": doc_attachment_file_name,
                        "file_type": doc_attachment_file_type,
                        "file_size": doc_attachment_file_size
                    },
                    {
                        "id": img_attachment_id,
                        "file_name": img_attachment_file_name,
                        "file_type": img_attachment_file_type,
                        "file_size": img_attachment_file_size
                    }
                ]
            },
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        assert response.status_code == 200
        assert response.json()["answer"] == "I've analyzed all the attachments you sent."
        
        # Verify both attachments are associated with the same message - query fresh
        updated_doc = db.query(Attachment).filter(Attachment.id == UUID(doc_attachment_id)).first()
        updated_img = db.query(Attachment).filter(Attachment.id == UUID(img_attachment_id)).first()
        
        assert updated_doc is not None and updated_img is not None
        assert updated_doc.message_id is not None
        assert updated_img.message_id is not None
        assert updated_doc.message_id == updated_img.message_id
