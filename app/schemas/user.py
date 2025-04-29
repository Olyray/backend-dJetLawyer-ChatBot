from pydantic import BaseModel, EmailStr
import uuid
from datetime import datetime
from typing import Optional
from enum import Enum

class SubscriptionPlanType(str, Enum):
    FREE = "free"
    PREMIUM = "premium"

class SubscriptionDetails(BaseModel):
    planType: SubscriptionPlanType
    startDate: Optional[datetime] = None
    expiryDate: Optional[datetime] = None
    autoRenew: bool = False

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserLogin(UserBase):
    password: str

class UserInDB(UserBase):
    id: uuid.UUID
    is_active: bool
    google_id: Optional[str] = None
    is_verified: bool = False
    subscription_plan: SubscriptionPlanType = SubscriptionPlanType.FREE
    subscription_start_date: Optional[datetime] = None
    subscription_expiry_date: Optional[datetime] = None
    subscription_auto_renew: bool = False

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    subscription: Optional[SubscriptionDetails] = None

class GoogleToken(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user: UserCreate
    subscription: Optional[SubscriptionDetails] = None

class RefreshToken(BaseModel):
    refresh_token: str

class GoogleLoginRequest(BaseModel):
    token: str
