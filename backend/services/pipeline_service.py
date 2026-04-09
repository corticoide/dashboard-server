"""Motor de ejecución de pipelines."""
import json
import subprocess
from datetime import datetime
from typing import Tuple
from sqlalchemy.orm import Session

from backend.models.pipeline import Pipeline, PipelineStep, PipelineRun, PipelineStepRun
from backend.services.pipeline_modules import MODULE_REGISTRY


def interpolate(config: dict, context: dict) -> dict:
    """Reemplaza {VARIABLE} en todos los valores string del config dict (recursivo).

    Itera sobre todas las claves del config y reemplaza placeholders {VAR}
    con valores del contexto. Recursiona en dicts anidados.
    Las listas y valores no-string se preservan sin cambios.
    """
    result = {}
    for k, v in config.items():
        if isinstance(v, str):
            # Reemplazar todas las variables en strings
            for var, val in context.items():
                v = v.replace(f"{{{var}}}", str(val))
            result[k] = v
        elif isinstance(v, dict):
            # Recursion en dicts anidados
            result[k] = interpolate(v, context)
        else:
            # Preservar otros tipos (int, bool, None, list, etc.)
            result[k] = v
    return result


def _should_run(step: PipelineStep, prev_exit_code, prev_on_success, prev_on_failure) -> bool:
    """Evalúa si el paso debe correr según on_success/on_failure del paso anterior.

    - Si es el primer paso (prev_exit_code es None), siempre corre.
    - Si el paso anterior fue exitoso y prev_on_success='stop', este paso se salta.
    - Si el paso anterior falló y prev_on_failure='stop', este paso se salta.
    - En otros casos, el paso corre.
    """
    if prev_exit_code is None:
        return True  # primer paso siempre corre

    prev_success = (prev_exit_code == 0)
    if prev_success:
        # Previous step succeeded; check if it should stop next steps
        return prev_on_success == "continue"
    else:
        # Previous step failed; check if it should stop next steps
        return prev_on_failure == "continue"


def _execute_shell(command: str) -> Tuple[int, str]:
    """Ejecuta un comando shell y retorna (exit_code, output)."""
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
    """Ejecuta un módulo nativo. Retorna (exit_code, output)."""
    module_name = config.get("module")
    if not module_name:
        return 1, "No 'module' key in config"

    # Caso especial: call_pipeline
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

    # Búsqueda en registro
    fn = MODULE_REGISTRY.get(module_name)
    if not fn:
        return 1, f"Unknown module: {module_name}"

    try:
        return fn(config, context)
    except Exception as e:
        return 1, f"Error executing module {module_name}: {e}"


def run_pipeline(pipeline_id: int, triggered_by: str, db: Session, existing_run_id: int = None) -> PipelineRun:
    """Ejecuta un pipeline completo. Bloquea hasta completar. Retorna el PipelineRun.

    Pasos:
    1. Obtener el pipeline y sus steps del DB.
    2. Reutilizar el PipelineRun ya creado (existing_run_id) o crear uno nuevo.
    3. Iterar sobre cada step en orden:
       - Evaluar si debe correr (on_success/on_failure logic).
       - Ejecutar (shell, module, o script).
       - Grabar resultado (status, exit_code, output, timestamps).
    4. Determinar status final (success si todos los que corrieron fueron exitosos).
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

        # Evaluar si este step debe correr basado en resultado anterior
        if not _should_run(step, prev_exit_code, prev_on_success, prev_on_failure):
            step_run.status = "skipped"
            step_run.ended_at = datetime.utcnow()
            step_run.exit_code = None
            db.commit()
            continue

        # Interpolar config con contexto actual
        cfg = interpolate(step.config_dict, context)

        # Ejecutar según tipo
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

        # Grabar resultado
        step_run.ended_at = datetime.utcnow()
        step_run.exit_code = exit_code
        step_run.output = output
        step_run.status = "success" if exit_code == 0 else "failed"
        db.commit()

        # Actualizar flags de fallo
        if exit_code != 0:
            overall_failed = True

        # Guardar estado para el próximo paso
        prev_exit_code = exit_code
        prev_on_success = step.on_success
        prev_on_failure = step.on_failure

    # Finalizar run
    run.ended_at = datetime.utcnow()
    run.status = "failed" if overall_failed else "success"
    db.commit()
    db.refresh(run)
    return run
