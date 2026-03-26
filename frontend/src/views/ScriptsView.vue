<template>
  <div class="scripts-view">
    <!-- ── Left panel: favorites list ───────────────────────────────── -->
    <div class="scripts-panel">
      <div class="panel-header">
        <span class="panel-title">SCRIPT FAVORITES</span>
        <span class="count-badge">{{ store.favorites.length }}</span>
      </div>

      <div v-if="!store.loaded" class="panel-empty">
        <span class="muted">Loading…</span>
      </div>
      <div v-else-if="store.favorites.length === 0" class="panel-empty">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="empty-icon">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
        </svg>
        <span>No scripts favorited yet.</span>
        <span class="muted-sm">Star files in the Files view.</span>
      </div>
      <div v-else class="scripts-list">
        <div
          v-for="fav in store.favorites" :key="fav.id"
          class="script-item"
          :class="{ selected: selected?.id === fav.id, missing: !fav.exists }"
          @click="selectScript(fav)"
        >
          <div class="runner-pill">{{ shortRunner(fav.runner) }}</div>
          <div class="script-info">
            <span class="script-name">{{ fileName(fav.path) }}</span>
            <span class="script-dir muted-sm">{{ dirName(fav.path) }}</span>
          </div>
          <div class="item-flags">
            <span v-if="!fav.exists" class="flag flag-warn" title="File not found">!</span>
            <span v-if="fav.admin_only" class="flag flag-admin" title="Admin only">A</span>
            <span v-if="fav.run_as_root" class="flag flag-root" title="Runs as root">R</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Right panel: detail + execution ──────────────────────────── -->
    <div class="detail-panel" v-if="selected">
      <!-- Header -->
      <div class="detail-header">
        <div class="detail-title-row">
          <span class="runner-pill lg">{{ selected.runner }}</span>
          <span class="detail-name">{{ fileName(selected.path) }}</span>
        </div>
        <!-- Path — click navigates to Files view at that directory -->
        <div class="detail-path" @click="openInFiles(selected.path)" title="Open directory in Files">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
          <span class="path-text">{{ selected.path }}</span>
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="ext-link">
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
          </svg>
        </div>
      </div>

      <!-- Admin config: run_as_root / admin_only / remove -->
      <div v-if="isAdmin" class="config-bar">
        <label class="toggle-wrap" :class="{ on: selected.run_as_root }">
          <input type="checkbox" :checked="selected.run_as_root" @change="toggleFlag('run_as_root')" />
          <span class="toggle-track"><span class="toggle-thumb"></span></span>
          <span class="toggle-label">Run as root</span>
        </label>
        <label class="toggle-wrap" :class="{ on: selected.admin_only }">
          <input type="checkbox" :checked="selected.admin_only" @change="toggleFlag('admin_only')" />
          <span class="toggle-track"><span class="toggle-thumb"></span></span>
          <span class="toggle-label">Admin only</span>
        </label>
        <button class="icon-btn btn-danger" @click="removeFavorite" title="Remove from favorites">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
          Remove favorite
        </button>
      </div>

      <!-- Execution controls -->
      <div class="exec-bar">
        <input
          v-model="scriptArgs"
          class="args-input"
          placeholder="Arguments (optional, space-separated)"
        />
        <div v-if="selected.run_as_root" class="sudo-inline" :class="{ unlocked: sudoPassword }">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
            <path v-if="!sudoPassword" d="M7 11V7a5 5 0 0 1 10 0v4"/>
            <path v-else d="M7 11V7a5 5 0 0 1 9.9-1"/>
          </svg>
          <input v-model="sudoPassword" type="password" placeholder="sudo password" class="sudo-input" autocomplete="off" />
          <button v-if="sudoPassword" class="sudo-clear" @click="sudoPassword = ''">✕</button>
        </div>
        <button
          class="run-btn"
          :class="{ running: polling }"
          :disabled="polling || !selected.exists"
          @click="runScript"
        >
          <svg v-if="!polling" width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
          <svg v-else width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin"><circle cx="12" cy="12" r="10" stroke-dasharray="20 60"/></svg>
          {{ polling ? 'Running…' : 'Run' }}
        </button>
        <button v-if="execId && !polling" class="clear-btn" @click="clearOutput">Clear</button>
      </div>

      <div v-if="!selected.exists" class="warn-banner">
        Script file not found on disk — it may have been moved or deleted.
      </div>

      <!-- Tabs -->
      <div class="tabs">
        <button class="tab-btn" :class="{ active: tab === 'output' }" @click="tab = 'output'">Output</button>
        <button class="tab-btn" :class="{ active: tab === 'history' }" @click="switchHistory">
          History
        </button>
      </div>

      <!-- Output terminal -->
      <div v-if="tab === 'output'" class="terminal-wrap">
        <div v-if="!execId" class="terminal-empty">
          Press <strong>Run</strong> to execute the script.
        </div>
        <div v-else class="terminal">
          <div class="terminal-status">
            <span class="exec-badge" :class="statusClass">{{ statusLabel }}</span>
            <span class="exec-time muted-sm">{{ execStarted }}</span>
          </div>
          <pre ref="terminalEl" class="terminal-output">{{ outputLines.join('\n') }}</pre>
        </div>
      </div>

      <!-- History tab -->
      <div v-if="tab === 'history'" class="history-wrap">
        <div v-if="historyLoading" class="terminal-empty muted">Loading…</div>
        <div v-else-if="history.length === 0" class="terminal-empty muted">No executions yet.</div>
        <div v-else>
          <div
            v-for="exec in history" :key="exec.id"
            class="history-item"
            :class="{ expanded: expandedExec === exec.id }"
            @click="toggleHistoryExec(exec)"
          >
            <div class="history-row">
              <span class="exec-badge sm" :class="exec.exit_code === 0 ? 'ok' : (exec.exit_code == null ? 'running-sm' : 'fail')">
                {{ exec.exit_code == null ? '…' : exec.exit_code }}
              </span>
              <span class="history-time">{{ formatDate(exec.started_at) }}</span>
              <span class="history-dur muted-sm">{{ duration(exec) }}</span>
              <span class="history-user muted-sm">{{ exec.triggered_by }}</span>
              <svg v-if="exec.run_as_root" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" title="Run as root"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
              <span class="expand-arrow">{{ expandedExec === exec.id ? '▲' : '▼' }}</span>
            </div>
            <pre v-if="expandedExec === exec.id" class="history-output">{{ exec.output || '(no output)' }}</pre>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="detail-panel empty-detail">
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" class="empty-icon">
        <polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>
      </svg>
      <span>Select a script from the list</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api/client.js'
