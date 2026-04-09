# Plan: ServerDash — Mejoras Integrales v1

**Fecha:** 2026-04-05  
**Scope:** Frontend UX, Network intelligence, System UTC

---

## ⚠️ SKILLS OBLIGATORIAS — leer ANTES de escribir cualquier línea de código

### Para TODO el trabajo (backend + frontend):
```
serverdash-performance   (.claude/skills/serverdash-performance/SKILL.md)
```
Contiene reglas vinculantes sobre: índices DB, caché de queries, patrones de scheduler, lazy-loading frontend, bounded state. **Ignorarla introduce bugs silenciosos de performance.**

### Para todo trabajo de UI/UX (frontend):
```
ui-ux-pro-max   (disponible via Skill tool: ui-ux-pro-max:ui-ux-pro-max)
```
Contiene el design system de la app: Dark OLED, tipografías Fira Code/Fira Sans, brand orange `#f97316`, CSS variables `--font-mono`, `--font-ui`, `--brand-orange`, tamaños de texto. **Todo componente nuevo debe respetar estas reglas.**

### Cuándo cargar cada skill:
| Trabajo | Skills requeridas |
|---------|-----------------|
| Backend (services, routers, schemas) | `serverdash-performance` |
| Frontend (views, components, composables) | `serverdash-performance` + `ui-ux-pro-max` |
| Cualquier nueva tabla / índice DB | `serverdash-performance` (ver patrón `add_indexes.py`) |

---

## ⚡ ESTRATEGIA DE EJECUCIÓN — Máximo paralelismo con multiagentes

**Regla:** Todo lo que no tenga dependencia directa se ejecuta en paralelo usando el Agent tool con múltiples llamadas simultáneas.

### Wave 1 — Backend puro (todo en paralelo, sin dependencias entre sí):
```
Agent A: system_service.py + schemas/system.py  → UTC offset
Agent B: network_service.py + schemas/network.py → internet gateway + subnet
```
Ambos agentes operan sobre archivos distintos → 100% paralelo.

### Wave 2 — WS payload (depende de Wave 1):
```
Agent C: routers/ws.py → incluir campos UTC + network nuevos en ambos payloads
```
Debe esperar que Wave 1 termine (los schemas ya actualizados).

### Wave 3 — Composable nuevo (independiente, puede ir junto con Wave 2):
```
Agent D: composables/useChartTheme.js → tema reactivo
```
No depende de nada del backend ni de otras views.

### Wave 4 — Frontend views (todas en paralelo, dependen de Wave 3):
```
Agent E: DashboardView.vue  → useChartTheme + windowSize + toggleSeries + UTC display
Agent F: NetworkView.vue    → useChartTheme + windowSize + toggleSeries + IconField + showLocal + internet badge
Agent G: AdminUsersView.vue → Toolbar + IconField + filteredUsers
Agent H: HistoryView.vue    → useChartTheme + smart labels + loading
```
Todos operan sobre archivos distintos → 100% paralelo entre sí (requieren que useChartTheme.js exista).

### Diagrama de dependencias:
```
Wave 1: [Agent A]  [Agent B]
              ↘    ↙
Wave 2:   [Agent C]   [Agent D]  ← paralelo con C
                           ↓
Wave 4: [Agent E] [Agent F] [Agent G] [Agent H]  ← todos paralelos
```

**Total: 4 waves en vez de 8 pasos secuenciales.**

---

## Resumen ejecutivo

Tres categorías de trabajo, con impacto visual y funcional concreto en cada una:

1. **Frontend**: Inputs nativos PrimeVue, ECG charts con tema dinámico + ventana configurable + filtro por serie, History view pulida.
2. **Networking**: Detección inteligente de interfaz de internet, filtro de conexiones locales (loopback), visualización de topología de red.
3. **UTC del sistema**: El backend detecta y expone el timezone automáticamente; el frontend lo muestra.

---

## CATEGORÍA 1 — FRONTEND

### 1.1 Textboxes con PrimeVue nativo (referencia: ServicesView)

**Patrón de referencia** (ServicesView.vue):
```html
<IconField>
  <InputIcon class="pi pi-search" />
  <InputText v-model="filter" placeholder="Filter..." size="small" />
</IconField>
```

**Cambios:**

**NetworkView.vue** — Sección "Active Connections":
- El `<InputText class="conn-search">` actual no tiene `IconField`/`InputIcon`
- Reemplazar con `IconField` + `InputIcon class="pi pi-search"` + `InputText`
- Agregar también un `<Toolbar>` de PrimeVue para agrupar los controles (filter + selects), igual que ServicesView

