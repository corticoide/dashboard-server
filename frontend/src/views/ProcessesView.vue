<template>
  <div class="processes-view">
    <div class="page-header">
      <div class="page-title">
        <i class="pi pi-server page-icon" />
        <span>PROCESSES</span>
        <span class="live-dot" :class="{ tick: liveTick }" title="Live" />
        <span v-if="truncated" class="badge-yellow">CAPPED AT 500</span>
      </div>
      <div class="header-actions">
        <div class="search-field">
          <i class="pi pi-search search-icon" />
          <input v-model="filterTerm" class="search-input" placeholder="Filter by name…" />
        </div>
      </div>
    </div>

    <!-- Summary bar -->
    <div class="summary-bar">
      <button
        class="summary-pill"
        :class="{ 'pill-active': statusFilter === 'running' }"
        @click="statusFilter = statusFilter === 'running' ? '' : 'running'"
      >
        <span class="pill-dot dot-running" />
        <span class="pill-count">{{ processStats.running }}</span>
        <span class="pill-label">RUNNING</span>
      </button>
      <button
        class="summary-pill"
        :class="{ 'pill-active': statusFilter === 'sleeping' }"
        @click="statusFilter = statusFilter === 'sleeping' ? '' : 'sleeping'"
      >
        <span class="pill-dot dot-sleeping" />
        <span class="pill-count">{{ processStats.sleeping }}</span>
        <span class="pill-label">SLEEPING</span>
      </button>
      <button
        v-if="processStats.zombie > 0"
        class="summary-pill pill-zombie"
        :class="{ 'pill-active': statusFilter === 'zombie' }"
        @click="statusFilter = statusFilter === 'zombie' ? '' : 'zombie'"
      >
        <span class="pill-dot dot-zombie" />
        <span class="pill-count">{{ processStats.zombie }}</span>
        <span class="pill-label">ZOMBIE</span>
      </button>
      <span class="summary-total">{{ countLabel }}</span>
    </div>

    <div v-if="error" class="banner banner-error"><i class="pi pi-times-circle" />{{ error }}</div>

    <DataTable
      :value="filteredProcesses"
      size="small"
      class="proc-table"
      :loading="initialLoading"
      scrollable
      scroll-height="flex"
    >
      <template #empty>
        <div class="table-empty">
          <i class="pi pi-server" style="font-size: 24px; opacity: 0.3;" />
          <span>No processes found.</span>
        </div>
      </template>

      <Column field="name" header="NAME" sortable style="min-width: 160px">
        <template #body="{ data }">
          <div class="name-cell">
            <span class="proc-name">{{ data.name }}</span>
            <span v-if="data.watched" class="badge-blue">WATCHED</span>
          </div>
        </template>
      </Column>

      <Column field="pid" header="PID" sortable style="width: 72px">
        <template #body="{ data }">
          <span class="cell-mono cell-dim">{{ data.pid }}</span>
        </template>
      </Column>

      <Column field="cpu_percent" header="CPU %" sortable style="width: 120px">
        <template #body="{ data }">
          <div class="bar-cell">
            <div class="bar-track">
              <div
                class="bar-fill"
                :class="barClass(data.cpu_percent)"
                :style="{ width: Math.min(data.cpu_percent, 100) + '%' }"
              />
            </div>
            <span class="cell-mono bar-val" :class="{ 'val-hot': data.cpu_percent > 50 }">
              {{ data.cpu_percent.toFixed(1) }}
            </span>
          </div>
        </template>
      </Column>

      <Column field="memory_mb" header="RAM MB" sortable style="width: 90px">
        <template #body="{ data }">
          <span class="cell-mono" :class="{ 'val-hot': data.memory_mb > 500, 'cell-dim': data.memory_mb <= 500 }">
            {{ data.memory_mb.toFixed(0) }}
          </span>
        </template>
      </Column>

      <Column field="username" header="USER" style="width: 100px">
        <template #body="{ data }">
          <span class="cell-mono cell-dim">{{ data.username }}</span>
        </template>
      </Column>

      <Column field="status" header="STATUS" style="width: 110px">
        <template #body="{ data }">
          <div class="status-cell">
            <span class="state-dot" :class="`state-dot--${data.status}`" />
            <span :class="statusBadgeClass(data.status)">{{ data.status }}</span>
          </div>
        </template>
      </Column>

      <Column header="ACTIONS" style="width: 90px" v-if="canExecute">
        <template #body="{ data }">
          <div class="row-actions">
            <Button
              v-if="!data.watched"
              icon="pi pi-eye"
              size="small"
              text
              severity="info"
              v-tooltip.top="'Watch process'"
              @click="openWatchDialog(data)"
            />
            <Button
              v-else
              icon="pi pi-eye-slash"
              size="small"
              text
              severity="secondary"
              v-tooltip.top="'Unwatch'"
              @click="unwatch(data)"
            />
            <Button
              icon="pi pi-times-circle"
              size="small"
              text
              severity="danger"
              v-tooltip.top="'Kill process'"
              @click="killProcess(data)"
            />
          </div>
        </template>
      </Column>
    </DataTable>

    <!-- Watch dialog -->
    <Dialog v-model:visible="watchDialog" header="WATCH PROCESS" :modal="true" style="width: 380px">
      <div class="dialog-form">
        <div class="form-field">
          <label>Process</label>
          <InputText :value="watchTarget?.name" disabled size="small" />
        </div>
        <div class="form-field">
          <label>Alert email</label>
          <InputText v-model="watchForm.email_to" size="small" placeholder="you@example.com" />
        </div>
        <div class="form-field">
          <label>Cooldown (minutes)</label>
          <InputNumber v-model="watchForm.cooldown_minutes" :min="1" size="small" />
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" size="small" severity="secondary" @click="watchDialog = false" />
        <Button label="Watch" icon="pi pi-eye" size="small" :loading="watchSaving" @click="saveWatch" />
      </template>
    </Dialog>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useConfirm } from 'primevue/useconfirm'
