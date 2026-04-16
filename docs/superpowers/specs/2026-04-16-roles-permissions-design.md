# Design: Roles & Permissions System
**Date:** 2026-04-16  
**Branch:** feat/pipeline-system  
**Status:** Approved

---

## Overview

ServerDash already has the infrastructure for a granular permission system (`Permission` model, `check_permission`, `require_permission` in `dependencies.py`, `hasPermission` in the auth store). The problem is it was never wired up end-to-end: the Permission table is never seeded, `require_permission` is never used in routers, and the frontend has consistency issues.

This design completes that system: seed defaults, wire every endpoint to `require_permission`, add an admin UI to edit permissions per role, and document the rule that every new feature must define its permissions.

---

## Section 1 — Data Layer & Core Logic

### Permission table (no schema change)
Existing: `permissions(id, role, resource, action)` with indexes on `(role)` and `(role, resource)`.

### Default permission matrix

| Resource | Action | admin | operator | readonly |
|----------|--------|:-----:|:--------:|:--------:|
| system | read | ✓ | ✓ | ✓ |
| services | read | ✓ | ✓ | ✓ |
| services | write | ✓ | ✓ | ✗ |
| services | execute | ✓ | ✓ | ✗ |
| files | read | ✓ | ✓ | ✓ |
| files | write | ✓ | ✓ | ✗ |
| files | delete | ✓ | ✗ | ✗ |
| network | read | ✓ | ✓ | ✓ |
| scripts | read | ✓ | ✓ | ✓ |
| scripts | write | ✓ | ✓ | ✗ |
| scripts | delete | ✓ | ✗ | ✗ |
| scripts | execute | ✓ | ✓ | ✗ |
| crontab | read | ✓ | ✓ | ✓ |
| crontab | write | ✓ | ✗ | ✗ |
| crontab | delete | ✓ | ✗ | ✗ |
| logs | read | ✓ | ✓ | ✓ |
| pipelines | read | ✓ | ✓ | ✓ |
| pipelines | write | ✓ | ✗ | ✗ |
| pipelines | delete | ✓ | ✗ | ✗ |
| pipelines | execute | ✓ | ✓ | ✗ |
| users | read | ✓ | ✗ | ✗ |
| users | write | ✓ | ✗ | ✗ |
| users | delete | ✓ | ✗ | ✗ |

### Seeding (`init_db.py`)
Add `seed_default_permissions(db)` that only inserts if the table is empty. Admin permissions are NOT inserted (admin bypasses the table entirely).

### Admin bypass (`dependencies.py`)
`check_permission` returns `True` immediately if `user.role == UserRole.admin`, before hitting the DB or cache. Admin can never be locked out.

### Cache invalidation
When `PUT /api/admin/permissions/{role}` is called, invoke `_perm_cache.clear()` to force re-read on next request.

### New permission management endpoints (`admin.py`)
```
GET  /api/admin/permissions           → { role: [{resource, action}] } for all roles
PUT  /api/admin/permissions/{role}    → replace all permissions for that role
```
Protected with `require_role("admin")` (not `require_permission` — intentional, to avoid chicken-and-egg lock-out).

---

## Section 2 — Backend Router Changes

All endpoints migrate from `require_role` / `get_current_user` to `require_permission(resource, action)`.

### `services.py`
- `GET /services/` → `require_permission("services", "read")`
- `GET /services/{name}/logs` → `require_permission("services", "read")`
- `POST /services/{name}/{action}` → `require_permission("services", "execute")`

### `files.py`
- `GET /files/` → `require_permission("files", "read")`
- `GET /files/download` → `require_permission("files", "read")`
- `POST /files/mkdir` → `require_permission("files", "write")`
- `POST /files/rename` → `require_permission("files", "write")`
- `POST /files/upload` → `require_permission("files", "write")`
- `DELETE /files/` → `require_permission("files", "delete")`

### `scripts.py`
- `GET /scripts/favorites` → `require_permission("scripts", "read")`
- `POST /scripts/favorites` → `require_permission("scripts", "write")`
- `DELETE /scripts/favorites/{id}` → `require_permission("scripts", "delete")`
- `PATCH /scripts/favorites/{id}` → `require_permission("scripts", "write")`
- `POST /scripts/favorites/{id}/run` → `require_permission("scripts", "execute")` + retain `admin_only` check
- WebSocket `run-ws` → same permission check on JWT validation step

