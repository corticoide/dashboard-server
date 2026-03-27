from fastapi import APIRouter, Depends, HTTPException
from typing import List

from backend.core.logging import get_audit_logger
from backend.dependencies import get_current_user, require_role
from backend.models.user import UserRole
from backend.schemas.crontab import CrontabEntry, CrontabEntryCreate
from backend.services.crontab_service import (
    list_entries, add_entry, update_entry, delete_entry, validate_field,
)

router = APIRouter(prefix="/api/crontab", tags=["crontab"])


def _validate_create(data: CrontabEntryCreate) -> None:
    if not data.command.strip():
        raise HTTPException(400, detail="Command cannot be empty")
    if not data.is_special:
        for field, name in [
            (data.minute, "minute"), (data.hour, "hour"),
            (data.dom, "day-of-month"), (data.month, "month"),
            (data.dow, "day-of-week"),
        ]:
            try:
                validate_field(field, name)
            except ValueError as e:
                raise HTTPException(400, detail=str(e))


@router.get("/", response_model=List[CrontabEntry])
def get_crontab(user=Depends(get_current_user)):
    try:
        return list_entries()
    except RuntimeError as e:
        raise HTTPException(503, detail=str(e))


@router.post("/", response_model=List[CrontabEntry])
def create_entry(body: CrontabEntryCreate, user=Depends(require_role(UserRole.admin))):
    _validate_create(body)
    try:
        result = add_entry(body)
        get_audit_logger().info("crontab_add user=%s", user.username)
        return result
    except RuntimeError as e:
        raise HTTPException(500, detail=str(e))


@router.put("/{entry_id}", response_model=List[CrontabEntry])
def edit_entry(
    entry_id: int,
    body: CrontabEntryCreate,
    user=Depends(require_role(UserRole.admin)),
):
    _validate_create(body)
    try:
        result = update_entry(entry_id, body)
        get_audit_logger().info("crontab_update user=%s entry_id=%s", user.username, entry_id)
        return result
    except ValueError as e:
        raise HTTPException(404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(500, detail=str(e))


@router.delete("/{entry_id}", response_model=List[CrontabEntry])
def remove_entry(entry_id: int, user=Depends(require_role(UserRole.admin))):
    try:
        result = delete_entry(entry_id)
        get_audit_logger().info("crontab_delete user=%s entry_id=%s", user.username, entry_id)
        return result
    except ValueError as e:
        raise HTTPException(404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(500, detail=str(e))
