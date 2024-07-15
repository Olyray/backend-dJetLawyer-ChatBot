import pytest
from fastapi.testclient import TestClient
from app.models.user import User
from app.models.chat import Chat, Message
from app.core.security import create_access_token
from app.services.auth import get_password_hash

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
def test_chat_creation_and_retrieval(client, db):
    # Create a test user
    hashed_password = get_password_hash("testpassword")
    user = User(email="chattest@example.com", hashed_password=hashed_password)
    db.add(user)
    db.commit()

    # Generate access token
    access_token = create_access_token(data={"sub": user.email})

    # Create a new chat
    response = client.post(
        "/api/v1/chat/chats",
        json={"title": "Test Chat"},
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    chat_id = response.json()["id"]

    # Retrieve the chat
    response = client.get(
        f"/api/v1/chat/chats/{chat_id}",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Test Chat"

    # Add a message to the chat
    response = client.post(
        f"/api/v1/chat/chats/{chat_id}/messages",
        json={"role": "human", "content": "Hello, AI!"},
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200

    # Retrieve chat messages
    response = client.get(
        f"/api/v1/chat/chats/{chat_id}/messages",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["content"] == "Hello, AI!"

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

    # Send a message to the chatbot
    response = client.post(
        "/api/v1/chatbot/chat",
        json={"message": "What is the meaning of life?", "chat_id": chat.id},
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    assert "answer" in response.json()
    assert "sources" in response.json()

    # Verify the message was saved in the database
    messages = db.query(Message).filter(Message.chat_id == chat.id).all()
    assert len(messages) == 2  # User message and AI response
    assert messages[0].role == "human"
    assert messages[0].content == "What is the meaning of life?"
    assert messages[1].role == "assistant"
    assert messages[1].content == "This is a mocked response from the AI."


def test_unauthorized_access(client):
    response = client.get("/api/v1/chat/chats/1")
    assert response.status_code == 401

    response = client.post("/api/v1/chatbot/chat", json={"message": "Hello"})
    assert response.status_code == 401

@pytest.mark.parametrize("endpoint", [
    "/api/v1/chat/999999",
    "/api/v1/chat/999999/messages",
])
def test_nonexistent_resource(client, db, endpoint):
    user = User(email="nonexistent@example.com", hashed_password=get_password_hash("testpassword"))
    db.add(user)
    db.commit()

    access_token = create_access_token(data={"sub": user.email})

    response = client.get(
        endpoint,
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 404
