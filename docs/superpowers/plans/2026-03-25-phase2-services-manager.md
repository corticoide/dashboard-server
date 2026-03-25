# ServerDash Phase 2 — Services Manager

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a systemd services management page: list all services with status, start/stop/restart actions, and view journald logs — with role-based access control.

**Architecture:** Backend uses `subprocess` to call `systemctl` and `journalctl`. FastAPI handles REST calls at `/api/services`. Vue 3 frontend shows a filterable service table with status badges and an inline log panel. `readonly` users can view but not control services.

**Tech Stack:** Python subprocess · systemctl · journalctl · FastAPI · Vue 3 · Vitest · pytest

**Spec:** `docs/superpowers/specs/2026-03-25-server-dashboard-design.md` (Phase 2 section)

---

## File Map

```
backend/
  schemas/services.py           # ServiceInfo, ServiceLog Pydantic models
  services/services_service.py  # list_services(), get_service_logs(), control_service()
  routers/services.py           # GET /api/services/, GET /{name}/logs, POST /{name}/{action}
  main.py                       # include services router (modify)
frontend/src/
  router/index.js               # add /services route (modify)
  views/ServicesView.vue        # main page: filter bar + table + log panel
  components/services/
    StatusBadge.vue             # colored badge: active/inactive/failed/other
tests/
  test_services.py              # API integration tests
  test_services_service.py      # unit tests for service helpers
```

---

## Task 1: Backend schema + service layer

**Files:**
- Create: `backend/schemas/services.py`
- Create: `backend/services/services_service.py`

- [ ] **Step 1: Write the tests**

```python
# tests/test_services_service.py
from unittest.mock import patch
from backend.services.services_service import parse_service_line, list_services, control_service

def test_parse_service_line():
    line = "ssh.service                    loaded active running OpenBSD Secure Shell server"
    svc = parse_service_line(line)
    assert svc["name"] == "ssh.service"
    assert svc["load_state"] == "loaded"
    assert svc["active_state"] == "active"
    assert svc["sub_state"] == "running"
    assert "OpenBSD" in svc["description"]

def test_parse_service_line_inactive():
    line = "cron.service                   loaded inactive dead  Regular background program processing daemon"
    svc = parse_service_line(line)
    assert svc["active_state"] == "inactive"
    assert svc["sub_state"] == "dead"

def test_control_service_invalid_action():
    import pytest
    with pytest.raises(ValueError, match="Invalid action"):
        control_service("ssh.service", "delete")
```

- [ ] **Step 2: Run tests — expect FAIL (function not found)**

```bash
.venv/bin/pytest tests/test_services_service.py -q
```

- [ ] **Step 3: Create `backend/schemas/services.py`**

```python
from pydantic import BaseModel
from typing import List

class ServiceInfo(BaseModel):
    name: str
    load_state: str      # loaded | not-found | masked
    active_state: str    # active | inactive | failed | activating | deactivating
    sub_state: str       # running | dead | exited | ...
    description: str
    enabled: str         # enabled | disabled | static | masked | unknown

class ServiceLog(BaseModel):
    service: str
    lines: List[str]
```

- [ ] **Step 4: Create `backend/services/services_service.py`**

