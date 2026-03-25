from fastapi import APIRouter, Depends
from backend.dependencies import get_current_user
from backend.schemas.system import SystemMetrics
from backend.services.system_service import get_metrics

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/metrics", response_model=SystemMetrics)
def metrics_endpoint(current_user=Depends(get_current_user)):
    return get_metrics()
