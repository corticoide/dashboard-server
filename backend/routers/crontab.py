from fastapi import APIRouter, Depends, HTTPException
from typing import List

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
        return add_entry(body)
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
        return update_entry(entry_id, body)
    except ValueError as e:
        raise HTTPException(404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(500, detail=str(e))


@router.delete("/{entry_id}", response_model=List[CrontabEntry])
def remove_entry(entry_id: int, user=Depends(require_role(UserRole.admin))):
    try:
        return delete_entry(entry_id)
    except ValueError as e:
        raise HTTPException(404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(500, detail=str(e))
