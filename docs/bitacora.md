# ServerDash — Bitácora de Desarrollo & Roadmap

---

## Roadmap de Features

### Features en desarrollo
1) Pausar/reanudar programaciones de crontab

### Features Planificadas (Ordenadas por Prioridad)

#### 1. Network Monitoring (IMPLEMENTADO ✓)
**Descripción:** Visualizar interfaces de red, ancho de banda en tiempo real, conexiones activas, estadísticas históricas.

**Integración con la app:**
- Backend: Router `network/` con endpoints:
  - GET `/network/interfaces` - lista interfaces + IP + estadísticas
  - GET `/network/bandwidth` - bytes in/out por interfaz (última 1h, formato time-series)
  - GET `/network/connections` - netstat/ss parsing (conexiones activas)
- Scheduler: Cada 5-10s capturar estadísticas de `/proc/net/dev` o comando `ip`
- BD: Tabla `NetworkStats` para histórico (timestamp, interfaz, bytes_in, bytes_out)
- Frontend: Dashboard con gráficos (Chart.js/ApexCharts) + tabla de conexiones activas

**Dependencias:**
- `psutil` (para lectura de stats de red)
- `chart.js` o `ApexCharts` (frontend)

**Buenos hábitos:**
- Recolectar stats cada 10s, guardar en BD (mantener histórico 30 días)
- Cálcular deltas entre muestras (no valores absolutos)
- Limpieza automática de datos antiguos (retention policy)
- Índices en BD para queries rápidas (timestamp, interfaz)
- Tests: mock datos de `/proc/net/dev`

**Método de expansión:**
1. Scheduler que lee `/proc/net/dev` cada 10s y calcula deltas
2. Tabla BD NetworkStats + migration para índices
3. Endpoints GET que retornan datos actuales + histórico
4. Frontend: gráfico de ancho de banda histórico (últimas 24h)
5. Tabla de conexiones activas con filtro por protocolo
6. Opcional: alertas si ancho de banda excede umbral

---

#### 2. Resource Usage History (IMPLEMENTADO ✓)
**Descripción:** Gráficos históricos de CPU, RAM, disco a lo largo del tiempo (últimas 24h, 7 días, 30 días).

**Integración con la app:**
- Backend: Tabla `SystemMetricsHistory` - timestamp, cpu%, ram%, disk%
- Scheduler: Cada minuto capturar `/api/system/metrics` y guardar en BD
- Endpoints: GET `/history` con parámetros (granularidad, rango fechas)
- Frontend: Nueva sección en Dashboard o vista dedicada con gráficos (ApexCharts)

**Dependencias:**
- `ApexCharts` o `Chart.js` (frontend)

**Buenos hábitos:**
- Retention policy: guardar últimos 30 días (luego purgar)
- Índices en BD: (timestamp, metric)
- Agregación: promedios por hora para rango largo (no graficar 30k puntos)
- Caché en frontend (no refetch si ya tiene datos recientes)

**Método de expansión:**
1. Tabla SystemMetricsHistory
2. Scheduler que guarda metrics cada minuto
3. Cleanup job que purga datos >30 días
4. Endpoints para obtener histórico (con agregación si es necesario)
5. Frontend: gráficos de CPU/RAM/Disk (últimas 24h default, selector de rango)

---

#### 3. Gestión de Usuarios con Permisos Dinámicos
**Descripción:** Sistema multi-usuario con roles y permisos granulares. Control de acceso a rutas, funcionalidades específicas y áreas de trabajo.

**Integración con la app:**
- BD: Expandir modelo `User`: agregar tabla `Role`, `Permission`, `UserPermission` (M2M)
- Auth: JWT payload incluir `roles` + `permissions` (refrescar token al cambiar permisos)
- Backend: Middleware/decorator `@require_permission("scripts.execute", "files.read")`
- Frontend: Ocultar menú/componentes según permisos del usuario (ej: no mostrar "Services" si no tiene permiso)
- Router: Gate por ruta - si no tiene permiso, redirect a 403
- Endpoint guard: cada router valida permisos antes de lógica de negocio

**Dependencias:**
- No nuevas (usar SQLAlchemy, JWT existentes)

