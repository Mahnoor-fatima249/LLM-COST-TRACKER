from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
import time

from app.database import get_db
from app.routes.auth import get_current_user
from app.models import CostLog, User

router = APIRouter(prefix="/api/health", tags=["Health"])


@router.get("")
async def health_check(db: AsyncSession = Depends(get_db)):
    start = time.time()
    try:
        await db.execute(select(func.count(User.id)))
        db_latency = round((time.time() - start) * 1000, 2)
    except Exception:
        db_latency = -1

    return {
        "status": "healthy" if db_latency > 0 else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "database": "up" if db_latency > 0 else "down",
            "db_latency_ms": db_latency,
        },
    }


@router.get("/user")
async def user_health(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)

    result = await db.execute(
        select(func.count(CostLog.id))
        .where(CostLog.user_id == user.id, CostLog.created_at >= day_ago)
    )
    calls_24h = result.scalar() or 0

    week_ago = now - timedelta(days=7)
    result2 = await db.execute(
        select(func.count(CostLog.id))
        .where(CostLog.user_id == user.id, CostLog.created_at >= week_ago)
    )
    calls_7d = result2.scalar() or 0

    return {
        "user_id": str(user.id),
        "status": "active",
        "calls_24h": calls_24h,
        "calls_7d": calls_7d,
        "account_status": "active",
        "member_since": user.created_at.isoformat() if user.created_at else None,
    }
