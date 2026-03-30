---
name: serverdash-performance
description: Use when adding features, fixing bugs, or refactoring any part of the ServerDash codebase. Covers mandatory performance and correctness rules for DB queries, caching, background jobs, frontend bundle, and test patterns. Consult BEFORE writing any code.
---

# ServerDash — Performance & Correctness Rules

## Core Principle

Every addition to this codebase must respect the performance contracts established in the hardening sprint. Violating them degrades the app silently — no crash, wrong behaviour at scale.

---

## 1. Database Layer

### Indexes — mandatory for every new model column used in WHERE/ORDER BY

Declare indexes in `__table_args__` inside the model. **Also add** a `CREATE INDEX IF NOT EXISTS` statement to `backend/scripts/add_indexes.py` so existing production databases can be migrated without downtime.

```python
# backend/models/my_model.py
__table_args__ = (
    Index("ix_my_table_column_name", "column_name"),
    Index("ix_my_table_col_a_col_b", "col_a", "col_b"),  # composite: most-selective first
)
```

```python
# backend/scripts/add_indexes.py  ← always add the matching SQL here too
"CREATE INDEX IF NOT EXISTS ix_my_table_column_name ON my_table (column_name)",
```

Run after deploy on existing DB: `python -m backend.scripts.add_indexes`

### Existing indexes on `execution_logs`

| Index | Columns | Purpose |
|---|---|---|
| `ix_execution_logs_started_at` | `started_at` | Date range filters |
| `ix_execution_logs_username` | `username` | User audit filters |
| `ix_execution_logs_exit_code` | `exit_code` | Status filters |
| `ix_execution_logs_username_started_at` | `(username, started_at)` | Composite audit queries |

### COUNT queries — never call `q.count()` on every request

Any paginated endpoint **must** cache its total count. Use the module-level `TTLCache` singleton pattern:

```python
# backend/routers/my_router.py
from backend.services.cache import TTLCache

_count_cache: TTLCache = TTLCache()
_COUNT_TTL = 300  # 5 minutes

def _count_key(filter_a, filter_b) -> str:
    # Normalize datetimes with .isoformat() — never use raw str(datetime)
    return f"{filter_a}|{filter_b}"

@router.get("/items")
def list_items(..., response: Response = None):
    q = build_query(...)
    key = _count_key(filter_a, filter_b)
    total = _count_cache.get(key)
    if total is None:
        total = q.count()
        _count_cache.set(key, total, _COUNT_TTL)
    if response is not None:
        response.headers["X-Total-Count"] = str(total)
    return q.offset(offset).limit(limit).all()
```

**CRITICAL — datetime keys must use `.isoformat()`**, never `str(datetime_obj)`. Raw string representation varies with microseconds and timezone offset format, causing cache misses and potential wrong counts.

### Datetime comparison with SQLite — use naive UTC

SQLite stores datetimes without timezone info (`server_default=func.now()` produces naive UTC strings). When filtering by date, use **`datetime.utcnow()`** not `datetime.now(timezone.utc)`. Mixing aware and naive datetimes causes incorrect comparisons.

```python
# ✅ Correct — matches what SQLite stores
cutoff = datetime.utcnow() - timedelta(days=retention_days)

# ❌ Wrong — aware datetime vs naive stored value
cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
```

Exception: `execution_stats` in `logs.py` uses `datetime.now(timezone.utc)` intentionally for a 24h relative window — that's a known special case, don't change it.

---

## 2. Background Scheduler

All periodic/background work goes through `backend/scheduler.py`. The scheduler starts/stops via the FastAPI `lifespan` in `backend/main.py`.

### Adding a new job

```python
# backend/scheduler.py

def _do_my_work(db: Session, param: int) -> int:
    """Pure function — testable without scheduler. Returns count/result."""
    # ... do work ...
    db.commit()
    return result

def _my_job() -> None:
    """APScheduler job wrapper — gets SessionLocal internally."""
    from backend.database import SessionLocal
    from backend.config import settings
    db = SessionLocal()
    try:
        _do_my_work(db, settings.some_param)
    except Exception:
        logger.exception("My job failed")
    finally:
        db.close()

# Inside init_scheduler():
_scheduler.add_job(_my_job, CronTrigger(hour=4, minute=0), id="my_job")
```

**Pattern rules:**
- Separate the pure logic (`_do_*`) from the job wrapper (`_*_job`). Tests call `_do_*` directly.
- Job wrappers import `SessionLocal` and `settings` lazily inside the function body — avoids circular imports.
- Always wrap job body in `try/except Exception` + `logger.exception` so one failure doesn't kill the scheduler.
- VACUUM requires raw `sqlite3` — SQLAlchemy's `Session` cannot execute VACUUM (transaction conflict). See `_do_vacuum` for the pattern.

### Existing scheduled jobs

| Job ID | Function | Schedule | What it does |
|---|---|---|---|
| `log_cleanup` | `_cleanup_job` | Daily 2 AM | Deletes `execution_logs` older than `LOG_RETENTION_DAYS` |
| `db_vacuum` | `_vacuum_job` | Sunday 3 AM | Runs SQLite VACUUM to reclaim fragmented space |

### Multi-worker warning

`BackgroundScheduler` runs once per process. With `gunicorn -w 4`, jobs run 4× per cycle. For idempotent cleanup jobs this is safe. For non-idempotent jobs, add a DB lock or run with a single worker.

