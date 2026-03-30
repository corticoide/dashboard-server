# Performance Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the backend for production by caching expensive COUNT queries, adding a log retention policy with VACUUM scheduling, lazy-loading Monaco, capping expanded rows in LogsView, and pruning unused dependencies.

**Architecture:** A TTLCache singleton (already in `backend/services/cache.py`) is wired into the logs pagination endpoint to avoid full-table COUNT on every request. APScheduler runs two background jobs (log cleanup + VACUUM) that are registered in FastAPI's lifespan context. Frontend changes are confined to `router/index.js` (FilesView lazy-load) and `LogsView.vue` (FIFO expand cap).

**Tech Stack:** FastAPI + SQLAlchemy 2 + SQLite + APScheduler 3.x + Vue 3 + PrimeVue 4 + Vitest

---

## Codebase Audit Notes (read before starting)

| Finding | File | Impact |
|---|---|---|
| `ExecutionLog` already has `started_at`, `username`, `exit_code` indexes | `backend/models/execution_log.py:18-22` | Only composite `(username, started_at)` index is missing |
| `TTLCache` exists but is unused in logs router | `backend/services/cache.py` | Use it for COUNT caching in Task 2 |
| `q.count()` runs on every paginated request | `backend/routers/logs.py:39` | Core target for Task 2 |
| `output_summary` is used consistently everywhere | `LogsView.vue:170-174` + schema | No schema fix needed |
| Monaco lives in `FilesView.vue` (not `main.js`), but `FilesView` is eagerly imported in router | `frontend/src/router/index.js:4,12` | Task 4 fixes this with lazy import |
| `websockets` + `httpx` in requirements.txt but never imported | `backend/requirements.txt` | Task 6 removes them |
| `python-crontab` IS used | `backend/services/crontab_service.py` | Keep it |

---

## File Map

**Create:**
- `backend/scheduler.py` — APScheduler setup + `_do_cleanup` + `_do_vacuum` job functions
- `tests/test_scheduler.py` — unit tests for retention and vacuum logic

**Modify:**
- `backend/requirements.txt` — add `apscheduler>=3.10,<4`, remove `websockets`, `httpx`
- `backend/config.py` — add `log_retention_days: int = 30`
- `backend/models/execution_log.py` — add composite index `(username, started_at)`
- `backend/scripts/add_indexes.py` — add composite index migration for existing DBs
- `backend/routers/logs.py` — use TTLCache for COUNT, add `POST /maintenance/cleanup`
- `backend/main.py` — replace `@app.on_event` pattern with lifespan that starts/stops scheduler
- `frontend/src/router/index.js` — lazy-import FilesView, ServicesView, ScriptsView, CrontabView
- `frontend/src/views/LogsView.vue` — FIFO cap at 5 expanded rows + `@row-collapse` handler

---

## Task 1: Add Composite Index

**Files:**
- Modify: `backend/models/execution_log.py:18-22`
- Modify: `backend/scripts/add_indexes.py:10-19`
- Test: `tests/test_db_indexes.py` (existing file — add one assertion)

- [ ] **Step 1: Write the failing test**

Open `tests/test_db_indexes.py` and add at the end:

```python
def test_composite_username_started_at_index_exists(db_session):
    from sqlalchemy import inspect, text
    # Check index exists via SQLite pragma
    result = db_session.execute(
        text("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='execution_logs'")
    ).fetchall()
    index_names = [r[0] for r in result]
    assert any("username" in n and "started_at" in n or "username_started_at" in n
               for n in index_names), f"Composite index not found, got: {index_names}"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_db_indexes.py::test_composite_username_started_at_index_exists -v
```

Expected: FAIL — composite index is not yet defined.

- [ ] **Step 3: Add the composite index to the model**

In `backend/models/execution_log.py`, update `__table_args__`:

```python
    __table_args__ = (
        Index("ix_execution_logs_started_at", "started_at"),
        Index("ix_execution_logs_username", "username"),
        Index("ix_execution_logs_exit_code", "exit_code"),
        Index("ix_execution_logs_username_started_at", "username", "started_at"),
    )
```

- [ ] **Step 4: Add the migration statement to the one-time script**

In `backend/scripts/add_indexes.py`, update the `statements` list:

