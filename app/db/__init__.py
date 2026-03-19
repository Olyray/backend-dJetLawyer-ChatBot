from .base import Base
from .session import engine

# Import all models here
from app.models.user import User
from app.models.chat import Chat, Message
from app.models.token_usage import TokenUsage
from app.models.attachment import Attachment
from app.models.subscription_history import SubscriptionHistory
from app.models.webhook_log import WebhookLog

# Create all tables in the engine
Base.metadata.create_all(bind=engine)
