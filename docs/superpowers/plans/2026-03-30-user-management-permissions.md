# User Management with Dynamic Permissions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the single-admin system into a multi-user platform with granular, dynamic permissions. Admins can create users, assign roles, and configure per-resource permissions. The frontend hides inaccessible routes/features based on the logged-in user's permissions.

**Architecture:** Extend the existing `User` model and `UserRole` enum. Add a new `Permission` table for granular per-role resource+action mappings. A `require_permission()` dependency replaces or augments `require_role()` for fine-grained endpoint protection. JWT tokens carry the role; permissions are looked up from DB (cached). The frontend reads permissions from a new `/api/auth/me` endpoint and reactively hides/shows sidebar items and UI controls. A new admin-only `/admin/users` route provides CRUD for user management.

**Tech Stack:** SQLAlchemy (existing), JWT (existing), Pinia store (existing), PrimeVue (existing). No new dependencies.

---

### Task 1: Extend User Model + Add Permission Model

**Files:**
- Modify: `backend/models/user.py`
- Create: `backend/models/permission.py`
- Modify: `backend/main.py` (register model)
- Modify: `backend/scripts/add_indexes.py`

- [ ] **Step 1: Add `is_active` and `created_at` columns to User**

Edit `backend/models/user.py`:

```python
import enum
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum
from sqlalchemy.sql import func
from backend.database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    operator = "operator"
    readonly = "readonly"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.readonly)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now())
```

- [ ] **Step 2: Create the Permission model**

```python
# backend/models/permission.py
from sqlalchemy import Column, Integer, String, Enum, Index
from backend.database import Base
from backend.models.user import UserRole


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    role = Column(Enum(UserRole), nullable=False)
    resource = Column(String, nullable=False)  # "scripts", "services", "files", "network", "crontab", "logs", "system"
    action = Column(String, nullable=False)    # "read", "write", "execute"

    __table_args__ = (
        Index("ix_permissions_role", "role"),
        Index("ix_permissions_role_resource", "role", "resource"),
    )
```

- [ ] **Step 3: Register model in main.py**

Add after the other model imports:

```python
import backend.models.permission  # noqa: F401
```

- [ ] **Step 4: Add indexes to add_indexes.py**

Append to `statements` list:

```python
"CREATE INDEX IF NOT EXISTS ix_permissions_role ON permissions (role)",
"CREATE INDEX IF NOT EXISTS ix_permissions_role_resource ON permissions (role, resource)",
```

- [ ] **Step 5: Verify table creation**

```bash
python -c "
from backend.database import engine, Base
import backend.models.user
import backend.models.permission
Base.metadata.create_all(bind=engine)
print('Tables created: users (extended), permissions')
"
```

Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add backend/models/user.py backend/models/permission.py backend/main.py backend/scripts/add_indexes.py
git commit -m "feat(users): extend User model, add Permission model"
```

---

### Task 2: Seed Default Permissions

**Files:**
- Modify: `backend/scripts/init_db.py`

- [ ] **Step 1: Read current init_db.py**

Read the file to understand the current seeding pattern.

- [ ] **Step 2: Write failing test**

Add to `tests/test_metrics_history.py` or create `tests/test_permissions.py`:

```python
from backend.models.permission import Permission
from backend.models.user import UserRole


def test_seed_permissions(db_session):
    from backend.scripts.init_db import seed_permissions
    seed_permissions(db_session)
    perms = db_session.query(Permission).all()
    assert len(perms) > 0
    # Admin should have all permissions
    admin_perms = [p for p in perms if p.role == UserRole.admin]
    assert len(admin_perms) >= 7  # at least one per resource
    # Readonly should only have read
    ro_perms = [p for p in perms if p.role == UserRole.readonly]
    for p in ro_perms:
        assert p.action == "read"
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/test_permissions.py::test_seed_permissions -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 4: Add seed_permissions to init_db.py**

Add this function to `backend/scripts/init_db.py`:

```python
from backend.models.permission import Permission
from backend.models.user import UserRole

RESOURCE_LIST = ["system", "services", "files", "scripts", "crontab", "logs", "network"]

DEFAULT_PERMISSIONS = {
    UserRole.admin: [(r, a) for r in RESOURCE_LIST for a in ("read", "write", "execute")],
    UserRole.operator: (
        [(r, "read") for r in RESOURCE_LIST]
        + [("services", "write"), ("services", "execute"),
           ("scripts", "write"), ("scripts", "execute"),
           ("crontab", "write"), ("crontab", "execute"),
           ("files", "write")]
    ),
    UserRole.readonly: [(r, "read") for r in RESOURCE_LIST],
}


def seed_permissions(db):
    """Insert default permissions if the table is empty."""
    if db.query(Permission).first() is not None:
        return
    for role, pairs in DEFAULT_PERMISSIONS.items():
        for resource, action in pairs:
            db.add(Permission(role=role, resource=resource, action=action))
    db.commit()
```

Call `seed_permissions(db)` inside the existing `main()` function after the admin user is created.

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/test_permissions.py::test_seed_permissions -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/init_db.py tests/test_permissions.py
git commit -m "feat(users): seed default permissions per role"
```

---

### Task 3: Permission Checking Dependency

**Files:**
- Modify: `backend/dependencies.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_permissions.py`:

```python
from fastapi import HTTPException
import pytest


def test_user_has_permission_admin(db_session):
    from backend.dependencies import check_permission
    from backend.models.user import User, UserRole
    from backend.scripts.init_db import seed_permissions

    seed_permissions(db_session)
    user = User(username="testadmin", hashed_password="x", role=UserRole.admin)
    db_session.add(user)
    db_session.commit()

    assert check_permission(db_session, user, "scripts", "execute") is True


def test_user_lacks_permission_readonly(db_session):
    from backend.dependencies import check_permission
    from backend.models.user import User, UserRole
    from backend.scripts.init_db import seed_permissions

    seed_permissions(db_session)
    user = User(username="viewer", hashed_password="x", role=UserRole.readonly)
    db_session.add(user)
    db_session.commit()

    assert check_permission(db_session, user, "scripts", "execute") is False


def test_user_has_read_permission_readonly(db_session):
    from backend.dependencies import check_permission
    from backend.models.user import User, UserRole
    from backend.scripts.init_db import seed_permissions

    seed_permissions(db_session)
    user = User(username="viewer", hashed_password="x", role=UserRole.readonly)
    db_session.add(user)
    db_session.commit()

    assert check_permission(db_session, user, "scripts", "read") is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_permissions.py -v
```

Expected: FAIL with `ImportError: cannot import name 'check_permission'`.

- [ ] **Step 3: Implement check_permission and require_permission**

Add to `backend/dependencies.py`:

```python
from backend.models.permission import Permission
from backend.services.cache import TTLCache

_perm_cache = TTLCache()
_PERM_TTL = 60  # cache permissions for 60 seconds


def check_permission(db: Session, user: User, resource: str, action: str) -> bool:
    """Check if a user's role grants them the given resource+action permission."""
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


def require_permission(resource: str, action: str):
    """FastAPI dependency: raises 403 if the user lacks the required permission."""
    def checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if not check_permission(db, current_user, resource, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {resource}.{action}",
            )
        return current_user
    return checker
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_permissions.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Add cache reset fixture to conftest.py**

Add to `tests/conftest.py`:

```python
@pytest.fixture(autouse=True)
def reset_permission_cache():
    from backend.dependencies import _perm_cache
    _perm_cache.clear()
    yield
```

- [ ] **Step 6: Commit**

```bash
git add backend/dependencies.py tests/test_permissions.py tests/conftest.py
git commit -m "feat(users): add check_permission + require_permission dependency"
```

---

### Task 4: Pydantic Schemas for Users + Admin Router

**Files:**
- Create: `backend/schemas/users.py`
- Create: `backend/routers/admin.py`
- Modify: `backend/main.py` (register router)

- [ ] **Step 1: Create user schemas**

```python
# backend/schemas/users.py
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "readonly"


class UserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class PermissionOut(BaseModel):
    resource: str
    action: str

    class Config:
        from_attributes = True


class MeOut(BaseModel):
    id: int
    username: str
    role: str
    permissions: List[PermissionOut]
```

- [ ] **Step 2: Write failing integration tests**

Create `tests/test_admin_router.py`:

```python
from backend.models.user import UserRole


def get_token(client, username="admin", password="adminpass"):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    return r.json()["access_token"]


def test_list_users(test_app):
    token = get_token(test_app)
    r = test_app.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    assert data[0]["username"] == "admin"


def test_create_user(test_app):
    token = get_token(test_app)
    r = test_app.post("/api/admin/users", json={
        "username": "newuser",
        "password": "securepass123",
        "role": "operator",
    }, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201
    data = r.json()
    assert data["username"] == "newuser"
    assert data["role"] == "operator"
    assert data["is_active"] is True


def test_create_duplicate_user(test_app):
    token = get_token(test_app)
    test_app.post("/api/admin/users", json={
        "username": "dupe", "password": "pass123", "role": "readonly",
    }, headers={"Authorization": f"Bearer {token}"})
    r = test_app.post("/api/admin/users", json={
        "username": "dupe", "password": "pass456", "role": "readonly",
    }, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 409


def test_update_user_role(test_app):
    token = get_token(test_app)
    # Create a user first
    r = test_app.post("/api/admin/users", json={
        "username": "roletest", "password": "pass", "role": "readonly",
    }, headers={"Authorization": f"Bearer {token}"})
    user_id = r.json()["id"]
    # Update role
    r = test_app.patch(f"/api/admin/users/{user_id}", json={
        "role": "operator",
    }, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["role"] == "operator"


def test_deactivate_user(test_app):
    token = get_token(test_app)
    r = test_app.post("/api/admin/users", json={
        "username": "deact", "password": "pass", "role": "readonly",
    }, headers={"Authorization": f"Bearer {token}"})
    user_id = r.json()["id"]
    r = test_app.patch(f"/api/admin/users/{user_id}", json={
        "is_active": False,
    }, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["is_active"] is False


def test_delete_user(test_app):
    token = get_token(test_app)
    r = test_app.post("/api/admin/users", json={
        "username": "todelete", "password": "pass", "role": "readonly",
    }, headers={"Authorization": f"Bearer {token}"})
    user_id = r.json()["id"]
    r = test_app.delete(f"/api/admin/users/{user_id}",
                         headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_cannot_delete_self(test_app):
    token = get_token(test_app)
    # Get admin's own id
    r = test_app.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    admin_id = r.json()["id"]
    r = test_app.delete(f"/api/admin/users/{admin_id}",
                         headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 400


def test_non_admin_cannot_access(test_app):
    # Create a readonly user
    token = get_token(test_app)
    test_app.post("/api/admin/users", json={
        "username": "viewer", "password": "viewerpass", "role": "readonly",
    }, headers={"Authorization": f"Bearer {token}"})
    # Login as readonly
    viewer_token = get_token(test_app, "viewer", "viewerpass")
    r = test_app.get("/api/admin/users",
                      headers={"Authorization": f"Bearer {viewer_token}"})
    assert r.status_code == 403
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_admin_router.py -v
```

Expected: FAIL (404 or ImportError).

- [ ] **Step 4: Write the admin router**

```python
# backend/routers/admin.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_current_user, require_role
from backend.models.user import User, UserRole
from backend.schemas.users import UserOut, UserCreate, UserUpdate
from backend.services.auth_service import hash_password

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users", response_model=List[UserOut])
def list_users(
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    return db.query(User).order_by(User.id).all()


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    existing = db.query(User).filter(User.username == body.username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")
    try:
        role = UserRole(body.role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {body.role}")
    new_user = User(
        username=body.username,
        hashed_password=hash_password(body.password),
        role=role,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
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
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(target)
    db.commit()
    return {"ok": True}
```

- [ ] **Step 5: Add /api/auth/me endpoint**

Add to `backend/routers/auth.py`:

```python
from backend.models.permission import Permission
from backend.schemas.users import MeOut, PermissionOut

@router.get("/me", response_model=MeOut)
def get_me(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    perms = db.query(Permission).filter(Permission.role == current_user.role).all()
    return MeOut(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role.value,
        permissions=[PermissionOut(resource=p.resource, action=p.action) for p in perms],
    )
```

Ensure `from sqlalchemy.orm import Session` and `from backend.database import get_db` are imported in `auth.py` (check existing imports).

- [ ] **Step 6: Register admin router in main.py**

Add import:

```python
from backend.routers.admin import router as admin_router
```

Add:

```python
app.include_router(admin_router)
```

