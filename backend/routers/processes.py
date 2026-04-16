import psutil
from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from pydantic import BaseModel
from backend.database import get_db
from backend.dependencies import require_permission
from backend.models.alert import AlertRule
from backend.core.logging import get_audit_logger

router = APIRouter(prefix="/api/processes", tags=["processes"])


def _list_procs(db: Session) -> list[dict]:
    watched_names = {
        r.target
        for r in db.query(AlertRule).filter(
            AlertRule.condition_type == "process_missing",
            AlertRule.enabled == True,  # noqa: E712
        ).all()
    }
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info", "username", "status"]):
        try:
            info = p.info
            procs.append({
                "pid": info["pid"],
                "name": info["name"] or "",
                "cpu_percent": info["cpu_percent"] or 0.0,
                "memory_mb": round(
                    (info["memory_info"].rss if info["memory_info"] else 0) / 1_048_576, 1
                ),
                "username": info["username"] or "",
                "status": info["status"] or "",
                "watched": (info["name"] or "") in watched_names,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    procs.sort(key=lambda x: x["cpu_percent"], reverse=True)
    return procs[:500]


@router.get("/")
async def list_processes(
    db: Session = Depends(get_db),
    user=Depends(require_permission("processes", "read")),
):
    return await run_in_threadpool(_list_procs, db)


@router.post("/{pid}/kill", status_code=204)
async def kill_process(
    pid: int,
    user=Depends(require_permission("processes", "execute")),
):
    def _kill():
        try:
            proc = psutil.Process(pid)
            proc.kill()
        except psutil.NoSuchProcess:
            raise HTTPException(status_code=404, detail="Process not found")
        except psutil.AccessDenied:
            raise HTTPException(status_code=403, detail="Access denied")

    await run_in_threadpool(_kill)
    get_audit_logger().info("process_kill user=%s pid=%s", user.username, pid)


class WatchRequest(BaseModel):
    name: str
    email_to: str
    cooldown_minutes: int = 15


@router.post("/watch", status_code=201)
def watch_process(
    body: WatchRequest,
    db: Session = Depends(get_db),
    user=Depends(require_permission("alerts", "write")),
):
    existing = db.query(AlertRule).filter(
        AlertRule.condition_type == "process_missing",
        AlertRule.target == body.name,
    ).first()
    if existing:
        return existing
    rule = AlertRule(
        name=f"Watch: {body.name}",
        enabled=True,
        condition_type="process_missing",
        target=body.name,
        cooldown_minutes=body.cooldown_minutes,
        notify_on_recovery=True,
        email_to=body.email_to,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/watch/{name}", status_code=204)
def unwatch_process(
    name: str,
    db: Session = Depends(get_db),
    user=Depends(require_permission("alerts", "write")),
):
    rule = db.query(AlertRule).filter(
        AlertRule.condition_type == "process_missing",
        AlertRule.target == name,
    ).first()
    if rule:
        db.delete(rule)
        db.commit()
