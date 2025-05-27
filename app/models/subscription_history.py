from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey
from app.db.base import Base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
import enum


class PaymentStatus(str, enum.Enum):
    SUCCESSFUL = "successful"
    FAILED = "failed"
    PENDING = "pending"
    REFUNDED = "refunded"


class SubscriptionEvent(str, enum.Enum):
    SUBSCRIPTION_CREATE = "subscription.create"
    CHARGE_SUCCESS = "charge.success" 
    INVOICE_CREATE = "invoice.create"
    INVOICE_PAYMENT_FAILED = "invoice.payment_failed"
    INVOICE_UPDATE = "invoice.update"
    SUBSCRIPTION_NOT_RENEW = "subscription.not_renew"
    SUBSCRIPTION_DISABLE = "subscription.disable"


class SubscriptionHistory(Base):
    __tablename__ = "subscription_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    user = relationship("User", back_populates="subscription_history")
    
    # Payment details
    payment_reference = Column(String, unique=True, index=True)
    amount = Column(Integer)  # Amount in kobo (smallest currency unit)
    payment_status = Column(Enum(PaymentStatus, values_callable=lambda x: [e.value for e in x]), default=PaymentStatus.PENDING)
    payment_date = Column(DateTime)
    
    # Subscription details
    event_type = Column(Enum(SubscriptionEvent, values_callable=lambda x: [e.value for e in x]), nullable=True)
    next_payment_date = Column(DateTime, nullable=True)
    plan_type = Column(String)
    duration_months = Column(Integer, default=1)
    
    # Additional metadata
    payment_method = Column(String, nullable=True)
    transaction_id = Column(String, nullable=True)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    
    # Cancellation details
    cancellation_reason = Column(String, nullable=True) 