**AdminUsersView.vue** — Tabla de usuarios:
- No tiene ningún filtro de búsqueda en la tabla → agregar Toolbar con `IconField` + search
- Conectar a computed `filteredUsers` (igual que `filtered` en ServicesView)

**Archivos:**
| Archivo | Operación |
|---------|-----------|
| `frontend/src/views/NetworkView.vue` | Modificar: Envolver conn-search en IconField+Toolbar |
| `frontend/src/views/AdminUsersView.vue` | Modificar: Agregar Toolbar + IconField search + filteredUsers computed |

---

### 1.2 ECG Charts — Dinámicos, Ventana configurable, Filtro por serie

**Problemas actuales:**
1. Fondo `#080c10` hardcodeado → no responde al tema claro
2. Colores de ejes `#555` hardcodeados → no adaptan
3. Buffer fixed de 120/90 puntos sin selector de usuario
4. No hay forma de ocultar/mostrar series individuales

**Solución — composable `useChartTheme.js` (NUEVO):**

```js
// frontend/src/composables/useChartTheme.js
import { ref, onMounted, onUnmounted } from 'vue'

export function useChartTheme() {
  const isDark = ref(true)
  
  function update() {
    isDark.value = document.documentElement.dataset.theme !== 'light'
  }
  
  let obs
  onMounted(() => {
    update()
    obs = new MutationObserver(update)
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
  })
  onUnmounted(() => obs?.disconnect())
  
  const chartBg = computed(() => isDark.value ? '#080c10' : '#f1f5f9')
  const axisColor = computed(() => isDark.value ? '#64748b' : '#94a3b8')
  const gridColor = computed(() => isDark.value ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.06)')
  
  return { isDark, chartBg, axisColor, gridColor }
}
```

**Ventana configurable ("VENTANA" — no "abscisas"):**
- Ref `windowSize` con opciones: `[30, 60, 90, 120]` segundos
- `Select` label "VENTANA" con icono `pi-window-maximize`
- El buffer interno sigue siendo `LIVE_BUFFER = 120` (máximo acumulado)
- Al hacer push, solo se pasan al chart las últimas `windowSize` entradas:
  ```js
  // En pushLivePoint():
  const w = windowSize.value
  liveChartData.labels = live.labels.slice(-w)
  liveChartData.datasets[0].data = live.cpu.slice(-w)
  // ... etc
  // entonces chart.update('none')
  ```
  > **Nota:** Como `liveChartData` es un objeto plain (no reactivo), reasignar `.labels` y `.data` y llamar `chart.update('none')` funciona correctamente.

**Filtro por serie:**
- Estado `hiddenSeries` = Set de labels ocultas (`ref(new Set())`)
- Leyenda personalizada clickeable: al clickear togglea la visibilidad
  ```js
  function toggleSeries(label) {
    const chart = liveChartRef.value?.chart
    const idx = chart.data.datasets.findIndex(d => d.label === label)
    if (idx >= 0) {
      chart.setDatasetVisibility(idx, !chart.isDatasetVisible(idx))
      chart.update('none')
    }
  }
  ```
- La leyenda (ya existente `.ecg-legend`) cambia la clase CSS a `legend-hidden` con `opacity: 0.3`

**Plugin ECG adaptado al tema:**
```js
// ecgDarkBg se vuelve ecgBg y usa chartBg.value
{
  id: 'ecgBg',
  beforeDraw(chart) {
    ctx.fillStyle = chartBg.value  // reactivo
    // ... fill chart area
  }
}
```

**Opciones de ejes adaptadas:**
- Usar `watchEffect` sobre `isDark` para actualizar `chart.options.scales.x.ticks.color` y llamar `chart.update()`

**Aplica a:**
- `DashboardView.vue` — gráfico LIVE METRICS
- `NetworkView.vue` — gráfico TRAFFIC ANALYSIS

**Archivos:**
| Archivo | Operación |
|---------|-----------|
| `frontend/src/composables/useChartTheme.js` | NUEVO |
| `frontend/src/views/DashboardView.vue` | Modificar: useChartTheme, windowSize, toggleSeries |
| `frontend/src/views/NetworkView.vue` | Modificar: useChartTheme, windowSize, toggleSeries |

---

### 1.3 History View — Pulido visual + tema dinámico

