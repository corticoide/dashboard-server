<template>
  <div class="dashboard">

    <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>

    <!-- Gauge row -->
    <div class="gauge-row">
      <MetricCard
        label="CPU"
        :value="metrics.cpu_percent"
        unit="%"
        color="auto"
        :subtitle="metrics.cpu_count ? `${metrics.cpu_count} cores · ${metrics.cpu_arch}` : ''"
      />
      <MetricCard
        label="MEMORY"
        :value="metrics.ram_percent"
        unit="%"
        color="auto"
        :subtitle="`${metrics.ram_used_gb} / ${metrics.ram_total_gb} GB`"
      />
      <MetricCard
        label="DISK"
        :value="metrics.disk_percent"
        unit="%"
        color="auto"
        :subtitle="`${metrics.disk_used_gb} / ${metrics.disk_total_gb} GB`"
      />
    </div>

    <!-- System info card -->
    <Card class="dash-card">
      <template #content>
        <div class="card-section-header">
          <i class="pi pi-desktop section-icon" />
          <span class="section-title">SYSTEM</span>
          <span class="section-extra">{{ metrics.os_name }}</span>
        </div>
        <Divider class="section-divider" />
        <div class="info-grid">
          <div class="info-item">
            <span class="info-key">HOSTNAME</span>
            <span class="info-val">{{ metrics.hostname || '—' }}</span>
          </div>
          <div class="info-item">
            <span class="info-key">UPTIME</span>
            <Tag :value="uptimeFormatted" severity="success" icon="pi pi-clock" class="uptime-tag" />
          </div>
          <div class="info-item">
            <span class="info-key">ARCH</span>
            <span class="info-val">{{ metrics.cpu_arch || '—' }}</span>
          </div>
          <div class="info-item">
            <span class="info-key">CPU CORES</span>
            <span class="info-val">{{ metrics.cpu_count ?? '—' }}</span>
          </div>
        </div>
        <Divider class="section-divider" />
        <div class="load-row">
          <span class="info-key">LOAD AVG</span>
          <div class="load-values">
            <div class="load-item">
              <Badge
                :value="String(metrics.load_average?.[0] ?? '—')"
                :class="loadBadgeClass(metrics.load_average?.[0])"
              />
              <span class="load-period">1m</span>
            </div>
            <span class="load-sep">·</span>
            <div class="load-item">
              <Badge
                :value="String(metrics.load_average?.[1] ?? '—')"
                :class="loadBadgeClass(metrics.load_average?.[1])"
              />
              <span class="load-period">5m</span>
            </div>
            <span class="load-sep">·</span>
            <div class="load-item">
              <Badge
                :value="String(metrics.load_average?.[2] ?? '—')"
                :class="loadBadgeClass(metrics.load_average?.[2])"
              />
              <span class="load-period">15m</span>
            </div>
          </div>
        </div>
      </template>
    </Card>

    <!-- Recent executions card -->
    <Card class="dash-card">
      <template #content>
        <div class="card-section-header">
          <i class="pi pi-list section-icon" />
          <span class="section-title">RECENT EXECUTIONS</span>
          <RouterLink to="/logs" class="view-all-link">View all →</RouterLink>
        </div>
        <Divider class="section-divider" />
        <DataTable :value="recentLogs" size="small" :show-gridlines="false" class="recent-table">
          <template #empty>
            <span class="cell-empty">No executions yet</span>
          </template>
          <Column field="script_path" header="Script">
            <template #body="{ data }">
              <span class="cell-name">{{ data.script_path?.split('/').at(-1) }}</span>
            </template>
          </Column>
          <Column field="username" header="User" style="width: 110px">
            <template #body="{ data }">
              <Chip :label="data.username" class="cell-chip" />
            </template>
          </Column>
          <Column field="exit_code" header="Status" style="width: 90px">
            <template #body="{ data }">
              <Tag v-if="data.exit_code === null"   value="running"              severity="info"    />
              <Tag v-else-if="data.exit_code === 0" value="ok"                   severity="success" />
              <Tag v-else                            :value="`exit ${data.exit_code}`" severity="danger"  />
            </template>
          </Column>
          <Column field="started_at" header="When" style="width: 140px">
            <template #body="{ data }">
              <span class="cell-meta">{{ formatLogDate(data.started_at) }}</span>
            </template>
          </Column>
          <Column field="duration_seconds" header="Duration" style="width: 90px">
            <template #body="{ data }">
              <span class="cell-meta cell-mono">{{ data.duration_seconds != null ? `${data.duration_seconds.toFixed(1)}s` : '—' }}</span>
            </template>
          </Column>
        </DataTable>
      </template>
    </Card>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { RouterLink } from 'vue-router'