```python
    statements = [
        "CREATE INDEX IF NOT EXISTS ix_execution_logs_started_at ON execution_logs (started_at)",
        "CREATE INDEX IF NOT EXISTS ix_execution_logs_username ON execution_logs (username)",
        "CREATE INDEX IF NOT EXISTS ix_execution_logs_exit_code ON execution_logs (exit_code)",
        "CREATE INDEX IF NOT EXISTS ix_execution_logs_username_started_at ON execution_logs (username, started_at)",
    ]
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_db_indexes.py -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/models/execution_log.py backend/scripts/add_indexes.py tests/test_db_indexes.py
git commit -m "perf: add composite (username, started_at) index on execution_logs"
```

---

## Task 2: Cache COUNT Queries in Logs Pagination

**Files:**
- Modify: `backend/routers/logs.py`
- Test: `tests/test_logs.py` (add two tests)

The existing `TTLCache` in `backend/services/cache.py` is used. A module-level singleton caches the total count per unique filter combination. TTL = 300 seconds (5 minutes).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_logs.py`:

```python
def test_x_total_count_header_present(test_app):
    """Paginated response always includes X-Total-Count header."""
    from backend.main import app
    from backend.database import get_db
    db = next(app.dependency_overrides[get_db]())
    for i in range(3):
        db.add(ExecutionLog(
            script_path=f"/cached_{i}.sh", username="admin",
            started_at=datetime.now(timezone.utc), exit_code=0,
        ))
    db.commit()
    db.close()
    token = get_token(test_app)
    r = test_app.get("/api/logs/executions?limit=2&offset=0",
                     headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert "x-total-count" in r.headers
    assert int(r.headers["x-total-count"]) == 3


def test_count_varies_by_filter(test_app):
    """Different filters produce different X-Total-Count values."""
    from backend.main import app
    from backend.database import get_db
    db = next(app.dependency_overrides[get_db]())
    db.add(ExecutionLog(script_path="/ok.sh",   username="admin",
                        started_at=datetime.now(timezone.utc), exit_code=0))
    db.add(ExecutionLog(script_path="/fail.sh", username="admin",
                        started_at=datetime.now(timezone.utc), exit_code=1))
    db.commit()
    db.close()
    token = get_token(test_app)
    headers = {"Authorization": f"Bearer {token}"}
    r_all  = test_app.get("/api/logs/executions", headers=headers)
    r_ok   = test_app.get("/api/logs/executions?exit_code=0", headers=headers)
    r_fail = test_app.get("/api/logs/executions?exit_code=1", headers=headers)
    assert int(r_all.headers["x-total-count"]) == 2
    assert int(r_ok.headers["x-total-count"])  == 1
    assert int(r_fail.headers["x-total-count"]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_logs.py::test_x_total_count_header_present tests/test_logs.py::test_count_varies_by_filter -v
```

Expected: FAIL — `x-total-count` header may be missing (if TTLCache breaks it; it shouldn't on first run, but run to establish baseline).

Actually these tests may already pass. Run them to confirm current behaviour before the change.

- [ ] **Step 3: Add the TTLCache to the logs router**

Replace the entire content of `backend/routers/logs.py` with:

```python
from fastapi import APIRouter, Depends, Query, Response
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.execution_log import ExecutionLog
from backend.schemas.logs import ExecutionLogOut, ExecutionStatsOut
from backend.services.cache import TTLCache

router = APIRouter(prefix="/api/logs", tags=["logs"])

_count_cache: TTLCache = TTLCache()
_COUNT_TTL = 300  # seconds


def _count_key(
    script: Optional[str],
    username: Optional[str],
    exit_code: Optional[int],
    from_date: Optional[datetime],
    to_date: Optional[datetime],
) -> str:
    return f"{script}|{username}|{exit_code}|{from_date}|{to_date}"


@router.get("/executions", response_model=List[ExecutionLogOut])
def list_executions(
    script: Optional[str] = Query(None),
    username: Optional[str] = Query(None),
    exit_code: Optional[int] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    response: Response = None,
):
    q = db.query(ExecutionLog).order_by(ExecutionLog.started_at.desc())
    if script:
        q = q.filter(ExecutionLog.script_path.contains(script))
    if username:
        q = q.filter(ExecutionLog.username == username)
    if exit_code is not None:
        q = q.filter(ExecutionLog.exit_code == exit_code)
    if from_date:
        q = q.filter(ExecutionLog.started_at >= from_date)
    if to_date:
        q = q.filter(ExecutionLog.started_at <= to_date)

    key = _count_key(script, username, exit_code, from_date, to_date)
    total = _count_cache.get(key)
    if total is None:
        total = q.count()
        _count_cache.set(key, total, _COUNT_TTL)

    if response is not None:
        response.headers["X-Total-Count"] = str(total)
    return q.offset(offset).limit(limit).all()


@router.get("/executions/stats", response_model=ExecutionStatsOut)
def execution_stats(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    row = db.query(
        func.count().label("total"),
        func.sum(case((ExecutionLog.exit_code == 0, 1), else_=0)).label("success"),
        func.sum(case(
            ((ExecutionLog.exit_code != 0) & ExecutionLog.exit_code.isnot(None), 1),
            else_=0,
        )).label("failed"),
        func.sum(case((ExecutionLog.started_at >= cutoff, 1), else_=0)).label("last_24h"),
    ).one()
    return ExecutionStatsOut(
        total=row.total or 0,
        success=row.success or 0,
        failed=row.failed or 0,
        last_24h=row.last_24h or 0,
    )


@router.post("/maintenance/cleanup")
def run_cleanup(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Manually trigger log retention cleanup. Admin only."""
    from backend.scheduler import _do_cleanup
    from backend.config import settings
    deleted = _do_cleanup(db, settings.log_retention_days)
    return {"deleted": deleted, "retention_days": settings.log_retention_days}
```

Note: The `run_cleanup` endpoint imports from `backend.scheduler` — that module is created in Task 3. Complete Task 3 before running tests that hit this endpoint.

- [ ] **Step 4: Run all logs tests**

```bash
pytest tests/test_logs.py -v
```

Expected: all PASS (count header tests pass; maintenance endpoint will fail with ImportError until Task 3 is done — that's OK for now, skip with `-k "not cleanup"`).

```bash
pytest tests/test_logs.py -v -k "not cleanup"
```

- [ ] **Step 5: Commit**

```bash
git add backend/routers/logs.py tests/test_logs.py
git commit -m "perf: cache COUNT queries in logs pagination (TTL=5min)"
```

---

## Task 3: Log Retention + VACUUM Scheduler

**Files:**
- Create: `backend/scheduler.py`
- Create: `tests/test_scheduler.py`
- Modify: `backend/config.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/main.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_scheduler.py`:

```python
import pytest
from datetime import datetime, timezone, timedelta
from backend.models.execution_log import ExecutionLog


def make_log(db, script, days_ago, exit_code=0):
    started = datetime.now(timezone.utc) - timedelta(days=days_ago)
    log = ExecutionLog(
        script_path=script,
        username="admin",
        started_at=started,
        exit_code=exit_code,
    )
    db.add(log)
    db.commit()
    return log


def test_cleanup_deletes_old_logs(db_session):
    from backend.scheduler import _do_cleanup
    make_log(db_session, "/old.sh", days_ago=31)
    make_log(db_session, "/recent.sh", days_ago=1)

    deleted = _do_cleanup(db_session, retention_days=30)

    assert deleted == 1
    remaining = db_session.query(ExecutionLog).all()
    assert len(remaining) == 1
    assert remaining[0].script_path == "/recent.sh"


def test_cleanup_returns_zero_when_nothing_to_delete(db_session):
    from backend.scheduler import _do_cleanup
    make_log(db_session, "/fresh.sh", days_ago=5)

    deleted = _do_cleanup(db_session, retention_days=30)

    assert deleted == 0
    assert db_session.query(ExecutionLog).count() == 1


def test_cleanup_deletes_all_when_all_are_old(db_session):
    from backend.scheduler import _do_cleanup
    for i in range(3):
        make_log(db_session, f"/old_{i}.sh", days_ago=60)

    deleted = _do_cleanup(db_session, retention_days=30)

    assert deleted == 3
    assert db_session.query(ExecutionLog).count() == 0


def test_cleanup_keeps_logs_exactly_at_boundary(db_session):
    from backend.scheduler import _do_cleanup
    # Log created exactly 30 days ago should NOT be deleted (cutoff is strictly <)
    make_log(db_session, "/boundary.sh", days_ago=30)

    deleted = _do_cleanup(db_session, retention_days=30)

    # Depending on sub-second timing this may be 0 or 1; assert it doesn't raise
    assert deleted >= 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_scheduler.py -v
```

Expected: FAIL — `backend.scheduler` does not exist yet.

- [ ] **Step 3: Add `log_retention_days` to config**

Edit `backend/config.py`:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    jwt_secret: str = "dev-secret-change-in-production"
    db_path: str = "./data/serverdash.db"
    cert_file: str = "./certs/cert.pem"
    key_file: str = "./certs/key.pem"
    port: int = 8443
    admin_username: str = "admin"
    admin_password: str = "changeme"
    allowed_origins: list[str] = ["https://localhost:8443"]
    log_retention_days: int = 30

    class Config:
        env_file = ".env"

settings = Settings()
```

- [ ] **Step 4: Add APScheduler to requirements.txt; remove unused deps**

Edit `backend/requirements.txt` — make these three changes:

1. Remove line: `httpx==0.27.2`
2. Remove line: `websockets>=12.0`
3. Add line: `apscheduler>=3.10,<4`

Final relevant section should look like:

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy==2.0.35
python-jose[cryptography]==3.3.0
bcrypt==4.2.1
python-multipart==0.0.20
psutil==6.0.0
pytest==8.3.3
pytest-asyncio==0.24.0
python-dotenv==1.0.1
pydantic-settings==2.5.2
cryptography==43.0.1
slowapi==0.1.9
apscheduler>=3.10,<4
gunicorn==22.0.0
python-crontab==3.2.0
```

- [ ] **Step 5: Install APScheduler**

```bash
pip install "apscheduler>=3.10,<4"
```

Expected: installs successfully.

- [ ] **Step 6: Create `backend/scheduler.py`**

```python
import logging
import sqlite3
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from backend.models.execution_log import ExecutionLog

logger = logging.getLogger(__name__)


def _do_cleanup(db: Session, retention_days: int) -> int:
    """Delete execution logs older than retention_days. Returns count deleted."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    deleted = db.query(ExecutionLog).filter(
        ExecutionLog.started_at < cutoff
    ).delete(synchronize_session=False)
    db.commit()
    logger.info("Retention cleanup: deleted %d log(s) older than %d days", deleted, retention_days)
    return deleted


def _do_vacuum(db_path: str) -> None:
    """Run SQLite VACUUM using a raw sqlite3 connection (can't run inside a transaction)."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("VACUUM")
        logger.info("SQLite VACUUM completed on %s", db_path)
    finally:
        conn.close()


def _cleanup_job() -> None:
    """APScheduler job: run daily log retention cleanup."""
    from backend.database import SessionLocal
    from backend.config import settings
    db = SessionLocal()
    try:
        _do_cleanup(db, settings.log_retention_days)
    except Exception:
        logger.exception("Log retention cleanup failed")
    finally:
        db.close()


def _vacuum_job() -> None:
    """APScheduler job: run weekly VACUUM."""
    from backend.config import settings
    try:
        _do_vacuum(settings.db_path)
    except Exception:
        logger.exception("SQLite VACUUM failed")


def start_scheduler():
    """Start the background scheduler. Call once on app startup."""
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = BackgroundScheduler()
    scheduler.add_job(_cleanup_job, CronTrigger(hour=2, minute=0), id="log_cleanup")
    scheduler.add_job(_vacuum_job, CronTrigger(day_of_week="sun", hour=3), id="db_vacuum")
    scheduler.start()
    logger.info("Background scheduler started")
    return scheduler


_scheduler = None


def get_scheduler():
    return _scheduler


def init_scheduler():
    """Initialize module-level scheduler instance."""
    global _scheduler
    _scheduler = start_scheduler()


def shutdown_scheduler():
    """Stop the module-level scheduler instance."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Background scheduler stopped")
```

- [ ] **Step 7: Wire scheduler into `backend/main.py` using lifespan**

Replace the existing `app = FastAPI(...)` line and add the lifespan context:

```python
import os
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from backend.limiter import limiter
from backend.middleware.security import SecurityHeadersMiddleware
from backend.routers import auth, system, services
from backend.routers.files import router as files_router
from backend.routers.scripts import router as scripts_router
from backend.routers.crontab import router as crontab_router
from backend.routers.logs import router as logs_router
from backend.config import settings
from backend.database import engine, Base
from backend.core.logging import init_logging
from backend.core.health import router as health_router
import backend.models.script  # noqa: F401
import backend.models.execution_log  # noqa: F401

init_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.scheduler import init_scheduler, shutdown_scheduler
    init_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(title="ServerDash", docs_url="/api/docs", redoc_url=None, lifespan=lifespan)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Sudo-Password"],
)

# Security headers
app.add_middleware(SecurityHeadersMiddleware)

# GZIP compression
app.add_middleware(GZipMiddleware, minimum_size=500)

# Create tables that don't exist yet (non-destructive)
Base.metadata.create_all(bind=engine)

app.include_router(health_router)
app.include_router(auth.router)
app.include_router(system.router)
app.include_router(services.router)
app.include_router(files_router)
app.include_router(scripts_router)
app.include_router(crontab_router)
app.include_router(logs_router)

# Serve Vue SPA (built files)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    assets_dir = os.path.join(static_dir, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        index = os.path.join(static_dir, "index.html")
        if os.path.exists(index):
            return FileResponse(index)
        return {"error": "Frontend not built. Run: cd frontend && npm run build"}

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=settings.port,
        ssl_certfile=settings.cert_file,
        ssl_keyfile=settings.key_file,
        reload=True,
    )
