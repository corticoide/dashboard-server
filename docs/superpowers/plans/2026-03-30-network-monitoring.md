# Network Monitoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Network Monitoring section that shows live interface stats, bandwidth history, and active connections.

**Architecture:** New `network` module across model/service/router/view layers. A scheduler job samples `/proc/net/dev` via `psutil` every 60 seconds, stores deltas in a `network_snapshots` table, and a retention job cleans data older than 30 days. The frontend shows a dedicated NetworkView with bandwidth charts (Chart.js) and a connections table.

**Tech Stack:** psutil (already installed), Chart.js + vue-chartjs (new frontend deps), FastAPI router, SQLAlchemy model, APScheduler job.

---

### Task 1: Network Snapshot Model + Migration

**Files:**
- Create: `backend/models/network_snapshot.py`
- Modify: `backend/main.py:22` (add model import)
- Modify: `backend/scripts/add_indexes.py` (add new indexes)

- [x] **Step 1: Create the model file**

```python
# backend/models/network_snapshot.py
from sqlalchemy import Column, Integer, Float, String, DateTime, Index
from sqlalchemy.sql import func
from backend.database import Base


class NetworkSnapshot(Base):
    __tablename__ = "network_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, server_default=func.now(), nullable=False)
    interface = Column(String, nullable=False)
    bytes_sent = Column(Float, nullable=False)
    bytes_recv = Column(Float, nullable=False)
    packets_sent = Column(Integer, nullable=False)
    packets_recv = Column(Integer, nullable=False)
    errin = Column(Integer, nullable=False, default=0)
    errout = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("ix_network_snapshots_timestamp", "timestamp"),
        Index("ix_network_snapshots_interface", "interface"),
        Index("ix_network_snapshots_interface_timestamp", "interface", "timestamp"),
    )
```

- [x] **Step 2: Register the model in main.py**

Add after line 23 in `backend/main.py`:

```python
import backend.models.network_snapshot  # noqa: F401
```

- [x] **Step 3: Add indexes to add_indexes.py**

Append these statements to the `statements` list in `backend/scripts/add_indexes.py`:

```python
"CREATE INDEX IF NOT EXISTS ix_network_snapshots_timestamp ON network_snapshots (timestamp)",
"CREATE INDEX IF NOT EXISTS ix_network_snapshots_interface ON network_snapshots (interface)",
"CREATE INDEX IF NOT EXISTS ix_network_snapshots_interface_timestamp ON network_snapshots (interface, timestamp)",
```

- [x] **Step 4: Verify table creation**

```bash
python -c "
from backend.database import engine, Base
import backend.models.network_snapshot
Base.metadata.create_all(bind=engine)
print('network_snapshots table created')
"
```

Expected: `network_snapshots table created` with no errors.

- [x] **Step 5: Commit**

```bash
git add backend/models/network_snapshot.py backend/main.py backend/scripts/add_indexes.py
git commit -m "feat(network): add NetworkSnapshot model and indexes"
```

---

### Task 2: Network Service Layer

**Files:**
- Create: `backend/services/network_service.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_network_service.py`:

```python
from backend.services.network_service import (
    get_interfaces,
    get_active_connections,
)


def test_get_interfaces_returns_list():
    result = get_interfaces()
    assert isinstance(result, list)
    assert len(result) > 0
    iface = result[0]
    assert "name" in iface
    assert "ip" in iface
    assert "bytes_sent" in iface
    assert "bytes_recv" in iface


def test_get_active_connections_returns_list():
    result = get_active_connections()
    assert isinstance(result, list)
    # each connection should have these fields
    if len(result) > 0:
        conn = result[0]
        assert "type" in conn
        assert "local_addr" in conn
        assert "status" in conn
```

- [x] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_network_service.py -v
```

Expected: FAIL with `ModuleNotFoundError` or `ImportError`.

- [x] **Step 3: Write the service**

```python
# backend/services/network_service.py
import psutil


def get_interfaces() -> list[dict]:
    """Return a list of network interfaces with their current stats."""
    counters = psutil.net_io_counters(pernic=True)
    addrs = psutil.net_if_addrs()

    result = []
    for name, stats in counters.items():
        if name == "lo":
            continue
        ip = ""
        if name in addrs:
            for addr in addrs[name]:
                if addr.family.name == "AF_INET":
                    ip = addr.address
                    break
        result.append({
            "name": name,
            "ip": ip,
            "bytes_sent": stats.bytes_sent,
            "bytes_recv": stats.bytes_recv,
            "packets_sent": stats.packets_sent,
            "packets_recv": stats.packets_recv,
            "errin": stats.errin,
            "errout": stats.errout,
        })
    return result


