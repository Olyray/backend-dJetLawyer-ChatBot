from .base import Base
from .session import engine

# Import all models here
from app.models.user import User
from app.models.chat import Chat, Message
from app.models.token_usage import TokenUsage

# Create all tables in the engine
Base.metadata.create_all(bind=engine)