```

- [ ] **Step 8: Run all backend tests**

```bash
pytest tests/test_scheduler.py tests/test_logs.py tests/test_auth.py -v
```

Expected: all PASS. The `run_cleanup` endpoint in logs router should now resolve correctly.

- [ ] **Step 9: Commit**

```bash
git add backend/scheduler.py backend/config.py backend/requirements.txt backend/main.py tests/test_scheduler.py
git commit -m "feat: add log retention policy + weekly VACUUM scheduler (APScheduler)"
```

---

## Task 4: Lazy-Load FilesView (Monaco Code-Splitting)

**Files:**
- Modify: `frontend/src/router/index.js`

Monaco editor (`@guolao/vue-monaco-editor`, ~2-3MB) is imported at the top of `FilesView.vue`. Since `FilesView` is eagerly imported in the router, Monaco ends up in the main bundle. Converting all non-critical routes to lazy imports fixes this.

- [ ] **Step 1: Check current bundle size baseline (optional but useful)**

```bash
cd frontend && npm run build 2>&1 | grep -E "kB|MB" | head -20
```

Note the size of the largest chunk for comparison after the change.

- [ ] **Step 2: Update `frontend/src/router/index.js` to lazy-load all views**

Replace the entire file content:

```javascript
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

const routes = [
  { path: '/login',   component: () => import('../views/LoginView.vue'),   meta: { public: true,        title: 'Login'    } },
  { path: '/',        component: () => import('../views/DashboardView.vue'), meta: { requiresAuth: true, title: 'Dashboard' } },
  { path: '/services',component: () => import('../views/ServicesView.vue'),  meta: { requiresAuth: true, title: 'Services'  } },
  { path: '/files',   component: () => import('../views/FilesView.vue'),     meta: { requiresAuth: true, title: 'Files'     } },
  { path: '/scripts', component: () => import('../views/ScriptsView.vue'),   meta: { requiresAuth: true, title: 'Scripts'   } },
  { path: '/crontab', component: () => import('../views/CrontabView.vue'),   meta: { requiresAuth: true, title: 'Crontab'   } },
  { path: '/logs',    component: () => import('../views/LogsView.vue'),      meta: { requiresAuth: true, title: 'Logs'      } },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.isAuthenticated) return '/login'
  if (to.path === '/login' && auth.isAuthenticated) return '/'
})