```python
import subprocess
from typing import List
from backend.schemas.services import ServiceInfo, ServiceLog

ALLOWED_ACTIONS = {"start", "stop", "restart", "reload"}


def parse_service_line(line: str) -> dict:
    """Parse one line from systemctl list-units output."""
    parts = line.split(None, 4)
    if len(parts) < 4:
        return {}
    return {
        "name": parts[0],
        "load_state": parts[1],
        "active_state": parts[2],
        "sub_state": parts[3],
        "description": parts[4] if len(parts) > 4 else "",
    }


def _get_enabled_map() -> dict[str, str]:
    """Returns {service_name: enabled_state} from systemctl list-unit-files."""
    try:
        result = subprocess.run(
            ["systemctl", "list-unit-files", "--type=service", "--no-pager", "--no-legend"],
            capture_output=True, text=True, timeout=10
        )
        mapping = {}
        for line in result.stdout.splitlines():
            parts = line.split(None, 2)
            if len(parts) >= 2:
                mapping[parts[0]] = parts[1]
        return mapping
    except Exception:
        return {}


def list_services() -> List[ServiceInfo]:
    """List all systemd service units."""
    try:
        result = subprocess.run(
            ["systemctl", "list-units", "--type=service", "--all",
             "--no-pager", "--no-legend", "--plain"],
            capture_output=True, text=True, timeout=15
        )
    except FileNotFoundError:
        raise RuntimeError("systemctl not found — systemd is not available on this system")

    enabled_map = _get_enabled_map()
    services = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parsed = parse_service_line(line)
        if not parsed or not parsed["name"].endswith(".service"):
            continue
        services.append(ServiceInfo(
            name=parsed["name"],
            load_state=parsed["load_state"],
            active_state=parsed["active_state"],
            sub_state=parsed["sub_state"],
            description=parsed["description"],
            enabled=enabled_map.get(parsed["name"], "unknown"),
        ))
    return services


def get_service_logs(name: str, lines: int = 100) -> ServiceLog:
    """Fetch recent journald logs for a service."""
    _validate_service_name(name)
    try:
        result = subprocess.run(
            ["journalctl", "-u", name, f"-n{lines}", "--no-pager", "--output=short"],
            capture_output=True, text=True, timeout=10
        )
        log_lines = result.stdout.splitlines()
    except FileNotFoundError:
        log_lines = ["journalctl not available on this system"]
    return ServiceLog(service=name, lines=log_lines)


def control_service(name: str, action: str) -> dict:
    """Run systemctl action on a service. Returns {'ok': True} or raises."""
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"Invalid action: {action!r}. Allowed: {ALLOWED_ACTIONS}")
    _validate_service_name(name)
    try:
        result = subprocess.run(
            ["sudo", "systemctl", action, name],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"systemctl {action} failed")
        return {"ok": True, "action": action, "service": name}
    except FileNotFoundError:
        raise RuntimeError("systemctl not found — systemd is not available")


def _validate_service_name(name: str) -> None:
    """Basic sanitization: only allow safe service name characters."""
    import re
    if not re.match(r'^[a-zA-Z0-9@._\-]+\.service$', name):
        raise ValueError(f"Invalid service name: {name!r}")
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
.venv/bin/pytest tests/test_services_service.py -q
```

- [ ] **Step 6: Commit**

```bash
git add backend/schemas/services.py backend/services/services_service.py tests/test_services_service.py
git commit -m "feat: Phase 2 services schema and service layer"
```

---

## Task 2: Services router + wire into app

**Files:**
- Create: `backend/routers/services.py`
- Modify: `backend/main.py`
- Create: `tests/test_services.py`

- [ ] **Step 1: Write API tests**

```python
# tests/test_services.py
from unittest.mock import patch
from backend.schemas.services import ServiceInfo, ServiceLog

MOCK_SERVICES = [
    ServiceInfo(name="ssh.service", load_state="loaded", active_state="active",
                sub_state="running", description="SSH Server", enabled="enabled"),
    ServiceInfo(name="cron.service", load_state="loaded", active_state="inactive",
                sub_state="dead", description="Cron daemon", enabled="enabled"),
]

def test_list_services_requires_auth(test_app):
    r = test_app.get("/api/services/")
    assert r.status_code == 403

def test_list_services_returns_list(test_app):
    login = test_app.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    token = login.json()["access_token"]
    with patch("backend.routers.services.list_services", return_value=MOCK_SERVICES):
        r = test_app.get("/api/services/", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert data[0]["name"] == "ssh.service"

def test_control_service_requires_operator(test_app):
    """readonly user cannot control services"""
    from backend.models.user import User, UserRole
    from backend.database import get_db
    from backend.services.auth_service import hash_password
    # Add a readonly user
    db = next(test_app.app.dependency_overrides[get_db]())
    db.add(User(username="viewer", hashed_password=hash_password("viewpass"), role=UserRole.readonly))
    db.commit()
    login = test_app.post("/api/auth/login", json={"username": "viewer", "password": "viewpass"})
    token = login.json()["access_token"]
    r = test_app.post("/api/services/ssh.service/restart",
                      headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403

def test_get_logs_returns_data(test_app):
    login = test_app.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    token = login.json()["access_token"]
    mock_log = ServiceLog(service="ssh.service", lines=["Mar 25 10:00:00 srv sshd: started"])
    with patch("backend.routers.services.get_service_logs", return_value=mock_log):
        r = test_app.get("/api/services/ssh.service/logs",
                         headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["service"] == "ssh.service"
```

