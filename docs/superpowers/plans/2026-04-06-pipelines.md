# Sistema de Pipelines Programables — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar un sistema de pipelines programables donde cada pipeline es una secuencia ordenada de pasos (scripts, comandos shell, módulos nativos) con condiciones de continuación, contexto de variables, ejecución manual y scheduling vía Crontab.

**Architecture:** Pipeline runner script (`pipeline_runner.py`) invocado desde Crontab como cualquier otro comando. Lógica pura en `pipeline_service.py` + `pipeline_modules.py`. API REST estándar en `routers/pipelines.py`. Frontend en 3 paneles: lista de pipelines, editor de steps, mini-flujo + historial.

**Tech Stack:** FastAPI + SQLAlchemy (SQLite), Pydantic v2, Vue 3 + PrimeVue 4 Aura, Python `tarfile`/`zipfile`/`shutil`/`smtplib` para módulos nativos.

**Spec:** `docs/superpowers/specs/2026-04-06-pipelines-design.md`

---

## File Map

### Crear
| Archivo | Responsabilidad |
|---|---|
| `backend/models/pipeline.py` | ORM: Pipeline, PipelineStep, PipelineRun, PipelineStepRun |
| `backend/schemas/pipeline.py` | Pydantic I/O schemas para la API |
| `backend/services/pipeline_modules.py` | 14 módulos nativos (funciones puras) |
| `backend/services/pipeline_service.py` | Motor de ejecución: run_pipeline, execute_step, interpolate |
| `backend/routers/pipelines.py` | API router /api/pipelines |
| `backend/scripts/pipeline_runner.py` | CLI entry point para crontab |
| `tests/test_pipeline_modules.py` | Tests unitarios de módulos |
| `tests/test_pipeline_service.py` | Tests del motor de ejecución |
| `tests/test_pipelines_api.py` | Tests de integración de la API |
| `frontend/src/views/PipelinesView.vue` | Vista principal (3 paneles) |

### Modificar
| Archivo | Cambio |
|---|---|
| `backend/models/__init__.py` | Import pipeline models |
| `backend/main.py` | Registrar router + import models |
| `backend/scripts/add_indexes.py` | Agregar 4 índices de pipeline |
| `backend/config.py` | Campos SMTP opcionales |
| `frontend/src/router/index.js` | Ruta `/pipelines` (lazy) |
| `frontend/src/components/layout/AppSidebar.vue` | Entrada "Pipelines" |
| `frontend/src/views/CrontabView.vue` | Tab "PIPELINE" en Step 2 |

---

## Task 1: Modelos ORM

**Files:**
- Create: `backend/models/pipeline.py`
- Modify: `backend/models/__init__.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Crear `backend/models/pipeline.py`**

```python
import json
from sqlalchemy import Column, Integer, String, Text, DateTime, Index
from sqlalchemy.sql import func
from backend.database import Base


class Pipeline(Base):
    __tablename__ = "pipelines"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PipelineStep(Base):
    __tablename__ = "pipeline_steps"

    id = Column(Integer, primary_key=True, index=True)
    pipeline_id = Column(Integer, nullable=False)
    order = Column(Integer, nullable=False)
    name = Column(String, nullable=False)
    step_type = Column(String, nullable=False)   # "script" | "shell" | "module"
    config = Column(Text, default="{}")          # JSON string
    on_success = Column(String, default="continue")  # "continue" | "stop"
    on_failure = Column(String, default="stop")      # "continue" | "stop"

    __table_args__ = (
        Index("ix_pipeline_steps_pipeline_id", "pipeline_id"),
    )

    @property
    def config_dict(self) -> dict:
        return json.loads(self.config or "{}")


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True, index=True)
    pipeline_id = Column(Integer, nullable=False)
    triggered_by = Column(String, nullable=False)
    started_at = Column(DateTime, server_default=func.now())
    ended_at = Column(DateTime, nullable=True)
    status = Column(String, default="running")  # "running" | "success" | "failed"

    __table_args__ = (
        Index("ix_pipeline_runs_pipeline_id", "pipeline_id"),
        Index("ix_pipeline_runs_started_at", "started_at"),
    )


class PipelineStepRun(Base):
    __tablename__ = "pipeline_step_runs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, nullable=False)
    step_id = Column(Integer, nullable=False)
    step_order = Column(Integer, nullable=False)
    started_at = Column(DateTime, server_default=func.now())
    ended_at = Column(DateTime, nullable=True)
    exit_code = Column(Integer, nullable=True)
    output = Column(Text, default="")
    status = Column(String, default="running")  # "running" | "skipped" | "success" | "failed"

    __table_args__ = (
        Index("ix_pipeline_step_runs_run_id", "run_id"),
    )
```

- [ ] **Step 2: Registrar modelos en `backend/main.py`**

Agregar después de los imports existentes de modelos:
```python
import backend.models.pipeline  # ensure pipeline tables are registered  # noqa: F401
```

- [ ] **Step 3: Agregar índices en `backend/scripts/add_indexes.py`**

Agregar al final de la lista `statements`:
```python
"CREATE INDEX IF NOT EXISTS ix_pipeline_steps_pipeline_id ON pipeline_steps (pipeline_id)",
"CREATE INDEX IF NOT EXISTS ix_pipeline_runs_pipeline_id  ON pipeline_runs  (pipeline_id)",
"CREATE INDEX IF NOT EXISTS ix_pipeline_runs_started_at   ON pipeline_runs  (started_at)",
"CREATE INDEX IF NOT EXISTS ix_pipeline_step_runs_run_id  ON pipeline_step_runs (run_id)",
```

- [ ] **Step 4: Verificar que las tablas se crean**

```bash
cd /home/crt/server_dashboard
python -c "
from backend.database import engine, Base
import backend.models.pipeline
Base.metadata.create_all(bind=engine)
print('Tables:', list(Base.metadata.tables.keys()))
"
```
Expected: `pipelines`, `pipeline_steps`, `pipeline_runs`, `pipeline_step_runs` en la lista.

- [ ] **Step 5: Commit**

```bash
git add backend/models/pipeline.py backend/main.py backend/scripts/add_indexes.py
git commit -m "feat(pipelines): add ORM models and DB indexes"
```

---

## Task 2: Schemas Pydantic

**Files:**
- Create: `backend/schemas/pipeline.py`

- [ ] **Step 1: Crear `backend/schemas/pipeline.py`**

```python
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


# ── Step schemas ───────────────────────────────────────────────────────────────

class PipelineStepIn(BaseModel):
    name: str
    step_type: str          # "script" | "shell" | "module"
    config: dict = {}
    on_success: str = "continue"
    on_failure: str = "stop"
    order: int = 0


class PipelineStepOut(BaseModel):
    id: int
    pipeline_id: int
    order: int
    name: str
    step_type: str
    config: dict
    on_success: str
    on_failure: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_step(cls, s) -> "PipelineStepOut":
        import json
        return cls(
            id=s.id,
            pipeline_id=s.pipeline_id,
            order=s.order,
            name=s.name,
            step_type=s.step_type,
            config=json.loads(s.config or "{}"),
            on_success=s.on_success,
            on_failure=s.on_failure,
        )


# ── Pipeline schemas ───────────────────────────────────────────────────────────

class PipelineIn(BaseModel):
    name: str
    description: str = ""
    steps: List[PipelineStepIn] = []


class PipelineOut(BaseModel):
    id: int
    name: str
    description: str
    step_count: int
    last_run_status: Optional[str] = None
    last_run_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PipelineDetailOut(BaseModel):
    id: int
    name: str
    description: str
    steps: List[PipelineStepOut]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Run schemas ────────────────────────────────────────────────────────────────

class PipelineStepRunOut(BaseModel):
    id: int
    run_id: int
    step_id: int
    step_order: int
    started_at: datetime
    ended_at: Optional[datetime] = None
    exit_code: Optional[int] = None
    output: str
    status: str

    model_config = {"from_attributes": True}


class PipelineRunOut(BaseModel):
    id: int
    pipeline_id: int
    triggered_by: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    status: str

    model_config = {"from_attributes": True}


class PipelineRunDetailOut(BaseModel):
    id: int
    pipeline_id: int
    triggered_by: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    status: str
    step_runs: List[PipelineStepRunOut]

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Verificar importación**

```bash
python -c "from backend.schemas.pipeline import PipelineIn, PipelineOut, PipelineDetailOut, PipelineRunDetailOut; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/schemas/pipeline.py
git commit -m "feat(pipelines): add Pydantic schemas"
```

---

## Task 3: Módulos Nativos

**Files:**
- Create: `backend/services/pipeline_modules.py`
- Create: `tests/test_pipeline_modules.py`

- [ ] **Step 1: Escribir tests de módulos**

Crear `tests/test_pipeline_modules.py`:

```python
import pytest
import os
import tempfile
from pathlib import Path


@pytest.fixture
def tmp(tmp_path):
    """Directorio temporal con archivos de prueba."""
    (tmp_path / "src.txt").write_text("hello world")
    (tmp_path / "subdir").mkdir()
    return tmp_path


def test_move_file(tmp):
    from backend.services.pipeline_modules import move_file
    src = str(tmp / "src.txt")
    dst = str(tmp / "moved.txt")
    code, out = move_file({"src": src, "dst": dst}, {})
    assert code == 0
    assert Path(dst).exists()
    assert not Path(src).exists()


def test_copy_file(tmp):
    from backend.services.pipeline_modules import copy_file
    src = str(tmp / "src.txt")
    dst = str(tmp / "copy.txt")
    code, out = copy_file({"src": src, "dst": dst}, {})
    assert code == 0
    assert Path(dst).exists()
    assert Path(src).exists()


def test_delete_file(tmp):
    from backend.services.pipeline_modules import delete_file
    path = str(tmp / "src.txt")
    code, out = delete_file({"path": path}, {})
    assert code == 0
    assert not Path(path).exists()


def test_mkdir(tmp):
    from backend.services.pipeline_modules import mkdir
    path = str(tmp / "newdir" / "nested")
    code, out = mkdir({"path": path}, {})
    assert code == 0
    assert Path(path).is_dir()


def test_write_file_overwrite(tmp):
    from backend.services.pipeline_modules import write_file
    path = str(tmp / "out.txt")
    code, out = write_file({"path": path, "content": "hello", "mode": "overwrite"}, {})
    assert code == 0
    assert Path(path).read_text() == "hello"


def test_write_file_append(tmp):
    from backend.services.pipeline_modules import write_file
    path = str(tmp / "out.txt")
    write_file({"path": path, "content": "line1\n", "mode": "overwrite"}, {})
    write_file({"path": path, "content": "line2\n", "mode": "append"}, {})
    assert Path(path).read_text() == "line1\nline2\n"


def test_rename_file(tmp):
    from backend.services.pipeline_modules import rename_file
    src = str(tmp / "src.txt")
    code, out = rename_file({"path": src, "new_name": "renamed.txt", "use_timestamp": False}, {})
    assert code == 0
    assert (tmp / "renamed.txt").exists()


def test_rename_file_with_timestamp(tmp):
    from backend.services.pipeline_modules import rename_file
    src = str(tmp / "src.txt")
    code, out = rename_file({"path": src, "new_name": "bkp.txt", "use_timestamp": True}, {})
    assert code == 0
    renamed = list(tmp.glob("*_bkp.txt"))
    assert len(renamed) == 1


def test_check_exists_success(tmp):
    from backend.services.pipeline_modules import check_exists
    code, out = check_exists({"path": str(tmp / "src.txt"), "type": "file"}, {})
    assert code == 0


def test_check_exists_failure(tmp):
    from backend.services.pipeline_modules import check_exists
    code, out = check_exists({"path": str(tmp / "nope.txt"), "type": "file"}, {})
    assert code == 1


def test_delay():
    from backend.services.pipeline_modules import delay
    import time
    start = time.time()
    code, out = delay({"seconds": 0.1}, {})
    assert code == 0
    assert time.time() - start >= 0.09


def test_log_module():
    from backend.services.pipeline_modules import log_message
    code, out = log_message({"message": "hello pipeline", "level": "info"}, {})
    assert code == 0
    assert "hello pipeline" in out


def test_compress_decompress(tmp):
    from backend.services.pipeline_modules import compress, decompress
    src = str(tmp / "src.txt")
    archive = str(tmp / "archive.tar.gz")
    out_dir = str(tmp / "extracted")
    code, _ = compress({"src": src, "dst": archive, "format": "tar.gz"}, {})
    assert code == 0
    assert Path(archive).exists()
    os.makedirs(out_dir)
    code, _ = decompress({"src": archive, "dst": out_dir}, {})
    assert code == 0


def test_load_env(tmp):
    from backend.services.pipeline_modules import load_env
    env_file = tmp / ".env"
    env_file.write_text("MY_VAR=hello\nOTHER=world\n")
    context = {}
    code, out = load_env({"path": str(env_file)}, context)
    assert code == 0
    assert context["MY_VAR"] == "hello"
    assert context["OTHER"] == "world"


def test_interpolate():
    from backend.services.pipeline_service import interpolate
    config = {"src": "{BASE}/file.txt", "dst": "{DEST}"}
    ctx = {"BASE": "/tmp", "DEST": "/mnt/nas"}
    result = interpolate(config, ctx)
    assert result["src"] == "/tmp/file.txt"
    assert result["dst"] == "/mnt/nas"
```

- [ ] **Step 2: Ejecutar tests — deben fallar**

```bash
cd /home/crt/server_dashboard
pytest tests/test_pipeline_modules.py -v 2>&1 | head -30
```
Expected: `ModuleNotFoundError` o `ImportError` en `pipeline_modules`.

- [ ] **Step 3: Crear `backend/services/pipeline_modules.py`**

```python
"""Módulos nativos para pipelines. Cada función retorna (exit_code: int, output: str)."""
import shutil
import tarfile
import zipfile
import time
import os
from datetime import datetime
from pathlib import Path
from typing import Tuple


def move_file(config: dict, context: dict) -> Tuple[int, str]:
    src, dst = config["src"], config["dst"]
    try:
        shutil.move(src, dst)
        return 0, f"Moved {src} → {dst}"
    except Exception as e:
        return 1, f"Error moving {src}: {e}"


def copy_file(config: dict, context: dict) -> Tuple[int, str]:
    src, dst = config["src"], config["dst"]
    try:
        if Path(src).is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        return 0, f"Copied {src} → {dst}"
    except Exception as e:
        return 1, f"Error copying {src}: {e}"


def delete_file(config: dict, context: dict) -> Tuple[int, str]:
    path = config["path"]
    try:
        p = Path(path)
        if p.is_dir():
            shutil.rmtree(path)
        else:
            p.unlink()
        return 0, f"Deleted {path}"
    except Exception as e:
        return 1, f"Error deleting {path}: {e}"


def mkdir(config: dict, context: dict) -> Tuple[int, str]:
    path = config["path"]
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return 0, f"Created directory {path}"
    except Exception as e:
        return 1, f"Error creating {path}: {e}"


def write_file(config: dict, context: dict) -> Tuple[int, str]:
    path = config["path"]
    content = config.get("content", "")
    mode = config.get("mode", "overwrite")
    try:
        file_mode = "a" if mode == "append" else "w"
        with open(path, file_mode, encoding="utf-8") as f:
            f.write(content)
        return 0, f"Written to {path} (mode={mode})"
    except Exception as e:
        return 1, f"Error writing {path}: {e}"


def rename_file(config: dict, context: dict) -> Tuple[int, str]:
    path = config["path"]
    new_name = config["new_name"]
    use_timestamp = config.get("use_timestamp", False)
    try:
        p = Path(path)
        if use_timestamp:
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            new_name = f"{ts}_{new_name}"
        dst = p.parent / new_name
        p.rename(dst)
        return 0, f"Renamed {path} → {dst}"
    except Exception as e:
        return 1, f"Error renaming {path}: {e}"


def compress(config: dict, context: dict) -> Tuple[int, str]:
    src = config["src"]
    dst = config["dst"]
    fmt = config.get("format", "tar.gz")
    try:
        if fmt == "tar.gz":
            with tarfile.open(dst, "w:gz") as tar:
                tar.add(src, arcname=Path(src).name)
        elif fmt == "zip":
            with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
                p = Path(src)
                if p.is_dir():
                    for f in p.rglob("*"):
                        zf.write(f, f.relative_to(p.parent))
                else:
                    zf.write(src, p.name)
        else:
            return 1, f"Unknown format: {fmt}"
        return 0, f"Compressed {src} → {dst}"
    except Exception as e:
        return 1, f"Error compressing {src}: {e}"


def decompress(config: dict, context: dict) -> Tuple[int, str]:
    src = config["src"]
    dst = config["dst"]
    try:
        if src.endswith(".tar.gz") or src.endswith(".tgz"):
            with tarfile.open(src, "r:gz") as tar:
                tar.extractall(dst)
        elif src.endswith(".zip"):
            with zipfile.ZipFile(src, "r") as zf:
                zf.extractall(dst)
        else:
            return 1, f"Unknown archive format for: {src}"
        return 0, f"Decompressed {src} → {dst}"
    except Exception as e:
        return 1, f"Error decompressing {src}: {e}"


def check_exists(config: dict, context: dict) -> Tuple[int, str]:
    path = config["path"]
    check_type = config.get("type", "any")
    p = Path(path)
    if check_type == "file":
        exists = p.is_file()
    elif check_type == "dir":
        exists = p.is_dir()
    else:
        exists = p.exists()
    if exists:
        return 0, f"Exists: {path}"
    return 1, f"Not found ({check_type}): {path}"


def delay(config: dict, context: dict) -> Tuple[int, str]:
    seconds = float(config.get("seconds", 1))
    time.sleep(seconds)
    return 0, f"Waited {seconds}s"


def log_message(config: dict, context: dict) -> Tuple[int, str]:
    message = config.get("message", "")
    level = config.get("level", "info").upper()
    return 0, f"[{level}] {message}"


def load_env(config: dict, context: dict) -> Tuple[int, str]:
    path = config["path"]
    try:
        loaded = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                context[key.strip()] = val.strip()
                loaded.append(key.strip())
        return 0, f"Loaded {len(loaded)} variables from {path}: {', '.join(loaded)}"
    except Exception as e:
        return 1, f"Error loading .env {path}: {e}"


def send_email(config: dict, context: dict) -> Tuple[int, str]:
    """Envía email vía SMTP. Requiere SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM en .env."""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders
    from backend.config import settings

    smtp_host = getattr(settings, "smtp_host", None)
    if not smtp_host:
        return 1, "SMTP not configured: set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM in .env"

    to = config["to"]
    subject = config.get("subject", "Pipeline notification")
    body = config.get("body", "")
    attachment = config.get("attachment")

    try:
        msg = MIMEMultipart()
        msg["From"] = settings.smtp_from
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        if attachment and Path(attachment).exists():
            with open(attachment, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={Path(attachment).name}")
            msg.attach(part)

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_from, to, msg.as_string())
        return 0, f"Email sent to {to}"
    except Exception as e:
        return 1, f"Error sending email: {e}"


# ── Dispatch table ──────────────────────────────────────────────────────────────

MODULE_REGISTRY = {
    "move_file": move_file,
    "copy_file": copy_file,
    "delete_file": delete_file,
    "mkdir": mkdir,
    "write_file": write_file,
    "rename_file": rename_file,
    "compress": compress,
    "decompress": decompress,
    "check_exists": check_exists,
    "delay": delay,
    "log": log_message,
    "load_env": load_env,
    "email": send_email,
    # "call_pipeline" is handled directly in pipeline_service to avoid circular import
}
```

- [ ] **Step 4: Ejecutar tests de módulos — deben pasar**

```bash
pytest tests/test_pipeline_modules.py -v
```
Expected: todos en verde (excepto `test_interpolate` que usa `pipeline_service` — se implementa en Task 4).

- [ ] **Step 5: Commit**

```bash
git add backend/services/pipeline_modules.py tests/test_pipeline_modules.py
git commit -m "feat(pipelines): add native modules with tests"
```

---

## Task 4: Motor de Ejecución (pipeline_service)

**Files:**
- Create: `backend/services/pipeline_service.py`
- Create: `tests/test_pipeline_service.py`

- [ ] **Step 1: Escribir tests del servicio**

