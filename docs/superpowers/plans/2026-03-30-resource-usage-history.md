# Resource Usage History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record CPU, RAM, and disk usage over time and display historical charts on the Dashboard, allowing the user to see trends across 24h, 7d, and 30d ranges.

**Architecture:** A new `metrics_snapshots` table stores periodic samples (every 60s via scheduler). A new `/api/metrics/history` endpoint returns time-series data with automatic aggregation for long ranges. The existing DashboardView is extended with a chart section using Chart.js (installed in the Network Monitoring plan). A retention job purges data older than the configured limit.

**Tech Stack:** psutil (already installed), Chart.js + vue-chartjs (installed by Network Monitoring plan — if implementing standalone, install them here), SQLAlchemy model, APScheduler job.

---

### Task 1: MetricsSnapshot Model + Migration

**Files:**
- Create: `backend/models/metrics_snapshot.py`
- Modify: `backend/main.py` (add model import)
- Modify: `backend/scripts/add_indexes.py` (add new indexes)

- [ ] **Step 1: Create the model file**

```python
# backend/models/metrics_snapshot.py
from sqlalchemy import Column, Integer, Float, DateTime, Index
from sqlalchemy.sql import func
from backend.database import Base


class MetricsSnapshot(Base):
    __tablename__ = "metrics_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, server_default=func.now(), nullable=False)
    cpu_percent = Column(Float, nullable=False)
    ram_percent = Column(Float, nullable=False)
    ram_used_gb = Column(Float, nullable=False)
    disk_percent = Column(Float, nullable=False)
    disk_used_gb = Column(Float, nullable=False)

    __table_args__ = (
        Index("ix_metrics_snapshots_timestamp", "timestamp"),
    )
```

- [ ] **Step 2: Register the model in main.py**

Add after the other model imports in `backend/main.py`:

```python
import backend.models.metrics_snapshot  # noqa: F401
```

- [ ] **Step 3: Add indexes to add_indexes.py**

Append to the `statements` list in `backend/scripts/add_indexes.py`:

```python
"CREATE INDEX IF NOT EXISTS ix_metrics_snapshots_timestamp ON metrics_snapshots (timestamp)",
```

- [ ] **Step 4: Verify table creation**

```bash
python -c "
from backend.database import engine, Base
import backend.models.metrics_snapshot
Base.metadata.create_all(bind=engine)
print('metrics_snapshots table created')
"
```

Expected: `metrics_snapshots table created`.

- [ ] **Step 5: Commit**

```bash
git add backend/models/metrics_snapshot.py backend/main.py backend/scripts/add_indexes.py
git commit -m "feat(metrics-history): add MetricsSnapshot model and indexes"
```

---

### Task 2: Scheduler Jobs — Sampling + Retention

**Files:**
- Modify: `backend/scheduler.py`
- Modify: `backend/config.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_metrics_history.py`:

```python
from datetime import datetime, timedelta
from backend.models.metrics_snapshot import MetricsSnapshot


def test_do_metrics_sample(db_session):
    from backend.scheduler import _do_metrics_sample
    _do_metrics_sample(db_session)
    snapshots = db_session.query(MetricsSnapshot).all()
    assert len(snapshots) == 1
    snap = snapshots[0]
    assert snap.cpu_percent >= 0
    assert snap.ram_percent >= 0
    assert snap.disk_percent >= 0
    assert snap.ram_used_gb >= 0
    assert snap.disk_used_gb >= 0


def test_do_metrics_cleanup(db_session):
    from backend.scheduler import _do_metrics_cleanup
    old = MetricsSnapshot(
        timestamp=datetime.utcnow() - timedelta(days=40),
        cpu_percent=50.0,
        ram_percent=60.0,
        ram_used_gb=4.0,
        disk_percent=70.0,
        disk_used_gb=100.0,
    )
    recent = MetricsSnapshot(
        timestamp=datetime.utcnow() - timedelta(hours=1),
        cpu_percent=55.0,
        ram_percent=65.0,
        ram_used_gb=4.5,
        disk_percent=72.0,
        disk_used_gb=102.0,
    )
    db_session.add_all([old, recent])
    db_session.commit()
    deleted = _do_metrics_cleanup(db_session, retention_days=30)
    assert deleted == 1
    remaining = db_session.query(MetricsSnapshot).all()
    assert len(remaining) == 1
    assert remaining[0].cpu_percent == 55.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_metrics_history.py -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Add config setting**

In `backend/config.py`, add to the `Settings` class:

```python
metrics_retention_days: int = 30
```

- [ ] **Step 4: Implement scheduler functions**

Add to `backend/scheduler.py`:

```python
def _do_metrics_sample(db: Session) -> None:
    """Capture current system metrics and store as snapshot."""
    from backend.models.metrics_snapshot import MetricsSnapshot
    from backend.services.system_service import get_metrics

    m = get_metrics()
    db.add(MetricsSnapshot(
        timestamp=datetime.utcnow(),
        cpu_percent=m.cpu_percent,
        ram_percent=m.ram_percent,
        ram_used_gb=m.ram_used_gb,
        disk_percent=m.disk_percent,
        disk_used_gb=m.disk_used_gb,
    ))
    db.commit()
    logger.info("Metrics sample recorded")


