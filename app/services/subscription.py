from sqlalchemy.orm import Session
from app.models.user import User, SubscriptionPlanType
from app.models.subscription_history import SubscriptionHistory, PaymentStatus, SubscriptionEvent
from datetime import datetime, timedelta
from fastapi import HTTPException, status
import uuid
from typing import Optional, Dict, Any, List
import requests
from app.core.config import settings


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
        "cancellationDate": user.cancellation_date,
        "cancellationReason": user.cancellation_reason,
        "remainingDays": calculate_remaining_days(user.subscription_expiry_date)
    }


def calculate_remaining_days(expiry_date: Optional[datetime]) -> int:
    """
    Calculate remaining days in subscription
    
    Args:
        expiry_date (datetime): Subscription expiry date
        
    Returns:
        int: Number of days remaining
    """
    if not expiry_date:
        return 0
    
    now = datetime.utcnow()
    if expiry_date < now:
        return 0
    
    remaining = (expiry_date - now).days
    return remaining if remaining > 0 else 0


def is_user_premium(db: Session, user_id: uuid.UUID) -> bool:
    """
    Check if a user has an active premium subscription
    
    Args:
        db (Session): Database session
        user_id (uuid.UUID): ID of the user
        
    Returns:
        bool: True if user has active premium subscription
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False
    
    # User must have premium plan
    if user.subscription_plan != SubscriptionPlanType.PREMIUM:
        return False
    
    # Subscription must not be expired
    if not user.subscription_expiry_date or user.subscription_expiry_date < datetime.utcnow():
        return False
    
    return True


def create_subscription_plan() -> Dict[str, Any]:
    """
    Create a Paystack subscription plan if it doesn't exist
    
    Returns:
        dict: Plan details including plan code
    """
    paystack_secret_key = settings.PAYSTACK_SECRET_KEY
    if not paystack_secret_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Paystack secret key not configured"
        )
    
    # First check if plan already exists
    headers = {
        "Authorization": f"Bearer {paystack_secret_key}",
        "Content-Type": "application/json"
    }
    
    # Get list of plans
    response = requests.get(
        "https://api.paystack.co/plan",
        headers=headers
    )
    
    if response.status_code == 200:
        plans = response.json().get("data", [])
        
        # Look for a plan with the right name and amount
        for plan in plans:
            if (plan.get("name") == "dJetLawyer Premium" and 
                plan.get("amount") == settings.SUBSCRIPTION_PRICE_NAIRA * 100):
                return {
                    "plan_code": plan.get("plan_code"),
                    "name": plan.get("name"),
                    "amount": plan.get("amount"),
                    "interval": plan.get("interval")
                }
    
    # If we get here, we need to create the plan
    payload = {
        "name": "dJetLawyer Premium",
        "interval": "monthly",
        "amount": settings.SUBSCRIPTION_PRICE_NAIRA * 100,  # Amount in kobo
        "currency": "NGN",
        "description": "Premium subscription for dJetLawyer Chatbot"
    }
    
    response = requests.post(
        "https://api.paystack.co/plan",
        json=payload,
        headers=headers
    )
    
    if response.status_code != 201:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create subscription plan: {response.json().get('message')}"
        )
    
    plan_data = response.json().get("data", {})
    return {
        "plan_code": plan_data.get("plan_code"),
        "name": plan_data.get("name"),
        "amount": plan_data.get("amount"),
        "interval": plan_data.get("interval")
    }


def create_customer(email: str) -> str:
    """
    Create or get a Paystack customer
    
    Args:
        email (str): Customer email
        
    Returns:
        str: Customer code
    """
    paystack_secret_key = settings.PAYSTACK_SECRET_KEY
    if not paystack_secret_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Paystack secret key not configured"
        )
    
    # Check if customer already exists
    headers = {
        "Authorization": f"Bearer {paystack_secret_key}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(
        f"https://api.paystack.co/customer?email={email}",
        headers=headers
    )
    
    if response.status_code == 200:
        customers = response.json().get("data", [])
        if customers:
            return customers[0].get("customer_code")
    
    # Create new customer
    payload = {
        "email": email,
        "first_name": "dJetLawyer",
        "last_name": "User"
    }
    
    response = requests.post(
        "https://api.paystack.co/customer",
        json=payload,
        headers=headers
    )
    
    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create customer: {response.json().get('message')}"
        )
    
    return response.json().get("data", {}).get("customer_code")


def initialize_subscription(db: Session, user_id: uuid.UUID) -> Dict[str, Any]:
    """
    Initialize a subscription for a user
    
    Args:
        db (Session): Database session
        user_id (uuid.UUID): ID of the user
        
    Returns:
        dict: Payment initialization data including authorization URL
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    paystack_secret_key = settings.PAYSTACK_SECRET_KEY
    if not paystack_secret_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Paystack secret key not configured"
        )
    
    # Get plan code
    plan = create_subscription_plan()
    
    # Get or create customer
    customer_code = create_customer(user.email)
    
    # Initialize transaction
    headers = {
        "Authorization": f"Bearer {paystack_secret_key}",
        "Content-Type": "application/json"
    }
    
    payment_reference = f"sub_{user_id}_{datetime.utcnow().timestamp()}"
    
    payload = {
        "customer": customer_code,
        "email": user.email,
        "plan": plan["plan_code"],
        "amount": plan["amount"],
        "reference": payment_reference
    }
    
    response = requests.post(
        "https://api.paystack.co/transaction/initialize",
        json=payload,
        headers=headers
    )
    
    if response.status_code != 200:
        print('The second 500 error')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize payment: {response.json().get('message')}"
        )
    
    data = response.json().get("data", {})
    
    # Save payment reference to user
    user.payment_reference = payment_reference
    db.commit()
    
    return {
        "authorization_url": data.get("authorization_url"),
        "access_code": data.get("access_code"),
        "reference": payment_reference
    }


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
    
    # Verify payment
    payment_verified = verify_payment(payment_reference)
    if not payment_verified.get("verified"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment verification failed"
        )
    
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


