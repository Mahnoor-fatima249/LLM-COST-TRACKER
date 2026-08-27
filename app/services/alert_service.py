import httpx
from datetime import datetime, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Budget, Alert, CostLog


async def check_budgets(db: AsyncSession, user_id) -> list[Alert]:
    result = await db.execute(select(Budget).where(Budget.user_id == user_id))
    budgets = result.scalars().all()
    new_alerts = []

    for budget in budgets:
        now = datetime.utcnow()

        if budget.daily_limit > 0:
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            daily_result = await db.execute(
                select(func.sum(CostLog.cost))
                .where(CostLog.user_id == user_id, CostLog.created_at >= today_start)
            )
            daily_spend = float(daily_result.scalar() or 0)

            if daily_spend >= budget.daily_limit:
                existing = await db.execute(
                    select(Alert)
                    .where(
                        Alert.user_id == user_id,
                        Alert.alert_type == "daily_budget",
                        Alert.created_at >= today_start,
                    )
                )
                if not existing.scalar():
                    alert = Alert(
                        user_id=user_id,
                        alert_type="daily_budget",
                        message=f"Daily budget limit reached! Spent ${daily_spend:.4f} / ${budget.daily_limit:.2f}",
                        threshold=budget.daily_limit,
                        current_value=daily_spend,
                    )
                    db.add(alert)
                    new_alerts.append(alert)

        if budget.monthly_limit > 0:
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            monthly_result = await db.execute(
                select(func.sum(CostLog.cost))
                .where(CostLog.user_id == user_id, CostLog.created_at >= month_start)
            )
            monthly_spend = float(monthly_result.scalar() or 0)

            if monthly_spend >= budget.monthly_limit:
                existing = await db.execute(
                    select(Alert)
                    .where(
                        Alert.user_id == user_id,
                        Alert.alert_type == "monthly_budget",
                        Alert.created_at >= month_start,
                    )
                )
                if not existing.scalar():
                    alert = Alert(
                        user_id=user_id,
                        alert_type="monthly_budget",
                        message=f"Monthly budget limit reached! Spent ${monthly_spend:.4f} / ${budget.monthly_limit:.2f}",
                        threshold=budget.monthly_limit,
                        current_value=monthly_spend,
                    )
                    db.add(alert)
                    new_alerts.append(alert)

        if budget.daily_limit > 0:
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            daily_result = await db.execute(
                select(func.sum(CostLog.cost))
                .where(CostLog.user_id == user_id, CostLog.created_at >= today_start)
            )
            daily_spend = float(daily_result.scalar() or 0)

            if daily_spend >= budget.daily_limit * 0.8 and daily_spend < budget.daily_limit:
                pct = daily_spend / budget.daily_limit * 100
                existing = await db.execute(
                    select(Alert)
                    .where(
                        Alert.user_id == user_id,
                        Alert.alert_type == "daily_budget",
                        Alert.created_at >= today_start,
                    )
                )
                if not existing.scalar():
                    alert = Alert(
                        user_id=user_id,
                        alert_type="daily_budget",
                        message=f"Daily budget warning: {pct:.0f}% used (${daily_spend:.4f} / ${budget.daily_limit:.2f})",
                        threshold=budget.daily_limit,
                        current_value=daily_spend,
                    )
                    db.add(alert)
                    new_alerts.append(alert)

    await db.commit()
    return new_alerts


async def send_slack_notification(webhook_url: str, message: str):
    async with httpx.AsyncClient() as client:
        await client.post(webhook_url, json={"text": message})


async def send_alert_notifications(db: AsyncSession, alerts: list[Alert]):
    for alert in alerts:
        result = await db.execute(
            select(Budget).where(Budget.user_id == alert.user_id)
        )
        budget = result.scalar()
        if budget and budget.alert_slack_webhook:
            await send_slack_notification(budget.alert_slack_webhook, alert.message)


async def check_cost_spike(db: AsyncSession, user_id, current_cost: float, model: str) -> Alert | None:
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    result = await db.execute(
        select(func.avg(CostLog.cost))
        .where(
            CostLog.user_id == user_id,
            CostLog.model == model,
            CostLog.created_at >= seven_days_ago,
        )
    )
    avg_cost = float(result.scalar() or 0)

    if avg_cost > 0 and current_cost > avg_cost * 3:
        alert = Alert(
            user_id=user_id,
            alert_type="cost_spike",
            message=f"Cost spike detected on {model}: ${current_cost:.6f} (avg: ${avg_cost:.6f})",
            threshold=avg_cost * 3,
            current_value=current_cost,
        )
        db.add(alert)
        await db.commit()
        return alert
    return None
