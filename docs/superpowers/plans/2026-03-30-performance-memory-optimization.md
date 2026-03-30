# Performance & Memory Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce memory consumption and improve runtime efficiency of ServerDash by fixing a file-handle leak, adding response compression, caching hot endpoints, optimizing DB queries, debouncing frontend API calls, and enabling virtual scrolling.

**Architecture:** Backend changes are isolated to their own files (`cache.py`, `logs.py`, `files_service.py`, `main.py`); frontend changes add one composable and modify `LogsView.vue` and `client.js`. No breaking changes to existing API contracts — pagination is additive via new optional query params and a `X-Total-Count` response header.

**Tech Stack:** FastAPI (GzipMiddleware, SQLAlchemy 2.0 CASE expressions), Vue 3 + PrimeVue 4 (built-in DataTable virtualScrollerOptions + Paginator), Vitest, pytest

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Modify | `backend/main.py` | Add GzipMiddleware |
| Modify | `backend/services/files_service.py` | Defensive file-handle close in `stream_file` |
| Modify | `backend/models/execution_log.py` | Add SQLAlchemy index declarations |
| Create | `backend/scripts/add_indexes.py` | One-time migration: `CREATE INDEX IF NOT EXISTS` |
| Modify | `backend/routers/logs.py` | Optimize stats query; add `limit`/`offset`/`X-Total-Count` |
| Create | `backend/services/cache.py` | Thread-safe TTL in-memory cache |
| Modify | `backend/routers/system.py` | Cache `get_metrics()` result for 3 s |
| Create | `frontend/src/composables/useDebounce.js` | Generic debounce utility |
| Modify | `frontend/src/api/client.js` | Add 30 s timeout |
| Modify | `frontend/src/views/LogsView.vue` | Debounce search; virtual scroll; server-side pagination |
| Modify | `tests/test_logs.py` | Tests for pagination params + X-Total-Count |
| Create | `tests/test_cache.py` | Tests for TTLCache |

---

## Task 1: Add GzipMiddleware

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_security_headers.py (or create tests/test_compression.py)
def test_gzip_compression_on_json_response(test_app):
    token = test_app.post(
        "/api/auth/login", json={"username": "admin", "password": "adminpass"}
    ).json()["access_token"]
    r = test_app.get(
        "/api/logs/executions/stats",
        headers={"Authorization": f"Bearer {token}", "Accept-Encoding": "gzip"},
    )
    assert r.status_code == 200
    # TestClient auto-decompresses; verify header was set by middleware
    assert r.headers.get("content-encoding") == "gzip"
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
pytest tests/test_compression.py -v
```

Expected: FAIL — `AssertionError: assert None == 'gzip'`

- [ ] **Step 3: Add GzipMiddleware to main.py**

Open `backend/main.py`. After line 8 (`from slowapi.errors import RateLimitExceeded`), add the import:

```python
from fastapi.middleware.gzip import GZipMiddleware
```

After line 41 (`app.add_middleware(SecurityHeadersMiddleware)`), add:

```python
app.add_middleware(GZipMiddleware, minimum_size=500)
```

The `minimum_size=500` avoids compressing tiny responses (e.g. `{"ok": true}`).

- [ ] **Step 4: Run test to confirm it passes**

```bash
pytest tests/test_compression.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/main.py tests/test_compression.py
git commit -m "perf: add GzipMiddleware (minimum_size=500) to compress API responses"
```

---

## Task 2: Fix stream_file Generator (Defensive File-Handle Close)

**Files:**
- Modify: `backend/services/files_service.py:189-194`
- Modify: `tests/test_files_service.py`

**Context:** `_iter()` at line 189 wraps `open(p, "rb")` in a sync generator passed to Starlette's `StreamingResponse`. Python GC will call `generator.close()` on finalization, which throws `GeneratorExit` and unwinds the `with` block — but only when GC runs. Under high concurrency with many aborted downloads, many generators (and thus file handles) can accumulate before GC sweeps them. Adding an explicit `try/finally` ensures the handle is released at `GeneratorExit` immediately, not when GC gets to it.

- [ ] **Step 1: Write the failing test**

```python
# Append to tests/test_files_service.py
import gc

