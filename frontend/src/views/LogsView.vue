<template>
  <div class="logs-view">

    <!-- Stats row -->
    <div class="stats-row">
      <Card class="stat-card">
        <template #content>
          <div class="stat-item">
            <span class="stat-label">TOTAL RUNS</span>
            <span class="stat-value">{{ stats.total }}</span>
          </div>
        </template>
      </Card>
      <Card class="stat-card stat-success">
        <template #content>
          <div class="stat-item">
            <span class="stat-label">SUCCESS</span>
            <span class="stat-value stat-value--success">{{ stats.success }}</span>
          </div>
        </template>
      </Card>
      <Card class="stat-card stat-failed">
        <template #content>
          <div class="stat-item">
            <span class="stat-label">FAILED</span>
            <span class="stat-value stat-value--failed">{{ stats.failed }}</span>
          </div>
        </template>
      </Card>
      <Card class="stat-card">
        <template #content>
          <div class="stat-item">
            <span class="stat-label">LAST 24H</span>
            <span class="stat-value stat-value--24h">{{ stats.last_24h }}</span>
          </div>
        </template>
      </Card>
    </div>

    <!-- Filters toolbar -->
    <Toolbar class="filters-toolbar">
      <template #start>
        <div class="filters-start">
          <IconField>
            <InputIcon class="pi pi-search" />
            <InputText v-model="filterScript" placeholder="Filter by script…" size="small" @input="loadLogs" />
          </IconField>
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
      </template>
      <template #end>
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
          <Button
            icon="pi pi-refresh"
            text rounded size="small"
            :loading="loading"
            v-tooltip.bottom="'Refresh'"
            @click="loadLogs"
          />
        </div>
      </template>
    </Toolbar>

    <!-- Table -->
    <DataTable
      :value="logs"
      :loading="loading"
      striped-rows
      size="small"
      data-key="id"
      scrollable
      scroll-height="flex"
      removableSort
      class="logs-table"
    >
      <template #empty>
        <div class="empty-state">
          <i class="pi pi-list empty-icon" />
          <span class="empty-text">No execution logs found</span>
        </div>
      </template>

      <Column field="script_path" header="SCRIPT" sortable style="min-width: 200px">
        <template #body="{ data }">
          <span class="cell-script-name">{{ scriptName(data.script_path) }}</span>
          <div class="cell-script-dir">{{ scriptDir(data.script_path) }}</div>
        </template>
      </Column>

      <Column field="username" header="USER" sortable style="width: 120px">
        <template #body="{ data }">
          <Chip :label="data.username" class="cell-chip" />
        </template>
      </Column>

      <Column field="exit_code" header="STATUS" style="width: 100px">
        <template #body="{ data }">
          <Tag v-if="data.exit_code === null"   value="running"                severity="info"    />
          <Tag v-else-if="data.exit_code === 0" value="success"                severity="success" />
          <Tag v-else                           :value="`exit ${data.exit_code}`" severity="danger"  />
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
    </DataTable>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import Card from 'primevue/card'
import Toolbar from 'primevue/toolbar'
import IconField from 'primevue/iconfield'
import InputIcon from 'primevue/inputicon'
import InputText from 'primevue/inputtext'
import DatePicker from 'primevue/datepicker'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import Chip from 'primevue/chip'
import { usePolling } from '../composables/usePolling.js'
import api from '../api/client.js'

const logs = ref([])
const stats = ref({ total: 0, success: 0, failed: 0, last_24h: 0 })
const loading = ref(false)
const filterScript = ref('')
const filterStatus = ref('all')
const dateRange = ref(null)

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
  loadLogs()
}

function clearFilters() {
  filterScript.value = ''
  filterStatus.value = 'all'
  dateRange.value = null
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
    const { data } = await api.get('/logs/executions', { params })
    logs.value = data
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    const { data } = await api.get('/logs/executions/stats')
    stats.value = data
  } catch {
    // non-critical
  }
}

async function loadAll() {
  await Promise.all([loadLogs(), loadStats()])
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

/* ── Stats row ────────────────────────────────────────── */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  flex-shrink: 0;
}
@media (max-width: 700px) {
  .stats-row { grid-template-columns: 1fr 1fr; }
}

.stat-item { display: flex; flex-direction: column; gap: 4px; }
.stat-label {
  font-family: var(--font-mono);
  font-size: var(--text-2xs); letter-spacing: 1.5px;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
}
.stat-value {
  font-size: 28px; font-weight: 700; font-family: var(--font-mono);
  color: var(--p-text-color);
}
.stat-value--success { color: var(--p-green-500); }
.stat-value--failed  { color: var(--p-red-500); }
.stat-value--24h     { color: var(--brand-blue); }

/* ── Filters toolbar ─────────────────────────────────── */
.filters-toolbar { flex-shrink: 0; }
.filters-start { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.filters-end   { display: flex; align-items: center; gap: 8px; }

/* Status pills */
.status-pills { display: flex; gap: 4px; }
.status-pill {
  display: flex; align-items: center; gap: 5px;
  padding: 4px 10px;
  border-radius: 14px;
  border: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
  cursor: pointer;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--p-text-muted-color);
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}
.status-pill:hover { background: var(--p-surface-hover); color: var(--p-text-color); }
.status-pill.active { color: var(--p-text-color); }
.pill-success.active { border-color: var(--p-green-500); background: color-mix(in srgb, var(--p-green-500) 10%, transparent); }
.pill-failed.active  { border-color: var(--p-red-500);   background: color-mix(in srgb, var(--p-red-500)   10%, transparent); }
.pill-all.active     { border-color: var(--p-primary-color); background: color-mix(in srgb, var(--p-primary-color) 10%, transparent); }

.pill-dot {
  width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0;
}
.dot-success { background: var(--p-green-500); }
.dot-failed  { background: var(--p-red-500); }

/* ── Table ────────────────────────────────────────────── */
.logs-table { flex: 1; min-height: 0; }

/* DataTable header normalization */
:deep(.logs-table .p-datatable-thead th) { background: transparent; }
:deep(.logs-table .p-datatable-column-header-content) {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 1.5px;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
  font-weight: 600;
}
:deep(.logs-table .p-datatable-tbody td) { padding: 5px 10px; }

/* Table cells */
.cell-script-name {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--p-text-color);
  display: block;
}
.cell-script-dir {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--p-text-muted-color);
}
:deep(.cell-chip) { font-size: var(--text-xs) !important; }
.cell-date     { font-size: var(--text-sm); color: var(--p-text-muted-color); }
.cell-duration { font-family: var(--font-mono); font-size: var(--text-sm); color: var(--p-text-muted-color); }
.cell-output {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--p-text-muted-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
  max-width: 300px;
}
.cell-output--empty { opacity: 0.5; }

/* ── Empty state ─────────────────────────────────────── */
.empty-state {
  display: flex; flex-direction: column; align-items: center;
  gap: 8px; padding: 40px;
}
.empty-icon { font-size: 2rem; color: var(--p-text-muted-color); opacity: 0.4; }
.empty-text { font-family: var(--font-mono); font-size: var(--text-sm); color: var(--p-text-muted-color); }
</style>