- [ ] **Step 2: Run tests — expect FAIL (router not wired)**

```bash
.venv/bin/pytest tests/test_services.py -q
```

- [ ] **Step 3: Create `backend/routers/services.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from backend.dependencies import get_current_user, require_role
from backend.models.user import UserRole
from backend.schemas.services import ServiceInfo, ServiceLog
from backend.services.services_service import list_services, get_service_logs, control_service

router = APIRouter(prefix="/api/services", tags=["services"])


@router.get("/", response_model=List[ServiceInfo])
def get_services(user=Depends(get_current_user)):
    try:
        return list_services()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/{name}/logs", response_model=ServiceLog)
def get_logs(name: str, lines: int = 100, user=Depends(get_current_user)):
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
    user=Depends(require_role(UserRole.operator)),
):
    try:
        return control_service(name, action)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 4: Wire router into `backend/main.py`**

Add import + `app.include_router(services_router)` after the existing routers.

```python
from backend.routers.services import router as services_router
# (in create_application or directly after other include_router calls)
app.include_router(services_router)
```

- [ ] **Step 5: Run all backend tests — expect PASS**

```bash
.venv/bin/pytest tests/ -q
```

- [ ] **Step 6: Commit**

```bash
git add backend/routers/services.py backend/main.py tests/test_services.py
git commit -m "feat: Phase 2 services router and API endpoints"
```

---

## Task 3: StatusBadge component + ServicesView frontend

**Files:**
- Create: `frontend/src/components/services/StatusBadge.vue`
- Create: `frontend/src/views/ServicesView.vue`
- Modify: `frontend/src/router/index.js`

- [ ] **Step 1: Create `frontend/src/components/services/StatusBadge.vue`**

```vue
<template>
  <span class="badge" :class="stateClass">{{ state }}</span>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({ state: String })
const stateClass = computed(() => ({
  active: 'badge-active',
  inactive: 'badge-inactive',
  failed: 'badge-failed',
  activating: 'badge-activating',
  deactivating: 'badge-deactivating',
}[props.state] || 'badge-other'))
</script>

<style scoped>
.badge {
  display: inline-flex; align-items: center;
  padding: 2px 8px; border-radius: 4px;
  font-family: var(--font-mono); font-size: 10px;
  font-weight: 600; letter-spacing: 0.5px;
  text-transform: uppercase;
}
.badge-active     { background: rgba(34,197,94,0.12);  color: var(--accent-green);  border: 1px solid rgba(34,197,94,0.25); }
.badge-inactive   { background: rgba(74,96,128,0.15);  color: var(--text-muted);    border: 1px solid var(--border); }
.badge-failed     { background: rgba(239,68,68,0.12);  color: var(--accent-red);    border: 1px solid rgba(239,68,68,0.25); }
.badge-activating { background: rgba(14,165,233,0.12); color: var(--accent-blue);   border: 1px solid rgba(14,165,233,0.25); }
.badge-other      { background: var(--surface-2);      color: var(--text-muted);    border: 1px solid var(--border); }
</style>
```

- [ ] **Step 2: Create `frontend/src/views/ServicesView.vue`**

```vue
<template>
  <div class="services-view">
    <!-- Toolbar -->
    <div class="toolbar">
      <div class="search-wrap">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <input v-model="filter" placeholder="Filter services…" class="search-input" />
      </div>
      <div class="state-filters">
        <button
          v-for="s in stateOptions" :key="s.value"
          class="filter-btn" :class="{ active: stateFilter === s.value }"
          @click="stateFilter = s.value"
        >{{ s.label }}</button>
      </div>
      <button class="refresh-btn" @click="loadServices" :disabled="loading" title="Refresh">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
        </svg>
      </button>
    </div>

    <!-- Error -->
    <div v-if="error" class="error-banner">{{ error }}</div>

    <!-- Table -->
    <div class="table-wrap">
      <table class="service-table">
        <thead>
          <tr>
            <th>SERVICE</th>
            <th>STATE</th>
            <th>SUB</th>
            <th>ENABLED</th>
            <th class="desc-col">DESCRIPTION</th>
            <th>ACTIONS</th>
          </tr>
        </thead>
        <tbody>
          <template v-if="loading">
            <tr v-for="i in 8" :key="i" class="skeleton-row">
              <td colspan="6"><div class="skeleton"></div></td>
            </tr>
          </template>
          <template v-else-if="filtered.length === 0">
            <tr><td colspan="6" class="empty-cell">No services found</td></tr>
          </template>
          <template v-else>
            <tr
              v-for="svc in filtered" :key="svc.name"
              class="service-row"
              :class="{ selected: selectedService === svc.name }"
              @click="toggleLogs(svc.name)"
            >
              <td class="name-cell">{{ svc.name }}</td>
              <td><StatusBadge :state="svc.active_state" /></td>
              <td class="sub-cell">{{ svc.sub_state }}</td>
              <td class="sub-cell">{{ svc.enabled }}</td>
              <td class="desc-col text-muted">{{ svc.description }}</td>
              <td class="actions-cell" @click.stop>
                <button
                  v-for="act in actions" :key="act.action"
                  class="action-btn" :class="`btn-${act.color}`"
                  :disabled="actionLoading[svc.name]"
                  @click="runAction(svc.name, act.action)"
                  :title="act.label"
                >{{ act.label }}</button>
              </td>
            </tr>
            <!-- Inline log panel -->
            <tr v-if="selectedService && logsByService[selectedService]" class="log-row">
              <td colspan="6">
                <div class="log-panel">
                  <div class="log-header">
                    <span>{{ selectedService }} — journald logs</span>
                    <button class="close-log" @click="selectedService = null">✕</button>
                  </div>
                  <pre class="log-content">{{ logsByService[selectedService].join('\n') }}</pre>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import StatusBadge from '../components/services/StatusBadge.vue'
