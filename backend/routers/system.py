from fastapi import APIRouter, Depends
from backend.dependencies import require_permission
from backend.schemas.system import SystemMetrics
from backend.services.system_service import get_metrics
from backend.services.cache import TTLCache

router = APIRouter(prefix="/api/system", tags=["system"])

_metrics_cache = TTLCache()
_METRICS_TTL = 3.0


@router.get("/metrics", response_model=SystemMetrics)
def metrics_endpoint(current_user=Depends(require_permission("system", "read"))):
    cached = _metrics_cache.get("metrics")
    if cached is not None:
        return cached
    result = get_metrics()
    _metrics_cache.set("metrics", result, ttl=_METRICS_TTL)
    return result
