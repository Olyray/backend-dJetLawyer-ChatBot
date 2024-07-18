from app.models.user import User
from app.models.chat import Chat, Message
from app.core.security import create_access_token
from app.services.auth import get_password_hash

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