**Buenos hábitos:**
- Principio de menor privilegio: roles por defecto sin permisos
- Permisos granulares: `scripts.execute`, `scripts.read`, `files.write`, etc (no solo "admin/user")
- Auditoría: log quién cambió qué permisos cuándo
- Caché permisos en JWT + validación en cada request (no regresar a BD cada vez)
- Tests: crear usuarios con diferentes permisos, validar acceso negado

**Método de expansión:**
1. Definir lista de permisos (scripts, files, services, system, alerts, crontab, logs, etc)
2. Crear modelos Role/Permission + seed roles básicos (Admin, Operator, Viewer)
3. Implementar middleware de validación de permisos
4. Proteger endpoints con decorators
5. Frontend: componentes que se muestran/ocultan según permisos
6. Admin panel: CRUD usuarios + asignación de roles

---

#### 4. Alertas & Notificaciones
**Descripción:** Sistema de alertas en tiempo real cuando métricas exceden umbrales (CPU >80%, disco bajo, servicios caídos). Notificaciones inicialmente por email, con soporte futuro para webhooks.

**Integración con la app:**
- Backend: Nuevo router `alerts/` con endpoints para CRUD de alertas + configuración de thresholds
- BD: Nuevas tablas: `Alert` (config), `AlertHistory` (log de disparos), `AlertChannel` (email, webhook, etc)
- Frontend: Nueva vista `AlertsView.vue` + componente para gestionar reglas de alerta
- Scheduler: Validación periódica de métricas contra thresholds + envío de notificaciones
- Integración con `/api/system/metrics` - usar datos existentes como input

**Dependencias:**
- `smtplib` (email) - ya disponible en Python std
- `python-dotenv` para configuración SMTP (host, puerto, credenciales)
- Opcional: `requests` para webhooks futuros

**Buenos hábitos:**
- Almacenar credenciales SMTP en `.env` (nunca hardcodear)
- Deduplicación: no enviar 5 emails seguidos por misma alerta
- Rate limiting de notificaciones (máx 1 por alerta/minuto)
- Logs auditados de cada alerta disparada
- Tests: fixtures con mock SMTP

**Método de expansión:**
1. Implementar base de alertas (tablas, modelo ORM)
2. Scheduler que valida métricas
3. Notificador por email
4. Documentar formato de webhook (schema JSON) para futura integración
5. Frontend: UI para crear/editar/deshabilitar alertas

---

#### 5. Logs Centralizado
**Descripción:** Visualizar, filtrar, buscar y exportar logs del sistema (`/var/log/`) en tiempo real.

**Integración con la app:**
- Backend: Router `logs/` con endpoints para listar/filtrar/tail logs
- Lectura desde `/var/log/` con permisos seguros (no exponer logs arbitrarios)
- Frontend: Nueva vista `LogsView.vue` con tabla de logs + filtros (severidad, archivo, fecha rango)
- Real-time: WebSocket opcional para tail en vivo
- Export: CSV/JSON de logs filtrados

**Dependencias:**
- `watchdog` (opcional, para tail en vivo)

**Buenos hábitos:**
- Validar archivo solicitado (whitelist de logs seguros: `/var/log/syslog`, `/var/log/auth.log`, etc)
- No leer todo el archivo - paginar/tail (máx 10k líneas)
- Parse de formatos comunes (syslog, JSON)
- Logs de acceso a logs (auditoría)
- Tests: mock archivos de log, validar parsing

**Método de expansión:**
1. Identificar logs críticos a exponer
2. Parser de log lines (timestamp, severity, message)
3. Endpoint de lista + filtro
4. Frontend: tabla con columnas date/severity/source/message
5. Export CSV/JSON
6. Opcional: WebSocket para tail en vivo

---

#### 6. Process Manager
**Descripción:** Listar procesos activos, ver detalles (PID, usuario, CPU%, RAM%, comando), matar procesos.

**Integración con la app:**
- Backend: Router `processes/` con endpoints: GET lista, POST kill/{pid}
- Comando: `ps aux` + `/proc/{pid}/` parsing
- Frontend: Nueva vista con tabla de procesos, sort/filter, kill button
- Real-time: Actualizar cada 5-10s (lazy-load, caché)

**Dependencias:**
- `psutil` (mejor que parsear `ps` manualmente)

**Buenos hábitos:**
- Validar PID antes de matar (evitar matar procesos críticos sin confirmación)
- Permiso: solo admin puede matar procesos
- Confirmación UI: "¿Seguro que quieres matar PID 1234?"
- Log de acciones (quién mató qué proceso)
- No permitir matar servicios systemd - usar Services manager en su lugar