Crear `tests/test_pipeline_service.py`:

```python
import pytest
from backend.models.pipeline import Pipeline, PipelineStep, PipelineRun, PipelineStepRun
from backend.services.pipeline_service import interpolate, run_pipeline
import backend.models.pipeline  # register tables  # noqa: F401


def test_interpolate_basic():
    from backend.services.pipeline_service import interpolate
    config = {"src": "{BASE}/file.txt", "dst": "{DEST}"}
    ctx = {"BASE": "/tmp", "DEST": "/mnt/nas"}
    result = interpolate(config, ctx)
    assert result["src"] == "/tmp/file.txt"
    assert result["dst"] == "/mnt/nas"


def test_interpolate_nested_dict():
    from backend.services.pipeline_service import interpolate
    config = {"outer": {"inner": "{VAR}"}}
    result = interpolate(config, {"VAR": "hello"})
    assert result["outer"]["inner"] == "hello"


def test_interpolate_missing_var_left_as_is():
    from backend.services.pipeline_service import interpolate
    config = {"path": "{MISSING}"}
    result = interpolate(config, {})
    assert result["path"] == "{MISSING}"


def _make_pipeline(db, steps_data):
    """Helper: crea un pipeline con steps en la BD de test."""
    import json
    p = Pipeline(name="test-pipeline", description="")
    db.add(p)
    db.flush()
    for i, sd in enumerate(steps_data):
        step = PipelineStep(
            pipeline_id=p.id,
            order=i,
            name=sd.get("name", f"step-{i}"),
            step_type=sd["step_type"],
            config=json.dumps(sd.get("config", {})),
            on_success=sd.get("on_success", "continue"),
            on_failure=sd.get("on_failure", "stop"),
        )
        db.add(step)
    db.commit()
    return p


def test_run_pipeline_all_success(db_session):
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "out.txt")
        p = _make_pipeline(db_session, [
            {"step_type": "module", "config": {"module": "write_file", "path": path, "content": "hi", "mode": "overwrite"}},
            {"step_type": "module", "config": {"module": "log", "message": "done"}},
        ])
        run = run_pipeline(p.id, "test_user", db_session)
        assert run.status == "success"
        step_runs = db_session.query(PipelineStepRun).filter_by(run_id=run.id).all()
        assert len(step_runs) == 2
        assert all(sr.status == "success" for sr in step_runs)


def test_run_pipeline_stops_on_failure(db_session):
    p = _make_pipeline(db_session, [
        {"step_type": "module", "config": {"module": "check_exists", "path": "/nonexistent/path", "type": "file"},
         "on_failure": "stop"},
        {"step_type": "module", "config": {"module": "log", "message": "should not run"}},
    ])
    run = run_pipeline(p.id, "test_user", db_session)
    assert run.status == "failed"
    step_runs = db_session.query(PipelineStepRun).filter_by(run_id=run.id).order_by(PipelineStepRun.step_order).all()
    assert step_runs[0].status == "failed"
    assert step_runs[1].status == "skipped"


def test_run_pipeline_continues_on_failure(db_session):
    p = _make_pipeline(db_session, [
        {"step_type": "module", "config": {"module": "check_exists", "path": "/nonexistent", "type": "file"},
         "on_failure": "continue"},
        {"step_type": "module", "config": {"module": "log", "message": "error handler ran"}},
    ])
    run = run_pipeline(p.id, "test_user", db_session)
    # Pipeline falla (primer paso falló) pero ambos steps corrieron
    step_runs = db_session.query(PipelineStepRun).filter_by(run_id=run.id).order_by(PipelineStepRun.step_order).all()
    assert step_runs[1].status == "success"


def test_run_pipeline_shell_step(db_session):
    p = _make_pipeline(db_session, [
        {"step_type": "shell", "config": {"command": "echo hello_pipeline"}},
    ])
    run = run_pipeline(p.id, "test_user", db_session)
    assert run.status == "success"
    sr = db_session.query(PipelineStepRun).filter_by(run_id=run.id).first()
    assert "hello_pipeline" in sr.output


def test_run_pipeline_context_interpolation(db_session):
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "ctx.txt")
        env_path = os.path.join(tmp, ".env")
        with open(env_path, "w") as f:
            f.write(f"OUT_PATH={path}\n")
        p = _make_pipeline(db_session, [
            {"step_type": "module", "config": {"module": "load_env", "path": env_path}},
            {"step_type": "module", "config": {"module": "write_file", "path": "{OUT_PATH}", "content": "ctx works", "mode": "overwrite"}},
        ])
        run = run_pipeline(p.id, "test_user", db_session)
        assert run.status == "success"
        assert open(path).read() == "ctx works"
```

- [ ] **Step 2: Ejecutar tests — deben fallar**

```bash
pytest tests/test_pipeline_service.py -v 2>&1 | head -20
```
Expected: `ImportError` en `pipeline_service`.

- [ ] **Step 3: Crear `backend/services/pipeline_service.py`**

```python
"""Motor de ejecución de pipelines."""
import json
import subprocess
from datetime import datetime
from typing import Tuple
from sqlalchemy.orm import Session

from backend.models.pipeline import Pipeline, PipelineStep, PipelineRun, PipelineStepRun
from backend.services.pipeline_modules import MODULE_REGISTRY


def interpolate(config: dict, context: dict) -> dict:
    """Reemplaza {VARIABLE} en todos los valores string del config dict (recursivo)."""
    result = {}
    for k, v in config.items():
        if isinstance(v, str):
            for var, val in context.items():
                v = v.replace(f"{{{var}}}", val)
            result[k] = v
        elif isinstance(v, dict):
            result[k] = interpolate(v, context)
        else:
            result[k] = v
    return result


def _should_run(step: PipelineStep, prev_exit_code) -> bool:
    """Evalúa si el paso debe correr según on_success/on_failure y el exit_code anterior."""
    if prev_exit_code is None:
        return True  # primer paso siempre corre
    prev_success = (prev_exit_code == 0)
    if prev_success:
        return step.on_success == "continue"
    else:
        return step.on_failure == "continue"


def _execute_shell(command: str) -> Tuple[int, str]:
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
    module_name = config.get("module")
    if not module_name:
        return 1, "No 'module' key in config"
    if module_name == "call_pipeline":
        # Handled separately to avoid circular import at module level
        from backend.database import SessionLocal
        sub_id = config.get("pipeline_id")
        if not sub_id:
            return 1, "call_pipeline requires 'pipeline_id'"
        db = SessionLocal()
        try:
            sub_run = run_pipeline(sub_id, "sub-pipeline", db)
            return (0 if sub_run.status == "success" else 1), f"Sub-pipeline {sub_id}: {sub_run.status}"
        finally:
            db.close()
    fn = MODULE_REGISTRY.get(module_name)
    if not fn:
        return 1, f"Unknown module: {module_name}"
    return fn(config, context)


def run_pipeline(pipeline_id: int, triggered_by: str, db: Session) -> PipelineRun:
    """Ejecuta un pipeline completo. Bloquea hasta completar. Retorna el PipelineRun."""
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise ValueError(f"Pipeline {pipeline_id} not found")

    steps = (
        db.query(PipelineStep)
        .filter(PipelineStep.pipeline_id == pipeline_id)
        .order_by(PipelineStep.order)
        .all()
    )

    run = PipelineRun(pipeline_id=pipeline_id, triggered_by=triggered_by, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    context: dict = {}
    prev_exit_code = None
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

        if not _should_run(step, prev_exit_code):
            step_run.status = "skipped"
            step_run.ended_at = datetime.utcnow()
            step_run.exit_code = None
            db.commit()
            continue

        cfg = interpolate(step.config_dict, context)

        if step.step_type == "shell":
            exit_code, output = _execute_shell(cfg.get("command", ""))
        elif step.step_type == "module":
            exit_code, output = _execute_module(cfg, context)
        elif step.step_type == "script":
            # Ejecuta script favorito por path con runner detectado
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

        step_run.ended_at = datetime.utcnow()
        step_run.exit_code = exit_code
        step_run.output = output
        step_run.status = "success" if exit_code == 0 else "failed"
        db.commit()

        if exit_code != 0:
            overall_failed = True

        prev_exit_code = exit_code

    run.ended_at = datetime.utcnow()
    run.status = "failed" if overall_failed else "success"
    db.commit()
    db.refresh(run)
    return run
```

- [ ] **Step 4: Ejecutar tests del servicio**

```bash
pytest tests/test_pipeline_service.py tests/test_pipeline_modules.py -v
```
Expected: todos en verde.

- [ ] **Step 5: Commit**

```bash
git add backend/services/pipeline_service.py tests/test_pipeline_service.py
git commit -m "feat(pipelines): add execution engine with tests"
```

---

## Task 5: Pipeline Runner Script (CLI)

**Files:**
- Create: `backend/scripts/pipeline_runner.py`

- [ ] **Step 1: Crear `backend/scripts/pipeline_runner.py`**

```python
"""CLI entry point para ejecutar un pipeline desde crontab.

Uso:
    python -m backend.scripts.pipeline_runner --pipeline-id 3

Exit code: 0 si el pipeline tuvo éxito, 1 si falló.
"""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="Run a ServerDash pipeline")
    parser.add_argument("--pipeline-id", type=int, required=True, help="ID del pipeline a ejecutar")
    args = parser.parse_args()

    from backend.database import SessionLocal
    from backend.services.pipeline_service import run_pipeline

    db = SessionLocal()
    try:
        run = run_pipeline(args.pipeline_id, triggered_by="crontab", db=db)
        print(f"Pipeline {args.pipeline_id} finished: {run.status}")
        sys.exit(0 if run.status == "success" else 1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verificar que el módulo es invocable**

```bash
cd /home/crt/server_dashboard
python -m backend.scripts.pipeline_runner --help
```
Expected: muestra `usage: pipeline_runner.py [-h] --pipeline-id PIPELINE_ID`

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/pipeline_runner.py
git commit -m "feat(pipelines): add pipeline_runner CLI script"
```

---

## Task 6: API Router

**Files:**
- Create: `backend/routers/pipelines.py`
- Create: `tests/test_pipelines_api.py`
- Modify: `backend/main.py`
- Modify: `backend/config.py`

