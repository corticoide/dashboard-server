# Design Spec: Alerts, System Logs & Process Manager

**Date:** 2026-04-16
**Branch:** feat/pipeline-system (merge target: main)
**Status:** Approved

---

## Overview

Three independent monitoring features added to ServerDash, sharing a common notification infrastructure (email via existing SMTP config).

| Feature | Route | New DB tables |
|---------|-------|---------------|
| Alerts & Notifications | `/alerts` | `alert_rules`, `alert_fires` |
| System Logs Viewer | `/logs` (replaces execution logs route) | none |
| Process Manager | `/processes` | none (watch → creates AlertRule) |

---

## 1. Alerts & Notifications

### Purpose

Evaluate configurable conditions every 60 seconds and send email notifications when a threshold is crossed, with cooldown to prevent spam and a recovery notification when the condition clears.

### Alert Conditions

| `condition_type` | `threshold` | `target` | Triggers when |
|-----------------|-------------|----------|---------------|
| `cpu` | float (%) | — | latest MetricsSnapshot.cpu_percent ≥ threshold |
| `ram` | float (%) | — | latest MetricsSnapshot.ram_percent ≥ threshold |
| `disk` | float (%) | — | latest MetricsSnapshot.disk_percent ≥ threshold |
| `service_down` | — | service name | `list_services()` returns status ≠ "active" for target |
| `process_missing` | — | process name | `psutil.process_iter()` finds no process matching target name |

### Data Model

```python
# backend/models/alert.py

class AlertRule(Base):
    __tablename__ = "alert_rules"
    id              = Column(Integer, primary_key=True)
    name            = Column(String, nullable=False)
    enabled         = Column(Boolean, default=True, nullable=False)
    condition_type  = Column(String, nullable=False)  # cpu|ram|disk|service_down|process_missing
    threshold       = Column(Float, nullable=True)    # for cpu/ram/disk
    target          = Column(String, nullable=True)   # service or process name
    cooldown_minutes = Column(Integer, default=60, nullable=False)
    notify_on_recovery = Column(Boolean, default=True, nullable=False)
    email_to        = Column(String, nullable=False)
    created_at      = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_alert_rules_enabled", "enabled"),
        Index("ix_alert_rules_condition_type", "condition_type"),
    )

class AlertFire(Base):
    __tablename__ = "alert_fires"
    id             = Column(Integer, primary_key=True)
    rule_id        = Column(Integer, ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=False)
    fired_at       = Column(DateTime, nullable=False)
    recovered_at   = Column(DateTime, nullable=True)
    status         = Column(String, default="active", nullable=False)  # active|recovered
    detail         = Column(String, nullable=True)   # "CPU at 87.3%"
    email_sent     = Column(Boolean, default=False)
    recovery_email_sent = Column(Boolean, default=False)

    __table_args__ = (
        Index("ix_alert_fires_rule_id", "rule_id"),
        Index("ix_alert_fires_status", "status"),
        Index("ix_alert_fires_fired_at", "fired_at"),
    )
```

### Notification Logic (per rule, every 60s)

```
condition_met = evaluate(rule)

IF condition_met:
    active_fire = query latest fire WHERE rule_id=rule.id AND status='active'
    IF no active_fire:
        create new AlertFire(status='active', fired_at=now, email_sent=False)
        send_email(rule, fire)  → mark email_sent=True
    ELSE IF now - active_fire.fired_at >= cooldown_minutes:
        send_email(rule, fire)  → update fired_at=now (reset cooldown window)
ELSE (condition NOT met):
    active_fire = query latest fire WHERE rule_id=rule.id AND status='active'
    IF active_fire exists:
        active_fire.status = 'recovered'
        active_fire.recovered_at = now
        IF rule.notify_on_recovery AND NOT active_fire.recovery_email_sent:
            send_recovery_email(rule, fire) → mark recovery_email_sent=True
```

### Backend API

```
GET    /api/alerts/rules            → list all rules (paginated)
POST   /api/alerts/rules            → create rule
PUT    /api/alerts/rules/{id}       → update rule
DELETE /api/alerts/rules/{id}       → delete rule
PATCH  /api/alerts/rules/{id}/toggle → enable/disable
GET    /api/alerts/fires            → list fire history (last 100, filterable by rule_id/status)
```

