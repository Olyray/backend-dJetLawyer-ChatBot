from pydantic import BaseModel, UUID4, EmailStr, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class PaymentStatus(str, Enum):
    SUCCESSFUL = "successful"
    FAILED = "failed"
    PENDING = "pending"
    REFUNDED = "refunded"


class SubscriptionEvent(str, Enum):
    SUBSCRIPTION_CREATE = "subscription.create"
    CHARGE_SUCCESS = "charge.success" 
    INVOICE_CREATE = "invoice.create"
    INVOICE_PAYMENT_FAILED = "invoice.payment_failed"
    INVOICE_UPDATE = "invoice.update"
    SUBSCRIPTION_NOT_RENEW = "subscription.not_renew"
    SUBSCRIPTION_DISABLE = "subscription.disable"


class CancellationRequest(BaseModel):
    reason: Optional[str] = None


class SubscriptionHistoryBase(BaseModel):
    payment_reference: str
    amount: int
    payment_status: PaymentStatus
    payment_date: datetime
    plan_type: str
    duration_months: int = 1


class SubscriptionHistoryCreate(SubscriptionHistoryBase):
    user_id: UUID4
    event_type: Optional[SubscriptionEvent] = None
    next_payment_date: Optional[datetime] = None
    payment_method: Optional[str] = None
    transaction_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    cancellation_reason: Optional[str] = None


class SubscriptionHistory(SubscriptionHistoryBase):
    id: UUID4
    user_id: UUID4
    event_type: Optional[SubscriptionEvent] = None
    next_payment_date: Optional[datetime] = None
    payment_method: Optional[str] = None
    transaction_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    cancellation_reason: Optional[str] = None

    class Config:
        orm_mode = True


class SubscriptionHistoryPaginated(BaseModel):
    total: int
    items: List[SubscriptionHistory]


class SubscriptionDetailsExtended(BaseModel):
    planType: str
    startDate: Optional[datetime] = None
    expiryDate: Optional[datetime] = None
    autoRenew: bool
    cancellationDate: Optional[datetime] = None
    cancellationReason: Optional[str] = None
    remainingDays: Optional[int] = None
    
    @validator('remainingDays', always=True)
    def calculate_remaining_days(cls, v, values):
        expiry = values.get('expiryDate')
        if not expiry:
            return 0
        
        now = datetime.utcnow()
        if expiry < now:
            return 0
        
        remaining = (expiry - now).days
        return remaining if remaining > 0 else 0 