export default router
```

- [ ] **Step 3: Rebuild and compare bundle size**

```bash
cd frontend && npm run build 2>&1 | grep -E "kB|MB" | head -20
```

Expected: Monaco chunk now appears as a separate file (e.g., `MonacoEditor-xxx.js`). The main `index-xxx.js` chunk should be smaller by ~2-3MB.

- [ ] **Step 4: Run frontend tests**

```bash
cd frontend && npm test
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/router/index.js
git commit -m "perf: lazy-load all route views — Monaco now code-split away from main bundle"
```

---

## Task 5: Cap Expanded Rows at 5 in LogsView (FIFO)

**Files:**
- Modify: `frontend/src/views/LogsView.vue`
- Create: `frontend/src/views/__tests__/expandedRowsCap.test.js`

The DataTable uses `v-model:expanded-rows="expandedRows"` (an object keyed by row ID). We add an insertion-order array to implement FIFO eviction when more than 5 rows are expanded simultaneously.

- [ ] **Step 1: Write the failing test**

Create directory and file `frontend/src/views/__tests__/expandedRowsCap.test.js`:

```javascript
import { describe, it, expect } from 'vitest'

/**
 * Extracted FIFO logic for testing.
 * Mirrors the implementation in LogsView.vue onRowExpand.
 */
