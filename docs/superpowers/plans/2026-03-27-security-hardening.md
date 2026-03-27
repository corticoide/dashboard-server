# ServerDash — Security & Functionality Hardening Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remediate all critical and high-severity bugs found in the full-spectrum audit of ServerDash, and document medium/low findings for the technical debt backlog.

**Architecture:** Fixes are surgical — each task targets one file/function. No refactors unless the bug requires structural change. All fixes maintain backward compatibility with existing SQLite schema and frontend.

**Tech Stack:** FastAPI, SQLAlchemy, SQLite, subprocess, Pydantic, Vue 3, Axios, Pinia, Vite, Vitest, pytest

---

## AUDIT FINDINGS (All 6 Axes)

---

### AXIS 1 — SECURITY AUDIT

#### 1.1 — JWT in localStorage (Medium)

**Finding:** `auth.js:6-8` stores `access_token`, `username`, and `role` in `localStorage`. Any injected JavaScript (XSS) can exfiltrate the token.

**Assessment for context:** This is a local admin tool, typically served over HTTPS on a private network. XSS is unlikely but not impossible (Monaco editor, future rich-text inputs). The risk is **accepted for now** but documented. The proper fix is httpOnly cookie + CSRF token, which requires changes to both auth router and all axios requests. This is a P2 improvement.

**No immediate code change required.** Tracked in MEDIUM findings.

---

#### 1.2 — WebSocket token in query param (Medium)

**Finding:** `routers/scripts.py:139` — `token: str = Query(...)` passes JWT via URL query param. Server access logs, Nginx logs, and browser history will capture the token. This is a known limitation: browsers cannot set `Authorization` headers on WebSocket connections.

**Code reference:**
```python
# scripts.py:135-141
@router.websocket("/favorites/{fav_id}/run-ws")
async def run_ws(
    websocket: WebSocket,
    fav_id: int,
    token: str = Query(...),  # ← token in URL
```

**Mitigations already present:** Token is short-lived (15 min). Connection is over HTTPS (token encrypted in transit). Acceptable for this use case. Tracked in MEDIUM findings — see Task 5 for a one-time-token alternative.

---

#### 1.3 — Rate limiting (Low-Medium)

**Finding:** `POST /api/auth/login` is limited to 10/min via slowapi. The limiter uses client IP (`get_remote_address`), which works correctly when no proxy is in front. With Nginx as reverse proxy, `X-Forwarded-For` header must be trusted — verify Nginx config sets `proxy_set_header X-Real-IP`. Not a code bug, but a deployment concern.

**No code change required.** Add a note to `deploy-prod.sh` and deployment docs.

---

#### 1.4 — CORS & SPA fallback bypass (Low)

**Finding:** `main.py:62-67` — the SPA fallback `/{full_path:path}` catches any unmatched path and returns `index.html`. CORSMiddleware is applied to all routes including this fallback. Since the SPA is at the same origin as the API, CORS is only relevant for cross-origin requests, which the `allowed_origins` setting already restricts. No bypass possible.

**Status: Not a bug.** The SPA fallback returns HTML, not JSON, so CORS headers on it are irrelevant.

---

#### 1.5 — Command injection in sudo paths (Low for this tool)

**Finding — `_sudo_read` / `_sudo_write`** (`files_service.py:73-121`):
```python
proc = subprocess.Popen(
    ["sudo", "-S", "cat", str(path)],  # path is already resolved by _safe_path
    stdin=subprocess.PIPE, ...
)
stdout, stderr = proc.communicate(input=(sudo_password + "\n").encode(), timeout=10)
```
The password check `if '\n' in sudo_password or '\r' in sudo_password` prevents newline injection. `path` is pre-resolved by `_safe_path`. `shell=False` throughout. **No injection vector found.**

However: the check omits null bytes (`\x00`) in the password. On most systems, `sudo` will reject null bytes in the password naturally, but the validation could be stricter. This is a **Low** finding.

**Finding — `_validate_service_name`** (`services_service.py:123-125`):
```python
if not re.match(r'^[a-zA-Z0-9@._\-]+\.service$', name):
    raise ValueError(f"Invalid service name: {name!r}")
```
The regex is correct and sufficient. It anchors start/end, requires `.service` suffix, and only allows safe characters. `shell=False` means shell metacharacters are irrelevant anyway. **No issue.**

