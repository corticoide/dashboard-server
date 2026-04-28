<template>
  <div class="dashboard">

    <!-- Error banner -->
    <div v-if="error" class="banner banner-error">
      <i class="pi pi-exclamation-circle" />
      <span>{{ error }}</span>
    </div>

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

    <!-- System info row — two terminal blocks -->
    <div class="info-grid">

      <!-- uname -a / uptime -->
      <div class="tblock">
        <div class="tblock-header">
          <i class="pi pi-desktop" />
          <span class="tblock-title">uname -a / uptime</span>
        </div>
        <div class="tblock-body">
          <div class="uname-line">Linux {{ metrics.hostname || '...' }} {{ metrics.cpu_arch || '' }}</div>
          <div class="kv-row">
            <span class="kv-key">hostname</span>
            <span class="kv-val kv-orange">{{ metrics.hostname || '—' }}</span>
          </div>
          <div class="kv-row">
            <span class="kv-key">os</span>
            <span class="kv-val">{{ metrics.os_name || '—' }}</span>
          </div>
          <div class="kv-row">
            <span class="kv-key">arch</span>
            <span class="kv-val">{{ metrics.cpu_arch || '—' }}</span>
          </div>
          <div class="kv-row">
            <span class="kv-key">uptime</span>
            <span class="kv-val kv-green">{{ uptimeFormatted }}</span>
          </div>
          <div class="kv-row">
            <span class="kv-key">timezone</span>
            <span class="kv-val">{{ metrics.utc_label || metrics.timezone_name || '—' }}</span>
          </div>
          <div class="tblock-divider" />
          <div class="load-row-inline">
            <span class="kv-key">load average:</span>
            <span v-for="(v, i) in (metrics.load_average || [])" :key="i" class="load-pair">
              <span :class="loadColor(v, i)">{{ v }}</span>
              <span class="load-period">{{ ['1m','5m','15m'][i] }}</span>
            </span>
          </div>
        </div>
      </div>

      <!-- df -h / free -h -->
      <div class="tblock">
        <div class="tblock-header">
          <i class="pi pi-server" />
          <span class="tblock-title">df -h / free -h</span>
        </div>
        <div class="tblock-body">
          <div class="df-header">Filesystem      Size  Used Avail Use%</div>
          <div class="df-row">
            <span class="df-fs">/dev/sda1</span>
            <span class="df-size">{{ metrics.disk_total_gb }}G</span>
            <span class="df-used">{{ metrics.disk_used_gb }}G</span>
            <span class="df-avail">{{ diskAvailGb }}G</span>
            <span :class="['df-pct', diskPctColor]">{{ metrics.disk_percent }}%</span>
          </div>
          <div class="tblock-divider" />
          <div class="kv-row">
            <span class="kv-key">RAM total</span>
            <span class="kv-val">{{ metrics.ram_total_gb }} GB</span>
          </div>
          <div class="kv-row">
            <span class="kv-key">RAM used</span>
            <span :class="['kv-val', ramPctColor]">{{ metrics.ram_used_gb }} GB ({{ metrics.ram_percent }}%)</span>
          </div>
          <div class="kv-row">
            <span class="kv-key">CPU cores</span>
            <span class="kv-val">{{ metrics.cpu_count ?? '—' }}</span>
          </div>
        </div>
      </div>

    </div>

    <!-- Live metrics chart -->
    <div class="tblock">
      <div class="tblock-header">
        <i class="pi pi-wave-pulse" />
        <span class="tblock-title">live metrics</span>
        <span class="live-badge">
          <span class="live-dot" />
          LIVE
        </span>
        <Select v-model="windowSize" :options="windowOptions" option-label="label" option-value="value"
          class="window-select" size="small" />
      </div>
      <div class="chart-area" :style="containerStyle">
        <Chart type="line" :data="chartData" :options="chartOptions" :plugins="ecgPlugins" class="ecg-chart" />
      </div>
      <div class="ecg-legend">
        <span class="ecg-legend-item" :class="{ 'legend-hidden': hiddenSeries.has('CPU %') }" style="--c:#f97316" @click="toggleSeries('CPU %')">CPU</span>
        <span class="ecg-legend-item" :class="{ 'legend-hidden': hiddenSeries.has('RAM %') }" style="--c:#3b82f6" @click="toggleSeries('RAM %')">RAM</span>
        <span class="ecg-legend-item" :class="{ 'legend-hidden': hiddenSeries.has('Disk %') }" style="--c:#10b981" @click="toggleSeries('Disk %')">Disk</span>
      </div>
    </div>

    <!-- History CTA -->
    <RouterLink to="/history" class="history-cta">
      <i class="pi pi-chart-bar" />
      <span class="history-cta-text">View Resource &amp; Bandwidth History</span>
      <i class="pi pi-arrow-right history-cta-arrow" />
    </RouterLink>

    <!-- Recent executions — journalctl style -->
    <div class="tblock">
      <div class="tblock-header">
        <i class="pi pi-list" />
        <span class="tblock-title">recent executions — journalctl</span>
        <RouterLink to="/execution-logs" class="view-all-link">view all →</RouterLink>
      </div>
      <div class="journal-body">
        <div class="journal-header-line">-- Journal begins at {{ journalDate }} --</div>
        <template v-if="recentLogs.length">
          <div v-for="log in recentLogs" :key="log.id" class="journal-row">
            <span class="j-when">{{ formatLogDate(log.started_at) }}</span>
            <span class="j-user">{{ log.username }}</span>
            <span class="j-script">{{ log.script_path?.split('/').at(-1) || '—' }}</span>
            <span class="j-dur">{{ log.duration_seconds != null ? `${log.duration_seconds.toFixed(1)}s` : '—' }}</span>
            <span v-if="log.exit_code === null"    class="badge badge-blue">running</span>
            <span v-else-if="log.exit_code === 0"  class="badge badge-green">exit 0</span>
            <span v-else                           class="badge badge-red">exit {{ log.exit_code }}</span>
          </div>
        </template>
        <div v-else class="journal-empty">No executions yet</div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { RouterLink } from 'vue-router'
