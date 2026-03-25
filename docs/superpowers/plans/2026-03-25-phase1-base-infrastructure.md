# ServerDash Phase 1 — Base Infrastructure + System Overview

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a working FastAPI + Vue 3 dashboard with JWT auth (3 roles), HTTPS, SQLite, and a live System Overview page (CPU/RAM/disk/uptime polling every 5s).

**Architecture:** FastAPI serves both the REST API and the Vue 3 SPA (built as static files into `backend/static/`). SQLite stores users and roles. Vue 3 polls `/api/system/metrics` every 5s and renders metric cards. Authentication uses JWT access tokens (15min) + refresh tokens (7 days via httpOnly cookie).

**Tech Stack:** Python 3.11+ · FastAPI · SQLAlchemy · SQLite · python-jose · bcrypt · psutil · Vue 3 · Vite · Pinia · Vue Router · Vitest · pytest · httpx

**Spec:** `docs/superpowers/specs/2026-03-25-server-dashboard-design.md`

---

## File Map

```
server_dashboard/
├── backend/
│   ├── main.py                        # FastAPI app, HTTPS, mounts static files, includes routers
│   ├── config.py                      # Settings via env vars: JWT_SECRET, DB_PATH, CERT paths
│   ├── database.py                    # SQLAlchemy engine, session factory, Base
│   ├── models/
│   │   └── user.py                    # User ORM model: id, username, hashed_password, role
│   ├── schemas/
│   │   ├── auth.py                    # Pydantic: LoginRequest, TokenResponse, UserOut
│   │   └── system.py                  # Pydantic: SystemMetrics
│   ├── routers/
│   │   ├── auth.py                    # POST /api/auth/login, /api/auth/refresh, /api/auth/logout
│   │   └── system.py                  # GET /api/system/metrics
│   ├── services/
│   │   ├── auth_service.py            # hash_password, verify_password, create_token, decode_token
│   │   └── system_service.py          # get_metrics() using psutil
│   ├── dependencies.py                # get_current_user(), require_role() FastAPI deps
│   ├── scripts/
│   │   ├── init_db.py                 # Create tables + seed admin user
│   │   └── generate_cert.py           # Generate self-signed TLS cert + key
│   └── requirements.txt
├── frontend/
│   ├── package.json
│   ├── vite.config.js                 # Build output → ../backend/static/
│   ├── vitest.config.js
│   ├── index.html
│   └── src/
│       ├── main.js                    # Mount app, use router + pinia
│       ├── App.vue                    # Root component: RouterView inside layout
│       ├── router/
│       │   └── index.js               # /login (public), / (requires auth → DashboardView)
│       ├── stores/
│       │   └── auth.js                # Pinia: token, user, role, login(), logout(), refresh()
│       ├── composables/
│       │   └── usePolling.js          # usePolling(fn, intervalMs) — starts/stops on mount/unmount
│       ├── api/
│       │   └── client.js              # axios instance with baseURL, JWT header, refresh interceptor
│       ├── views/
│       │   ├── LoginView.vue          # Login form, calls auth store
│       │   └── DashboardView.vue      # System overview, uses usePolling + MetricCard
│       ├── components/
│       │   ├── layout/
│       │   │   ├── AppSidebar.vue     # Collapsable sidebar, nav links, role-aware
│       │   │   └── AppHeader.vue      # Logo, page title, user avatar, theme toggle
│       │   └── dashboard/
│       │       ├── MetricCard.vue     # Single metric display: label, value, progress bar, color
│       │       └── UptimeDisplay.vue  # Formats uptime seconds into "Xd Xh Xm"
│       └── assets/
│           └── style.css              # CSS custom properties: --bg, --surface, --accent, --text
├── tests/
│   ├── conftest.py                    # pytest fixtures: test client, test DB, seeded admin user
│   ├── test_auth.py                   # Auth endpoint tests
│   ├── test_system.py                 # System metrics endpoint tests
│   └── test_dependencies.py           # JWT decode, role enforcement tests
└── .env.example                       # JWT_SECRET, DB_PATH, CERT_FILE, KEY_FILE, PORT
```

---

## Task 1: Project Scaffold & Dependencies

**Files:**
- Create: `backend/requirements.txt`
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/vitest.config.js`
- Create: `frontend/index.html`
- Create: `.env.example`
- Create: `.gitignore`

- [ ] **Step 1: Create backend requirements file**

```
# backend/requirements.txt
fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy==2.0.35
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
psutil==6.0.0
httpx==0.27.2
pytest==8.3.3
pytest-asyncio==0.24.0
python-dotenv==1.0.1
pydantic-settings==2.5.2
```

- [ ] **Step 2: Create frontend package.json**

```json
{
  "name": "serverdash-frontend",
  "version": "0.1.0",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "vue": "^3.5.0",
    "vue-router": "^4.4.0",
    "pinia": "^2.2.0",
    "axios": "^1.7.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.1.0",
    "vite": "^5.4.0",
    "vitest": "^2.1.0",
    "@vue/test-utils": "^2.4.0",
    "jsdom": "^25.0.0"
  }
}
```

- [ ] **Step 3: Create vite.config.js**

```js
// frontend/vite.config.js
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  build: {
    outDir: '../backend/static',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': {
        target: 'https://localhost:8443',
        secure: false,
      }
    }
  }
})
```

- [ ] **Step 4: Create vitest.config.js**

```js
// frontend/vitest.config.js
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    globals: true,
  }
})
```

- [ ] **Step 5: Create frontend/index.html**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>ServerDash</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.js"></script>
  </body>
</html>
```

