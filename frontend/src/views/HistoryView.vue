<template>
  <div class="history-view">

    <!-- ── Page Header ── -->
    <div class="page-header">
      <RouterLink to="/" class="back-link">
        <i class="pi pi-arrow-left back-icon" />
        Dashboard
      </RouterLink>
      <span class="page-title">HISTORY</span>
    </div>

    <!-- ── Resource History ── -->
    <Card class="hist-card">
      <template #content>
        <div class="card-section-header">
          <i class="pi pi-chart-line section-icon" />
          <span class="section-title">RESOURCE HISTORY</span>
          <div class="header-controls">
            <span class="section-extra">CPU · RAM · Disk</span>
            <Select v-model="metricsHours" :options="hourOptions" option-label="label" option-value="value" class="hours-select" />
          </div>
        </div>
        <Divider class="section-divider" />
        <div class="chart-wrap" :style="containerStyle">
          <div v-if="loadingMetrics" class="loading-state">
            <ProgressSpinner style="width:40px;height:40px" strokeWidth="4" />
          </div>
          <Chart v-else-if="metricsChartData.labels.length" type="line" :data="metricsChartData" :options="areaOptions" class="history-chart" />
          <div v-else class="empty-state">
            <i class="pi pi-chart-line empty-icon" />
            <span>No history yet — data collects every 60s automatically</span>
          </div>
        </div>
      </template>
    </Card>

    <!-- ── Network Bandwidth History ── -->
    <Card class="hist-card">
      <template #content>
        <div class="card-section-header">
          <i class="pi pi-wifi section-icon" />
          <span class="section-title">BANDWIDTH HISTORY</span>
          <div class="header-controls">
            <Select v-model="selectedIface" :options="ifaceOptions" placeholder="All interfaces"
              :show-clear="true" class="iface-select" />
            <Select v-model="netHours" :options="hourOptions" option-label="label" option-value="value" class="hours-select" />
          </div>
        </div>
        <Divider class="section-divider" />
        <div class="chart-wrap" :style="containerStyle">
          <div v-if="loadingBandwidth" class="loading-state">
            <ProgressSpinner style="width:40px;height:40px" strokeWidth="4" />
          </div>
          <Chart v-else-if="bandwidthChartData.labels.length" type="line" :data="bandwidthChartData" :options="bandwidthOptions" class="history-chart" />
          <div v-else class="empty-state">
            <i class="pi pi-wifi empty-icon" />
            <span>No bandwidth history yet — sampling every 60s</span>
          </div>
        </div>
      </template>
    </Card>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import Card from 'primevue/card'
import Divider from 'primevue/divider'
import Select from 'primevue/select'
import ProgressSpinner from 'primevue/progressspinner'
import Chart from 'primevue/chart'
import api from '../api/client.js'
import { useChartTheme } from '../composables/useChartTheme.js'
import { RouterLink } from 'vue-router'

const { containerStyle, buildScales, buildTooltip, buildLegend } = useChartTheme()
const loadingMetrics = ref(false)
const loadingBandwidth = ref(false)

const hourOptions = [
  { label: '1h',   value: 1   },
  { label: '6h',   value: 6   },
  { label: '12h',  value: 12  },
  { label: '24h',  value: 24  },
  { label: '48h',  value: 48  },
  { label: '7d',   value: 168 },
  { label: '30d',  value: 720 },
]

function formatHistoryLabel(isoStr, hours) {
  const d = new Date(isoStr)
  if (hours <= 48) {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' }) +
         ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

// ── Metrics history ──
const metricsHours = ref(24)
const metricsData = ref([])

async function fetchMetrics() {
  loadingMetrics.value = true
  try {
    const { data } = await api.get('/metrics/history', { params: { hours: metricsHours.value } })
    metricsData.value = data
  } catch { /* non-critical */ }
  finally { loadingMetrics.value = false }
}

const metricsChartData = computed(() => ({
  labels: metricsData.value.map(p => formatHistoryLabel(p.timestamp, metricsHours.value)),
  datasets: [
    { label: 'CPU %',  data: metricsData.value.map(p => p.cpu_percent),  borderColor: '#f97316', backgroundColor: 'rgba(249,115,22,0.08)',  fill: true, tension: 0.3, pointRadius: 0, borderWidth: 2 },
    { label: 'RAM %',  data: metricsData.value.map(p => p.ram_percent),  borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,0.08)',   fill: true, tension: 0.3, pointRadius: 0, borderWidth: 2 },
    { label: 'Disk %', data: metricsData.value.map(p => p.disk_percent), borderColor: '#10b981', backgroundColor: 'rgba(16,185,129,0.08)',   fill: true, tension: 0.3, pointRadius: 0, borderWidth: 2 },
  ],
}))

const areaOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: buildLegend(true),
    tooltip: buildTooltip(ctx => ` ${ctx.dataset.label}: ${ctx.parsed.y?.toFixed(1)}%`),
  },
  scales: buildScales({ yMin: 0, yMax: 100, yCallback: v => `${v}%`, xMaxTicks: 8 }),
}))