- [ ] **Step 1: Agregar campos SMTP en `backend/config.py`**

```python
# Agregar dentro de class Settings:
smtp_host: str = ""
smtp_port: int = 587
smtp_user: str = ""
smtp_password: str = ""
smtp_from: str = ""
```

- [ ] **Step 2: Escribir tests de la API**

Crear `tests/test_pipelines_api.py`:

```python
import pytest


def _auth(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_create_and_list_pipeline(test_app):
    h = _auth(test_app)
    r = test_app.post("/api/pipelines", json={
        "name": "test-pipe",
        "description": "desc",
        "steps": [
            {"name": "step1", "step_type": "shell", "config": {"command": "echo hi"},
             "on_success": "continue", "on_failure": "stop", "order": 0}
        ]
    }, headers=h)
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "test-pipe"
    assert data["step_count"] == 1

    r2 = test_app.get("/api/pipelines", headers=h)
    assert r2.status_code == 200
    assert len(r2.json()) == 1


def test_get_pipeline_detail(test_app):
    h = _auth(test_app)
    r = test_app.post("/api/pipelines", json={"name": "detail-pipe", "steps": []}, headers=h)
    pid = r.json()["id"]
    r2 = test_app.get(f"/api/pipelines/{pid}", headers=h)
    assert r2.status_code == 200
    assert r2.json()["id"] == pid


def test_update_pipeline(test_app):
    h = _auth(test_app)
    r = test_app.post("/api/pipelines", json={"name": "update-me", "steps": []}, headers=h)
    pid = r.json()["id"]
    r2 = test_app.put(f"/api/pipelines/{pid}", json={
        "name": "updated-name",
        "description": "new desc",
        "steps": []
    }, headers=h)
    assert r2.status_code == 200
    assert r2.json()["name"] == "updated-name"


def test_delete_pipeline(test_app):
    h = _auth(test_app)
    r = test_app.post("/api/pipelines", json={"name": "delete-me", "steps": []}, headers=h)
    pid = r.json()["id"]
    r2 = test_app.delete(f"/api/pipelines/{pid}", headers=h)
    assert r2.status_code == 200
    r3 = test_app.get(f"/api/pipelines/{pid}", headers=h)
    assert r3.status_code == 404


def test_manual_run(test_app):
    h = _auth(test_app)
    r = test_app.post("/api/pipelines", json={
        "name": "runnable",
        "steps": [{"name": "s1", "step_type": "shell", "config": {"command": "echo test"},
                   "on_success": "continue", "on_failure": "stop", "order": 0}]
    }, headers=h)
    pid = r.json()["id"]
    r2 = test_app.post(f"/api/pipelines/{pid}/run", headers=h)
    assert r2.status_code == 200
    assert "run_id" in r2.json()


def test_run_history(test_app):
    h = _auth(test_app)
    r = test_app.post("/api/pipelines", json={"name": "hist-pipe", "steps": []}, headers=h)
    pid = r.json()["id"]
    test_app.post(f"/api/pipelines/{pid}/run", headers=h)
    import time; time.sleep(0.3)  # esperar que el ThreadPoolExecutor termine
    r2 = test_app.get(f"/api/pipelines/{pid}/runs", headers=h)
    assert r2.status_code == 200
```

- [ ] **Step 3: Ejecutar tests — deben fallar**

```bash
pytest tests/test_pipelines_api.py -v 2>&1 | head -15
```
Expected: `404 Not Found` o `ImportError`.

- [ ] **Step 4: Crear `backend/routers/pipelines.py`**

```python
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.logging import get_audit_logger
from backend.database import get_db, SessionLocal
from backend.dependencies import get_current_user, require_role
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


@router.get("/", response_model=List[PipelineOut])
def list_pipelines(db: Session = Depends(get_db), user=Depends(get_current_user)):
    pipelines = db.query(Pipeline).order_by(Pipeline.created_at.desc()).all()
    return [_build_pipeline_out(p, db) for p in pipelines]


@router.post("/", response_model=PipelineOut)
def create_pipeline(body: PipelineIn, db: Session = Depends(get_db), user=Depends(require_role(UserRole.admin))):
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


@router.get("/runs/{run_id}", response_model=PipelineRunDetailOut)
def get_run_detail(run_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
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
def get_pipeline(pipeline_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    p = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not p:
        raise HTTPException(404, detail="Pipeline not found")
    steps = db.query(PipelineStep).filter(PipelineStep.pipeline_id == pipeline_id).order_by(PipelineStep.order).all()
    return PipelineDetailOut(
        id=p.id, name=p.name, description=p.description or "",
        steps=[PipelineStepOut.from_orm_step(s) for s in steps],
        created_at=p.created_at, updated_at=p.updated_at,
    )


@router.put("/{pipeline_id}", response_model=PipelineOut)
def update_pipeline(pipeline_id: int, body: PipelineIn, db: Session = Depends(get_db), user=Depends(require_role(UserRole.admin))):
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
def delete_pipeline(pipeline_id: int, db: Session = Depends(get_db), user=Depends(require_role(UserRole.admin))):
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


@router.post("/{pipeline_id}/run")
def run_pipeline_endpoint(pipeline_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if user.role == UserRole.readonly:
        raise HTTPException(403, detail="Read-only users cannot execute pipelines")
    p = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not p:
        raise HTTPException(404, detail="Pipeline not found")

    from backend.services.pipeline_service import run_pipeline as _run
    from backend.models.pipeline import PipelineRun as PR

    # Crear el run record antes de lanzar el thread
    run_record = PR(pipeline_id=pipeline_id, triggered_by=user.username, status="running")
    db.add(run_record)
    db.commit()
    db.refresh(run_record)
    run_id = run_record.id

    def _background(pid, triggered_by, rid):
        _db = SessionLocal()
        try:
            _run(pid, triggered_by, _db)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Pipeline run %s failed", rid)
        finally:
            _db.close()

    _executor.submit(_background, pipeline_id, user.username, run_id)
    get_audit_logger().info("pipeline_run user=%s id=%s run_id=%s", user.username, pipeline_id, run_id)
    return {"run_id": run_id}


@router.get("/{pipeline_id}/runs", response_model=List[PipelineRunOut])
def list_runs(pipeline_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
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
```

- [ ] **Step 5: Registrar router en `backend/main.py`**

Agregar import:
```python
from backend.routers.pipelines import router as pipelines_router
```

Y en la sección de `include_router`:
```python
app.include_router(pipelines_router)
```

- [ ] **Step 6: Ejecutar todos los tests**

```bash
pytest tests/test_pipelines_api.py tests/test_pipeline_service.py tests/test_pipeline_modules.py -v
```
Expected: todos en verde.

- [ ] **Step 7: Ejecutar suite completa**

```bash
pytest -q
```
Expected: todos en verde (los 3 fallos de LoginView en frontend son conocidos, no aplican aquí).

- [ ] **Step 8: Commit**

```bash
git add backend/routers/pipelines.py backend/config.py backend/main.py tests/test_pipelines_api.py
git commit -m "feat(pipelines): add API router with full CRUD and manual run"
```

---

## Task 7: Frontend — PipelinesView.vue