All endpoints require `require_permission("alerts", action)`.

### Notification Service

New file: `backend/services/notification_service.py`

```python
def send_alert_email(rule: AlertRule, fire: AlertFire) -> None:
    """Send alert fired email via smtplib using settings.smtp_*"""

def send_recovery_email(rule: AlertRule, fire: AlertFire) -> None:
    """Send alert recovered email via smtplib using settings.smtp_*"""
```

Uses `smtplib` from Python stdlib. Raises on failure (caught by scheduler job wrapper).
SMTP credentials from `settings.smtp_host/port/user/password/from` (already in config.py).

### Scheduler Job

New job in `backend/scheduler.py`: `_check_alerts_job()` on `IntervalTrigger(seconds=60)`.

Follows the `_do_check_alerts(db)` / `_check_alerts_job()` split pattern.

`_do_check_alerts` is a pure function (testable directly with db_session fixture).

### Frontend: AlertsView.vue

Layout: two-panel split (Splitter).
- **Left panel** — rule list with status dot (active fire = red, ok = green, disabled = gray) + "New rule" button (admin only)
- **Right panel** — rule editor (top) + fire history table (bottom)

Rule editor fields: Name, Type (SelectButton: CPU/RAM/Disk/Service/Process), Threshold or Target, Cooldown, Notify on recovery toggle, Email to.

Fire history shows: status badge, detail, fired_at, recovered_at, duration.

Admin-only: create/edit/delete/toggle rules.
All roles with `alerts.read`: view rules and fire history.

---

## 2. System Logs Viewer

### Purpose

Browse the `/var/log/` directory tree, select a file, and tail it in real time via WebSocket. Read-only.

### Security Constraints

- Backend validates all requested paths are under `/var/log/` (resolves symlinks, checks with `Path.is_relative_to`). Rejects anything outside.
- No write operations. No shell execution.
- Directory listing excludes files the process cannot read (permission errors caught silently).

### Backend API

```
GET /api/system-logs/tree            → recursive listing of /var/log/ (name, path, size, is_dir, readable)
GET /api/system-logs/read?path=&lines=100&offset=0  → paginated read of last N lines
WS  /ws/log-tail?path=               → streams new lines as they are appended
```

**`/tree` response shape:**
```json
[
  {"name": "syslog", "path": "/var/log/syslog", "size_bytes": 2100000, "is_dir": false, "readable": true},
  {"name": "nginx", "path": "/var/log/nginx", "is_dir": true, "children": [...]}
]
```

**WebSocket tail (`/ws/log-tail`):**
- Validates path on connect (must be under `/var/log/`, must be a file, must be readable).
- Opens file, seeks to end, then polls every 500ms for new content using `file.read()`.
- Sends new lines as plain text chunks.
- Closes cleanly on client disconnect.
- No `watchdog` dependency — simple poll is sufficient and keeps the dependency list clean.

### Route naming

Current `/logs` route (execution logs) is renamed to `/execution-logs` in `router/index.js`. The sidebar entry "Logs" is updated to point to the new system logs view. Execution logs remain accessible via sidebar as "Execution Logs" or under Admin section.

### Frontend: SystemLogsView.vue

Layout: two-panel split.
- **Left panel** — `/var/log/` file tree (collapsible directories, file size shown, unreadable files grayed out)
- **Right panel** — log viewer with:
  - Header: filename, TAILING badge (animated), Pause/Resume button, text search input
  - Output area: monospace, color-coded lines (ERROR=red, WARN=orange, INFO=default), auto-scroll to bottom while tailing
  - When paused: scroll freely through buffered lines (capped at 2000 lines per the bounded state rule)

All roles with `system_logs.read` can access. No write actions.

---

## 3. Process Manager

### Purpose

List all running processes with CPU%, RAM usage, and user. Admin can kill a process with confirmation. Any user can "watch" a process — this creates an `AlertRule` of type `process_missing`, integrating with the Alerts system.

### Backend API