### `crontab.py`
- `GET /crontab/` → `require_permission("crontab", "read")`
- `POST /crontab/` → `require_permission("crontab", "write")`
- `PUT /crontab/{id}` → `require_permission("crontab", "write")`
- `DELETE /crontab/{id}` → `require_permission("crontab", "delete")`
- `POST /crontab/{id}/toggle` → `require_permission("crontab", "write")`

### `pipelines.py`
- `GET /pipelines/` → `require_permission("pipelines", "read")`
- `POST /pipelines/` → `require_permission("pipelines", "write")`
- `POST /pipelines/import` → `require_permission("pipelines", "write")`
- `PUT /pipelines/{id}` → `require_permission("pipelines", "write")`
- `DELETE /pipelines/{id}` → `require_permission("pipelines", "delete")`
- `POST /pipelines/{id}/run` → `require_permission("pipelines", "execute")`

### `system.py`, `logs.py`, `network.py`, `metrics_history.py`
- All `GET` endpoints → `require_permission("<resource>", "read")` where resource matches the router domain.

### `admin.py`
- No changes. User and permission management stays under `require_role("admin")`.

---

## Section 3 — Frontend Changes

### 3a. Fix consistency bugs
- Replace `auth.role === 'admin'` with `auth.isAdmin` in `CrontabView.vue`, `PipelinesView.vue`, `ScriptsView.vue` (these are non-reactive reads today).

### 3b. Vue Router guards
Add a navigation guard in `router/index.js`:
- `/admin/*` routes redirect to `/` if `!auth.isAdmin`.
- Any route whose sidebar item was filtered by `hasPermission(resource, 'read')` also gets a guard that redirects if the permission is missing.

### 3c. Fix action-level hasPermission in views
Views that show write/delete/execute buttons should call `auth.hasPermission(resource, action)` for the specific action, not just check `isAdmin`. Example: a `write` button in Files should check `hasPermission('files', 'write')`.

### 3d. New `AdminPermissionsView.vue`
A permission matrix editor accessible at `/admin/permissions`:
- Rows: every `resource × action` combination from the default matrix
- Columns: `operator`, `readonly` (admin column is shown but all checkboxes are disabled/checked)
- Checkboxes are togglable; on change they call `PUT /api/admin/permissions/{role}`
- On load, calls `GET /api/admin/permissions`

### 3e. Sidebar update
Add "Permissions" link under the ADMIN section in `AppSidebar.vue` pointing to `/admin/permissions`.

---

## Section 4 — Developer Rule: Permissions for New Features

Every new feature added to ServerDash MUST:

1. **Identify or create a resource name** (e.g., `backups`, `alerts`)
2. **Define which actions apply** from: `read`, `write`, `delete`, `execute`
3. **Add default permissions** to `DEFAULT_PERMISSIONS` in `init_db.py` for `operator` and `readonly` roles
4. **Use `require_permission(resource, action)`** in every new backend endpoint — never bare `get_current_user` for protected resources
5. **Use `auth.hasPermission(resource, action)`** in the frontend to conditionally render action buttons and filter nav items
6. **Document the permissions** in the default matrix table above

This rule is enforced in `CLAUDE.md`.

---

## Files to Create / Modify

### Backend
- `backend/scripts/init_db.py` — add `seed_default_permissions()`
- `backend/dependencies.py` — admin bypass in `check_permission`
- `backend/routers/admin.py` — add permission CRUD endpoints + cache clear
- `backend/routers/services.py` — migrate to `require_permission`
- `backend/routers/files.py` — migrate to `require_permission`
- `backend/routers/scripts.py` — migrate to `require_permission`
- `backend/routers/crontab.py` — migrate to `require_permission`
- `backend/routers/pipelines.py` — migrate to `require_permission`
- `backend/routers/system.py` — migrate to `require_permission`
- `backend/routers/logs.py` — migrate to `require_permission`
- `backend/routers/network.py` — migrate to `require_permission`
- `backend/routers/metrics_history.py` — migrate to `require_permission`

### Frontend
- `frontend/src/views/CrontabView.vue` — fix `isAdmin` usage
- `frontend/src/views/PipelinesView.vue` — fix `isAdmin` usage
- `frontend/src/views/ScriptsView.vue` — fix `isAdmin` usage
- `frontend/src/router/index.js` — add navigation guards
- `frontend/src/components/layout/AppSidebar.vue` — add Permissions link
- `frontend/src/views/AdminPermissionsView.vue` — new file

### Documentation
- `CLAUDE.md` — add permissions rule for new features
- `docs/bitacora.md` — log this change
