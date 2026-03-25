from fastapi import APIRouter, Depends
from backend.dependencies import get_current_user

router = APIRouter(prefix="/api/system", tags=["system"])

@router.get("/metrics")
def get_metrics(current_user=Depends(get_current_user)):
    return {"status": "stub"}