- [ ] **Step 7: Seed permissions in test fixture**

In `tests/conftest.py`, inside the `test_app` fixture, add after the admin user creation and before `yield`:

```python
from backend.scripts.init_db import seed_permissions
db = TestingSession()
seed_permissions(db)
db.close()
```

- [ ] **Step 8: Run tests to verify they pass**

```bash
pytest tests/test_admin_router.py -v
```

Expected: All 8 tests PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/schemas/users.py backend/routers/admin.py backend/routers/auth.py backend/main.py tests/test_admin_router.py tests/conftest.py
git commit -m "feat(users): add admin router for user CRUD + /auth/me endpoint"
```

---

### Task 5: Block Inactive Users from Login

**Files:**
- Modify: `backend/routers/auth.py`
- Modify: `backend/dependencies.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_admin_router.py`:

```python
def test_inactive_user_cannot_login(test_app):
    token = get_token(test_app)
    # Create then deactivate
    r = test_app.post("/api/admin/users", json={
        "username": "inactive", "password": "pass", "role": "readonly",
    }, headers={"Authorization": f"Bearer {token}"})
    user_id = r.json()["id"]
    test_app.patch(f"/api/admin/users/{user_id}", json={"is_active": False},
                    headers={"Authorization": f"Bearer {token}"})
    # Try to login
    r = test_app.post("/api/auth/login", json={"username": "inactive", "password": "pass"})
    assert r.status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_admin_router.py::test_inactive_user_cannot_login -v
```

Expected: FAIL (200 instead of 403 — login currently succeeds).

- [ ] **Step 3: Add is_active check to login endpoint**

In `backend/routers/auth.py`, in the login function, after verifying password and before creating the token, add:

```python
if not user.is_active:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")
```

- [ ] **Step 4: Add is_active check to get_current_user**

In `backend/dependencies.py`, in `get_current_user`, after finding the user from DB, add:

```python
if not user.is_active:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/test_admin_router.py::test_inactive_user_cannot_login -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/auth.py backend/dependencies.py
git commit -m "feat(users): block inactive users from login and API access"
```

---

### Task 6: Frontend — Auth Store Permissions + Route Guards

**Files:**
- Modify: `frontend/src/stores/auth.js`
- Modify: `frontend/src/api/client.js` (add /me fetch)
- Modify: `frontend/src/router/index.js`

- [ ] **Step 1: Extend auth store to hold permissions**

Replace `frontend/src/stores/auth.js`:

```javascript
import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import api from '../api/client.js'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('access_token'))
  const username = ref(localStorage.getItem('username') || null)
  const role = ref(localStorage.getItem('role') || null)
  const permissions = ref([])
  const isAuthenticated = computed(() => !!token.value)
  const isAdmin = computed(() => role.value === 'admin')

  function hasPermission(resource, action) {
    if (role.value === 'admin') return true
    return permissions.value.some(p => p.resource === resource && p.action === action)
  }

  async function fetchMe() {
    try {
      const { data } = await api.get('/auth/me')
      username.value = data.username
      role.value = data.role
      permissions.value = data.permissions
      localStorage.setItem('username', data.username)
      localStorage.setItem('role', data.role)
    } catch {
      // token may be invalid
    }
  }

  async function login(usernameInput, password) {
    const { data } = await api.post('/auth/login', { username: usernameInput, password })
    token.value = data.access_token
    localStorage.setItem('access_token', data.access_token)
    const payload = JSON.parse(atob(data.access_token.split('.')[1]))
    username.value = payload.username
    role.value = payload.role
    localStorage.setItem('username', payload.username)
    localStorage.setItem('role', payload.role)
    await fetchMe()
  }

  function logout() {
    token.value = null
    username.value = null
    role.value = null
    permissions.value = []
    localStorage.removeItem('access_token')
    localStorage.removeItem('username')
    localStorage.removeItem('role')
  }

  return { token, username, role, permissions, isAuthenticated, isAdmin, hasPermission, login, logout, fetchMe }
})
```

- [ ] **Step 2: Add permission-based route meta**

Update `frontend/src/router/index.js` to add `resource` meta on each route:

```javascript
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

