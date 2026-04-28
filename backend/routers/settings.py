from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import require_role
from backend.services import settings_service

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsOut(BaseModel):
    log_retention_days: int
    metrics_retention_days: int
    network_retention_days: int
    alerts_retention_days: int
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password_set: bool
    smtp_from: str


class SettingsIn(BaseModel):
    log_retention_days: Optional[int] = None
    metrics_retention_days: Optional[int] = None
    network_retention_days: Optional[int] = None
    alerts_retention_days: Optional[int] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None


class TimezoneIn(BaseModel):
    timezone: str


class SmtpTestIn(BaseModel):
    host: str
    port: int
    user: str
    password: str
    from_addr: str
    to_addr: str


@router.get("", response_model=SettingsOut)
def get_settings(db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    raw = settings_service.get_all_settings(db)
    return SettingsOut(
        log_retention_days=int(raw["log_retention_days"]),
        metrics_retention_days=int(raw["metrics_retention_days"]),
        network_retention_days=int(raw["network_retention_days"]),
        alerts_retention_days=int(raw["alerts_retention_days"]),
        smtp_host=raw["smtp_host"],
        smtp_port=int(raw["smtp_port"]),
        smtp_user=raw["smtp_user"],
        smtp_password_set=bool(raw["smtp_password"]),
        smtp_from=raw["smtp_from"],
    )


@router.put("")
def update_settings(
    body: SettingsIn,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    updates: dict[str, str] = {}
    int_fields = {
        "log_retention_days":     body.log_retention_days,
        "metrics_retention_days": body.metrics_retention_days,
        "network_retention_days": body.network_retention_days,
        "alerts_retention_days":  body.alerts_retention_days,
    }
    for field, val in int_fields.items():
        if val is not None:
            if val < 1:
                raise HTTPException(status_code=422, detail=f"{field} must be >= 1")
            updates[field] = str(val)
    if body.smtp_host is not None:
        updates["smtp_host"] = body.smtp_host
    if body.smtp_port is not None:
        updates["smtp_port"] = str(body.smtp_port)
    if body.smtp_user is not None:
        updates["smtp_user"] = body.smtp_user
    if body.smtp_password is not None:
        updates["smtp_password"] = body.smtp_password
    if body.smtp_from is not None:
        updates["smtp_from"] = body.smtp_from
    settings_service.upsert_settings(db, updates)
    return {"ok": True}


@router.get("/timezone")
def get_timezone(_=Depends(require_role("admin"))):
    return {
        "current":   settings_service.get_system_timezone(),
        "available": settings_service.list_timezones(),
    }


@router.put("/timezone")
def set_timezone(body: TimezoneIn, _=Depends(require_role("admin"))):
    ok, error = settings_service.set_system_timezone(body.timezone)
    if not ok:
        raise HTTPException(status_code=422, detail=error)
    return {"ok": True, "timezone": body.timezone}


@router.post("/test-smtp")
def test_smtp(body: SmtpTestIn, _=Depends(require_role("admin"))):
    ok, error = settings_service.test_smtp(
        body.host, body.port, body.user, body.password, body.from_addr, body.to_addr
    )
    if not ok:
        raise HTTPException(status_code=422, detail=error)
    return {"ok": True}
