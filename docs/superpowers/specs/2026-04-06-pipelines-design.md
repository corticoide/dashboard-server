# Sistema de Pipelines Programables — Design Spec

**Date:** 2026-04-06  
**Status:** Approved

---

## Overview

Sistema de automatización basado en pipelines: secuencias ordenadas de pasos con condiciones de continuación y contexto de variables compartido. Los pipelines se disparan manualmente desde el dashboard o se programan desde la sección Crontab (que actúa como centro de scheduling). No hay scheduler interno propio — crontab es la fuente única de automatismo por tiempo.

---

## 1. Modelo de Datos

### `pipelines`
| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer PK | — |
| `name` | String | Nombre único del pipeline |
| `description` | Text | Descripción opcional |
| `created_at` | DateTime | Auto |
| `updated_at` | DateTime | Auto, actualizado en cada PUT |

### `pipeline_steps`
| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer PK | — |
| `pipeline_id` | Integer FK | → pipelines.id |
| `order` | Integer | Orden de ejecución (0-indexed) |
| `name` | String | Label descriptivo del paso |
| `step_type` | String | `"script"` \| `"shell"` \| `"module"` |
| `config` | JSON/Text | Configuración específica del tipo (ver abajo) |
| `on_success` | String | `"continue"` \| `"stop"` (default: `"continue"`) |
| `on_failure` | String | `"continue"` \| `"stop"` (default: `"stop"`) |

**Configs por tipo:**
- `script` → `{"favorite_id": 3, "args": ["--flag"]}`
- `shell` → `{"command": "systemctl restart nginx"}`
- `module` → `{"module": "move_file", "src": "{RUTA}", "dst": "/backup/"}`

### `pipeline_runs`
| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer PK | — |
| `pipeline_id` | Integer FK | → pipelines.id |
| `triggered_by` | String | Username o `"crontab"` |
| `started_at` | DateTime | Auto |
| `ended_at` | DateTime | Nullable |
| `status` | String | `"running"` \| `"success"` \| `"failed"` |

### `pipeline_step_runs`
| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer PK | — |
| `run_id` | Integer FK | → pipeline_runs.id |
| `step_id` | Integer FK | → pipeline_steps.id |
| `step_order` | Integer | Snapshot del orden en el momento de la run |
| `started_at` | DateTime | — |
| `ended_at` | DateTime | Nullable |
| `exit_code` | Integer | Nullable; módulos retornan 0/1 |
| `output` | Text | stdout + stderr capturado |
| `status` | String | `"skipped"` \| `"success"` \| `"failed"` |

### Índices requeridos (add_indexes.py)
```sql
CREATE INDEX IF NOT EXISTS ix_pipeline_steps_pipeline_id ON pipeline_steps (pipeline_id);
CREATE INDEX IF NOT EXISTS ix_pipeline_runs_pipeline_id  ON pipeline_runs  (pipeline_id);
CREATE INDEX IF NOT EXISTS ix_pipeline_runs_started_at   ON pipeline_runs  (started_at);
CREATE INDEX IF NOT EXISTS ix_pipeline_step_runs_run_id  ON pipeline_step_runs (run_id);
```

---

## 2. Contexto de Variables

Durante la ejecución, cada pipeline mantiene un dict en memoria `context: dict[str, str]`.

- El módulo `load_env` inyecta variables desde un archivo `.env` al contexto.
- En la config de cualquier paso, los patrones `{VARIABLE}` son reemplazados por su valor del contexto antes de ejecutar.
- Stdout de un paso **no** se pasa automáticamente al siguiente (el usuario puede usar `load_env` + archivo intermedio para lograr ese efecto — C queda para versión futura).

---

## 3. Arquitectura de Ejecución

### `backend/scripts/pipeline_runner.py`
Punto de entrada para crontab y uso CLI:
```bash
python -m backend.scripts.pipeline_runner --pipeline-id 3
```
Sigue el patrón de `cron_log.py`. Carga DB, llama `run_pipeline()`, sale con código 0 (éxito) o 1 (fallo).

### `backend/services/pipeline_service.py`
Lógica pura de ejecución — testeable directamente:

```python
def run_pipeline(pipeline_id: int, triggered_by: str, db: Session) -> PipelineRun
def execute_step(step: PipelineStep, context: dict, db: Session) -> PipelineStepRun
def execute_module(module_name: str, config: dict, context: dict) -> tuple[int, str]
def interpolate(config: dict, context: dict) -> dict
```

**Flujo de ejecución:**
```
pipeline_runner.py
  └─ run_pipeline(pipeline_id, triggered_by, db)
       ├─ crea PipelineRun (status="running")
       ├─ prev_exit_code = None
       ├─ for step in steps ordenados:
       │    ├─ evalúa condición (prev_exit_code=None para el primer paso → siempre corre):
       │    │    on_success="continue" + on_failure="continue" → siempre corre
       │    │    on_success="continue" + on_failure="stop"    → corre solo si prev éxito (default)
       │    │    on_success="stop"     + on_failure="continue"→ corre solo si prev falló (error handler)
       │    │    on_success="stop"     + on_failure="stop"    → nunca corre (skip incondicional)
       │    │    Si el paso es skipped → status="skipped", no afecta prev_exit_code
       │    ├─ interpola {VARIABLES} en step.config
       │    ├─ execute_step() → captura exit_code + output
       │    ├─ guarda PipelineStepRun
       │    └─ prev_exit_code = exit_code
       └─ actualiza PipelineRun (status="success"|"failed", ended_at)
```

