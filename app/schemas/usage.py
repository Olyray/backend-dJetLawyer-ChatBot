from pydantic import BaseModel
from datetime import datetime
import uuid

class TokenUsageCreate(BaseModel):
    user_id: uuid.UUID
    tokens_used: int

class TokenUsage(TokenUsageCreate):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True

class MonthlyUsage(BaseModel):
    month: datetime
    avg_tokens: float

class UserMonthlyUsage(BaseModel):
    month: datetime
    total_tokens: int