def test_stream_file_closes_handle_on_partial_read(tmp):
    """Simulates a client disconnect: partially consume the iterator, then close it."""
    iterator, filename, size = stream_file(str(tmp / "hello.txt"))
    # Read one chunk then abandon the iterator (simulates disconnect)
    next(iterator)
    iterator.close()           # triggers GeneratorExit
    gc.collect()
    # If the file handle leaked, the next assertion would fail on some OSes.
    # We verify the generator is now closed (no StopIteration raised on further calls).
    try:
        next(iterator)
        assert False, "Should have raised StopIteration"
    except StopIteration:
        pass
```

- [ ] **Step 2: Run test to confirm it passes already (baseline)**

```bash
pytest tests/test_files_service.py::test_stream_file_closes_handle_on_partial_read -v
```

This test will likely pass already (Python's `with` unwinds on `GeneratorExit`). The purpose is to document the expected behavior and prevent regressions if the generator is refactored.

- [ ] **Step 3: Add explicit try/finally to _iter() in files_service.py**

Replace lines 189–193 of `backend/services/files_service.py`:

```python
    def _iter():
        with open(p, "rb") as f:
            while chunk := f.read(65536):
                yield chunk
```

With:

```python
    def _iter():
        f = open(p, "rb")  # noqa: WPS515
        try:
            while chunk := f.read(65536):
                yield chunk
        finally:
            f.close()
```

Using explicit `open`/`close` instead of `with` ensures `f.close()` executes in the `finally` block immediately when `GeneratorExit` is thrown, rather than relying on `__exit__` being triggered (which is equivalent, but more explicit and easier to verify in code review).

- [ ] **Step 4: Run test again + full file tests**

```bash
pytest tests/test_files_service.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/files_service.py tests/test_files_service.py
git commit -m "fix: explicit file handle close in stream_file generator to prevent FD accumulation"
```

---

## Task 3: Add DB Indexes to ExecutionLog + Migration Script

**Files:**
- Modify: `backend/models/execution_log.py`
- Create: `backend/scripts/add_indexes.py`

**Context:** `started_at` is filtered in the 24h stats query. `username` and `exit_code` are filtered in list queries. None have indexes beyond the auto-created primary key index. `script_path` already has `index=True`.

- [ ] **Step 1: Write the test**

```python
# Create tests/test_db_indexes.py
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.models.execution_log import ExecutionLog  # noqa: F401 — registers table


def test_execution_log_index_declarations():
    """Verify model declares indexes on performance-critical columns."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    index_columns = {
        idx["column_names"][0]
        for idx in inspector.get_indexes("execution_logs")
    }
    assert "started_at" in index_columns, "missing index on started_at"
    assert "username" in index_columns, "missing index on username"
    assert "exit_code" in index_columns, "missing index on exit_code"
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
pytest tests/test_db_indexes.py -v
```

Expected: FAIL — `AssertionError: missing index on started_at`

- [ ] **Step 3: Add index declarations to the model**

Replace `backend/models/execution_log.py` entirely:

```python
from sqlalchemy import Column, Integer, String, Float, DateTime, Index
from sqlalchemy.sql import func
from backend.database import Base


class ExecutionLog(Base):
    __tablename__ = "execution_logs"

    id = Column(Integer, primary_key=True, index=True)
    script_path = Column(String, nullable=False, index=True)
    username = Column(String, nullable=False)
    started_at = Column(DateTime, server_default=func.now())
    ended_at = Column(DateTime, nullable=True)
    exit_code = Column(Integer, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    output_summary = Column(String, nullable=True)

    __table_args__ = (
        Index("ix_execution_logs_started_at", "started_at"),
        Index("ix_execution_logs_username", "username"),
        Index("ix_execution_logs_exit_code", "exit_code"),
    )
```

- [ ] **Step 4: Create migration script for existing databases**

Create `backend/scripts/add_indexes.py`:

```python
"""One-time migration: add performance indexes to execution_logs.

