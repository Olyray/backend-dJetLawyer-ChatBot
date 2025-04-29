from sqlalchemy.orm import Session
from app.models.user import User, SubscriptionPlanType
from datetime import datetime, timedelta
from fastapi import HTTPException, status
import uuid
from typing import Optional


def get_user_subscription(db: Session, user_id: uuid.UUID):
    """
    Get subscription details for a user
    
    Args:
        db (Session): Database session
        user_id (uuid.UUID): ID of the user
        
    Returns:
        dict: Subscription details
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "planType": user.subscription_plan.value if user.subscription_plan else "free",
        "startDate": user.subscription_start_date,
        "expiryDate": user.subscription_expiry_date,
        "autoRenew": user.subscription_auto_renew,
    }


def is_user_premium(db: Session, user_id: uuid.UUID) -> bool:
    """
    Check if a user has an active premium subscription
    
    Args:
        db (Session): Database session
        user_id (uuid.UUID): ID of the user
        
    Returns:
        bool: True if user has an active premium subscription
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False
    
    # Check if user has a premium subscription
    if user.subscription_plan != SubscriptionPlanType.PREMIUM:
        return False
    
    # Check if subscription is active (not expired)
    if user.subscription_expiry_date and user.subscription_expiry_date < datetime.utcnow():
        return False
    
    return True


def activate_premium_subscription(
    db: Session, 
    user_id: uuid.UUID, 
    payment_reference: str,
    duration_months: int = 1,
    auto_renew: bool = True
) -> dict:
    """
    Activate premium subscription for a user
    
    Args:
        db (Session): Database session
        user_id (uuid.UUID): ID of the user
        payment_reference (str): Reference from payment provider
        duration_months (int): Duration of subscription in months
        auto_renew (bool): Whether to auto-renew the subscription
        
    Returns:
        dict: Updated subscription details
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Set subscription details
    start_date = datetime.utcnow()
    expiry_date = start_date + timedelta(days=30 * duration_months)
    
    # Update user record
    user.subscription_plan = SubscriptionPlanType.PREMIUM
    user.subscription_start_date = start_date
    user.subscription_expiry_date = expiry_date
    user.subscription_auto_renew = auto_renew
    user.payment_reference = payment_reference
    
    db.commit()
    db.refresh(user)
    
    return {
        "planType": user.subscription_plan.value,
        "startDate": user.subscription_start_date,
        "expiryDate": user.subscription_expiry_date,
        "autoRenew": user.subscription_auto_renew,
    }


def cancel_subscription(db: Session, user_id: uuid.UUID) -> dict:
    """
    Cancel a user's subscription
    
    Args:
        db (Session): Database session
        user_id (uuid.UUID): ID of the user
        
    Returns:
        dict: Updated subscription details
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Allow subscription to continue until expiry date, but disable auto-renew
    user.subscription_auto_renew = False
    
    db.commit()
    db.refresh(user)
    
    return {
        "planType": user.subscription_plan.value,
        "startDate": user.subscription_start_date,
        "expiryDate": user.subscription_expiry_date,
        "autoRenew": user.subscription_auto_renew,
    }


def update_subscription_from_payment_webhook(
    db: Session, 
    payment_reference: str,
    status: str
) -> Optional[dict]:
    """
    Update subscription status based on payment webhook
    
    Args:
        db (Session): Database session
        payment_reference (str): Payment reference from payment gateway
        status (str): Payment status (success, failed, etc.)
        
    Returns:
        dict or None: Updated subscription details if user found
    """
    user = db.query(User).filter(User.payment_reference == payment_reference).first()
    if not user:
        return None
    
    if status.lower() == "success":
        # Payment successful, ensure subscription is active
        if user.subscription_plan != SubscriptionPlanType.PREMIUM:
            user.subscription_plan = SubscriptionPlanType.PREMIUM
            user.subscription_start_date = datetime.utcnow()
            user.subscription_expiry_date = datetime.utcnow() + timedelta(days=30)
    elif status.lower() in ["failed", "cancelled"]:
        # Payment failed, revert to free plan if this was an initial subscription
        # If it's a renewal failure, we'll let it expire naturally
        if not user.subscription_expiry_date or user.subscription_expiry_date < datetime.utcnow():
            user.subscription_plan = SubscriptionPlanType.FREE
            user.subscription_expiry_date = None
    
    db.commit()
    db.refresh(user)
    
    return {
        "planType": user.subscription_plan.value,
        "startDate": user.subscription_start_date,
        "expiryDate": user.subscription_expiry_date,
        "autoRenew": user.subscription_auto_renew,
    } 