**Problemas actuales:**
- Colores de ejes hardcodeados (`rgba(255,255,255,0.05)`)
- Labels de tiempo: muestra solo `HH:MM` siempre → para rangos de 7d/30d debería mostrar `DD/MM HH:MM`
- No hay loading state
- No hay título de page con back-link

**Mejoras:**

**Tema dinámico:** Usar `useChartTheme()` + `watchEffect` para actualizar `areaOptions.scales.y.grid.color` y similares cuando cambia el tema:
```js
watchEffect(() => {
  areaOptions.scales.x.ticks.color = axisColor.value
  areaOptions.scales.y.ticks.color = axisColor.value
  areaOptions.scales.x.grid.color = gridColor.value
  // Llamar update en la instancia del chart si existe
  resourceChartRef.value?.chart?.update()
  bandwidthChartRef.value?.chart?.update()
})
```

**Labels de tiempo inteligentes:**
```js
function formatHistoryLabel(isoStr, hours) {
  const d = new Date(isoStr)
  if (hours <= 6) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  if (hours <= 48) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  // Para 7d y 30d: mostrar fecha + hora
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' }) + 
         ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}
```

**Loading state:** `<ProgressSpinner>` de PrimeVue mientras `loading.value` sea true.

**Header de página:** Agregar un row con `pi-arrow-left` link al dashboard + título grande "HISTORY".

**Archivos:**
| Archivo | Operación |
|---------|-----------|
| `frontend/src/views/HistoryView.vue` | Modificar: useChartTheme, smart labels, loading, header |

---

## CATEGORÍA 2 — NETWORKING

### 2.1 Detección de interfaz de internet + visualización mejorada

**Backend — `network_service.py`:**

La función `get_network_config()` ya lee `/proc/net/route` para detectar gateways por defecto. Extender `get_interfaces()` para marcar cuál interfaz tiene el gateway por defecto:

```python
def _get_internet_ifaces() -> set[str]:
    """Return set of interface names that have a default route."""
    ifaces = set()
    try:
        with open("/proc/net/route") as f:
            next(f)
            for line in f:
                parts = line.split()
                if len(parts) >= 4 and parts[1] == "00000000":
                    ifaces.add(parts[0])
    except (OSError, IOError):
        pass
    return ifaces

def get_interfaces() -> list[dict]:
    internet_ifaces = _get_internet_ifaces()
    # ... existing code ...
    result.append({
        # ... existing fields ...
        "is_internet_gateway": name in internet_ifaces,
        "subnet": _get_subnet(name, addrs),  # ver abajo
    })
```

**Subnet detection:**
```python
def _get_subnet(name: str, addrs) -> str:
    """Return subnet in CIDR notation e.g. '192.168.1.0/24'"""
    import ipaddress
    if name not in addrs:
        return ""
    for addr in addrs[name]:
        if addr.family.name == "AF_INET" and addr.address and addr.netmask:
            try:
                net = ipaddress.IPv4Network(f"{addr.address}/{addr.netmask}", strict=False)
                return str(net)
            except ValueError:
                pass
    return ""
```

**Schema — `schemas/network.py`:**
```python
class InterfaceInfo(BaseModel):
    # ... campos existentes ...
    is_internet_gateway: bool = False
    subnet: str = ""
```

**Frontend — `NetworkView.vue`:**
- Las interface cards marcan con badge especial "INTERNET" (color verde) si `iface.is_internet_gateway`
- Mostrar subnet en la card si existe
- Icono dinámico ya existente funciona bien (eth→pi-server, etc.)

**Archivos:**
| Archivo | Operación |
|---------|-----------|
| `backend/services/network_service.py` | Modificar: `_get_internet_ifaces()`, `_get_subnet()`, `get_interfaces()` |
| `backend/schemas/network.py` | Modificar: `InterfaceInfo` + `is_internet_gateway` + `subnet` |
| `frontend/src/views/NetworkView.vue` | Modificar: mostrar badge INTERNET + subnet |

---

### 2.2 Active Connections — Filtrar ruido de conexiones locales

**Análisis del problema:**
- `127.0.0.1:*` = loopback — conexiones internas de la propia máquina (FastAPI ↔ sí mismo, Vite HMR, etc.)
- Puerto 5173 = Vite dev server
- Puerto 8443 = FastAPI backend
- Puerto 52974, 54836 = puertos efímeros de conexiones locales
- **NO son conexiones reales de red** — generan ruido visual sin valor operacional

**Solución:**
Agregar toggle en el header de "Active Connections" para mostrar/ocultar locales.