- [ ] **Step 6: Create .env.example**

```
# .env.example — copy to .env and fill in values
JWT_SECRET=change-me-to-a-long-random-string
DB_PATH=./data/serverdash.db
CERT_FILE=./certs/cert.pem
KEY_FILE=./certs/key.pem
PORT=8443
ADMIN_USERNAME=admin
ADMIN_PASSWORD=changeme
```

- [ ] **Step 7: Create .gitignore**

```
# .gitignore
.env
data/
certs/
backend/static/
frontend/node_modules/
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 8: Install dependencies**

```bash
cd backend && pip install -r requirements.txt
cd ../frontend && npm install
```

- [ ] **Step 9: Commit scaffold**

```bash
git add .
git commit -m "chore: project scaffold — backend deps and frontend vite setup"
```

---

## Task 2: Database Setup + User Model

**Files:**
- Create: `backend/config.py`
- Create: `backend/database.py`
- Create: `backend/models/user.py`
- Create: `backend/models/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.models.user import User

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)
```

```python
# tests/test_models.py
from backend.models.user import User, UserRole

def test_create_user(db_session):
    user = User(username="alice", hashed_password="hash", role=UserRole.admin)
    db_session.add(user)
    db_session.commit()
    found = db_session.query(User).filter_by(username="alice").first()
    assert found is not None
    assert found.role == UserRole.admin

def test_user_roles_are_valid():
    assert set(r.value for r in UserRole) == {"admin", "operator", "readonly"}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/crt/server_dashboard
pytest tests/test_models.py -v
```
Expected: `ERROR` — `backend.database` not found.

- [ ] **Step 3: Implement config, database, and user model**

```python
# backend/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    jwt_secret: str = "dev-secret-change-in-production"
    db_path: str = "./data/serverdash.db"
    cert_file: str = "./certs/cert.pem"
    key_file: str = "./certs/key.pem"
    port: int = 8443
    admin_username: str = "admin"
    admin_password: str = "changeme"

    class Config:
        env_file = ".env"

settings = Settings()
```

```python
# backend/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from backend.config import settings
import os

os.makedirs(os.path.dirname(settings.db_path), exist_ok=True)

engine = create_engine(f"sqlite:///{settings.db_path}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

```python
# backend/models/__init__.py
from backend.models.user import User
```

```python
# backend/models/user.py
import enum
from sqlalchemy import Column, Integer, String, Enum
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_models.py -v
```
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/config.py backend/database.py backend/models/ tests/
git commit -m "feat: database setup and User model with roles"
```

---

## Task 3: Auth Service (JWT + bcrypt)

**Files:**
- Create: `backend/schemas/auth.py`
- Create: `backend/schemas/__init__.py`
- Create: `backend/services/auth_service.py`
- Create: `backend/services/__init__.py`
- Create: `tests/test_auth_service.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_auth_service.py
import pytest
from backend.services.auth_service import (
    hash_password, verify_password, create_access_token, decode_token
)

def test_hash_and_verify_password():
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)

def test_create_and_decode_access_token():
    token = create_access_token(user_id=1, username="alice", role="admin")
    payload = decode_token(token)
    assert payload["sub"] == "1"
    assert payload["username"] == "alice"
    assert payload["role"] == "admin"

def test_decode_invalid_token_raises():
    with pytest.raises(Exception):
        decode_token("not.a.real.token")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_auth_service.py -v
```
Expected: `ERROR` — `backend.services.auth_service` not found.

- [ ] **Step 3: Implement auth service and schemas**

```python
# backend/schemas/__init__.py
```

```python
# backend/schemas/auth.py
from pydantic import BaseModel
from backend.models.user import UserRole

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserOut(BaseModel):
    id: int
    username: str
    role: UserRole

    class Config:
        from_attributes = True
