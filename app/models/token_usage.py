from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base import Base

class TokenUsage(Base):
    __tablename__ = "tokenusage"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), index=True)
    tokens_used = Column(Integer)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