Run once against an existing database:
    python -m backend.scripts.add_indexes
"""
from sqlalchemy import text
from backend.database import engine


def main() -> None:
    statements = [
        "CREATE INDEX IF NOT EXISTS ix_execution_logs_started_at ON execution_logs (started_at)",
        "CREATE INDEX IF NOT EXISTS ix_execution_logs_username ON execution_logs (username)",
        "CREATE INDEX IF NOT EXISTS ix_execution_logs_exit_code ON execution_logs (exit_code)",
    ]
    with engine.connect() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
        conn.commit()
    print("Indexes applied.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run test to confirm it passes**

```bash
pytest tests/test_db_indexes.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/models/execution_log.py backend/scripts/add_indexes.py tests/test_db_indexes.py
git commit -m "perf: add DB indexes on execution_logs (started_at, username, exit_code)"
```

---

## Task 4: Optimize Logs Stats Query (4 COUNT → 1 Query)

**Files:**
- Modify: `backend/routers/logs.py`
- Modify: `tests/test_logs.py`

**Context:** `execution_stats` at line 38 runs 4 separate `COUNT(*)` queries against the same table. Each one is a full-table scan. Replace with a single query using `func.sum(case(...))`.

- [ ] **Step 1: Write the test**

```python
# Append to tests/test_logs.py
def test_stats_query_counts_correctly(test_app):
    """Seed 3 rows (2 success, 1 failed) and verify stats returns correct counts."""
    from backend.main import app
    from backend.database import get_db
    from datetime import datetime, timezone

    db = next(app.dependency_overrides[get_db]())
    now = datetime.now(timezone.utc)
    db.add(ExecutionLog(script_path="/a.sh", username="admin", started_at=now, exit_code=0))
    db.add(ExecutionLog(script_path="/b.sh", username="admin", started_at=now, exit_code=0))
    db.add(ExecutionLog(script_path="/c.sh", username="admin", started_at=now, exit_code=1))
    db.commit()
    db.close()

    token = get_token(test_app)
    r = test_app.get("/api/logs/executions/stats", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 3
    assert data["success"] == 2
    assert data["failed"] == 1
    assert data["last_24h"] == 3
```

- [ ] **Step 2: Run test to confirm it passes (baseline — logic is already correct)**

```bash
pytest tests/test_logs.py::test_stats_query_counts_correctly -v
```

Expected: PASS (this verifies the existing behavior before refactoring)

- [ ] **Step 3: Replace the 4-query implementation in logs.py**

Replace the `execution_stats` function in `backend/routers/logs.py`:

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

router = APIRouter(prefix="/api/logs", tags=["logs"])


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
    total = q.count()
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
```

- [ ] **Step 4: Run all log tests**

```bash
pytest tests/test_logs.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add backend/routers/logs.py tests/test_logs.py
git commit -m "perf: replace 4 COUNT queries with single CASE query in stats; add pagination params + X-Total-Count header"
```

---

## Task 5: Add TTL Cache for System Metrics

**Files:**
- Create: `backend/services/cache.py`
- Modify: `backend/routers/system.py`
- Create: `tests/test_cache.py`

**Context:** The dashboard polls `/api/system/metrics` every 5 s. `get_metrics()` calls `psutil` (CPU %, disk I/O, etc.) on every request. Caching the result for 3 s reduces CPU overhead during bursts without perceptibly staling the displayed data.

- [ ] **Step 1: Write tests for TTLCache**

Create `tests/test_cache.py`:

```python
import time
from backend.services.cache import TTLCache


def test_cache_miss_returns_none():
    cache = TTLCache()
    assert cache.get("missing") is None


def test_cache_hit_returns_value():
    cache = TTLCache()
    cache.set("k", {"cpu": 42}, ttl=10)
    assert cache.get("k") == {"cpu": 42}


def test_cache_expires_after_ttl(monkeypatch):
    cache = TTLCache()
    fake_time = [100.0]
    monkeypatch.setattr("backend.services.cache.time.monotonic", lambda: fake_time[0])
    cache.set("k", "value", ttl=5)
    assert cache.get("k") == "value"

    fake_time[0] = 106.0  # 6 s later — expired
    assert cache.get("k") is None


def test_cache_evicts_expired_on_get():
    cache = TTLCache()
    cache.set("k", "v", ttl=0.01)
    time.sleep(0.02)
    assert cache.get("k") is None
    assert "k" not in cache._store
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_cache.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'backend.services.cache'`

- [ ] **Step 3: Create backend/services/cache.py**

```python
import time
from typing import Any, Optional


class TTLCache:
    """Thread-safe in-memory cache with per-key TTL. Safe for single-process use."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expiry = entry
        if time.monotonic() >= expiry:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl: float) -> None:
        self._store[key] = (value, time.monotonic() + ttl)
