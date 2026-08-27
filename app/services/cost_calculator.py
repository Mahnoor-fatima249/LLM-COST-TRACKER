from datetime import datetime, timedelta
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import CostLog


MODEL_PRICING = {
    "openai": {
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4-turbo": {"input": 10.00, "output": 30.00},
        "gpt-4": {"input": 30.00, "output": 60.00},
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
        "o1": {"input": 15.00, "output": 60.00},
        "o1-mini": {"input": 3.00, "output": 12.00},
        "o1-preview": {"input": 15.00, "output": 60.00},
    },
    "groq": {
        "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
        "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
        "mixtral-8x7b-32768": {"input": 0.24, "output": 0.24},
        "gemma2-9b-it": {"input": 0.20, "output": 0.20},
    },
    "google": {
        "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
        "gemini-2.0-flash-lite": {"input": 0.075, "output": 0.30},
        "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
        "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    },
    "anthropic": {
        "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
        "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
        "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
        "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    },
    "mistral": {
        "mistral-large-latest": {"input": 2.00, "output": 6.00},
        "mistral-small-latest": {"input": 0.20, "output": 0.60},
    },
}


def calculate_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    provider = provider.lower()
    model = model.lower()

    if provider in MODEL_PRICING and model in MODEL_PRICING[provider]:
        pricing = MODEL_PRICING[provider][model]
    else:
        pricing = {"input": 1.00, "output": 3.00}

    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return round(input_cost + output_cost, 8)


async def get_daily_costs(db: AsyncSession, user_id, days: int = 30) -> list[dict]:
    start_date = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(
            func.date(CostLog.created_at).label("date"),
            func.sum(CostLog.cost).label("total_cost"),
            func.count(CostLog.id).label("total_calls"),
            func.sum(CostLog.input_tokens + CostLog.output_tokens).label("total_tokens"),
        )
        .where(CostLog.user_id == user_id, CostLog.created_at >= start_date)
        .group_by(func.date(CostLog.created_at))
        .order_by(func.date(CostLog.created_at))
    )
    rows = result.all()
    return [
        {
            "date": str(row.date),
            "total_cost": round(float(row.total_cost or 0), 4),
            "total_calls": row.total_calls or 0,
            "total_tokens": row.total_tokens or 0,
        }
        for row in rows
    ]


async def get_model_breakdown(db: AsyncSession, user_id, days: int = 30) -> list[dict]:
    start_date = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(
            CostLog.model,
            CostLog.provider,
            func.sum(CostLog.cost).label("total_cost"),
            func.count(CostLog.id).label("total_calls"),
            func.avg(CostLog.latency_ms).label("avg_latency"),
        )
        .where(CostLog.user_id == user_id, CostLog.created_at >= start_date)
        .group_by(CostLog.model, CostLog.provider)
        .order_by(func.sum(CostLog.cost).desc())
    )
    rows = result.all()
    return [
        {
            "model": row.model,
            "provider": row.provider,
            "total_cost": round(float(row.total_cost or 0), 4),
            "total_calls": row.total_calls or 0,
            "avg_latency": round(float(row.avg_latency or 0), 2),
        }
        for row in rows
    ]


async def get_provider_breakdown(db: AsyncSession, user_id, days: int = 30) -> list[dict]:
    start_date = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(
            CostLog.provider,
            func.sum(CostLog.cost).label("total_cost"),
            func.count(CostLog.id).label("total_calls"),
        )
        .where(CostLog.user_id == user_id, CostLog.created_at >= start_date)
        .group_by(CostLog.provider)
        .order_by(func.sum(CostLog.cost).desc())
    )
    rows = result.all()
    return [
        {
            "provider": row.provider,
            "total_cost": round(float(row.total_cost or 0), 4),
            "total_calls": row.total_calls or 0,
        }
        for row in rows
    ]


async def get_hourly_costs(db: AsyncSession, user_id) -> list[dict]:
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(
            func.strftime("%H", CostLog.created_at).label("hour"),
            func.sum(CostLog.cost).label("total_cost"),
            func.count(CostLog.id).label("total_calls"),
        )
        .where(CostLog.user_id == user_id, CostLog.created_at >= today)
        .group_by(func.strftime("%H", CostLog.created_at))
        .order_by(func.strftime("%H", CostLog.created_at))
    )
    rows = result.all()
    return [
        {
            "hour": int(row.hour),
            "total_cost": round(float(row.total_cost or 0), 4),
            "total_calls": row.total_calls or 0,
        }
        for row in rows
    ]


async def forecast_monthly_cost(db: AsyncSession, user_id) -> dict:
    today = datetime.utcnow()
    start_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    days_in_month = (today.replace(month=today.month % 12 + 1, day=1) - timedelta(days=1)).day if today.month < 12 else 31
    days_remaining = days_in_month - today.day

    result = await db.execute(
        select(func.sum(CostLog.cost).label("total_cost"))
        .where(CostLog.user_id == user_id, CostLog.created_at >= start_of_month)
    )
    total_so_far = round(float(result.scalar() or 0), 4)
    avg_daily = round(total_so_far / max(today.day, 1), 4)

    recent_result = await db.execute(
        select(func.sum(CostLog.cost).label("total_cost"))
        .where(
            CostLog.user_id == user_id,
            CostLog.created_at >= today - timedelta(days=7),
        )
    )
    recent_weekly = round(float(recent_result.scalar() or 0), 4)
    recent_avg_daily = round(recent_weekly / 7, 4)

    if recent_avg_daily > avg_daily * 1.1:
        trend = "increasing"
    elif recent_avg_daily < avg_daily * 0.9:
        trend = "decreasing"
    else:
        trend = "stable"

    projected = round(total_so_far + (recent_avg_daily * days_remaining), 4)

    return {
        "projected_monthly_cost": projected,
        "days_remaining": days_remaining,
        "average_daily_cost": avg_daily,
        "total_spent_so_far": total_so_far,
        "trend": trend,
    }


async def get_model_comparison(db: AsyncSession, user_id) -> list[dict]:
    result = await db.execute(
        select(
            CostLog.model,
            CostLog.provider,
            func.avg(CostLog.cost).label("avg_cost"),
            func.avg(CostLog.latency_ms).label("avg_latency"),
            func.count(CostLog.id).label("total_calls"),
            func.sum(CostLog.input_tokens + CostLog.output_tokens).label("total_tokens"),
            func.sum(case((CostLog.status == "success", 1), else_=0)).label("success_count"),
        )
        .where(CostLog.user_id == user_id)
        .group_by(CostLog.model, CostLog.provider)
        .having(func.count(CostLog.id) >= 2)
        .order_by(func.count(CostLog.id).desc())
    )
    rows = result.all()
    return [
        {
            "model": row.model,
            "provider": row.provider,
            "avg_cost_per_call": round(float(row.avg_cost or 0), 6),
            "avg_latency": round(float(row.avg_latency or 0), 2),
            "total_calls": row.total_calls or 0,
            "total_tokens": row.total_tokens or 0,
            "success_rate": round((row.success_count / row.total_calls * 100) if row.total_calls > 0 else 0, 2),
        }
        for row in rows
    ]
