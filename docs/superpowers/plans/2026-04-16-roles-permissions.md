# Roles & Permissions System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the existing permission infrastructure end-to-end: update the default permission matrix (4 actions, no admin in table), add admin bypass, expose permission management API, migrate all routers to `require_permission`, and add an admin UI to edit permissions per role.

**Architecture:** The `Permission` table (role, resource, action) is the source of truth. Admin always bypasses the table (hardcoded True in `check_permission`). A 60s TTL cache sits in front of DB queries; it is cleared on every PUT to the permissions API. All backend endpoints use `require_permission(resource, action)`. The frontend's `auth.hasPermission(resource, action)` drives sidebar visibility and button rendering; it already reads from `/auth/me`.

**Tech Stack:** FastAPI, SQLAlchemy (SQLite), Pinia (Vue 3), PrimeVue 4 (Aura theme), pytest.

---

## File Map

### Backend — Modified
- `backend/scripts/init_db.py` — update DEFAULT_PERMISSIONS (4 actions, no admin, add pipelines/users)
- `backend/dependencies.py` — add admin bypass in `check_permission`
- `backend/routers/admin.py` — add GET/PUT `/api/admin/permissions` endpoints
- `backend/routers/system.py` — migrate to `require_permission`
- `backend/routers/logs.py` — migrate to `require_permission`
- `backend/routers/network.py` — migrate to `require_permission`
- `backend/routers/metrics_history.py` — migrate to `require_permission`
- `backend/routers/services.py` — migrate to `require_permission`
- `backend/routers/files.py` — migrate to `require_permission`
- `backend/routers/scripts.py` — migrate to `require_permission` + fix WebSocket check
- `backend/routers/crontab.py` — migrate to `require_permission`
- `backend/routers/pipelines.py` — migrate to `require_permission`

### Backend — Tests Modified
- `tests/test_permissions.py` — update assertions for new matrix (no admin in table)
- `tests/test_admin_router.py` — add tests for new permission endpoints

### Frontend — Modified
- `frontend/src/router/index.js` — fix pipelines resource (`'scripts'` → `'pipelines'`), add `/admin/permissions` route
- `frontend/src/views/CrontabView.vue` — fix `auth.role === 'admin'` → `auth.isAdmin`
- `frontend/src/views/PipelinesView.vue` — fix `auth.role === 'admin'` → `auth.isAdmin`
- `frontend/src/views/ScriptsView.vue` — fix `auth.role === 'admin'` → `auth.isAdmin`
- `frontend/src/components/layout/AppSidebar.vue` — add Permissions link under ADMIN

### Frontend — Created
- `frontend/src/views/AdminPermissionsView.vue` — permission matrix editor

### Documentation — Modified
- `CLAUDE.md` — add permissions rule for new features
- `docs/bitacora.md` — log the change

---

## Task 1: Update DEFAULT_PERMISSIONS and fix test_permissions.py

**Files:**
- Modify: `backend/scripts/init_db.py`
- Modify: `tests/test_permissions.py`

The current matrix has 3 actions, includes admin (who should bypass the table), and is missing `pipelines` and `users` resources. This task fixes all of that.

- [ ] **Step 1: Update `init_db.py`**

Replace the entire top section of `backend/scripts/init_db.py` (lines 1–29):

```python
"""Run once: python -m backend.scripts.init_db"""
from backend.database import engine, Base, SessionLocal
from backend.models.user import User, UserRole
from backend.models.permission import Permission
from backend.services.auth_service import hash_password
from backend.config import settings
import backend.models  # ensure models are registered

# Admin is NOT in this dict — admin always bypasses the Permission table.
DEFAULT_PERMISSIONS = {
    UserRole.operator: [
        ("system",    "read"),
        ("services",  "read"),  ("services",  "write"), ("services",  "execute"),
        ("files",     "read"),  ("files",     "write"),
        ("network",   "read"),
        ("scripts",   "read"),  ("scripts",   "write"), ("scripts",   "execute"),
        ("crontab",   "read"),
        ("logs",      "read"),
        ("pipelines", "read"),  ("pipelines", "execute"),
    ],
    UserRole.readonly: [
        ("system",    "read"),
        ("services",  "read"),
        ("files",     "read"),
        ("network",   "read"),
        ("scripts",   "read"),
        ("crontab",   "read"),
        ("logs",      "read"),
        ("pipelines", "read"),
    ],
}

def seed_permissions(db):
    if db.query(Permission).first() is not None:
        return
    for role, pairs in DEFAULT_PERMISSIONS.items():
        for resource, action in pairs:
            db.add(Permission(role=role, resource=resource, action=action))
    db.commit()

def init():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    existing = db.query(User).filter_by(username=settings.admin_username).first()
    if not existing:
        admin = User(
            username=settings.admin_username,
            hashed_password=hash_password(settings.admin_password),
            role=UserRole.admin,
        )
        db.add(admin)
        db.commit()
        print(f"Admin user '{settings.admin_username}' created.")
    else:
        print(f"Admin user '{settings.admin_username}' already exists.")
    seed_permissions(db)
    db.close()

if __name__ == "__main__":
    init()
```

- [ ] **Step 2: Update `tests/test_permissions.py`**

The test `test_seed_permissions` checks for admin permissions in the table — these no longer exist. Replace the entire file:

