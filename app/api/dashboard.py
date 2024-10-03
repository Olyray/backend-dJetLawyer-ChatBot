from fastapi import APIRouter, Depends, HTTPException
from app.services import usage_analytics
from app.core.deps import get_current_user
from app.models.user import User
from typing import List, Optional
from app.schemas.usage import MonthlyUsage, UserMonthlyUsage, TokenUsage
from uuid import UUID

router = APIRouter()

def get_admin_user(current_user: User = Depends(get_current_user)):
    if not current_user.admin_user:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

@router.get("/monthly-average", response_model=List[MonthlyUsage])
def get_monthly_average_usage(admin_user: User = Depends(get_admin_user)):
    return usage_analytics.get_monthly_average_usage()

@router.get("/user-monthly-usage", response_model=List[UserMonthlyUsage])
def get_user_monthly_usage(user_id: Optional[UUID] = None, admin_user: User = Depends(get_admin_user)):
    if user_id:
        return usage_analytics.get_user_monthly_usage(user_id)
    return usage_analytics.get_user_monthly_usage(admin_user.id)

@router.get("/recent-token-usage", response_model=List[TokenUsage])
def get_recent_token_usage(user_id: Optional[UUID] = None, admin_user: User = Depends(get_admin_user)):
    if user_id:
        return usage_analytics.get_recent_token_usage(user_id)
    return usage_analytics.get_recent_token_usage(admin_user.id)
