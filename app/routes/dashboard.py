from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import CostLog, Budget, Alert, User
from app.schemas import (
    DashboardSummary, CostForecast, BudgetCreate, BudgetResponse,
    AlertResponse,
)
from app.routes.auth import get_current_user
from app.services.cost_calculator import (
    get_daily_costs, get_model_breakdown, get_provider_breakdown,
    get_hourly_costs, forecast_monthly_cost, get_model_comparison,
)
from app.services.alert_service import check_budgets
from app.services.optimizer import analyze_usage

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardSummary)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    # Today
    today_result = await db.execute(
        select(
            func.sum(CostLog.cost),
            func.count(CostLog.id),
            func.sum(CostLog.input_tokens + CostLog.output_tokens),
            func.avg(CostLog.latency_ms),
        ).where(CostLog.user_id == current_user.id, CostLog.created_at >= today_start)
    )
    today = today_result.one()
    total_cost_today = round(float(today[0] or 0), 4)
    total_calls_today = today[1] or 0
    total_tokens_today = today[2] or 0
    avg_latency_today = round(float(today[3] or 0), 2)

    # Error rate today
    error_result = await db.execute(
        select(func.count(CostLog.id))
        .where(
            CostLog.user_id == current_user.id,
            CostLog.created_at >= today_start,
            CostLog.status != "success",
        )
    )
    errors_today = error_result.scalar() or 0
    error_rate_today = round((errors_today / total_calls_today * 100) if total_calls_today > 0 else 0, 2)

    # Cache hit rate
    cache_total_result = await db.execute(
        select(func.count(CostLog.id))
        .where(CostLog.user_id == current_user.id, CostLog.created_at >= today_start)
    )
    cache_total = cache_total_result.scalar() or 0

    cache_hits_result = await db.execute(
        select(func.count(CostLog.id))
        .where(
            CostLog.user_id == current_user.id,
            CostLog.created_at >= today_start,
            CostLog.cache_hit == True,
        )
    )
    cache_hits = cache_hits_result.scalar() or 0
    cache_hit_rate = round((cache_hits / cache_total * 100) if cache_total > 0 else 0, 2)

    # Week cost
    week_result = await db.execute(
        select(func.sum(CostLog.cost))
        .where(CostLog.user_id == current_user.id, CostLog.created_at >= week_start)
    )
    total_cost_week = round(float(week_result.scalar() or 0), 4)

    # Month cost
    month_result = await db.execute(
        select(func.sum(CostLog.cost))
        .where(CostLog.user_id == current_user.id, CostLog.created_at >= month_start)
    )
    total_cost_month = round(float(month_result.scalar() or 0), 4)

    daily_costs = await get_daily_costs(db, current_user.id, 30)
    model_breakdown = await get_model_breakdown(db, current_user.id, 30)
    provider_breakdown = await get_provider_breakdown(db, current_user.id, 30)
    hourly_costs = await get_hourly_costs(db, current_user.id)

    return DashboardSummary(
        total_cost_today=total_cost_today,
        total_cost_week=total_cost_week,
        total_cost_month=total_cost_month,
        total_calls_today=total_calls_today,
        total_tokens_today=total_tokens_today,
        avg_latency_today=avg_latency_today,
        error_rate_today=error_rate_today,
        cache_hit_rate=cache_hit_rate,
        daily_costs=daily_costs,
        model_breakdown=model_breakdown,
        provider_breakdown=provider_breakdown,
        hourly_costs_today=hourly_costs,
    )


@router.get("/forecast", response_model=CostForecast)
async def get_forecast(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await forecast_monthly_cost(db, current_user.id)
    return CostForecast(**result)


@router.get("/comparison")
async def get_comparison(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_model_comparison(db, current_user.id)


@router.post("/budget", response_model=BudgetResponse)
async def set_budget(
    budget_data: BudgetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Budget).where(Budget.user_id == current_user.id))
    existing = result.scalar()

    if existing:
        existing.daily_limit = budget_data.daily_limit
        existing.monthly_limit = budget_data.monthly_limit
        existing.alert_email = budget_data.alert_email
        existing.alert_slack_webhook = budget_data.alert_slack_webhook
        await db.commit()
        await db.refresh(existing)
        return existing
    else:
        budget = Budget(
            user_id=current_user.id,
            daily_limit=budget_data.daily_limit,
            monthly_limit=budget_data.monthly_limit,
            alert_email=budget_data.alert_email,
            alert_slack_webhook=budget_data.alert_slack_webhook,
        )
        db.add(budget)
        await db.commit()
        await db.refresh(budget)
        return budget


@router.get("/budget", response_model=BudgetResponse)
async def get_budget(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Budget).where(Budget.user_id == current_user.id))
    budget = result.scalar()
    if not budget:
        raise HTTPException(status_code=404, detail="No budget set")
    return budget


@router.get("/alerts", response_model=list[AlertResponse])
async def get_alerts(
    unread_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Alert).where(Alert.user_id == current_user.id)
    if unread_only:
        query = query.where(Alert.is_read == False)
    query = query.order_by(Alert.created_at.desc()).limit(50)
    result = await db.execute(query)
    return result.scalars().all()


@router.put("/alerts/{alert_id}/read")
async def mark_alert_read(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Alert).where(Alert.id == alert_id, Alert.user_id == current_user.id)
    )
    alert = result.scalar()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.is_read = True
    await db.commit()
    return {"detail": "Alert marked as read"}


@router.get("/optimize")
async def get_optimization_suggestions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await analyze_usage(db, current_user.id)