**Método de expansión:**
1. Endpoint que usa `psutil.process_iter()` con CPU%, RAM, usuario
2. Endpoint POST /kill/{pid} con validación
3. Frontend: tabla con sort/filter, botón kill
4. Refresh periódico (lazy-load, caché de 5s)

---

#### 7. Backups Automated (CON SOPORTE FUTURO "GIT-STYLE")
**Descripción:** Crear/restaurar backups de directorios. Buscar discos disponibles, centralizar copias, con arquitectura preparada para versionado estilo git.

**Integración con la app:**
- Backend: Router `backups/` con endpoints:
  - GET `/backups/disks` - listar discos + espacio libre
  - GET `/backups/configs` - lista de configuraciones de backup
  - POST `/backups/create/{config_id}` - crear backup manual
  - POST `/backups/restore/{backup_id}` - restaurar desde backup
  - GET `/backups/history` - listar backups completados
- BD: Tablas: `BackupConfig` (qué respaldar, cuándo, dónde), `Backup` (instancia de backup), `BackupFile` (metadata de archivos)
- Scheduler: Ejecutar backups programados según config
- Frontend: Vista de backups con calendario + tabla de historial

**Dependencias:**
- `tarfile` (compresión) o `shutil` (copia simple)
- `pathlib` (inspeccionar discos)
- `hashlib` (futuro: checksums para verificación)

**Buenos hábitos:**
- Arquitectura preparada para futuro "git-style":
  - Almacenar por commit/snapshot (hash de contenido)
  - Metadata de cambios (qué archivos cambiaron desde último backup)
  - Deduplicación: no duplicar archivos idénticos entre backups
- Validación: verificar integridad después de backup (checksum)
- Espacio: mostrar estimación antes de crear backup
- Documentar en BD: origen, destino, tamaño, timestamp, estado (success/error)
- Tests: crear backup de directorio temp, verificar contenido

**Método de expansión:**
1. Endpoint que detecta discos y espacio libre
2. CRUD de configuraciones de backup (qué/dónde/cuándo)
3. Scheduler ejecuta backups según config
4. Almacenar como tar.gz en disco central
5. Frontend: lista backups + botón restore
6. Futura expansión: arquitectura de snapshots versionados (prepare datos en BD para esto)

---

#### 8. Webhooks & Integraciones
**Descripción:** Disparar webhooks cuando ciertos eventos ocurren (alerta disparada, backup completado, proceso muerto, etc). Integración futura con Slack/Discord.

**Integración con la app:**
- Backend: Tabla `WebhookConfig` - URL destino, eventos a triggear, headers custom
- Sistema de eventos: Cuando ocurre evento (alerta, backup, etc), llamar a `trigger_webhook(event, data)`
- Queue: Usar scheduler/background task para enviar webhooks (no bloquear request)
- Frontend: Admin panel para crear/editar webhooks + test

**Dependencias:**
- `requests` (para POST a webhook)
- `celery` o similar (opcional, si se usa queue distributed)

**Buenos hábitos:**
- Retry logic: reintentar si webhook falla (exponential backoff)
- Timeout: no esperar más de 5s por respuesta
- Log de intentos: cuándo se disparó, status code, payload
- Validar URL antes de guardar
- Dejar documentado formato de payload para cada evento
- Signature de webhook: HMAC para validar que viene del dashboard

**Método de expansión:**
1. Tabla WebhookConfig
2. Identificar eventos clave (alertas, backups, cambios de usuario, etc)
3. Función `trigger_webhook(event, data)` que envía POST asincrónico
4. Log + retry logic
5. Frontend: CRUD webhooks + test button
6. Documentación: formato de payload por evento
7. Futuro: Slack/Discord adapters (transformar payload a formato compatible)

---

#### 9. Terminal Web SSH
**Descripción:** Terminal interactivo en el navegador para ejecutar comandos directamente. No urgente.

**Integración con la app:**
- Backend: WebSocket endpoint `/ws/terminal` - spawn shell, relay stdin/stdout/stderr
- Frontend: Terminal component (xterm.js o similar)
- Auth: Solo usuarios con permiso específico (`terminal.access`)

