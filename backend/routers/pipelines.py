import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.logging import get_audit_logger
from backend.database import get_db, SessionLocal
from backend.dependencies import require_permission
from backend.models.pipeline import Pipeline, PipelineStep, PipelineRun, PipelineStepRun
from backend.models.user import UserRole
from backend.schemas.pipeline import (
    PipelineIn, PipelineOut, PipelineDetailOut,
    PipelineRunOut, PipelineRunDetailOut, PipelineStepOut, PipelineStepRunOut,
)

router = APIRouter(prefix="/api/pipelines", tags=["pipelines"])
_executor = ThreadPoolExecutor(max_workers=4)


def _build_pipeline_out(p: Pipeline, db: Session) -> PipelineOut:
    step_count = db.query(PipelineStep).filter(PipelineStep.pipeline_id == p.id).count()
    last_run = (
        db.query(PipelineRun)
        .filter(PipelineRun.pipeline_id == p.id)
        .order_by(PipelineRun.started_at.desc())
        .first()
    )
    return PipelineOut(
        id=p.id, name=p.name, description=p.description or "",
        step_count=step_count,
        last_run_status=last_run.status if last_run else None,
        last_run_at=last_run.started_at if last_run else None,
        created_at=p.created_at, updated_at=p.updated_at,
    )


def _save_steps(pipeline_id: int, steps_in, db: Session):
    db.query(PipelineStep).filter(PipelineStep.pipeline_id == pipeline_id).delete()
    for i, s in enumerate(steps_in):
        step = PipelineStep(
            pipeline_id=pipeline_id,
            order=s.order if s.order is not None else i,
            name=s.name,
            step_type=s.step_type,
            config=json.dumps(s.config),
            on_success=s.on_success,
            on_failure=s.on_failure,
        )
        db.add(step)


@router.get("", response_model=List[PipelineOut])
def list_pipelines(db: Session = Depends(get_db), user=Depends(require_permission("pipelines", "read"))):
    pipelines = db.query(Pipeline).order_by(Pipeline.created_at.desc()).all()
    return [_build_pipeline_out(p, db) for p in pipelines]


@router.post("", response_model=PipelineOut)
def create_pipeline(body: PipelineIn, db: Session = Depends(get_db), user=Depends(require_permission("pipelines", "write"))):
    existing = db.query(Pipeline).filter(Pipeline.name == body.name).first()
    if existing:
        raise HTTPException(400, detail=f"Pipeline name '{body.name}' already exists")
    p = Pipeline(name=body.name, description=body.description)
    db.add(p)
    db.flush()
    _save_steps(p.id, body.steps, db)
    db.commit()
    db.refresh(p)
    get_audit_logger().info("pipeline_create user=%s name=%s", user.username, p.name)
    return _build_pipeline_out(p, db)


@router.post("/import", response_model=PipelineOut)
def import_pipeline(body: PipelineIn, db: Session = Depends(get_db), user=Depends(require_permission("pipelines", "write"))):
    name = body.name.strip() or "Pipeline importado"
    if db.query(Pipeline).filter(Pipeline.name == name).first():
        counter = 1
        while db.query(Pipeline).filter(Pipeline.name == f"{name} ({counter})").first():
            counter += 1
        name = f"{name} ({counter})"
    p = Pipeline(name=name, description=body.description)
    db.add(p)
    db.flush()
    _save_steps(p.id, body.steps, db)
    db.commit()
    db.refresh(p)
    get_audit_logger().info("pipeline_import user=%s name=%s", user.username, p.name)
    return _build_pipeline_out(p, db)


@router.get("/runs/{run_id}", response_model=PipelineRunDetailOut)
def get_run_detail(run_id: int, db: Session = Depends(get_db), user=Depends(require_permission("pipelines", "read"))):
    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if not run:
        raise HTTPException(404, detail="Run not found")
    step_runs = (
        db.query(PipelineStepRun)
        .filter(PipelineStepRun.run_id == run_id)
        .order_by(PipelineStepRun.step_order)
        .all()
    )
    return PipelineRunDetailOut(
        id=run.id, pipeline_id=run.pipeline_id, triggered_by=run.triggered_by,
        started_at=run.started_at, ended_at=run.ended_at, status=run.status,
        step_runs=[PipelineStepRunOut.model_validate(sr) for sr in step_runs],
    )


@router.get("/{pipeline_id}", response_model=PipelineDetailOut)
def get_pipeline(pipeline_id: int, db: Session = Depends(get_db), user=Depends(require_permission("pipelines", "read"))):
    p = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not p:
        raise HTTPException(404, detail="Pipeline not found")
    steps = db.query(PipelineStep).filter(PipelineStep.pipeline_id == pipeline_id).order_by(PipelineStep.order).all()
    return PipelineDetailOut(
        id=p.id, name=p.name, description=p.description or "",
        steps=[PipelineStepOut.from_orm_step(s) for s in steps],
        created_at=p.created_at, updated_at=p.updated_at,
    )