**Ejecución manual desde API:** `POST /api/pipelines/{id}/run` lanza `run_pipeline()` en `ThreadPoolExecutor` (igual que `launch_execution` en scripts). Retorna `{"run_id": N}` para polling.

### `backend/services/pipeline_modules.py`
Un módulo por función, todos con la firma `(config: dict, context: dict) -> tuple[int, str]` (exit_code, output):

| Módulo | Config keys | Descripción |
|---|---|---|
| `load_env` | `path` | Carga `.env` al contexto en memoria |
| `move_file` | `src`, `dst` | Mueve archivo/directorio |
| `copy_file` | `src`, `dst` | Copia archivo/directorio |
| `delete_file` | `path` | Elimina archivo o directorio (con `rm -rf` equivalente) |
| `mkdir` | `path` | Crea directorio (y parents) |
| `write_file` | `path`, `content`, `mode` (`append`\|`overwrite`) | Escribe texto |
| `rename_file` | `path`, `new_name`, `use_timestamp` (bool) | Renombra; si timestamp=true → `{timestamp}_{new_name}` |
| `compress` | `src`, `dst`, `format` (`tar.gz`\|`zip`) | Comprime |
| `decompress` | `src`, `dst` | Descomprime |
| `check_exists` | `path`, `type` (`file`\|`dir`\|`any`) | Falla (exit=1) si no existe |
| `delay` | `seconds` | Espera N segundos |
| `log` | `message`, `level` (`info`\|`warn`\|`error`) | Escribe al output del step |
| `email` | `to`, `subject`, `body`, `attachment` (opcional) | Envía email vía SMTP. Config requerida en `.env`: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`. |
| `call_pipeline` | `pipeline_id` | Ejecuta otro pipeline como sub-pipeline (sincrónico). No detecta ciclos — responsabilidad del usuario. |

---

## 4. API Backend

**Router:** `backend/routers/pipelines.py` — prefix `/api/pipelines`

```
GET    /api/pipelines                  → List[PipelineOut] (con step_count, last_run)
POST   /api/pipelines                  → PipelineOut (crear)
GET    /api/pipelines/{id}             → PipelineDetailOut (con steps completos)
PUT    /api/pipelines/{id}             → PipelineDetailOut (replace completo: pipeline + steps)
DELETE /api/pipelines/{id}             → {"ok": true}
POST   /api/pipelines/{id}/run         → {"run_id": N}
GET    /api/pipelines/{id}/runs        → List[PipelineRunOut] (últimas 50)
GET    /api/pipelines/runs/{run_id}    → PipelineRunDetailOut (con step_runs)
```

**Permisos:**
- Crear/editar/eliminar: `require_role(UserRole.admin)`
- Ejecutar manualmente: `require_role(UserRole.operator)` — readonly no puede
- Ver lista e historial: cualquier usuario autenticado

---

## 5. Frontend

### Ruta y sidebar
- Nueva ruta `/pipelines` → `PipelinesView.vue` (lazy import)
- Entrada en sidebar: "Pipelines" con icono `pi-sitemap`, entre Scripts y Crontab

### Layout: 3 paneles (Splitter)
**Panel izquierdo (25%):** Lista de pipelines
- Header: icono + label "PIPELINES" + count + botón "+" + refresh
- Cards por pipeline: nombre, step count, último run (timestamp + status badge éxito/fallo/sin runs)
- Click selecciona y carga el panel central

**Panel central (50%):** Editor de steps
- Toolbar: nombre del pipeline + botón "▶ Ejecutar" + "＋ Paso"
- Lista de steps ordenados, reordenables con drag-and-drop
- Cada step card muestra: handle de drag, número, badge de tipo (color por tipo), nombre, condición
- Click en step abre un drawer/sidebar de configuración
- Bottom: botón "Guardar pipeline"

**Panel derecho (25%):** Mini-flujo + historial
- Mini-flow: diagrama vertical de nodos con colores por tipo y flechas anotadas con la condición
- Últimas runs: lista compacta con ícono éxito/fallo, timestamp, duración, y link "ver historial →"

### Step config drawer
Formulario adaptativo según `step_type`:
- **Script**: dropdown de ScriptFavorites, input de args
- **Shell**: InputText de comando
- **Módulo**: Select de módulo → formulario de campos específicos + preview de interpolación de variables

### Integración en CrontabView
En el wizard, Step 2 (COMMAND) agrega una tercera tab **"PIPELINE ⚡"**:
- Dropdown de pipelines disponibles
- Preview del comando generado: `python -m backend.scripts.pipeline_runner --pipeline-id N`
- Al guardar la entrada de crontab, ese comando queda como el `command` de la entrada

---

## 6. Fuera de Alcance (versión 1)

- HTTP request step (tipo D) — backlog
- Paso stdout → stdin del siguiente (tipo C de variables) — backlog
- Branching / bifurcaciones — backlog
- Ejecución paralela de pasos — backlog
- Configuración SMTP en UI (se usa la existente en `.env`) — asumido configurado
- Editor visual drag-and-drop tipo canvas — el mini-flow es solo visualización, no edición

---

## 7. Checklist de Performance (serverdash-performance)

- [x] Todos los FK columns usados en WHERE tienen índice en `__table_args__` y en `add_indexes.py`
- [x] No hay endpoints paginados con `q.count()` inline (historial usa `.limit(50)`)
- [x] Sin nuevas colecciones Vue sin cota máxima
- [x] Ruta `/pipelines` usa lazy import en `router/index.js`
- [x] `pipeline_runner.py` sigue el patrón `_do_*` / wrapper del scheduler
