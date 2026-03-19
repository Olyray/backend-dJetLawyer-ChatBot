import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.core.config import settings
from main import app
from fastapi.testclient import TestClient
from app.core.deps import get_db, get_rate_limiter
from app.models.user import User, SubscriptionPlanType
from app.models.chat import Chat, Message
from app.models.attachment import Attachment
from app.models.subscription_history import SubscriptionHistory
from app.models.token_usage import TokenUsage
from app.models.webhook_log import WebhookLog
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, ANY


@pytest.fixture(scope="session")
def engine():
    return create_engine(settings.TEST_DATABASE_URL)

@pytest.fixture(scope="session")
def TestingSessionLocal(engine):
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db(TestingSessionLocal):
    connection = TestingSessionLocal()
    yield connection
    connection.close()

@pytest.fixture
def client(db, monkeypatch):
    async def no_rate_limit(request=None, response=None):
        return None

    async def no_setup_rate_limiter():
        return None

    async def no_subscription_job(*args, **kwargs):
        return None

    def override_get_db():
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_rate_limiter] = lambda: no_rate_limit
    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr("main.setup_rate_limiter", no_setup_rate_limiter)
    monkeypatch.setattr("main.run_subscription_expiry_job", no_subscription_job)
    monkeypatch.setattr("main.expire_subscriptions", lambda: None)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def make_premium_user(db):
    def _make_premium(user: User) -> User:
        user.subscription_plan = SubscriptionPlanType.PREMIUM
        user.subscription_start_date = datetime.utcnow() - timedelta(days=1)
        user.subscription_expiry_date = datetime.utcnow() + timedelta(days=30)
        user.subscription_auto_renew = True
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _make_premium


@pytest.fixture
def mocker():
    patchers = []

    class SimpleMocker:
        ANY = ANY
        Mock = MagicMock

        def patch(self, target, *args, **kwargs):
            patcher = patch(target, *args, **kwargs)
            mocked = patcher.start()
            patchers.append(patcher)
            return mocked

    helper = SimpleMocker()
    try:
        yield helper
    finally:
        while patchers:
            patchers.pop().stop()


@pytest.fixture(autouse=True)
def mock_anonymous_chat_store(monkeypatch):
    counts = {}
    chats = {}

    async def get_anonymous_message_count(session_id: str):
        return counts.get(session_id, 0)

    async def increment_anonymous_message_count(session_id: str):
        counts[session_id] = counts.get(session_id, 0) + 1
        return counts[session_id]

    async def get_anonymous_chat_messages(session_id: str, chat_id: str):
        return chats.get((session_id, chat_id), [])

    async def save_anonymous_chat_messages(session_id: str, chat_id: str, messages):
        chats[(session_id, chat_id)] = messages

    async def clear_anonymous_session(session_id: str):
        keys = [key for key in chats if key[0] == session_id]
        for key in keys:
            del chats[key]
        counts.pop(session_id, None)

    monkeypatch.setattr("app.services.anonymous_chat.get_anonymous_message_count", get_anonymous_message_count)
    monkeypatch.setattr("app.services.anonymous_chat.increment_anonymous_message_count", increment_anonymous_message_count)
    monkeypatch.setattr("app.services.anonymous_chat.get_anonymous_chat_messages", get_anonymous_chat_messages)
    monkeypatch.setattr("app.services.anonymous_chat.save_anonymous_chat_messages", save_anonymous_chat_messages)
    monkeypatch.setattr("app.services.anonymous_chat.clear_anonymous_session", clear_anonymous_session)

    monkeypatch.setattr("app.services.chat_management.get_anonymous_message_count", get_anonymous_message_count)
    monkeypatch.setattr("app.services.chat_management.increment_anonymous_message_count", increment_anonymous_message_count)
    monkeypatch.setattr("app.services.chat_management.get_anonymous_chat_messages", get_anonymous_chat_messages)
    monkeypatch.setattr("app.services.chat_processing.save_anonymous_chat_messages", save_anonymous_chat_messages)
    monkeypatch.setattr("app.api.chatbot.get_anonymous_chat_messages", get_anonymous_chat_messages)

@pytest.fixture(autouse=True)
def clear_db(db):
    db.query(Attachment).delete()
    db.query(WebhookLog).delete()
    db.query(TokenUsage).delete()
    db.query(SubscriptionHistory).delete()
    db.query(Message).delete()
    db.query(Chat).delete()
    db.query(User).delete()
    db.commit()
