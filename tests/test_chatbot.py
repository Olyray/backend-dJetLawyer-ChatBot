from app.models.user import User
from app.models.chat import Chat, Message
from app.core.security import create_access_token
from app.services.auth import get_password_hash
from uuid import UUID
import pytest
import uuid
from datetime import datetime

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

    # Mock the database save function
    def mock_save_anonymous_chat_to_db(*args, **kwargs):
        # Create a mock chat with the same data structure as a real chat
        mock_chat_id = uuid.uuid4()
        return {
            "id": mock_chat_id,
            "title": args[1],  # Get title from arguments
            "created_at": datetime.utcnow().isoformat(),
            "messages": mock_get_anonymous_messages(None, None)
        }

    # Apply the mocks
    monkeypatch.setattr("app.api.chatbot.get_anonymous_chat_messages", mock_get_anonymous_messages)
    monkeypatch.setattr("app.api.chatbot.save_anonymous_chat_to_db", mock_save_anonymous_chat_to_db)

    # Test sharing an anonymous chat
    response = await client.post(
        "/api/share-anonymous-chat",
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
