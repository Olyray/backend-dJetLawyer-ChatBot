from app.models.user import User
from app.models.chat import Chat
from app.core.security import create_access_token
from app.services.auth import get_password_hash
from unittest.mock import patch

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

def test_chat_sharing(client, db):
    # Create a test user
    hashed_password = get_password_hash("testpassword")
    user = User(email="sharingtest@example.com", hashed_password=hashed_password)
    db.add(user)
    db.commit()

    # Generate access token
    access_token = create_access_token(data={"sub": user.email})

    # Create a new chat
    response = client.post(
        "/api/v1/chat/chats",
        json={"title": "Chat to Share"},
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    chat_id = response.json()["id"]

    # Add a message to the chat
    response = client.post(
        f"/api/v1/chat/chats/{chat_id}/messages",
        json={"role": "human", "content": "This is a message in a shared chat"},
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200

    # Add a response message
    response = client.post(
        f"/api/v1/chat/chats/{chat_id}/messages",
        json={"role": "assistant", "content": "This is a response in a shared chat"},
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200

    # Share the chat
    response = client.post(
        f"/api/v1/chat/chats/{chat_id}/share",
        json={"is_shared": True},
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    assert response.json()["is_shared"] == True

    # Get the shared chat without authentication
    response = client.get(f"/api/v1/chat/shared/{chat_id}")
    assert response.status_code == 200
    
    # Verify the content of the shared chat
    shared_chat = response.json()
    assert shared_chat["title"] == "Chat to Share"
    assert len(shared_chat["messages"]) == 2
    assert shared_chat["messages"][0]["content"] == "This is a message in a shared chat"
    assert shared_chat["messages"][1]["content"] == "This is a response in a shared chat"

def test_anonymous_user_shared_chat_limit(client, db):
    # 1. Create a user and share a chat
    # Create a test user
    hashed_password = get_password_hash("testpassword")
    user = User(email="sharelimituser@example.com", hashed_password=hashed_password)
    db.add(user)
    db.commit()

    # Generate access token
    access_token = create_access_token(data={"sub": user.email})

    # Create a new chat
    response = client.post(
        "/api/v1/chat/chats",
        json={"title": "Shared Chat with Limit Test"},
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    chat_id = response.json()["id"]

    # Add a message to the chat
    response = client.post(
        f"/api/v1/chat/chats/{chat_id}/messages",
        json={"role": "human", "content": "Initial shared message"},
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200

    # Add a response message
    response = client.post(
        f"/api/v1/chat/chats/{chat_id}/messages",
        json={"role": "assistant", "content": "Initial AI response"},
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200

    # Share the chat
    response = client.post(
        f"/api/v1/chat/chats/{chat_id}/share",
        json={"is_shared": True},
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    assert response.json()["is_shared"] == True

    # 2. Anonymous user accesses the shared chat
    anonymous_session_id = "test-anonymous-session-id"
    
    # Verify the anonymous user can access the shared chat
    response = client.get(f"/api/v1/chat/shared/{chat_id}")
    assert response.status_code == 200
    shared_chat = response.json()
    assert shared_chat["title"] == "Shared Chat with Limit Test"
    
    # 3. Anonymous user continues the conversation - should be allowed 5 messages
    
    # Mock the Redis message counter (normally incremented by the service)
    with patch("app.services.chat_management.get_anonymous_message_count") as mock_get_count, \
         patch("app.services.chat_management.increment_anonymous_message_count") as mock_increment:
        
        # Message 1 - Should be allowed
        mock_get_count.return_value = 0
        response = client.post(
            "/api/v1/chatbot/chat",
            json={"message": "Anonymous message 1", "chat_id": chat_id},
            headers={"x-anonymous-session-id": anonymous_session_id}
        )
        assert response.status_code == 200
        assert response.json().get("limit_reached") == False
        
        # Message 2 - Should be allowed
        mock_get_count.return_value = 1
        response = client.post(
            "/api/v1/chatbot/chat",
            json={"message": "Anonymous message 2", "chat_id": chat_id},
            headers={"x-anonymous-session-id": anonymous_session_id}
        )
        assert response.status_code == 200
        assert response.json().get("limit_reached") == False
        
        # Message 3 - Should be allowed
        mock_get_count.return_value = 2
        response = client.post(
            "/api/v1/chatbot/chat",
            json={"message": "Anonymous message 3", "chat_id": chat_id},
            headers={"x-anonymous-session-id": anonymous_session_id}
        )
        assert response.status_code == 200
        assert response.json().get("limit_reached") == False
        
        # Message 4 - Should be allowed
        mock_get_count.return_value = 3
        response = client.post(
            "/api/v1/chatbot/chat",
            json={"message": "Anonymous message 4", "chat_id": chat_id},
            headers={"x-anonymous-session-id": anonymous_session_id}
        )
        assert response.status_code == 200
        assert response.json().get("limit_reached") == False
        
        # Message 5 - Should be allowed (5th message)
        mock_get_count.return_value = 4
        response = client.post(
            "/api/v1/chatbot/chat",
            json={"message": "Anonymous message 5", "chat_id": chat_id},
            headers={"x-anonymous-session-id": anonymous_session_id}
        )
        assert response.status_code == 200
        assert response.json().get("limit_reached") == False
        
        # Message 6 - Should hit the limit
        mock_get_count.return_value = 5
        response = client.post(
            "/api/v1/chatbot/chat",
            json={"message": "Anonymous message 6 - should hit limit", "chat_id": chat_id},
            headers={"x-anonymous-session-id": anonymous_session_id}
        )
        assert response.status_code == 200
        assert response.json().get("limit_reached") == True
        assert "Message limit reached" in response.json().get("answer", "")
    
    # 4. Test sign-in to continue chat
    # Create a new user that will "sign in" after being anonymous
    new_user_password = "newuserpassword"
    new_user_email = "newuser@example.com"
    hashed_password = get_password_hash(new_user_password)
    new_user = User(email=new_user_email, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    
    # Login as the new user
    login_response = client.post(
        "/api/v1/auth/login",
        data={
            "username": new_user_email,
            "password": new_user_password
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert login_response.status_code == 200
    new_user_token = login_response.json()["access_token"]
    
    # For testing purposes, we create a new chat here
    # In production, this wouldn't be necessary as the authentication system
    # would associate the anonymous session with the newly logged-in user
    response = client.post(
        "/api/v1/chat/chats",
        json={"title": "New chat after login"},
        headers={"Authorization": f"Bearer {new_user_token}"}
    )
    assert response.status_code == 200
    new_chat_id = response.json()["id"]
    
    # Continue the conversation as authenticated user with the new chat
    response = client.post(
        "/api/v1/chatbot/chat",
        json={"message": "Continuing after login", "chat_id": new_chat_id},
        headers={"Authorization": f"Bearer {new_user_token}"}
    )
    assert response.status_code == 200
    
    # Verify user can now interact with the chat without limits
    response_data = response.json()
    assert "answer" in response_data
    assert response_data.get("chat_id") == new_chat_id
