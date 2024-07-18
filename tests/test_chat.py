from app.models.user import User
from app.models.chat import Chat
from app.core.security import create_access_token
from app.services.auth import get_password_hash

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