**Files:**
- Create: `frontend/src/views/PipelinesView.vue`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/components/layout/AppSidebar.vue`

- [ ] **Step 1: Agregar ruta en `frontend/src/router/index.js`**

Agregar al array de rutas (lazy import, con `requiresAuth: true`):
```javascript
{ path: '/pipelines', component: () => import('../views/PipelinesView.vue'), meta: { requiresAuth: true } },
```

- [ ] **Step 2: Agregar entrada en `AppSidebar.vue`**

Buscar el bloque de items del sidebar y agregar (entre Scripts y Crontab):
```javascript
{ label: 'Pipelines', icon: 'pi pi-sitemap', path: '/pipelines' },
```

- [ ] **Step 3: Crear `frontend/src/views/PipelinesView.vue`**

La vista es extensa. Estructura en secciones:

```vue
<template>
  <div class="pipelines-view">
    <Splitter class="pipelines-splitter">

      <!-- ── Panel 1: Lista de pipelines ── -->
      <SplitterPanel :size="25" :minSize="18">
        <div class="list-panel">
          <div class="list-panel-header">
            <i class="pi pi-sitemap list-header-icon" />
            <span class="list-header-label">PIPELINES</span>
            <span class="list-header-count">{{ pipelines.length }}</span>
            <Button v-if="isAdmin" icon="pi pi-plus" text rounded size="small"
              v-tooltip.right="'New pipeline'" @click="startNewPipeline" />
            <Button icon="pi pi-refresh" text rounded size="small" :loading="loading"
              v-tooltip.right="'Refresh'" @click="loadPipelines" />
          </div>
          <div class="pipeline-list">
            <div
              v-for="p in pipelines" :key="p.id"
              class="pipeline-card"
              :class="{ 'pipeline-card--active': selectedPipeline?.id === p.id }"
              @click="selectPipeline(p)"
            >
              <div class="pipeline-card-name">
                <i class="pi pi-sitemap pipeline-card-icon" />
                {{ p.name }}
              </div>
              <div class="pipeline-card-meta">{{ p.step_count }} paso{{ p.step_count !== 1 ? 's' : '' }}</div>
              <div class="pipeline-card-status">
                <span v-if="p.last_run_status === 'success'" class="status-badge status-badge--success">✓ éxito</span>
                <span v-else-if="p.last_run_status === 'failed'" class="status-badge status-badge--error">✗ falló</span>
                <span v-else-if="p.last_run_status === 'running'" class="status-badge status-badge--running">◌ corriendo</span>
                <span v-else class="status-badge status-badge--none">— sin runs</span>
                <span v-if="p.last_run_at" class="pipeline-card-time">{{ timeAgo(p.last_run_at) }}</span>
              </div>
            </div>
            <div v-if="!pipelines.length && !loading" class="empty-state">
              <i class="pi pi-sitemap empty-icon" />
              <span class="empty-text">No hay pipelines.</span>
              <Button v-if="isAdmin" label="Crear pipeline" size="small" @click="startNewPipeline" />
            </div>
          </div>
        </div>
      </SplitterPanel>

      <!-- ── Panel 2: Editor de steps ── -->
      <SplitterPanel :size="50" :minSize="35">
        <div class="editor-panel">
          <div v-if="!selectedPipeline && !editingNew" class="empty-editor">
            <i class="pi pi-sitemap empty-icon" />
            <span class="empty-text">Seleccioná un pipeline o creá uno nuevo.</span>
          </div>
          <template v-else>
            <!-- Toolbar -->
            <div class="editor-toolbar">
              <div class="editor-toolbar-left">
                <i class="pi pi-sitemap" style="color: var(--brand-orange)" />
                <input
                  v-model="form.name"
                  class="pipeline-name-input"
                  placeholder="Nombre del pipeline"
                  :disabled="!isAdmin"
                />
              </div>
              <div class="editor-toolbar-right">
                <Button v-if="selectedPipeline && !editingNew" icon="pi pi-play" label="Ejecutar"
                  size="small" severity="success" @click="runPipeline" :loading="running" />
                <Button v-if="isAdmin" icon="pi pi-check" label="Guardar"
                  size="small" @click="savePipeline" :loading="saving" />
                <Button v-if="isAdmin && selectedPipeline" icon="pi pi-trash" text rounded size="small"
                  severity="danger" v-tooltip.left="'Eliminar pipeline'" @click="confirmDelete" />
              </div>
            </div>
            <div class="editor-description">
              <InputText v-model="form.description" placeholder="Descripción (opcional)"
                size="small" fluid :disabled="!isAdmin" />
            </div>

            <!-- Steps list -->
            <div class="steps-header">
              <span class="steps-label">PASOS</span>
              <Button v-if="isAdmin" icon="pi pi-plus" text rounded size="small"
                label="Agregar paso" @click="addStep" />
            </div>
            <div class="steps-list">
              <div
                v-for="(step, idx) in form.steps" :key="step._key"
                class="step-card"
                :class="{ 'step-card--active': activeStepIdx === idx }"
                @click="activeStepIdx = idx"
              >
                <div class="step-card-header">
                  <span class="step-drag-handle">⋮⋮</span>
                  <span class="step-order">{{ idx + 1 }}</span>
                  <span class="step-type-badge" :class="`step-type-badge--${step.step_type}`">
                    {{ step.step_type.toUpperCase() }}
                  </span>
                  <span class="step-name">{{ step.name || '(sin nombre)' }}</span>
                  <span class="step-condition">{{ conditionLabel(step) }}</span>
                  <Button v-if="isAdmin" icon="pi pi-trash" text rounded size="small"
                    severity="danger" @click.stop="removeStep(idx)" />
                </div>
                <div class="step-card-preview">{{ stepPreview(step) }}</div>
              </div>
              <div v-if="!form.steps.length" class="empty-steps">
                <span>No hay pasos. Hacé click en "Agregar paso".</span>
              </div>
            </div>

            <!-- Step config drawer (inline, shown when a step is selected) -->
            <div v-if="activeStepIdx !== null && form.steps[activeStepIdx]" class="step-drawer">
              <StepConfigEditor
                v-model="form.steps[activeStepIdx]"
                :favorites="favorites"
                :pipelines="pipelines"
                :disabled="!isAdmin"
              />
            </div>
          </template>
        </div>
      </SplitterPanel>

      <!-- ── Panel 3: Mini-flujo + historial ── -->
      <SplitterPanel :size="25" :minSize="18">
        <div class="flow-panel">
          <div class="flow-section">
            <div class="flow-label">FLUJO</div>
            <div class="flow-diagram">
              <template v-for="(step, idx) in form.steps" :key="step._key">
                <div class="flow-node" :class="`flow-node--${step.step_type}`">
                  {{ stepIcon(step) }} {{ step.name || step.step_type }}
                </div>
                <div v-if="idx < form.steps.length - 1" class="flow-arrow">
                  <span :class="conditionClass(step)">{{ conditionArrow(step) }}</span>
                </div>
              </template>
              <div v-if="!form.steps.length" class="flow-empty">Sin pasos</div>
            </div>
          </div>
          <div class="runs-section">
            <div class="flow-label">ÚLTIMAS RUNS</div>
            <div class="runs-list">
              <div v-for="run in recentRuns" :key="run.id" class="run-item"
                @click="openRunDetail(run.id)">
                <span :class="run.status === 'success' ? 'run-ok' : run.status === 'failed' ? 'run-fail' : 'run-running'">
                  {{ run.status === 'success' ? '✓' : run.status === 'failed' ? '✗' : '◌' }}
                </span>
                <span class="run-time">{{ timeAgo(run.started_at) }}</span>
                <span v-if="run.ended_at" class="run-duration">
                  {{ duration(run.started_at, run.ended_at) }}
                </span>
              </div>
              <div v-if="!recentRuns.length" class="runs-empty">Sin ejecuciones</div>
            </div>
          </div>
        </div>
      </SplitterPanel>

    </Splitter>

    <!-- Run detail dialog -->
    <Dialog v-model:visible="showRunDetail" modal header="Detalle de ejecución"
      :style="{ width: '700px' }">
      <div v-if="runDetail" class="run-detail">
        <div class="run-detail-status">
          Estado: <strong>{{ runDetail.status }}</strong> ·
          Disparado por: <strong>{{ runDetail.triggered_by }}</strong>
        </div>
        <div v-for="sr in runDetail.step_runs" :key="sr.id" class="step-run-card"
          :class="`step-run-card--${sr.status}`">
          <div class="step-run-header">
            <span class="step-run-order">{{ sr.step_order + 1 }}</span>
            <span class="step-run-status">{{ sr.status }}</span>
            <span v-if="sr.ended_at" class="step-run-duration">
              {{ duration(sr.started_at, sr.ended_at) }}
            </span>
          </div>
          <pre v-if="sr.output" class="step-run-output">{{ sr.output }}</pre>
        </div>
      </div>
    </Dialog>

    <ConfirmDialog />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import Splitter from 'primevue/splitter'
import SplitterPanel from 'primevue/splitterpanel'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Dialog from 'primevue/dialog'
import ConfirmDialog from 'primevue/confirmdialog'
import api from '../api/client.js'
import { useAuthStore } from '../stores/auth.js'
import StepConfigEditor from '../components/pipelines/StepConfigEditor.vue'

const toast = useToast()
const confirm = useConfirm()
const auth = useAuthStore()
const isAdmin = auth.role === 'admin'

const pipelines = ref([])
const loading = ref(false)
const saving = ref(false)
const running = ref(false)
const selectedPipeline = ref(null)
const editingNew = ref(false)
const activeStepIdx = ref(null)
const recentRuns = ref([])
const showRunDetail = ref(false)
const runDetail = ref(null)
const favorites = ref([])

const form = ref({ name: '', description: '', steps: [] })

let _stepKey = 0
function newStepKey() { return ++_stepKey }

function emptyStep() {
  return {
    _key: newStepKey(),
    name: '',
    step_type: 'shell',
    config: { command: '' },
    on_success: 'continue',
    on_failure: 'stop',
    order: 0,
  }
}

async function loadPipelines() {
  loading.value = true
  try {
    const { data } = await api.get('/pipelines/')
    pipelines.value = data
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: 'No se pudieron cargar los pipelines', life: 4000 })
  } finally {
    loading.value = false
  }
}

async function selectPipeline(p) {
  selectedPipeline.value = p
  editingNew.value = false
  activeStepIdx.value = null
  const { data } = await api.get(`/pipelines/${p.id}`)
  form.value = {
    name: data.name,
    description: data.description,
    steps: data.steps.map(s => ({ ...s, _key: newStepKey() })),
  }
  const runsRes = await api.get(`/pipelines/${p.id}/runs`)
  recentRuns.value = runsRes.data.slice(0, 5)
}

function startNewPipeline() {
  selectedPipeline.value = null
  editingNew.value = true
  activeStepIdx.value = null
  recentRuns.value = []
  form.value = { name: '', description: '', steps: [] }
}

function addStep() {
  const s = emptyStep()
  s.order = form.value.steps.length
  form.value.steps.push(s)
  activeStepIdx.value = form.value.steps.length - 1
}

function removeStep(idx) {
  form.value.steps.splice(idx, 1)
  if (activeStepIdx.value >= form.value.steps.length) {
    activeStepIdx.value = form.value.steps.length - 1
  }
}

async function savePipeline() {
  if (!form.value.name.trim()) {
    toast.add({ severity: 'warn', summary: 'Nombre requerido', life: 3000 })
    return
  }
  saving.value = true
  try {
    const body = {
      name: form.value.name,
      description: form.value.description,
      steps: form.value.steps.map((s, i) => ({
        name: s.name, step_type: s.step_type, config: s.config,
        on_success: s.on_success, on_failure: s.on_failure, order: i,
      })),
    }
    if (editingNew.value) {
      const { data } = await api.post('/pipelines/', body)
      await loadPipelines()
      await selectPipeline(data)
      editingNew.value = false
    } else {
      await api.put(`/pipelines/${selectedPipeline.value.id}`, body)
      await loadPipelines()
      await selectPipeline(selectedPipeline.value)
    }
    toast.add({ severity: 'success', summary: 'Guardado', life: 3000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error al guardar', detail: e.response?.data?.detail, life: 5000 })
  } finally {
    saving.value = false
  }
}

async function runPipeline() {
  if (!selectedPipeline.value) return
  running.value = true
  try {
    const { data } = await api.post(`/pipelines/${selectedPipeline.value.id}/run`)
    toast.add({ severity: 'info', summary: 'Pipeline iniciado', detail: `Run ID: ${data.run_id}`, life: 4000 })
    setTimeout(async () => {
      await selectPipeline(selectedPipeline.value)
      await loadPipelines()
    }, 2000)
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.response?.data?.detail, life: 5000 })
  } finally {
    running.value = false
  }
}

async function openRunDetail(runId) {
  const { data } = await api.get(`/pipelines/runs/${runId}`)
  runDetail.value = data
  showRunDetail.value = true
}

