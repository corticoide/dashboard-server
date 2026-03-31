from fastapi import APIRouter, Depends, Query
from typing import List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.metrics_snapshot import MetricsSnapshot
from backend.schemas.metrics_history import MetricsSnapshotOut

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/history", response_model=List[MetricsSnapshotOut])
def metrics_history(
    hours: int = Query(24, ge=1, le=720),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Get metrics history for the last N hours. Downsamples to 1440 points max."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    q = db.query(MetricsSnapshot).filter(
        MetricsSnapshot.timestamp >= cutoff
    ).order_by(MetricsSnapshot.timestamp.asc())

    max_points = 1440
    rows = q.all()

    # Downsample if necessary
    if len(rows) > max_points:
        step = (len(rows) + max_points - 1) // max_points  # Ceiling division
        rows = rows[::step]

    return rows
