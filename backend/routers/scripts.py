from fastapi import APIRouter, Depends, HTTPException
from typing import List
from datetime import datetime, timezone

from backend.dependencies import get_current_user, require_role
from backend.models.user import UserRole
from backend.models.script import ScriptFavorite, ScriptExecution
from backend.schemas.scripts import (
    FavoriteCreate, FavoriteUpdate, FavoriteOut,
    RunRequest, ExecutionOut, ExecutionPoll,
)
from backend.services.scripts_service import (
    build_favorite_out, detect_runner, launch_execution, get_poll_state
)
from backend.database import get_db
from sqlalchemy.orm import Session
from pathlib import Path

router = APIRouter(prefix="/api/scripts", tags=["scripts"])


# ── Favorites CRUD ────────────────────────────────────────────────────────────

@router.get("/favorites", response_model=List[FavoriteOut])
def list_favorites(db: Session = Depends(get_db), user=Depends(get_current_user)):
    favs = db.query(ScriptFavorite).order_by(ScriptFavorite.created_at.desc()).all()
    return [build_favorite_out(f) for f in favs]


@router.post("/favorites", response_model=FavoriteOut)
def add_favorite(body: FavoriteCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    existing = db.query(ScriptFavorite).filter(ScriptFavorite.path == body.path).first()
    if existing:
        return build_favorite_out(existing)
    fav = ScriptFavorite(path=body.path)
    db.add(fav)
    db.commit()
    db.refresh(fav)
    return build_favorite_out(fav)


@router.delete("/favorites/{fav_id}")
def remove_favorite(fav_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    fav = db.query(ScriptFavorite).filter(ScriptFavorite.id == fav_id).first()
    if not fav:
        raise HTTPException(404, detail="Favorite not found")
    db.delete(fav)
    db.commit()
    return {"ok": True}


@router.patch("/favorites/{fav_id}", response_model=FavoriteOut)
def update_favorite(
    fav_id: int,
    body: FavoriteUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_role(UserRole.admin)),
):
    fav = db.query(ScriptFavorite).filter(ScriptFavorite.id == fav_id).first()
    if not fav:
        raise HTTPException(404, detail="Favorite not found")
    if body.run_as_root is not None:
        fav.run_as_root = body.run_as_root
    if body.admin_only is not None:
        fav.admin_only = body.admin_only
    db.commit()
    db.refresh(fav)
    return build_favorite_out(fav)


# ── Execution ─────────────────────────────────────────────────────────────────

@router.post("/favorites/{fav_id}/run", response_model=ExecutionPoll)
def run_favorite(
    fav_id: int,
    body: RunRequest = RunRequest(),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    fav = db.query(ScriptFavorite).filter(ScriptFavorite.id == fav_id).first()
    if not fav:
        raise HTTPException(404, detail="Favorite not found")

    # Permission checks
    if fav.admin_only and user.role != UserRole.admin:
        raise HTTPException(403, detail="This script is restricted to admins")
    if user.role == UserRole.readonly:
        raise HTTPException(403, detail="Read-only users cannot execute scripts")

    # File existence check
    p = Path(fav.path)
    if not p.exists() or not p.is_file():
        raise HTTPException(404, detail=f"Script not found: {fav.path}")

    runner = detect_runner(p)

    # Create execution record
    exe = ScriptExecution(
        script_path=fav.path,
        run_as_root=fav.run_as_root,
        triggered_by=user.username,
    )
    db.add(exe)
    db.commit()
    db.refresh(exe)

    # Launch in background thread
    launch_execution(
        exec_id=exe.id,
        script_path=fav.path,
        runner=runner,
        run_as_root=fav.run_as_root,
        sudo_password=body.sudo_password,
        args=body.args or [],
        triggered_by=user.username,
    )

    return ExecutionPoll(id=exe.id, running=True, exit_code=None, lines=[])


@router.get("/executions/{exec_id}", response_model=ExecutionPoll)
def poll_execution(exec_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    state = get_poll_state(exec_id)
    if state is not None:
        return ExecutionPoll(
            id=exec_id,
            running=state["running"],
            exit_code=state["exit_code"],
            lines=list(state["lines"]),
        )

    # Not in memory — check DB (completed and evicted)
    exe = db.query(ScriptExecution).filter(ScriptExecution.id == exec_id).first()
    if not exe:
        raise HTTPException(404, detail="Execution not found")

    return ExecutionPoll(
        id=exec_id,
        running=False,
        exit_code=exe.exit_code,
        lines=exe.output.splitlines() if exe.output else [],
    )


@router.get("/favorites/{fav_id}/history", response_model=List[ExecutionOut])
def execution_history(fav_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    fav = db.query(ScriptFavorite).filter(ScriptFavorite.id == fav_id).first()
    if not fav:
        raise HTTPException(404, detail="Favorite not found")
    execs = (
        db.query(ScriptExecution)
        .filter(ScriptExecution.script_path == fav.path)
        .order_by(ScriptExecution.started_at.desc())
        .limit(50)
        .all()
    )
    result = []
    for exe in execs:
        running = bool(get_poll_state(exe.id))
        result.append(ExecutionOut(
            id=exe.id,
            script_path=exe.script_path,
            started_at=exe.started_at,
            ended_at=exe.ended_at,
            exit_code=exe.exit_code,
            output=exe.output or "",
            run_as_root=exe.run_as_root,
            triggered_by=exe.triggered_by,
            running=running,
        ))
    return result