function confirmDelete() {
  confirm.require({
    message: `¿Eliminar pipeline "${selectedPipeline.value.name}"?`,
    header: 'Confirmar eliminación',
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: 'Eliminar', rejectLabel: 'Cancelar',
    acceptClass: 'p-button-danger',
    accept: async () => {
      await api.delete(`/pipelines/${selectedPipeline.value.id}`)
      selectedPipeline.value = null
      editingNew.value = false
      form.value = { name: '', description: '', steps: [] }
      recentRuns.value = []
      await loadPipelines()
      toast.add({ severity: 'success', summary: 'Eliminado', life: 3000 })
    },
  })
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function conditionLabel(step) {
  const s = step.on_success, f = step.on_failure
  if (s === 'continue' && f === 'continue') return 'siempre →'
  if (s === 'continue' && f === 'stop') return 'si éxito →'
  if (s === 'stop' && f === 'continue') return 'si falla →'
  return '→'
}

function conditionArrow(step) { return conditionLabel(step) }
function conditionClass(step) {
  if (step.on_success === 'continue' && step.on_failure === 'continue') return 'arrow-always'
  if (step.on_success === 'continue') return 'arrow-success'
  return 'arrow-failure'
}

function stepIcon(step) {
  if (step.step_type === 'script') return '⚙'
  if (step.step_type === 'shell') return '$'
  const mod = step.config?.module
  const icons = { load_env: '📄', email: '✉', compress: '📦', move_file: '↗', copy_file: '⧉',
    delete_file: '🗑', mkdir: '📁', write_file: '✏', rename_file: '✎', decompress: '📂',
    check_exists: '?', delay: '⏱', log: '📝', call_pipeline: '⚡' }
  return icons[mod] || '◆'
}

function stepPreview(step) {
  if (step.step_type === 'shell') return step.config?.command || ''
  if (step.step_type === 'script') return step.config?.path || `script #${step.config?.favorite_id}`
  if (step.step_type === 'module') return `${step.config?.module || 'módulo'}`
  return ''
}

function timeAgo(dt) {
  if (!dt) return ''
  const diff = Date.now() - new Date(dt).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'ahora'
  if (mins < 60) return `hace ${mins}m`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `hace ${hrs}h`
  return `hace ${Math.floor(hrs / 24)}d`
}

function duration(start, end) {
  const ms = new Date(end).getTime() - new Date(start).getTime()
  if (ms < 1000) return `${ms}ms`
  const s = (ms / 1000).toFixed(1)
  return `${s}s`
}

onMounted(async () => {
  await loadPipelines()
  const { data } = await api.get('/scripts/favorites')
  favorites.value = data
})
</script>

<style scoped>
.pipelines-view {
  height: calc(100vh - var(--header-height) - 48px);
  display: flex;
  flex-direction: column;
}
.pipelines-splitter { flex: 1; min-height: 0; border-radius: 8px; overflow: hidden; }

/* ── Panel 1 ── */
.list-panel { display: flex; flex-direction: column; height: 100%; background: var(--p-surface-card); border-right: 1px solid var(--p-surface-border); overflow: hidden; }
.list-panel-header { display: flex; align-items: center; gap: 7px; padding: 10px; border-bottom: 1px solid var(--p-surface-border); flex-shrink: 0; }
.list-header-icon { font-size: 12px; color: var(--brand-orange); }
.list-header-label { font-family: var(--font-mono); font-size: var(--text-2xs); letter-spacing: 2px; color: var(--p-text-muted-color); flex: 1; }
.list-header-count { font-family: var(--font-mono); font-size: var(--text-2xs); font-weight: 600; color: var(--brand-orange); background: color-mix(in srgb, var(--brand-orange) 12%, transparent); border-radius: 4px; padding: 1px 6px; }
.pipeline-list { flex: 1; overflow-y: auto; padding: 6px; }
.pipeline-card { padding: 8px 10px; border-radius: 6px; cursor: pointer; margin-bottom: 4px; border: 1px solid transparent; transition: background 0.15s, border-color 0.15s; }
.pipeline-card:hover { background: var(--p-surface-hover); }
.pipeline-card--active { background: color-mix(in srgb, var(--brand-orange) 8%, transparent); border-color: color-mix(in srgb, var(--brand-orange) 30%, transparent); }
.pipeline-card-name { display: flex; align-items: center; gap: 6px; font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-color); margin-bottom: 3px; }
.pipeline-card-icon { color: var(--brand-orange); font-size: 10px; }
.pipeline-card-meta { font-family: var(--font-mono); font-size: var(--text-2xs); color: var(--p-text-muted-color); margin-bottom: 4px; }
.pipeline-card-status { display: flex; align-items: center; gap: 6px; }
.status-badge { font-family: var(--font-mono); font-size: 8px; letter-spacing: 0.5px; padding: 1px 5px; border-radius: 3px; }
.status-badge--success { background: color-mix(in srgb, var(--p-green-500) 15%, transparent); color: var(--p-green-500); }
.status-badge--error { background: color-mix(in srgb, var(--p-red-500) 15%, transparent); color: var(--p-red-500); }
.status-badge--running { background: color-mix(in srgb, var(--p-blue-500) 15%, transparent); color: var(--p-blue-500); }
.status-badge--none { background: color-mix(in srgb, var(--p-text-muted-color) 10%, transparent); color: var(--p-text-muted-color); }
.pipeline-card-time { font-family: var(--font-mono); font-size: 9px; color: var(--p-text-muted-color); }