```
GET  /api/processes              → list processes (pid, name, cpu_percent, memory_mb, username, status, watched)
POST /api/processes/{pid}/kill   → kill process (admin only, require_permission("processes","execute"))
POST /api/processes/watch        → create AlertRule(type=process_missing, target=name) — requires alerts.write
DELETE /api/processes/watch/{name} → delete the matching AlertRule — requires alerts.write
```

**`GET /api/processes` response:** calls `psutil.process_iter(['pid','name','cpu_percent','memory_info','username','status'])` wrapped in `run_in_threadpool`. Returns list sorted by cpu_percent desc. Includes `watched: bool` (derived by checking if an active AlertRule of type `process_missing` exists for that name).

**`POST /api/processes/{pid}/kill`:** validates PID exists, calls `psutil.Process(pid).kill()`, logs action to audit logger. Returns 404 if PID not found, 403 if not admin.

### Frontend: ProcessesView.vue

Single-panel view with:
- Header: process count, auto-refresh badge (5s), filter input (by name)
- DataTable columns: Name, PID, CPU%, RAM (MB), User, Status, Watch toggle, Kill button
- Watch toggle (all users with processes.read): calls watch/unwatch endpoints, shows orange dot if watched
- Kill button (admin only): opens ConfirmDialog before calling kill endpoint
- Auto-refresh via `usePolling(loadProcesses, 5000)`, stopped in `onUnmounted`
- Bounded state: max 500 processes displayed (sorted by CPU desc) — beyond that, a note "showing top 500 by CPU"

---

## 4. Permissions

New resources added to `DEFAULT_PERMISSIONS` in `backend/scripts/init_db.py`:

| Resource | operator | readonly |
|----------|----------|----------|
| `alerts` | read, write | read |
| `system_logs` | read | read |
| `processes` | read, execute | read |

Admin bypasses the permission table entirely (existing behavior).

`write` on `alerts` is required to create/edit/delete rules and to toggle process watching.
`execute` on `processes` is required to kill a process.

New resources added to `MATRIX_ROWS` in `AdminPermissionsView.vue`.

---

## 5. Navigation

Three new sidebar entries added to `AppSidebar.vue`, below Crontab and above the Admin section:

```
🔔  Alerts      /alerts      resource: alerts
📋  Logs        /logs        resource: system_logs
🖥️  Processes   /processes   resource: processes
```

Current "Logs" sidebar entry (execution logs) renamed to "Exec Logs" pointing to `/execution-logs`.

All three routes use lazy imports in `router/index.js` per the project rule.

---

## 6. Files Created / Modified

### New files
- `backend/models/alert.py`
- `backend/schemas/alert.py`
- `backend/routers/alerts.py`
- `backend/routers/system_logs.py`
- `backend/routers/processes.py`
- `backend/services/notification_service.py`
- `frontend/src/views/AlertsView.vue`
- `frontend/src/views/SystemLogsView.vue`
- `frontend/src/views/ProcessesView.vue`
- `tests/test_alerts.py`
- `tests/test_system_logs.py`
- `tests/test_processes.py`

### Modified files
- `backend/main.py` — register 3 new routers
- `backend/scheduler.py` — add `_do_check_alerts` / `_check_alerts_job`
- `backend/scripts/init_db.py` — add 3 resources to DEFAULT_PERMISSIONS
- `backend/scripts/add_indexes.py` — add 5 new indexes
- `backend/config.py` — add `alerts_retention_days: int = 90`
- `backend/routers/ws.py` — add `/ws/log-tail` endpoint
- `backend/tests/conftest.py` — patch SessionLocal for new routers
- `frontend/src/router/index.js` — 3 new routes + rename /logs → /execution-logs
- `frontend/src/components/layout/AppSidebar.vue` — 3 new entries + rename Logs
- `frontend/src/views/AdminPermissionsView.vue` — 3 new MATRIX_ROWS

---

## 7. Out of Scope

- Webhook notification channel (future feature, roadmap item #8)
- Log export (CSV/JSON) — future iteration
- Alert escalation (notify different emails at different severities)
- Process resource limits or nice/renice
- Real-time process streaming (WebSocket for processes — polling at 5s is sufficient)
