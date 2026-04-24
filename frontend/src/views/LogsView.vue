<template>
  <div class="logs-view">

    <!-- Stats row -->
    <div class="stats-row">
      <div class="stat-card">
        <i class="pi pi-list stat-icon" />
        <div class="stat-body">
          <span class="stat-label">TOTAL</span>
          <span class="stat-value">{{ stats.total }}</span>
        </div>
      </div>
      <div class="stat-card stat-card--success">
        <i class="pi pi-check-circle stat-icon stat-icon--success" />
        <div class="stat-body">
          <span class="stat-label">SUCCESS</span>
          <span class="stat-value stat-val-success">{{ stats.success }}</span>
        </div>
      </div>
      <div class="stat-card stat-card--failed">
        <i class="pi pi-times-circle stat-icon stat-icon--failed" />
        <div class="stat-body">
          <span class="stat-label">FAILED</span>
          <span class="stat-value stat-val-failed">{{ stats.failed }}</span>
        </div>
      </div>
      <div class="stat-card stat-card--24h">
        <i class="pi pi-clock stat-icon stat-icon--24h" />
        <div class="stat-body">
          <span class="stat-label">LAST 24H</span>
          <span class="stat-value stat-val-24h">{{ stats.last_24h }}</span>
        </div>
      </div>
    </div>

    <!-- Filters toolbar -->
    <div class="filters-toolbar">
      <div class="filters-start">
        <div class="search-field">
          <i class="pi pi-search search-icon" />
          <input
            v-model="filterScript"
            class="search-input"
            placeholder="Filter by script…"
            @input="debouncedLoadLogs"
          />
        </div>
        <div class="status-pills">
          <button
            v-for="opt in statusOptions"
            :key="opt.value"
            class="status-pill"
            :class="{ active: filterStatus === opt.value, [`pill-${opt.value}`]: true }"
            @click="setStatus(opt.value)"
          >
            <span v-if="opt.dot" class="pill-dot" :class="`dot-${opt.value}`"></span>
            {{ opt.label }}
          </button>
        </div>
      </div>
      <div class="filters-end">
        <Button
          v-if="hasActiveFilters"
          label="Clear"
          icon="pi pi-times"
          text size="small"
          severity="secondary"
          @click="clearFilters"
        />
        <DatePicker
          v-model="dateRange"
          selectionMode="range"
          :manualInput="false"
          placeholder="Date range"
          size="small"
          show-icon
          show-clear
          @update:model-value="loadLogs"
        />
        <button class="refresh-btn" :disabled="loading" v-tooltip.bottom="'Refresh'" @click="loadLogs">
          <i :class="['pi', loading ? 'pi-spin pi-spinner' : 'pi-refresh']" />
        </button>
      </div>
    </div>

    <!-- Table -->
    <DataTable
      :value="logs"
      :loading="loading"
      v-model:expanded-rows="expandedRows"
      @row-expand="onRowExpand"
      @row-collapse="onRowCollapse"
      striped-rows
      size="small"
      data-key="id"
      scrollable
      scroll-height="flex"
      :virtual-scroller-options="{ itemSize: 50 }"
      removableSort
      class="logs-table"
    >
      <template #empty>
        <div class="empty-state">
          <i class="pi pi-list empty-icon" />
          <span class="empty-text">No execution logs found</span>
        </div>
      </template>

      <Column expander style="width: 2rem" />

      <Column field="script_path" header="SCRIPT" sortable style="min-width: 200px">
        <template #body="{ data }">
          <div class="script-cell">
            <button
              v-if="scriptsStore.isFavorite(data.script_path)"
              class="script-name-link"
              v-tooltip.top="'Open in Scripts'"
              @click="navigateToScript(data.script_path)"
            >
              <span class="cell-script-name cell-script-name--link">{{ scriptName(data.script_path) }}</span>
              <i class="pi pi-arrow-right link-arrow" />
            </button>
            <span v-else class="cell-script-name">{{ scriptName(data.script_path) }}</span>
            <div class="script-meta-row">
              <span class="cell-script-dir">{{ scriptDir(data.script_path) }}</span>
              <button
                v-if="cronJobsFor(data.script_path).length"
                class="cron-badge"
                v-tooltip.top="`${cronJobsFor(data.script_path).length} cron job(s)`"
                @click.stop="router.push('/crontab')"
              >
                <i class="pi pi-clock" />
                {{ cronJobsFor(data.script_path).length }}
              </button>
            </div>
          </div>
        </template>
      </Column>

      <Column field="username" header="USER" sortable style="width: 120px">
        <template #body="{ data }">
          <Chip :label="data.username" class="cell-chip" />
        </template>
      </Column>

      <Column field="exit_code" header="STATUS" style="width: 100px">
        <template #body="{ data }">
          <span v-if="data.exit_code === null"   class="badge-blue">running</span>
          <span v-else-if="data.exit_code === 0" class="badge-green">success</span>
          <span v-else                           class="badge-red">exit {{ data.exit_code }}</span>
        </template>
      </Column>

      <Column field="started_at" header="STARTED" sortable style="width: 160px">
        <template #body="{ data }">
          <span class="cell-date">{{ formatDate(data.started_at) }}</span>
        </template>
      </Column>

      <Column field="duration_seconds" header="DURATION" sortable style="width: 110px">
        <template #body="{ data }">
          <span class="cell-duration">
            {{ data.duration_seconds != null ? `${data.duration_seconds.toFixed(1)}s` : '—' }}
          </span>
        </template>
      </Column>

      <Column field="output_summary" header="OUTPUT" style="min-width: 200px">
        <template #body="{ data }">
          <span v-if="data.output_summary" class="cell-output">{{ data.output_summary }}</span>
          <span v-else class="cell-output cell-output--empty">—</span>
        </template>
      </Column>

      <template #expansion="{ data }">
        <div class="log-expansion">
          <div class="log-expansion-header">
            <div class="log-expansion-title">
              <i class="pi pi-terminal" />
              <span class="log-expansion-name">{{ scriptName(data.script_path) }}</span>
              <span class="log-expansion-source">output</span>
            </div>
            <div class="log-expansion-meta">
              <span :class="data.exit_code === 0 ? 'badge-green' : data.exit_code == null ? 'badge-yellow' : 'badge-red'">
                {{ data.exit_code === 0 ? 'EXIT 0 ✓' : data.exit_code == null ? 'RUNNING' : `EXIT ${data.exit_code}` }}
              </span>
              <span class="log-expansion-time">{{ formatDate(data.started_at) }}</span>
              <button
                v-if="scriptsStore.isFavorite(data.script_path)"
                class="go-to-script-btn"
                @click="navigateToScript(data.script_path)"
              >
                <i class="pi pi-external-link" />
                Open in Scripts
              </button>
            </div>
          </div>
          <pre class="log-expansion-output">{{ data.output || data.output_summary || '(no output captured)' }}</pre>
        </div>
      </template>
    </DataTable>

    <Paginator
      v-if="totalLogs > pageSize"
      :rows="pageSize"
      :total-records="totalLogs"
      :first="pageOffset"
      class="logs-paginator"
      @page="onPageChange"
    />

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useScriptsStore } from '../stores/scripts.js'
import InputText from 'primevue/inputtext'
import DatePicker from 'primevue/datepicker'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Chip from 'primevue/chip'
import Paginator from 'primevue/paginator'
import { usePolling } from '../composables/usePolling.js'
import { useDebounce } from '../composables/useDebounce.js'
import api from '../api/client.js'