import api from '../api/client.js'

const services = ref([])
const loading = ref(false)
const error = ref('')
const filter = ref('')
const stateFilter = ref('all')
const selectedService = ref(null)
const logsByService = ref({})
const actionLoading = ref({})

const stateOptions = [
  { value: 'all', label: 'All' },
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
  { value: 'failed', label: 'Failed' },
]

const actions = [
  { action: 'start', label: 'Start', color: 'green' },
  { action: 'stop', label: 'Stop', color: 'yellow' },
  { action: 'restart', label: 'Restart', color: 'blue' },
]

async function loadServices() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get('/services/')
    services.value = data
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load services'
  } finally {
    loading.value = false
  }
}

async function toggleLogs(name) {
  if (selectedService.value === name) {
    selectedService.value = null
    return
  }
  selectedService.value = name
  if (!logsByService.value[name]) {
    try {
      const { data } = await api.get(`/services/${name}/logs?lines=80`)
      logsByService.value[name] = data.lines
    } catch {
      logsByService.value[name] = ['Failed to load logs']
    }
  }
}

async function runAction(name, action) {
  actionLoading.value[name] = true
  try {
    await api.post(`/services/${name}/${action}`)
    // Refresh service state
    const { data } = await api.get('/services/')
    services.value = data
    // Refresh logs if open
    if (selectedService.value === name) {
      const logResp = await api.get(`/services/${name}/logs?lines=80`)
      logsByService.value[name] = logResp.data.lines
    }
  } catch (e) {
    error.value = e.response?.data?.detail || `Failed to ${action} ${name}`
    setTimeout(() => { error.value = '' }, 4000)
  } finally {
    actionLoading.value[name] = false
  }
}

const filtered = computed(() => services.value.filter(s => {
  const matchesText = filter.value === '' ||
    s.name.toLowerCase().includes(filter.value.toLowerCase()) ||
    s.description.toLowerCase().includes(filter.value.toLowerCase())
  const matchesState = stateFilter.value === 'all' || s.active_state === stateFilter.value
  return matchesText && matchesState
}))

onMounted(loadServices)
</script>

<style scoped>
.services-view { display: flex; flex-direction: column; gap: 14px; }

