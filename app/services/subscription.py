from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import User, CostLog
from app.services.plans import get_plan, list_plans

settings = get_settings()


async def _monthly_usage(
    db: AsyncSession, user_id: str
) -> tuple[int, int]:
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(
            func.count(CostLog.id),
            func.coalesce(func.sum(CostLog.input_tokens + CostLog.output_tokens), 0),
        ).where(CostLog.user_id == user_id, CostLog.created_at >= month_start)
    )
    row = result.one()
    return int(row[0] or 0), int(row[1] or 0)


async def get_current_plan(db: AsyncSession, user: User) -> dict:
    plan = get_plan(user.plan)
    calls_used, tokens_used = await _monthly_usage(db, user.id)
    now = datetime.utcnow()
    renews = None
    if user.plan != "free":
        renews = (now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                  + timedelta(days=32)).replace(day=1)
    return {
        "plan": plan.id,
        "name": plan.name,
        "calls_used": calls_used,
        "calls_limit": plan.calls_per_month,
        "tokens_used": tokens_used,
        "tokens_limit": plan.tokens_per_month,
        "renews_at": renews,
        "is_trial": False,
    }


async def enforce_limits(db: AsyncSession, user: User, input_tokens: int, output_tokens: int) -> None:
    plan = get_plan(user.plan)
    calls_used, tokens_used = await _monthly_usage(db, user.id)
    new_tokens = tokens_used + input_tokens + output_tokens
    if calls_used + 1 > plan.calls_per_month:
        raise HTTPException(
            status_code=402,
            detail=(
                f"You have reached your {plan.name} plan call limit "
                f"({plan.calls_per_month} calls/month). "
                "Upgrade your plan to continue."
            ),
        )
    if new_tokens > plan.tokens_per_month:
        raise HTTPException(
            status_code=402,
            detail=(
                f"This request would exceed your {plan.name} plan token limit "
                f"({plan.tokens_per_month} tokens/month). "
                "Upgrade your plan to continue."
            ),
        )


def billing_enabled() -> bool:
    return bool(settings.STRIPE_SECRET_KEY) and settings.DISABLE_BILLING is False


def get_stripe():
    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


async def create_checkout_session(db: AsyncSession, user: User, plan_id: str) -> str:
    plan = get_plan(plan_id)
    if not billing_enabled():
        return ""

    checkout_url = ""
    try:
        stripe = get_stripe()
        price_id = plan.stripe_price_id
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=user.stripe_customer_id or None,
            customer_email=user.email if not user.stripe_customer_id else None,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=settings.APP_BASE_URL + "/#/pricing?status=success",
            cancel_url=settings.APP_BASE_URL + "/#/pricing?status=cancelled",
            metadata={"plan": plan_id, "user_id": str(user.id)},
        )
        checkout_url = session.url
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to create checkout session")
    return checkout_url