def cancel_subscription(db: Session, user_id: uuid.UUID, reason: Optional[str] = None) -> dict:
    """
    Cancel a user's subscription
    
    Args:
        db (Session): Database session
        user_id (uuid.UUID): ID of the user
        reason (str, optional): Reason for cancellation
        
    Returns:
        dict: Updated subscription details
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    paystack_secret_key = settings.PAYSTACK_SECRET_KEY
    if not paystack_secret_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Paystack secret key not configured"
        )
    
    # Disable subscription in Paystack
    # First get the subscription code by searching with email
    headers = {
        "Authorization": f"Bearer {paystack_secret_key}",
        "Content-Type": "application/json"
    }
    
    # Find subscriptions for this customer
    response = requests.get(
        f"https://api.paystack.co/subscription?customer={user.email}",
        headers=headers
    )
    
    if response.status_code == 200:
        subscriptions = response.json().get("data", [])
        for subscription in subscriptions:
            if subscription.get("status") == "active":
                # Disable the subscription
                subscription_code = subscription.get("subscription_code")
                
                disable_response = requests.post(
                    f"https://api.paystack.co/subscription/disable",
                    json={"code": subscription_code, "token": "token"},
                    headers=headers
                )
                
                if disable_response.status_code != 200:
                    # Log error but continue
                    print(f"Failed to disable Paystack subscription: {disable_response.text}")
    
    # Set cancellation date and reason
    user.cancellation_date = datetime.utcnow()
    user.cancellation_reason = reason
    
    # Allow subscription to continue until expiry date, but disable auto-renew
    user.subscription_auto_renew = False
    
    # Record cancellation in subscription history
    if user.payment_reference:
        # Check if we already have a record for this payment reference
        existing_record = db.query(SubscriptionHistory).filter(
            SubscriptionHistory.payment_reference == user.payment_reference
        ).first()
        
        if not existing_record:
            # Create a new history record
            history_record = SubscriptionHistory(
                user_id=user.id,
                payment_reference=user.payment_reference,
                amount=settings.SUBSCRIPTION_PRICE_NAIRA * 100,  # Convert to kobo
                payment_status=PaymentStatus.SUCCESSFUL,
                payment_date=user.subscription_start_date or datetime.utcnow(),
                event_type=SubscriptionEvent.SUBSCRIPTION_DISABLE,
                plan_type=user.subscription_plan.value,
                duration_months=1,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                cancellation_reason=reason
            )
            db.add(history_record)
    
    db.commit()
    db.refresh(user)
    
    return {
        "planType": user.subscription_plan.value,
        "startDate": user.subscription_start_date,
        "expiryDate": user.subscription_expiry_date,
        "autoRenew": user.subscription_auto_renew,
        "cancellationDate": user.cancellation_date,
        "cancellationReason": user.cancellation_reason,
        "remainingDays": calculate_remaining_days(user.subscription_expiry_date)
    }


def verify_payment(
    payment_reference: str,
) -> dict:
    """
    Verify a payment with Paystack
    
    Args:
        payment_reference (str): Payment reference to verify
        
    Returns:
        dict: Verification result with status
    """
    try:
        # Log the reference being verified
        print(f"Attempting to verify payment reference: {payment_reference}")
        
        # Get Paystack secret key from environment variables
        paystack_secret_key = settings.PAYSTACK_SECRET_KEY
        
        if not paystack_secret_key:
            return {"verified": False, "message": "Paystack secret key not configured"}
        
        # Make API request to Paystack to verify the transaction
        headers = {
            "Authorization": f"Bearer {paystack_secret_key}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"https://api.paystack.co/transaction/verify/{payment_reference}",
            headers=headers
        )
        
        # Parse response
        result = response.json()
        
        if response.status_code == 200 and result.get("status") == True:
            data = result.get("data", {})
            status = data.get("status")
            
            # Check if the transaction was successful
            if status == "success":
                return {"verified": True, "amount": data.get("amount"), "message": "Payment verified"}
        
        # Payment verification failed
        return {"verified": False, "message": result.get("message", "Payment verification failed")}
        
    except Exception as e:
        print(f"Error verifying payment: {str(e)}")
        return {"verified": False, "message": str(e)}


def process_subscription_event(db: Session, event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Process a Paystack event from the events system
    
    According to Paystack docs, these events include:
    - subscription.create: Subscription was created for the customer
    - charge.success: Transaction was successful
    - invoice.create: Charge attempt will be made (sent 3 days before next payment)
    - invoice.payment_failed: Charge attempt failed
    - invoice.update: Final status of the invoice after charge attempt
    - subscription.not_renew: Subscription will not renew on next payment date
    - subscription.disable: Subscription has been cancelled or completed
    
    Args:
        db (Session): Database session
        event_data (dict): Event data from webhook
        
    Returns:
        dict or None: Updated subscription details if applicable
    """
    event_type = event_data.get("event")
    data = event_data.get("data", {})
    
    if not event_type or not data:
        return None
    
    if event_type == "subscription.create":
        # New subscription created
        customer_email = data.get("customer", {}).get("email")
        subscription_code = data.get("subscription_code")
        plan = data.get("plan", {})
        
        if not customer_email:
            return None
        
        user = db.query(User).filter(User.email == customer_email).first()
        if not user:
            return None
        
        # Update user subscription details
        user.subscription_plan = SubscriptionPlanType.PREMIUM
        user.subscription_start_date = datetime.utcnow()
        user.subscription_expiry_date = datetime.utcnow() + timedelta(days=30)
        user.subscription_auto_renew = True
        
        db.commit()
        db.refresh(user)
        
        return {
            "planType": user.subscription_plan.value,
            "startDate": user.subscription_start_date,
            "expiryDate": user.subscription_expiry_date,
            "autoRenew": user.subscription_auto_renew,
        }
        
    elif event_type == "charge.success":
        # Successful payment (initial or recurring)
        customer_email = data.get("customer", {}).get("email")
        
        if not customer_email:
            return None
        
        user = db.query(User).filter(User.email == customer_email).first()
        if not user:
            return None
        
        # Extend subscription
        user.subscription_plan = SubscriptionPlanType.PREMIUM
        
        # If already have expiry date, extend from there, otherwise from now
        if user.subscription_expiry_date and user.subscription_expiry_date > datetime.utcnow():
            user.subscription_expiry_date = user.subscription_expiry_date + timedelta(days=30)
        else:
            user.subscription_start_date = datetime.utcnow()
            user.subscription_expiry_date = datetime.utcnow() + timedelta(days=30)
        
        db.commit()
        db.refresh(user)
        
        return {
            "planType": user.subscription_plan.value,
            "startDate": user.subscription_start_date,
            "expiryDate": user.subscription_expiry_date,
            "autoRenew": user.subscription_auto_renew,
        }
    
    elif event_type == "invoice.create":
        # Notification that a charge attempt will be made soon (3 days before)
        # We can use this to notify the user via email or in-app
        customer_email = data.get("customer", {}).get("email")
        
        if not customer_email:
            return None
        
        user = db.query(User).filter(User.email == customer_email).first()
        if not user:
            return None
        
        # Here you would implement notification logic
        # For example, sending an email that payment will be processed soon
        
        return {
            "status": "notification_scheduled",
            "message": "Payment reminder notification scheduled"
        }
    
    elif event_type == "invoice.payment_failed":
        # Payment attempt failed
        customer_email = data.get("customer", {}).get("email")
        
        if not customer_email:
            return None
        
        user = db.query(User).filter(User.email == customer_email).first()
        if not user:
            return None
        
        # Mark that there was a payment failure but don't change status yet
        # Could implement notification logic here
        
        return {
            "status": "payment_failed",
            "planType": user.subscription_plan.value,
            "expiryDate": user.subscription_expiry_date,
            "autoRenew": user.subscription_auto_renew,
        }
    
    elif event_type == "invoice.update":
        # Final status of invoice after charge attempt
        customer_email = data.get("customer", {}).get("email")
        invoice_status = data.get("status")
        
        if not customer_email:
            return None
        
        user = db.query(User).filter(User.email == customer_email).first()
        if not user:
            return None
        
        # Handle based on the invoice status
        if invoice_status == "success":
            # Payment was successful - similar to charge.success
            if user.subscription_expiry_date and user.subscription_expiry_date > datetime.utcnow():
                user.subscription_expiry_date = user.subscription_expiry_date + timedelta(days=30)
            else:
                user.subscription_start_date = datetime.utcnow()
                user.subscription_expiry_date = datetime.utcnow() + timedelta(days=30)
                
            db.commit()
            db.refresh(user)
            
        elif invoice_status == "failed":
            # Payment failed - no immediate action but could implement notification
            pass
            
        return {
            "planType": user.subscription_plan.value,
            "startDate": user.subscription_start_date,
            "expiryDate": user.subscription_expiry_date,
            "autoRenew": user.subscription_auto_renew,
            "invoiceStatus": invoice_status
        }
        
    elif event_type == "subscription.not_renew":
        # Subscription will not renew on next payment date
        customer_email = data.get("customer", {}).get("email")
        
        if not customer_email:
            return None
        
        user = db.query(User).filter(User.email == customer_email).first()
        if not user:
            return None
        
        # Set auto_renew to false
        user.subscription_auto_renew = False
        
        db.commit()
        db.refresh(user)
        
        return {
            "planType": user.subscription_plan.value,
            "startDate": user.subscription_start_date,
            "expiryDate": user.subscription_expiry_date,
            "autoRenew": user.subscription_auto_renew,
        }
        
    elif event_type == "subscription.disable":
        # Subscription has been cancelled or completed
        customer_email = data.get("customer", {}).get("email")
        status = data.get("status")
        
        if not customer_email:
            return None
        
        user = db.query(User).filter(User.email == customer_email).first()
        if not user:
            return None
        
        # Handle based on status
        if status == "complete":
            # Subscription completed normally (reached end of billing cycles)
            user.subscription_auto_renew = False
            
            # If subscription is expired, downgrade to free
            if not user.subscription_expiry_date or user.subscription_expiry_date < datetime.utcnow():
                user.subscription_plan = SubscriptionPlanType.FREE
        else:
            # Subscription cancelled - keep active until expiry date
            user.subscription_auto_renew = False
        
        db.commit()
        db.refresh(user)
        
        return {
            "planType": user.subscription_plan.value,
            "startDate": user.subscription_start_date,
            "expiryDate": user.subscription_expiry_date,
            "autoRenew": user.subscription_auto_renew,
        }
    
    return None


