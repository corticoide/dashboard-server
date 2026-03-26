from datetime import datetime, timezone
from fastapi import APIRouter

router = APIRouter(tags=["health"])

VERSION = "1.0.0"


@router.get("/api/health")
def health():
    """Public healthcheck — no authentication required."""
    return {
        "status": "ok",
        "version": VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
