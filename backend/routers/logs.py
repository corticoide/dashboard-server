from fastapi import APIRouter, Depends, Query
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.execution_log import ExecutionLog
from backend.schemas.logs import ExecutionLogOut, ExecutionStatsOut

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("/executions", response_model=List[ExecutionLogOut])
def list_executions(
    script: Optional[str] = Query(None),
    username: Optional[str] = Query(None),
    exit_code: Optional[int] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
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
    return q.limit(100).all()


@router.get("/executions/stats", response_model=ExecutionStatsOut)
def execution_stats(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    total = db.query(ExecutionLog).count()
    success = db.query(ExecutionLog).filter(ExecutionLog.exit_code == 0).count()
    failed = db.query(ExecutionLog).filter(
        ExecutionLog.exit_code != 0, ExecutionLog.exit_code.isnot(None)
    ).count()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    last_24h = db.query(ExecutionLog).filter(ExecutionLog.started_at >= cutoff).count()
    return ExecutionStatsOut(total=total, success=success, failed=failed, last_24h=last_24h)