import Select from 'primevue/select'
import Chart from 'primevue/chart'
import MetricCard from '../components/dashboard/MetricCard.vue'
import { usePolling } from '../composables/usePolling.js'
import { useChartTheme } from '../composables/useChartTheme.js'
import api from '../api/client.js'

const { chartBg, containerStyle, buildScales, buildTooltip } = useChartTheme()

// ── ECG live chart ─────────────────────────────────────────────────────
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

const chartData = ref({
  labels: [],
  datasets: [
    { label: 'CPU %',  data: [], borderColor: '#f97316', borderWidth: 2, tension: 0.3, pointRadius: 0, fill: false },
    { label: 'RAM %',  data: [], borderColor: '#3b82f6', borderWidth: 2, tension: 0.3, pointRadius: 0, fill: false },
    { label: 'Disk %', data: [], borderColor: '#10b981', borderWidth: 2, tension: 0.3, pointRadius: 0, fill: false },
  ],
})

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

function toggleSeries(label) {
  if (hiddenSeries.value.has(label)) {
    hiddenSeries.value.delete(label)
  } else {
    hiddenSeries.value.add(label)
  }
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

// ── Metrics ──────────────────────────────────────────────────────────
const metrics = ref({
  cpu_percent: 0, ram_percent: 0, ram_used_gb: 0, ram_total_gb: 0,
  disk_percent: 0, disk_used_gb: 0, disk_total_gb: 0, uptime_seconds: 0,
  load_average: [0, 0, 0], os_name: '', hostname: '', cpu_count: 0, cpu_arch: '',
  utc_offset_seconds: 0, utc_label: '', timezone_name: '',
})
const error = ref('')
const recentLogs = ref([])

// ── WebSocket ─────────────────────────────────────────────────────────
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

async function fetchRecentLogs() {
  try {
    const { data } = await api.get('/logs/executions', { params: {} })
    recentLogs.value = data.slice(0, 5)
  } catch { /* non-critical */ }
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

// ── Computed ──────────────────────────────────────────────────────────
const uptimeFormatted = computed(() => {
  const s = metrics.value.uptime_seconds
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (d > 0) return `${d}d ${h}h ${m}m`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
})

const diskAvailGb = computed(() => {
  const total = parseFloat(metrics.value.disk_total_gb) || 0
  const used  = parseFloat(metrics.value.disk_used_gb)  || 0
  return (total - used).toFixed(1)
})

const diskPctColor = computed(() => {
  const p = metrics.value.disk_percent
  if (p >= 85) return 'kv-red'
  if (p >= 60) return 'kv-yellow'
  return 'kv-green'
})

const ramPctColor = computed(() => {
  const p = metrics.value.ram_percent
  if (p >= 85) return 'kv-red'
  if (p >= 60) return 'kv-yellow'
  return 'kv-green'
})

function loadColor(v, i) {
  const cores = metrics.value.cpu_count || 1
  const ratio = v / cores
  if (ratio >= 0.85) return 'kv-red'
  if (ratio >= 0.6)  return 'kv-yellow'
  return 'kv-green'
}

const journalDate = computed(() => {
  const d = new Date()
  return d.toLocaleDateString('en-US', { weekday: 'short', year: 'numeric', month: 'short', day: '2-digit' })
})

function formatLogDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  return time
}
</script>

<style scoped>
.dashboard { display: flex; flex-direction: column; gap: 14px; }

/* ── Gauge row ────────────────────────────────────────────── */
.gauge-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
@media (max-width: 640px) { .gauge-row { grid-template-columns: 1fr; } }

/* ── Info grid (two terminal blocks side by side) ─────────── */
.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
@media (max-width: 768px) { .info-grid { grid-template-columns: 1fr; } }

/* ── KV rows inside terminal blocks ──────────────────────── */
.uname-line {
  font-size: var(--text-xs);
  color: var(--p-text-muted-color);
  margin-bottom: 8px;
  letter-spacing: 0.3px;
  opacity: 0.7;
}
.kv-row {
  display: flex;
  gap: 0;
  line-height: 1.9;
}
.kv-key {
  color: var(--p-text-muted-color);
  min-width: 110px;
  flex-shrink: 0;
}
.kv-val { color: var(--p-text-color); }
.kv-orange { color: var(--brand-orange) !important; }
.kv-green  { color: #4ade80 !important; }
.kv-yellow { color: #fde047 !important; }
.kv-red    { color: #f87171 !important; }

/* ── Load average ─────────────────────────────────────────── */
.load-row-inline {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.load-pair {
  display: flex;
  align-items: baseline;
  gap: 3px;
  font-size: var(--text-xs);
}
.load-period { color: var(--p-surface-500); margin-left: 2px; }

/* ── df-h block ───────────────────────────────────────────── */
.df-header {
  font-size: var(--text-xs);
  color: var(--p-surface-500);
  margin-bottom: 4px;
}
.df-row {
  display: flex;
  align-items: center;
  font-size: var(--text-xs);
  line-height: 2;
}
.df-fs   { color: var(--p-text-muted-color); min-width: 100px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.df-size { color: var(--p-text-muted-color); min-width: 44px; text-align: right; }
.df-used { color: var(--p-text-color); min-width: 44px; text-align: right; }
.df-avail{ color: var(--p-text-muted-color); min-width: 44px; text-align: right; }
.df-pct  { min-width: 44px; text-align: right; font-weight: 600; }

/* ── Live metrics chart ───────────────────────────────────── */
.live-badge {
  display: flex;
  align-items: center;
  gap: 5px;
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  font-weight: 600;
  letter-spacing: 1.5px;
  color: #22c55e;
  margin-left: auto;
}
.live-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 6px #22c55e;
  animation: pulse-dot 1.4s ease-in-out infinite;
  flex-shrink: 0;
}
@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%       { opacity: 0.5; transform: scale(0.8); }
}
.chart-area { height: 260px; position: relative; padding: 10px 14px; }
.ecg-chart  { height: 100%; width: 100%; }

.ecg-legend {
  display: flex;
  gap: 16px;
  padding: 8px 14px 12px;
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
  width: 16px; height: 2px;
  background: var(--c);
  box-shadow: 0 0 5px var(--c);
  border-radius: 1px;
}
.legend-hidden { opacity: 0.25; }

/* Window select */
:deep(.window-select) { font-family: var(--font-mono); font-size: var(--text-xs); }
:deep(.window-select .p-select-label) { padding: 4px 8px; font-size: var(--text-xs); }

/* ── History CTA ──────────────────────────────────────────── */
.history-cta {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-radius: var(--radius-base);
  border: 1px solid var(--border-strong);
  background: var(--p-surface-card);
  text-decoration: none;
  color: var(--p-text-muted-color);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  letter-spacing: 0.5px;
  transition: var(--transition-fast);
  cursor: pointer;
}
.history-cta:hover {
  border-color: color-mix(in srgb, var(--brand-orange) 40%, transparent);
  color: var(--brand-orange);
  background: var(--orange-tint-05);
}
.history-cta-text { flex: 1; }
.history-cta-arrow { font-size: 11px; flex-shrink: 0; transition: transform 0.15s; }
.history-cta:hover .history-cta-arrow { transform: translateX(3px); }

/* ── Journal (recent executions) ──────────────────────────── */
.view-all-link {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--p-blue-500);
  text-decoration: none;
  cursor: pointer;
  letter-spacing: 0.5px;
  flex-shrink: 0;
}
.journal-body {
  padding: 10px 14px;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
}
.journal-header-line {
  color: var(--p-surface-500);
  margin-bottom: 6px;
}
.journal-row {
  display: flex;
  align-items: center;
  gap: 0;
  line-height: 1.9;
  flex-wrap: nowrap;
}
.j-when   { color: var(--p-surface-500); min-width: 80px; flex-shrink: 0; }
.j-user   { color: var(--p-text-muted-color); min-width: 60px; flex-shrink: 0; }
.j-script { color: var(--p-text-color); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.j-dur    { color: var(--p-text-muted-color); min-width: 50px; text-align: right; margin-right: 8px; flex-shrink: 0; }
.journal-empty {
  color: var(--p-text-muted-color);
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  padding: 8px 0;
}
</style>