import { useAuthStore } from '../stores/auth.js'
import { usePolling } from '../composables/usePolling.js'
import api from '../api/client.js'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'

const MAX_DISPLAY = 500

const auth = useAuthStore()
const confirm = useConfirm()

const processes = ref([])
const initialLoading = ref(false)
const truncated = ref(false)
const error = ref(null)
const filterTerm = ref('')
const statusFilter = ref('')
const liveTick = ref(false)

let fetching = false

const watchDialog = ref(false)
const watchTarget = ref(null)
const watchSaving = ref(false)
const watchForm = ref({ email_to: '', cooldown_minutes: 60 })

const canExecute = computed(() => auth.hasPermission('processes', 'execute'))

const processStats = computed(() => ({
  running:  processes.value.filter(p => p.status === 'running').length,
  sleeping: processes.value.filter(p => p.status === 'sleeping').length,
  zombie:   processes.value.filter(p => p.status === 'zombie').length,
}))

const filteredProcesses = computed(() => {
  let list = processes.value
  if (statusFilter.value) list = list.filter(p => p.status === statusFilter.value)
  if (!filterTerm.value) return list
  const term = filterTerm.value.toLowerCase()
  return list.filter(p => p.name.toLowerCase().includes(term))
})

const countLabel = computed(() => {
  const total = processes.value.length
  const shown = filteredProcesses.value.length
  return (filterTerm.value || statusFilter.value) ? `${shown} / ${total}` : `${total} total`
})

async function loadProcesses() {
  if (fetching) return
  fetching = true
  if (processes.value.length === 0) initialLoading.value = true
  try {
    const r = await api.get('/processes/')
    processes.value = r.data.slice(0, MAX_DISPLAY)
    truncated.value = r.data.length >= MAX_DISPLAY
    error.value = null
    liveTick.value = true
    setTimeout(() => { liveTick.value = false }, 400)
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load processes'
  } finally {
    initialLoading.value = false
    fetching = false
  }
}

