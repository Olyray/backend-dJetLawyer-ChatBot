from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Header
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user, get_rate_limiter
from app.services.subscription import (
    get_user_subscription,
    is_user_premium,
    activate_premium_subscription,
    cancel_subscription,
    initialize_subscription,
    verify_payment,
    process_subscription_event,
    verify_webhook_signature
)
from app.models.user import User
from app.schemas.user import SubscriptionDetails
from pydantic import BaseModel
from typing import Optional, Dict, Any
from fastapi_limiter.depends import RateLimiter
import json

router = APIRouter()

class SubscriptionActivationRequest(BaseModel):
    payment_reference: str
    duration_months: int = 1
    auto_renew: bool = True

class PaymentVerificationResponse(BaseModel):
    verified: bool
    message: str
    amount: Optional[int] = None

class WebhookEventData(BaseModel):
    """
    Model for Paystack webhook event data
    
    According to Paystack docs, these events include:
    - subscription.create: Subscription was created for the customer
    - charge.success: Transaction was successful
    - invoice.create: Charge attempt will be made (sent 3 days before next payment)
    - invoice.payment_failed: Charge attempt failed
    - invoice.update: Final status of the invoice after charge attempt
    - subscription.not_renew: Subscription will not renew on next payment date
    - subscription.disable: Subscription has been cancelled or completed
    """
    event: str
    data: Dict[str, Any]

@router.get("/status", response_model=SubscriptionDetails)
async def get_subscription_status(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter)
):
    """
    Get the current user's subscription status
    """
    await rate_limiter(request, response)
    return get_user_subscription(db, current_user.id)

@router.get("/is-premium", response_model=bool)
async def check_premium_status(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter)
):
    """
    Check if the current user has an active premium subscription
    Used for quick checks in frontend
    """
    await rate_limiter(request, response)
    return is_user_premium(db, current_user.id)

@router.post("/initialize", response_model=Dict[str, Any])
async def initialize_new_subscription(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter)
):
    """
    Initialize a new subscription for the current user
    Returns payment authorization URL
    """
    await rate_limiter(request, response)
    return initialize_subscription(db, current_user.id)

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
    print(f"Activating subscription for user {current_user.id} with reference: {subscription_data.payment_reference}")
    return activate_premium_subscription(
        db,
        current_user.id,
        subscription_data.payment_reference,
        subscription_data.duration_months,
        subscription_data.auto_renew
    )

@router.post("/cancel", response_model=SubscriptionDetails)
async def cancel_user_subscription(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter)
):
    """
    Cancel the current user's subscription
    Will keep active until expiry date but disable auto-renewal
    """
    await rate_limiter(request, response)
    return cancel_subscription(db, current_user.id)

@router.post("/webhook", status_code=status.HTTP_200_OK)
async def subscription_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_paystack_signature: str = Header(None)
):
    """
    Webhook endpoint for Paystack events system
    
    This endpoint handles various events from Paystack including:
    - subscription.create: When a subscription is created
    - charge.success: When a payment is successful
    - invoice.create: 3 days before next payment
    - invoice.payment_failed: When payment fails
    - invoice.update: Final status after charge attempt
    - subscription.not_renew: When subscription won't renew
    - subscription.disable: When subscription is disabled/completed
    """
    # Get the raw request body
    payload = await request.body()
    
    # Verify that the request is coming from Paystack
    if not x_paystack_signature or not verify_webhook_signature(payload, x_paystack_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature"
        )
    print('Webhook received')
    # Paystack sends the event as JSON
    try:
        event_data = json.loads(payload)
    except json.JSONDecodeError:
        return {"status": "error", "message": "Invalid JSON payload"}
    
    # Basic validation of the event data
    if not isinstance(event_data, dict):
        return {"status": "error", "message": "Invalid event data format"}
    
    event_type = event_data.get("event")
    if not event_type:
        return {"status": "error", "message": "Missing event type"}
    
    data = event_data.get("data")
    if not data:
        return {"status": "error", "message": "Missing event data"}
    
    # Process the event
    result = process_subscription_event(db, event_data)
    
    if not result:
        return {"status": "warning", "message": "No action taken for this event"}
    
    response_message = f"Processed {event_type} event successfully"
    if result.get("status") == "notification_scheduled":
        response_message = "Payment reminder notification scheduled"
    elif result.get("status") == "payment_failed":
        response_message = "Payment failure recorded"
    
    return {
        "status": "success",
        "message": response_message,
        "event_type": event_type
    }

@router.get("/verify/{payment_reference}", response_model=PaymentVerificationResponse)
async def verify_payment_status(
    payment_reference: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter)
):
    """
    Verify a payment transaction with Paystack
    Used after payment to confirm payment was successful
    """
    await rate_limiter(request, response)
    result = verify_payment(payment_reference)
    
    if result["verified"]:
        # If payment is verified, we could automatically activate the subscription here
        # Or we can leave that to a separate activate call
        return result
    
    return result 