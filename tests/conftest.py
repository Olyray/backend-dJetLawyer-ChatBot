import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.core.config import settings
from main import app
from fastapi.testclient import TestClient
from app.core.deps import get_db
from app.models.user import User
from app.models.chat import Chat, Message
from alembic import command
from alembic.config import Config
from app.models.attachment import Attachment


@pytest.fixture(scope="session")
def apply_migrations():
    settings.TESTING = True
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")


@pytest.fixture(scope="session")
def engine():
    return create_engine(settings.TEST_DATABASE_URL)

@pytest.fixture(scope="session")
def TestingSessionLocal(engine, apply_migrations):
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db(TestingSessionLocal):
    connection = TestingSessionLocal()
    yield connection
    connection.close()

@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def clear_db(db):
    db.query(Attachment).delete()
    db.query(Message).delete()
    db.query(Chat).delete()
    db.query(User).delete()
    db.commit()