def get_active_connections() -> list[dict]:
    """Return active network connections (TCP/UDP)."""
    connections = []
    for conn in psutil.net_connections(kind="inet"):
        local = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else ""
        remote = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else ""
        connections.append({
            "type": "TCP" if conn.type == 1 else "UDP",
            "local_addr": local,
            "remote_addr": remote,
            "status": conn.status if conn.status else "NONE",
            "pid": conn.pid,
        })
    return connections
```

- [x] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_network_service.py -v
```

Expected: PASS (both tests).

- [x] **Step 5: Commit**

```bash
git add backend/services/network_service.py tests/test_network_service.py
git commit -m "feat(network): add network service layer (interfaces + connections)"
```

---

### Task 3: Pydantic Schemas for Network

**Files:**
- Create: `backend/schemas/network.py`

- [ ] **Step 1: Create schema file**

```python
# backend/schemas/network.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class InterfaceInfo(BaseModel):
    name: str
    ip: str
    bytes_sent: float
    bytes_recv: float
    packets_sent: int
    packets_recv: int
    errin: int
    errout: int


class ConnectionInfo(BaseModel):
    type: str
    local_addr: str
    remote_addr: str
    status: str
    pid: Optional[int] = None


class NetworkSnapshotOut(BaseModel):
    id: int
    timestamp: datetime
    interface: str
    bytes_sent: float
    bytes_recv: float
    packets_sent: int
    packets_recv: int
    errin: int
    errout: int

    class Config:
        from_attributes = True


class BandwidthPoint(BaseModel):
    timestamp: datetime
    bytes_sent: float
    bytes_recv: float
```

- [x] **Step 2: Commit**

```bash
git add backend/schemas/network.py
git commit -m "feat(network): add Pydantic schemas for network endpoints"
```

---

### Task 4: Network Router

**Files:**
- Create: `backend/routers/network.py`
- Modify: `backend/main.py` (register router)

- [ ] **Step 1: Write failing integration test**

Create `tests/test_network_router.py`:

```python
def get_token(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    return r.json()["access_token"]


def test_get_interfaces(test_app):
    token = get_token(test_app)
    r = test_app.get("/api/network/interfaces", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


def test_get_connections(test_app):
    token = get_token(test_app)
    r = test_app.get("/api/network/connections", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


def test_get_bandwidth_history(test_app):
    token = get_token(test_app)
    r = test_app.get("/api/network/bandwidth", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


def test_unauthenticated_returns_403(test_app):
    r = test_app.get("/api/network/interfaces")
    assert r.status_code == 403
```

- [x] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_network_router.py -v
```

Expected: FAIL (404, router not registered).

- [x] **Step 3: Write the router**

```python
# backend/routers/network.py
from fastapi import APIRouter, Depends, Query, Response
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.network_snapshot import NetworkSnapshot
from backend.schemas.network import InterfaceInfo, ConnectionInfo, BandwidthPoint
from backend.services.network_service import get_interfaces, get_active_connections
from backend.services.cache import TTLCache

router = APIRouter(prefix="/api/network", tags=["network"])

_iface_cache = TTLCache()
_IFACE_TTL = 5.0
_count_cache = TTLCache()
_COUNT_TTL = 300


@router.get("/interfaces", response_model=List[InterfaceInfo])
def list_interfaces(user=Depends(get_current_user)):
    cached = _iface_cache.get("ifaces")
    if cached is not None:
        return cached
    result = get_interfaces()
    _iface_cache.set("ifaces", result, ttl=_IFACE_TTL)
    return result


@router.get("/connections", response_model=List[ConnectionInfo])
def list_connections(user=Depends(get_current_user)):
    return get_active_connections()


