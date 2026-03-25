# ServerDash — Design Spec

**Date:** 2026-03-25
**Status:** Approved

---

## Overview

ServerDash is a local web dashboard for Linux server management. It is a self-contained, installable tool: each server runs its own independent instance. There is no inter-server communication. The system is designed for local-first use with a clear path to internet-facing deployment.

---

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+ · FastAPI |
| Frontend | Vue 3 · Vite |
| Database | SQLite (via SQLAlchemy) |
| Auth | JWT (access + refresh tokens) · bcrypt |
| Transport | HTTPS (self-signed cert locally → Let's Encrypt for internet) |
| Code editor | Monaco Editor (embedded in frontend) |
| System libs | psutil · python-crontab · subprocess · pathlib |

---

## Architecture

FastAPI serves both the REST API and the Vue 3 SPA (built as static files). No separate web server required.

```
Browser (Vue 3 SPA)
       │
       │  HTTPS · REST API · JWT
       ▼
FastAPI application
  ├── /api/auth        — login, token refresh, user management
  ├── /api/system      — CPU, RAM, disk, uptime, load
  ├── /api/services    — systemd service list, start/stop/restart, logs
  ├── /api/files       — filesystem browse, upload, download, move, delete
  ├── /api/scripts     — favorites, execute, execution logs
  └── /api/crontab     — read and write crontab entries
       │
       ▼
Linux system (psutil · systemctl · subprocess · python-crontab · os/pathlib)
       │
       ▼
SQLite database
  ├── users            — credentials, roles
  ├── script_favorites — path, name, type, metadata
  └── execution_logs   — script id, timestamp, exit code, stdout/stderr
```

Frontend polls `/api/system` and `/api/services` every 5 seconds for live updates. No WebSockets in initial phases.

---

## Authentication & Authorization

### Mechanism
- Login with username + password (bcrypt hashed)
- JWT access token (15 min expiry) + refresh token (7 days, stored in httpOnly cookie)
- HTTPS enforced from day one (self-signed cert, replaceable with Let's Encrypt)

### Roles

| Role | Permissions |
|------|------------|
| `admin` | Full access: all modules + user management + system config |
| `operator` | Execute scripts, manage services, read/write files, edit crontab |
| `readonly` | View-only: no modifications, no script execution |

Role is stored in JWT claims and enforced on every API endpoint via FastAPI dependency injection.

---

## UI Layout & Theme

### Layout
- **Sidebar collapsable** (left) with module navigation icons + labels
- **Header bar** with app name, current page title, user avatar, dark/light toggle
- Sidebar collapses to icon-only mode to maximize content area
- Responsive for standard desktop/laptop screen sizes

### Theme
- **Default: Dark Pro** — deep black backgrounds (`#0d1117`, `#161b22`), blue/green accents (`#58a6ff`, `#3fb950`). GitHub Dark aesthetic.
- **Toggle:** dark ↔ light mode, persisted in localStorage
- Monospace font for logs, terminal output, and code editor areas

---

## Modules & Development Phases

### Phase 1 — Base Infrastructure + System Overview
**Deliverables:**
- FastAPI project scaffold with HTTPS, JWT auth, role middleware
- SQLite setup with users table, initial admin user seeded
- Vue 3 + Vite frontend with login page, layout shell (sidebar + header), dark/light toggle
- `/api/system` endpoint: CPU %, RAM %, disk usage, uptime, load average, OS info
- System Overview dashboard page with polling every 5s
- Metric cards with visual gauges/progress bars

### Phase 2 — Services Manager
**Deliverables:**
- `/api/services` endpoints: list all systemd services, get status, start/stop/restart
- Services page: list with status badges (active/inactive/failed), action buttons
- View journald logs for a selected service
- Role enforcement: `readonly` cannot start/stop/restart

### Phase 3 — File Explorer + Code Editor
**Deliverables:**
- `/api/files` endpoints: list directory, upload, download, move, rename, delete, get file content
- File explorer page: tree/list view, breadcrumb navigation, file permissions and owner display
- Monaco Editor embedded for viewing and editing text/code files
- Upload files via drag & drop or file picker
- Role enforcement: `readonly` cannot modify or upload

### Phase 4 — Script Favorites + Execution
**Deliverables:**
- `/api/scripts` endpoints: list favorites, add/remove, execute, get execution logs
- Scripts page: grid of favorite scripts (.py · .sh · .cpp · .cs and others)
- Monaco Editor embedded for editing scripts inline
- Execute button: runs script via `subprocess`, streams output to frontend via polling
- Execution log panel: stdout/stderr, exit code, timestamp, duration
- Execution history: persisted in SQLite, browseable per script
- Role enforcement: `readonly` cannot execute or edit; `operator` and `admin` can

### Phase 5 — Visual Crontab Editor
**Deliverables:**
- `/api/crontab` endpoints: list entries, create, update, delete
- Crontab page: list of scheduled tasks with human-readable descriptions
- Visual editor per task:
  - Calendar picker for day-of-month / day-of-week
  - Time picker (hour + minute)
  - Frequency selector: "every N minutes", "hourly", "daily", "weekly", "monthly", custom
  - Natural language preview: "Every Monday at 03:00"
  - Cron expression generated automatically, shown as reference
- Role enforcement: only `admin` and `operator` can modify crontab

---

## Persistence

| Store | Contents |
|-------|----------|
| `data/serverdash.db` (SQLite) | users, roles, script favorites, execution logs |
| `data/config.json` | server-side dashboard settings (allowed script paths, service filters, etc.) |
| `localStorage` (browser) | client-side preferences: dark/light theme toggle |

No external database dependency. Migratable to PostgreSQL in the future without architectural changes (SQLAlchemy abstraction layer).

---

## Security Considerations

- All API endpoints require valid JWT (except `/api/auth/login`)
- Role checks enforced server-side on every request, not just client-side
- File API: path traversal protection (all paths resolved and validated against allowed root)
- Script execution: whitelist of allowed script extensions, no shell injection via `subprocess` with argument lists (never `shell=True` with user input)
- Passwords hashed with bcrypt (min cost factor 12)
- HTTPS from day one; HTTP redirects to HTTPS
- Secrets (JWT secret key) stored in environment variables, never hardcoded

---

## Future Modules (plug-in, independent)

- **Disks & SMART** — disk partitions, usage, SMART data via `smartmontools`
- **Network & Ports** — active connections, open ports, interface stats
- **Linux User Management** — list/add/remove OS users, SSH key management
- **Docker Containers** — list, start/stop, logs via Docker SDK
- **Web Terminal** — in-browser terminal via xterm.js + pty (admin only)
- **Notifications & Alerts** — threshold alerts for CPU/RAM/disk, email or webhook