function statusBadgeClass(status) {
  return {
    running:    'badge-green',
    sleeping:   'badge-neutral',
    disk_sleep: 'badge-yellow',
    stopped:    'badge-yellow',
    zombie:     'badge-red',
  }[status] ?? 'badge-neutral'
}

function barClass(cpu) {
  if (cpu > 75) return 'bar-critical'
  if (cpu > 50) return 'bar-hot'
  if (cpu > 20) return 'bar-warm'
  return 'bar-ok'
}

function openWatchDialog(proc) {
  watchTarget.value = proc
  watchForm.value = { email_to: '', cooldown_minutes: 60 }
  watchDialog.value = true
}

async function saveWatch() {
  watchSaving.value = true
  try {
    await api.post('/processes/watch', {
      name: watchTarget.value.name,
      email_to: watchForm.value.email_to,
      cooldown_minutes: watchForm.value.cooldown_minutes,
    })
    watchDialog.value = false
    await loadProcesses()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to watch process'
  } finally {
    watchSaving.value = false
  }
}

async function unwatch(proc) {
  try {
    await api.delete(`/processes/watch/${encodeURIComponent(proc.name)}`)
    await loadProcesses()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to unwatch process'
  }
}

function killProcess(proc) {
  confirm.require({
    message: `Kill process "${proc.name}" (PID ${proc.pid})?`,
    header: 'Confirm Kill',
    icon: 'pi pi-exclamation-triangle',
    acceptSeverity: 'danger',
    accept: async () => {
      try {
        await api.post(`/processes/${proc.pid}/kill`)
        await loadProcesses()
      } catch (e) {
        error.value = e.response?.data?.detail || 'Failed to kill process'
      }
    },
  })
}

const { start, stop } = usePolling(loadProcesses, 2000)

onMounted(() => {
  loadProcesses()
  start()
})

onUnmounted(stop)
</script>

<style scoped>
.processes-view { display: flex; flex-direction: column; height: 100%; gap: 12px; }

/* ── Header ──────────────────────────────────────── */
.page-header {
  display: flex; align-items: center; justify-content: space-between;
  padding-bottom: 14px;
  border-bottom: 2px solid var(--border-strong);
  flex-shrink: 0;
}
.page-title {
  display: flex; align-items: center; gap: 10px;
  font-family: var(--font-mono); font-size: var(--text-sm);
  font-weight: 700; letter-spacing: 2px; color: var(--p-text-muted-color);
}
.page-icon { color: var(--brand-orange); font-size: var(--text-lg); }
.header-actions { display: flex; align-items: center; gap: 8px; }

/* Search */
.search-field {
  position: relative; display: flex; align-items: center;
}
.search-icon {
  position: absolute; left: 8px; font-size: 11px;
  color: var(--p-text-muted-color); pointer-events: none;
}
.search-input {
  padding: 5px 10px 5px 28px;
  background: var(--p-surface-900);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-base);
  font-family: var(--font-mono); font-size: var(--text-sm);
  color: var(--p-text-color);
  outline: none; width: 200px;
  transition: var(--transition-fast);
}
.search-input:focus { border-color: var(--brand-orange); }

/* Live dot */
.live-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--p-green-500); flex-shrink: 0;
  transition: background 0.15s, box-shadow 0.15s;
}
.live-dot.tick {
  background: var(--p-green-400);
  box-shadow: 0 0 8px var(--p-green-400);
}