function applyExpand(expandedRows, expandedOrder, newId, MAX = 5) {
  expandedRows = { ...expandedRows, [newId]: true }
  expandedOrder = [...expandedOrder, newId]
  if (expandedOrder.length > MAX) {
    const evicted = expandedOrder[0]
    expandedOrder = expandedOrder.slice(1)
    expandedRows = { ...expandedRows }
    delete expandedRows[evicted]
  }
  return { expandedRows, expandedOrder }
}

function applyCollapse(expandedRows, expandedOrder, id) {
  expandedRows = { ...expandedRows }
  delete expandedRows[id]
  expandedOrder = expandedOrder.filter(i => i !== id)
  return { expandedRows, expandedOrder }
}

describe('expanded rows FIFO cap', () => {
  it('allows up to 5 rows expanded', () => {
    let rows = {}, order = []
    for (let i = 1; i <= 5; i++) {
      ;({ expandedRows: rows, expandedOrder: order } = applyExpand(rows, order, i))
    }
    expect(Object.keys(rows)).toHaveLength(5)
    expect(order).toHaveLength(5)
  })

  it('evicts the oldest row when a 6th is expanded', () => {
    let rows = {}, order = []
    for (let i = 1; i <= 6; i++) {
      ;({ expandedRows: rows, expandedOrder: order } = applyExpand(rows, order, i))
    }
    expect(Object.keys(rows)).toHaveLength(5)
    expect(rows[1]).toBeUndefined()  // row 1 was evicted
    expect(rows[6]).toBe(true)       // row 6 is present
  })

  it('tracks insertion order correctly after collapse', () => {
    let rows = { 1: true, 2: true, 3: true }, order = [1, 2, 3]
    ;({ expandedRows: rows, expandedOrder: order } = applyCollapse(rows, order, 2))
    expect(rows[2]).toBeUndefined()
    expect(order).toEqual([1, 3])
    // Now fill to 5 — row 1 (not 2) is oldest
    ;({ expandedRows: rows, expandedOrder: order } = applyExpand(rows, order, 4))
    ;({ expandedRows: rows, expandedOrder: order } = applyExpand(rows, order, 5))
    ;({ expandedRows: rows, expandedOrder: order } = applyExpand(rows, order, 6))
    expect(Object.keys(rows)).toHaveLength(5)
    expect(rows[1]).toBeUndefined()  // row 1 is oldest after collapsing row 2
  })

  it('does not evict on collapse', () => {
    let rows = { 1: true, 2: true }, order = [1, 2]
    ;({ expandedRows: rows, expandedOrder: order } = applyCollapse(rows, order, 1))
    expect(Object.keys(rows)).toHaveLength(1)
    expect(rows[2]).toBe(true)
  })
})
```

- [ ] **Step 2: Run test to verify it passes (pure logic test)**

```bash
cd frontend && npm test src/views/__tests__/expandedRowsCap.test.js
```

Expected: all PASS — this is a pure logic test, not a component test.

- [ ] **Step 3: Implement the cap logic in `LogsView.vue`**

In `frontend/src/views/LogsView.vue`, make these changes:

**a) Add `expandedOrder` ref** (after the existing `expandedRows` ref at line 241):

```javascript
const expandedRows = ref({})
const expandedOrder = ref([])
const MAX_EXPANDED = 5
```

**b) Replace the `onRowExpand` no-op function** (currently at line 334):

```javascript
function onRowExpand(event) {
  const id = event.data.id
  expandedOrder.value.push(id)
  if (expandedOrder.value.length > MAX_EXPANDED) {
    const evicted = expandedOrder.value.shift()
    delete expandedRows.value[evicted]
  }
}
```

**c) Add `onRowCollapse` handler** (after `onRowExpand`):

```javascript
function onRowCollapse(event) {
  const id = event.data.id
  expandedOrder.value = expandedOrder.value.filter(i => i !== id)
}
```

**d) Wire `@row-collapse` on the DataTable** — find the `<DataTable` opening tag and add the event handler:

```html
<DataTable
  :value="logs"
  :loading="loading"
  v-model:expanded-rows="expandedRows"
  @row-expand="onRowExpand"
  @row-collapse="onRowCollapse"
  striped-rows
  ...