const router = useRouter()
const scriptsStore = useScriptsStore()
const cronEntries = ref([])
const expandedRows = ref({})
const expandedOrder = ref([])
const MAX_EXPANDED = 5

const logs = ref([])
const stats = ref({ total: 0, success: 0, failed: 0, last_24h: 0 })
const loading = ref(false)
const filterScript = ref('')
const filterStatus = ref('all')
const dateRange = ref(null)

const totalLogs = ref(0)
const pageSize = ref(50)
const pageOffset = ref(0)

const statusOptions = [
  { label: 'All',     value: 'all',     dot: false },
  { label: 'Success', value: 'success', dot: true  },
  { label: 'Failed',  value: 'failed',  dot: true  },
]

const hasActiveFilters = computed(() =>
  filterStatus.value !== 'all' || filterScript.value !== '' || dateRange.value != null
)

function setStatus(val) {
  filterStatus.value = val
  pageOffset.value = 0
  loadLogs()
}

function clearFilters() {
  filterScript.value = ''
  filterStatus.value = 'all'
  dateRange.value = null
  pageOffset.value = 0
  loadLogs()
}

async function loadLogs() {
  loading.value = true
  try {
    const params = {}
    if (filterScript.value) params.script = filterScript.value
    if (filterStatus.value === 'success') params.exit_code = 0
    if (filterStatus.value === 'failed') params.exit_code = 1
    if (dateRange.value?.[0]) params.from_date = dateRange.value[0].toISOString()
    if (dateRange.value?.[1]) params.to_date = dateRange.value[1].toISOString()
    params.limit = pageSize.value
    params.offset = pageOffset.value
    const { data, headers } = await api.get('/logs/executions', { params })
    logs.value = data
    totalLogs.value = parseInt(headers['x-total-count'] || '0', 10)
  } finally {
    loading.value = false
  }
}