**Frontend — `NetworkView.vue`:**
```js
const showLocal = ref(false)  // default: ocultar locales

const filteredConnections = computed(() => {
  let list = connections.value
  
  // Filtrar loopback por defecto
  if (!showLocal.value) {
    list = list.filter(c => {
      const localIp = c.local_addr.split(':')[0]
      const remoteIp = c.remote_addr.split(':')[0]
      return localIp !== '127.0.0.1' && localIp !== '::1' &&
             remoteIp !== '127.0.0.1' && remoteIp !== '::1' &&
             c.local_addr !== '' 
    })
  }
  
  // Filtros existentes
  if (connStatusFilter.value) list = list.filter(c => c.status === connStatusFilter.value)
  if (connProtoFilter.value) list = list.filter(c => c.proto === connProtoFilter.value)
  if (connSearch.value) {
    const q = connSearch.value.toLowerCase()
    list = list.filter(c => c.local_addr.includes(q) || c.remote_addr.includes(q))
  }
  return list
})
```

**UI:** Agregar `ToggleButton` (PrimeVue nativo) o `ToggleSwitch` en el header:
```html
<ToggleButton v-model="showLocal" 
  on-label="+ LOCAL" off-label="— LOCAL"
  on-icon="pi pi-eye" off-icon="pi pi-eye-slash"
  size="small" />
```

**Archivos:**
| Archivo | Operación |
|---------|-----------|
| `frontend/src/views/NetworkView.vue` | Modificar: `showLocal` ref + `filteredConnections` update + ToggleButton en header |

---

### 2.3 Visualización de topología (Enhanced)

> **Scope reducido** — el escaneo de red completo (nmap, arp-scan) requiere permisos de root y puede ser muy lento. En cambio implementar lo que funciona sin root y es rápido.

**Lo que implementamos:**
1. Badge "INTERNET" en la interfaz con gateway por defecto (ya cubierto en 2.1)
2. Mostrar subnet range en cada card
3. En la sección "Device Detection", mostrar a qué interfaz pertenece cada device (ya tenemos `interface` en ARP response)
4. Nuevo label: "LAN DEVICES POR INTERFAZ" agrupando los ARP devices por su interfaz

**No implementamos** (por ahora):
- Escaneo activo de puertos (requiere herramientas externas)
- Mapa visual de topología (demasiado scope)

---

## CATEGORÍA 3 — HORA DEL SISTEMA / UTC

### 3.1 Backend — Exponer UTC offset automáticamente

**`backend/services/system_service.py`:**
```python
import time as _time
from datetime import timezone, datetime

def get_utc_offset() -> dict:
    """Return the system's UTC offset."""
    now = datetime.now(timezone.utc).astimezone()
    offset_seconds = int(now.utcoffset().total_seconds())
    hours = offset_seconds // 3600
    minutes = abs(offset_seconds % 3600) // 60
    sign = '+' if offset_seconds >= 0 else '-'
    label = f"UTC{sign}{abs(hours):02d}:{minutes:02d}" if minutes else f"UTC{sign}{abs(hours)}"
    return {
        "offset_seconds": offset_seconds,
        "label": label,  # e.g. "UTC-03:00"
        "timezone_name": _time.tzname[0],  # e.g. "ART"
    }
```

Incluir en `get_metrics()` como campo `utc_info: dict`.

**`backend/schemas/system.py`:**
```python
class SystemMetrics(BaseModel):
    # ... campos existentes ...
    utc_offset_seconds: int = 0
    utc_label: str = "UTC+00:00"
    timezone_name: str = ""
```

**`backend/routers/ws.py`:**
Incluir `utc_offset_seconds`, `utc_label`, `timezone_name` en el payload del WS `/metrics`.

### 3.2 Frontend — Mostrar timezone en System card

**`DashboardView.vue`** — System card, info-grid:
- Agregar item "TIMEZONE" mostrando `metrics.utc_label` (e.g. "UTC-03:00 ART")
- El WS ya incluye el dato, solo hay que añadir el campo al estado `metrics`

```html
<div class="info-item">
  <span class="info-key">TIMEZONE</span>
  <span class="info-val">{{ metrics.utc_label || '—' }}</span>
</div>
```

**Archivos:**
| Archivo | Operación |
|---------|-----------|
| `backend/services/system_service.py` | Modificar: calcular y retornar utc_label + timezone_name |
| `backend/schemas/system.py` | Modificar: agregar utc_offset_seconds, utc_label, timezone_name |
| `backend/routers/ws.py` | Modificar: incluir campos UTC en payload /metrics |
| `frontend/src/views/DashboardView.vue` | Modificar: agregar TIMEZONE a info-grid + estado metrics |

