from fastapi import APIRouter, Depends, HTTPException, Query
from app.services import usage_analytics
from app.core.deps import get_current_user, get_db
from app.models.user import User, SubscriptionPlanType
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from app.schemas.usage import MonthlyUsage, UserMonthlyUsage, TokenUsage
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel

router = APIRouter()

# Response models for user lists
class UserSummary(BaseModel):
    id: UUID
    email: str
    subscription_plan: str
    subscription_expiry_date: Optional[datetime]
    subscription_auto_renew: bool
    subscription_start_date: Optional[datetime]
    
    class Config:
        from_attributes = True

class UserDetail(BaseModel):
    id: UUID
    email: str
    subscription_plan: str
    subscription_expiry_date: Optional[datetime]
    subscription_auto_renew: bool
    subscription_start_date: Optional[datetime]
    admin_user: bool
    is_active: bool
    
    class Config:
        from_attributes = True

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

@router.get("/user-stats", response_model=Dict[str, Any])
def get_user_stats(db: Session = Depends(get_db), admin_user: User = Depends(get_admin_user)):
    """
    Get comprehensive user statistics including total users, subscribed users, and subscription details
    """
    # Total users
    total_users = db.query(User).count()
    
    # Current premium subscribers (active subscriptions)
    now = datetime.utcnow()
    active_premium_users = db.query(User).filter(
        User.subscription_plan == SubscriptionPlanType.PREMIUM,
        User.subscription_expiry_date > now
    ).count()
    
    # All users with premium plan (including expired)
    total_premium_users = db.query(User).filter(
        User.subscription_plan == SubscriptionPlanType.PREMIUM
    ).count()
    
    # Premium users with auto-renew enabled
    auto_renew_count = db.query(User).filter(
        User.subscription_plan == SubscriptionPlanType.PREMIUM,
        User.subscription_auto_renew == True,
        User.subscription_expiry_date > now
    ).count()
    
    # Recently expired (within last 7 days)
    from datetime import timedelta
    seven_days_ago = now - timedelta(days=7)
    recently_expired = db.query(User).filter(
        User.subscription_plan == SubscriptionPlanType.PREMIUM,
        User.subscription_expiry_date < now,
        User.subscription_expiry_date > seven_days_ago
    ).count()
    
    # Cancelled subscriptions (still active but won't renew)
    cancelled_active = db.query(User).filter(
        User.subscription_plan == SubscriptionPlanType.PREMIUM,
        User.subscription_expiry_date > now,
        User.subscription_auto_renew == False
    ).count()
    
    return {
        "total_users": total_users,
        "active_premium_subscribers": active_premium_users,
        "total_premium_users": total_premium_users,
        "auto_renew_enabled": auto_renew_count,
        "recently_expired": recently_expired,
        "cancelled_but_active": cancelled_active,
        "free_users": total_users - total_premium_users
    }

@router.get("/users", response_model=List[UserSummary])
def get_users(
    category: Optional[str] = Query(None, description="Filter category: all, active_subscribers, free, auto_renew, recently_expired, cancelled_active, all_premium"),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    Get list of users filtered by category
    """
    query = db.query(User)
    now = datetime.utcnow()
    
    if category == "active_subscribers":
        query = query.filter(
            User.subscription_plan == SubscriptionPlanType.PREMIUM,
            User.subscription_expiry_date > now
        )
    elif category == "free":
        query = query.filter(User.subscription_plan == SubscriptionPlanType.FREE)
    elif category == "auto_renew":
        query = query.filter(
            User.subscription_plan == SubscriptionPlanType.PREMIUM,
            User.subscription_auto_renew == True,
            User.subscription_expiry_date > now
        )
    elif category == "recently_expired":
        from datetime import timedelta
        seven_days_ago = now - timedelta(days=7)
        query = query.filter(
            User.subscription_plan == SubscriptionPlanType.PREMIUM,
            User.subscription_expiry_date < now,
            User.subscription_expiry_date > seven_days_ago
        )
    elif category == "cancelled_active":
        query = query.filter(
            User.subscription_plan == SubscriptionPlanType.PREMIUM,
            User.subscription_expiry_date > now,
            User.subscription_auto_renew == False
        )
    elif category == "all_premium":
        query = query.filter(User.subscription_plan == SubscriptionPlanType.PREMIUM)
    
    # Order by email for consistent ordering
    users = query.order_by(User.email).offset(offset).limit(limit).all()
    return users

@router.get("/users/{user_id}", response_model=UserDetail)
def get_user_detail(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    Get detailed information for a specific user
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.get("/users/{user_id}/usage", response_model=Dict[str, Any])
def get_user_usage_stats(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    Get usage statistics for a specific user
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get monthly usage for this user
    monthly_usage = usage_analytics.get_user_monthly_usage(user_id)
    
    # Get recent token usage
    recent_usage = usage_analytics.get_recent_token_usage(user_id)
    
    return {
        "user_id": str(user_id),
        "email": user.email,
        "monthly_usage": monthly_usage,
        "recent_usage": recent_usage
    }
