from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum
from app.db.base import Base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
import enum


class SubscriptionPlanType(str, enum.Enum):
    FREE = "free"
    PREMIUM = "premium"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    google_id = Column(String, unique=True, nullable=True)
    chats = relationship("Chat", back_populates="user")
    is_verified = Column(Boolean, default=False)
    verification_token = Column(String, nullable=True)
    verification_token_expiry = Column(DateTime, nullable=True)
    admin_user = Column(Boolean, default=False)
    
    # Subscription fields
    subscription_plan = Column(Enum(SubscriptionPlanType), default=SubscriptionPlanType.FREE)
    subscription_start_date = Column(DateTime, nullable=True)
    subscription_expiry_date = Column(DateTime, nullable=True)
    subscription_auto_renew = Column(Boolean, default=True)
    payment_reference = Column(String, nullable=True)