/* Toolbar */
.toolbar {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
}
.search-wrap {
  display: flex; align-items: center; gap: 8px;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 5px; padding: 6px 10px; flex: 1; min-width: 200px;
  color: var(--text-muted);
}
.search-input {
  background: none; border: none; outline: none;
  color: var(--text); font-family: var(--font-mono); font-size: 12px; width: 100%;
}
.search-input::placeholder { color: var(--text-dim); }
.state-filters { display: flex; gap: 4px; }
.filter-btn {
  background: var(--surface); border: 1px solid var(--border);
  color: var(--text-muted); padding: 5px 10px;
  border-radius: 4px; font-size: 11px; cursor: pointer;
  font-family: var(--font-mono); transition: all 0.15s;
}
.filter-btn:hover, .filter-btn.active {
  background: var(--surface-2); border-color: var(--accent-blue); color: var(--accent-blue);
}
.refresh-btn {
  background: var(--surface); border: 1px solid var(--border);
  color: var(--text-muted); padding: 6px 8px; border-radius: 5px; cursor: pointer;
  display: flex; align-items: center; transition: all 0.15s;
}
.refresh-btn:hover { color: var(--text); border-color: var(--border-bright); }

/* Error */
.error-banner {
  background: rgba(239,68,68,0.1); border: 1px solid var(--accent-red);
  color: var(--accent-red); padding: 10px 14px; border-radius: 6px; font-size: 13px;
}

/* Table */
.table-wrap { overflow-x: auto; }
.service-table {
  width: 100%; border-collapse: collapse;
  background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
  overflow: hidden;
}
.service-table th {
  font-family: var(--font-mono); font-size: 9px; letter-spacing: 1.5px;
  color: var(--text-muted); text-align: left; padding: 10px 14px;
  border-bottom: 1px solid var(--border); background: var(--surface-2);
  font-weight: 600;
}
.service-row { cursor: pointer; transition: background 0.1s; }
.service-row:hover { background: var(--surface-2); }
.service-row.selected { background: var(--surface-2); border-left: 2px solid var(--accent-blue); }
.service-row td {
  padding: 9px 14px; border-bottom: 1px solid var(--border);
  font-size: 12px; vertical-align: middle;
}
.name-cell { font-family: var(--font-mono); font-size: 12px; color: var(--text-bright); }
.sub-cell { font-family: var(--font-mono); font-size: 11px; color: var(--text-muted); }
.desc-col { max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.text-muted { color: var(--text-muted); }
.empty-cell { text-align: center; padding: 40px; color: var(--text-muted); font-size: 13px; }

/* Actions */
.actions-cell { white-space: nowrap; }
.action-btn {
  background: none; border: 1px solid var(--border); color: var(--text-muted);
  padding: 3px 8px; border-radius: 4px; font-size: 10px; cursor: pointer;
  font-family: var(--font-mono); margin-right: 4px; transition: all 0.15s;
}
.btn-green:hover { border-color: var(--accent-green); color: var(--accent-green); }
.btn-yellow:hover { border-color: var(--accent-yellow); color: var(--accent-yellow); }
.btn-blue:hover { border-color: var(--accent-blue); color: var(--accent-blue); }
.action-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* Log panel */
.log-row td { padding: 0; border-bottom: 1px solid var(--border); }
.log-panel { background: var(--bg); }
.log-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 14px; border-bottom: 1px solid var(--border);
  font-family: var(--font-mono); font-size: 11px; color: var(--text-muted);
}
.close-log {
  background: none; border: none; color: var(--text-muted); cursor: pointer; font-size: 12px;
}
.close-log:hover { color: var(--text); }
.log-content {
  font-family: var(--font-mono); font-size: 11px; line-height: 1.7;
  color: var(--text-muted); padding: 12px 14px;
  max-height: 300px; overflow-y: auto;
  white-space: pre-wrap; word-break: break-all;
}

/* Skeleton */
.skeleton-row td { padding: 10px 14px; border-bottom: 1px solid var(--border); }
.skeleton {
  height: 14px; background: var(--surface-2);
  border-radius: 4px; animation: shimmer 1.4s ease-in-out infinite;
}
@keyframes shimmer {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 0.8; }
}
</style>
```

- [ ] **Step 3: Add `/services` route to `frontend/src/router/index.js`**

Add import and route:
```js
import ServicesView from '../views/ServicesView.vue'
// in routes array:
{ path: '/services', component: ServicesView, meta: { title: 'Services' } }
```

- [ ] **Step 4: Build frontend and run all tests**

```bash
cd /home/crt/server_dashboard/frontend && npm run build
.venv/bin/pytest tests/ -q
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/services/ frontend/src/views/ServicesView.vue frontend/src/router/index.js
git commit -m "feat: Phase 2 Services frontend — table, status badges, log panel"
```