function onPageChange(event) {
  pageOffset.value = event.first
  loadLogs()
}

const debouncedLoadLogs = useDebounce(loadLogs, 400)

async function loadStats() {
  try {
    const { data } = await api.get('/logs/executions/stats')
    stats.value = data
  } catch {
    // non-critical
  }
}

async function loadCronEntries() {
  try {
    const { data } = await api.get('/crontab/')
    cronEntries.value = data
  } catch {}
}

function cronJobsFor(path) {
  if (!path) return []
  return cronEntries.value.filter(e => e.command && e.command.includes(path))
}

function navigateToScript(path) {
  if (scriptsStore.isFavorite(path)) {
    router.push({ path: '/scripts', query: { select: path } })
  } else {
    const parts = path.split('/')
    parts.pop()
    router.push({ path: '/files', query: { dir: parts.join('/') || '/' } })
  }
}

function onRowExpand(event) {
  const id = event.data.id
  expandedOrder.value.push(id)
  if (expandedOrder.value.length > MAX_EXPANDED) {
    const evicted = expandedOrder.value.shift()
    delete expandedRows.value[evicted]
  }
}

function onRowCollapse(event) {
  const id = event.data.id
  expandedOrder.value = expandedOrder.value.filter(i => i !== id)
}

async function loadAll() {
  await Promise.all([loadLogs(), loadStats(), loadCronEntries(), scriptsStore.loadFavorites()])
}

const { start, stop } = usePolling(loadAll, 30000)
onMounted(start)
onUnmounted(stop)

function scriptName(path) {
  return path?.split('/').at(-1) || path
}
function scriptDir(path) {
  const parts = path?.split('/') || []
  return parts.slice(0, -1).join('/') || '/'
}
function formatDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped>
.logs-view {
  display: flex; flex-direction: column;
  height: calc(100vh - var(--header-height) - 48px);
  gap: 14px;
}

/* ── Stats row ─────────────────────────────── */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  flex-shrink: 0;
}
@media (max-width: 700px) { .stats-row { grid-template-columns: 1fr 1fr; } }

.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  background: var(--p-surface-card);
  border: 1px solid var(--p-surface-border);
  border-radius: 10px;
  border-left: 3px solid var(--p-surface-border);
}
.stat-card--success { border-left-color: var(--p-green-500); }
.stat-card--failed  { border-left-color: var(--p-red-500); }
.stat-card--24h     { border-left-color: var(--brand-orange); }