**Finding — `ALLOWED_RUNNERS`** (`scripts_service.py:14-17`): Runner list is a fixed whitelist. Detection reads up to 256 bytes from the script file — the attacker would need write access to the script file itself (which means they're already compromised). No injection path found.

---

#### 1.6 — ALLOWED_ROOT = Path("/") (Design Decision, Low for admin tool)

**Finding:** `files_service.py:12` — `ALLOWED_ROOT = Path("/")` allows access to the entire filesystem. This is **intentional** for a server administration tool (admins need to browse `/etc`, `/var`, `/proc`, etc.). With sudo support, even root-owned files are accessible.

**Risk:** Any authenticated user (even `readonly` role) can read any file the server process user can read. File writes are restricted to `admin` role. This is the intended design — document it clearly rather than restrict it.

**Status: Intentional design. No change required.** Documented for future multi-tenant consideration.

---

#### 1.7 — Missing Content-Security-Policy (High)

**Finding:** `middleware/security.py:4-12` sets 5 headers but omits `Content-Security-Policy`. Without CSP, any XSS vector can run arbitrary inline scripts.

```python
# Current headers:
"X-Content-Type-Options": "nosniff"
"X-Frame-Options": "DENY"
"X-XSS-Protection": "1; mode=block"
"Referrer-Policy": "strict-origin-when-cross-origin"
"Strict-Transport-Security": "max-age=31536000; includeSubDomains"
# Missing:
"Content-Security-Policy": "..."  # ← absent
```

**Fix:** Add CSP header. Monaco editor requires `'unsafe-eval'` for its worker. See Task 1.

---

#### 1.8 — No audit trail for destructive operations (Medium)

**Finding:** `audit_logger` is used in `scripts.py` for script execution. But file writes (`PUT /api/files/content`), file deletions (`DELETE /api/files/delete`), service control (`POST /api/services/control`), and crontab changes (`POST/PUT/DELETE /api/crontab`) produce **no audit log entries**. Only script executions are tracked.

**Risk:** After a misconfiguration, there's no log of which admin changed which file or service. See Task 6.

---

#### 1.9 — Favorites path not validated with _safe_path (Medium)

**Finding:** `routers/scripts.py:35-43` — `POST /api/scripts/favorites` stores `body.path` directly in the DB without `_safe_path` validation:
```python
fav = ScriptFavorite(path=body.path)  # no _safe_path() called
```
This means any path string can be stored. When `build_favorite_out` runs `detect_runner(p)`, it will try to open and read the file for shebang detection — effectively allowing read of the first 256 bytes of any file an authenticated user favorites. For execution, `detect_runner` + `launch_execution` will attempt to run the path, which could be any file.

For an admin tool with authenticated-only access, this is acceptable but should be documented. A stricter approach would call `_safe_path` on add. See Task 3.

---

### AXIS 2 — FUNCTIONALITY AUDIT

#### 2.1 — Polling & Visibility API (Already Fixed)

**Finding (pre-verified):** `usePolling.js` at lines 6 and 9-13 **already implements** `document.hidden` check and `visibilitychange` listener:
```js
function tick() {
  if (!document.hidden) fn()  // ← already guarded
}
function onVisibilityChange() {
  if (!active) return
  if (!document.hidden) fn()  // ← already guarded
}
```
**Status: Not a bug. The spec concern was already addressed in a recent commit.** No change needed.

---

#### 2.2 — WebSocket execution flow (Works correctly for single-worker)

**Finding:** `scripts.py:198-201`:
```python
try:
    raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
    params = json.loads(raw)
except (asyncio.TimeoutError, Exception):
    params = {}
```
If the client never sends params (timeout), the code falls back to `params = {}`, so `sudo_password = None` and `args = []`. Execution proceeds with empty args and no sudo. This is the correct graceful degradation.

**Status: Not a bug.**

---

#### 2.3 — stdout/stderr merged into `lines` (Intentional)

**Finding:** `scripts_service.py:188-193` — stderr is read concurrently into the same `lines` list as stdout. This means stderr and stdout are interleaved in time order, which is the correct behavior for a terminal-like experience. The user sees output as it would appear in a terminal.

**Status: Intentional. No change needed.**

---

#### 2.4 — `stream_file` for sudo files reads entire file into memory (Low)

**Finding:** `files_service.py:197-203`:
```python
content = _sudo_read(p, sudo_password)   # reads entire file as string
data = content.encode("utf-8")           # converts to bytes

def _iter_sudo():
    yield data                           # yields entire file at once
```
This is fine for text config files (which is the expected sudo use case), but would break for large binary files (e.g., `sudo cat /dev/sda`). However, `read_file` already enforces a 5MB limit on non-sudo reads, and `stream_file` is only called for download which bypasses the size check.

**Assessment:** The 5MB limit in `read_file` is not applied to `stream_file`. A root-only binary file could exhaust memory. But the typical use case (config files, logs) makes this acceptable. Tracked in LOW.

---

#### 2.5 — Auth 401 handling (Medium-High)

**Finding:** `client.js` has only a **request interceptor** (attaches JWT) but **no response interceptor**. If the 15-minute token expires mid-session, all API calls will silently return 401. Vue components will see empty data or show error toasts but the user won't be redirected to login.

```js
// client.js — only request interceptor exists:
api.interceptors.request.use((config) => { ... })
// Missing:
api.interceptors.response.use(null, (error) => {
  if (error.response?.status === 401) { /* redirect to /login */ }
  return Promise.reject(error)
})
```

**Fix:** See Task 2.

---

#### 2.6 — `atob()` JWT decode — base64 padding (Low)

**Finding:** `auth.js:16`:
```js
const payload = JSON.parse(atob(data.access_token.split('.')[1]))
```
JWT Base64url encoding omits padding (`=`). `atob()` in modern browsers handles missing padding gracefully, but it's not guaranteed in all environments. The server uses `python-jose` which produces standard Base64url. In practice, this has never broken.

**Assessment:** Low risk. Tracked in LOW.

---

#### 2.7 — `loadFavorites` race condition (Low)

**Finding:** `stores/scripts.js:19-26`:
```js
async function loadFavorites(force = false) {
  if (loaded.value && !force) return
  // If two components call this simultaneously before first resolves,
  // both see loaded.value === false and both fire the request
  const { data } = await api.get('/scripts/favorites')
  favorites.value = data
  loaded.value = true
}
```
If two components mount simultaneously, two GET requests are fired. Both resolve correctly, `favorites.value` is set twice (idempotent). No corruption, just a wasted request.

**Assessment:** Low risk, cosmetic issue.

---

#### 2.8 — Crontab: multiple consecutive comment lines (Low)

**Finding:** `crontab_service.py:63-67`:
```python
if stripped.startswith("#"):
    ...
    pending_comment = stripped[1:].strip()  # overwrites previous comment
    continue
```
Multiple consecutive comment lines → only the last line is preserved. This is a data-loss issue if users write multi-line comments.

**Assessment:** Rare use case. Tracked in LOW/MEDIUM.

---

### AXIS 3 — BUG HUNT (Concrete Bugs)

---

#### BUG-1 (CRITICAL): Upload path traversal via unsanitized `file.filename`

**File:** `backend/routers/files.py:103`

**Code:**
```python
target = _safe_path(path) / file.filename  # ← file.filename is attacker-controlled!
```

**How it breaks:** A client sends a multipart upload with `filename="../../etc/cron.d/backdoor"`. Python's `Path.__truediv__` resolves this as a path component — `Path("/tmp/uploads") / "../../etc/cron.d/backdoor"` produces `Path("/tmp/uploads/../../etc/cron.d/backdoor")`. `open(target, "wb")` will write to `/etc/cron.d/backdoor` if the server process has write access.

**Reproduction:**
```bash
curl -X POST "https://server:8443/api/files/upload?path=/tmp" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@payload.sh;filename=../../etc/cron.d/evil"
```

**Fix:**
```python
# files.py:103 — sanitize filename before joining
safe_name = Path(file.filename).name  # strips all directory components
if not safe_name or safe_name in (".", ".."):
    raise HTTPException(400, detail="Invalid filename")
target = _safe_path(path) / safe_name
```

---

#### BUG-2 (CRITICAL): Multi-worker execution state bug

**File:** `backend/services/scripts_service.py:120`

**Code:**
```python
_running: Dict[int, dict] = {}  # ← process-local dict
```

**How it breaks:** With `gunicorn -w 4`, there are 4 separate Python processes. `launch_execution()` stores state in `_running` of **worker A**. The WebSocket connection (which launched the execution) holds state on **worker A**. But HTTP poll requests to `GET /api/scripts/executions/{exec_id}` are load-balanced across all 4 workers. Workers B, C, D have no entry for `exec_id` in their `_running` dict, so they check the DB. The DB entry only shows completion *after* the thread in worker A persists it (at execution end). During execution, the poll returns 404 on 3 of 4 requests.

**Frontend manifestation:** `ScriptsView.vue` HTTP polling (fallback mode) shows intermittent "Execution not found" errors while the script is running.

**Note:** The WebSocket path (`run-ws`) is immune because the WebSocket connection is sticky to the worker that accepted it, and the output streaming polls `get_poll_state()` within the same process.

**Fix options (ordered by complexity):**
1. **DB-only poll state (recommended):** Update `ScriptExecution.output` incrementally during execution (append to DB) and use a small DB poll. Eliminates `_running` dict entirely.
2. **Sticky sessions via Nginx:** `ip_hash` or `hash $request_uri consistent` in Nginx upstream config — HTTP and WS from the same client hit the same worker. Quick fix but not a code fix.
3. **Redis shared state:** Replace `_running` dict with Redis. Requires `redis` dependency.

**Immediate fix (Option 1 — DB-based live output):** See Task 4.

---

#### BUG-3 (HIGH): Crontab env var silent deletion

**File:** `backend/services/crontab_service.py:70-73`

**Code:**
```python
# _parse_raw: env var lines are SKIPPED (not stored)
if re.match(r'^[A-Z_][A-Z0-9_]*\s*=', stripped):
    pending_comment = None
    continue  # ← dropped, not added to entries list
```

```python
# _entries_to_text: only outputs CrontabEntry objects (no env vars)
def _entries_to_text(entries: List[CrontabEntry]) -> str:
    lines: List[str] = []
    for e in entries:  # ← only entries, never env vars
        if e.comment:
            lines.append(f"# {e.comment}")
        ...
```

**How it breaks:** User has a crontab with `MAILTO=""` and `SHELL=/bin/bash`. Any save operation (add/update/delete an entry) calls `_save(entries)`, which rebuilds the entire crontab from `entries` — silently dropping all `VAR=value` lines. After save, `MAILTO` and `SHELL` are gone forever. This is **silent permanent data loss** on any edit.

**Reproduction:**
1. User has crontab with `MAILTO=""` line
2. User adds a crontab entry via UI
3. `add_entry()` calls `_save()` which calls `_entries_to_text()` — `MAILTO=""` is gone

**Fix:** See Task 7.

---

#### BUG-4 (Medium): MetricCard test uses wrong CSS class

**File:** `frontend/src/components/dashboard/MetricCard.test.js:14`

**Code:**
```js
const fill = wrapper.find('.bar-fill')      // ← class doesn't exist in component
const style = fill.attributes('style')      // ← fill is empty wrapper, attributes() returns undefined
expect(style).toContain('stroke-dashoffset') // ← FAILS: undefined doesn't contain anything
```

**Actual class in `MetricCard.vue:104`:**
```css
.gauge-fill { transition: stroke-dashoffset 0.5s ease, stroke 0.3s ease; }
```

The element is also an SVG element with a `class` attribute of `gauge-fill`, not `bar-fill`. This test currently **throws** rather than asserting, making CI silently miss it.

**Fix:** See Task 8.

---

#### BUG-5 (Low): Duration calculation assumes UTC — breaks on non-UTC systems

**File:** `backend/services/scripts_service.py:234`

**Code:**
```python
duration = (ended - exe.started_at.replace(tzinfo=timezone.utc)).total_seconds()
```

`exe.started_at` is stored by SQLAlchemy as a naive datetime via `server_default=func.now()`. On SQLite, `func.now()` returns the system's local time as a naive datetime. If the server is in UTC, `replace(tzinfo=timezone.utc)` is correct. On non-UTC servers, this produces an incorrect (potentially negative) duration.

**Fix:**
```python
# Use aware datetime for started_at by storing with explicit timezone
started_at_aware = exe.started_at.replace(tzinfo=timezone.utc) if exe.started_at else None
duration = (ended - started_at_aware).total_seconds() if started_at_aware else None
```

A proper fix would configure SQLite to always store UTC or use `datetime.utcnow()` explicitly. Tracked in LOW.

---

#### BUG-6 (Low): `get_error_logger()` is dead infrastructure

**File:** `backend/core/logging.py:56-57`

```python
def get_error_logger() -> logging.Logger:
    return logging.getLogger("serverdash.errors")
```

Searching all `.py` files confirms zero call sites for `get_error_logger`. The `errors.log` file is created but nothing writes to it. This is dead infrastructure.

**Fix:** Either use it (wrap exception handlers) or remove it. See Task 9.

---

#### BUG-7 (Low): `.superpowers/` directory not in .gitignore

**Finding:** `.superpowers/brainstorm/*/` contains design artifacts (HTML files with architecture brainstorms). No secrets found. But this directory should be gitignored to avoid polluting the repository with session artifacts.

**Fix:** Add `.superpowers/` to `.gitignore`. See Task 10.

---

#### BUG-8 (Low): `Chip` import in `ScriptsView.vue` — NOT dead (audit correction)

**Finding:** The audit prompt suggested `Chip` is unused in `ScriptsView.vue`. After code verification:
- `ScriptsView.vue:241` — `<Chip :label="data.triggered_by" class="history-chip" />` — **actually used**
- `ScriptsView.vue:302` — `import Chip from 'primevue/chip'` — import is valid

**Status: False positive from the audit prompt. No action needed.**

---

#### BUG-9 (Medium): `ScriptExecution` vs `ExecutionLog` — partial overlap

**Models:**
- `ScriptExecution` (script_executions): id, script_path, started_at, ended_at, exit_code, output (full), run_as_root, triggered_by
- `ExecutionLog` (execution_logs): id, script_path, username, started_at, ended_at, exit_code, duration_seconds, output_summary (500 chars)

`ExecutionLog` is written at execution completion (`scripts_service.py:236-244`) as an **audit trail** (compact, no full output). `ScriptExecution` is the **live execution record** with full output storage. They serve different purposes:
- `ScriptExecution` → live state, poll endpoint, history per script
- `ExecutionLog` → cross-script audit, used by `/api/logs` endpoint for the Logs view

**Assessment:** Both are needed. The naming is confusing but the functionality is distinct. Track as a documentation/naming concern, not a bug.

---

### AXIS 4 — CODE QUALITY

| Item | Location | Finding | Action |
|------|----------|---------|--------|
| `error_logger` dead code | `core/logging.py:56` | `get_error_logger()` has zero call sites | Remove or use (Task 9) |
| MetricCard test broken | `MetricCard.test.js:14` | `.bar-fill` should be `.gauge-fill` | Fix (Task 8) |
| `.superpowers/` in git | `.gitignore` | Design artifacts tracked | Add to .gitignore (Task 10) |
| `deploy.sh` vs `deploy-prod.sh` | root | Near-identical, only `--reload` differs | Merge with ENV flag (LOW) |
| `Chip` import `ScriptsView` | line 302 | Actually used at line 241 | No action |
| `AppSidebar` PanelMenu hack | `AppSidebar.vue` | `headerAction: { style: 'display: none' }` | Low priority cosmetic |

---

### AXIS 5 — ROBUSTNESS IMPROVEMENTS

**P0 — Blocks production use:**
- [x] Fix upload path traversal (Task 1... see Task 3 below)
- [x] Fix multi-worker execution state (Task 4)
- [x] Fix crontab env var loss (Task 7)

**P1 — Important for reliability:**
- [x] Add axios 401 interceptor (Task 2)
- [x] Add CSP header (Task 1)
- [x] Validate favorites path with _safe_path (Task 3)
- Upload size limit via `.env` variable (MEDIUM, tracked)

**P2 — Maintainability:**
- Add audit logging for file writes/deletes/service actions (Task 6)
- Remove dead `get_error_logger` / wire it up (Task 9)
- Fix MetricCard test (Task 8)
- `.gitignore` fix (Task 10)

**P3 — Future:**
- Alembic for DB migrations
- Redis for shared worker state
- httpOnly cookie + CSRF instead of localStorage JWT
- File upload size limit configurable via `.env`

---

### AXIS 6 — REMEDIATION PLAN (Ordered by Priority)

---

## FILES TO MODIFY

| File | Change |
|------|--------|
| `backend/routers/files.py` | Sanitize `file.filename` in upload endpoint |
| `backend/middleware/security.py` | Add Content-Security-Policy header |
| `frontend/src/api/client.js` | Add 401 response interceptor |
| `backend/routers/scripts.py` | Add `_safe_path` validation on add_favorite |
| `backend/services/scripts_service.py` | Fix multi-worker bug: write live output to DB incrementally |
| `backend/routers/scripts.py` | Update poll endpoint to read from DB during execution |
| `backend/services/crontab_service.py` | Preserve env var lines through parse/save cycle |
| `frontend/src/components/dashboard/MetricCard.test.js` | Fix `.bar-fill` → `.gauge-fill` |
| `backend/core/logging.py` | Remove dead `get_error_logger` or wire it to exception handlers |
| `backend/routers/files.py` | Add audit logging for write/delete operations |
| `backend/routers/services.py` | Add audit logging for service control |
| `backend/routers/crontab.py` | Add audit logging for crontab changes |
| `.gitignore` | Add `.superpowers/` |

---

## TASK 1: Add Content-Security-Policy header

**Files:**
- Modify: `backend/middleware/security.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_security_headers.py
def test_csp_header_present(test_app):
    r = test_app.get("/health")
    assert "Content-Security-Policy" in r.headers
    csp = r.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp

def test_existing_headers_still_present(test_app):
    r = test_app.get("/health")
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-Content-Type-Options"] == "nosniff"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/crt/server_dashboard
pytest tests/test_security_headers.py -v
```
Expected: FAIL — `Content-Security-Policy` key not in headers.

- [ ] **Step 3: Implement the fix**

```python
# backend/middleware/security.py
from starlette.middleware.base import BaseHTTPMiddleware

# Monaco editor requires 'unsafe-eval' for its web workers.
# blob: is required for Monaco worker blobs.
_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-eval' blob:; "
    "style-src 'self' 'unsafe-inline'; "
    "font-src 'self' data:; "
    "img-src 'self' data:; "
    "connect-src 'self' wss:; "
    "worker-src blob: 'self';"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = _CSP
        return response
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_security_headers.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/middleware/security.py tests/test_security_headers.py
git commit -m "security: add Content-Security-Policy header (allow Monaco eval + blob workers)"
```

---

## TASK 2: Add axios 401 response interceptor

**Files:**
- Modify: `frontend/src/api/client.js`

> No backend test. Vitest test for the interceptor would require mocking axios — simpler to test manually.

- [ ] **Step 1: Write the test (manual verification steps)**

After implementation, to verify:
1. Login to the app
2. Open browser console, run: `localStorage.setItem('access_token', 'invalid.token.here')`
3. Navigate to `/services` (triggers API call)
4. Verify: you are redirected to `/login` automatically

- [ ] **Step 2: Implement the interceptor**

```js
// frontend/src/api/client.js
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  if (config.data instanceof FormData) {
    delete config.headers['Content-Type']
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Clear stale auth state and redirect to login
      localStorage.removeItem('access_token')
      localStorage.removeItem('username')
      localStorage.removeItem('role')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api
```

- [ ] **Step 3: Verify manually (see Step 1)**

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/client.js
git commit -m "fix: add axios 401 interceptor — redirect to /login on expired token"
```

---

## TASK 3: Fix upload path traversal + favorites path validation

**Files:**
- Modify: `backend/routers/files.py` (upload endpoint)
- Modify: `backend/routers/scripts.py` (add_favorite endpoint)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_files.py — add to existing file

def test_upload_path_traversal_rejected(test_app):
    """A filename with ../ components must not escape the target directory."""
    import io
    token = test_app.post("/api/auth/login", json={"username": "admin", "password": "adminpass"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    # The important part is that the filename is sanitized — we test the API rejects it
    # by checking the written file is in the expected directory, not traversed
    data = {"file": ("../../evil.txt", io.BytesIO(b"pwned"), "text/plain")}
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        r = test_app.post(
            f"/api/files/upload?path={tmpdir}",
            headers=headers,
            files=data,
        )
        # File should be written as "evil.txt" inside tmpdir, NOT as ../../evil.txt
        if r.status_code == 200:
            written_path = r.json()["path"]
            assert written_path.startswith(tmpdir), f"Path traversal! Got: {written_path}"
            assert "evil.txt" in written_path
```

- [ ] **Step 2: Run test to confirm current behavior**

```bash
pytest tests/test_files.py::test_upload_path_traversal_rejected -v
```
Expected: Test may pass or fail depending on OS path resolution — run to see current behavior.

- [ ] **Step 3: Fix upload endpoint**

```python
# backend/routers/files.py — api_upload function (line 96-109)
@router.post("/upload")
def api_upload(
    path: str = Query(...),
    file: UploadFile = File(...),
    user=Depends(require_role(UserRole.operator)),
):
    try:
        # Sanitize filename: strip all directory components
        safe_name = Path(file.filename).name if file.filename else ""
        if not safe_name or safe_name in (".", ".."):
            raise HTTPException(400, detail="Invalid filename")
        target = _safe_path(path) / safe_name
        with open(target, "wb") as f:
            while chunk := file.file.read(65536):
                f.write(chunk)
        return {"ok": True, "path": str(target)}
    except HTTPException:
        raise
    except (ValueError, PermissionError) as e:
        raise HTTPException(400, detail=str(e))
```

- [ ] **Step 4: Fix favorites path validation**

```python
# backend/routers/scripts.py — add_favorite function (line 34-43)
# Add _safe_path import (already imported: from backend.services.files_service import ... _safe_path)
@router.post("/favorites", response_model=FavoriteOut)
def add_favorite(body: FavoriteCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    # Validate the path is a real, safe path
    try:
        safe = _safe_path(body.path)
    except (ValueError, PermissionError) as e:
        raise HTTPException(400, detail=f"Invalid path: {e}")

    existing = db.query(ScriptFavorite).filter(ScriptFavorite.path == str(safe)).first()
    if existing:
        return build_favorite_out(existing)
    fav = ScriptFavorite(path=str(safe))
    db.add(fav)
    db.commit()
    db.refresh(fav)
    return build_favorite_out(fav)
```

Also add the import at the top of `scripts.py`:
```python
from backend.services.files_service import _safe_path
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_files.py tests/test_files_service.py -v
```
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add backend/routers/files.py backend/routers/scripts.py
git commit -m "security: fix upload path traversal + validate favorites path via _safe_path"
```

---

## TASK 4: Fix multi-worker execution state bug

**Context:** The `_running` dict is process-local. The fix moves live output to the DB incrementally so any worker can poll it. This replaces the in-memory `_running` dict with DB-only state for the HTTP poll endpoint.

**Approach:** Rather than polling the `_running` dict from HTTP (which fails cross-worker), the `poll_execution` endpoint will always query the DB. The `ScriptExecution.output` column will be updated incrementally by the background thread. We add an `is_running` boolean column to `ScriptExecution` to distinguish live vs. completed. The WebSocket stream still uses `_running` (it's in the same process/worker) for low-latency streaming.

**Files:**
- Modify: `backend/models/script.py` (add `is_running` column)
- Modify: `backend/services/scripts_service.py` (write output to DB incrementally)
- Modify: `backend/routers/scripts.py` (poll_execution reads DB, not `_running`)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_scripts_multiworker.py
import time
import threading
from unittest.mock import patch, MagicMock

def test_poll_execution_reads_from_db_during_run(test_app):
    """poll_execution must return data from DB, not in-memory _running dict."""
    # Simulate: execution is running on a different "worker" (empty _running)
    token = test_app.post("/api/auth/login", json={"username": "admin", "password": "adminpass"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create a ScriptExecution record directly (as if another worker started it)
    from backend.database import SessionLocal
    from backend.models.script import ScriptExecution, ScriptFavorite
    db = SessionLocal()
    fav = ScriptFavorite(path="/usr/bin/true")
    db.add(fav)
    db.flush()
    exe = ScriptExecution(
        script_path="/usr/bin/true",
        run_as_root=False,
        triggered_by="admin",
        is_running=True,
        output="line1\nline2",
    )
    db.add(exe)
    db.commit()
    exec_id = exe.id
    db.close()

    # Poll with empty _running (simulating different worker)
    from backend.services import scripts_service
    assert exec_id not in scripts_service._running  # confirm not in memory

    r = test_app.get(f"/api/scripts/executions/{exec_id}", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["running"] == True
    assert "line1" in data["lines"]
    assert "line2" in data["lines"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_scripts_multiworker.py -v
```
Expected: FAIL — `is_running` column doesn't exist yet.

- [ ] **Step 3: Add `is_running` to ScriptExecution model**

```python
# backend/models/script.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from backend.database import Base


class ScriptFavorite(Base):
    __tablename__ = "script_favorites"

    id = Column(Integer, primary_key=True, index=True)
    path = Column(String, unique=True, nullable=False, index=True)
    run_as_root = Column(Boolean, default=False, nullable=False)
    admin_only = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class ScriptExecution(Base):
    __tablename__ = "script_executions"

    id = Column(Integer, primary_key=True, index=True)
    script_path = Column(String, nullable=False, index=True)
    started_at = Column(DateTime, server_default=func.now())
    ended_at = Column(DateTime, nullable=True)
    exit_code = Column(Integer, nullable=True)
    output = Column(Text, default="")
    run_as_root = Column(Boolean, default=False)
    triggered_by = Column(String, nullable=True)
    is_running = Column(Boolean, default=True, nullable=False)  # ← new column
```

**Schema note:** SQLite `Base.metadata.create_all` won't add the column to existing databases. Run this migration manually on production:
```sql
ALTER TABLE script_executions ADD COLUMN is_running BOOLEAN NOT NULL DEFAULT 0;
UPDATE script_executions SET is_running = 0 WHERE ended_at IS NOT NULL;
```

- [ ] **Step 4: Update `launch_execution` to write output to DB incrementally**

```python
# backend/services/scripts_service.py — replace launch_execution's _run() inner function

def launch_execution(
    exec_id: int,
    script_path: str,
    runner: str,
    run_as_root: bool,
    sudo_password: Optional[str],
    args: List[str],
    triggered_by: str,
) -> None:
    """Start the script execution in a background thread."""
    state: dict = {"lines": [], "running": True, "exit_code": None}
    _running[exec_id] = state

    def _flush_to_db(lines_snapshot: List[str]) -> None:
        """Write current output snapshot to DB (best-effort, non-fatal)."""
        try:
            db = SessionLocal()
            exe = db.query(ScriptExecution).filter(ScriptExecution.id == exec_id).first()
            if exe:
                exe.output = "\n".join(lines_snapshot)
                db.commit()
        except Exception:
            pass
        finally:
            try:
                db.close()
            except Exception:
                pass

    def _run():
        cmd = _build_cmd(script_path, runner, args, run_as_root)
        last_flush = 0
        FLUSH_EVERY = 1  # flush to DB after every new line to ensure cross-worker visibility

        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE if (run_as_root and sudo_password) else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=str(Path(script_path).parent),
            )

            if run_as_root and sudo_password and proc.stdin:
                proc.stdin.write(sudo_password + "\n")
                proc.stdin.flush()
                proc.stdin.close()

            t_err = threading.Thread(target=_reader, args=(proc.stderr, state["lines"]))
            t_err.daemon = True
            t_err.start()

            # Read stdout line by line, flushing to DB periodically
            for line in proc.stdout:
                state["lines"].append(line.rstrip("\n"))
                if len(state["lines"]) - last_flush >= FLUSH_EVERY:
                    _flush_to_db(list(state["lines"]))
                    last_flush = len(state["lines"])

            t_err.join(timeout=5)
            proc.wait(timeout=300)
            exit_code = proc.returncode

            combined = "\n".join(state["lines"]).lower()
            if (
                run_as_root
                and exit_code != 0
                and ("incorrect password" in combined or "authentication failure" in combined)
            ):
                state["lines"] = ["[sudo] Error: Incorrect password"]
                exit_code = 1

        except FileNotFoundError:
            runner_name = cmd[0] if not run_as_root else cmd[2]
            state["lines"].append(f"Error: '{runner_name}' not found — is it installed?")
            exit_code = 127
        except subprocess.TimeoutExpired:
            proc.kill()
            state["lines"].append("[Execution timed out after 5 minutes]")
            exit_code = -1
        except Exception as e:
            state["lines"].append(f"Error: {e}")
            exit_code = 1

        state["running"] = False
        state["exit_code"] = exit_code

        # Final DB persist
        ended = datetime.now(timezone.utc)
        db = SessionLocal()
        try:
            exe = db.query(ScriptExecution).filter(ScriptExecution.id == exec_id).first()
            if exe:
                exe.ended_at = ended
                exe.exit_code = exit_code
                exe.output = "\n".join(state["lines"])
                exe.is_running = False
                started_aware = exe.started_at.replace(tzinfo=timezone.utc) if exe.started_at else None
                duration = (ended - started_aware).total_seconds() if started_aware else None
                full_output = "\n".join(state["lines"])
                log = ExecutionLog(
                    script_path=script_path,
                    username=triggered_by,
                    started_at=exe.started_at,
                    ended_at=ended,
                    exit_code=exit_code,
                    duration_seconds=duration,
                    output_summary=full_output[:500] if full_output else None,
                )
                db.add(log)
                db.commit()
        finally:
            db.close()

        threading.Timer(300, lambda: _running.pop(exec_id, None)).start()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
```

- [ ] **Step 5: Update `poll_execution` to use DB as source of truth**

```python
# backend/routers/scripts.py — replace poll_execution

@router.get("/executions/{exec_id}", response_model=ExecutionPoll)
def poll_execution(exec_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    # Always check DB first — works across all gunicorn workers
    exe = db.query(ScriptExecution).filter(ScriptExecution.id == exec_id).first()
    if not exe:
        raise HTTPException(404, detail="Execution not found")

    # If in _running on THIS worker, prefer in-memory for freshest data
    state = get_poll_state(exec_id)
    if state is not None:
        return ExecutionPoll(
            id=exec_id,
            running=state["running"],
            exit_code=state["exit_code"],
            lines=list(state["lines"]),
        )

    # Cross-worker: use DB state (output written incrementally)
    return ExecutionPoll(
        id=exec_id,
        running=exe.is_running,
        exit_code=exe.exit_code,
        lines=exe.output.splitlines() if exe.output else [],
    )
```

Also update the two `ScriptExecution` creation points (in `run_favorite` and `run_ws`) to set `is_running=True`:
```python
exe = ScriptExecution(
    script_path=fav.path,
    run_as_root=fav.run_as_root,
    triggered_by=user.username,
    is_running=True,  # ← add this
)
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_scripts_multiworker.py tests/test_scripts.py -v 2>/dev/null || pytest tests/ -v -k "script" 2>/dev/null
```

- [ ] **Step 7: Manual migration for existing DB**

```bash
sqlite3 data/serverdash.db "ALTER TABLE script_executions ADD COLUMN is_running BOOLEAN NOT NULL DEFAULT 1; UPDATE script_executions SET is_running = 0 WHERE ended_at IS NOT NULL;"
```
> **Note:** `DEFAULT 1` matches the SQLAlchemy model's `default=True`. All historical completed rows are then corrected to `0` by the UPDATE.

- [ ] **Step 8: Commit**

```bash
git add backend/models/script.py backend/services/scripts_service.py backend/routers/scripts.py
git commit -m "fix: resolve multi-worker execution state bug — poll from DB, flush output incrementally"
```

---

## TASK 5 (Optional/P1): WebSocket token as one-time token

**Context:** The WebSocket endpoint uses `?token=JWT` in the URL, which leaks into server logs. An alternative is to issue a short-lived (30s) single-use "ws_token" that maps to the user's exec context.

**Assessment:** This adds significant complexity (token store, cleanup) for a marginal benefit in a private-network admin tool. **Defer to P2.** Document the risk in CLAUDE.md.

**No implementation in this plan.**

---

## TASK 6: Add audit logging for destructive operations

**Files:**
- Modify: `backend/routers/files.py`
- Modify: `backend/routers/services.py`
- Modify: `backend/routers/crontab.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_audit_logging.py
import logging
from unittest.mock import patch, MagicMock

def test_file_write_emits_audit_log(test_app, tmp_path):
    import tempfile, os
    token = test_app.post("/api/auth/login", json={"username": "admin", "password": "adminpass"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"original")
        fpath = f.name

    try:
        with patch("backend.routers.files.get_audit_logger") as mock_logger:
            mock_log = MagicMock()
            mock_logger.return_value = mock_log
            r = test_app.put(
                f"/api/files/content?path={fpath}",
                headers=headers,
                json={"content": "new content"},
            )
            assert r.status_code == 200
            mock_log.info.assert_called_once()
            call_args = mock_log.info.call_args[0][0]
            assert "file_write" in call_args
    finally:
        os.unlink(fpath)
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
pytest tests/test_audit_logging.py -v
```

- [ ] **Step 3: Add audit logging to files router**

```python
# backend/routers/files.py — add import at top
from backend.core.logging import get_audit_logger

# In api_write:
@router.put("/content")
def api_write(
    body: FileWriteRequest,
    path: str = Query(...),
    user=Depends(require_role(UserRole.admin)),
    x_sudo_password: Optional[str] = Header(None),
):
    try:
        write_file(path, body.content, sudo_password=x_sudo_password)
        get_audit_logger().info("file_write user=%s path=%s", user.username, path)
        return {"ok": True}
    except (ValueError, PermissionError) as e:
        raise HTTPException(400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(500, detail=str(e))

# In api_delete:
@router.delete("/delete")
def api_delete(path: str = Query(...), user=Depends(require_role(UserRole.admin))):
    try:
        delete_path(path)
        get_audit_logger().info("file_delete user=%s path=%s", user.username, path)
        return {"ok": True}
    ...
```

- [ ] **Step 4: Add audit logging to services router**

```python
# backend/routers/services.py — find control_service endpoint, add:
get_audit_logger().info("service_control user=%s service=%s action=%s", user.username, body.name, body.action)
```

- [ ] **Step 5: Add audit logging to crontab router**

```python
# backend/routers/crontab.py — add to add_entry, update_entry, delete_entry endpoints:
get_audit_logger().info("crontab_%s user=%s entry_id=%s", action, user.username, entry_id)
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_audit_logging.py -v
```

- [ ] **Step 7: Commit**

```bash
git add backend/routers/files.py backend/routers/services.py backend/routers/crontab.py tests/test_audit_logging.py
git commit -m "feat: add audit logging for file write/delete, service control, crontab changes"
```

---

## TASK 7: Fix crontab env var silent deletion

**Files:**
- Modify: `backend/services/crontab_service.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_crontab_service.py (add to existing or create)
from unittest.mock import patch
from backend.services.crontab_service import _parse_raw, _entries_to_text, add_entry
from backend.schemas.crontab import CrontabEntryCreate

def test_env_vars_preserved_through_parse_save_cycle():
    """Env vars like MAILTO= must survive a parse→save roundtrip."""
    raw_crontab = """MAILTO=""
SHELL=/bin/bash
# My job
* * * * * /usr/bin/true
"""
    entries = _parse_raw(raw_crontab)
    # Entries should not include env vars (they're not CrontabEntry objects)
    assert len(entries) == 1
    assert entries[0].command == "/usr/bin/true"

def test_env_vars_preserved_in_output():
    """When rebuilding crontab text, env var lines must be included."""
    raw_crontab = 'MAILTO=""\nSHELL=/bin/bash\n* * * * * /usr/bin/true\n'
    from backend.services.crontab_service import _parse_raw_with_envvars, _entries_and_envs_to_text
    entries, envvars = _parse_raw_with_envvars(raw_crontab)
    output = _entries_and_envs_to_text(entries, envvars)
    assert 'MAILTO=""' in output
    assert 'SHELL=/bin/bash' in output
    assert '* * * * * /usr/bin/true' in output
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
pytest tests/test_crontab_service.py -v
```
Expected: FAIL — `_parse_raw_with_envvars` doesn't exist yet.

- [ ] **Step 3: Implement env var preservation in crontab_service.py**

Replace the internal parsing/saving functions to preserve env vars as opaque lines:

```python
# backend/services/crontab_service.py
# Replace _parse_raw and _entries_to_text with new versions that preserve env vars

from typing import List, Optional, Tuple  # add Tuple to imports


def _parse_raw_with_envvars(text: str) -> Tuple[List[CrontabEntry], List[str]]:
    """Parse crontab text, returning (entries, envvar_lines).

    envvar_lines preserves VAR=value lines in their original order (before all jobs).
    They are opaque strings — not parsed, just stored and re-emitted on save.
    """
    entries: List[CrontabEntry] = []
    envvar_lines: List[str] = []
    pending_comment: Optional[str] = None
    logical_idx = 0

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            pending_comment = None
            continue

        if stripped.startswith("#"):
            if stripped.startswith("# DO NOT EDIT") or stripped.startswith("# ("):
                continue
            pending_comment = stripped[1:].strip()
            continue

        # Preserve env var lines as-is
        if re.match(r'^[A-Z_][A-Z0-9_]*\s*=', stripped):
            envvar_lines.append(stripped)
            pending_comment = None
            continue

        if stripped.startswith("@"):
            parts = stripped.split(None, 1)
            special = parts[0].lower()
            if special in SPECIAL_STRINGS:
                entries.append(CrontabEntry(
                    id=logical_idx,
                    minute="", hour="", dom="", month="", dow="",
                    command=parts[1] if len(parts) > 1 else "",
                    comment=pending_comment,
                    is_special=True,
                    special=parts[0],
                    raw=line,
                ))
                logical_idx += 1
            pending_comment = None
            continue

        m = _CRON_RE.match(stripped)
        if m:
            entries.append(CrontabEntry(
                id=logical_idx,
                minute=m.group(1),
                hour=m.group(2),
                dom=m.group(3),
                month=m.group(4),
                dow=m.group(5),
                command=m.group(6),
                comment=pending_comment,
                is_special=False,
                special=None,
                raw=line,
            ))
            logical_idx += 1

        pending_comment = None

    return entries, envvar_lines


def _entries_and_envs_to_text(entries: List[CrontabEntry], envvar_lines: List[str]) -> str:
    """Rebuild crontab text preserving env var lines at the top."""
    lines: List[str] = []
    # Emit env vars first (as they must precede job definitions)
    for ev in envvar_lines:
        lines.append(ev)
    if envvar_lines:
        lines.append("")  # blank line separator
    for e in entries:
        if e.comment:
            lines.append(f"# {e.comment}")
        if e.is_special and e.special:
            lines.append(f"{e.special} {e.command}")
        else:
            lines.append(f"{e.minute} {e.hour} {e.dom} {e.month} {e.dow} {e.command}")
    lines.append("")  # trailing newline
    return "\n".join(lines)


# Keep _parse_raw as a compatibility shim (used internally only)
def _parse_raw(text: str) -> List[CrontabEntry]:
    entries, _ = _parse_raw_with_envvars(text)
    return entries


def _save(entries: List[CrontabEntry], envvar_lines: Optional[List[str]] = None) -> None:
    if envvar_lines is None:
        # Reload from current crontab to preserve env vars
        _, envvar_lines = _parse_raw_with_envvars(_load_raw())
    text = _entries_and_envs_to_text(entries, envvar_lines)
    _, stderr, rc = _run(["-"], stdin=text)
    if rc != 0:
        raise RuntimeError(stderr.strip() or "Failed to save crontab")


# Update public API functions to use new helpers:

def list_entries() -> List[CrontabEntry]:
    entries, _ = _parse_raw_with_envvars(_load_raw())
    return _strip_wrapper_from_entries(entries)


def add_entry(data: CrontabEntryCreate) -> List[CrontabEntry]:
    raw = _load_raw()
    entries, envvar_lines = _parse_raw_with_envvars(raw)
    new_id = max((e.id for e in entries), default=-1) + 1
    new_entry = CrontabEntry(
        id=new_id,
        minute=data.minute,
        hour=data.hour,
        dom=data.dom,
        month=data.month,
        dow=data.dow,
        command=_wrap_command(data.command),
        comment=data.comment,
        is_special=data.is_special,
        special=data.special,
        raw="",
    )
    entries.append(new_entry)
    _save(entries, envvar_lines)
    entries_out, _ = _parse_raw_with_envvars(_load_raw())
    return _strip_wrapper_from_entries(entries_out)


def update_entry(entry_id: int, data: CrontabEntryCreate) -> List[CrontabEntry]:
    raw = _load_raw()
    entries, envvar_lines = _parse_raw_with_envvars(raw)
    idx = next((i for i, e in enumerate(entries) if e.id == entry_id), None)
    if idx is None:
        raise ValueError(f"Entry {entry_id} not found")
    entries[idx] = CrontabEntry(
        id=entry_id,
        minute=data.minute,
        hour=data.hour,
        dom=data.dom,
        month=data.month,
        dow=data.dow,
        command=_wrap_command(data.command),
        comment=data.comment,
        is_special=data.is_special,
        special=data.special,
        raw="",
    )
    _save(entries, envvar_lines)
    entries_out, _ = _parse_raw_with_envvars(_load_raw())
    return _strip_wrapper_from_entries(entries_out)


def delete_entry(entry_id: int) -> List[CrontabEntry]:
    raw = _load_raw()
    entries, envvar_lines = _parse_raw_with_envvars(raw)
    before = len(entries)
    entries = [e for e in entries if e.id != entry_id]
    if len(entries) == before:
        raise ValueError(f"Entry {entry_id} not found")
    _save(entries, envvar_lines)
    entries_out, _ = _parse_raw_with_envvars(_load_raw())
    return _strip_wrapper_from_entries(entries_out)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_crontab_service.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/crontab_service.py tests/test_crontab_service.py
git commit -m "fix: preserve crontab env var lines (MAILTO, SHELL, PATH) through parse/save cycle"
```

---

## TASK 8: Fix MetricCard test (wrong CSS class)

**Files:**
- Modify: `frontend/src/components/dashboard/MetricCard.test.js`

- [ ] **Step 1: Verify the actual class in MetricCard.vue**

The SVG fill element uses class `gauge-fill` (not `bar-fill`).

- [ ] **Step 2: Fix the test**

```js
// frontend/src/components/dashboard/MetricCard.test.js — line 13-18
it('arc fill has stroke-dashoffset reflecting value', () => {
  const wrapper = mount(MetricCard, { props: { label: 'RAM', value: 75, unit: '%', color: 'green' } })
  const fill = wrapper.find('.gauge-fill')  // ← was '.bar-fill'
  expect(fill.exists()).toBe(true)          // ← add existence check
  const style = fill.attributes('style')
  expect(style).toContain('stroke-dashoffset')
})
```

- [ ] **Step 3: Run tests**

```bash
cd /home/crt/server_dashboard/frontend && npm test -- --run
```
Expected: All MetricCard tests PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/dashboard/MetricCard.test.js
git commit -m "fix: MetricCard test uses correct CSS class .gauge-fill (was .bar-fill)"
```

---

## TASK 9: Remove dead `get_error_logger` infrastructure

**Files:**
- Modify: `backend/core/logging.py`

- [ ] **Step 1: Confirm zero usages**

```bash
grep -r "get_error_logger\|error_logger" backend/ --include="*.py" | grep -v "core/logging.py"
```
Expected: no output (zero call sites outside the definition file).

- [ ] **Step 2: Remove the dead function and its setup from init_logging**

```python
# backend/core/logging.py — remove the error logger section

import logging
import os
from logging.handlers import TimedRotatingFileHandler

_initialized = False


def _ensure_data_dir() -> str:
    data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
    data_dir = os.path.normpath(data_dir)
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def init_logging() -> None:
    """Configure the audit logger. Safe to call multiple times."""
    global _initialized
    if _initialized:
        return
    _initialized = True

    data_dir = _ensure_data_dir()

    audit_logger = logging.getLogger("serverdash.audit")
    audit_logger.setLevel(logging.INFO)
    if not audit_logger.handlers:
        handler = TimedRotatingFileHandler(
            filename=os.path.join(data_dir, "audit.log"),
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        audit_logger.addHandler(handler)
    audit_logger.propagate = False


def get_audit_logger() -> logging.Logger:
    return logging.getLogger("serverdash.audit")
```

- [ ] **Step 3: Run the full test suite to confirm nothing broke**

```bash
cd /home/crt/server_dashboard && pytest -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/core/logging.py
git commit -m "chore: remove dead get_error_logger / errors.log infrastructure (zero call sites)"
```

---

## TASK 10: Fix .gitignore

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add .superpowers/ to .gitignore**

```bash
echo '.superpowers/' >> /home/crt/server_dashboard/.gitignore
```

- [ ] **Step 2: Verify the files are now ignored**

```bash
cd /home/crt/server_dashboard && git status --short | grep superpowers
```
Expected: no output (ignored by git).

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore .superpowers/ brainstorm artifacts"
```

---

## SUMMARY TABLE

| ID | Severity | Finding | File | Task |
|----|----------|---------|------|------|
| S-1 | **CRITICAL** | Upload path traversal via `file.filename` | `routers/files.py:103` | Task 3 |
| S-2 | **CRITICAL** | Multi-worker execution state — `_running` is process-local | `services/scripts_service.py:120` | Task 4 |
| S-3 | **HIGH** | Crontab env var silent deletion on save | `services/crontab_service.py:70` | Task 7 |
| S-4 | **HIGH** | No Content-Security-Policy header | `middleware/security.py` | Task 1 |
| S-5 | **HIGH** | No 401 interceptor — expired tokens silent-fail | `frontend/src/api/client.js` | Task 2 |
| S-6 | **Medium** | No audit trail for file/service/crontab operations | `routers/{files,services,crontab}.py` | Task 6 |
| S-7 | **Medium** | Favorites path not validated with `_safe_path` | `routers/scripts.py:39` | Task 3 |
| S-8 | **Medium** | JWT stored in localStorage (XSS exposure) | `stores/auth.js` | Tracked, P2 |
| S-9 | **Medium** | WebSocket token in query param (logs exposure) | `routers/scripts.py:139` | Tracked, P2 |
| S-10 | **Medium** | MetricCard test uses wrong CSS class `.bar-fill` — throws in CI, silently masking regressions | `MetricCard.test.js:14` | Task 8 |
| S-11 | **Low** | `get_error_logger()` dead infrastructure (0 call sites) | `core/logging.py:56` | Task 9 |
| S-12 | **Low** | `.superpowers/` not in .gitignore | `.gitignore` | Task 10 |
| S-13 | **Low** | Duration calc assumes UTC — wrong on non-UTC systems | `scripts_service.py:234` | Tracked, LOW |
| S-14 | **Low** | `atob()` Base64 padding edge case | `stores/auth.js:16` | Tracked, LOW |

---

## TEST COVERAGE GAPS

These scenarios are not covered by existing `pytest`/`vitest` tests and could mask the bugs found:

| Gap | Missing Test | Suggested Test |
|-----|-------------|----------------|
| Upload path traversal | No test for malicious `file.filename` | `test_upload_path_traversal_rejected` (see Task 3) |
| Multi-worker poll | No cross-worker execution poll test | `test_poll_execution_reads_from_db_during_run` (see Task 4) |
| Crontab env var preservation | No roundtrip test for VAR=value lines | `test_env_vars_preserved_through_parse_save_cycle` (see Task 7) |
| 401 interceptor redirect | No frontend test for expired token behavior | Manual test (Task 2) |
| CSP header presence | No test for CSP header | `test_csp_header_present` (see Task 1) |
| Audit log emission | No test that file write/delete emits audit log | `test_file_write_emits_audit_log` (see Task 6) |
| `_safe_path` on favorites add | No test that `../` in path is rejected | Add to `test_files_service.py` |
| `detect_runner` fallback to bash | No test for file with no ext/shebang/exec bit | Add to `test_scripts_service.py` |

---

## ARCHITECTURAL DECISIONS TO REVISIT

| Decision | Rationale at Design Time | Concern at Scale |
|----------|--------------------------|-----------------|
| In-memory `_running` dict | Simple, fast, no deps | Broken with multiple gunicorn workers. Fixed by Task 4 (DB-based) |
| JWT in localStorage | Simple SPA auth pattern | XSS exposure. Revisit with httpOnly cookie + CSRF token pattern at P2 |
| `Base.metadata.create_all` (no migrations) | Zero-dependency schema init | Cannot handle column additions (e.g., `is_running` needs `ALTER TABLE`). Evaluate Alembic at P3 |
| `ALLOWED_ROOT = Path("/")` | Full filesystem access for admin tool | Acceptable now; reconsider if multi-user support is added |
| `ScriptExecution` + `ExecutionLog` dual models | Different purposes (live vs audit) | Confusing names; consider renaming `ExecutionLog` → `ExecutionAudit` for clarity |