import Message from 'primevue/message'
import Card from 'primevue/card'
import Divider from 'primevue/divider'
import Tag from 'primevue/tag'
import Badge from 'primevue/badge'
import Chip from 'primevue/chip'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import MetricCard from '../components/dashboard/MetricCard.vue'
import { usePolling } from '../composables/usePolling.js'
import api from '../api/client.js'

const recentLogs = ref([])

async function fetchRecentLogs() {
  try {
    const { data } = await api.get('/logs/executions', { params: { } })
    recentLogs.value = data.slice(0, 5)
  } catch {
    // non-critical
  }
}

function formatLogDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

const metrics = ref({
  cpu_percent: 0, ram_percent: 0, ram_used_gb: 0, ram_total_gb: 0,
  disk_percent: 0, disk_used_gb: 0, disk_total_gb: 0, uptime_seconds: 0,
  load_average: [0, 0, 0], os_name: '', hostname: '', cpu_count: 0, cpu_arch: '',
})
const error = ref('')

async function fetchMetrics() {
  try {
    const { data } = await api.get('/system/metrics')
    metrics.value = data
    error.value = ''
  } catch {
    error.value = 'Failed to fetch metrics'
  }
}

const { start, stop } = usePolling(fetchMetrics, 5000)
const { start: startLogs, stop: stopLogs } = usePolling(fetchRecentLogs, 30000)
onMounted(() => { start(); startLogs() })
onUnmounted(() => { stop(); stopLogs() })

const uptimeFormatted = computed(() => {
  const s = metrics.value.uptime_seconds
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (d > 0) return `${d}d ${h}h ${m}m`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
})

function loadBadgeClass(val) {
  if (val == null) return ''
  const ratio = val / (metrics.value.cpu_count || 1)
  if (ratio >= 0.85) return 'load-high'
  if (ratio >= 0.6)  return 'load-mid'
  return 'load-ok'
}
</script>

<style scoped>
.dashboard { display: flex; flex-direction: column; gap: 16px; }

/* ── Gauge row ────────────────────────────────── */
.gauge-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}
@media (max-width: 600px) {
  .gauge-row { grid-template-columns: 1fr; }
}

/* ── Card inner layout ────────────────────────── */
:deep(.dash-card .p-card-body) { padding: 0; }
:deep(.dash-card .p-card-content) { padding: 14px 16px; }

.card-section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-bottom: 2px;
}
.section-icon {
  font-size: 12px;
  color: var(--brand-orange);
  flex-shrink: 0;
}
.section-title {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--p-text-muted-color);
  flex: 1;
}
.section-extra {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--p-text-muted-color);
}

.section-divider { margin: 10px 0 !important; }

/* ── Info grid ────────────────────────────────── */
.info-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
@media (max-width: 700px) {
  .info-grid { grid-template-columns: 1fr 1fr; }
}
.info-item { display: flex; flex-direction: column; gap: 5px; }
.info-key {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 1.5px;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
}
.info-val {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--p-text-color);
}
:deep(.uptime-tag) { font-family: var(--font-mono); font-size: var(--text-xs); }

/* ── Load average ─────────────────────────────── */
.load-row { display: flex; align-items: center; gap: 14px; }
.load-values { display: flex; align-items: center; gap: 8px; }
.load-sep { color: var(--p-text-muted-color); }
.load-item { display: flex; align-items: baseline; gap: 4px; }
.load-period {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  color: var(--p-text-muted-color);
}
:deep(.load-ok .p-badge)   { background: var(--p-green-500) !important; color: #fff !important; font-family: var(--font-mono); font-size: var(--text-xs) !important; font-weight: 600; }
:deep(.load-mid .p-badge)  { background: var(--p-yellow-500) !important; color: #000 !important; font-family: var(--font-mono); font-size: var(--text-xs) !important; font-weight: 600; }
:deep(.load-high .p-badge) { background: var(--p-red-500) !important; color: #fff !important; font-family: var(--font-mono); font-size: var(--text-xs) !important; font-weight: 600; }

/* ── Recent executions table ──────────────────── */
.view-all-link {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  color: var(--p-primary-color);
  text-decoration: none;
}
.view-all-link:hover { text-decoration: underline; }

:deep(.recent-table .p-datatable-thead th) {
  padding: 6px 10px;
  background: transparent;
}
:deep(.recent-table .p-datatable-column-header-content) {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 1.5px;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
  font-weight: 600;
}
:deep(.recent-table .p-datatable-tbody td) { padding: 5px 10px; }

.cell-name  { font-family: var(--font-mono); font-size: var(--text-sm); }
.cell-meta  { font-size: var(--text-xs); color: var(--p-text-muted-color); }
.cell-mono  { font-family: var(--font-mono); }
.cell-empty { font-size: var(--text-sm); color: var(--p-text-muted-color); }
:deep(.cell-chip) { font-size: var(--text-xs) !important; }
</style>