const routes = [
  { path: '/login',    component: () => import('../views/LoginView.vue'),    meta: { public: true,        title: 'Login'     } },
  { path: '/',         component: () => import('../views/DashboardView.vue'), meta: { requiresAuth: true,  title: 'Dashboard', resource: 'system' } },
  { path: '/services', component: () => import('../views/ServicesView.vue'),  meta: { requiresAuth: true,  title: 'Services',  resource: 'services' } },
  { path: '/files',    component: () => import('../views/FilesView.vue'),     meta: { requiresAuth: true,  title: 'Files',     resource: 'files' } },
  { path: '/scripts',  component: () => import('../views/ScriptsView.vue'),   meta: { requiresAuth: true,  title: 'Scripts',   resource: 'scripts' } },
  { path: '/crontab',  component: () => import('../views/CrontabView.vue'),   meta: { requiresAuth: true,  title: 'Crontab',   resource: 'crontab' } },
  { path: '/logs',     component: () => import('../views/LogsView.vue'),      meta: { requiresAuth: true,  title: 'Logs',      resource: 'logs' } },
  { path: '/network',  component: () => import('../views/NetworkView.vue'),   meta: { requiresAuth: true,  title: 'Network',   resource: 'network' } },
  { path: '/admin/users', component: () => import('../views/AdminUsersView.vue'), meta: { requiresAuth: true, title: 'Users', adminOnly: true } },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.isAuthenticated) return '/login'
  if (to.path === '/login' && auth.isAuthenticated) return '/'
  if (to.meta.adminOnly && !auth.isAdmin) return '/'
  if (to.meta.resource && !auth.hasPermission(to.meta.resource, 'read')) return '/'
})

export default router
```

- [ ] **Step 3: Fetch permissions on app load**

In `frontend/src/main.js`, after creating the app and before mounting, add a call to fetch permissions if already authenticated. Or better, do it inside `App.vue` on mount:

In `frontend/src/App.vue`, inside `<script setup>`, add:

```javascript
import { onMounted } from 'vue'
import { useAuthStore } from './stores/auth.js'

const auth = useAuthStore()
onMounted(async () => {
  if (auth.isAuthenticated) {
    await auth.fetchMe()
  }
})
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/stores/auth.js frontend/src/router/index.js frontend/src/App.vue
git commit -m "feat(users): frontend permission-aware auth store + route guards"
```

---

### Task 7: Frontend — Sidebar Permission Filtering

**Files:**
- Modify: `frontend/src/components/layout/AppSidebar.vue`

- [ ] **Step 1: Import auth store and filter nav items**

Replace the `<script setup>` section:

```javascript
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { RouterLink } from 'vue-router'
import { useAuthStore } from '../../stores/auth.js'

defineProps({ collapsed: Boolean })
defineEmits(['toggle'])

const route = useRoute()
const auth = useAuthStore()

const monitorItems = computed(() => {
  const items = [
    { to: '/', icon: 'pi-th-large', label: 'Dashboard', resource: 'system' },
    { to: '/services', icon: 'pi-cog', label: 'Services', resource: 'services' },
    { to: '/files', icon: 'pi-folder-open', label: 'Files', resource: 'files' },
    { to: '/network', icon: 'pi-wifi', label: 'Network', resource: 'network' },
  ]
  return items.filter(i => auth.hasPermission(i.resource, 'read'))
})

const manageItems = computed(() => {
  const items = [
    { to: '/scripts', icon: 'pi-code', label: 'Scripts', resource: 'scripts' },
    { to: '/crontab', icon: 'pi-clock', label: 'Crontab', resource: 'crontab' },
    { to: '/logs', icon: 'pi-list', label: 'Logs', resource: 'logs' },
  ]
  return items.filter(i => auth.hasPermission(i.resource, 'read'))
})
```

- [ ] **Step 2: Replace static nav with dynamic rendering**

Replace the `<nav>` section:

```html
<nav class="nav">
  <div class="nav-section" v-if="monitorItems.length > 0">
    <span class="nav-section-label">MONITOR</span>
    <RouterLink v-for="item in monitorItems" :key="item.to"
      class="nav-item" :to="item.to" :class="{ active: route.path === item.to }">
      <i :class="['pi', item.icon, 'nav-icon']" />
      <span class="nav-label">{{ item.label }}</span>
    </RouterLink>
  </div>

  <div class="nav-section" v-if="manageItems.length > 0">
    <span class="nav-section-label">MANAGE</span>
    <RouterLink v-for="item in manageItems" :key="item.to"
      class="nav-item" :to="item.to" :class="{ active: route.path === item.to }">
      <i :class="['pi', item.icon, 'nav-icon']" />
      <span class="nav-label">{{ item.label }}</span>
    </RouterLink>
  </div>

  <div class="nav-section" v-if="auth.isAdmin">
    <span class="nav-section-label">ADMIN</span>
    <RouterLink class="nav-item" to="/admin/users" :class="{ active: route.path === '/admin/users' }">
      <i class="pi pi-users nav-icon" />
      <span class="nav-label">Users</span>
    </RouterLink>
  </div>