.stat-icon { font-size: var(--text-xl); opacity: 0.5; color: var(--p-text-muted-color); flex-shrink: 0; }
.stat-icon--success { color: var(--p-green-500); opacity: 1; }
.stat-icon--failed  { color: var(--p-red-500); opacity: 1; }
.stat-icon--24h     { color: var(--brand-orange); opacity: 1; }

.stat-body { display: flex; flex-direction: column; gap: 2px; }
.stat-label {
  font-family: var(--font-mono);
  font-size: var(--text-2xs); letter-spacing: 1.5px;
  color: var(--p-text-muted-color); text-transform: uppercase;
}
.stat-value {
  font-size: var(--text-2xl); font-weight: 700; font-family: var(--font-mono);
  color: var(--p-text-color); line-height: 1;
}
.stat-val-success { color: var(--p-green-500); }
.stat-val-failed  { color: var(--p-red-500); }
.stat-val-24h     { color: var(--brand-orange); }

/* ── Filters toolbar ─────────────────────────── */
.filters-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: var(--p-surface-900);
  border: 1px solid var(--p-surface-border);
  border-radius: var(--radius-base);
  flex-shrink: 0;
}
.filters-start { display: flex; align-items: center; gap: 8px; flex: 1; flex-wrap: wrap; }
.filters-end   { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }

/* Search field */
.search-field {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--p-surface-ground);
  border: 1px solid var(--p-surface-border);
  border-radius: var(--radius-md);
  padding: 0 10px;
  height: 32px;
}
.search-icon { font-size: 11px; color: var(--p-text-muted-color); flex-shrink: 0; }
.search-input {
  background: transparent;
  border: none;
  outline: none;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--p-text-color);
  width: 160px;
}
.search-input::placeholder { color: var(--p-text-muted-color); }

/* Refresh button */
.refresh-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px; height: 32px;
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--p-text-muted-color);
  cursor: pointer;
  font-size: var(--text-base);
  transition: var(--transition-fast);
}
.refresh-btn:hover { background: var(--p-surface-hover); color: var(--p-text-color); }
.refresh-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.status-pills { display: flex; gap: 4px; }
.status-pill {
  display: flex; align-items: center; gap: 5px;
  padding: 4px 10px;
  border-radius: 14px;
  border: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
  cursor: pointer;
  font-family: var(--font-mono); font-size: var(--text-xs);
  letter-spacing: 1.5px; text-transform: uppercase;
  color: var(--p-text-muted-color);
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}
.status-pill:hover { background: var(--p-surface-hover); color: var(--p-text-color); }
.status-pill.active { color: var(--p-text-color); }
.pill-success.active { border-color: var(--p-green-500); background: color-mix(in srgb, var(--p-green-500) 10%, transparent); }
.pill-failed.active  { border-color: var(--p-red-500);   background: color-mix(in srgb, var(--p-red-500) 10%, transparent); }
.pill-all.active     { border-color: var(--brand-orange); background: color-mix(in srgb, var(--brand-orange) 10%, transparent); }
.pill-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.dot-success { background: var(--p-green-500); }
.dot-failed  { background: var(--p-red-500); }

/* ── Table ────────────────────────────────────── */
.logs-table { flex: 1; min-height: 0; }
:deep(.logs-table .p-datatable-thead th) { background: transparent; }
:deep(.logs-table .p-datatable-column-header-content) {
  font-family: var(--font-mono); font-size: var(--text-2xs);
  letter-spacing: 1.5px; color: var(--p-text-muted-color);
  text-transform: uppercase; font-weight: 600;
}
:deep(.logs-table .p-datatable-tbody td) { padding: 5px 10px; }