```python
import pytest
from backend.models.permission import Permission
from backend.models.user import User, UserRole


def test_seed_permissions_populates_operator_and_readonly(db_session):
    from backend.scripts.init_db import seed_permissions
    seed_permissions(db_session)
    perms = db_session.query(Permission).all()
    assert len(perms) > 0

    roles = {p.role for p in perms}
    # Admin is NOT seeded — admin bypasses the table
    assert UserRole.admin not in roles
    assert UserRole.operator in roles
    assert UserRole.readonly in roles


def test_seed_permissions_is_idempotent(db_session):
    from backend.scripts.init_db import seed_permissions
    seed_permissions(db_session)
    count_first = db_session.query(Permission).count()
    seed_permissions(db_session)  # second call — must be a no-op
    count_second = db_session.query(Permission).count()
    assert count_first == count_second


def test_readonly_only_has_read_actions(db_session):
    from backend.scripts.init_db import seed_permissions
    seed_permissions(db_session)
    ro_perms = db_session.query(Permission).filter(Permission.role == UserRole.readonly).all()
    assert len(ro_perms) > 0
    for p in ro_perms:
        assert p.action == "read", f"readonly had unexpected action: {p.action} on {p.resource}"


def test_operator_has_write_on_services(db_session):
    from backend.scripts.init_db import seed_permissions
    seed_permissions(db_session)
    perm = db_session.query(Permission).filter(
        Permission.role == UserRole.operator,
        Permission.resource == "services",
        Permission.action == "write",
    ).first()
    assert perm is not None


def test_operator_cannot_delete_files(db_session):
    from backend.scripts.init_db import seed_permissions
    seed_permissions(db_session)
    perm = db_session.query(Permission).filter(
        Permission.role == UserRole.operator,
        Permission.resource == "files",
        Permission.action == "delete",
    ).first()
    assert perm is None


def test_pipelines_execute_seeded_for_operator(db_session):
    from backend.scripts.init_db import seed_permissions
    seed_permissions(db_session)
    perm = db_session.query(Permission).filter(
        Permission.role == UserRole.operator,
        Permission.resource == "pipelines",
        Permission.action == "execute",
    ).first()
    assert perm is not None


def test_check_permission_admin_always_true(db_session):
    """Admin bypasses the table — must return True even with no permissions seeded."""
    from backend.dependencies import check_permission
    user = User(username="testadmin", hashed_password="x", role=UserRole.admin)
    db_session.add(user)
    db_session.commit()
    # No seed_permissions call — table is empty
    assert check_permission(db_session, user, "scripts", "execute") is True
    assert check_permission(db_session, user, "users", "delete") is True


def test_check_permission_readonly_cannot_execute(db_session):
    from backend.dependencies import check_permission
    from backend.scripts.init_db import seed_permissions
    seed_permissions(db_session)
    user = User(username="viewer", hashed_password="x", role=UserRole.readonly)
    db_session.add(user)
    db_session.commit()
    assert check_permission(db_session, user, "scripts", "execute") is False


def test_check_permission_readonly_can_read(db_session):
    from backend.dependencies import check_permission
    from backend.scripts.init_db import seed_permissions
    seed_permissions(db_session)
    user = User(username="viewer", hashed_password="x", role=UserRole.readonly)
    db_session.add(user)
    db_session.commit()
    assert check_permission(db_session, user, "scripts", "read") is True
```

- [ ] **Step 3: Run tests to see current failures**

```bash
cd /home/crt/server_dashboard && pytest tests/test_permissions.py -v
```

Expected: several failures (admin bypass not yet in code, old test structure).

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/init_db.py tests/test_permissions.py
git commit -m "feat(permissions): update DEFAULT_PERMISSIONS matrix — 4 actions, no admin in table, add pipelines"
```

---

## Task 2: Add admin bypass in `check_permission`

**Files:**
- Modify: `backend/dependencies.py`

- [ ] **Step 1: Run the two admin tests to confirm they fail**

```bash
cd /home/crt/server_dashboard && pytest tests/test_permissions.py::test_check_permission_admin_always_true -v
```

Expected: FAIL — `check_permission` currently queries the DB and returns False for admin (no rows seeded for admin).

- [ ] **Step 2: Update `check_permission` in `backend/dependencies.py`**

Replace lines 46–54:

```python
def check_permission(db: Session, user: User, resource: str, action: str) -> bool:
    if user.role == UserRole.admin:
        return True
    cache_key = f"{user.role.value}|{resource}|{action}"
    cached = _perm_cache.get(cache_key)
    if cached is not None:
        return cached
    perm = db.query(Permission).filter(
        Permission.role == user.role,
        Permission.resource == resource,
        Permission.action == action,
    ).first()
    result = perm is not None
    _perm_cache.set(cache_key, result, _PERM_TTL)
    return result
