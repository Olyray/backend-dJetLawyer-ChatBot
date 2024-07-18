import pytest
from app.models.user import User
from app.core.security import create_access_token
from app.services.auth import get_password_hash

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