@router.get("/bandwidth", response_model=List[BandwidthPoint])
def bandwidth_history(
    interface: Optional[str] = Query(None),
    hours: int = Query(24, ge=1, le=720),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    q = db.query(NetworkSnapshot).filter(NetworkSnapshot.timestamp >= cutoff)
    if interface:
        q = q.filter(NetworkSnapshot.interface == interface)
    q = q.order_by(NetworkSnapshot.timestamp.asc())
    rows = q.limit(2000).all()
    return [
        BandwidthPoint(
            timestamp=r.timestamp,
            bytes_sent=r.bytes_sent,
            bytes_recv=r.bytes_recv,
        )
        for r in rows
    ]
```

- [x] **Step 4: Register router in main.py**

Add import after line 17 in `backend/main.py`:

```python
from backend.routers.network import router as network_router
```

Add after line 67 (after `logs_router`):

```python
app.include_router(network_router)
```

- [x] **Step 5: Add cache reset fixture to conftest.py**

Add to `tests/conftest.py` after the `reset_count_cache` fixture:

```python
@pytest.fixture(autouse=True)
def reset_network_caches():
    from backend.routers.network import _iface_cache, _count_cache
    _iface_cache.clear()
    _count_cache.clear()
    yield
```

- [x] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_network_router.py -v
```

Expected: All 4 tests PASS.

- [x] **Step 7: Commit**

```bash
git add backend/routers/network.py backend/main.py tests/test_network_router.py tests/conftest.py
git commit -m "feat(network): add /api/network router with interfaces, connections, bandwidth"
```

---

### Task 5: Scheduler Job — Network Snapshot Sampling

**Files:**
- Modify: `backend/scheduler.py`
- Modify: `backend/config.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_network_service.py`:

```python
from datetime import datetime, timedelta
from backend.models.network_snapshot import NetworkSnapshot


def test_do_network_sample(db_session):
    from backend.scheduler import _do_network_sample
    count = _do_network_sample(db_session)
    assert count >= 1
    snapshots = db_session.query(NetworkSnapshot).all()
    assert len(snapshots) == count
    snap = snapshots[0]
    assert snap.interface != ""
    assert snap.bytes_sent >= 0
    assert snap.bytes_recv >= 0


def test_do_network_cleanup(db_session):
    from backend.scheduler import _do_network_cleanup
    # Seed old snapshot
    old = NetworkSnapshot(
        timestamp=datetime.utcnow() - timedelta(days=40),
        interface="eth0",
        bytes_sent=100.0,
        bytes_recv=200.0,
        packets_sent=10,
        packets_recv=20,
        errin=0,
        errout=0,
    )
    db_session.add(old)
    db_session.commit()
    deleted = _do_network_cleanup(db_session, retention_days=30)
    assert deleted == 1
    assert db_session.query(NetworkSnapshot).count() == 0
```

- [x] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_network_service.py::test_do_network_sample tests/test_network_service.py::test_do_network_cleanup -v
```

Expected: FAIL with `ImportError`.

- [x] **Step 3: Add config setting**

In `backend/config.py`, add to the `Settings` class:

```python
network_retention_days: int = 30
```

- [x] **Step 4: Implement scheduler functions**

Add to `backend/scheduler.py` (after the `_vacuum_job` function):

```python
def _do_network_sample(db: Session) -> int:
    """Capture current network stats and store as snapshots. Returns count inserted."""
    import psutil
    from backend.models.network_snapshot import NetworkSnapshot

    counters = psutil.net_io_counters(pernic=True)
    now = datetime.utcnow()
    count = 0
    for name, stats in counters.items():
        if name == "lo":
            continue
        db.add(NetworkSnapshot(
            timestamp=now,
            interface=name,
            bytes_sent=stats.bytes_sent,
            bytes_recv=stats.bytes_recv,
            packets_sent=stats.packets_sent,
            packets_recv=stats.packets_recv,
            errin=stats.errin,
            errout=stats.errout,
        ))
        count += 1
    db.commit()
    logger.info("Network sample: inserted %d interface snapshots", count)
    return count


def _do_network_cleanup(db: Session, retention_days: int) -> int:
    """Delete network snapshots older than retention_days. Returns count deleted."""
    from backend.models.network_snapshot import NetworkSnapshot

    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    deleted = db.query(NetworkSnapshot).filter(
        NetworkSnapshot.timestamp < cutoff
    ).delete(synchronize_session=False)
    db.commit()
    logger.info("Network cleanup: deleted %d snapshot(s) older than %d days", deleted, retention_days)
    return deleted


def _network_sample_job() -> None:
    """APScheduler job: sample network stats every minute."""
    from backend.database import SessionLocal
    db = SessionLocal()
    try:
        _do_network_sample(db)
    except Exception:
        logger.exception("Network sample job failed")
    finally:
        db.close()


def _network_cleanup_job() -> None:
    """APScheduler job: daily network snapshot retention cleanup."""
    from backend.database import SessionLocal
    from backend.config import settings
    db = SessionLocal()
    try:
        _do_network_cleanup(db, settings.network_retention_days)
    except Exception:
        logger.exception("Network cleanup job failed")
    finally:
        db.close()
```

- [x] **Step 5: Register jobs in init_scheduler()**

Add inside `init_scheduler()`, after the existing `add_job` calls:

```python
from apscheduler.triggers.interval import IntervalTrigger
_scheduler.add_job(_network_sample_job, IntervalTrigger(seconds=60), id="network_sample")
_scheduler.add_job(_network_cleanup_job, CronTrigger(hour=2, minute=30), id="network_cleanup")
```

- [x] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_network_service.py -v
```

Expected: All 4 tests PASS.

- [x] **Step 7: Commit**

```bash
git add backend/scheduler.py backend/config.py
git commit -m "feat(network): add scheduler jobs for sampling + retention cleanup"
```

---

### Task 6: Frontend — Install Chart.js + Create NetworkView

**Files:**
- Modify: `frontend/package.json` (new deps)
- Create: `frontend/src/views/NetworkView.vue`
- Modify: `frontend/src/router/index.js` (add route)
- Modify: `frontend/src/components/layout/AppSidebar.vue` (add nav item)

- [ ] **Step 1: Install chart dependencies**

```bash
cd frontend && npm install chart.js vue-chartjs
```

- [x] **Step 2: Add route (lazy-loaded)**

In `frontend/src/router/index.js`, add after the `/logs` route (before the catch-all):

```javascript
{ path: '/network', component: () => import('../views/NetworkView.vue'), meta: { requiresAuth: true, title: 'Network' } },
```

- [x] **Step 3: Add sidebar nav item**

In `frontend/src/components/layout/AppSidebar.vue`, add after the Files `<RouterLink>` (inside the MONITOR section):

```html
<RouterLink class="nav-item" to="/network" :class="{ active: route.path === '/network' }">
  <i class="pi pi-wifi nav-icon" />
  <span class="nav-label">Network</span>
</RouterLink>
```

- [x] **Step 4: Create NetworkView.vue**

```vue
<!-- frontend/src/views/NetworkView.vue -->
<template>
  <div class="network-view">

    <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>

    <!-- Interfaces -->
    <Card class="net-card">
      <template #content>
        <div class="card-section-header">
          <i class="pi pi-wifi section-icon" />
          <span class="section-title">INTERFACES</span>
        </div>
        <Divider class="section-divider" />
        <DataTable :value="interfaces" size="small" :show-gridlines="false">
          <template #empty><span class="cell-empty">No interfaces found</span></template>
          <Column field="name" header="Interface" />
          <Column field="ip" header="IP Address" />
          <Column header="Sent">
            <template #body="{ data }">
              <span class="cell-mono">{{ formatBytes(data.bytes_sent) }}</span>
            </template>
          </Column>
          <Column header="Received">
            <template #body="{ data }">
              <span class="cell-mono">{{ formatBytes(data.bytes_recv) }}</span>
            </template>
          </Column>
          <Column field="packets_sent" header="Pkts Out" />
          <Column field="packets_recv" header="Pkts In" />
          <Column header="Errors">
            <template #body="{ data }">
              <Tag v-if="data.errin + data.errout > 0"
                :value="`${data.errin + data.errout}`" severity="danger" />
              <span v-else class="cell-meta">0</span>
            </template>
          </Column>
        </DataTable>
      </template>
    </Card>

    <!-- Bandwidth Chart -->
    <Card class="net-card">
      <template #content>
        <div class="card-section-header">
          <i class="pi pi-chart-line section-icon" />
          <span class="section-title">BANDWIDTH (LAST {{ hours }}H)</span>
          <Select v-model="hours" :options="hourOptions" class="hours-select" />
        </div>
        <Divider class="section-divider" />
        <div class="chart-container">
          <Line v-if="chartData.labels.length > 0" :data="chartData" :options="chartOptions" />
          <span v-else class="cell-empty">No bandwidth data yet — collecting...</span>
        </div>
      </template>
    </Card>

    <!-- Active connections -->
    <Card class="net-card">
      <template #content>
        <div class="card-section-header">
          <i class="pi pi-arrows-h section-icon" />
          <span class="section-title">ACTIVE CONNECTIONS</span>
          <span class="section-extra">{{ connections.length }} total</span>
        </div>
        <Divider class="section-divider" />
        <DataTable :value="connections" size="small" :show-gridlines="false"
          :paginator="connections.length > 20" :rows="20">
          <template #empty><span class="cell-empty">No connections</span></template>
          <Column field="type" header="Proto" style="width: 70px" />
          <Column field="local_addr" header="Local Address" />
          <Column field="remote_addr" header="Remote Address" />
          <Column field="status" header="Status" style="width: 120px">
            <template #body="{ data }">
              <Tag :value="data.status"
                :severity="data.status === 'ESTABLISHED' ? 'success' : 'secondary'" />
            </template>
          </Column>
          <Column field="pid" header="PID" style="width: 80px" />
        </DataTable>
      </template>
    </Card>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import Message from 'primevue/message'
import Card from 'primevue/card'
import Divider from 'primevue/divider'
import Tag from 'primevue/tag'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Select from 'primevue/select'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  LineElement,
  PointElement,
  LinearScale,
  TimeScale,
  CategoryScale,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'
import { usePolling } from '../composables/usePolling.js'
import api from '../api/client.js'

ChartJS.register(LineElement, PointElement, LinearScale, TimeScale, CategoryScale, Tooltip, Legend, Filler)

const error = ref('')
const interfaces = ref([])
const connections = ref([])
const bandwidthData = ref([])
const hours = ref(24)
const hourOptions = [1, 6, 12, 24, 48, 168]

function formatBytes(b) {
  if (b >= 1e9) return `${(b / 1e9).toFixed(2)} GB`
  if (b >= 1e6) return `${(b / 1e6).toFixed(2)} MB`
  if (b >= 1e3) return `${(b / 1e3).toFixed(1)} KB`
  return `${b} B`
}

async function fetchInterfaces() {
  try {
    const { data } = await api.get('/network/interfaces')
    interfaces.value = data
    error.value = ''
  } catch {
    error.value = 'Failed to fetch network data'
  }
}

async function fetchConnections() {
  try {
    const { data } = await api.get('/network/connections')
    connections.value = data
  } catch { /* non-critical */ }
}

async function fetchBandwidth() {
  try {
    const { data } = await api.get('/network/bandwidth', { params: { hours: hours.value } })
    bandwidthData.value = data
  } catch { /* non-critical */ }
}

watch(hours, fetchBandwidth)

const chartData = computed(() => {
  const labels = bandwidthData.value.map(p => {
    const d = new Date(p.timestamp)
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  })
  return {
    labels,
    datasets: [
      {
        label: 'Sent',
        data: bandwidthData.value.map(p => p.bytes_sent),
        borderColor: '#f97316',
        backgroundColor: 'rgba(249, 115, 22, 0.1)',
        fill: true,
        tension: 0.3,
        pointRadius: 0,
      },
      {
        label: 'Received',
        data: bandwidthData.value.map(p => p.bytes_recv),
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        fill: true,
        tension: 0.3,
        pointRadius: 0,
      },
    ],
  }
})

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { position: 'top' } },
  scales: {
    y: { beginAtZero: true, ticks: { callback: (v) => formatBytes(v) } },
  },
}

function fetchAll() {
  fetchInterfaces()
  fetchConnections()
}

const { start, stop } = usePolling(fetchAll, 10000)
const { start: startBw, stop: stopBw } = usePolling(fetchBandwidth, 60000)
onMounted(() => { start(); startBw() })
onUnmounted(() => { stop(); stopBw() })
</script>

<style scoped>
.network-view { display: flex; flex-direction: column; gap: 16px; }
:deep(.net-card .p-card-body) { padding: 0; }
:deep(.net-card .p-card-content) { padding: 14px 16px; }
.card-section-header { display: flex; align-items: center; gap: 8px; padding-bottom: 2px; }
.section-icon { font-size: 12px; color: var(--brand-orange); flex-shrink: 0; }
.section-title { font-family: var(--font-mono); font-size: var(--text-2xs); letter-spacing: 2px; text-transform: uppercase; color: var(--p-text-muted-color); flex: 1; }
.section-extra { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-muted-color); }
.section-divider { margin: 10px 0 !important; }
.cell-mono { font-family: var(--font-mono); font-size: var(--text-sm); }
.cell-meta { font-size: var(--text-xs); color: var(--p-text-muted-color); }
.cell-empty { font-size: var(--text-sm); color: var(--p-text-muted-color); }
.chart-container { height: 300px; position: relative; }
.hours-select { width: 80px; }
</style>
```

- [x] **Step 5: Verify frontend builds**

```bash
cd frontend && npm run build
```

Expected: Build succeeds with no errors.

- [x] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/views/NetworkView.vue frontend/src/router/index.js frontend/src/components/layout/AppSidebar.vue
git commit -m "feat(network): add NetworkView with interfaces, bandwidth chart, connections table"
```

---

### Task 7: Run Full Test Suite

**Files:** None (validation only)

- [ ] **Step 1: Run all backend tests**

```bash
pytest -v
```

Expected: All tests PASS (existing + new network tests).

- [x] **Step 2: Run frontend build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds.

- [x] **Step 3: Final commit if any fixups needed**

Only if tests revealed issues that required fixes.