---

## Orden de implementación — con skills y paralelismo explícitos

### Wave 1 — Backend (ejecutar en paralelo con 2 agentes)

**Agent A** — Leer skill `serverdash-performance` → modificar:
- `backend/services/system_service.py` → UTC offset
- `backend/schemas/system.py` → campos UTC

**Agent B** — Leer skill `serverdash-performance` → modificar:
- `backend/services/network_service.py` → `_get_internet_ifaces()`, `_get_subnet()`, `get_interfaces()`
- `backend/schemas/network.py` → `InterfaceInfo` nuevos campos

### Wave 2 — WS router + composable (ejecutar en paralelo con 2 agentes)

**Agent C** — Leer skill `serverdash-performance` → modificar:
- `backend/routers/ws.py` → payload `/metrics` + `/network` con nuevos campos

**Agent D** — Leer skills `serverdash-performance` + `ui-ux-pro-max` → crear:
- `frontend/src/composables/useChartTheme.js` → composable reactivo de tema

### Wave 3 — Frontend views (ejecutar en paralelo con 4 agentes)

**Agent E** — Leer skills `serverdash-performance` + `ui-ux-pro-max` → modificar:
- `frontend/src/views/DashboardView.vue` → useChartTheme + windowSize + toggleSeries + UTC

**Agent F** — Leer skills `serverdash-performance` + `ui-ux-pro-max` → modificar:
- `frontend/src/views/NetworkView.vue` → useChartTheme + windowSize + toggleSeries + IconField + showLocal + internet badge

**Agent G** — Leer skills `serverdash-performance` + `ui-ux-pro-max` → modificar:
- `frontend/src/views/AdminUsersView.vue` → Toolbar + IconField + filteredUsers

**Agent H** — Leer skills `serverdash-performance` + `ui-ux-pro-max` → modificar:
- `frontend/src/views/HistoryView.vue` → useChartTheme + smart labels + loading + header

---

## Resumen de archivos

| Archivo | Operación | Categoría |
|---------|-----------|-----------|
| `backend/services/system_service.py` | Modificar | UTC |
| `backend/schemas/system.py` | Modificar | UTC |
| `backend/services/network_service.py` | Modificar | Network |
| `backend/schemas/network.py` | Modificar | Network |
| `backend/routers/ws.py` | Modificar | UTC + Network |
| `frontend/src/composables/useChartTheme.js` | NUEVO | Frontend |
| `frontend/src/views/DashboardView.vue` | Modificar | Frontend + UTC |
| `frontend/src/views/NetworkView.vue` | Modificar | Frontend + Network |
| `frontend/src/views/AdminUsersView.vue` | Modificar | Frontend |
| `frontend/src/views/HistoryView.vue` | Modificar | Frontend |

---

## Notas técnicas importantes

- **`useChartTheme`** observa `document.documentElement.dataset.theme` vía `MutationObserver` — no hay que pasar nada como prop
- **windowSize vs LIVE_BUFFER**: `LIVE_BUFFER` sigue siendo 120 (buffer interno); `windowSize` solo controla cuántos puntos se muestran en el chart (slice del buffer)
- **Chart.js reactivity**: Los datasets deben modificarse in-place (mutación de arrays) o reasignando `.data` y llamando `chart.update('none')`. Evitar reemplazar el objeto `liveChartData` completo
- **UTC offset**: Python `datetime.now(timezone.utc).astimezone().utcoffset()` es el método correcto (respeta DST); `time.timezone` es estático y no respeta DST
- **Loopback filter**: Filtrar `127.x` y `::1`; el socket `0.0.0.0` (LISTEN) se debe dejar visible
- **`_read_connections_proc` y tcp6**: Los IPs de IPv6 con formato 4-in-6 (`::ffff:127.0.0.1`) también deben ser filtrados como locales

---

## Riesgos y mitigación

| Riesgo | Mitigación |
|--------|------------|
| MutationObserver no detecta theme changes | Verificar que la app cambia `data-theme` en el elemento raíz al togglear modo |
| Chart.js no actualiza al cambiar colores de opciones | Llamar `chart.update()` (con animación) después de cambiar opciones de escala |
| `ipaddress.IPv4Network` falla en interfaces sin netmask | Try/except con fallback a `""` |
| Subnet de WSL/Docker IPs puede ser confuso | Mostrar tal cual, no hacer inferencias |

---

**Plan generado y guardado en `.claude/plan/serverdash-improvements-v1.md`**