/* ── Panel 2 ── */
.editor-panel { display: flex; flex-direction: column; height: 100%; background: var(--p-surface-card); overflow: hidden; }
.editor-toolbar { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; border-bottom: 1px solid var(--p-surface-border); flex-shrink: 0; gap: 8px; }
.editor-toolbar-left { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0; }
.editor-toolbar-right { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.pipeline-name-input { font-family: var(--font-mono); font-size: var(--text-sm); font-weight: 600; color: var(--p-text-color); background: transparent; border: none; outline: none; flex: 1; min-width: 0; }
.pipeline-name-input:focus { border-bottom: 1px solid var(--brand-orange); }
.editor-description { padding: 8px 12px; border-bottom: 1px solid var(--p-surface-border); flex-shrink: 0; }
.steps-header { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px 4px; flex-shrink: 0; }
.steps-label { font-family: var(--font-mono); font-size: var(--text-2xs); letter-spacing: 2px; color: var(--p-text-muted-color); }
.steps-list { flex: 1; overflow-y: auto; padding: 4px 12px; }
.step-card { background: var(--p-surface-ground); border: 1px solid var(--p-surface-border); border-radius: 6px; padding: 8px 10px; margin-bottom: 6px; cursor: pointer; transition: border-color 0.15s; }
.step-card:hover { border-color: var(--p-text-muted-color); }
.step-card--active { border-color: var(--brand-orange); background: color-mix(in srgb, var(--brand-orange) 5%, var(--p-surface-ground)); }
.step-card-header { display: flex; align-items: center; gap: 6px; margin-bottom: 3px; }
.step-drag-handle { color: var(--p-text-muted-color); cursor: grab; font-size: 12px; }
.step-order { font-family: var(--font-mono); font-size: var(--text-2xs); color: var(--p-text-muted-color); min-width: 14px; }
.step-type-badge { font-family: var(--font-mono); font-size: 8px; letter-spacing: 1px; padding: 1px 5px; border-radius: 3px; flex-shrink: 0; }
.step-type-badge--script { background: color-mix(in srgb, var(--brand-orange) 15%, transparent); color: var(--brand-orange); }
.step-type-badge--shell { background: color-mix(in srgb, var(--p-green-500) 15%, transparent); color: var(--p-green-500); }
.step-type-badge--module { background: color-mix(in srgb, var(--p-purple-500) 15%, transparent); color: var(--p-purple-500); }
.step-name { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-color); flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.step-condition { font-family: var(--font-mono); font-size: 9px; color: var(--p-text-muted-color); flex-shrink: 0; }
.step-card-preview { font-family: var(--font-mono); font-size: 9px; color: var(--p-text-muted-color); padding-left: 28px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.step-drawer { border-top: 1px solid var(--p-surface-border); padding: 12px; overflow-y: auto; max-height: 280px; flex-shrink: 0; }
.empty-steps { padding: 24px; text-align: center; font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-muted-color); }

/* ── Panel 3 ── */
.flow-panel { display: flex; flex-direction: column; height: 100%; background: var(--p-surface-card); border-left: 1px solid var(--p-surface-border); overflow: hidden; }
.flow-section { padding: 10px; border-bottom: 1px solid var(--p-surface-border); flex-shrink: 0; }
.flow-label { font-family: var(--font-mono); font-size: var(--text-2xs); letter-spacing: 2px; color: var(--p-text-muted-color); margin-bottom: 8px; }
.flow-diagram { display: flex; flex-direction: column; align-items: flex-start; gap: 2px; }
.flow-node { font-family: var(--font-mono); font-size: 10px; padding: 3px 10px; border-radius: 4px; border: 1px solid; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
.flow-node--script { background: color-mix(in srgb, var(--brand-orange) 12%, transparent); color: var(--brand-orange); border-color: color-mix(in srgb, var(--brand-orange) 30%, transparent); }
.flow-node--shell { background: color-mix(in srgb, var(--p-green-500) 12%, transparent); color: var(--p-green-500); border-color: color-mix(in srgb, var(--p-green-500) 30%, transparent); }
.flow-node--module { background: color-mix(in srgb, var(--p-purple-500) 12%, transparent); color: var(--p-purple-500); border-color: color-mix(in srgb, var(--p-purple-500) 30%, transparent); }
.flow-arrow { padding-left: 14px; font-family: var(--font-mono); font-size: 9px; }
.arrow-always { color: var(--p-text-muted-color); }
.arrow-success { color: var(--p-green-500); }
.arrow-failure { color: var(--p-red-400); }
.flow-empty { font-family: var(--font-mono); font-size: 10px; color: var(--p-text-muted-color); padding: 8px; }
.runs-section { flex: 1; padding: 10px; overflow-y: auto; }
.runs-list { display: flex; flex-direction: column; gap: 4px; }
.run-item { display: flex; align-items: center; gap: 6px; cursor: pointer; padding: 4px 6px; border-radius: 4px; }
.run-item:hover { background: var(--p-surface-hover); }
.run-ok { color: var(--p-green-500); font-size: 11px; }
.run-fail { color: var(--p-red-400); font-size: 11px; }
.run-running { color: var(--p-blue-400); font-size: 11px; }
.run-time { font-family: var(--font-mono); font-size: 9px; color: var(--p-text-muted-color); flex: 1; }
.run-duration { font-family: var(--font-mono); font-size: 9px; color: var(--p-text-muted-color); }
.runs-empty { font-family: var(--font-mono); font-size: 10px; color: var(--p-text-muted-color); padding: 4px; }

/* ── Empty states ── */
.empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; padding: 32px; }
.empty-icon { font-size: 28px; opacity: 0.4; color: var(--p-text-muted-color); }
.empty-text { font-size: var(--text-sm); font-family: var(--font-mono); color: var(--p-text-muted-color); text-align: center; }
.empty-editor { height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; }

/* ── Run detail dialog ── */
.run-detail { display: flex; flex-direction: column; gap: 12px; }
.run-detail-status { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-muted-color); }
.step-run-card { border: 1px solid var(--p-surface-border); border-radius: 6px; padding: 10px; }
.step-run-card--success { border-left: 3px solid var(--p-green-500); }
.step-run-card--failed { border-left: 3px solid var(--p-red-400); }
.step-run-card--skipped { border-left: 3px solid var(--p-text-muted-color); opacity: 0.6; }
.step-run-header { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; font-family: var(--font-mono); font-size: var(--text-xs); }
.step-run-order { color: var(--p-text-muted-color); }
.step-run-status { font-weight: 600; }
.step-run-duration { color: var(--p-text-muted-color); margin-left: auto; }
.step-run-output { font-family: var(--font-mono); font-size: 10px; background: var(--p-surface-ground); border-radius: 4px; padding: 8px; margin: 0; white-space: pre-wrap; max-height: 150px; overflow-y: auto; color: var(--p-text-muted-color); }
</style>
```

- [ ] **Step 4: Crear `frontend/src/components/pipelines/StepConfigEditor.vue`**

```vue
<template>
  <div class="step-config">
    <div class="config-row">
      <label class="config-label">NOMBRE DEL PASO</label>
      <InputText v-model="local.name" size="small" fluid :disabled="disabled" />
    </div>

    <div class="config-row">
      <label class="config-label">TIPO</label>
      <SelectButton
        v-model="local.step_type"
        :options="typeOptions"
        optionLabel="label" optionValue="value"
        size="small" :disabled="disabled"
        @change="onTypeChange"
      />
    </div>

    <!-- Shell config -->
    <div v-if="local.step_type === 'shell'" class="config-row">
      <label class="config-label">COMANDO</label>
      <InputText v-model="local.config.command" size="small" fluid
        placeholder="systemctl restart nginx" :disabled="disabled" />
    </div>

    <!-- Script config -->
    <div v-if="local.step_type === 'script'" class="config-row">
      <label class="config-label">SCRIPT FAVORITO</label>
      <Select v-model="local.config.favorite_id" :options="favoriteOptions"
        optionLabel="label" optionValue="value" size="small" fluid :disabled="disabled" />
    </div>

    <!-- Module config -->
    <template v-if="local.step_type === 'module'">
      <div class="config-row">
        <label class="config-label">MÓDULO</label>
        <Select v-model="local.config.module" :options="moduleOptions"
          optionLabel="label" optionValue="value" size="small" fluid :disabled="disabled"
          @change="onModuleChange" />
      </div>
      <!-- Dynamic fields per module -->
      <template v-if="local.config.module === 'load_env' || local.config.module === 'check_exists' || local.config.module === 'delete_file'">
        <div class="config-row">
          <label class="config-label">RUTA</label>
          <InputText v-model="local.config.path" size="small" fluid placeholder="/path/to/file" :disabled="disabled" />
        </div>
      </template>
      <template v-if="local.config.module === 'check_exists'">
        <div class="config-row">
          <label class="config-label">TIPO</label>
          <Select v-model="local.config.type" :options="[{l:'Archivo',v:'file'},{l:'Directorio',v:'dir'},{l:'Cualquiera',v:'any'}]"
            optionLabel="l" optionValue="v" size="small" fluid :disabled="disabled" />
        </div>
      </template>
      <template v-if="['move_file','copy_file','compress'].includes(local.config.module)">
        <div class="config-row">
          <label class="config-label">ORIGEN</label>
          <InputText v-model="local.config.src" size="small" fluid placeholder="{VAR}/archivo.txt" :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">DESTINO</label>
          <InputText v-model="local.config.dst" size="small" fluid placeholder="/destino/" :disabled="disabled" />
        </div>
      </template>
      <template v-if="local.config.module === 'compress'">
        <div class="config-row">
          <label class="config-label">FORMATO</label>
          <Select v-model="local.config.format" :options="[{l:'tar.gz',v:'tar.gz'},{l:'zip',v:'zip'}]"
            optionLabel="l" optionValue="v" size="small" fluid :disabled="disabled" />
        </div>
      </template>
      <template v-if="local.config.module === 'decompress'">
        <div class="config-row">
          <label class="config-label">ARCHIVO</label>
          <InputText v-model="local.config.src" size="small" fluid placeholder="/archivo.tar.gz" :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">DIRECTORIO DESTINO</label>
          <InputText v-model="local.config.dst" size="small" fluid placeholder="/destino/" :disabled="disabled" />
        </div>
      </template>
      <template v-if="local.config.module === 'mkdir'">
        <div class="config-row">
          <label class="config-label">RUTA</label>
          <InputText v-model="local.config.path" size="small" fluid placeholder="/nuevo/directorio" :disabled="disabled" />
        </div>
      </template>
      <template v-if="local.config.module === 'write_file'">
        <div class="config-row">
          <label class="config-label">RUTA</label>
          <InputText v-model="local.config.path" size="small" fluid :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">CONTENIDO</label>
          <Textarea v-model="local.config.content" rows="3" size="small" fluid :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">MODO</label>
          <Select v-model="local.config.mode" :options="[{l:'Sobrescribir',v:'overwrite'},{l:'Agregar',v:'append'}]"
            optionLabel="l" optionValue="v" size="small" fluid :disabled="disabled" />
        </div>
      </template>
      <template v-if="local.config.module === 'rename_file'">
        <div class="config-row">
          <label class="config-label">RUTA ORIGINAL</label>
          <InputText v-model="local.config.path" size="small" fluid :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">NUEVO NOMBRE</label>
          <InputText v-model="local.config.new_name" size="small" fluid :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">PREFIJO TIMESTAMP</label>
          <ToggleButton v-model="local.config.use_timestamp" onLabel="Sí" offLabel="No" size="small" :disabled="disabled" />
        </div>
      </template>
      <template v-if="local.config.module === 'delay'">
        <div class="config-row">
          <label class="config-label">SEGUNDOS</label>
          <InputNumber v-model="local.config.seconds" :min="0" :max="3600" size="small" fluid :disabled="disabled" />
        </div>
      </template>
      <template v-if="local.config.module === 'log'">
        <div class="config-row">
          <label class="config-label">MENSAJE</label>
          <InputText v-model="local.config.message" size="small" fluid :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">NIVEL</label>
          <Select v-model="local.config.level" :options="[{l:'Info',v:'info'},{l:'Warn',v:'warn'},{l:'Error',v:'error'}]"
            optionLabel="l" optionValue="v" size="small" fluid :disabled="disabled" />
        </div>
      </template>
      <template v-if="local.config.module === 'email'">
        <div class="config-row">
          <label class="config-label">DESTINATARIO</label>
          <InputText v-model="local.config.to" size="small" fluid placeholder="admin@host" :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">ASUNTO</label>
          <InputText v-model="local.config.subject" size="small" fluid :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">CUERPO</label>
          <Textarea v-model="local.config.body" rows="3" size="small" fluid :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">ADJUNTO (opcional)</label>
          <InputText v-model="local.config.attachment" size="small" fluid placeholder="/ruta/archivo" :disabled="disabled" />
        </div>
      </template>
      <template v-if="local.config.module === 'call_pipeline'">
        <div class="config-row">
          <label class="config-label">PIPELINE</label>
          <Select v-model="local.config.pipeline_id" :options="pipelineOptions"
            optionLabel="label" optionValue="value" size="small" fluid :disabled="disabled" />
        </div>
      </template>
    </template>

    <!-- Conditions -->
    <div class="config-row">
      <label class="config-label">SI EL PASO ANTERIOR TUVO ÉXITO</label>
      <Select v-model="local.on_success"
        :options="[{l:'Continuar (ejecutar este paso)',v:'continue'},{l:'Detener (saltar este paso)',v:'stop'}]"
        optionLabel="l" optionValue="v" size="small" fluid :disabled="disabled" />
    </div>
    <div class="config-row">
      <label class="config-label">SI EL PASO ANTERIOR FALLÓ</label>
      <Select v-model="local.on_failure"
        :options="[{l:'Detener pipeline',v:'stop'},{l:'Continuar (ejecutar de todas formas)',v:'continue'}]"
        optionLabel="l" optionValue="v" size="small" fluid :disabled="disabled" />
    </div>
  </div>
</template>

<script setup>
import { reactive, watch } from 'vue'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Select from 'primevue/select'
import SelectButton from 'primevue/selectbutton'
import Textarea from 'primevue/textarea'
import ToggleButton from 'primevue/togglebutton'

const props = defineProps({
  modelValue: Object,
  favorites: Array,
  pipelines: Array,
  disabled: Boolean,
})
const emit = defineEmits(['update:modelValue'])

const local = reactive({ ...props.modelValue, config: { ...(props.modelValue.config || {}) } })

watch(local, (val) => emit('update:modelValue', { ...val }), { deep: true })
watch(() => props.modelValue, (val) => {
  Object.assign(local, val)
  Object.assign(local.config, val.config || {})
}, { deep: true })

const typeOptions = [
  { label: 'Shell', value: 'shell' },
  { label: 'Script', value: 'script' },
  { label: 'Módulo', value: 'module' },
]

