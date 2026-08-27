import csv
import io
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import CostLog, User
from app.schemas import CostLogCreate, CostLogResponse, PaginatedLogs
from app.routes.auth import get_current_user
from app.services.cost_calculator import calculate_cost
from app.services.alert_service import check_budgets, check_cost_spike
from app.services.subscription import enforce_limits
from app.websocket import manager

router = APIRouter(prefix="/api", tags=["tracking"])


@router.post("/track", response_model=CostLogResponse)
async def track_api_call(
    log_data: CostLogCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await enforce_limits(
        db, current_user, log_data.input_tokens, log_data.output_tokens
    )

    cost = calculate_cost(
        log_data.provider,
        log_data.model,
        log_data.input_tokens,
        log_data.output_tokens,
    )

    cost_log = CostLog(
        user_id=current_user.id,
        provider=log_data.provider,
        model=log_data.model,
        input_tokens=log_data.input_tokens,
        output_tokens=log_data.output_tokens,
        cost=cost,
        latency_ms=log_data.latency_ms,
        status=log_data.status,
        error_message=log_data.error_message,
        project=log_data.project,
        cache_hit=log_data.cache_hit,
    )
    db.add(cost_log)
    await db.commit()
    await db.refresh(cost_log)

    await check_budgets(db, current_user.id)
    await check_cost_spike(db, current_user.id, cost, log_data.model)

    await manager.broadcast_cost_update(str(current_user.id), {
        "id": str(cost_log.id),
        "model": cost_log.model,
        "provider": cost_log.provider,
        "cost": cost_log.cost,
        "input_tokens": cost_log.input_tokens,
        "output_tokens": cost_log.output_tokens,
    })

    return cost_log


@router.get("/logs", response_model=PaginatedLogs)
async def get_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    provider: str = None,
    model: str = None,
    status: str = None,
    project: str = None,
    start_date: datetime = None,
    end_date: datetime = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(CostLog).where(CostLog.user_id == current_user.id)
    count_query = select(func.count(CostLog.id)).where(CostLog.user_id == current_user.id)

    if provider:
        query = query.where(CostLog.provider == provider)
        count_query = count_query.where(CostLog.provider == provider)
    if model:
        query = query.where(CostLog.model == model)
        count_query = count_query.where(CostLog.model == model)
    if status:
        query = query.where(CostLog.status == status)
        count_query = count_query.where(CostLog.status == status)
    if project:
        query = query.where(CostLog.project == project)
        count_query = count_query.where(CostLog.project == project)
    if start_date:
        query = query.where(CostLog.created_at >= start_date)
        count_query = count_query.where(CostLog.created_at >= start_date)
    if end_date:
        query = query.where(CostLog.created_at <= end_date)
        count_query = count_query.where(CostLog.created_at <= end_date)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(desc(CostLog.created_at)).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    logs = result.scalars().all()

    return PaginatedLogs(
        logs=[CostLogResponse.model_validate(log) for log in logs],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/logs/{log_id}", response_model=CostLogResponse)
async def get_log(
    log_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CostLog).where(CostLog.id == log_id, CostLog.user_id == current_user.id)
    )
    log = result.scalar()
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    return log


@router.delete("/logs/{log_id}")
async def delete_log(
    log_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CostLog).where(CostLog.id == log_id, CostLog.user_id == current_user.id)
    )
    log = result.scalar()
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    await db.delete(log)
    await db.commit()
    return {"detail": "Log deleted"}


@router.get("/export")
async def export_logs(
    start_date: datetime = None,
    end_date: datetime = None,
    format: str = Query("csv", pattern="^(csv|json)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(CostLog).where(CostLog.user_id == current_user.id)
    if start_date:
        query = query.where(CostLog.created_at >= start_date)
    if end_date:
        query = query.where(CostLog.created_at <= end_date)
    query = query.order_by(desc(CostLog.created_at))

    result = await db.execute(query)
    logs = result.scalars().all()

    if format == "json":
        data = [
            {
                "id": str(log.id),
                "provider": log.provider,
                "model": log.model,
                "input_tokens": log.input_tokens,
                "output_tokens": log.output_tokens,
                "cost": log.cost,
                "latency_ms": log.latency_ms,
                "status": log.status,
                "project": log.project,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ]
        return data

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Provider", "Model", "Input Tokens", "Output Tokens",
        "Cost ($)", "Latency (ms)", "Status", "Project", "Created At"
    ])
    for log in logs:
        writer.writerow([
            str(log.id), log.provider, log.model, log.input_tokens,
            log.output_tokens, f"{log.cost:.8f}", f"{log.latency_ms:.2f}",
            log.status, log.project or "", log.created_at.isoformat(),
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=llm_costs_{datetime.utcnow().strftime('%Y%m%d')}.csv"},
    )