watch(metricsHours, fetchMetrics)

// ── Network bandwidth history ──
const netHours = ref(24)
const selectedIface = ref(null)
const bandwidthData = ref([])
const ifaceOptions = ref([])

async function fetchBandwidth() {
  loadingBandwidth.value = true
  try {
    const params = { hours: netHours.value }
    if (selectedIface.value) params.interface = selectedIface.value
    const { data } = await api.get('/network/bandwidth', { params })
    bandwidthData.value = data
  } catch { /* non-critical */ }
  finally { loadingBandwidth.value = false }
}

async function fetchIfaceNames() {
  try {
    const { data } = await api.get('/network/interfaces/names')
    ifaceOptions.value = data
  } catch { /* non-critical */ }
}

const COLORS = ['#f97316', '#3b82f6', '#10b981', '#8b5cf6', '#ec4899']

const bandwidthChartData = computed(() => {
  const ifaceSet = [...new Set(bandwidthData.value.map(p => p.interface))]
  const labels = [...new Set(bandwidthData.value.map(p =>
    formatHistoryLabel(p.timestamp, netHours.value)
  ))]
  const datasets = ifaceSet.map((iface, idx) => {
    const color = COLORS[idx % COLORS.length]
    const pts = bandwidthData.value.filter(p => p.interface === iface)
    return {
      label: `${iface} recv`,
      data: pts.map(p => +(p.bytes_recv / 1024 / 1024).toFixed(3)),
      borderColor: color, backgroundColor: color + '12',
      fill: true, tension: 0.3, pointRadius: 0, borderWidth: 2,
    }
  })
  return { labels, datasets }
})

const bandwidthOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: buildLegend(true),
    tooltip: buildTooltip(ctx => ` ${ctx.dataset.label}: ${ctx.parsed.y?.toFixed(2)} MB`),
  },
  scales: buildScales({ yCallback: v => `${v} MB`, xMaxTicks: 8 }),
}))

watch([netHours, selectedIface], fetchBandwidth)

onMounted(() => {
  fetchMetrics()
  fetchBandwidth()
  fetchIfaceNames()
})
</script>

<style scoped>
.history-view { display: flex; flex-direction: column; gap: 16px; }

:deep(.hist-card .p-card-body) { padding: 0; }
:deep(.hist-card .p-card-content) { padding: 14px 16px; }

.card-section-header { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.section-icon { font-size: 12px; color: var(--brand-orange); flex-shrink: 0; }
.section-title {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--p-text-muted-color);
  flex: 1;
}
.section-extra { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-muted-color); }
.header-controls { display: flex; align-items: center; gap: 8px; }
.section-divider { margin: 10px 0 !important; }

.chart-wrap {
  height: 320px;
  position: relative;
}
.history-chart {
  height: 100%;
  width: 100%;
}

.empty-state {
  height: 220px;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 10px;
  color: var(--p-text-muted-color);
  font-family: var(--font-mono);
  font-size: var(--text-sm);
}
.empty-icon { font-size: 2rem; opacity: 0.25; }

.hours-select { width: 90px; }
.iface-select { width: 160px; }

/* Page header */
.page-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 4px;
}
.back-link {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--p-text-muted-color);
  text-decoration: none;
  transition: color 0.15s;
}
.back-link:hover { color: var(--brand-orange); }
.back-icon { font-size: 11px; }
.page-title {
  font-family: var(--font-mono);
  font-size: var(--text-base);
  font-weight: 700;
  letter-spacing: 3px;
  color: var(--p-text-color);
  text-transform: uppercase;
}

/* Loading state */
.loading-state {
  height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