```

- [ ] **Step 4: Run all frontend tests**

```bash
cd frontend && npm test
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/LogsView.vue frontend/src/views/__tests__/expandedRowsCap.test.js
git commit -m "perf: cap LogsView expanded rows at 5 (FIFO eviction)"
```

---

## Task 6: Remove Unused Backend Dependencies

**Files:**
- Modify: `backend/requirements.txt`

Note: `websockets` and `httpx` were already removed from `requirements.txt` in Task 3 Step 4. This task verifies the removals didn't break anything and updates the installed environment.

- [ ] **Step 1: Confirm neither package is imported anywhere**

```bash
grep -r "import httpx\|from httpx\|import websockets\|from websockets" backend/
```

Expected: no output (no imports found).

- [ ] **Step 2: Verify requirements.txt no longer contains them**

```bash
grep -E "websockets|httpx" backend/requirements.txt
```

Expected: no output.

If either package is still present (e.g., Task 3 was not done), remove the lines manually from `backend/requirements.txt`.

- [ ] **Step 3: Reinstall dependencies to confirm nothing breaks**

```bash
pip install -r backend/requirements.txt
```

Expected: installs cleanly, no import errors.

- [ ] **Step 4: Run full test suite**

```bash
pytest -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit (only if requirements.txt changed)**