</nav>
```

- [ ] **Step 3: Verify build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/layout/AppSidebar.vue
git commit -m "feat(users): sidebar dynamically shows/hides items based on permissions"
```

---

### Task 8: Frontend — Admin Users View

**Files:**
- Create: `frontend/src/views/AdminUsersView.vue`

- [ ] **Step 1: Create the admin users management view**

```vue
<!-- frontend/src/views/AdminUsersView.vue -->
<template>
  <div class="admin-users">

    <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>

    <Card class="users-card">
      <template #content>
        <div class="card-section-header">
          <i class="pi pi-users section-icon" />
          <span class="section-title">USER MANAGEMENT</span>
          <Button label="New User" icon="pi pi-plus" size="small" @click="showCreateDialog = true" />
        </div>
        <Divider class="section-divider" />

        <DataTable :value="users" size="small" :show-gridlines="false">
          <template #empty><span class="cell-empty">No users found</span></template>
          <Column field="id" header="ID" style="width: 60px" />
          <Column field="username" header="Username" />
          <Column field="role" header="Role" style="width: 120px">
            <template #body="{ data }">
              <Tag :value="data.role"
                :severity="data.role === 'admin' ? 'danger' : data.role === 'operator' ? 'warn' : 'info'" />
            </template>
          </Column>
          <Column field="is_active" header="Status" style="width: 100px">
            <template #body="{ data }">
              <Tag :value="data.is_active ? 'Active' : 'Inactive'"
                :severity="data.is_active ? 'success' : 'secondary'" />
            </template>
          </Column>
          <Column field="created_at" header="Created" style="width: 160px">
            <template #body="{ data }">
              <span class="cell-meta">{{ formatDate(data.created_at) }}</span>
            </template>
          </Column>
          <Column header="Actions" style="width: 160px">
            <template #body="{ data }">
              <div class="action-btns">
                <Button icon="pi pi-pencil" size="small" text @click="editUser(data)" />
                <Button icon="pi pi-trash" size="small" text severity="danger"
                  :disabled="data.username === auth.username"
                  @click="confirmDelete(data)" />
              </div>
            </template>
          </Column>
        </DataTable>
      </template>
    </Card>

    <!-- Create dialog -->
    <Dialog v-model:visible="showCreateDialog" header="Create User" :modal="true" style="width: 400px">
      <div class="form-grid">
        <label>Username</label>
        <InputText v-model="newUser.username" />
        <label>Password</label>
        <Password v-model="newUser.password" :feedback="false" toggleMask />
        <label>Role</label>
        <Select v-model="newUser.role" :options="roleOptions" />
      </div>
      <template #footer>
        <Button label="Cancel" text @click="showCreateDialog = false" />
        <Button label="Create" @click="createUser" />
      </template>
    </Dialog>

    <!-- Edit dialog -->
    <Dialog v-model:visible="showEditDialog" header="Edit User" :modal="true" style="width: 400px">
      <div class="form-grid">
        <label>Username</label>
        <InputText :model-value="editingUser?.username" disabled />
        <label>Role</label>
        <Select v-model="editForm.role" :options="roleOptions" />
        <label>Active</label>
        <ToggleSwitch v-model="editForm.is_active" />
        <label>New Password (optional)</label>
        <Password v-model="editForm.password" :feedback="false" toggleMask />
      </div>
      <template #footer>
        <Button label="Cancel" text @click="showEditDialog = false" />
        <Button label="Save" @click="saveUser" />
      </template>
    </Dialog>

    <ConfirmDialog />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import Message from 'primevue/message'
import Card from 'primevue/card'
import Divider from 'primevue/divider'
import Tag from 'primevue/tag'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Select from 'primevue/select'
import ToggleSwitch from 'primevue/toggleswitch'
import ConfirmDialog from 'primevue/confirmdialog'
import { useConfirm } from 'primevue/useconfirm'
import { useToast } from 'primevue/usetoast'
import { useAuthStore } from '../stores/auth.js'
import api from '../api/client.js'

const auth = useAuthStore()
const confirm = useConfirm()
const toast = useToast()

const users = ref([])
const error = ref('')
const roleOptions = ['admin', 'operator', 'readonly']

const showCreateDialog = ref(false)
const newUser = ref({ username: '', password: '', role: 'readonly' })

const showEditDialog = ref(false)
const editingUser = ref(null)
const editForm = ref({ role: '', is_active: true, password: '' })

function formatDate(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleDateString()
}

async function loadUsers() {
  try {
    const { data } = await api.get('/admin/users')
    users.value = data
    error.value = ''
  } catch {
    error.value = 'Failed to load users'
  }
}

async function createUser() {
  try {
    await api.post('/admin/users', newUser.value)
    showCreateDialog.value = false
    newUser.value = { username: '', password: '', role: 'readonly' }
    toast.add({ severity: 'success', summary: 'User created', life: 3000 })
    await loadUsers()
  } catch (e) {
    toast.add({ severity: 'error', summary: e.response?.data?.detail || 'Error', life: 5000 })
  }
}

function editUser(user) {
  editingUser.value = user
  editForm.value = { role: user.role, is_active: user.is_active, password: '' }
  showEditDialog.value = true
}

async function saveUser() {
  try {
    const payload = { role: editForm.value.role, is_active: editForm.value.is_active }
    if (editForm.value.password) payload.password = editForm.value.password
    await api.patch(`/admin/users/${editingUser.value.id}`, payload)
    showEditDialog.value = false
    toast.add({ severity: 'success', summary: 'User updated', life: 3000 })
    await loadUsers()
  } catch (e) {
    toast.add({ severity: 'error', summary: e.response?.data?.detail || 'Error', life: 5000 })
  }
}

function confirmDelete(user) {
  confirm.require({
    message: `Delete user "${user.username}"? This cannot be undone.`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: async () => {
      try {
        await api.delete(`/admin/users/${user.id}`)
        toast.add({ severity: 'success', summary: 'User deleted', life: 3000 })
        await loadUsers()
      } catch (e) {
        toast.add({ severity: 'error', summary: e.response?.data?.detail || 'Error', life: 5000 })
      }
    },
  })
}

onMounted(loadUsers)
</script>

<style scoped>
.admin-users { display: flex; flex-direction: column; gap: 16px; }
:deep(.users-card .p-card-body) { padding: 0; }
:deep(.users-card .p-card-content) { padding: 14px 16px; }
.card-section-header { display: flex; align-items: center; gap: 8px; padding-bottom: 2px; }
.section-icon { font-size: 12px; color: var(--brand-orange); flex-shrink: 0; }
.section-title { font-family: var(--font-mono); font-size: var(--text-2xs); letter-spacing: 2px; text-transform: uppercase; color: var(--p-text-muted-color); flex: 1; }
.section-divider { margin: 10px 0 !important; }
.cell-meta { font-size: var(--text-xs); color: var(--p-text-muted-color); }
.cell-empty { font-size: var(--text-sm); color: var(--p-text-muted-color); }
.action-btns { display: flex; gap: 4px; }
.form-grid { display: grid; grid-template-columns: auto 1fr; gap: 12px 16px; align-items: center; }
.form-grid label { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-muted-color); text-transform: uppercase; letter-spacing: 1px; }
</style>
```

- [ ] **Step 2: Verify build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/AdminUsersView.vue
git commit -m "feat(users): add AdminUsersView with CRUD, role assignment, activation toggle"
```

---

### Task 9: Run Full Test Suite

**Files:** None (validation only)

- [ ] **Step 1: Run all backend tests**

```bash
pytest -v
```

Expected: All tests PASS (existing + new permission + admin tests).

- [ ] **Step 2: Run frontend build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds.

- [ ] **Step 3: Final commit if any fixups needed**

Only if tests revealed issues that required fixes.