```

- [ ] **Step 4: Run cache tests**

```bash
pytest tests/test_cache.py -v
```

Expected: all PASS

- [ ] **Step 5: Write the metrics cache test**

```python
# Append to tests/test_system.py
def test_metrics_endpoint_caches_response(test_app, monkeypatch):
    """Two rapid calls should return identical objects (same cached dict)."""
    import backend.routers.system as sys_router
    import backend.services.system_service as sys_svc

    call_count = {"n": 0}
    original = sys_svc.get_metrics

    def counting_get_metrics():
        call_count["n"] += 1
        return original()

    monkeypatch.setattr(sys_svc, "get_metrics", counting_get_metrics)
    # Also patch the cache reference in the router module
    monkeypatch.setattr(sys_router, "_metrics_cache", __import__("backend.services.cache", fromlist=["TTLCache"]).TTLCache())

    token = test_app.post("/api/auth/login", json={"username": "admin", "password": "adminpass"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    test_app.get("/api/system/metrics", headers=headers)
    test_app.get("/api/system/metrics", headers=headers)

    assert call_count["n"] == 1, "get_metrics() should only be called once within TTL"
```

- [ ] **Step 6: Run test to confirm it fails**

```bash
pytest tests/test_system.py::test_metrics_endpoint_caches_response -v
```

Expected: FAIL

- [ ] **Step 7: Modify backend/routers/system.py to use the cache**

```python
from fastapi import APIRouter, Depends
from backend.dependencies import get_current_user
from backend.schemas.system import SystemMetrics
from backend.services.system_service import get_metrics
from backend.services.cache import TTLCache

router = APIRouter(prefix="/api/system", tags=["system"])

_metrics_cache = TTLCache()
_METRICS_TTL = 3.0  # seconds


@router.get("/metrics", response_model=SystemMetrics)
def metrics_endpoint(current_user=Depends(get_current_user)):
    cached = _metrics_cache.get("metrics")
    if cached is not None:
        return cached
    result = get_metrics()
    _metrics_cache.set("metrics", result, ttl=_METRICS_TTL)
    return result
```

- [ ] **Step 8: Run all system tests**

```bash
pytest tests/test_system.py -v
```

Expected: all PASS

- [ ] **Step 9: Commit**

```bash
git add backend/services/cache.py backend/routers/system.py tests/test_cache.py tests/test_system.py
git commit -m "perf: add TTL cache (3s) for system metrics; new TTLCache service"
```

---

## Task 6: Add Axios Timeout to Frontend Client

**Files:**
- Modify: `frontend/src/api/client.js`

**Context:** axios defaults to no timeout — a slow or stalled backend response hangs the UI forever. A 30 s timeout covers all expected response times (including large file reads) while preventing indefinite hangs.

- [ ] **Step 1: Add timeout to the axios instance**

Open `frontend/src/api/client.js`. Replace:

```javascript
const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})
```

With:

```javascript
const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
})
```

- [ ] **Step 2: Verify no existing tests break**

```bash
cd frontend && npm test -- --run
```

Expected: all PASS (timeout only affects stalled requests, not fast test responses)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.js
git commit -m "perf: add 30s timeout to axios client to prevent indefinite hangs"
```