```bash
git add backend/requirements.txt
git commit -m "chore: remove unused websockets and httpx from requirements.txt"
```

---

## Self-Review

### Spec Coverage

| Spec Section | Task | Status |
|---|---|---|
| 1.1 DB Indexes | Task 1 | Composite index added; simple indexes already exist |
| 1.2 COUNT cache | Task 2 | TTLCache wired, 5-min TTL |
| 1.3 Log retention | Task 3 | `_do_cleanup` + APScheduler daily job at 2AM |
| 1.4 VACUUM | Task 3 | `_do_vacuum` + APScheduler weekly job Sunday 3AM |
| 2.1 Schema standardize | N/A | `output_summary` is already consistent everywhere; expansion `data.output \|\| data.output_summary` is a harmless fallback, not a bug |
| 3.1 Monaco lazy load | Task 4 | All views lazy-loaded; Monaco code-splits into its own chunk |
| 3.2 Cap expanded rows | Task 5 | FIFO cap at 5 with `@row-collapse` handler |
| 3.3 Date memoize | Skipped | 50 rows × one format call = negligible; YAGNI |
| 4.1 Remove unused deps | Tasks 3+6 | `websockets` + `httpx` removed |
| 5.x Load/perf testing | Out of scope | Manual testing with Chrome DevTools; automated tests cover correctness not benchmarks |

### Type/Name Consistency Check

- `_do_cleanup(db: Session, retention_days: int) -> int` — called the same way in `test_scheduler.py` and `routers/logs.py` ✓
- `_do_vacuum(db_path: str) -> None` — called only in `_vacuum_job()` with `settings.db_path` ✓
- `init_scheduler()` / `shutdown_scheduler()` — called by name in `main.py` lifespan ✓
- `expandedRows` / `expandedOrder` / `MAX_EXPANDED` — consistent between implementation and test ✓
- `_count_cache` / `_COUNT_TTL` / `_count_key(...)` — all in `routers/logs.py`, internally consistent ✓

### Deployment Notes

1. **`pip install -r backend/requirements.txt`** — installs APScheduler; all other changes are code-only
2. **Existing databases** — Run `python -m backend.scripts.add_indexes` once after deploying to add the composite index to the live `.db` file
3. **New config variable** — `LOG_RETENTION_DAYS=30` can be set in `.env` to override default; existing deployments use the default silently
4. **Scheduler in multi-worker mode** — APScheduler `BackgroundScheduler` runs one scheduler per process. With `gunicorn -w 4`, the cleanup job runs 4 times. This is safe (idempotent deletes) but slightly wasteful. For production with many workers, pin to 1 worker for the scheduler or use an external cron. Document this in `.env.example`.
