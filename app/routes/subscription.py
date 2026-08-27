from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import User
from app.schemas import (
    CurrentPlan,
    Plan,
    SubscriptionCheckout,
    SubscriptionCheckoutResponse,
    PlanChangeRequest,
)
from app.routes.auth import get_current_user
from app.services.plans import get_plan, list_plans
from app.services.subscription import (
    get_current_plan,
    create_checkout_session,
    billing_enabled,
)

router = APIRouter(prefix="/api", tags=["subscription"])
settings = get_settings()


@router.get("/plans", response_model=list[Plan])
async def plans():
    return list_plans()


@router.get("/plan", response_model=CurrentPlan)
async def current_plan(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_current_plan(db, current_user)


@router.post("/subscribe", response_model=SubscriptionCheckoutResponse)
async def subscribe(
    body: SubscriptionCheckout,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = get_plan(body.plan)
    if plan.id == "free":
        current_user.plan = "free"
        current_user.stripe_customer_id = None
        current_user.stripe_subscription_id = None
        await db.commit()
        return SubscriptionCheckoutResponse(
            plan="free",
            checkout_url=None,
            message="You are now on the Free plan.",
        )

    if not billing_enabled():
        # No Stripe keys configured -> allow free upgrade for testing.
        current_user.plan = plan.id
        await db.commit()
        return SubscriptionCheckoutResponse(
            plan=plan.id,
            checkout_url=None,
            message=f"You are now on the {plan.name} plan (billing disabled).",
        )

    checkout_url = await create_checkout_session(db, current_user, plan.id)
    return SubscriptionCheckoutResponse(
        plan=plan.id,
        checkout_url=checkout_url,
        message="Redirecting to secure checkout.",
    )


@router.post("/plan", response_model=CurrentPlan)
async def change_plan(
    body: PlanChangeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = get_plan(body.plan)
    if plan.id == current_user.plan:
        return await get_current_plan(db, current_user)
    if plan.id != "free" and not billing_enabled():
        current_user.plan = plan.id
        await db.commit()
        return await get_current_plan(db, current_user)
    if plan.id != "free" and billing_enabled():
        raise HTTPException(
            status_code=400,
            detail="Please use the /api/subscribe endpoint to change to a paid plan.",
        )
    current_user.plan = "free"
    current_user.stripe_customer_id = None
    current_user.stripe_subscription_id = None
    await db.commit()
    return await get_current_plan(db, current_user)


@router.post("/stripe-webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    if not billing_enabled():
        return {"received": True}
    try:
        import stripe
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("metadata", {}).get("user_id")
        if user_id:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar()
            if user:
                user.plan = "pro"
                user.stripe_customer_id = session.get("customer")
                user.stripe_subscription_id = session.get("subscription")
                await db.commit()
    elif event["type"] == "customer.subscription.deleted":
        subscription_id = event["data"]["object"].get("id")
        result = await db.execute(
            select(User).where(User.stripe_subscription_id == subscription_id)
        )
        user = result.scalar()
        if user:
            user.plan = "free"
            await db.commit()

    return {"received": True}
