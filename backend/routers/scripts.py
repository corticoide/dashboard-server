import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from typing import List
from datetime import datetime, timezone
from backend.core.logging import get_audit_logger

from backend.dependencies import get_current_user, require_role
from backend.models.user import User, UserRole
from backend.models.script import ScriptFavorite, ScriptExecution
from backend.schemas.scripts import (
    FavoriteCreate, FavoriteUpdate, FavoriteOut,
    RunRequest, ExecutionOut, ExecutionPoll,
)
from backend.services.auth_service import decode_token
from backend.services.scripts_service import (
    build_favorite_out, detect_runner, launch_execution, get_poll_state
)
from backend.services.files_service import _safe_path
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
    try:
        safe = _safe_path(body.path)
    except (ValueError, PermissionError) as e:
        raise HTTPException(400, detail=f"Invalid path: {e}")

    existing = db.query(ScriptFavorite).filter(ScriptFavorite.path == str(safe)).first()
    if existing:
        return build_favorite_out(existing)
    fav = ScriptFavorite(path=str(safe))
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


# ── Execution (HTTP) ───────────────────────────────────────────────────────────

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

    try:
        runner = detect_runner(p)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    # Create execution record
    exe = ScriptExecution(
        script_path=fav.path,
        run_as_root=fav.run_as_root,
        triggered_by=user.username,
        is_running=True,
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

    get_audit_logger().info(
        "script_executed user=%s script=%s runner=%s run_as_root=%s exec_id=%d",
        user.username, fav.path, runner, fav.run_as_root, exe.id,
    )

    return ExecutionPoll(id=exe.id, running=True, exit_code=None, lines=[])


# ── Execution (WebSocket) ──────────────────────────────────────────────────────

@router.websocket("/favorites/{fav_id}/run-ws")
async def run_ws(
    websocket: WebSocket,
    fav_id: int,
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    """Stream script execution output in real-time over WebSocket.

    Auth: JWT passed as ?token=... query param (browsers cannot set
    Authorization headers on WebSocket connections).

    Protocol:
      Client → Server (after accept): {"sudo_password": "...", "args": [...]}
      Server → Client: {"type": "line",  "content": "..."}
      Server → Client: {"type": "done",  "exit_code": N}
      Server → Client: {"type": "error", "detail":  "..."}
    """
    # 1. Validate JWT before accepting the connection
    try:
        payload = decode_token(token)
        user = db.query(User).filter(User.id == int(payload["sub"])).first()
        if not user:
            await websocket.close(code=4001)
            return
    except ValueError:
        await websocket.close(code=4001)
        return

    # 2. Load favorite
    fav = db.query(ScriptFavorite).filter(ScriptFavorite.id == fav_id).first()
    if not fav:
        await websocket.close(code=4004)
        return

    # 3. Permission checks
    if fav.admin_only and user.role != UserRole.admin:
        await websocket.close(code=4003)
        return
    if user.role == UserRole.readonly:
        await websocket.close(code=4003)
        return

    # 4. Accept connection
    await websocket.accept()

    # 5. File existence
    p = Path(fav.path)
    if not p.exists() or not p.is_file():
        await websocket.send_json({"type": "error", "detail": f"Script not found: {fav.path}"})
        await websocket.close()
        return

    # 6. Detect runner
    try:
        runner = detect_runner(p)
    except ValueError as e:
        await websocket.send_json({"type": "error", "detail": str(e)})
        await websocket.close()
        return

    # 7. Receive run params sent by client after connection opens
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        params = json.loads(raw)
    except (asyncio.TimeoutError, Exception):
        params = {}

    sudo_password = params.get("sudo_password")
    args = params.get("args") or []

    # 8. Create execution record
    exe = ScriptExecution(
        script_path=fav.path,
        run_as_root=fav.run_as_root,
        triggered_by=user.username,
        is_running=True,
    )
    db.add(exe)
    db.commit()
    db.refresh(exe)

    # 9. Launch in background thread
    launch_execution(
        exec_id=exe.id,
        script_path=fav.path,
        runner=runner,
        run_as_root=fav.run_as_root,
        sudo_password=sudo_password,
        args=args,
        triggered_by=user.username,
    )

    get_audit_logger().info(
        "script_executed user=%s script=%s runner=%s run_as_root=%s exec_id=%d via=websocket",
        user.username, fav.path, runner, fav.run_as_root, exe.id,
    )

    # 10. Stream output: poll shared state every 200 ms, forward new lines
    sent = 0
    try:
        while True:
            state = get_poll_state(exe.id)
            if state is None:
                # State evicted (execution long finished) — just send done
                await websocket.send_json({"type": "done", "exit_code": None})
                break

            lines = state["lines"]
            while sent < len(lines):
                await websocket.send_json({"type": "line", "content": lines[sent]})
                sent += 1

            if not state["running"]:
                await websocket.send_json({"type": "done", "exit_code": state["exit_code"]})
                break

            await asyncio.sleep(0.2)

    except (WebSocketDisconnect, Exception):
        # Client disconnected or any other error — stop streaming silently
        pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@router.get("/executions/{exec_id}", response_model=ExecutionPoll)
def poll_execution(exec_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    # Same-worker fast path: in-memory state is freshest
    state = get_poll_state(exec_id)
    if state is not None:
        return ExecutionPoll(
            id=exec_id,
            running=state["running"],
            exit_code=state["exit_code"],
            lines=list(state["lines"]),
        )

    # Cross-worker or completed: always readable from DB
    exe = db.query(ScriptExecution).filter(ScriptExecution.id == exec_id).first()
    if not exe:
        raise HTTPException(404, detail="Execution not found")

    return ExecutionPoll(
        id=exec_id,
        running=exe.is_running,
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