**Dependencias:**
- `websockets` (Python, ya disponible con FastAPI)
- `xterm.js` (frontend)
- `pty` módulo (Python) para spawn shell interactivo

**Buenos hábitos:**
- Rate limit de comandos (evitar spam)
- Log de todos los comandos ejecutados (auditoría)
- Timeout de sesión inactiva
- Restringir ciertos comandos peligrosos (blacklist)
- Permisos finamente granulares

**Método de expansión:**
1. WebSocket handler que spawns bash/sh
2. Relay de I/O bidireccional
3. Frontend component con xterm.js
4. Autenticación + permisos
5. Log de comandos en BD

---

#### 10. Package Manager
**Descripción:** Instalar/actualizar/remover paquetes (apt, yum, etc) desde el dashboard. No urgente.

**Integración con la app:**
- Backend: Router `packages/` - detectar package manager del SO (apt/yum/pacman)
- Endpoints: GET lista, POST install/{pkg}, POST remove/{pkg}, POST update/{pkg}
- Scheduler: Ejecutar comandos en background, guardar output en BD para historial
- Frontend: Tabla de paquetes instalados + buscador + botones install/remove/update

**Dependencias:**
- `subprocess` (ejecutar apt/yum)
- Permiso de sudo en el sistema

**Buenos hábitos:**
- Ejecutar en background con timeout
- Capturar stdout/stderr
- Log de auditoría: quién instaló/removió qué
- No permitir instalar cualquier paquete (whitelist de seguros)
- Confirmación UI antes de cambios

**Método de expansión:**
1. Detectar SO + package manager
2. Endpoint para listar paquetes (apt list --installed)
3. Install/remove con sudo + captura de output
4. Historial en BD
5. Frontend: tabla + search + botones

---

#### 11. Dark Mode Toggle
**Descripción:** Mejorar selector de tema con persistencia mejorada.

**Integración con la app:**
- Frontend: Toggleador persistente en header (localStorage)
- Backend: Opcional - guardar preferencia de tema por usuario en BD
- Aplicación: CSS variables + atributo `[data-theme="dark"]` en root

**Dependencias:**
- No nuevas

**Método de expansión:**
1. Persistir en localStorage
2. Opcional: guardar en BD si el usuario está autenticado
3. Aplicar al cargar página

---

#### 12. Environment Variables Manager
**Descripción:** Editar variables de entorno del sistema (`.bashrc`, `.profile`, etc). No urgente.

**Integración con la app:**
- Backend: Router `env/` - GET lista variables, POST actualizar
- Lectura desde: `~/.bashrc`, `~/.profile`, `/etc/environment`, etc
- Frontend: Tabla editable de variables + botón save

**Dependencias:**
- No nuevas

**Buenos hábitos:**
- Backup de archivos antes de editar (guardar versión anterior)
- Validar sintaxis (no quebrar shell scripts)
- Log de cambios: quién cambió qué variable cuándo
- Permisos: solo admin
- Requiere logout/re-login para que cambios tomen efecto

**Método de expansión:**
1. Parser de `.bashrc` y otros env files
2. Endpoint GET que retorna variables actuales
3. Endpoint POST para actualizar (con backup)
4. Frontend: tabla editable
5. Notificación: "Requiere logout para aplicar cambios"

---

# Historial de Desarrollo

## 2026-04-03

### Sesión anterior
- Implementación inicial de monitoreo de red (network monitoring)
- WebSocket para métricas en tiempo real
- Arreglos en gestión de usuarios (user management)

---

## 2026-04-04

### Características implementadas

#### ECG Live Charts (Dashboard)
- Card "LIVE METRICS" con Chart.js en estilo ECG (electrocardiógrafo)
- Buffer rodante de 120 puntos (2 minutos a 1Hz)
- Tres líneas: CPU (naranja), RAM (cian), Disk (verde)
- Plugins personalizados: fondo oscuro `#080c10`, glow por `shadowBlur` en canvas
- Actualización eficiente con `chart.update('none')` sin reactividad Vue
- Dot animado pulsante "LIVE" indicando conexión activa

