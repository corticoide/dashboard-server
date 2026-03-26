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
            <span class="stat-value">{{ stats.success }}</span>
          </div>
        </template>
      </Card>
      <Card class="stat-card stat-failed">
        <template #content>
          <div class="stat-item">
            <span class="stat-label">FAILED</span>
            <span class="stat-value">{{ stats.failed }}</span>
          </div>
        </template>
      </Card>
      <Card class="stat-card stat-24h">
        <template #content>
          <div class="stat-item">
            <span class="stat-label">LAST 24H</span>
            <span class="stat-value">{{ stats.last_24h }}</span>
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
          <SelectButton
            v-model="filterStatus"
            :options="statusOptions"
            option-label="label"
            option-value="value"
            size="small"
            @change="loadLogs"
          />
        </div>
      </template>
      <template #end>
        <div class="filters-end">
          <DatePicker
            v-model="dateRange"
            selectionMode="range"
            :manualInput="false"
            placeholder="Date range"
            size="small"
            show-icon
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
      class="logs-table"
    >
      <template #empty>
        <div class="empty-state">
          <i class="pi pi-list" style="font-size: 2rem; color: var(--p-text-muted-color);" />
          <span style="color: var(--p-text-muted-color);">No execution logs found</span>
        </div>
      </template>

      <Column field="script_path" header="SCRIPT" sortable style="min-width: 200px">
        <template #body="{ data }">
          <span class="font-mono" style="font-size: 12px;">{{ scriptName(data.script_path) }}</span>
          <div style="font-size: 10px; color: var(--p-text-muted-color); font-family: var(--font-mono);">
            {{ scriptDir(data.script_path) }}
          </div>
        </template>
      </Column>

      <Column field="username" header="USER" sortable style="width: 120px">
        <template #body="{ data }">
          <Chip :label="data.username" style="font-size: 11px;" />
        </template>
      </Column>

      <Column field="exit_code" header="STATUS" style="width: 100px">
        <template #body="{ data }">
          <Tag
            v-if="data.exit_code === null"
            value="running"
            severity="info"
          />
          <Tag
            v-else-if="data.exit_code === 0"
            value="success"
            severity="success"
          />
          <Tag
            v-else
            :value="`exit ${data.exit_code}`"
            severity="danger"
          />
        </template>
      </Column>

      <Column field="started_at" header="STARTED" sortable style="width: 160px">
        <template #body="{ data }">
          <span style="font-size: 12px; color: var(--p-text-muted-color);">{{ formatDate(data.started_at) }}</span>
        </template>
      </Column>

      <Column field="duration_seconds" header="DURATION" sortable style="width: 110px">
        <template #body="{ data }">
          <span class="font-mono" style="font-size: 12px; color: var(--p-text-muted-color);">
            {{ data.duration_seconds != null ? `${data.duration_seconds.toFixed(1)}s` : '—' }}
          </span>
        </template>
      </Column>

      <Column field="output_summary" header="OUTPUT" style="min-width: 200px">
        <template #body="{ data }">
          <span
            v-if="data.output_summary"
            style="font-size: 11px; font-family: var(--font-mono); color: var(--p-text-muted-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block; max-width: 300px;"
          >{{ data.output_summary }}</span>
          <span v-else style="color: var(--p-text-muted-color); font-size: 11px;">—</span>
        </template>
      </Column>
    </DataTable>

  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import Card from 'primevue/card'
import Toolbar from 'primevue/toolbar'
import IconField from 'primevue/iconfield'
import InputIcon from 'primevue/inputicon'
import InputText from 'primevue/inputtext'
import SelectButton from 'primevue/selectbutton'
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
  { label: 'All', value: 'all' },
  { label: 'Success', value: 'success' },
  { label: 'Failed', value: 'failed' },
]

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
  font-size: 9px; letter-spacing: 1.5px;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
}
.stat-value {
  font-size: 28px; font-weight: 700; font-family: var(--font-mono);
  color: var(--p-text-color);
}
.stat-success .stat-value { color: var(--p-green-500); }
.stat-failed  .stat-value { color: var(--p-red-500); }
.stat-24h     .stat-value { color: var(--p-blue-500); }

.filters-toolbar { flex-shrink: 0; }
.filters-start { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.filters-end   { display: flex; align-items: center; gap: 8px; }

.logs-table { flex: 1; min-height: 0; }

.empty-state {
  display: flex; flex-direction: column; align-items: center;
  gap: 8px; padding: 40px;
}
</style>