def _do_metrics_cleanup(db: Session, retention_days: int) -> int:
    """Delete metrics snapshots older than retention_days. Returns count deleted."""
    from backend.models.metrics_snapshot import MetricsSnapshot

    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    deleted = db.query(MetricsSnapshot).filter(
        MetricsSnapshot.timestamp < cutoff
    ).delete(synchronize_session=False)
    db.commit()
    logger.info("Metrics cleanup: deleted %d snapshot(s) older than %d days", deleted, retention_days)
    return deleted


def _metrics_sample_job() -> None:
    """APScheduler job: sample system metrics every minute."""
    from backend.database import SessionLocal
    db = SessionLocal()
    try:
        _do_metrics_sample(db)
    except Exception:
        logger.exception("Metrics sample job failed")
    finally:
        db.close()


def _metrics_cleanup_job() -> None:
    """APScheduler job: daily metrics retention cleanup."""
    from backend.database import SessionLocal
    from backend.config import settings
    db = SessionLocal()
    try:
        _do_metrics_cleanup(db, settings.metrics_retention_days)
    except Exception:
        logger.exception("Metrics cleanup job failed")
    finally:
        db.close()
```

- [ ] **Step 5: Register jobs in init_scheduler()**

Add inside `init_scheduler()`:

```python
from apscheduler.triggers.interval import IntervalTrigger
_scheduler.add_job(_metrics_sample_job, IntervalTrigger(seconds=60), id="metrics_sample")
_scheduler.add_job(_metrics_cleanup_job, CronTrigger(hour=2, minute=15), id="metrics_cleanup")
```

Note: If `IntervalTrigger` is already imported (from network monitoring plan), don't duplicate the import.

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_metrics_history.py -v
```

Expected: Both tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/scheduler.py backend/config.py tests/test_metrics_history.py
git commit -m "feat(metrics-history): add scheduler jobs for sampling + retention"
```

---

### Task 3: Pydantic Schemas + History Router

**Files:**
- Create: `backend/schemas/metrics_history.py`
- Create: `backend/routers/metrics_history.py`
- Modify: `backend/main.py` (register router)

- [ ] **Step 1: Create schema file**

```python
# backend/schemas/metrics_history.py
from pydantic import BaseModel
from datetime import datetime


class MetricsSnapshotOut(BaseModel):
    timestamp: datetime
    cpu_percent: float
    ram_percent: float
    ram_used_gb: float
    disk_percent: float
    disk_used_gb: float

    class Config:
        from_attributes = True


class MetricsAggregateOut(BaseModel):
    timestamp: datetime
    avg_cpu: float
    avg_ram: float
    avg_disk: float
```

- [ ] **Step 2: Write failing integration tests**

Create `tests/test_metrics_history_router.py`:

```python
from datetime import datetime, timedelta
from backend.models.metrics_snapshot import MetricsSnapshot