/* ── Script cell ──────────────────────────────── */
.script-cell { display: flex; flex-direction: column; gap: 2px; }
.script-name-link {
  display: inline-flex; align-items: center; gap: 5px;
  background: none; border: none; cursor: pointer; padding: 0;
  text-align: left;
  transition: background 0.15s, color 0.15s;
}
.script-name-link:hover .cell-script-name--link { color: var(--brand-orange); }
.link-arrow {
  font-size: var(--text-xs); color: var(--brand-orange); opacity: 0;
  transition: opacity 0.15s;
}
.script-name-link:hover .link-arrow { opacity: 1; }
.cell-script-name {
  font-family: var(--font-mono); font-size: var(--text-sm);
  color: var(--p-text-color); transition: color 0.15s;
}
.cell-script-name--link { cursor: pointer; }
.script-meta-row { display: flex; align-items: center; gap: 6px; }
.cell-script-dir {
  font-family: var(--font-mono); font-size: var(--text-xs);
  color: var(--p-text-muted-color);
}
.cron-badge {
  display: inline-flex; align-items: center; gap: 3px;
  font-family: var(--font-mono); font-size: var(--text-2xs);
  color: var(--brand-orange);
  background: color-mix(in srgb, var(--brand-orange) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand-orange) 30%, transparent);
  border-radius: 10px; padding: 1px 6px;
  cursor: pointer; transition: background 0.15s;
}
.cron-badge:hover { background: color-mix(in srgb, var(--brand-orange) 22%, transparent); }
.cron-badge .pi { font-size: var(--text-xs); }

:deep(.cell-chip) { font-size: var(--text-xs) !important; }
.cell-date     { font-size: var(--text-sm); color: var(--p-text-muted-color); font-family: var(--font-mono); }
.cell-duration { font-family: var(--font-mono); font-size: var(--text-sm); color: var(--p-text-muted-color); }
.cell-output {
  font-family: var(--font-mono); font-size: var(--text-xs);
  color: var(--p-text-muted-color);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  display: block; max-width: 280px;
}
.cell-output--empty { opacity: 0.4; }

/* ── Row expansion ────────────────────────────── */
.log-expansion {
  background: var(--p-surface-900);
  border-top: 1px solid var(--p-surface-border);
}
.log-expansion-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 14px 6px;
  border-bottom: 1px solid color-mix(in srgb, var(--brand-orange) 25%, transparent);
}
.log-expansion-title {
  display: flex; align-items: center; gap: 8px;
  color: var(--brand-orange); font-size: var(--text-sm);
}
.log-expansion-name {
  font-family: var(--font-mono); font-size: var(--text-sm);
  font-weight: 600; color: var(--brand-orange);
}
.log-expansion-source {
  font-family: var(--font-mono); font-size: var(--text-2xs);
  letter-spacing: 1.5px; color: var(--p-text-muted-color); text-transform: uppercase;
}
.log-expansion-meta { display: flex; align-items: center; gap: 10px; }
.log-expansion-time {
  font-family: var(--font-mono); font-size: var(--text-xs);
  color: var(--p-text-muted-color);
}
.go-to-script-btn {
  display: inline-flex; align-items: center; gap: 5px;
  font-family: var(--font-mono); font-size: var(--text-xs);
  color: var(--brand-orange);
  background: color-mix(in srgb, var(--brand-orange) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand-orange) 30%, transparent);
  border-radius: 4px; padding: 3px 8px; cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.go-to-script-btn:hover { background: color-mix(in srgb, var(--brand-orange) 20%, transparent); }
.go-to-script-btn .pi { font-size: var(--text-2xs); }
.log-expansion-output {
  font-family: var(--font-mono); font-size: var(--text-xs); line-height: 1.7;
  color: var(--p-text-muted-color);
  padding: 10px 16px; white-space: pre-wrap; word-break: break-all;
  background: var(--p-surface-900); margin: 0;
  max-height: 280px; overflow-y: auto;
}

/* ── Empty state ──────────────────────────────── */
.empty-state {
  display: flex; flex-direction: column; align-items: center;
  gap: 10px; padding: 32px 16px;
  color: var(--p-text-muted-color);
}
.empty-icon { font-size: 28px; opacity: 0.4; color: var(--p-text-muted-color); }
.empty-text { font-family: var(--font-mono); font-size: var(--text-sm); color: var(--p-text-muted-color); }

.logs-paginator {
  flex-shrink: 0;
  border-top: 1px solid var(--p-surface-border);
}
</style>
