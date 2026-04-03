# Bitácora de Sesión — 2026-04-03

## Estado del Proyecto al cierre de sesión

### Completado al 100%
- Phase 1: Base Infrastructure
- Phase 2: Services Manager
- Phase 3: File Explorer
- Resource Usage History (metrics_snapshots + scheduler + DashboardView charts)
- Performance Hardening (indexes, TTLCache, lazy-load, retention)
- User Management with Permissions (models, admin CRUD, /auth/me, frontend)
- **Network Monitoring** (IMPLEMENTADO HOY — model, service, router, scheduler, NetworkView enterprise)

### Upgrades implementados hoy
- **WebSocket real-time**: DashboardView ahora recibe metrics via WS cada 1s (antes polling 5s)
- **NetworkView WebSocket**: interface stats y bps en tiempo real cada 2s via /api/ws/network
- **dev-start.sh**: script para levantar la app en modo dev

### Pendiente
- Monaco Editor fix (antifix commit pendiente — FilesView editor panel)
- Security P2 improvements (JWT → httpOnly cookie, documentados como aceptados por ahora)
- Performance & Memory Optimization — debounce API calls frontend (parcial)

## Archivos clave modificados esta sesión
- backend/models/network_snapshot.py (NEW)
- backend/services/network_service.py (NEW)
- backend/schemas/network.py (NEW)
- backend/routers/network.py (NEW)
- backend/routers/ws.py (NEW)
- backend/scheduler.py (network jobs added)
- backend/config.py (network_retention_days)
- backend/scripts/add_indexes.py (network indexes)
- frontend/src/views/NetworkView.vue (NEW — enterprise)
- frontend/src/views/DashboardView.vue (WS upgrade)
- frontend/src/router/index.js (/network route)
- frontend/src/components/layout/AppSidebar.vue (Network item)
- tests/conftest.py (network cache reset)
- dev-start.sh (prerequisite checks fix)

## Tests
- pytest: 99 passed
- frontend build: OK (exit code 0)