#### Vista de Historial (`/history`)
- Nueva ruta `/history` con `HistoryView.vue`
- Dos gráficos de área: Resource History (CPU/RAM/Disk) y Bandwidth History
- Selectores de rango: 1h, 6h, 12h, 24h, 48h, 7d, 30d
- Selector de interfaz para historial de ancho de banda
- Fuentes de datos: `/api/metrics/history` y `/api/network/bandwidth`
- Entrada en sidebar: "History" con icono `pi-chart-bar`
- CTAs "View History →" en Dashboard y Network con animación de flecha

#### Network View — Rediseño completo
- Iconos dinámicos por tipo de interfaz (eth, wlan, tun/vpn, docker, genérico)
- Cards de interfaz rediseñadas: bloque bps prominente con fondo `#080c10`, TX naranja / RX azul, hover glow
- Traffic Analysis: gráfico ECG en vivo desde datos bps del WebSocket, buffer de 90 puntos
- Device Detection: tabla ARP devices vía `/api/network/devices`
- Config Management: panel DNS + gateways vía `/api/network/config`
- CTA "View Bandwidth History →" reemplaza historial inline

#### Consistencia visual
- DataTable deep overrides aplicados a AdminUsersView y NetworkView
  - `font-mono`, `text-2xs`, uppercase, letter-spacing 1.5px en headers
  - Padding uniforme `6px 10px` en th, `5px 10px` en td
- Tipografía y espaciado alineados con el resto de la app en todas las vistas nuevas

### Bugs corregidos

#### WebSocket en dev mode (Vite)
- **Problema:** "Live metrics connection error" en localhost:5173 — el proxy de Vite no reenviaba conexiones WebSocket
- **Fix:** Añadido `ws: true` en la entrada `/api` de `vite.config.js`

#### Network View se congelaba
- **Problema:** `startBw()` era llamado en `onMounted` pero la función había sido eliminada durante el refactor → `ReferenceError` → crash del componente → UI congelada, sin navegación
- **Fix:** Eliminada la llamada `startBw()` huérfana de `onMounted`

#### "No connections detected" (sin root)
- **Problema:** `psutil.net_connections()` requiere root en Linux → retornaba vacío silenciosamente
- **Fix:** Añadido `_read_connections_proc()` que parsea `/proc/net/tcp`, `/proc/net/tcp6`, `/proc/net/udp`, `/proc/net/udp6` directamente (funciona sin root). IPs little-endian hex, estados hex mapeados a strings.

#### Event loop bloqueado en WebSocket handlers
- **Problema:** `get_metrics()` y `get_interfaces()` son llamadas síncronas de psutil dentro de handlers async — bloqueaban el event loop de uvicorn
- **Fix:** Envueltos con `await run_in_threadpool(...)` en ambos endpoints de `backend/routers/ws.py`

#### AdminUsersView slot incorrecto (PrimeVue 4)
- **Problema:** Contenido en slot `#header` (solo para media) y slot default (no se renderiza) — PrimeVue 4 Card requiere `#content`
- **Fix:** Todo el contenido movido a `<template #content>`

### Archivos modificados
- `frontend/vite.config.js` — proxy ws: true
- `frontend/src/views/DashboardView.vue` — ECG live chart, eliminar historial inline, CTA history
- `frontend/src/views/HistoryView.vue` — NUEVA: vista unificada de historial
- `frontend/src/views/NetworkView.vue` — rediseño completo, bugfix startBw, ECG tráfico, ARP devices, config
- `frontend/src/views/AdminUsersView.vue` — deep DataTable overrides, fix slot PrimeVue
- `frontend/src/components/layout/AppSidebar.vue` — icono Network, entrada History
- `frontend/src/router/index.js` — ruta /history
- `backend/routers/ws.py` — run_in_threadpool para ambos WS endpoints
- `backend/services/network_service.py` — _read_connections_proc, get_arp_devices, get_network_config
- `backend/routers/network.py` — endpoints /devices y /config

---

## 2026-04-05

### Características implementadas

#### Composable `useChartTheme` (NUEVO)
- `frontend/src/composables/useChartTheme.js`
- Observa `data-theme` en `<html>` vía `MutationObserver` — reactivo instantáneo
- Retorna: `chartBg` (`#080c10` dark / `#f1f5f9` light), `axisColor`, `gridColorWeak`, `gridColorMid`
- Usado por Dashboard, Network y History para adaptar charts al tema