import { useScriptsStore } from '../stores/scripts.js'
import { useAuthStore } from '../stores/auth.js'

const store = useScriptsStore()
const auth = useAuthStore()
const router = useRouter()

const isAdmin = auth.role === 'admin'

const selected = ref(null)
const sudoPassword = ref('')
const scriptArgs = ref('')
const tab = ref('output')

// Execution state
const execId = ref(null)
const polling = ref(false)
const outputLines = ref([])
const currentExitCode = ref(null)
const execStarted = ref('')
const pollTimer = ref(null)
const terminalEl = ref(null)

// History state
const history = ref([])
const historyLoading = ref(false)
const expandedExec = ref(null)

onMounted(() => store.loadFavorites())

// ── Helpers ──────────────────────────────────────────────────────────────────

function fileName(path) {
  return path.split('/').pop()
}
function dirName(path) {
  const parts = path.split('/')
  parts.pop()
  return parts.join('/') || '/'
}
function shortRunner(runner) {
  if (!runner) return '?'
  const name = runner.split('/').pop()
  return name.length > 8 ? name.slice(0, 7) + '…' : name
}

const statusLabel = computed(() => {
  if (polling.value) return 'RUNNING'
  if (currentExitCode.value === 0) return 'EXIT 0 ✓'
  if (currentExitCode.value != null) return `EXIT ${currentExitCode.value}`
  return '—'
})
const statusClass = computed(() => {
  if (polling.value) return 'running-sm'
  if (currentExitCode.value === 0) return 'ok'
  if (currentExitCode.value != null) return 'fail'
  return ''
})

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' })
}
function duration(exec) {
  if (!exec.ended_at || !exec.started_at) return exec.running ? 'running' : '—'
  const ms = new Date(exec.ended_at) - new Date(exec.started_at)
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`
}

// ── Selection ─────────────────────────────────────────────────────────────────

function selectScript(fav) {
  selected.value = { ...fav }
  stopPolling()
  execId.value = null
  outputLines.value = []
  currentExitCode.value = null
  tab.value = 'output'
  history.value = []
  expandedExec.value = null
}

// ── Navigation to Files ───────────────────────────────────────────────────────

function openInFiles(path) {
  const dir = dirName(path)
  router.push({ path: '/files', query: { dir } })
}

// ── Execution ─────────────────────────────────────────────────────────────────

async function runScript() {
  if (!selected.value || polling.value) return

  const args = scriptArgs.value.trim()
    ? scriptArgs.value.trim().split(/\s+/)
    : []

  try {
    const { data } = await api.post(`/scripts/favorites/${selected.value.id}/run`, {
      sudo_password: selected.value.run_as_root ? (sudoPassword.value || null) : null,
      args,
    })
    execId.value = data.id
    outputLines.value = []
    currentExitCode.value = null
    execStarted.value = formatDate(new Date().toISOString())
    tab.value = 'output'
    startPolling()
  } catch (e) {
    alert(e.response?.data?.detail || 'Failed to start script')
  }
}

function startPolling() {
  polling.value = true
  pollTimer.value = setInterval(doPoll, 500)
}

function stopPolling() {
  if (pollTimer.value) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
  polling.value = false
}

async function doPoll() {
  if (!execId.value) return
  try {
    const { data } = await api.get(`/scripts/executions/${execId.value}`)
    outputLines.value = data.lines
    if (!data.running) {
      currentExitCode.value = data.exit_code
      stopPolling()
    }
    // Auto-scroll terminal
    await nextTick()
    if (terminalEl.value) {
      terminalEl.value.scrollTop = terminalEl.value.scrollHeight
    }
  } catch {
    stopPolling()
  }
}

function clearOutput() {
  execId.value = null
  outputLines.value = []
  currentExitCode.value = null
}

// ── Admin config ──────────────────────────────────────────────────────────────

async function toggleFlag(flag) {
  if (!selected.value) return
  const newVal = !selected.value[flag]
  try {
    const updated = await store.updateFavorite(selected.value.id, { [flag]: newVal })
    selected.value = { ...updated }
  } catch (e) {
    alert(e.response?.data?.detail || 'Update failed')
  }
}

async function removeFavorite() {
  if (!selected.value) return
  if (!confirm(`Remove "${fileName(selected.value.path)}" from favorites?`)) return
  await store.removeFavoriteByPath(selected.value.path)
  selected.value = null
}

// ── History ───────────────────────────────────────────────────────────────────

async function switchHistory() {
  tab.value = 'history'
  await loadHistory()
}

async function loadHistory() {
  if (!selected.value) return
  historyLoading.value = true
  try {
    const { data } = await api.get(`/scripts/favorites/${selected.value.id}/history`)
    history.value = data
  } catch {
    history.value = []
  } finally {
    historyLoading.value = false
  }
}

function toggleHistoryExec(exec) {
  expandedExec.value = expandedExec.value === exec.id ? null : exec.id
}
</script>

<style scoped>
.scripts-view {
  display: flex;
  height: calc(100vh - var(--header-height) - 48px);
  gap: 0;
  overflow: hidden;
}

/* ── Left panel ─────────────────────────────────────────────────────────── */
.scripts-panel {
  width: 280px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px 0 0 8px;
  overflow: hidden;
}
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: var(--surface-2);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.panel-title {
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 1.5px;
  color: var(--text-muted);
}
.count-badge {
  font-family: var(--font-mono);
  font-size: 10px;
  background: var(--surface-3);
  color: var(--text-muted);
  padding: 1px 6px;
  border-radius: 10px;
}
.panel-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 20px;
  color: var(--text-muted);
  font-size: 12px;
  text-align: center;
}
.empty-icon { color: var(--text-dim); margin-bottom: 4px; }
.scripts-list { flex: 1; overflow-y: auto; padding: 4px 0; }
.script-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  transition: background 0.1s;
  border-bottom: 1px solid var(--border);
}
.script-item:hover { background: var(--surface-2); }
.script-item.selected { background: var(--surface-3); border-left: 2px solid var(--accent-blue); padding-left: 10px; }
.script-item.missing { opacity: 0.5; }
.script-info { flex: 1; min-width: 0; }
.script-name {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-bright);
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.script-dir {
  font-size: 10px;
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.item-flags { display: flex; gap: 3px; flex-shrink: 0; }

/* ── Runner pill ─────────────────────────────────────────────────────────── */
.runner-pill {
  font-family: var(--font-mono);
  font-size: 9px;
  padding: 2px 6px;
  border-radius: 3px;
  background: var(--surface-3);
  color: var(--accent-cyan);
  border: 1px solid var(--border-bright);
  white-space: nowrap;
  flex-shrink: 0;
}
.runner-pill.lg {
  font-size: 11px;
  padding: 3px 8px;
  color: var(--accent-blue);
}

/* ── Flags ───────────────────────────────────────────────────────────────── */
.flag {
  font-family: var(--font-mono);
  font-size: 9px;
  padding: 1px 4px;
  border-radius: 3px;
  font-weight: 700;
}
.flag-warn { background: rgba(239,68,68,0.15); color: var(--accent-red); }
.flag-admin { background: rgba(139,92,246,0.15); color: #a78bfa; }
.flag-root { background: rgba(245,158,11,0.15); color: var(--accent-yellow); }

/* ── Right panel ─────────────────────────────────────────────────────────── */
.detail-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: none;
  border-radius: 0 8px 8px 0;
  overflow: hidden;
}
.detail-panel.empty-detail {
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--text-muted);
  font-size: 13px;
}

.detail-header {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  background: var(--surface-2);
  flex-shrink: 0;
}
.detail-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}
.detail-name {
  font-family: var(--font-mono);
  font-size: 14px;
  color: var(--text-bright);
  font-weight: 600;
}
.detail-path {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-muted);
  cursor: pointer;
  border-radius: 4px;
  padding: 3px 5px;
  transition: background 0.15s, color 0.15s;
  width: fit-content;
}
.detail-path:hover { background: var(--surface-3); color: var(--accent-blue); }
.path-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 500px; }
.ext-link { opacity: 0.5; }

/* ── Config bar (admin) ──────────────────────────────────────────────────── */
.config-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 16px;
  background: var(--surface-2);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.toggle-wrap {
  display: flex;
  align-items: center;
  gap: 7px;
  cursor: pointer;
  user-select: none;
}
.toggle-wrap input { display: none; }
.toggle-track {
  width: 32px; height: 16px;
  background: var(--surface-3);
  border: 1px solid var(--border-bright);
  border-radius: 8px;
  position: relative;
  transition: background 0.15s, border-color 0.15s;
}
.toggle-wrap.on .toggle-track {
  background: rgba(14,165,233,0.25);
  border-color: var(--accent-blue);
}
.toggle-thumb {
  position: absolute;
  top: 2px; left: 2px;
  width: 10px; height: 10px;
  border-radius: 50%;
  background: var(--text-dim);
  transition: transform 0.15s, background 0.15s;
}
.toggle-wrap.on .toggle-thumb {
  transform: translateX(16px);
  background: var(--accent-blue);
}
.toggle-label { font-size: 12px; color: var(--text-muted); }
.toggle-wrap.on .toggle-label { color: var(--text); }
.icon-btn {
  display: flex; align-items: center; gap: 5px;
  background: none; border: 1px solid var(--border);
  padding: 4px 10px; border-radius: 4px;
  font-size: 11px; font-family: var(--font-mono);
  cursor: pointer; color: var(--text-muted);
  transition: all 0.15s; margin-left: auto;
}
.icon-btn.btn-danger:hover { border-color: var(--accent-red); color: var(--accent-red); }

/* ── Execution bar ───────────────────────────────────────────────────────── */
.exec-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  flex-wrap: wrap;
}
.args-input {
  flex: 1; min-width: 200px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  padding: 5px 10px;
  border-radius: 4px;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text);
  outline: none;
  transition: border-color 0.15s;
}
.args-input:focus { border-color: var(--accent-blue); }
.args-input::placeholder { color: var(--text-dim); }
.sudo-inline {
  display: flex; align-items: center; gap: 6px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 4px; padding: 5px 9px;
  color: var(--text-muted); transition: border-color 0.15s;
}
.sudo-inline.unlocked { border-color: var(--accent-green); color: var(--accent-green); }
.sudo-input {
  background: none; border: none; outline: none;
  font-family: var(--font-mono); font-size: 12px;
  color: var(--text); width: 140px;
}
.sudo-input::placeholder { color: var(--text-dim); }
.sudo-clear {
  background: none; border: none; cursor: pointer;
  color: var(--text-muted); font-size: 11px; padding: 0; line-height: 1;
}
.sudo-clear:hover { color: var(--accent-red); }
.run-btn {
  display: flex; align-items: center; gap: 6px;
  background: var(--accent-blue); border: none;
  color: #fff; padding: 5px 16px; border-radius: 4px;
  font-family: var(--font-mono); font-size: 12px;
  cursor: pointer; transition: opacity 0.15s; white-space: nowrap;
}
.run-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.run-btn.running { background: var(--accent-yellow); }
.clear-btn {
  background: none; border: 1px solid var(--border);
  color: var(--text-muted); padding: 5px 10px;
  border-radius: 4px; font-family: var(--font-mono);
  font-size: 11px; cursor: pointer; transition: all 0.15s;
}
.clear-btn:hover { border-color: var(--border-bright); color: var(--text); }
.warn-banner {
  background: rgba(239,68,68,0.1);
  border-bottom: 1px solid var(--accent-red);
  color: var(--accent-red);
  padding: 6px 16px;
  font-size: 12px;
  flex-shrink: 0;
}

/* ── Tabs ────────────────────────────────────────────────────────────────── */
.tabs {
  display: flex;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  background: var(--surface-2);
}
.tab-btn {
  background: none; border: none; border-bottom: 2px solid transparent;
  padding: 7px 16px;
  font-family: var(--font-mono); font-size: 11px;
  color: var(--text-muted); cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}
.tab-btn:hover { color: var(--text); }
.tab-btn.active { color: var(--accent-blue); border-bottom-color: var(--accent-blue); }

/* ── Terminal ────────────────────────────────────────────────────────────── */
.terminal-wrap { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.terminal-empty {
  flex: 1; display: flex; align-items: center; justify-content: center;
  font-size: 13px; color: var(--text-muted);
}
.terminal { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.terminal-status {
  display: flex; align-items: center; gap: 10px;
  padding: 6px 14px;
  background: var(--surface-2);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.exec-badge {
  font-family: var(--font-mono);
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 3px;
  font-weight: 600;
  letter-spacing: 0.5px;
}
.exec-badge.ok { background: rgba(34,197,94,0.15); color: var(--accent-green); }
.exec-badge.fail { background: rgba(239,68,68,0.15); color: var(--accent-red); }
.exec-badge.running-sm { background: rgba(245,158,11,0.15); color: var(--accent-yellow); }
.exec-badge.sm { font-size: 9px; padding: 1px 5px; }
.exec-time { font-size: 11px; }
.terminal-output {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.7;
  color: var(--text-muted);
  white-space: pre-wrap;
  word-break: break-all;
  background: var(--bg);
}

/* ── History ─────────────────────────────────────────────────────────────── */
.history-wrap { flex: 1; overflow-y: auto; }
.history-item {
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  transition: background 0.1s;
}
.history-item:hover { background: var(--surface-2); }
.history-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 16px;
  font-size: 12px;
}
.history-time { font-family: var(--font-mono); font-size: 11px; color: var(--text); flex: 1; }
.history-dur { font-family: var(--font-mono); }
.history-user { font-family: var(--font-mono); }
.expand-arrow { font-size: 9px; color: var(--text-dim); }
.history-output {
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.6;
  color: var(--text-muted);
  padding: 8px 16px 12px 32px;
  white-space: pre-wrap;
  word-break: break-all;
  border-top: 1px dashed var(--border);
  background: var(--bg);
  max-height: 300px;
  overflow-y: auto;
}

/* ── Utilities ───────────────────────────────────────────────────────────── */
.muted { color: var(--text-muted); }
.muted-sm { font-size: 10px; color: var(--text-muted); font-family: var(--font-mono); }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