```

```python
# backend/services/__init__.py
```

```python
# backend/services/auth_service.py
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from backend.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ACCESS_TOKEN_EXPIRE_MINUTES = 15
ALGORITHM = "HS256"

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(user_id: int, username: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_auth_service.py -v
```
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/schemas/ backend/services/auth_service.py backend/services/__init__.py tests/test_auth_service.py
git commit -m "feat: auth service — bcrypt password hashing and JWT creation/decoding"
```

---

## Task 4: Auth Dependencies (JWT Middleware)

**Files:**
- Create: `backend/dependencies.py`
- Create: `tests/test_dependencies.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_dependencies.py
import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException
from backend.dependencies import get_current_user, require_role
from backend.services.auth_service import create_access_token
from backend.models.user import User, UserRole

def make_mock_user(role: UserRole) -> User:
    user = MagicMock(spec=User)
    user.id = 1
    user.username = "alice"
    user.role = role
    return user

def test_require_role_passes_when_role_matches():
    user = make_mock_user(UserRole.admin)
    checker = require_role("admin")
    result = checker(current_user=user)
    assert result == user

def test_require_role_raises_when_role_insufficient():
    user = make_mock_user(UserRole.readonly)
    checker = require_role("admin")
    with pytest.raises(HTTPException) as exc:
        checker(current_user=user)
    assert exc.value.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_dependencies.py -v
```
Expected: `ERROR` — `backend.dependencies` not found.

- [ ] **Step 3: Implement dependencies**

```python
# backend/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.services.auth_service import decode_token
from backend.models.user import User, UserRole

bearer_scheme = HTTPBearer()

ROLE_HIERARCHY = {
    UserRole.readonly: 0,
    UserRole.operator: 1,
    UserRole.admin: 2,
}

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = decode_token(credentials.credentials)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user

def require_role(minimum_role: str):
    def checker(current_user: User = Depends(get_current_user)) -> User:
        user_level = ROLE_HIERARCHY.get(current_user.role, -1)
        required_level = ROLE_HIERARCHY.get(UserRole(minimum_role), 999)
        if user_level < required_level:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user
    return checker
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_dependencies.py -v
```
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/dependencies.py tests/test_dependencies.py
git commit -m "feat: JWT dependency injection with role hierarchy enforcement"
```

---

## Task 5: Auth Router

**Files:**
- Create: `backend/routers/auth.py`
- Create: `backend/routers/__init__.py`
- Create: `tests/test_auth.py`
- Update: `tests/conftest.py`

- [ ] **Step 1: Update conftest with HTTP test client fixture**

Add to `tests/conftest.py`:

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base, get_db
from backend.models.user import User, UserRole
from backend.services.auth_service import hash_password

@pytest.fixture
def test_app():
    from backend.main import app
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # seed admin user
    db = TestingSession()
    db.add(User(username="admin", hashed_password=hash_password("adminpass"), role=UserRole.admin))
    db.commit()
    db.close()

    yield TestClient(app, base_url="http://test")
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
```

- [ ] **Step 2: Write the failing auth endpoint tests**

```python
# tests/test_auth.py
def test_login_success(test_app):
    response = test_app.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_login_wrong_password(test_app):
    response = test_app.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert response.status_code == 401

def test_login_unknown_user(test_app):
    response = test_app.post("/api/auth/login", json={"username": "ghost", "password": "x"})
    assert response.status_code == 401

def test_protected_route_without_token(test_app):
    response = test_app.get("/api/system/metrics")
    assert response.status_code == 403  # HTTPBearer returns 403 when no credentials

def test_protected_route_with_valid_token(test_app):
    login = test_app.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    token = login.json()["access_token"]
    response = test_app.get("/api/system/metrics", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_auth.py -v
```
Expected: `ERROR` — `backend.main` not found.

- [ ] **Step 4: Implement auth router**

Note: `/api/auth/refresh` and `/api/auth/logout` endpoints are deferred to Phase 2. Only `/api/auth/login` is implemented here.

```python
# backend/routers/__init__.py
```

```python
# backend/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.user import User
from backend.schemas.auth import LoginRequest, TokenResponse
from backend.services.auth_service import verify_password, create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == request.username).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user_id=user.id, username=user.username, role=user.role.value)
    return TokenResponse(access_token=token)
```

- [ ] **Step 5: Create minimal main.py to unblock tests**

```python
# backend/main.py
from fastapi import FastAPI
from backend.routers import auth, system

app = FastAPI(title="ServerDash")
app.include_router(auth.router)
app.include_router(system.router)
```

Also create a stub `backend/routers/system.py` so imports don't fail:

```python
# backend/routers/system.py  (stub — completed in Task 7)
from fastapi import APIRouter, Depends
from backend.dependencies import get_current_user

router = APIRouter(prefix="/api/system", tags=["system"])

@router.get("/metrics")
def get_metrics(current_user=Depends(get_current_user)):
    return {"status": "stub"}
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_auth.py -v
```
Expected: `5 passed`

- [ ] **Step 7: Commit**

```bash
git add backend/routers/ backend/main.py tests/test_auth.py tests/conftest.py
git commit -m "feat: auth router — login endpoint with JWT response"
```

---

## Task 6: System Service (psutil metrics)

**Files:**
- Create: `backend/schemas/system.py`
- Create: `backend/services/system_service.py`
- Create: `tests/test_system_service.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_system_service.py
from unittest.mock import patch, MagicMock
from backend.services.system_service import get_metrics

def test_get_metrics_returns_expected_fields():
    with patch("backend.services.system_service.psutil") as mock_psutil:
        mock_psutil.cpu_percent.return_value = 42.5
        mock_psutil.virtual_memory.return_value = MagicMock(
            total=8_000_000_000, used=5_000_000_000, percent=62.5
        )
        mock_psutil.disk_usage.return_value = MagicMock(
            total=100_000_000_000, used=40_000_000_000, percent=40.0
        )
        mock_psutil.boot_time.return_value = 1000.0
        with patch("backend.services.system_service.time") as mock_time:
            mock_time.return_value = 4600.0
            metrics = get_metrics()

    assert metrics.cpu_percent == 42.5
    assert metrics.ram_percent == 62.5
    assert metrics.disk_percent == 40.0
    assert metrics.uptime_seconds == 3600
    assert metrics.ram_total_gb > 0
    assert metrics.disk_total_gb > 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_system_service.py -v
```
Expected: `ERROR` — `backend.services.system_service` not found.

- [ ] **Step 3: Implement system service and schema**

```python
# backend/schemas/system.py
from pydantic import BaseModel
from typing import List

class SystemMetrics(BaseModel):
    cpu_percent: float
    ram_percent: float
    ram_used_gb: float
    ram_total_gb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    uptime_seconds: int
    load_average: List[float]   # 1min, 5min, 15min
    os_name: str                # e.g. "Linux 6.6.87"
```

```python
# backend/services/system_service.py
import psutil
from time import time
from backend.schemas.system import SystemMetrics

def get_metrics() -> SystemMetrics:
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    uptime = int(time() - psutil.boot_time())

    import platform
    load = [round(x, 2) for x in psutil.getloadavg()]

    return SystemMetrics(
        cpu_percent=psutil.cpu_percent(interval=0.1),
        ram_percent=ram.percent,
        ram_used_gb=round(ram.used / 1e9, 2),
        ram_total_gb=round(ram.total / 1e9, 2),
        disk_percent=disk.percent,
        disk_used_gb=round(disk.used / 1e9, 2),
        disk_total_gb=round(disk.total / 1e9, 2),
        uptime_seconds=uptime,
        load_average=load,
        os_name=f"{platform.system()} {platform.release()}",
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_system_service.py -v
```
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/schemas/system.py backend/services/system_service.py tests/test_system_service.py
git commit -m "feat: system service — CPU/RAM/disk/uptime metrics via psutil"
```

---

## Task 7: System Router

**Files:**
- Update: `backend/routers/system.py`
- Create: `tests/test_system.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_system.py
from unittest.mock import patch
from backend.schemas.system import SystemMetrics

MOCK_METRICS = SystemMetrics(
    cpu_percent=25.0, ram_percent=50.0, ram_used_gb=4.0, ram_total_gb=8.0,
    disk_percent=40.0, disk_used_gb=40.0, disk_total_gb=100.0, uptime_seconds=3600
)

def test_metrics_endpoint_returns_data(test_app):
    login = test_app.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    token = login.json()["access_token"]
    with patch("backend.routers.system.get_metrics", return_value=MOCK_METRICS):
        response = test_app.get("/api/system/metrics", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["cpu_percent"] == 25.0
    assert data["ram_percent"] == 50.0
    assert "uptime_seconds" in data

def test_metrics_endpoint_requires_auth(test_app):
    response = test_app.get("/api/system/metrics")
    assert response.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_system.py -v
```
Expected: the stub endpoint passes auth but returns `{"status": "stub"}` so `data["cpu_percent"]` will fail.

- [ ] **Step 3: Replace stub system router with real implementation**

```python
# backend/routers/system.py
from fastapi import APIRouter, Depends
from backend.dependencies import get_current_user
from backend.schemas.system import SystemMetrics
from backend.services.system_service import get_metrics

router = APIRouter(prefix="/api/system", tags=["system"])

@router.get("/metrics", response_model=SystemMetrics)
def metrics_endpoint(current_user=Depends(get_current_user)):
    return get_metrics()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_system.py -v
```
Expected: `2 passed`

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -v
```
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/system.py tests/test_system.py
git commit -m "feat: system metrics endpoint — GET /api/system/metrics"
```

---

## Task 8: FastAPI App — HTTPS + Static Files + Init Scripts

**Files:**
- Update: `backend/main.py`
- Create: `backend/scripts/generate_cert.py`
- Create: `backend/scripts/init_db.py`
- Create: `backend/scripts/__init__.py`

- [ ] **Step 1: Create scripts package init**

```bash
touch backend/scripts/__init__.py
```

- [ ] **Step 2: Create cert generation script**

```python
# backend/scripts/generate_cert.py
"""Run once: python -m backend.scripts.generate_cert"""
import os
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from datetime import datetime, timedelta, timezone
from backend.config import settings

def generate_self_signed_cert():
    os.makedirs(os.path.dirname(settings.cert_file), exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
        .sign(key, hashes.SHA256())
    )
    with open(settings.cert_file, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    with open(settings.key_file, "wb") as f:
        f.write(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption()
        ))
    print(f"Cert written to {settings.cert_file}")
    print(f"Key written to {settings.key_file}")

if __name__ == "__main__":
    generate_self_signed_cert()
```

Note: add `cryptography` to `requirements.txt`.

- [ ] **Step 3: Create DB init script**

```python
# backend/scripts/init_db.py
"""Run once: python -m backend.scripts.init_db"""
from backend.database import engine, Base, SessionLocal
from backend.models.user import User, UserRole
from backend.services.auth_service import hash_password
from backend.config import settings
import backend.models  # ensure models are registered

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
    db.close()

if __name__ == "__main__":
    init()
```

- [ ] **Step 4: Update main.py with HTTPS and static file serving**

```python
# backend/main.py
import os
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.routers import auth, system
from backend.config import settings

app = FastAPI(title="ServerDash", docs_url="/api/docs", redoc_url=None)

app.include_router(auth.router)
app.include_router(system.router)

# Serve Vue SPA (built files)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(static_dir, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        """Serve index.html for all non-API routes (Vue Router handles routing)."""
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

- [ ] **Step 5: Add cryptography to requirements.txt**

Add `cryptography==43.0.1` to `backend/requirements.txt` and run:

```bash
pip install cryptography
```

- [ ] **Step 6: Run full test suite to make sure nothing broke**

```bash
pytest tests/ -v
```
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/main.py backend/scripts/ backend/requirements.txt
git commit -m "feat: HTTPS server setup, static file serving, init scripts"
```

---

## Task 9: Vue 3 Frontend — Auth Store + API Client + Router

**Files:**
- Create: `frontend/src/main.js`
- Create: `frontend/src/App.vue`
- Create: `frontend/src/api/client.js`
- Create: `frontend/src/stores/auth.js`
- Create: `frontend/src/router/index.js`
- Create: `frontend/src/assets/style.css`

- [ ] **Step 1: Write failing tests for auth store**

```js
// frontend/src/stores/auth.test.js
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from './auth.js'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../api/client.js', () => ({
  default: {
    post: vi.fn(),
  }
}))