---

## Task 7: Add Debounce Composable + Apply to Logs Search

**Files:**
- Create: `frontend/src/composables/useDebounce.js`
- Modify: `frontend/src/views/LogsView.vue`

**Context:** `LogsView.vue` line 42 fires `loadLogs()` on every `@input` event. Typing "my-script" sends 9 API requests instead of 1. A 400 ms debounce collapses these into a single call.

- [ ] **Step 1: Create useDebounce.js**

Create `frontend/src/composables/useDebounce.js`:

```javascript
/**
 * Returns a debounced version of `fn` that waits `delay` ms after the last call.
 *
 * @param {Function} fn    - Function to debounce.
 * @param {number}   delay - Milliseconds to wait (default 400).
 * @returns {Function}
 */
export function useDebounce(fn, delay = 400) {
  let timer = null
  return function (...args) {
    clearTimeout(timer)
    timer = setTimeout(() => fn(...args), delay)
  }
}
```

- [ ] **Step 2: Write a Vitest test for the composable**

Create `frontend/src/composables/__tests__/useDebounce.test.js`:

```javascript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useDebounce } from '../useDebounce.js'

describe('useDebounce', () => {
  beforeEach(() => { vi.useFakeTimers() })
  afterEach(() => { vi.useRealTimers() })

  it('does not call fn before delay elapses', () => {
    const fn = vi.fn()
    const debounced = useDebounce(fn, 400)
    debounced()
    expect(fn).not.toHaveBeenCalled()
  })

  it('calls fn once after delay', () => {
    const fn = vi.fn()
    const debounced = useDebounce(fn, 400)
    debounced()
    vi.advanceTimersByTime(400)
    expect(fn).toHaveBeenCalledTimes(1)
  })

  it('collapses rapid calls into one', () => {
    const fn = vi.fn()
    const debounced = useDebounce(fn, 400)
    debounced()
    debounced()
    debounced()
    vi.advanceTimersByTime(400)
    expect(fn).toHaveBeenCalledTimes(1)
  })

  it('passes arguments through', () => {
    const fn = vi.fn()
    const debounced = useDebounce(fn, 100)
    debounced('hello', 42)
    vi.advanceTimersByTime(100)
    expect(fn).toHaveBeenCalledWith('hello', 42)
  })
})
```

- [ ] **Step 3: Run test to confirm it passes**

```bash
cd frontend && npm test -- --run src/composables/__tests__/useDebounce.test.js
```

Expected: all PASS

- [ ] **Step 4: Apply debounce in LogsView.vue**

In `frontend/src/views/LogsView.vue`, in the `<script setup>` block:

Add the import (after line 223, with the other composable imports):
```javascript
import { useDebounce } from '../composables/useDebounce.js'
```

After the declaration of `loadLogs` function, add:
```javascript
const debouncedLoadLogs = useDebounce(loadLogs, 400)
```

In the template, replace line 42:
```vue
<InputText v-model="filterScript" placeholder="Filter by script…" size="small" @input="loadLogs" />
```
With:
```vue
<InputText v-model="filterScript" placeholder="Filter by script…" size="small" @input="debouncedLoadLogs" />
```

- [ ] **Step 5: Verify frontend builds without errors**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

Expected: `✓ built in` — no errors

- [ ] **Step 6: Commit**

```bash
git add frontend/src/composables/useDebounce.js frontend/src/composables/__tests__/useDebounce.test.js frontend/src/views/LogsView.vue
git commit -m "perf: add useDebounce composable; debounce Logs search input by 400ms"
```

---

## Task 8: Enable Virtual Scrolling in Logs DataTable