def get_token(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    return r.json()["access_token"]


def _seed_snapshots(test_app):
    """Insert sample snapshots via the test DB."""
    from backend.main import app
    from backend.database import get_db
    db = next(app.dependency_overrides[get_db]())
    now = datetime.utcnow()
    for i in range(5):
        db.add(MetricsSnapshot(
            timestamp=now - timedelta(hours=i),
            cpu_percent=50.0 + i,
            ram_percent=60.0 + i,
            ram_used_gb=4.0,
            disk_percent=70.0,
            disk_used_gb=100.0,
        ))
    db.commit()
    db.close()


def test_get_history(test_app):
    _seed_snapshots(test_app)
    token = get_token(test_app)
    r = test_app.get("/api/metrics/history?hours=24", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 5
    assert "cpu_percent" in data[0]
    assert "timestamp" in data[0]


def test_get_history_empty(test_app):
    token = get_token(test_app)
    r = test_app.get("/api/metrics/history?hours=1", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == []


def test_unauthenticated_returns_403(test_app):
    r = test_app.get("/api/metrics/history")
    assert r.status_code == 403
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_metrics_history_router.py -v
```

Expected: FAIL (404 — router not registered).

- [ ] **Step 4: Write the router**

```python
# backend/routers/metrics_history.py
from fastapi import APIRouter, Depends, Query
from typing import List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.metrics_snapshot import MetricsSnapshot
from backend.schemas.metrics_history import MetricsSnapshotOut

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/history", response_model=List[MetricsSnapshotOut])
def metrics_history(
    hours: int = Query(24, ge=1, le=720),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    q = db.query(MetricsSnapshot).filter(
        MetricsSnapshot.timestamp >= cutoff
    ).order_by(MetricsSnapshot.timestamp.asc())

    # For ranges > 24h, downsample to avoid returning 43k+ points
    # At 1 sample/min: 24h=1440, 168h=10080, 720h=43200
    max_points = 1440
    rows = q.all()
    if len(rows) > max_points:
        step = len(rows) // max_points
        rows = rows[::step]
    return rows
```

- [ ] **Step 5: Register router in main.py**

Add import:

```python
from backend.routers.metrics_history import router as metrics_history_router
```

Add after the other `include_router` calls:

```python
app.include_router(metrics_history_router)
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_metrics_history_router.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/schemas/metrics_history.py backend/routers/metrics_history.py backend/main.py tests/test_metrics_history_router.py
git commit -m "feat(metrics-history): add /api/metrics/history endpoint with downsampling"
```

---

### Task 4: Frontend — History Charts on Dashboard

**Files:**
- Modify: `frontend/src/views/DashboardView.vue`

- [ ] **Step 1: Add chart imports and data to DashboardView.vue**

Add these imports to the `<script setup>` section (after the existing imports):

```javascript
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  LineElement,
  PointElement,
  LinearScale,
  CategoryScale,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'

ChartJS.register(LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Legend, Filler)
```

Add these reactive variables and functions (after the existing `fetchMetrics` function):

```javascript
const historyData = ref([])
const historyHours = ref(24)
const historyHourOptions = [1, 6, 12, 24, 48, 168]

async function fetchHistory() {
  try {
    const { data } = await api.get('/metrics/history', { params: { hours: historyHours.value } })
    historyData.value = data
  } catch { /* non-critical */ }
}

const cpuChartData = computed(() => ({
  labels: historyData.value.map(p => {
    const d = new Date(p.timestamp)
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }),
  datasets: [
    {
      label: 'CPU %',
      data: historyData.value.map(p => p.cpu_percent),
      borderColor: '#f97316',
      backgroundColor: 'rgba(249, 115, 22, 0.1)',
      fill: true,
      tension: 0.3,
      pointRadius: 0,
    },
    {
      label: 'RAM %',
      data: historyData.value.map(p => p.ram_percent),
      borderColor: '#3b82f6',
      backgroundColor: 'rgba(59, 130, 246, 0.1)',
      fill: true,
      tension: 0.3,
      pointRadius: 0,
    },
    {
      label: 'Disk %',
      data: historyData.value.map(p => p.disk_percent),
      borderColor: '#10b981',
      backgroundColor: 'rgba(16, 185, 129, 0.1)',
      fill: true,
      tension: 0.3,
      pointRadius: 0,
    },
  ],
}))

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { position: 'top' } },
  scales: { y: { min: 0, max: 100, ticks: { callback: (v) => `${v}%` } } },
}
```

- [ ] **Step 2: Add watch for hours change**

```javascript
import { watch } from 'vue'  // add to existing import if not present

watch(historyHours, fetchHistory)
```

- [ ] **Step 3: Update polling to include history**

Replace the existing polling setup:

```javascript
const { start: startHistory, stop: stopHistory } = usePolling(fetchHistory, 60000)
onMounted(() => { start(); startLogs(); startHistory() })
onUnmounted(() => { stop(); stopLogs(); stopHistory() })
```

- [ ] **Step 4: Add chart template section**

Add after the System info `<Card>` and before the Recent executions `<Card>`:

```html
<!-- Resource Usage History -->
<Card class="dash-card">
  <template #content>
    <div class="card-section-header">
      <i class="pi pi-chart-line section-icon" />
      <span class="section-title">RESOURCE HISTORY</span>
      <Select v-model="historyHours" :options="historyHourOptions" class="hours-select" />
    </div>
    <Divider class="section-divider" />
    <div class="chart-container">
      <Line v-if="cpuChartData.labels.length > 0" :data="cpuChartData" :options="chartOptions" />
      <span v-else class="cell-empty">No history data yet — collecting starts automatically</span>
    </div>
  </template>
</Card>
```

- [ ] **Step 5: Add PrimeVue Select import**

Add to the imports at the top of `<script setup>`:

```javascript
import Select from 'primevue/select'
```

- [ ] **Step 6: Add chart container style**

Add to `<style scoped>`:

```css
.chart-container { height: 300px; position: relative; }
.hours-select { width: 80px; }
```

- [ ] **Step 7: Verify frontend builds**

```bash
cd frontend && npm run build
```

Expected: Build succeeds.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/views/DashboardView.vue
git commit -m "feat(metrics-history): add resource usage history charts to Dashboard"
```

---

### Task 5: Run Full Test Suite

**Files:** None (validation only)

- [ ] **Step 1: Run all backend tests**

```bash
pytest -v
```

Expected: All tests PASS.

- [ ] **Step 2: Run frontend build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds.