---

## 3. Frontend — Bundle & State

### All route views must be lazy imports

`frontend/src/router/index.js` uses `() => import(...)` for every route. **Never** add a static `import SomeView from '...'` at the top of the router file. Vite code-splits each view into its own chunk; static imports collapse everything into the main bundle.

```javascript
// ✅ Correct
{ path: '/my-route', component: () => import('../views/MyView.vue'), meta: { requiresAuth: true } },

// ❌ Wrong — bundles the view (and all its dependencies) into main chunk
import MyView from '../views/MyView.vue'
{ path: '/my-route', component: MyView },
```

### Bounded collections — always cap unbounded state

Any Vue component that accumulates items in a `ref([])` or `ref({})` based on user interaction **must** have a maximum size and eviction logic. Unbounded DOM growth causes memory leaks.

Pattern (FIFO cap, from `LogsView.vue`):

```javascript
const items = ref({})
const itemOrder = ref([])
const MAX_ITEMS = 5

function onAddItem(event) {
  const id = event.data.id
  itemOrder.value.push(id)
  if (itemOrder.value.length > MAX_ITEMS) {
    const evicted = itemOrder.value.shift()
    delete items.value[evicted]
  }
}

function onRemoveItem(event) {
  itemOrder.value = itemOrder.value.filter(i => i !== event.data.id)
}
```

### Debouncing inputs

Use the existing `useDebounce` composable (`frontend/src/composables/useDebounce.js`) for any input that triggers an API call. Minimum 400ms for search inputs.

```javascript
import { useDebounce } from '../composables/useDebounce.js'
const debouncedSearch = useDebounce(loadData, 400)
```

---

## 4. Test Patterns

### Fixtures (conftest.py)

| Fixture | Use for | Admin credentials |
|---|---|---|
| `db_session` | Unit tests — direct DB access, no HTTP | N/A |
| `test_app` | Integration tests — HTTP via `TestClient` | username: `admin`, password: `adminpass` |

`test_app` creates an in-memory SQLite DB and patches `SessionLocal` globally. If you add a new service that calls `SessionLocal()` directly (like `scripts_service` does), **add it to the patch block** in `conftest.py`:

```python
import backend.services.my_new_service as _my_svc
original_my_svc_session = _my_svc.SessionLocal
_my_svc.SessionLocal = TestingSession
# ... and restore in teardown
_my_svc.SessionLocal = original_my_svc_session
```

### Module-level cache singletons need a conftest reset

Any new module-level `TTLCache` instance will persist across tests (same process, different in-memory DBs). Add an `autouse` fixture to `conftest.py`:

```python
@pytest.fixture(autouse=True)
def reset_my_router_cache():
    from backend.routers.my_router import _count_cache
    _count_cache.clear()
    yield
```

Without this, test A populates the cache with count=3, test B gets a fresh DB but reads the stale 3 — silent wrong results.

### Scheduler job testing

Test the `_do_*` functions directly with `db_session` — never test the job wrappers (`_*_job`) or the scheduler itself:

```python
def test_my_cleanup(db_session):
    from backend.scheduler import _do_my_work
    # seed data
    result = _do_my_work(db_session, param=30)
    assert result == expected
```

Use `datetime.utcnow()` in test fixtures when seeding `started_at` values — must match the naive UTC comparison in `_do_cleanup`.

---

## 5. Dependencies

Current `backend/requirements.txt` — deliberate inclusions:

| Package | Why it's here |
|---|---|
| `apscheduler>=3.10,<4` | Background scheduler (cleanup + VACUUM jobs) |
| `python-crontab==3.2.0` | Used by `crontab_service.py` for crontab management |
| `slowapi` | Rate limiting on `/api/auth/login` |

**Not in requirements (intentionally removed):**
- `websockets` — never used in production code
- `httpx` — never used in production code

Do not re-add these. If you need HTTP client functionality, use `httpx` only after confirming no alternative exists and add it explicitly with a pinned version.

---

## 6. Config Variables

New tunable behaviour goes in `backend/config.py` as a `pydantic-settings` field with a sensible default. Document it in `.env.example`.

```python
# backend/config.py
class Settings(BaseSettings):
    my_new_param: int = 100  # add here with default
```

Current performance-related config:

| Variable | Default | Purpose |
|---|---|---|
| `LOG_RETENTION_DAYS` | `30` | Days before execution logs are auto-deleted |

---

## 7. Checklist Before Merging Any Feature

- [ ] New DB columns that appear in WHERE/ORDER BY have an index in `__table_args__` AND in `add_indexes.py`
- [ ] New paginated endpoints use `TTLCache` for COUNT, not `q.count()` inline
- [ ] Date comparisons against SQLite columns use `datetime.utcnow()` (naive)
- [ ] New background tasks follow the `_do_*` / `_*_job` split and are registered in `init_scheduler()`
- [ ] New Vue route uses `() => import(...)` — no static imports in `router/index.js`
- [ ] New Vue collections that grow from user interaction have a maximum size + eviction
- [ ] New module-level cache singletons have `.clear()` + autouse fixture in `conftest.py`
- [ ] New services that call `SessionLocal()` directly are patched in `test_app` fixture
- [ ] `pytest` passes: `pytest -q` → all green
- [ ] Frontend tests pass: `npm test` (3 pre-existing `LoginView` failures are a known PrimeVue test env issue — not ours)