const moduleOptions = [
  { label: '📄 Cargar .env', value: 'load_env' },
  { label: '↗ Mover archivo', value: 'move_file' },
  { label: '⧉ Copiar archivo', value: 'copy_file' },
  { label: '🗑 Eliminar archivo', value: 'delete_file' },
  { label: '📁 Crear directorio', value: 'mkdir' },
  { label: '✏ Escribir archivo', value: 'write_file' },
  { label: '✎ Renombrar archivo', value: 'rename_file' },
  { label: '📦 Comprimir', value: 'compress' },
  { label: '📂 Descomprimir', value: 'decompress' },
  { label: '? Verificar existencia', value: 'check_exists' },
  { label: '⏱ Esperar N segundos', value: 'delay' },
  { label: '📝 Log', value: 'log' },
  { label: '✉ Enviar email', value: 'email' },
  { label: '⚡ Llamar pipeline', value: 'call_pipeline' },
]

const favoriteOptions = computed(() =>
  (props.favorites || []).map(f => ({ label: f.path.split('/').pop(), value: f.id }))
)
const pipelineOptions = computed(() =>
  (props.pipelines || []).map(p => ({ label: p.name, value: p.id }))
)

function onTypeChange() {
  local.config = {}
  if (local.step_type === 'shell') local.config.command = ''
  if (local.step_type === 'module') local.config.module = 'log'
}

function onModuleChange() {
  const m = local.config.module
  local.config = { module: m }
  if (m === 'load_env' || m === 'delete_file' || m === 'mkdir') local.config.path = ''
  if (m === 'move_file' || m === 'copy_file') { local.config.src = ''; local.config.dst = '' }
  if (m === 'compress') { local.config.src = ''; local.config.dst = ''; local.config.format = 'tar.gz' }
  if (m === 'decompress') { local.config.src = ''; local.config.dst = '' }
  if (m === 'write_file') { local.config.path = ''; local.config.content = ''; local.config.mode = 'overwrite' }
  if (m === 'rename_file') { local.config.path = ''; local.config.new_name = ''; local.config.use_timestamp = false }
  if (m === 'check_exists') { local.config.path = ''; local.config.type = 'file' }
  if (m === 'delay') local.config.seconds = 5
  if (m === 'log') { local.config.message = ''; local.config.level = 'info' }
  if (m === 'email') { local.config.to = ''; local.config.subject = ''; local.config.body = '' }
  if (m === 'call_pipeline') local.config.pipeline_id = null
}

import { computed } from 'vue'
</script>

<style scoped>
.step-config { display: flex; flex-direction: column; gap: 10px; }
.config-row { display: flex; flex-direction: column; gap: 4px; }
.config-label { font-family: var(--font-mono); font-size: var(--text-2xs); letter-spacing: 1.5px; color: var(--p-text-muted-color); text-transform: uppercase; }
</style>
```

- [ ] **Step 5: Verificar que la app compila**

```bash
cd /home/crt/server_dashboard/frontend
npm run build 2>&1 | tail -20
```
Expected: `✓ built in` sin errores.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/PipelinesView.vue frontend/src/components/pipelines/StepConfigEditor.vue frontend/src/router/index.js frontend/src/components/layout/AppSidebar.vue
git commit -m "feat(pipelines): add PipelinesView with 3-panel layout and StepConfigEditor"
```

---

## Task 8: Integración Crontab — Tab "PIPELINE"

**Files:**
- Modify: `frontend/src/views/CrontabView.vue`

- [ ] **Step 1: Agregar import de api y datos de pipelines en CrontabView**

En la sección `<script setup>`, agregar después de los imports existentes:
```javascript
// Pipelines para la tab de integración
const availablePipelines = ref([])

async function loadPipelinesList() {
  try {
    const { data } = await api.get('/pipelines/')
    availablePipelines.value = data
  } catch { /* silencioso si falla */ }
}
```

Y en `onMounted`:
```javascript
loadPipelinesList()
```

- [ ] **Step 2: Agregar estado de selección de pipeline en el form**

El form del wizard ya existe. Agregar variables para la tab de pipeline:
```javascript
const formTab = ref('command')  // 'command' | 'favorite' | 'pipeline'
const selectedPipelineId = ref(null)

const pipelineCommand = computed(() => {
  if (!selectedPipelineId.value) return ''
  return `python -m backend.scripts.pipeline_runner --pipeline-id ${selectedPipelineId.value}`
})

watch(pipelineCommand, (cmd) => {
  if (formTab.value === 'pipeline' && cmd && form.value) {
    form.value.command = cmd
  }
})
```

- [ ] **Step 3: Agregar la tab "PIPELINE" en el template — Step 2 (COMMAND)**

Localizar el bloque de Step 2 (buscar `<!-- ── Step 2: COMMAND`) y agregar la tab selector + panel pipeline:

```vue
<!-- Tab selector (agregar antes del bloque de "Favorites") -->
<div class="cmd-tabs">
  <button class="cmd-tab" :class="{ active: formTab === 'favorite' }" @click="formTab = 'favorite'">
    SCRIPT FAVORITO
  </button>
  <button class="cmd-tab" :class="{ active: formTab === 'command' }" @click="formTab = 'command'">
    COMANDO
  </button>
  <button class="cmd-tab cmd-tab--pipeline" :class="{ active: formTab === 'pipeline' }" @click="formTab = 'pipeline'">
    ⚡ PIPELINE
  </button>
</div>

<!-- Tab: Pipeline -->
<div v-if="formTab === 'pipeline'" class="pipeline-tab">
  <div class="section-label">SELECCIONÁ UN PIPELINE</div>
  <div class="pipeline-select-list">
    <div
      v-for="p in availablePipelines" :key="p.id"
      class="pipeline-select-card"
      :class="{ active: selectedPipelineId === p.id }"
      @click="selectedPipelineId = p.id"
    >
      <span class="pipeline-select-name">⚡ {{ p.name }}</span>
      <span class="pipeline-select-steps">{{ p.step_count }} pasos</span>
    </div>
    <div v-if="!availablePipelines.length" class="pipeline-select-empty">
      No hay pipelines. Creá uno en la sección Pipelines.
    </div>
  </div>
  <div v-if="pipelineCommand" class="pipeline-cmd-preview">
    <span class="pipeline-cmd-label">COMANDO GENERADO</span>
    <code class="pipeline-cmd-code">{{ pipelineCommand }}</code>
  </div>
</div>
```

- [ ] **Step 4: Agregar estilos CSS para la tab**

Al final del `<style scoped>`:
```css
.cmd-tabs { display: flex; gap: 0; margin-bottom: 12px; border-bottom: 1px solid var(--p-surface-border); }
.cmd-tab { padding: 6px 14px; font-family: var(--font-mono); font-size: var(--text-2xs); letter-spacing: 1px; background: none; border: none; border-bottom: 2px solid transparent; color: var(--p-text-muted-color); cursor: pointer; transition: color 0.15s, border-color 0.15s; }
.cmd-tab:hover { color: var(--p-text-color); }
.cmd-tab.active { color: var(--brand-orange); border-bottom-color: var(--brand-orange); }
.cmd-tab--pipeline.active { color: var(--p-green-400); border-bottom-color: var(--p-green-400); }
.pipeline-tab { display: flex; flex-direction: column; gap: 10px; }
.pipeline-select-list { display: flex; flex-direction: column; gap: 4px; max-height: 200px; overflow-y: auto; }
.pipeline-select-card { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; background: var(--p-surface-ground); border: 1px solid var(--p-surface-border); border-radius: 6px; cursor: pointer; transition: border-color 0.15s; }
.pipeline-select-card:hover { border-color: var(--p-text-muted-color); }
.pipeline-select-card.active { border-color: var(--p-green-400); background: color-mix(in srgb, var(--p-green-400) 8%, transparent); }
.pipeline-select-name { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-color); }
.pipeline-select-steps { font-family: var(--font-mono); font-size: 9px; color: var(--p-text-muted-color); }
.pipeline-select-empty { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-muted-color); padding: 12px; text-align: center; }
.pipeline-cmd-preview { background: var(--p-surface-ground); border: 1px solid var(--p-surface-border); border-radius: 6px; padding: 8px 12px; }
.pipeline-cmd-label { font-family: var(--font-mono); font-size: var(--text-2xs); letter-spacing: 1px; color: var(--p-text-muted-color); display: block; margin-bottom: 4px; }
.pipeline-cmd-code { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-cyan-400); }
```

- [ ] **Step 5: Verificar build**

```bash
cd /home/crt/server_dashboard/frontend && npm run build 2>&1 | tail -10
```
Expected: sin errores.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/CrontabView.vue
git commit -m "feat(pipelines): add Pipeline tab in CrontabView step 2"
```

---

## Task 9: Test Final + Bitácora

- [ ] **Step 1: Ejecutar suite completa de tests**

```bash
cd /home/crt/server_dashboard && pytest -q
```
Expected: todos en verde.

- [ ] **Step 2: Actualizar bitácora en `docs/bitacora.md`**

Agregar entrada con fecha de implementación, archivos modificados, decisiones tomadas, y bugs conocidos.

- [ ] **Step 3: Actualizar roadmap en `docs/bitacora.md`**

Marcar el plan de Pipelines como `(IMPLEMENTADO ✓)` en la sección de Roadmap.

- [ ] **Step 4: Commit final**

```bash
git add docs/bitacora.md
git commit -m "docs: update bitácora — pipeline system implemented"
```

---

## Resumen de Archivos

| Archivo | Estado |
|---|---|
| `backend/models/pipeline.py` | CREAR |
| `backend/schemas/pipeline.py` | CREAR |
| `backend/services/pipeline_modules.py` | CREAR |
| `backend/services/pipeline_service.py` | CREAR |
| `backend/routers/pipelines.py` | CREAR |
| `backend/scripts/pipeline_runner.py` | CREAR |
| `frontend/src/views/PipelinesView.vue` | CREAR |
| `frontend/src/components/pipelines/StepConfigEditor.vue` | CREAR |
| `tests/test_pipeline_modules.py` | CREAR |
| `tests/test_pipeline_service.py` | CREAR |
| `tests/test_pipelines_api.py` | CREAR |
| `backend/main.py` | MODIFICAR |
| `backend/config.py` | MODIFICAR |
| `backend/scripts/add_indexes.py` | MODIFICAR |
| `frontend/src/router/index.js` | MODIFICAR |
| `frontend/src/components/layout/AppSidebar.vue` | MODIFICAR |
| `frontend/src/views/CrontabView.vue` | MODIFICAR |