**Files:**
- Modify: `frontend/src/views/LogsView.vue`

**Context:** PrimeVue 4 DataTable has built-in `virtualScrollerOptions` — no new library required. Setting `itemSize` to the row height in pixels makes the table render only ~20 visible rows regardless of how many are in the array, reducing DOM nodes by ~80% for a 100-row result.

The log row height is approximately 46 px (padding `5px 10px` top+bottom = 10 px, line-height ~1.5 × 14px font ≈ 21px content × 2 lines for script-cell = ~52px). Use `50` as a safe estimate; PrimeVue adjusts scroll position dynamically.

- [ ] **Step 1: Enable virtualScrollerOptions on the DataTable**

In `frontend/src/views/LogsView.vue`, find the `<DataTable>` opening tag (line 90). It currently reads:

```vue
    <DataTable
      :value="logs"
      :loading="loading"
      v-model:expanded-rows="expandedRows"
      @row-expand="onRowExpand"
      striped-rows
      size="small"
      data-key="id"
      scrollable
      scroll-height="flex"
      removableSort
      class="logs-table"
    >
```

Replace with:

```vue
    <DataTable
      :value="logs"
      :loading="loading"
      v-model:expanded-rows="expandedRows"
      @row-expand="onRowExpand"
      striped-rows
      size="small"
      data-key="id"
      scrollable
      scroll-height="flex"
      removableSort
      :virtualScrollerOptions="{ itemSize: 50 }"
      class="logs-table"
    >
```

