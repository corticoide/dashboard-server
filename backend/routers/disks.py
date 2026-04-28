from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import require_permission
from backend.services import disk_service

router = APIRouter(prefix="/api/disks", tags=["disks"])


class NameIn(BaseModel):
    name: str


class FavoriteIn(BaseModel):
    favorite: bool


@router.get("")
async def get_disks(
    db: Session = Depends(get_db),
    _=Depends(require_permission("disks", "read")),
):
    return await run_in_threadpool(disk_service.list_disks, db)


@router.post("/scan")
async def scan_disks(
    db: Session = Depends(get_db),
    _=Depends(require_permission("disks", "read")),
):
    return await run_in_threadpool(disk_service.list_disks, db)


@router.patch("/{disk_id}/name")
async def rename_disk(
    disk_id: str,
    body: NameIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("disks", "write")),
):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Name cannot be empty")
    await run_in_threadpool(disk_service.set_disk_name, db, disk_id, name)
    return {"ok": True}


@router.patch("/{disk_id}/favorite")
async def toggle_favorite(
    disk_id: str,
    body: FavoriteIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("disks", "write")),
):
    await run_in_threadpool(disk_service.set_disk_favorite, db, disk_id, body.favorite)
    return {"ok": True}


@router.post("/{disk_id}/mount")
async def mount_disk(
    disk_id: str,
    _=Depends(require_permission("disks", "write")),
):
    dev = f"/dev/{disk_id}"
    ok, msg = await run_in_threadpool(disk_service.mount_disk, dev)
    if not ok:
        raise HTTPException(status_code=422, detail=msg)
    return {"ok": True, "message": msg}


@router.post("/{disk_id}/unmount")
async def unmount_disk(
    disk_id: str,
    _=Depends(require_permission("disks", "write")),
):
    dev = f"/dev/{disk_id}"
    ok, msg = await run_in_threadpool(disk_service.unmount_disk, dev)
    if not ok:
        raise HTTPException(status_code=422, detail=msg)
    return {"ok": True, "message": msg}
