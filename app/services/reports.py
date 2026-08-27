from datetime import datetime, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import CostLog, Budget


async def generate_daily_report(db: AsyncSession, user_id) -> dict:
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)

    today_result = await db.execute(
        select(
            func.sum(CostLog.cost).label("cost"),
            func.count(CostLog.id).label("calls"),
            func.sum(CostLog.input_tokens + CostLog.output_tokens).label("tokens"),
        )
        .where(CostLog.user_id == user_id, CostLog.created_at >= today_start)
    )
    today = today_result.one()

    yesterday_result = await db.execute(
        select(
            func.sum(CostLog.cost).label("cost"),
            func.count(CostLog.id).label("calls"),
        )
        .where(CostLog.user_id == user_id, CostLog.created_at >= yesterday_start, CostLog.created_at < today_start)
    )
    yesterday = yesterday_result.one()

    top_model_result = await db.execute(
        select(CostLog.model, func.sum(CostLog.cost).label("cost"))
        .where(CostLog.user_id == user_id, CostLog.created_at >= today_start)
        .group_by(CostLog.model)
        .order_by(func.sum(CostLog.cost).desc())
        .limit(1)
    )
    top_model = top_model_result.first()

    budget_result = await db.execute(select(Budget).where(Budget.user_id == user_id))
    budget = budget_result.scalar_one_or_none()

    daily_limit = float(budget.daily_limit or 0) if budget else 0
    today_cost = float(today.cost or 0)
    usage_pct = (today_cost / daily_limit * 100) if daily_limit > 0 else 0

    return {
        "date": now.strftime("%Y-%m-%d"),
        "today_cost": round(today_cost, 4),
        "today_calls": today.calls or 0,
        "today_tokens": today.tokens or 0,
        "yesterday_cost": round(float(yesterday.cost or 0), 4),
        "yesterday_calls": yesterday.calls or 0,
        "cost_change_pct": round(((today_cost - float(yesterday.cost or 0)) / float(yesterday.cost or 1)) * 100, 1) if yesterday.cost else 0,
        "top_model": top_model.model if top_model else "N/A",
        "top_model_cost": round(float(top_model.cost or 0), 4) if top_model else 0,
        "daily_limit": daily_limit,
        "budget_usage_pct": round(usage_pct, 1),
        "over_budget": usage_pct >= 100,
    }


def format_report_email(report: dict) -> str:
    change_emoji = "📈" if report["cost_change_pct"] > 0 else "📉"
    status_emoji = "🔴" if report["over_budget"] else "🟢"

    return f"""
    <html>
    <body style="font-family: -apple-system, sans-serif; background: #0a0a0f; color: #e0e0e0; padding: 20px;">
        <div style="max-width: 500px; margin: 0 auto; background: #12121a; border-radius: 12px; padding: 30px; border: 1px solid #1e1e2e;">
            <h2 style="color: #00d4ff; margin: 0 0 24px 0;">📊 Daily Cost Report</h2>
            <p style="color: #666; margin: 0 0 20px 0;">{report['date']}</p>

            <div style="display: flex; gap: 12px; margin-bottom: 24px;">
                <div style="flex:1; background: #1a1a2e; padding: 16px; border-radius: 8px;">
                    <div style="color: #666; font-size: 12px;">Today's Cost</div>
                    <div style="font-size: 24px; font-weight: 700; color: #00d4ff;">${report['today_cost']:.4f}</div>
                </div>
                <div style="flex:1; background: #1a1a2e; padding: 16px; border-radius: 8px;">
                    <div style="color: #666; font-size: 12px;">Calls</div>
                    <div style="font-size: 24px; font-weight: 700;">{report['today_calls']}</div>
                </div>
            </div>

            <div style="background: #1a1a2e; padding: 16px; border-radius: 8px; margin-bottom: 16px;">
                <div style="color: #666; font-size: 12px;">vs Yesterday</div>
                <div style="font-size: 18px; font-weight: 600;">{change_emoji} {report['cost_change_pct']:+.1f}%</div>
            </div>

            <div style="background: #1a1a2e; padding: 16px; border-radius: 8px; margin-bottom: 16px;">
                <div style="color: #666; font-size: 12px;">Budget Usage</div>
                <div style="font-size: 18px; font-weight: 600;">{status_emoji} ${report['today_cost']:.4f} / ${report['daily_limit']:.2f} ({report['budget_usage_pct']}%)</div>
            </div>

            <div style="background: #1a1a2e; padding: 16px; border-radius: 8px; margin-bottom: 16px;">
                <div style="color: #666; font-size: 12px;">Top Model</div>
                <div style="font-size: 16px; font-weight: 600;">{report['top_model']} — ${report['top_model_cost']:.4f}</div>
            </div>

            <p style="color: #444; font-size: 12px; margin-top: 24px; text-align: center;">LLM Cost Tracker</p>
        </div>
    </body>
    </html>
    """
