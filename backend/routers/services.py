from fastapi import APIRouter, Depends, HTTPException
from typing import List
from backend.core.logging import get_audit_logger
from backend.dependencies import get_current_user, require_role
from backend.models.user import UserRole
from backend.schemas.services import ServiceInfo, ServiceLog, ServiceActionRequest
from backend.services.services_service import list_services, get_service_logs, control_service

router = APIRouter(prefix="/api/services", tags=["services"])


@router.get("/", response_model=List[ServiceInfo])
def get_services(user=Depends(get_current_user)):
    try:
        return list_services()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/{name}/logs", response_model=ServiceLog)
def get_logs(name: str, lines: int = 100, user=Depends(get_current_user)):
    try:
        return get_service_logs(name, lines)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/{name}/{action}")
def service_action(
    name: str,
    action: str,
    body: ServiceActionRequest = None,
    user=Depends(require_role(UserRole.operator)),
):
    password = body.sudo_password if body else None
    try:
        result = control_service(name, action, password)
        get_audit_logger().info("service_control user=%s service=%s action=%s", user.username, name, action)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