#### ECG Charts dinámicos (Dashboard + Network)
- Plugin `ecgBg` reemplaza `ecgDarkBg` — usa `chartBg.value` reactivo
- `watchEffect` actualiza colores de ejes y grid cuando cambia el tema
- Selector "VENTANA" (30s / 1m / 2m / MAX) — controla cuántos puntos visibles
- Leyenda clickeable para ocultar/mostrar series individuales (`chart.setDatasetVisibility`)

#### History View pulida
- Tema dinámico via `useChartTheme` + `watchEffect` en opciones de chart
- Labels inteligentes: `HH:MM` para rangos ≤48h, `DD Mon HH:MM` para 7d/30d
- Loading spinner (`ProgressSpinner`) mientras carga
- Header de página con back-link `← Dashboard`

#### PrimeVue nativo en inputs
- NetworkView: `InputText` envuelto en `IconField` + `InputIcon`
- AdminUsersView: `Toolbar` con `IconField` + `InputIcon` + `filteredUsers` computed

#### Network — Filtro de conexiones locales
- Toggle `ToggleButton` "− LOCAL / + LOCAL" en Active Connections
- `showLocal = false` por defecto — oculta `127.0.0.1` y `::1`
- Estas son conexiones internas de FastAPI/Vite, no tráfico real de red

#### Network — Interfaz con internet + subnet
- `_get_internet_ifaces()` detecta interfaces con ruta default en `/proc/net/route`
- `_get_subnet()` calcula CIDR con `ipaddress.IPv4Network`
- Badge "INTERNET" en cards de interfaces con gateway default
- Subnet mostrado en cada card (e.g. `172.29.160.0/20`)

#### UTC automático del sistema
- `datetime.now(timezone.utc).astimezone()` — respeta DST
- Retorna `utc_label`, `timezone_name`, `utc_offset_seconds`
- WS `/metrics` incluye los campos; Dashboard System card muestra "TIMEZONE"

### Verificación backend
- `UTC: UTC+0 UTC` — timezone detectado correctamente
- `eth0: is_internet_gateway=True, subnet=172.29.160.0/20` — red detectada correctamente

### Archivos modificados
- `frontend/src/composables/useChartTheme.js` — NUEVO
- `frontend/src/views/DashboardView.vue`
- `frontend/src/views/NetworkView.vue`
- `frontend/src/views/AdminUsersView.vue`
- `frontend/src/views/HistoryView.vue`
- `backend/services/system_service.py`
- `backend/schemas/system.py`
- `backend/services/network_service.py`
- `backend/schemas/network.py`
- `backend/routers/ws.py`

---

## 2026-04-06

### Tareas Completadas
- Consolidación de bitácoras: combinadas en un único archivo `/docs/bitacora.md`
- Actualización de CLAUDE.md: agregadas notas de desarrollo sobre documentación, frontend, backend y performance

### Feature: Pause/Resume de entradas crontab

**Descripción:** Permite pausar y reanudar entradas de crontab individualmente sin eliminarlas. El estado pausado se almacena directamente en el archivo crontab con un marcador `#PAUSED:` (sin espacio después de `#`, para distinguirlo de comentarios normales `# descripción`).

**Mecanismo:**
- Entrada activa: `0 * * * * /usr/bin/backup.sh`
- Entrada pausada: `#PAUSED:0 * * * * /usr/bin/backup.sh`
- El cron daemon ignora líneas con `#`, por lo que la entrada queda efectivamente deshabilitada
- El estado es completamente autónomo en el crontab (sin cambios de BD)

**Archivos modificados:**
- `backend/schemas/crontab.py` — campo `enabled: bool = True` en `CrontabEntry`
- `backend/services/crontab_service.py` — parser detecta `#PAUSED:` como entries con `enabled=False`; serializer emite `#PAUSED:` prefix cuando `enabled=False`; nueva función `toggle_entry(entry_id)`
- `backend/routers/crontab.py` — endpoint `PATCH /api/crontab/{id}/toggle` (requiere admin, retorna lista completa, audit log)
- `frontend/src/views/CrontabView.vue` — pills de filtro ALL/ACTIVE/PAUSED; botón pause/play por fila; filas pausadas con opacity 0.45 y expression tachada

**Sin cambios de BD, sin scheduler, sin índices nuevos.**

**Nota importante:** Cualquier nueva característica, bug fix importante o cambio significativo debe ser documentado en esta bitácora con descripción del cambio, archivos modificados y consideraciones importantes.