describe('auth store', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('starts unauthenticated', () => {
    const auth = useAuthStore()
    expect(auth.isAuthenticated).toBe(false)
    expect(auth.token).toBeNull()
  })

  it('sets token and user on successful login', async () => {
    const api = (await import('../api/client.js')).default
    api.post.mockResolvedValue({ data: { access_token: 'tok123', token_type: 'bearer' } })

    const auth = useAuthStore()
    await auth.login('admin', 'pass')
    expect(auth.token).toBe('tok123')
    expect(auth.isAuthenticated).toBe(true)
  })

  it('clears token on logout', async () => {
    const auth = useAuthStore()
    auth.token = 'tok123'
    auth.logout()
    expect(auth.token).toBeNull()
    expect(auth.isAuthenticated).toBe(false)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm test
```
Expected: FAIL — `stores/auth.js` not found.

- [ ] **Step 3: Implement API client**

```js
// frontend/src/api/client.js
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

// Attach token from store before each request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export default api
```

- [ ] **Step 4: Implement auth store**

```js
// frontend/src/stores/auth.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api/client.js'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('access_token'))
  const username = ref(localStorage.getItem('username') || null)
  const role = ref(localStorage.getItem('role') || null)

  const isAuthenticated = computed(() => !!token.value)

  async function login(usernameInput, password) {
    const { data } = await api.post('/auth/login', { username: usernameInput, password })
    token.value = data.access_token
    localStorage.setItem('access_token', data.access_token)
    // Decode role from JWT payload (base64)
    const payload = JSON.parse(atob(data.access_token.split('.')[1]))
    username.value = payload.username
    role.value = payload.role
    localStorage.setItem('username', payload.username)
    localStorage.setItem('role', payload.role)
  }

  function logout() {
    token.value = null
    username.value = null
    role.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('username')
    localStorage.removeItem('role')
  }

  return { token, username, role, isAuthenticated, login, logout }
})
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd frontend && npm test
```
Expected: `3 passed`

- [ ] **Step 6: Implement router**

```js
// frontend/src/router/index.js
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

const routes = [
  { path: '/login', component: () => import('../views/LoginView.vue'), meta: { public: true } },
  { path: '/', component: () => import('../views/DashboardView.vue'), meta: { requiresAuth: true } },
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

- [ ] **Step 7: Implement main.js and App.vue**

```js
// frontend/src/main.js
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router/index.js'
import './assets/style.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
```

```vue
<!-- frontend/src/App.vue -->
<template>
  <RouterView />
</template>
```

- [ ] **Step 8: Create global CSS with dark/light variables**

```css
/* frontend/src/assets/style.css */
:root {
  --bg: #0d1117;
  --surface: #161b22;
  --surface-2: #21262d;
  --border: #30363d;
  --text: #e6edf3;
  --text-muted: #8b949e;
  --accent-blue: #58a6ff;
  --accent-green: #3fb950;
  --accent-yellow: #d29922;
  --accent-red: #f85149;
  --sidebar-width: 220px;
  --sidebar-collapsed-width: 56px;
  --header-height: 52px;
}

[data-theme="light"] {
  --bg: #f6f8fa;
  --surface: #ffffff;
  --surface-2: #f0f2f5;
  --border: #d0d7de;
  --text: #1f2328;
  --text-muted: #656d76;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 14px;
  line-height: 1.5;
}

a { color: var(--accent-blue); text-decoration: none; }
```

- [ ] **Step 9: Commit**

```bash
cd ..
git add frontend/src/
git commit -m "feat: Vue 3 frontend — auth store, API client, router, global CSS"
```

---

## Task 10: Login View

**Files:**
- Create: `frontend/src/views/LoginView.vue`

- [ ] **Step 1: Write failing component test**

```js
// frontend/src/views/LoginView.test.js
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import LoginView from './LoginView.vue'

const mockLogin = vi.fn()
vi.mock('../stores/auth.js', () => ({
  useAuthStore: () => ({ login: mockLogin, isAuthenticated: false })
}))

const router = createRouter({ history: createWebHistory(), routes: [
  { path: '/login', component: LoginView },
  { path: '/', component: { template: '<div>home</div>' } }
]})

describe('LoginView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockLogin.mockReset()
  })

  it('renders username and password fields', () => {
    const wrapper = mount(LoginView, { global: { plugins: [router] } })
    expect(wrapper.find('input[type="text"]').exists()).toBe(true)
    expect(wrapper.find('input[type="password"]').exists()).toBe(true)
  })

  it('calls login with form values on submit', async () => {
    mockLogin.mockResolvedValue(undefined)
    const wrapper = mount(LoginView, { global: { plugins: [router] } })
    await wrapper.find('input[type="text"]').setValue('admin')
    await wrapper.find('input[type="password"]').setValue('pass')
    await wrapper.find('form').trigger('submit')
    expect(mockLogin).toHaveBeenCalledWith('admin', 'pass')
  })

  it('shows error message on login failure', async () => {
    mockLogin.mockRejectedValue(new Error('Invalid credentials'))
    const wrapper = mount(LoginView, { global: { plugins: [router] } })
    await wrapper.find('form').trigger('submit')
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Invalid credentials')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm test
```
Expected: FAIL — `LoginView.vue` not found.

- [ ] **Step 3: Implement LoginView**

```vue
<!-- frontend/src/views/LoginView.vue -->
<template>
  <div class="login-page">
    <div class="login-card">
      <h1 class="login-title">ServerDash</h1>
      <p class="login-subtitle">Sign in to continue</p>
      <form @submit.prevent="handleLogin">
        <div class="field">
          <label>Username</label>
          <input type="text" v-model="username" autocomplete="username" required />
        </div>
        <div class="field">
          <label>Password</label>
          <input type="password" v-model="password" autocomplete="current-password" required />
        </div>
        <p v-if="error" class="error">{{ error }}</p>
        <button type="submit" :disabled="loading">
          {{ loading ? 'Signing in…' : 'Sign in' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

const auth = useAuthStore()
const router = useRouter()
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    router.push('/')
  } catch {
    error.value = 'Invalid credentials'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg);
}
.login-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 40px;
  width: 360px;
}
.login-title { font-size: 24px; margin-bottom: 4px; }
.login-subtitle { color: var(--text-muted); margin-bottom: 28px; }
.field { margin-bottom: 16px; }
.field label { display: block; margin-bottom: 6px; font-size: 13px; color: var(--text-muted); }
.field input {
  width: 100%; padding: 8px 12px;
  background: var(--surface-2); border: 1px solid var(--border);
  border-radius: 6px; color: var(--text); font-size: 14px;
}
.field input:focus { outline: none; border-color: var(--accent-blue); }
.error { color: var(--accent-red); font-size: 13px; margin-bottom: 12px; }
button {
  width: 100%; padding: 10px;
  background: var(--accent-blue); color: #fff;
  border: none; border-radius: 6px; font-size: 14px; cursor: pointer;
}
button:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npm test
```
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
cd ..
git add frontend/src/views/LoginView.vue frontend/src/views/LoginView.test.js
git commit -m "feat: login view with form validation and error handling"
```

---

## Task 11: Layout Components (Sidebar + Header)

**Files:**
- Create: `frontend/src/components/layout/AppSidebar.vue`
- Create: `frontend/src/components/layout/AppHeader.vue`
- Update: `frontend/src/App.vue`

- [ ] **Step 1: Write failing component tests**

```js
// frontend/src/components/layout/AppSidebar.test.js
import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import AppSidebar from './AppSidebar.vue'

describe('AppSidebar', () => {
  it('renders nav links', () => {
    const wrapper = mount(AppSidebar, { props: { collapsed: false } })
    expect(wrapper.text()).toContain('Dashboard')
  })

  it('applies collapsed class when collapsed prop is true', () => {
    const wrapper = mount(AppSidebar, { props: { collapsed: true } })
    expect(wrapper.classes()).toContain('collapsed')
  })

  it('emits toggle event when toggle button clicked', async () => {
    const wrapper = mount(AppSidebar, { props: { collapsed: false } })
    await wrapper.find('.toggle-btn').trigger('click')
    expect(wrapper.emitted('toggle')).toBeTruthy()
  })
})
```

```js
// frontend/src/components/layout/AppHeader.test.js
import { mount } from '@vue/test-utils'
import { describe, it, expect, vi } from 'vitest'
import AppHeader from './AppHeader.vue'

vi.mock('../../stores/auth.js', () => ({
  useAuthStore: () => ({ username: 'admin', role: 'admin', logout: vi.fn() })
}))

describe('AppHeader', () => {
  it('displays the username', () => {
    const wrapper = mount(AppHeader, { props: { pageTitle: 'Dashboard' } })
    expect(wrapper.text()).toContain('admin')
  })

  it('displays the page title', () => {
    const wrapper = mount(AppHeader, { props: { pageTitle: 'System Overview' } })
    expect(wrapper.text()).toContain('System Overview')
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npm test
```
Expected: FAIL — components not found.

- [ ] **Step 3: Implement AppSidebar**

```vue
<!-- frontend/src/components/layout/AppSidebar.vue -->
<template>
  <aside :class="['sidebar', { collapsed }]">
    <button class="toggle-btn" @click="$emit('toggle')" title="Toggle sidebar">
      <span class="icon">☰</span>
    </button>
    <nav>
      <RouterLink to="/" class="nav-item" title="Dashboard">
        <span class="icon">⬛</span>
        <span class="label">Dashboard</span>
      </RouterLink>
    </nav>
  </aside>
</template>

<script setup>
defineProps({ collapsed: Boolean })
defineEmits(['toggle'])
</script>

<style scoped>
.sidebar {
  width: var(--sidebar-width);
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  height: 100vh;
  position: fixed;
  top: 0; left: 0;
  transition: width 0.2s ease;
  z-index: 100;
  overflow: hidden;
}
.sidebar.collapsed { width: var(--sidebar-collapsed-width); }
.toggle-btn {
  background: none; border: none; color: var(--text-muted);
  padding: 16px; cursor: pointer; font-size: 16px; text-align: left;
  width: 100%;
}
.toggle-btn:hover { color: var(--text); }
.nav-item {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 16px; color: var(--text-muted);
  border-radius: 6px; margin: 2px 8px;
  transition: background 0.15s, color 0.15s;
  white-space: nowrap;
}
.nav-item:hover, .nav-item.router-link-active {
  background: var(--surface-2); color: var(--text);
}
.sidebar.collapsed .label { display: none; }
.icon { font-size: 16px; flex-shrink: 0; }
</style>
```

- [ ] **Step 4: Implement AppHeader**

```vue
<!-- frontend/src/components/layout/AppHeader.vue -->
<template>
  <header class="header">
    <span class="page-title">{{ pageTitle }}</span>
    <div class="header-right">
      <button class="theme-btn" @click="toggleTheme" :title="isDark ? 'Switch to light' : 'Switch to dark'">
        {{ isDark ? '☀️' : '🌙' }}
      </button>
      <span class="username">{{ auth.username }}</span>
      <button class="logout-btn" @click="handleLogout">Sign out</button>
    </div>
  </header>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth.js'

defineProps({ pageTitle: String })

const auth = useAuthStore()
const router = useRouter()
const isDark = ref(document.documentElement.getAttribute('data-theme') !== 'light')

function toggleTheme() {
  isDark.value = !isDark.value
  document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
}

function handleLogout() {
  auth.logout()
  router.push('/login')
}

// Apply saved theme on mount
const savedTheme = localStorage.getItem('theme') || 'dark'
document.documentElement.setAttribute('data-theme', savedTheme)
isDark.value = savedTheme !== 'light'
</script>

<style scoped>
.header {
  height: var(--header-height);
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  position: fixed;
  top: 0;
  right: 0;
  left: var(--sidebar-width);
  transition: left 0.2s ease;
  z-index: 99;
}
.page-title { font-weight: 600; font-size: 15px; }
.header-right { display: flex; align-items: center; gap: 12px; }
.username { color: var(--text-muted); font-size: 13px; }
.theme-btn, .logout-btn {
  background: none; border: 1px solid var(--border);
  color: var(--text-muted); border-radius: 6px;
  padding: 4px 10px; cursor: pointer; font-size: 12px;
}
.theme-btn:hover, .logout-btn:hover { color: var(--text); border-color: var(--text-muted); }
</style>
```

- [ ] **Step 5: Update App.vue with layout shell**

```vue
<!-- frontend/src/App.vue -->
<template>
  <template v-if="isAuthRoute">
    <RouterView />
  </template>
  <template v-else>
    <AppSidebar :collapsed="sidebarCollapsed" @toggle="sidebarCollapsed = !sidebarCollapsed" />
    <div :class="['main-content', { 'sidebar-collapsed': sidebarCollapsed }]">
      <AppHeader :page-title="pageTitle" />
      <div class="page-body">
        <RouterView />
      </div>
    </div>
  </template>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import AppSidebar from './components/layout/AppSidebar.vue'
import AppHeader from './components/layout/AppHeader.vue'

const route = useRoute()
const sidebarCollapsed = ref(false)
const isAuthRoute = computed(() => route.meta.public)
const pageTitle = computed(() => route.meta.title || 'Dashboard')
</script>

<style>
.main-content {
  margin-left: var(--sidebar-width);
  padding-top: var(--header-height);
  min-height: 100vh;
  transition: margin-left 0.2s ease;
}
.main-content.sidebar-collapsed {
  margin-left: var(--sidebar-collapsed-width);
}
.page-body { padding: 24px; }
</style>
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
cd frontend && npm test
```
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
cd ..
git add frontend/src/components/ frontend/src/App.vue
git commit -m "feat: layout shell — collapsable sidebar and header with theme toggle"
```

---

## Task 12: Polling Composable + Metric Components + Dashboard View

**Files:**
- Create: `frontend/src/composables/usePolling.js`
- Create: `frontend/src/components/dashboard/MetricCard.vue`
- Create: `frontend/src/components/dashboard/UptimeDisplay.vue`
- Create: `frontend/src/views/DashboardView.vue`

- [ ] **Step 1: Write failing tests**

```js
// frontend/src/composables/usePolling.test.js
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { usePolling } from './usePolling.js'

describe('usePolling', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('calls fn immediately on start', () => {
    const fn = vi.fn().mockResolvedValue(undefined)
    const { start, stop } = usePolling(fn, 5000)
    start()
    expect(fn).toHaveBeenCalledTimes(1)
    stop()
  })

  it('calls fn again after interval', async () => {
    const fn = vi.fn().mockResolvedValue(undefined)
    const { start, stop } = usePolling(fn, 5000)
    start()
    vi.advanceTimersByTime(5000)
    expect(fn).toHaveBeenCalledTimes(2)
    stop()
  })

  it('stops calling fn after stop()', async () => {
    const fn = vi.fn().mockResolvedValue(undefined)
    const { start, stop } = usePolling(fn, 5000)
    start()
    stop()
    vi.advanceTimersByTime(10000)
    expect(fn).toHaveBeenCalledTimes(1)
  })
})
```

```js
// frontend/src/components/dashboard/MetricCard.test.js
import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import MetricCard from './MetricCard.vue'

describe('MetricCard', () => {
  it('renders label and value', () => {
    const wrapper = mount(MetricCard, {
      props: { label: 'CPU', value: 42.5, unit: '%', color: 'blue' }
    })
    expect(wrapper.text()).toContain('CPU')
    expect(wrapper.text()).toContain('42.5')
  })

  it('renders progress bar with correct width', () => {
    const wrapper = mount(MetricCard, {
      props: { label: 'RAM', value: 75, unit: '%', color: 'green' }
    })
    const bar = wrapper.find('.bar-fill')
    expect(bar.attributes('style')).toContain('75%')
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npm test
```
Expected: FAIL.

- [ ] **Step 3: Implement usePolling composable**

```js
// frontend/src/composables/usePolling.js
export function usePolling(fn, intervalMs) {
  let timer = null

  function start() {
    fn()
    timer = setInterval(fn, intervalMs)
  }

  function stop() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  return { start, stop }
}
```

- [ ] **Step 4: Implement MetricCard component**

```vue
<!-- frontend/src/components/dashboard/MetricCard.vue -->
<template>
  <div class="metric-card">
    <div class="metric-label">{{ label }}</div>
    <div class="metric-value">{{ value }}<span class="unit">{{ unit }}</span></div>
    <div class="bar-track">
      <div
        class="bar-fill"
        :style="{ width: `${value}%`, background: colorVar }"
      ></div>
    </div>
    <div v-if="subtitle" class="metric-subtitle">{{ subtitle }}</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  label: String,
  value: Number,
  unit: { type: String, default: '%' },
  color: { type: String, default: 'blue' },
  subtitle: String,
})

const colorVar = computed(() => ({
  blue: 'var(--accent-blue)',
  green: 'var(--accent-green)',
  yellow: 'var(--accent-yellow)',
  red: 'var(--accent-red)',
}[props.color] || 'var(--accent-blue)'))
</script>

<style scoped>
.metric-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 20px;
}
.metric-label { font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }
.metric-value { font-size: 32px; font-weight: 700; margin-bottom: 12px; }
.unit { font-size: 16px; color: var(--text-muted); margin-left: 2px; }
.bar-track { height: 6px; background: var(--surface-2); border-radius: 3px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 3px; transition: width 0.4s ease; }
.metric-subtitle { font-size: 12px; color: var(--text-muted); margin-top: 8px; }
</style>
```

- [ ] **Step 5: Implement UptimeDisplay component**

```vue
<!-- frontend/src/components/dashboard/UptimeDisplay.vue -->
<template>
  <div class="metric-card">
    <div class="metric-label">Uptime</div>
    <div class="metric-value uptime-value">{{ formatted }}</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({ seconds: Number })
const formatted = computed(() => {
  const s = props.seconds || 0
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  return [d && `${d}d`, h && `${h}h`, `${m}m`].filter(Boolean).join(' ') || '0m'
})
</script>

<style scoped>
.metric-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; padding: 20px;
}
.metric-label { font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }
.uptime-value { font-size: 28px; font-weight: 700; }
</style>
```

- [ ] **Step 6: Implement DashboardView**

```vue
<!-- frontend/src/views/DashboardView.vue -->
<template>
  <div class="dashboard">
    <p v-if="error" class="error-banner">{{ error }}</p>
    <div class="metrics-grid">
      <MetricCard label="CPU" :value="metrics.cpu_percent" unit="%" color="blue" />
      <MetricCard
        label="RAM"
        :value="metrics.ram_percent"
        unit="%"
        color="green"
        :subtitle="`${metrics.ram_used_gb} / ${metrics.ram_total_gb} GB`"
      />
      <MetricCard
        label="Disk"
        :value="metrics.disk_percent"
        unit="%"
        color="yellow"
        :subtitle="`${metrics.disk_used_gb} / ${metrics.disk_total_gb} GB`"
      />
      <UptimeDisplay :seconds="metrics.uptime_seconds" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import MetricCard from '../components/dashboard/MetricCard.vue'
import UptimeDisplay from '../components/dashboard/UptimeDisplay.vue'
import { usePolling } from '../composables/usePolling.js'
import api from '../api/client.js'

const metrics = ref({
  cpu_percent: 0, ram_percent: 0, ram_used_gb: 0, ram_total_gb: 0,
  disk_percent: 0, disk_used_gb: 0, disk_total_gb: 0, uptime_seconds: 0
})
const error = ref('')

async function fetchMetrics() {
  try {
    const { data } = await api.get('/system/metrics')
    metrics.value = data
    error.value = ''
  } catch {
    error.value = 'Failed to fetch metrics'
  }
}

const { start, stop } = usePolling(fetchMetrics, 5000)
onMounted(start)
onUnmounted(stop)
</script>

<style scoped>
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}
.error-banner {
  background: var(--accent-red); color: #fff;
  padding: 10px 16px; border-radius: 6px; margin-bottom: 16px;
}
</style>
```

- [ ] **Step 7: Run all tests to verify they pass**

```bash
cd frontend && npm test
```
Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
cd ..
git add frontend/src/composables/ frontend/src/components/dashboard/ frontend/src/views/DashboardView.vue
git commit -m "feat: dashboard view — metric cards with 5s polling composable"
```

---

## Task 13: Build + Integration Smoke Test

**Files:** no new files — wires everything together.

- [ ] **Step 1: Build the frontend**

```bash
cd frontend && npm run build
```
Expected: `dist` written to `../backend/static/`. No errors.

- [ ] **Step 2: Generate HTTPS cert and initialize DB**

```bash
cd ..
cp .env.example .env
# Edit .env: set JWT_SECRET to a long random string
python -m backend.scripts.generate_cert
python -m backend.scripts.init_db
```
Expected:
```
Cert written to ./certs/cert.pem
Admin user 'admin' created.
```

- [ ] **Step 3: Run full backend test suite**

```bash
pytest tests/ -v
```
Expected: all tests pass.

- [ ] **Step 4: Start the server**

```bash
python -m backend.main
```
Expected: `Uvicorn running on https://0.0.0.0:8443`

- [ ] **Step 5: Smoke test in browser**

Open `https://localhost:8443` (accept the self-signed cert warning).

- Login page appears ✓
- Login with `admin` / `changeme` ✓
- Dashboard loads with CPU, RAM, Disk, Uptime cards ✓
- Metrics update every 5 seconds ✓
- Sidebar collapse button works ✓
- Dark/light toggle works ✓

- [ ] **Step 6: Commit**

```bash
git add .
git commit -m "feat: Phase 1 complete — FastAPI + Vue 3 dashboard with JWT auth and system metrics"
```

---

## Phase 1 Done ✓

At this point you have:
- FastAPI backend with HTTPS, JWT auth, 3 roles, SQLite
- Vue 3 SPA with login, collapsable sidebar, dark/light theme
- System Overview dashboard with live CPU/RAM/disk/uptime (5s polling)
- Full test coverage for backend (pytest) and frontend (vitest)

**Next:** `docs/superpowers/plans/2026-03-25-phase2-services.md` — systemd service management.