/* ── Summary bar ─────────────────────────────────── */
.summary-bar {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.summary-pill {
  display: flex; align-items: center; gap: 6px;
  padding: 4px 12px; border-radius: 20px;
  border: 1px solid var(--border-strong);
  background: var(--p-surface-card);
  cursor: pointer; font-family: var(--font-mono);
  transition: background 0.15s, border-color 0.15s;
}
.summary-pill:hover { background: var(--p-surface-hover); }
.summary-pill.pill-active {
  border-color: color-mix(in srgb, var(--p-green-500) 40%, transparent);
  background: color-mix(in srgb, var(--p-green-500) 8%, transparent);
}
.pill-zombie.pill-active {
  border-color: color-mix(in srgb, var(--p-red-500) 40%, transparent);
  background: color-mix(in srgb, var(--p-red-500) 8%, transparent);
}
.pill-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.dot-running  { background: var(--p-green-500); animation: pulse-green 2s ease-in-out infinite; }
.dot-sleeping { background: var(--p-surface-400); }
.dot-zombie   { background: var(--p-red-500); }
@keyframes pulse-green {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.6; }
}
.pill-count { font-size: var(--text-base); font-weight: 700; color: var(--p-text-color); line-height: 1; }
.pill-label { font-size: var(--text-2xs); letter-spacing: 1.5px; color: var(--p-text-muted-color); }
.summary-total {
  font-family: var(--font-mono); font-size: var(--text-xs);
  color: var(--p-text-muted-color); margin-left: 4px;
}

/* ── Table ───────────────────────────────────────── */
.proc-table { flex: 1; }

:deep(.proc-table .p-datatable-thead th) { background: transparent; }
:deep(.proc-table .p-datatable-column-header-content) {
  font-family: var(--font-mono); font-size: var(--text-2xs);
  letter-spacing: 1.5px; color: var(--p-text-muted-color);
  text-transform: uppercase; font-weight: 600;
}
:deep(.proc-table .p-datatable-tbody td) { padding: 5px 10px; }
:deep(.proc-table .p-datatable-tbody tr:hover td) {
  background: color-mix(in srgb, var(--brand-orange) 6%, transparent) !important;
}
:deep(.proc-table .p-row-selected td) {
  background: color-mix(in srgb, var(--brand-orange) 10%, transparent) !important;
}

/* ── Table cells ─────────────────────────────────── */
.name-cell { display: flex; align-items: center; gap: 6px; }
.proc-name { font-family: var(--font-mono); font-size: var(--text-sm); font-weight: 500; }
.watched-tag { font-size: var(--text-xs) !important; }

.cell-mono { font-family: var(--font-mono); font-size: var(--text-sm); }
.cell-dim  { color: var(--p-text-muted-color); }
.val-hot   { color: var(--p-red-400); font-weight: 600; }

/* CPU bar */
.bar-cell { display: flex; align-items: center; gap: 8px; }
.bar-track {
  width: 56px; height: 5px;
  background: var(--p-surface-border);
  border-radius: 3px; overflow: hidden; flex-shrink: 0;
}
.bar-fill { height: 100%; border-radius: 3px; transition: width 0.5s ease; }
.bar-ok       { background: var(--p-green-500); }
.bar-warm     { background: var(--p-yellow-500); }
.bar-hot      { background: var(--p-orange-400); }
.bar-critical { background: var(--p-red-400); }
.bar-val { font-size: var(--text-xs); }

/* Status cell */
.status-cell { display: flex; align-items: center; gap: 6px; }
.state-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.state-dot--running    { background: var(--p-green-500); animation: pulse-green 2s ease-in-out infinite; }
.state-dot--sleeping   { background: var(--p-surface-400); }
.state-dot--disk_sleep { background: var(--p-yellow-500); }
.state-dot--stopped    { background: var(--p-orange-400); }
.state-dot--zombie     { background: var(--p-red-500); }

.row-actions { display: flex; gap: 2px; }

/* ── Table empty ─────────────────────────────────── */
.table-empty {
  display: flex; flex-direction: column; align-items: center;
  gap: 8px; padding: 32px 16px;
  color: var(--p-text-muted-color); font-family: var(--font-mono); font-size: var(--text-sm);
}

/* ── Watch dialog ────────────────────────────────── */
.dialog-form { display: flex; flex-direction: column; gap: 12px; padding: 8px 0; }
.form-field { display: flex; flex-direction: column; gap: 4px; }
.form-field label { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-muted-color); letter-spacing: 1px; }
</style>
