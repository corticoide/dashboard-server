from fastapi import APIRouter, Depends, Query, Response
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from backend.database import get_db
from backend.dependencies import require_permission, require_role
from backend.models.execution_log import ExecutionLog
from backend.schemas.logs import ExecutionLogOut, ExecutionStatsOut
from backend.services.cache import TTLCache

router = APIRouter(prefix="/api/logs", tags=["logs"])

_count_cache: TTLCache = TTLCache()
_COUNT_TTL = 300


def _count_key(script, username, exit_code, from_date, to_date) -> str:
    fd = from_date.isoformat() if from_date else None
    td = to_date.isoformat() if to_date else None
    return f"{script}|{username}|{exit_code}|{fd}|{td}"


@router.get("/executions", response_model=List[ExecutionLogOut])
def list_executions(
    script: Optional[str] = Query(None),
    username: Optional[str] = Query(None),
    exit_code: Optional[int] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(require_permission("logs", "read")),
    response: Response = None,
):
    q = db.query(ExecutionLog).order_by(ExecutionLog.started_at.desc())
    if script:
        q = q.filter(ExecutionLog.script_path.contains(script))
    if username:
        q = q.filter(ExecutionLog.username == username)
    if exit_code is not None:
        q = q.filter(ExecutionLog.exit_code == exit_code)
    if from_date:
        q = q.filter(ExecutionLog.started_at >= from_date)
    if to_date:
        q = q.filter(ExecutionLog.started_at <= to_date)

    key = _count_key(script, username, exit_code, from_date, to_date)
    total = _count_cache.get(key)
    if total is None:
        total = q.count()
        _count_cache.set(key, total, _COUNT_TTL)

    if response is not None:
        response.headers["X-Total-Count"] = str(total)
    return q.offset(offset).limit(limit).all()


@router.get("/executions/stats", response_model=ExecutionStatsOut)
def execution_stats(
    db: Session = Depends(get_db),
    user=Depends(require_permission("logs", "read")),
):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    row = db.query(
        func.count().label("total"),
        func.sum(case((ExecutionLog.exit_code == 0, 1), else_=0)).label("success"),
        func.sum(case(
            ((ExecutionLog.exit_code != 0) & ExecutionLog.exit_code.isnot(None), 1),
            else_=0,
        )).label("failed"),
        func.sum(case((ExecutionLog.started_at >= cutoff, 1), else_=0)).label("last_24h"),
    ).one()
    return ExecutionStatsOut(
        total=row.total or 0,
        success=row.success or 0,
        failed=row.failed or 0,
        last_24h=row.last_24h or 0,
    )


@router.post("/maintenance/cleanup")
def run_cleanup(
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """Manually trigger log retention cleanup. Admin only — destructive operation."""
    from backend.scheduler import _do_cleanup
    from backend.config import settings
    deleted = _do_cleanup(db, settings.log_retention_days)
    return {"deleted": deleted, "retention_days": settings.log_retention_days}
