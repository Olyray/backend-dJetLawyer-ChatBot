from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user, get_rate_limiter
from app.services.subscription import (
    get_user_subscription,
    is_user_premium,
    activate_premium_subscription,
    cancel_subscription,
    update_subscription_from_payment_webhook
)
from app.models.user import User
from app.schemas.user import SubscriptionDetails
from pydantic import BaseModel
from typing import Optional
from fastapi_limiter.depends import RateLimiter

router = APIRouter()

class SubscriptionActivationRequest(BaseModel):
    payment_reference: str
    duration_months: int = 1
    auto_renew: bool = True

class PaymentWebhookRequest(BaseModel):
    payment_reference: str
    status: str
    metadata: Optional[dict] = None

@router.get("/current", response_model=SubscriptionDetails)
async def get_current_subscription(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter)
):
    """
    Get current user's subscription details
    """
    await rate_limiter(request, response)
    return get_user_subscription(db, current_user.id)

@router.get("/verify-premium")
async def verify_premium_status(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter)
):
    """
    Verify if the current user has premium status
    Used by frontend to verify premium features access
    """
    await rate_limiter(request, response)
    is_premium = is_user_premium(db, current_user.id)
    return {
        "isPremium": is_premium,
        "planType": current_user.subscription_plan.value if current_user.subscription_plan else "free"
    }

@router.post("/activate", response_model=SubscriptionDetails)
async def activate_subscription(
    subscription_data: SubscriptionActivationRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter)
):
    """
    Activate premium subscription for the current user
    Called after successful payment
    """
    await rate_limiter(request, response)
    return activate_premium_subscription(
        db,
        current_user.id,
        subscription_data.payment_reference,
        subscription_data.duration_months,
        subscription_data.auto_renew
    )

@router.post("/cancel", response_model=SubscriptionDetails)
async def cancel_current_subscription(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter)
):
    """
    Cancel the current user's subscription
    Subscription will remain active until expiry date
    """
    await rate_limiter(request, response)
    return cancel_subscription(db, current_user.id)

@router.post("/webhook", status_code=status.HTTP_200_OK)
async def payment_webhook(
    webhook_data: PaymentWebhookRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    rate_limiter: RateLimiter = Depends(get_rate_limiter)
):
    """
    Webhook endpoint for payment provider
    Updates subscription status based on payment status
    """
    await rate_limiter(request, response)
    result = update_subscription_from_payment_webhook(
        db,
        webhook_data.payment_reference,
        webhook_data.status
    )
    
    if not result:
        return {"status": "warning", "message": "No matching user found for payment reference"}
    
    return {"status": "success", "message": "Subscription updated successfully"} 