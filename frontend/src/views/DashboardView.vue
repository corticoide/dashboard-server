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
          <div class="info-item">
            <span class="info-key">TIMEZONE</span>
            <span class="info-val">{{ metrics.utc_label || metrics.timezone_name || '—' }}</span>
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

    <!-- Live ECG chart card -->
    <Card class="dash-card">
      <template #content>
        <div class="card-section-header">
          <i class="pi pi-wave-pulse section-icon" />
          <span class="section-title">LIVE METRICS</span>
          <span class="live-dot-wrapper"><span class="live-dot" />LIVE</span>
          <div class="chart-controls">
            <Select v-model="windowSize" :options="windowOptions" option-label="label" option-value="value"
              class="window-select" size="small" />
          </div>
        </div>
        <Divider class="section-divider" />
        <div class="chart-container" :style="containerStyle">
          <Chart type="line" :data="chartData" :options="chartOptions" :plugins="ecgPlugins" class="ecg-chart" />
        </div>
        <div class="ecg-legend">
          <span class="ecg-legend-item" :class="{ 'legend-hidden': hiddenSeries.has('CPU %') }" style="--c:#f97316" @click="toggleSeries('CPU %', 0)">CPU</span>
          <span class="ecg-legend-item" :class="{ 'legend-hidden': hiddenSeries.has('RAM %') }" style="--c:#3b82f6" @click="toggleSeries('RAM %', 1)">RAM</span>
          <span class="ecg-legend-item" :class="{ 'legend-hidden': hiddenSeries.has('Disk %') }" style="--c:#10b981" @click="toggleSeries('Disk %', 2)">Disk</span>
        </div>
      </template>
    </Card>

    <!-- History CTA -->
    <RouterLink to="/history" class="history-cta">
      <i class="pi pi-chart-bar history-cta-icon" />
      <span class="history-cta-text">View Resource &amp; Bandwidth History</span>
      <i class="pi pi-arrow-right history-cta-arrow" />
    </RouterLink>

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
import Select from 'primevue/select'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Chart from 'primevue/chart'
import MetricCard from '../components/dashboard/MetricCard.vue'
import { usePolling } from '../composables/usePolling.js'
import { useChartTheme } from '../composables/useChartTheme.js'
import api from '../api/client.js'

const { chartBg, containerStyle, buildScales, buildTooltip } = useChartTheme()

// ── ECG live chart ─────────────────────────────────────────────────────────
const LIVE_BUFFER = 120

const windowSize = ref(60)
const windowOptions = [
  { label: '30s', value: 30 },
  { label: '1m',  value: 60 },
  { label: '2m',  value: 90 },
  { label: 'MAX', value: 120 },
]

const hiddenSeries = ref(new Set())
const live = { labels: [], cpu: [], ram: [], disk: [] }

// Reactive chart data — PrimeVue Chart watches this ref
const chartData = ref({
  labels: [],
  datasets: [
    { label: 'CPU %',  data: [], borderColor: '#f97316', borderWidth: 2, tension: 0.3, pointRadius: 0, fill: false },
    { label: 'RAM %',  data: [], borderColor: '#3b82f6', borderWidth: 2, tension: 0.3, pointRadius: 0, fill: false },
    { label: 'Disk %', data: [], borderColor: '#10b981', borderWidth: 2, tension: 0.3, pointRadius: 0, fill: false },
  ],
})