```

- [ ] **Step 3: Run all permission tests**

```bash
cd /home/crt/server_dashboard && pytest tests/test_permissions.py -v
```

Expected: all PASS.

- [ ] **Step 4: Run full test suite to check for regressions**

```bash
cd /home/crt/server_dashboard && pytest -x -q
```

Expected: all pass (or only pre-existing failures).

- [ ] **Step 5: Commit**

```bash
git add backend/dependencies.py
git commit -m "feat(permissions): admin always bypasses permission table in check_permission"
```

---

## Task 3: Permission management API endpoints

**Files:**
- Modify: `backend/routers/admin.py`
- Modify: `tests/test_admin_router.py`

These endpoints let the admin view and replace the permission list for `operator` and `readonly` roles. They also clear the permission TTL cache on write.

- [ ] **Step 1: Write tests first (append to `tests/test_admin_router.py`)**

```python
def test_list_permissions(test_app):
    token = get_token(test_app)
    r = test_app.get("/api/admin/permissions", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert "operator" in data
    assert "readonly" in data
    # readonly only reads
    ro = data["readonly"]
    assert all(p["action"] == "read" for p in ro)
    # operator can execute scripts
    op = data["operator"]
    assert any(p["resource"] == "scripts" and p["action"] == "execute" for p in op)


def test_update_permissions_operator(test_app):
    token = get_token(test_app)
    new_perms = [
        {"resource": "system", "action": "read"},
        {"resource": "logs",   "action": "read"},
    ]
    r = test_app.put(
        "/api/admin/permissions/operator",
        json=new_perms,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    # Verify the change persisted
    r2 = test_app.get("/api/admin/permissions", headers={"Authorization": f"Bearer {token}"})
    op = r2.json()["operator"]
    assert len(op) == 2
    assert any(p["resource"] == "system" and p["action"] == "read" for p in op)


def test_update_permissions_admin_forbidden(test_app):
    """Admin permissions cannot be edited via the API."""
    token = get_token(test_app)
    r = test_app.put(
        "/api/admin/permissions/admin",
        json=[{"resource": "system", "action": "read"}],
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400


def test_update_permissions_invalid_role(test_app):
    token = get_token(test_app)
    r = test_app.put(
        "/api/admin/permissions/superuser",
        json=[{"resource": "system", "action": "read"}],
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400


def test_non_admin_cannot_list_permissions(test_app):
    admin_token = get_token(test_app)
    test_app.post("/api/admin/users", json={"username": "op1", "password": "pass", "role": "operator"},
                  headers={"Authorization": f"Bearer {admin_token}"})
    op_token = get_token(test_app, "op1", "pass")
    r = test_app.get("/api/admin/permissions", headers={"Authorization": f"Bearer {op_token}"})
    assert r.status_code == 403
```

- [ ] **Step 2: Run new tests to confirm they fail**

```bash
cd /home/crt/server_dashboard && pytest tests/test_admin_router.py::test_list_permissions tests/test_admin_router.py::test_update_permissions_operator -v
```

Expected: FAIL — 404 (endpoints don't exist yet).

- [ ] **Step 3: Implement endpoints in `backend/routers/admin.py`**

Replace the full file:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.dependencies import require_role, _perm_cache
from backend.models.user import User, UserRole
from backend.models.permission import Permission
from backend.schemas.users import UserOut, UserCreate, UserUpdate, PermissionOut
from backend.services.auth_service import hash_password

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── Users ─────────────────────────────────────────────────────────────────────

@router.get("/users", response_model=List[UserOut])
def list_users(db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    return db.query(User).order_by(User.id).all()


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    existing = db.query(User).filter(User.username == body.username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")
    try:
        role = UserRole(body.role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {body.role}")
    new_user = User(username=body.username, hashed_password=hash_password(body.password), role=role)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, db: Session = Depends(get_db), current_user=Depends(require_role("admin"))):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if body.role is not None:
        try:
            target.role = UserRole(body.role)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid role: {body.role}")
    if body.is_active is not None:
        target.is_active = body.is_active
    if body.password is not None:
        target.hashed_password = hash_password(body.password)
    db.commit()
    db.refresh(target)
    return target


@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), current_user=Depends(require_role("admin"))):
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(target)
    db.commit()
    return {"ok": True}


# ── Permissions ───────────────────────────────────────────────────────────────

@router.get("/permissions", response_model=Dict[str, List[PermissionOut]])
def list_permissions(db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    result: Dict[str, List[PermissionOut]] = {}
    for role in [UserRole.operator, UserRole.readonly]:
        perms = db.query(Permission).filter(Permission.role == role).all()
        result[role.value] = [PermissionOut(resource=p.resource, action=p.action) for p in perms]
    return result


@router.put("/permissions/{role}")
def update_permissions(
    role: str,
    body: List[PermissionOut],
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    try:
        target_role = UserRole(role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {role}")
    if target_role == UserRole.admin:
        raise HTTPException(status_code=400, detail="Cannot edit admin permissions")
    db.query(Permission).filter(Permission.role == target_role).delete()
    for p in body:
        db.add(Permission(role=target_role, resource=p.resource, action=p.action))
    db.commit()
    _perm_cache.clear()
    return {"ok": True}
```

- [ ] **Step 4: Run all admin router tests**

```bash
cd /home/crt/server_dashboard && pytest tests/test_admin_router.py -v
```

Expected: all PASS.

- [ ] **Step 5: Run full suite**

```bash
cd /home/crt/server_dashboard && pytest -x -q
```

- [ ] **Step 6: Commit**

```bash
git add backend/routers/admin.py tests/test_admin_router.py
git commit -m "feat(permissions): add GET/PUT /api/admin/permissions endpoints with cache invalidation"
```

---

## Task 4: Migrate read-only routers (system, logs, network, metrics_history)

**Files:**
- Modify: `backend/routers/system.py`
- Modify: `backend/routers/logs.py`
- Modify: `backend/routers/network.py`
- Modify: `backend/routers/metrics_history.py`

All endpoints in these routers are reads except `POST /logs/maintenance/cleanup` (which stays `require_role("admin")` — no read/write concept maps to log deletion).

- [ ] **Step 1: Update `backend/routers/system.py`**

```python
from fastapi import APIRouter, Depends
from backend.dependencies import require_permission
from backend.schemas.system import SystemMetrics
from backend.services.system_service import get_metrics
from backend.services.cache import TTLCache

router = APIRouter(prefix="/api/system", tags=["system"])

_metrics_cache = TTLCache()
_METRICS_TTL = 3.0


@router.get("/metrics", response_model=SystemMetrics)
def metrics_endpoint(current_user=Depends(require_permission("system", "read"))):
    cached = _metrics_cache.get("metrics")
    if cached is not None:
        return cached
    result = get_metrics()
    _metrics_cache.set("metrics", result, ttl=_METRICS_TTL)
    return result
```

- [ ] **Step 2: Update `backend/routers/metrics_history.py`**

```python
from fastapi import APIRouter, Depends, Query
from typing import List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import require_permission
from backend.models.metrics_snapshot import MetricsSnapshot
from backend.schemas.metrics_history import MetricsSnapshotOut

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/history", response_model=List[MetricsSnapshotOut])
def metrics_history(
    hours: int = Query(24, ge=1, le=720),
    db: Session = Depends(get_db),
    user=Depends(require_permission("system", "read")),
):
    """Get metrics history for the last N hours. Downsamples to 1440 points max."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    q = db.query(MetricsSnapshot).filter(
        MetricsSnapshot.timestamp >= cutoff
    ).order_by(MetricsSnapshot.timestamp.asc())

    max_points = 1440
    rows = q.all()

    if len(rows) > max_points:
        step = (len(rows) + max_points - 1) // max_points
        rows = rows[::step]

    return rows
```

- [ ] **Step 3: Update `backend/routers/logs.py`**

Replace `get_current_user` with `require_permission` on read endpoints; keep `require_role("admin")` on cleanup:

```python
from fastapi import APIRouter, Depends, Query, Response
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from backend.database import get_db
from backend.dependencies import require_permission, require_role
from backend.models.execution_log import ExecutionLog
from backend.schemas.logs import ExecutionLogOut, ExecutionStatsOut
from backend.services.cache import TTLCache

router = APIRouter(prefix="/api/logs", tags=["logs"])

_count_cache: TTLCache = TTLCache()
_COUNT_TTL = 300


def _count_key(script, username, exit_code, from_date, to_date) -> str:
    fd = from_date.isoformat() if from_date else None
    td = to_date.isoformat() if to_date else None
    return f"{script}|{username}|{exit_code}|{fd}|{td}"


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
    user=Depends(require_permission("logs", "read")),
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
    user=Depends(require_permission("logs", "read")),
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
    user=Depends(require_role("admin")),
):
    """Manually trigger log retention cleanup. Admin only — destructive operation."""
    from backend.scheduler import _do_cleanup
    from backend.config import settings
    deleted = _do_cleanup(db, settings.log_retention_days)
    return {"deleted": deleted, "retention_days": settings.log_retention_days}
```

- [ ] **Step 4: Update `backend/routers/network.py`**

Replace every `Depends(get_current_user)` with `Depends(require_permission("network", "read"))` and remove the `get_current_user` import:

```python
from fastapi import APIRouter, Depends, Query
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database import get_db
from backend.dependencies import require_permission
from backend.models.network_snapshot import NetworkSnapshot
from backend.schemas.network import InterfaceInfo, ConnectionInfo, ConnectionSummary, BandwidthPoint
from backend.services.network_service import (
    get_interfaces, get_active_connections, get_connection_summary,
    get_arp_devices, get_network_config,
)
from backend.services.cache import TTLCache

router = APIRouter(prefix="/api/network", tags=["network"])

_iface_cache: TTLCache = TTLCache()
_conn_summary_cache: TTLCache = TTLCache()
_IFACE_TTL = 3.0
_SUMMARY_TTL = 5.0


@router.get("/interfaces", response_model=List[InterfaceInfo])
def list_interfaces(user=Depends(require_permission("network", "read"))):
    cached = _iface_cache.get("ifaces")
    if cached is not None:
        return cached
    result = get_interfaces()
    _iface_cache.set("ifaces", result, ttl=_IFACE_TTL)
    return result


@router.get("/connections", response_model=List[ConnectionInfo])
def list_connections(
    status_filter: Optional[str] = Query(None),
    proto_filter: Optional[str] = Query(None),
    user=Depends(require_permission("network", "read")),
):
    conns = get_active_connections()
    if status_filter:
        conns = [c for c in conns if c["status"] == status_filter.upper()]
    if proto_filter:
        conns = [c for c in conns if c["proto"] == proto_filter.upper()]
    return conns


@router.get("/connections/summary", response_model=ConnectionSummary)
def connections_summary(user=Depends(require_permission("network", "read"))):
    cached = _conn_summary_cache.get("summary")
    if cached is not None:
        return ConnectionSummary(counts=cached)
    counts = get_connection_summary()
    _conn_summary_cache.set("summary", counts, ttl=_SUMMARY_TTL)
    return ConnectionSummary(counts=counts)


@router.get("/bandwidth", response_model=List[BandwidthPoint])
def bandwidth_history(
    interface: Optional[str] = Query(None),
    hours: int = Query(24, ge=1, le=720),
    db: Session = Depends(get_db),
    user=Depends(require_permission("network", "read")),
):
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    q = db.query(NetworkSnapshot).filter(NetworkSnapshot.timestamp >= cutoff)
    if interface:
        q = q.filter(NetworkSnapshot.interface == interface)
    q = q.order_by(NetworkSnapshot.timestamp.asc())
    rows = q.all()
    if len(rows) > 1440:
        step = len(rows) // 1440
        rows = rows[::step]
    return [
        BandwidthPoint(
            timestamp=r.timestamp, interface=r.interface,
            bytes_sent=r.bytes_sent, bytes_recv=r.bytes_recv,
        )
        for r in rows
    ]


@router.get("/interfaces/names")
def interface_names(
    db: Session = Depends(get_db),
    user=Depends(require_permission("network", "read")),
):
    rows = db.query(NetworkSnapshot.interface).distinct().all()
    return [r[0] for r in rows]


@router.get("/devices")
def arp_devices(user=Depends(require_permission("network", "read"))):
    return get_arp_devices()


@router.get("/config")
def network_config(user=Depends(require_permission("network", "read"))):
    return get_network_config()
```

- [ ] **Step 5: Run affected test suites**

```bash
cd /home/crt/server_dashboard && pytest tests/test_system.py tests/test_logs.py tests/test_metrics_history_router.py -v
```

Expected: all PASS (admin token is used in existing tests, admin bypasses permission check).

- [ ] **Step 6: Run full suite**

```bash
cd /home/crt/server_dashboard && pytest -x -q
```

- [ ] **Step 7: Commit**

```bash
git add backend/routers/system.py backend/routers/logs.py backend/routers/network.py backend/routers/metrics_history.py
git commit -m "feat(permissions): migrate system/logs/network/metrics_history routers to require_permission"
```

---

## Task 5: Migrate `services.py`

**Files:**
- Modify: `backend/routers/services.py`

- [ ] **Step 1: Replace `backend/routers/services.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from backend.core.logging import get_audit_logger
from backend.dependencies import require_permission
from backend.schemas.services import ServiceInfo, ServiceLog, ServiceActionRequest
from backend.services.services_service import list_services, get_service_logs, control_service

router = APIRouter(prefix="/api/services", tags=["services"])


@router.get("/", response_model=List[ServiceInfo])
def get_services(user=Depends(require_permission("services", "read"))):
    try:
        return list_services()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/{name}/logs", response_model=ServiceLog)
def get_logs(name: str, lines: int = 100, user=Depends(require_permission("services", "read"))):
    try:
        return get_service_logs(name, lines)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/{name}/{action}")
def service_action(
    name: str,
    action: str,
    body: ServiceActionRequest = None,
    user=Depends(require_permission("services", "execute")),
):
    password = body.sudo_password if body else None
    try:
        result = control_service(name, action, password)
        get_audit_logger().info("service_control user=%s service=%s action=%s", user.username, name, action)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 2: Run services tests**

```bash
cd /home/crt/server_dashboard && pytest tests/test_services.py -v
```

Expected: all PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/routers/services.py
git commit -m "feat(permissions): migrate services router to require_permission"
```

---

## Task 6: Migrate `files.py`

**Files:**
- Modify: `backend/routers/files.py`

- [ ] **Step 1: Replace `backend/routers/files.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Header
from fastapi.responses import StreamingResponse
from pathlib import Path
from typing import List, Optional
from backend.core.logging import get_audit_logger
from backend.dependencies import require_permission
from backend.schemas.files import DirListing, FileContent, MkdirRequest, RenameRequest, FileWriteRequest
from backend.services.files_service import (
    list_dir, read_file, stream_file, make_dir, rename_path, delete_path, write_file, _safe_path
)

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("/list", response_model=DirListing)
def api_list(path: str = Query("/"), user=Depends(require_permission("files", "read"))):
    try:
        return list_dir(path)
    except (FileNotFoundError, NotADirectoryError) as e:
        raise HTTPException(404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))


@router.get("/content", response_model=FileContent)
def api_content(
    path: str = Query(...),
    user=Depends(require_permission("files", "read")),
    x_sudo_password: Optional[str] = Header(None),
):
    try:
        return read_file(path, sudo_password=x_sudo_password)
    except FileNotFoundError as e:
        raise HTTPException(404, detail=str(e))
    except (ValueError, IsADirectoryError) as e:
        raise HTTPException(400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(403, detail=f"{str(e)} — sudo password required")
    except RuntimeError as e:
        raise HTTPException(500, detail=str(e))


@router.get("/download")
def api_download(
    path: str = Query(...),
    user=Depends(require_permission("files", "read")),
    x_sudo_password: Optional[str] = Header(None),
):
    try:
        iterator, filename, size = stream_file(path, sudo_password=x_sudo_password)
    except FileNotFoundError as e:
        raise HTTPException(404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(403, detail=f"{str(e)} — sudo password required")
    except RuntimeError as e:
        raise HTTPException(500, detail=str(e))
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Length": str(size),
    }
    return StreamingResponse(iterator, media_type="application/octet-stream", headers=headers)


@router.post("/mkdir")
def api_mkdir(body: MkdirRequest, user=Depends(require_permission("files", "write"))):
    try:
        make_dir(body.path)
        return {"ok": True, "path": body.path}
    except FileExistsError:
        raise HTTPException(409, detail="Already exists")
    except (ValueError, PermissionError) as e:
        raise HTTPException(400, detail=str(e))


@router.post("/rename")
def api_rename(body: RenameRequest, user=Depends(require_permission("files", "write"))):
    try:
        rename_path(body.source, body.destination)
        return {"ok": True}
    except FileNotFoundError as e:
        raise HTTPException(404, detail=str(e))
    except (ValueError, PermissionError) as e:
        raise HTTPException(400, detail=str(e))


@router.delete("/delete")
def api_delete(path: str = Query(...), user=Depends(require_permission("files", "delete"))):
    try:
        delete_path(path)
        get_audit_logger().info("file_delete user=%s path=%s", user.username, path)
        return {"ok": True}
    except FileNotFoundError as e:
        raise HTTPException(404, detail=str(e))
    except (ValueError, PermissionError) as e:
        raise HTTPException(400, detail=str(e))


@router.post("/upload")
def api_upload(
    path: str = Query(...),
    file: UploadFile = File(...),
    user=Depends(require_permission("files", "write")),
):
    try:
        safe_name = Path(file.filename).name if file.filename else ""
        if not safe_name or safe_name in (".", ".."):
            raise HTTPException(400, detail="Invalid filename")
        target = _safe_path(path) / safe_name
        with open(target, "wb") as f:
            while chunk := file.file.read(65536):
                f.write(chunk)
        return {"ok": True, "path": str(target)}
    except HTTPException:
        raise
    except (ValueError, PermissionError) as e:
        raise HTTPException(400, detail=str(e))


@router.put("/content")
def api_write(
    body: FileWriteRequest,
    path: str = Query(...),
    user=Depends(require_permission("files", "write")),
    x_sudo_password: Optional[str] = Header(None),
):
    try:
        write_file(path, body.content, sudo_password=x_sudo_password)
        get_audit_logger().info("file_write user=%s path=%s", user.username, path)
        return {"ok": True}
    except (ValueError, PermissionError) as e:
        raise HTTPException(400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(500, detail=str(e))
```

- [ ] **Step 2: Run files tests**

```bash
cd /home/crt/server_dashboard && pytest tests/test_files.py -v
```

Expected: all PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/routers/files.py
git commit -m "feat(permissions): migrate files router to require_permission (read/write/delete)"
```

---

## Task 7: Migrate `scripts.py`

**Files:**
- Modify: `backend/routers/scripts.py`

The WebSocket endpoint can't use FastAPI `Depends` — it authenticates via `?token=`. We call `check_permission` manually in that handler.

- [ ] **Step 1: Replace `backend/routers/scripts.py`**

Key changes: replace all `Depends(get_current_user)` / `Depends(require_role(...))` with `Depends(require_permission(...))`, and add `check_permission` call in the WebSocket handler.

```python
import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from typing import List
from datetime import datetime, timezone
from backend.core.logging import get_audit_logger

from backend.dependencies import require_permission, check_permission
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
def list_favorites(db: Session = Depends(get_db), user=Depends(require_permission("scripts", "read"))):
    favs = db.query(ScriptFavorite).order_by(ScriptFavorite.created_at.desc()).all()
    return [build_favorite_out(f) for f in favs]


@router.post("/favorites", response_model=FavoriteOut)
def add_favorite(body: FavoriteCreate, db: Session = Depends(get_db), user=Depends(require_permission("scripts", "write"))):
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
def remove_favorite(fav_id: int, db: Session = Depends(get_db), user=Depends(require_permission("scripts", "delete"))):
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
    user=Depends(require_permission("scripts", "write")),
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
    user=Depends(require_permission("scripts", "execute")),
):
    fav = db.query(ScriptFavorite).filter(ScriptFavorite.id == fav_id).first()
    if not fav:
        raise HTTPException(404, detail="Favorite not found")

    if fav.admin_only and user.role != UserRole.admin:
        raise HTTPException(403, detail="This script is restricted to admins")

    p = Path(fav.path)
    if not p.exists() or not p.is_file():
        raise HTTPException(404, detail=f"Script not found: {fav.path}")

    try:
        runner = detect_runner(p)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    exe = ScriptExecution(
        script_path=fav.path,
        run_as_root=fav.run_as_root,
        triggered_by=user.username,
        is_running=True,
    )
    db.add(exe)
    db.commit()
    db.refresh(exe)

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
    try:
        payload = decode_token(token)
        user = db.query(User).filter(User.id == int(payload["sub"])).first()
        if not user:
            await websocket.close(code=4001)
            return
    except ValueError:
        await websocket.close(code=4001)
        return

    # Permission check via check_permission (WebSocket can't use Depends)
    if not check_permission(db, user, "scripts", "execute"):
        await websocket.close(code=4003)
        return

    fav = db.query(ScriptFavorite).filter(ScriptFavorite.id == fav_id).first()
    if not fav:
        await websocket.close(code=4004)
        return

    if fav.admin_only and user.role != UserRole.admin:
        await websocket.close(code=4003)
        return

    await websocket.accept()

    p = Path(fav.path)
    if not p.exists() or not p.is_file():
        await websocket.send_json({"type": "error", "detail": f"Script not found: {fav.path}"})
        await websocket.close()
        return

    try:
        runner = detect_runner(p)
    except ValueError as e:
        await websocket.send_json({"type": "error", "detail": str(e)})
        await websocket.close()
        return

    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        params = json.loads(raw)
    except (asyncio.TimeoutError, Exception):
        params = {}

    sudo_password = params.get("sudo_password")
    args = params.get("args") or []

    exe = ScriptExecution(
        script_path=fav.path,
        run_as_root=fav.run_as_root,
        triggered_by=user.username,
        is_running=True,
    )
    db.add(exe)
    db.commit()
    db.refresh(exe)

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

    sent = 0
    try:
        while True:
            state = get_poll_state(exe.id)
            if state is None:
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
        pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@router.get("/executions/{exec_id}", response_model=ExecutionPoll)
def poll_execution(exec_id: int, user=Depends(require_permission("scripts", "read")), db: Session = Depends(get_db)):
    state = get_poll_state(exec_id)
    if state is not None:
        return ExecutionPoll(
            id=exec_id,
            running=state["running"],
            exit_code=state["exit_code"],
            lines=list(state["lines"]),
        )
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
def execution_history(fav_id: int, db: Session = Depends(get_db), user=Depends(require_permission("scripts", "read"))):
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
```

- [ ] **Step 2: Run scripts-related tests**

```bash
cd /home/crt/server_dashboard && pytest tests/test_scripts_multiworker.py -v
```

Expected: all PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/routers/scripts.py
git commit -m "feat(permissions): migrate scripts router to require_permission (read/write/delete/execute)"
```

---

## Task 8: Migrate `crontab.py`

**Files:**
- Modify: `backend/routers/crontab.py`

- [ ] **Step 1: Replace `backend/routers/crontab.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from typing import List

from backend.core.logging import get_audit_logger
from backend.dependencies import require_permission
from backend.schemas.crontab import CrontabEntry, CrontabEntryCreate
from backend.services.crontab_service import (
    list_entries, add_entry, update_entry, delete_entry, validate_field, toggle_entry,
)

router = APIRouter(prefix="/api/crontab", tags=["crontab"])


def _validate_create(data: CrontabEntryCreate) -> None:
    if not data.command.strip():
        raise HTTPException(400, detail="Command cannot be empty")
    if not data.is_special:
        for field, name in [
            (data.minute, "minute"), (data.hour, "hour"),
            (data.dom, "day-of-month"), (data.month, "month"),
            (data.dow, "day-of-week"),
        ]:
            try:
                validate_field(field, name)
            except ValueError as e:
                raise HTTPException(400, detail=str(e))


@router.get("/", response_model=List[CrontabEntry])
def get_crontab(user=Depends(require_permission("crontab", "read"))):
    try:
        return list_entries()
    except RuntimeError as e:
        raise HTTPException(503, detail=str(e))


@router.post("/", response_model=List[CrontabEntry])
def create_entry(body: CrontabEntryCreate, user=Depends(require_permission("crontab", "write"))):
    _validate_create(body)
    try:
        result = add_entry(body)
        get_audit_logger().info("crontab_add user=%s", user.username)
        return result
    except RuntimeError as e:
        raise HTTPException(500, detail=str(e))


@router.put("/{entry_id}", response_model=List[CrontabEntry])
def edit_entry(
    entry_id: int,
    body: CrontabEntryCreate,
    user=Depends(require_permission("crontab", "write")),
):
    _validate_create(body)
    try:
        result = update_entry(entry_id, body)
        get_audit_logger().info("crontab_update user=%s entry_id=%s", user.username, entry_id)
        return result
    except ValueError as e:
        raise HTTPException(404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(500, detail=str(e))


@router.delete("/{entry_id}", response_model=List[CrontabEntry])
def remove_entry(entry_id: int, user=Depends(require_permission("crontab", "delete"))):
    try:
        result = delete_entry(entry_id)
        get_audit_logger().info("crontab_delete user=%s entry_id=%s", user.username, entry_id)
        return result
    except ValueError as e:
        raise HTTPException(404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(500, detail=str(e))


@router.patch("/{entry_id}/toggle", response_model=List[CrontabEntry])
def toggle_entry_endpoint(entry_id: int, user=Depends(require_permission("crontab", "write"))):
    try:
        result = toggle_entry(entry_id)
        enabled = next((e.enabled for e in result if e.id == entry_id), None)
        get_audit_logger().info("crontab_toggle user=%s entry_id=%s enabled=%s", user.username, entry_id, enabled)
        return result
    except ValueError as e:
        raise HTTPException(404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(500, detail=str(e))
```

- [ ] **Step 2: Run crontab tests**

```bash
cd /home/crt/server_dashboard && pytest -k crontab -v
```

Expected: all PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/routers/crontab.py
git commit -m "feat(permissions): migrate crontab router to require_permission (read/write/delete)"
```

---

## Task 9: Migrate `pipelines.py`

**Files:**
- Modify: `backend/routers/pipelines.py`

Only the `Depends(...)` calls change — the rest of the router logic stays identical.

- [ ] **Step 1: Replace the imports and dependency calls in `backend/routers/pipelines.py`**

Change the import line from:
```python
from backend.dependencies import get_current_user, require_role
```
to:
```python
from backend.dependencies import require_permission
```

Then update each endpoint's `Depends`:
- `GET /pipelines/` → `Depends(require_permission("pipelines", "read"))`
- `POST /pipelines/` → `Depends(require_permission("pipelines", "write"))`
- `POST /pipelines/import` → `Depends(require_permission("pipelines", "write"))`
- `GET /pipelines/{id}` → `Depends(require_permission("pipelines", "read"))`
- `PUT /pipelines/{id}` → `Depends(require_permission("pipelines", "write"))`
- `DELETE /pipelines/{id}` → `Depends(require_permission("pipelines", "delete"))`
- `POST /pipelines/{id}/run` → `Depends(require_permission("pipelines", "execute"))`
- `GET /pipelines/{id}/runs` → `Depends(require_permission("pipelines", "read"))`
- `GET /pipelines/runs/{run_id}` → `Depends(require_permission("pipelines", "read"))`

Also remove `from backend.models.user import UserRole` if it's only used for `require_role`.

- [ ] **Step 2: Run pipeline tests**

```bash
cd /home/crt/server_dashboard && pytest tests/test_pipelines_api.py -v
```

Expected: all PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/routers/pipelines.py
git commit -m "feat(permissions): migrate pipelines router to require_permission (read/write/delete/execute)"
```

---

## Task 10: Frontend — fix `isAdmin` consistency + router resource fix

**Files:**
- Modify: `frontend/src/views/CrontabView.vue`
- Modify: `frontend/src/views/PipelinesView.vue`
- Modify: `frontend/src/views/ScriptsView.vue`
- Modify: `frontend/src/router/index.js`

Three views use `const isAdmin = auth.role === 'admin'` which is a non-reactive snapshot. Replace with the reactive computed.

- [ ] **Step 1: Fix `CrontabView.vue`**

Find (around line 426):
```js
const isAdmin = auth.role === 'admin'
```
Replace with:
```js
const isAdmin = computed(() => auth.isAdmin)
```
And add `computed` to the vue import at the top of `<script setup>`:
```js
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
```
(add `computed` if not already there)

- [ ] **Step 2: Fix `PipelinesView.vue`**

Find (around line 350):
```js
const isAdmin = auth.role === 'admin'
```
Replace with:
```js
const isAdmin = computed(() => auth.isAdmin)
```
Add `computed` to the vue import if missing.

- [ ] **Step 3: Fix `ScriptsView.vue`**

Find (around line 314):
```js
const isAdmin = auth.role === 'admin'
```
Replace with:
```js
const isAdmin = computed(() => auth.isAdmin)
```
Add `computed` to the vue import if missing.

- [ ] **Step 4: Fix pipelines route resource in `router/index.js`**

Find:
```js
{ path: '/pipelines', component: () => import('../views/PipelinesView.vue'), meta: { requiresAuth: true, title: 'Pipelines', resource: 'scripts' } },
```
Replace with:
```js
{ path: '/pipelines', component: () => import('../views/PipelinesView.vue'), meta: { requiresAuth: true, title: 'Pipelines', resource: 'pipelines' } },
```

Also add the `/admin/permissions` route:
```js
{ path: '/admin/permissions', component: () => import('../views/AdminPermissionsView.vue'), meta: { requiresAuth: true, title: 'Permissions', adminOnly: true } },
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/CrontabView.vue frontend/src/views/PipelinesView.vue frontend/src/views/ScriptsView.vue frontend/src/router/index.js
git commit -m "fix(frontend): use reactive auth.isAdmin computed, fix pipelines route resource to 'pipelines'"
```

---

## Task 11: Frontend — `AdminPermissionsView.vue` + sidebar

**Files:**
- Create: `frontend/src/views/AdminPermissionsView.vue`
- Modify: `frontend/src/components/layout/AppSidebar.vue`

The permissions view shows a matrix table: rows are `resource × action` pairs, columns are `readonly`, `operator`, and `admin` (disabled). Checkboxes call `PUT /api/admin/permissions/{role}` when toggled.

- [ ] **Step 1: Create `frontend/src/views/AdminPermissionsView.vue`**

```vue
<template>
  <div class="permissions-view">
    <Card class="permissions-card">
      <template #content>

        <div class="card-section-header">
          <i class="pi pi-shield section-icon" />
          <span class="section-title">PERMISSION MATRIX</span>
        </div>
        <Divider class="section-divider" />

        <div v-if="loading" class="loading-state">
          <ProgressSpinner style="width:32px;height:32px" />
        </div>

        <div v-else>
          <DataTable :value="rows" size="small" :show-gridlines="true">
            <template #empty>
              <span class="cell-empty">No permissions found</span>
            </template>

            <Column header="Resource" style="width: 120px">
              <template #body="{ data }">
                <span class="cell-mono">{{ data.resource }}</span>
              </template>
            </Column>

            <Column header="Action" style="width: 100px">
              <template #body="{ data }">
                <Tag :value="data.action" :severity="actionSeverity(data.action)" />
              </template>
            </Column>

            <Column header="Admin" style="width: 80px; text-align:center">
              <template #body>
                <Checkbox :modelValue="true" :disabled="true" binary />
              </template>
            </Column>

            <Column header="Operator" style="width: 90px; text-align:center">
              <template #body="{ data }">
                <Checkbox
                  :modelValue="hasPermission('operator', data.resource, data.action)"
                  binary
                  @change="toggle('operator', data.resource, data.action)"
                />
              </template>
            </Column>

            <Column header="Read-only" style="width: 90px; text-align:center">
              <template #body="{ data }">
                <Checkbox
                  :modelValue="hasPermission('readonly', data.resource, data.action)"
                  binary
                  @change="toggle('readonly', data.resource, data.action)"
                />
              </template>
            </Column>
          </DataTable>
        </div>

        <div v-if="error" class="error-msg">{{ error }}</div>

      </template>
    </Card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api/client.js'

// All resource×action combinations in the system
const MATRIX_ROWS = [
  { resource: 'system',    action: 'read' },
  { resource: 'services',  action: 'read' },
  { resource: 'services',  action: 'write' },
  { resource: 'services',  action: 'execute' },
  { resource: 'files',     action: 'read' },
  { resource: 'files',     action: 'write' },
  { resource: 'files',     action: 'delete' },
  { resource: 'network',   action: 'read' },
  { resource: 'scripts',   action: 'read' },
  { resource: 'scripts',   action: 'write' },
  { resource: 'scripts',   action: 'delete' },
  { resource: 'scripts',   action: 'execute' },
  { resource: 'crontab',   action: 'read' },
  { resource: 'crontab',   action: 'write' },
  { resource: 'crontab',   action: 'delete' },
  { resource: 'logs',      action: 'read' },
  { resource: 'pipelines', action: 'read' },
  { resource: 'pipelines', action: 'write' },
  { resource: 'pipelines', action: 'delete' },
  { resource: 'pipelines', action: 'execute' },
  { resource: 'users',     action: 'read' },
  { resource: 'users',     action: 'write' },
  { resource: 'users',     action: 'delete' },
]

const rows = ref(MATRIX_ROWS)
const loading = ref(true)
const error = ref(null)

// permissions[role] = Set of "resource|action" strings
const permissions = ref({ operator: new Set(), readonly: new Set() })

function key(resource, action) {
  return `${resource}|${action}`
}

function hasPermission(role, resource, action) {
  return permissions.value[role]?.has(key(resource, action)) ?? false
}

async function loadPermissions() {
  loading.value = true
  error.value = null
  try {
    const { data } = await api.get('/admin/permissions')
    permissions.value.operator = new Set(data.operator.map(p => key(p.resource, p.action)))
    permissions.value.readonly = new Set(data.readonly.map(p => key(p.resource, p.action)))
  } catch (e) {
    error.value = 'Failed to load permissions'
  } finally {
    loading.value = false
  }
}

async function toggle(role, resource, action) {
  const k = key(resource, action)
  const current = new Set(permissions.value[role])
  if (current.has(k)) {
    current.delete(k)
  } else {
    current.add(k)
  }
  permissions.value[role] = current

  // Build payload from current Set
  const payload = [...current].map(k => {
    const [res, act] = k.split('|')
    return { resource: res, action: act }
  })

  try {
    await api.put(`/admin/permissions/${role}`, payload)
  } catch (e) {
    // Revert optimistic update
    error.value = 'Failed to save permission change'
    await loadPermissions()
  }
}

function actionSeverity(action) {
  return { read: 'info', write: 'warn', delete: 'danger', execute: 'success' }[action] ?? 'secondary'
}

onMounted(loadPermissions)
</script>

<style scoped>
.permissions-view {
  padding: 16px;
  max-width: 900px;
}
.permissions-card {
  border: 1px solid var(--p-surface-border);
}
.card-section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-bottom: 4px;
}
.section-icon {
  color: var(--brand-orange);
  font-size: var(--text-base);
}
.section-title {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: 2px;
  color: var(--p-text-muted-color);
}
.section-divider {
  margin: 8px 0 16px;
}
.loading-state {
  display: flex;
  justify-content: center;
  padding: 32px;
}
.cell-mono {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
}
.cell-empty {
  color: var(--p-text-muted-color);
  font-size: var(--text-sm);
}
.error-msg {
  color: var(--p-red-500);
  font-size: var(--text-sm);
  margin-top: 12px;
}
</style>
```

- [ ] **Step 2: Add Permissions link in `AppSidebar.vue`**

Find the ADMIN section (around line 43):
```html
<div class="nav-section" v-if="auth.isAdmin">
  <span class="nav-section-label">ADMIN</span>
  <RouterLink class="nav-item" to="/admin/users" :class="{ active: route.path === '/admin/users' }">
    <i class="pi pi-users nav-icon" />
    <span class="nav-label">Users</span>
  </RouterLink>
</div>
```
Replace with:
```html
<div class="nav-section" v-if="auth.isAdmin">
  <span class="nav-section-label">ADMIN</span>
  <RouterLink class="nav-item" to="/admin/users" :class="{ active: route.path === '/admin/users' }">
    <i class="pi pi-users nav-icon" />
    <span class="nav-label">Users</span>
  </RouterLink>
  <RouterLink class="nav-item" to="/admin/permissions" :class="{ active: route.path === '/admin/permissions' }">
    <i class="pi pi-shield nav-icon" />
    <span class="nav-label">Permissions</span>
  </RouterLink>
</div>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/AdminPermissionsView.vue frontend/src/components/layout/AppSidebar.vue
git commit -m "feat(frontend): add AdminPermissionsView permission matrix editor + sidebar link"
```

---

## Task 12: CLAUDE.md + Bitácora

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/bitacora.md`

- [ ] **Step 1: Add permissions rule to `CLAUDE.md`**

Append the following section after the `## Key Constraints` section:

```markdown
## Permissions for New Features

Every new feature added to ServerDash MUST follow this checklist:

1. **Identify or create a resource name** (e.g., `backups`, `alerts`)
2. **Define which actions apply** from: `read`, `write`, `delete`, `execute`
3. **Add default permissions** to `DEFAULT_PERMISSIONS` in `backend/scripts/init_db.py` for `operator` and `readonly` roles (admin always has everything)
4. **Use `require_permission(resource, action)`** in every new backend endpoint — never use bare `get_current_user` for protected resources
5. **Use `auth.hasPermission(resource, action)`** in the frontend to conditionally render action buttons and filter nav items
6. **Add the resource to `MATRIX_ROWS`** in `frontend/src/views/AdminPermissionsView.vue` so the admin can edit it from the UI
7. **Update the default matrix** in `docs/superpowers/specs/2026-04-16-roles-permissions-design.md`

**Never use `get_current_user` directly** in a router that controls access to a resource — always use `require_permission`.
```

- [ ] **Step 2: Add entry to `docs/bitacora.md`**

Prepend to the top of the file (after any front matter):

```markdown
## 2026-04-16 — Roles & Permissions System (full implementation)

**Description:** Completed the end-to-end permission system. Previously the `Permission` table existed but was never used — all protection was via `require_role`. Now all backend endpoints use `require_permission(resource, action)`, the default matrix is seeded with 4 actions (read/write/delete/execute), admin bypasses the table entirely, and a new `/admin/permissions` UI lets the admin edit permissions per role in real time.

**Files modified:**
- `backend/scripts/init_db.py` — updated DEFAULT_PERMISSIONS (4 actions, no admin in table, added pipelines)
- `backend/dependencies.py` — admin bypass in check_permission
- `backend/routers/admin.py` — added GET/PUT /api/admin/permissions endpoints
- `backend/routers/services.py`, `files.py`, `scripts.py`, `crontab.py`, `pipelines.py`, `system.py`, `logs.py`, `network.py`, `metrics_history.py` — migrated to require_permission
- `frontend/src/views/AdminPermissionsView.vue` — new permission matrix editor
- `frontend/src/views/CrontabView.vue`, `PipelinesView.vue`, `ScriptsView.vue` — fixed reactive isAdmin
- `frontend/src/router/index.js` — fixed pipelines resource, added /admin/permissions route
- `frontend/src/components/layout/AppSidebar.vue` — added Permissions link
- `CLAUDE.md` — added "Permissions for New Features" rule

**Bugs fixed:**
- Sidebar was empty for non-admin users because Permission table was never seeded for operator/readonly
- `const isAdmin = auth.role === 'admin'` in 3 views was non-reactive
- `/pipelines` route had `resource: 'scripts'` instead of `'pipelines'`
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md docs/bitacora.md
git commit -m "docs: add permissions rule to CLAUDE.md and log full permissions system in bitacora"
```

---

## Task 13: Final verification

- [ ] **Step 1: Run full test suite**

```bash
cd /home/crt/server_dashboard && pytest -v
```

Expected: all tests pass.

- [ ] **Step 2: Build the frontend**

```bash
cd /home/crt/server_dashboard/frontend && npm run build
```

Expected: clean build, no errors.

- [ ] **Step 3: Verify permissions seeding runs cleanly**

```bash
cd /home/crt/server_dashboard && python -m backend.scripts.init_db
```

Expected: `Admin user 'admin' already exists.` (no crash, exits cleanly).

- [ ] **Step 4: Final commit if any stragglers**

```bash
cd /home/crt/server_dashboard && git status
```

If anything is uncommitted, stage and commit it with an appropriate message.
