from datetime import datetime, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import CostLog


async def analyze_usage(db: AsyncSession, user_id) -> dict:
    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)

    result = await db.execute(
        select(
            CostLog.model,
            CostLog.provider,
            func.sum(CostLog.cost).label("total_cost"),
            func.count(CostLog.id).label("total_calls"),
            func.avg(CostLog.latency_ms).label("avg_latency"),
            func.sum(CostLog.input_tokens + CostLog.output_tokens).label("total_tokens"),
        )
        .where(CostLog.user_id == user_id, CostLog.created_at >= thirty_days_ago)
        .group_by(CostLog.model, CostLog.provider)
    )
    rows = result.all()

    suggestions = []
    total_cost = sum(float(r.total_cost or 0) for r in rows)
    total_calls = sum(r.total_calls or 0 for r in rows)

    if not rows:
        return {
            "total_cost_30d": 0,
            "total_calls_30d": 0,
            "suggestions": [{"type": "info", "message": "Start tracking API calls to get optimization suggestions"}],
            "potential_savings": 0,
        }

    cheap_alternatives = {
        "gpt-4": {"alt": "gpt-4o-mini", "savings_pct": 95},
        "gpt-4-turbo": {"alt": "gpt-4o-mini", "savings_pct": 94},
        "claude-3-opus-20240229": {"alt": "claude-3-5-haiku-20241022", "savings_pct": 95},
        "claude-3-5-sonnet-20241022": {"alt": "claude-3-5-haiku-20241022", "savings_pct": 73},
        "gemini-1.5-pro": {"alt": "gemini-2.0-flash", "savings_pct": 92},
    }

    potential_savings = 0
    for row in rows:
        model = row.model
        if model in cheap_alternatives:
            alt = cheap_alternatives[model]
            model_cost = float(row.total_cost or 0)
            saving = model_cost * (alt["savings_pct"] / 100)
            potential_savings += saving

            suggestions.append({
                "type": "optimization",
                "priority": "high",
                "message": f"Switch {model} → {alt['alt']} to save ~{alt['savings_pct']}%",
                "current_model": model,
                "suggested_model": alt["alt"],
                "estimated_saving": round(saving, 4),
                "savings_pct": alt["savings_pct"],
            })

    high_latency_models = [r for r in rows if float(r.avg_latency or 0) > 5000]
    for row in high_latency_models:
        suggestions.append({
            "type": "performance",
            "priority": "medium",
            "message": f"{row.model} has high avg latency ({float(row.avg_latency or 0):.0f}ms) — consider streaming or caching",
            "model": row.model,
            "avg_latency": float(row.avg_latency or 0),
        })

    if total_calls > 100:
        cache_suggestion = total_cost * 0.3
        suggestions.append({
            "type": "caching",
            "priority": "high",
            "message": f"With caching, you could save ~${cache_suggestion:.2f}/month on repeated prompts",
            "estimated_saving": round(cache_suggestion, 4),
        })

    daily_avg = total_cost / 30
    monthly_projected = daily_avg * 30

    suggestions.append({
        "type": "summary",
        "priority": "info",
        "message": f"Monthly projection: ${monthly_projected:.2f} at current rate",
        "daily_avg": round(daily_avg, 4),
        "monthly_projected": round(monthly_projected, 2),
    })

    suggestions.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2, "info": 3}.get(x.get("priority", "info"), 3))

    return {
        "total_cost_30d": round(total_cost, 4),
        "total_calls_30d": total_calls,
        "suggestions": suggestions,
        "potential_savings": round(potential_savings, 4),
        "models_used": len(rows),
        "top spender": rows[0].model if rows else "N/A",
    }