def verify_webhook_signature(request_body: bytes, signature_header: str) -> bool:
    """
    Verify that the webhook request is coming from Paystack by validating the signature
    
    Args:
        request_body (bytes): Raw request body
        signature_header (str): Value of the X-Paystack-Signature header
        
    Returns:
        bool: True if signature is valid, False otherwise
    """
    import hmac
    import hashlib
    
    if not signature_header or not request_body:
        return False
    
    # Get Paystack secret key
    paystack_secret_key = settings.PAYSTACK_SECRET_KEY
    if not paystack_secret_key:
        return False
    
    # Generate HMAC SHA512 hash
    computed_hash = hmac.new(
        paystack_secret_key.encode(),
        request_body,
        hashlib.sha512
    ).hexdigest()
    
    # Compare with the signature from Paystack
    return hmac.compare_digest(computed_hash, signature_header)


def get_subscription_history(db: Session, user_id: uuid.UUID, skip: int = 0, limit: int = 10) -> Dict[str, Any]:
    """
    Get subscription history for a user
    
    Args:
        db (Session): Database session
        user_id (uuid.UUID): ID of the user
        skip (int): Number of records to skip
        limit (int): Maximum number of records to return
        
    Returns:
        dict: Paginated subscription history
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get total count
    total = db.query(SubscriptionHistory).filter(
        SubscriptionHistory.user_id == user_id
    ).count()
    
    # Get paginated records
    history = db.query(SubscriptionHistory).filter(
        SubscriptionHistory.user_id == user_id
    ).order_by(SubscriptionHistory.created_at.desc())\
    .offset(skip).limit(limit).all()
    
    return {
        "total": total,
        "items": history
    }


def record_subscription_payment(
    db: Session, 
    user_id: uuid.UUID, 
    payment_reference: str,
    amount: int,
    payment_status: PaymentStatus,
    transaction_id: Optional[str] = None,
    payment_method: Optional[str] = None
) -> SubscriptionHistory:
    """
    Record a subscription payment in history
    
    Args:
        db (Session): Database session
        user_id (uuid.UUID): ID of the user
        payment_reference (str): Payment reference
        amount (int): Payment amount in kobo
        payment_status (PaymentStatus): Status of payment
        transaction_id (str, optional): Transaction ID from payment provider
        payment_method (str, optional): Payment method used
        
    Returns:
        SubscriptionHistory: Created history record
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if record already exists
    existing = db.query(SubscriptionHistory).filter(
        SubscriptionHistory.payment_reference == payment_reference
    ).first()
    
    if existing:
        # Update existing record
        existing.payment_status = payment_status
        existing.transaction_id = transaction_id or existing.transaction_id
        existing.payment_method = payment_method or existing.payment_method
        existing.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(existing)
        return existing
    
    # Create new record
    history = SubscriptionHistory(
        user_id=user_id,
        payment_reference=payment_reference,
        amount=amount,
        payment_status=payment_status,
        payment_date=datetime.utcnow(),
        event_type=SubscriptionEvent.CHARGE_SUCCESS if payment_status == PaymentStatus.SUCCESSFUL else None,
        plan_type=user.subscription_plan.value,
        duration_months=1,
        transaction_id=transaction_id,
        payment_method=payment_method,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(history)
    db.commit()
    db.refresh(history)
    
    return history 