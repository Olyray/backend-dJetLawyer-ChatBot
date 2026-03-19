from sqlalchemy import Column, String, DateTime, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.base import Base
import uuid
from datetime import datetime


class WebhookLog(Base):
    __tablename__ = "webhook_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    received_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Event metadata
    event_type = Column(String, nullable=True, index=True)
    paystack_signature = Column(String, nullable=True)
    signature_valid = Column(Boolean, nullable=False)

    # Full raw payload for complete audit trail
    raw_payload = Column(JSONB, nullable=True)

    # Extracted key fields for quick querying
    customer_email = Column(String, nullable=True, index=True)
    payment_reference = Column(String, nullable=True, index=True)

    # Processing outcome
    processed_successfully = Column(Boolean, nullable=True)
    processing_result = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