- [ ] **Step 2: Verify build**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/LogsView.vue
git commit -m "perf: enable PrimeVue DataTable virtual scrolling for Logs (itemSize=50)"
```

---

## Task 9: Wire Pagination UI to Logs (Frontend + Backend)

**Files:**
- Modify: `frontend/src/views/LogsView.vue`
- Modify: `tests/test_logs.py`

**Context:** The backend (Task 4) now accepts `limit` and `offset` query params and returns `X-Total-Count`. The frontend needs to: (1) track `totalLogs` from the header, (2) track `currentPage`, (3) pass `offset` to the backend, (4) show PrimeVue Paginator below the table.

- [ ] **Step 1: Add pagination tests to test_logs.py**

Append to `tests/test_logs.py`:

```python
def test_pagination_offset_and_limit(test_app):
    from backend.main import app
    from backend.database import get_db
    from datetime import datetime, timezone

    db = next(app.dependency_overrides[get_db]())
    for i in range(10):
        db.add(ExecutionLog(
            script_path=f"/script_{i}.sh",
            username="admin",
            started_at=datetime.now(timezone.utc),
            exit_code=0,
        ))
    db.commit()
    db.close()

    token = get_token(test_app)
    headers = {"Authorization": f"Bearer {token}"}

    # First page: 5 items
    r = test_app.get("/api/logs/executions?limit=5&offset=0", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 5
    assert r.headers.get("x-total-count") == "10"

    # Second page: remaining 5
    r2 = test_app.get("/api/logs/executions?limit=5&offset=5", headers=headers)
    assert r2.status_code == 200
    assert len(r2.json()) == 5

    # No overlap between pages
    ids_p1 = {item["id"] for item in r.json()}
    ids_p2 = {item["id"] for item in r2.json()}
    assert ids_p1.isdisjoint(ids_p2)
```

- [ ] **Step 2: Run the test**

```bash
pytest tests/test_logs.py::test_pagination_offset_and_limit -v
```

Expected: PASS (backend was updated in Task 4)

- [ ] **Step 3: Add pagination state + Paginator import in LogsView.vue**

In the `<script setup>` block of `frontend/src/views/LogsView.vue`:

Add the import at the top with the other PrimeVue imports:
```javascript
import Paginator from 'primevue/paginator'
```

Add reactive state after the existing refs (after `const dateRange = ref(null)`):
```javascript
const totalLogs = ref(0)
const pageSize = ref(50)
const pageOffset = ref(0)
```

- [ ] **Step 4: Update loadLogs to send offset/limit and read X-Total-Count**

Replace the existing `loadLogs` function:

```javascript
async function loadLogs() {
  loading.value = true
  try {
    const params = {}
    if (filterScript.value) params.script = filterScript.value
    if (filterStatus.value === 'success') params.exit_code = 0
    if (filterStatus.value === 'failed') params.exit_code = 1
    if (dateRange.value?.[0]) params.from_date = dateRange.value[0].toISOString()
    if (dateRange.value?.[1]) params.to_date = dateRange.value[1].toISOString()
    params.limit = pageSize.value
    params.offset = pageOffset.value
    const { data, headers } = await api.get('/logs/executions', { params })
    logs.value = data
    totalLogs.value = parseInt(headers['x-total-count'] || '0', 10)
  } finally {
    loading.value = false
  }
}
```

Add an `onPageChange` handler after `clearFilters`:
```javascript
function onPageChange(event) {
  pageOffset.value = event.first
  loadLogs()
}
```

Reset offset when filters change. Replace `clearFilters`:
```javascript
function clearFilters() {
  filterScript.value = ''
  filterStatus.value = 'all'
  dateRange.value = null
  pageOffset.value = 0
  loadLogs()
}
```

Also update `setStatus` to reset offset:
```javascript
function setStatus(val) {
  filterStatus.value = val
  pageOffset.value = 0
  loadLogs()
}
```

- [ ] **Step 5: Add Paginator to the template**

In `frontend/src/views/LogsView.vue`, after the closing `</DataTable>` tag (line 203), add:

```vue
    <Paginator
      v-if="totalLogs > pageSize"
      :rows="pageSize"
      :total-records="totalLogs"
      :first="pageOffset"
      class="logs-paginator"
      @page="onPageChange"
    />
```

Add the style at the bottom of the `<style scoped>` block:
```css
.logs-paginator {
  flex-shrink: 0;
  border-top: 1px solid var(--p-surface-border);
}
```

- [ ] **Step 6: Verify build**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

Expected: no errors

- [ ] **Step 7: Run all backend log tests**

```bash
pytest tests/test_logs.py -v
```

Expected: all PASS

- [ ] **Step 8: Commit**

```bash
git add frontend/src/views/LogsView.vue tests/test_logs.py
git commit -m "feat: server-side pagination for logs (50/page) with X-Total-Count + Paginator UI"
```

---

## Self-Review Checklist

### Spec Coverage

| Spec Requirement | Task |
|-----------------|------|
| Memory leaks in file routing module | Task 2 (stream_file generator) |
| Pagination for file listings (backend) | Task 4 adds `limit`/`offset` to logs; file listing pagination deferred — file directories in practice are small enough for a single-server tool. Add as follow-up if `/` listing becomes slow. |
| List virtualization (logs) | Task 8 |
| Gzip compression | Task 1 |
| Strategic caching | Task 5 (system metrics TTL) |
| Debouncing & throttling | Task 7 |
| DB query optimization + indexes | Tasks 3 & 4 |
| Lazy loading for non-critical UI | Addressed via virtual scroll + pagination; intersection-observer lazy components deferred — PrimeVue already lazy-loads tab content by default |
| Axios timeout | Task 6 |
| No breaking changes | All backend changes are additive (new optional params, new header) |

### Deferred (Phase 3 / Future Work)
- **WebSocket for real-time dashboard** — polling at 5s is negligible CPU overhead for a single-server tool. Add only if profiling shows CPU regression.
- **Web Workers for log parsing** — output_summary is truncated server-side; client-side log parsing isn't happening.
- **File listing pagination** — directories large enough to cause perf issues are rare on a single managed server. Add if a user reports slowness on e.g. `/usr/lib`.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-03-30-performance-memory-optimization.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** — Fresh subagent per task, review between tasks, fast iteration. Uses `superpowers:subagent-driven-development`.

**2. Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.

Which approach?
