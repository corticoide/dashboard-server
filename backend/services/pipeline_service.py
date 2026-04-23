"""Pipeline execution engine."""
import json
import subprocess
from datetime import datetime
from typing import Tuple
from sqlalchemy.orm import Session

from backend.models.pipeline import Pipeline, PipelineStep, PipelineRun, PipelineStepRun
from backend.services.pipeline_modules import MODULE_REGISTRY


def interpolate(config: dict, context: dict) -> dict:
    """Replace {VARIABLE} in all string values of the config dict (recursive).

    Iterates over all config keys and replaces {VAR} placeholders with values
    from the context. Recurses into nested dicts.
    Lists and non-string values are preserved unchanged.
    """
    result = {}
    for k, v in config.items():
        if isinstance(v, str):
            for var, val in context.items():
                v = v.replace(f"{{{var}}}", str(val))
            result[k] = v
        elif isinstance(v, dict):
            result[k] = interpolate(v, context)
        else:
            result[k] = v
    return result


def _should_run(step: PipelineStep, prev_exit_code, prev_on_success, prev_on_failure) -> bool:
    """Evaluate whether the step should run based on on_success/on_failure of the previous step.

    - If it is the first step (prev_exit_code is None), always runs.
    - If the previous step succeeded and prev_on_success='stop', this step is skipped.
    - If the previous step failed and prev_on_failure='stop', this step is skipped.
    - Otherwise, the step runs.
    """
    if prev_exit_code is None:
        return True  # first step always runs

    prev_success = (prev_exit_code == 0)
    if prev_success:
        # Previous step succeeded; check if it should stop next steps
        return prev_on_success == "continue"
    else:
        # Previous step failed; check if it should stop next steps
        return prev_on_failure == "continue"


def _execute_shell(command: str) -> Tuple[int, str]:
    """Execute a shell command and return (exit_code, output)."""
    try:
        proc = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=300
        )
        output = proc.stdout + proc.stderr
        return proc.returncode, output
    except subprocess.TimeoutExpired:
        return 1, "Command timed out (300s)"
    except Exception as e:
        return 1, str(e)


def _execute_module(config: dict, context: dict) -> Tuple[int, str]:
    """Execute a native module. Returns (exit_code, output)."""
    module_name = config.get("module")
    if not module_name:
        return 1, "No 'module' key in config"

    # Special case: call_pipeline
    if module_name == "call_pipeline":
        from backend.database import SessionLocal
        sub_id = config.get("pipeline_id")
        if not sub_id:
            return 1, "call_pipeline requires 'pipeline_id'"
        db = SessionLocal()
        try:
            sub_run = run_pipeline(sub_id, "sub-pipeline", db)
            return (0 if sub_run.status == "success" else 1), \
                   f"Sub-pipeline {sub_id}: {sub_run.status}"
        finally:
            db.close()

    # Look up in registry
    fn = MODULE_REGISTRY.get(module_name)
    if not fn:
        return 1, f"Unknown module: {module_name}"

    try:
        return fn(config, context)
    except Exception as e:
        return 1, f"Error executing module {module_name}: {e}"


def run_pipeline(pipeline_id: int, triggered_by: str, db: Session, existing_run_id: int = None) -> PipelineRun:
    """Execute a full pipeline. Blocks until complete. Returns the PipelineRun.

    Steps:
    1. Fetch the pipeline and its steps from DB.
    2. Reuse an existing PipelineRun (existing_run_id) or create a new one.
    3. Iterate over each step in order:
       - Evaluate whether it should run (on_success/on_failure logic).
       - Execute (shell, module, or script).
       - Record result (status, exit_code, output, timestamps).
    4. Determine final status (success if all executed steps succeeded).
    """
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise ValueError(f"Pipeline {pipeline_id} not found")

    steps = (
        db.query(PipelineStep)
        .filter(PipelineStep.pipeline_id == pipeline_id)
        .order_by(PipelineStep.order)
        .all()
    )

    if existing_run_id:
        run = db.query(PipelineRun).filter(PipelineRun.id == existing_run_id).first()
        if not run:
            raise ValueError(f"PipelineRun {existing_run_id} not found")
    else:
        run = PipelineRun(pipeline_id=pipeline_id, triggered_by=triggered_by, status="running")
        db.add(run)
        db.commit()
        db.refresh(run)

    context: dict = {}
    prev_exit_code = None
    prev_on_success = "continue"
    prev_on_failure = "stop"
    overall_failed = False

    for step in steps:
        step_run = PipelineStepRun(
            run_id=run.id,
            step_id=step.id,
            step_order=step.order,
            started_at=datetime.utcnow(),
        )
        db.add(step_run)
        db.flush()

        # Evaluate whether this step should run based on the previous result
        if not _should_run(step, prev_exit_code, prev_on_success, prev_on_failure):
            step_run.status = "skipped"
            step_run.ended_at = datetime.utcnow()
            step_run.exit_code = None
            db.commit()
            continue

        # Interpolate config with current context
        cfg = interpolate(step.config_dict, context)

        # Execute according to type
        if step.step_type == "shell":
            exit_code, output = _execute_shell(cfg.get("command", ""))
        elif step.step_type == "module":
            exit_code, output = _execute_module(cfg, context)
        elif step.step_type == "script":
            from backend.services.scripts_service import detect_runner
            from pathlib import Path
            script_path = cfg.get("path", "")
            args = cfg.get("args", [])
            try:
                runner = detect_runner(Path(script_path))
                cmd = f"{runner} {script_path} {' '.join(args)}"
                exit_code, output = _execute_shell(cmd)
            except Exception as e:
                exit_code, output = 1, str(e)
        else:
            exit_code, output = 1, f"Unknown step_type: {step.step_type}"

        # Record result
        step_run.ended_at = datetime.utcnow()
        step_run.exit_code = exit_code
        step_run.output = output
        step_run.status = "success" if exit_code == 0 else "failed"
        db.commit()

        # Update failure flags
        if exit_code != 0:
            overall_failed = True

        # Save state for the next step
        prev_exit_code = exit_code
        prev_on_success = step.on_success
        prev_on_failure = step.on_failure

    # Finalize run
    run.ended_at = datetime.utcnow()
    run.status = "failed" if overall_failed else "success"
    db.commit()
    db.refresh(run)
    return run