@router.get("/{pipeline_id}/export")
def export_pipeline(pipeline_id: int, db: Session = Depends(get_db), user=Depends(require_permission("pipelines", "read"))):
    p = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not p:
        raise HTTPException(404, detail="Pipeline not found")
    steps = (
        db.query(PipelineStep)
        .filter(PipelineStep.pipeline_id == pipeline_id)
        .order_by(PipelineStep.order)
        .all()
    )
    return {
        "name": p.name,
        "description": p.description or "",
        "steps": [
            {
                "name": s.name,
                "step_type": s.step_type,
                "config": json.loads(s.config or "{}"),
                "on_success": s.on_success,
                "on_failure": s.on_failure,
                "order": s.order,
            }
            for s in steps
        ],
    }


@router.put("/{pipeline_id}", response_model=PipelineOut)
def update_pipeline(pipeline_id: int, body: PipelineIn, db: Session = Depends(get_db), user=Depends(require_permission("pipelines", "write"))):
    p = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not p:
        raise HTTPException(404, detail="Pipeline not found")
    name_conflict = db.query(Pipeline).filter(Pipeline.name == body.name, Pipeline.id != pipeline_id).first()
    if name_conflict:
        raise HTTPException(400, detail=f"Pipeline name '{body.name}' already exists")
    p.name = body.name
    p.description = body.description
    p.updated_at = datetime.utcnow()
    _save_steps(pipeline_id, body.steps, db)
    db.commit()
    db.refresh(p)
    get_audit_logger().info("pipeline_update user=%s id=%s", user.username, pipeline_id)
    return _build_pipeline_out(p, db)


@router.delete("/{pipeline_id}")
def delete_pipeline(pipeline_id: int, db: Session = Depends(get_db), user=Depends(require_permission("pipelines", "delete"))):
    p = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not p:
        raise HTTPException(404, detail="Pipeline not found")
    db.query(PipelineStepRun).filter(
        PipelineStepRun.run_id.in_(
            db.query(PipelineRun.id).filter(PipelineRun.pipeline_id == pipeline_id)
        )
    ).delete(synchronize_session=False)
    db.query(PipelineRun).filter(PipelineRun.pipeline_id == pipeline_id).delete()
    db.query(PipelineStep).filter(PipelineStep.pipeline_id == pipeline_id).delete()
    db.delete(p)
    db.commit()
    get_audit_logger().info("pipeline_delete user=%s id=%s", user.username, pipeline_id)
    return {"ok": True}


@router.get("/{pipeline_id}/cron-command")
def get_cron_command(pipeline_id: int, db: Session = Depends(get_db), user=Depends(require_permission("pipelines", "read"))):
    p = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not p:
        raise HTTPException(404, detail="Pipeline not found")
    _project_root = Path(__file__).resolve().parent.parent.parent
    _venv_python = _project_root / ".venv" / "bin" / "python3"
    python_exe = str(_venv_python) if _venv_python.exists() else sys.executable
    return {"command": f"{python_exe} -m backend.scripts.pipeline_runner --pipeline-id {pipeline_id}"}


@router.post("/{pipeline_id}/run")
def run_pipeline_endpoint(pipeline_id: int, db: Session = Depends(get_db), user=Depends(require_permission("pipelines", "execute"))):
    p = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not p:
        raise HTTPException(404, detail="Pipeline not found")

    from backend.services.pipeline_service import run_pipeline as _run

    # Crear el run record antes de lanzar el thread
    run_record = PipelineRun(pipeline_id=pipeline_id, triggered_by=user.username, status="running")
    db.add(run_record)
    db.commit()
    db.refresh(run_record)
    run_id = run_record.id

    def _background(pid, triggered_by, rid):
        _db = SessionLocal()
        try:
            _run(pid, triggered_by, _db, existing_run_id=rid)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Pipeline run %s failed", rid)
        finally:
            _db.close()

    _executor.submit(_background, pipeline_id, user.username, run_id)
    get_audit_logger().info("pipeline_run user=%s id=%s run_id=%s", user.username, pipeline_id, run_id)
    return {"run_id": run_id}


@router.get("/{pipeline_id}/runs", response_model=List[PipelineRunOut])
def list_runs(pipeline_id: int, db: Session = Depends(get_db), user=Depends(require_permission("pipelines", "read"))):
    p = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not p:
        raise HTTPException(404, detail="Pipeline not found")
    runs = (
        db.query(PipelineRun)
        .filter(PipelineRun.pipeline_id == pipeline_id)
        .order_by(PipelineRun.started_at.desc())
        .limit(50)
        .all()
    )
    return [PipelineRunOut.model_validate(r) for r in runs]