// Reactive options — PrimeVue Chart re-renders when this changes
const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  plugins: {
    legend: { display: false },
    tooltip: buildTooltip((ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)}%`),
  },
  scales: buildScales({ yMin: 0, yMax: 100, yCallback: (v) => `${v}%` }),
}))

// ECG glow plugin — background uses reactive chartBg
const ecgPlugins = [
  {
    id: 'ecgBg',
    beforeDraw(chart) {
      const ctx = chart.ctx
      ctx.save()
      ctx.fillStyle = chartBg.value
      const { left, top, right, bottom } = chart.chartArea || {}
      if (left != null) ctx.fillRect(left, top, right - left, bottom - top)
      ctx.restore()
    },
  },
  {
    id: 'ecgGlow',
    beforeDatasetsDraw(chart) { chart.ctx.save() },
    beforeDatasetDraw(chart, { index }) {
      const color = chart.data.datasets[index].borderColor
      chart.ctx.shadowColor = color
      chart.ctx.shadowBlur = 10
    },
    afterDatasetsDraw(chart) { chart.ctx.restore() },
  },
]

function toggleSeries(label, idx) {
  if (hiddenSeries.value.has(label)) {
    hiddenSeries.value.delete(label)
  } else {
    hiddenSeries.value.add(label)
  }
  // Rebuild chart data with hidden series having empty data
  updateChartData()
}

function updateChartData() {
  const w = windowSize.value
  const labels = live.labels.slice(-w)
  const sources = [
    { label: 'CPU %',  arr: live.cpu,  color: '#f97316' },
    { label: 'RAM %',  arr: live.ram,  color: '#3b82f6' },
    { label: 'Disk %', arr: live.disk, color: '#10b981' },
  ]
  chartData.value = {
    labels,
    datasets: sources.map(s => ({
      label: s.label,
      data: hiddenSeries.value.has(s.label) ? [] : s.arr.slice(-w),
      borderColor: s.color,
      borderWidth: 2,
      tension: 0.3,
      pointRadius: 0,
      fill: false,
      hidden: hiddenSeries.value.has(s.label),
    })),
  }
}

function pushLivePoint(d) {
  const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  live.labels.push(now)
  live.cpu.push(+(d.cpu_percent ?? 0).toFixed(1))
  live.ram.push(+(d.ram_percent ?? 0).toFixed(1))
  live.disk.push(+(d.disk_percent ?? 0).toFixed(1))
  if (live.labels.length > LIVE_BUFFER) {
    live.labels.shift(); live.cpu.shift(); live.ram.shift(); live.disk.shift()
  }
  updateChartData()
}

const recentLogs = ref([])

async function fetchRecentLogs() {
  try {
    const { data } = await api.get('/logs/executions', { params: {} })
    recentLogs.value = data.slice(0, 5)
  } catch { /* non-critical */ }
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
  utc_offset_seconds: 0, utc_label: '', timezone_name: '',
})
const error = ref('')

// ── WebSocket for real-time metrics ──
let metricsWs = null

function connectMetricsWs() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const token = localStorage.getItem('access_token') || ''
  metricsWs = new WebSocket(`${proto}://${location.host}/api/ws/metrics?token=${token}`)

  metricsWs.onmessage = (evt) => {
    try {
      const d = JSON.parse(evt.data)
      metrics.value = d
      error.value = ''
      pushLivePoint(d)
    } catch { /* ignore */ }
  }
  metricsWs.onerror = () => { error.value = 'Live metrics connection error — retrying...' }
  metricsWs.onclose = () => {
    if (metricsWs) setTimeout(connectMetricsWs, 3000)
  }
}

function disconnectMetricsWs() {
  if (metricsWs) {
    const old = metricsWs
    metricsWs = null
    old.close()
  }
}

const { start: startLogs, stop: stopLogs } = usePolling(fetchRecentLogs, 30000)

onMounted(() => {
  connectMetricsWs()
  startLogs()
  fetchRecentLogs()
})
onUnmounted(() => {
  disconnectMetricsWs()
  stopLogs()
})

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
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
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

/* ── Live ECG chart ───────────────────────────── */
.chart-container {
  height: 300px;
  position: relative;
}
.ecg-chart {
  height: 100%;
  width: 100%;
}
.live-dot-wrapper {
  display: flex;
  align-items: center;
  gap: 5px;
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 1.5px;
  color: #22c55e;
}
.live-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 6px #22c55e;
  animation: pulse-dot 1.4s ease-in-out infinite;
}
@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.8); }
}
.ecg-legend {
  display: flex;
  gap: 16px;
  margin-top: 8px;
  padding-left: 2px;
}
.ecg-legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  color: var(--p-text-muted-color);
  letter-spacing: 1px;
  cursor: pointer;
  user-select: none;
  transition: opacity 0.2s;
}
.ecg-legend-item:hover { opacity: 0.7; }
.ecg-legend-item::before {
  content: '';
  display: inline-block;
  width: 16px;
  height: 2px;
  background: var(--c);
  box-shadow: 0 0 5px var(--c);
  border-radius: 1px;
}
.legend-hidden { opacity: 0.25; }

/* ── History CTA ──────────────────────────────── */
.history-cta {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-radius: 8px;
  border: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
  text-decoration: none;
  color: var(--p-text-muted-color);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  letter-spacing: 0.5px;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
  cursor: pointer;
}
.history-cta:hover {
  border-color: color-mix(in srgb, var(--brand-orange) 40%, transparent);
  color: var(--brand-orange);
  background: color-mix(in srgb, var(--brand-orange) 5%, transparent);
}
.history-cta-icon { font-size: 13px; flex-shrink: 0; }
.history-cta-text { flex: 1; }
.history-cta-arrow { font-size: 11px; flex-shrink: 0; transition: transform 0.15s; }
.history-cta:hover .history-cta-arrow { transform: translateX(3px); }

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

/* Window selector */
.chart-controls { display: flex; align-items: center; gap: 8px; margin-left: auto; }
:deep(.window-select) { font-family: var(--font-mono); font-size: var(--text-xs); }
:deep(.window-select .p-select-label) { padding: 4px 8px; font-size: var(--text-xs); }
</style>
