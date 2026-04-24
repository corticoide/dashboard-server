<template>
  <div class="network-view">

    <div v-if="error" class="banner banner-error"><i class="pi pi-times-circle" />{{ error }}</div>

    <!-- ── Live Interface Cards ── -->
    <div class="iface-grid">
      <Card v-for="iface in interfaces" :key="iface.name" class="iface-card" :class="{ 'iface-down': !iface.is_up }">
        <template #content>
          <div class="iface-header">
            <div class="iface-name-group">
              <i :class="['pi', ifaceIcon(iface.name), 'iface-icon']" />
              <span class="iface-name">{{ iface.name }}</span>
            </div>
            <span :class="iface.is_up ? 'badge-green' : 'badge-red'">{{ iface.is_up ? 'UP' : 'DOWN' }}</span>
          </div>

          <div class="iface-meta">
            <span class="iface-ip">{{ iface.ip || 'No IP' }}</span>
            <span class="iface-mac">{{ iface.mac || '—' }}</span>
          </div>

          <div class="iface-badges">
            <span v-if="iface.is_internet_gateway" class="badge-green">INTERNET</span>
            <span v-if="iface.subnet" class="iface-subnet">{{ iface.subnet }}</span>
          </div>

          <div v-if="liveBps[iface.name]" class="bps-block">
            <div class="bps-item">
              <span class="bps-arrow bps-up-arrow">↑</span>
              <span class="bps-val bps-up-val">{{ formatBps(liveBps[iface.name].sent_bps) }}/s</span>
            </div>
            <div class="bps-sep" />
            <div class="bps-item">
              <span class="bps-arrow bps-dn-arrow">↓</span>
              <span class="bps-val bps-dn-val">{{ formatBps(liveBps[iface.name].recv_bps) }}/s</span>
            </div>
          </div>
          <div v-else class="bps-block bps-waiting">
            <span class="bps-waiting-text">— waiting for data —</span>
          </div>

          <Divider class="iface-divider" />

          <div class="iface-stats">
            <div class="stat-row">
              <span class="stat-label">TOTAL TX</span>
              <span class="stat-val">{{ formatBytes(iface.bytes_sent) }}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">TOTAL RX</span>
              <span class="stat-val">{{ formatBytes(iface.bytes_recv) }}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">LINK</span>
              <span class="stat-val">{{ iface.speed_mbps ? `${iface.speed_mbps} Mbps` : '—' }}</span>
            </div>
            <div v-if="iface.errin + iface.errout + iface.dropin + iface.dropout > 0" class="stat-row stat-error">
              <span class="stat-label">ERRORS</span>
              <span class="stat-val">err {{ iface.errin + iface.errout }} / drop {{ iface.dropin + iface.dropout }}</span>
            </div>
          </div>
        </template>
      </Card>
    </div>

    <!-- ── Traffic Analysis (Live ECG) ── -->
    <Card class="net-card">
      <template #content>
        <div class="card-section-header">
          <i class="pi pi-wave-pulse section-icon" />
          <span class="section-title">TRAFFIC ANALYSIS</span>
          <span class="live-dot-wrapper"><span class="live-dot" />LIVE</span>
          <div class="chart-controls">
            <Select v-model="trafficWindowSize" :options="windowOptions" option-label="label" option-value="value"
              class="window-select" size="small" />
          </div>
        </div>
        <Divider class="section-divider" />
        <div class="chart-container" :style="containerStyle">
          <Chart type="line" :data="trafficChartData" :options="trafficChartOptions" :plugins="ecgPlugins" class="ecg-chart" />
        </div>
        <div class="ecg-legend" v-if="trafficLegendItems.length">
          <span v-for="item in trafficLegendItems" :key="item.label"
            class="ecg-legend-item"
            :class="{ 'legend-hidden': hiddenTrafficSeries.has(item.label) }"
            :style="`--c:${item.color}`"
            @click="toggleTrafficSeries(item.label)">
            {{ item.label }}
          </span>
        </div>
      </template>
    </Card>

    <!-- ── History CTA ── -->
    <RouterLink to="/history" class="history-cta">
      <i class="pi pi-chart-bar history-cta-icon" />
      <span class="history-cta-text">View Bandwidth &amp; Resource History</span>
      <i class="pi pi-arrow-right history-cta-arrow" />
    </RouterLink>

    <!-- ── Connection States + Device Detection ── -->
    <div class="two-col-grid">
      <Card class="net-card">
        <template #content>
          <div class="card-section-header">
            <i class="pi pi-chart-bar section-icon" />
            <span class="section-title">CONNECTION STATES</span>
            <span class="section-extra">{{ totalConnections }} total</span>
          </div>
          <Divider class="section-divider" />
          <div class="conn-summary">
            <div v-for="(count, state) in connSummary" :key="state" class="conn-state-item">
              <span :class="stateBadgeClass(state)">{{ state }}</span>
              <span class="state-count">{{ count }}</span>
            </div>
            <span v-if="Object.keys(connSummary).length === 0" class="cell-empty">No connections</span>
          </div>
        </template>
      </Card>

      <!-- ── Device Detection (ARP) ── -->
      <Card class="net-card">
        <template #content>
          <div class="card-section-header">
            <i class="pi pi-sitemap section-icon" />
            <span class="section-title">DEVICE DETECTION</span>
            <span class="section-extra">{{ devices.length }} device{{ devices.length !== 1 ? 's' : '' }}</span>
          </div>
          <Divider class="section-divider" />
          <div v-if="devices.length === 0" class="cell-empty">No LAN devices in ARP table</div>
          <div v-else class="device-list">
            <div v-for="d in devices" :key="d.ip + d.mac" class="device-row">
              <div class="device-icon-wrap"><i class="pi pi-desktop device-icon" /></div>
              <div class="device-info">
                <span class="device-ip">{{ d.ip }}</span>
                <span class="device-mac">{{ d.mac }}</span>
              </div>
              <span class="badge-neutral">{{ d.interface }}</span>
            </div>
          </div>
        </template>
      </Card>
    </div>

    <!-- ── Active Connections Table ── -->
    <Card class="net-card">
      <template #content>
        <div class="card-section-header">
          <i class="pi pi-arrows-h section-icon" />
          <span class="section-title">ACTIVE CONNECTIONS</span>
          <div class="header-controls">
            <div class="search-field">
              <i class="pi pi-search search-icon" />
              <input v-model="connSearch" class="search-input" placeholder="Filter address…" />
            </div>
            <Select v-model="connStatusFilter" :options="statusOptions" placeholder="All states"
              :show-clear="true" class="status-select" />
            <Select v-model="connProtoFilter" :options="['TCP','UDP']" placeholder="All proto"
              :show-clear="true" class="proto-select" />
            <ToggleButton v-model="showLocal"
              on-label="+ LOCAL" off-label="− LOCAL"
              on-icon="pi pi-eye" off-icon="pi pi-eye-slash"
              size="small" class="local-toggle" />
          </div>
        </div>
        <Divider class="section-divider" />
        <DataTable :value="filteredConnections" size="small" :show-gridlines="false"
          :paginator="filteredConnections.length > 25" :rows="25"
          sort-field="status" :sort-order="1"
          class="conn-table">
          <template #empty><span class="cell-empty">No connections match filters</span></template>
          <Column field="proto" header="Proto" style="width: 70px">
            <template #body="{ data }">
              <span :class="data.proto === 'TCP' ? 'badge-blue' : 'badge-neutral'">{{ data.proto }}</span>
            </template>
          </Column>
          <Column field="local_addr" header="Local Address" />
          <Column field="remote_addr" header="Remote Address">
            <template #body="{ data }">
              <span :class="{ 'remote-external': isExternal(data.remote_addr) }">
                {{ data.remote_addr || '—' }}
              </span>
            </template>
          </Column>
          <Column field="status" header="State" style="width: 130px">
            <template #body="{ data }">
              <span :class="stateBadgeClass(data.status)">{{ data.status }}</span>
            </template>
          </Column>
          <Column field="pid" header="PID" style="width: 70px">
            <template #body="{ data }">
              <span class="cell-mono">{{ data.pid ?? '—' }}</span>
            </template>
          </Column>
        </DataTable>
      </template>
    </Card>

    <!-- ── Configuration Management ── -->
    <Card class="net-card">
      <template #content>
        <div class="card-section-header">
          <i class="pi pi-sliders-h section-icon" />
          <span class="section-title">CONFIGURATION</span>
        </div>
        <Divider class="section-divider" />
        <div class="config-grid">
          <div class="config-section">
            <span class="config-section-label">DEFAULT GATEWAYS</span>
            <div v-if="netConfig.gateways?.length" class="config-items">
              <div v-for="gw in netConfig.gateways" :key="gw.interface" class="config-item">
                <span class="config-key">{{ gw.interface }}</span>
                <span class="config-val">{{ gw.gateway }}</span>
              </div>
            </div>
            <span v-else class="cell-empty">No gateway detected</span>
          </div>
          <div class="config-section">
            <span class="config-section-label">DNS SERVERS</span>
            <div v-if="netConfig.dns_servers?.length" class="config-items">
              <div v-for="(dns, i) in netConfig.dns_servers" :key="i" class="config-item">
                <span class="config-key">DNS {{ i + 1 }}</span>
                <span class="config-val">{{ dns }}</span>
              </div>
            </div>
            <span v-else class="cell-empty">No DNS servers found</span>
          </div>
          <div class="config-section">
            <span class="config-section-label">INTERFACES SUMMARY</span>
            <div class="config-items">
              <div v-for="iface in interfaces" :key="iface.name" class="config-item">
                <span class="config-key">{{ iface.name }}</span>
                <span class="config-val">{{ iface.ip || 'No IP' }}</span>
              </div>
            </div>
          </div>
        </div>
      </template>
    </Card>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { RouterLink } from 'vue-router'
import Card from 'primevue/card'
import Divider from 'primevue/divider'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Select from 'primevue/select'
import ToggleButton from 'primevue/togglebutton'
import Chart from 'primevue/chart'
import { usePolling } from '../composables/usePolling.js'
import { useChartTheme } from '../composables/useChartTheme.js'
import api from '../api/client.js'

const { chartBg, containerStyle, buildScales, buildTooltip } = useChartTheme()

// ── State ──
const error = ref('')
const interfaces = ref([])
const connections = ref([])
const connSummary = ref({})
const devices = ref([])
const netConfig = ref({ dns_servers: [], gateways: [] })
const liveBps = ref({})
const connSearch = ref('')
const connStatusFilter = ref(null)
const connProtoFilter = ref(null)
const showLocal = ref(false)

// ── Traffic Analysis (ECG live chart) ──
const TRAFFIC_BUFFER = 90
const IFACE_COLORS = ['#f97316', '#3b82f6', '#10b981', '#8b5cf6', '#ec4899', '#facc15']

const trafficWindowSize = ref(60)
const windowOptions = [
  { label: '30s', value: 30 },
  { label: '1m',  value: 60 },
  { label: '3m',  value: 90 },
  { label: 'MAX', value: 120 },
]

const hiddenTrafficSeries = ref(new Set())

// Internal buffer — non-reactive for performance
const traffic = { labels: [], series: {} }
// Track known interfaces and their colors for stable legend
const knownIfaces = ref([])

// Reactive chart data — PrimeVue Chart watches this
const trafficChartData = ref({
  labels: [],
  datasets: [],
})

const trafficChartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  plugins: {
    legend: { display: false },
    tooltip: buildTooltip((ctx) => ` ${ctx.dataset.label}: ${formatBps(ctx.parsed.y * 8)}`),
  },
  scales: buildScales({ yCallback: (v) => formatBps(v) }),
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
      const color = chart.data.datasets[index]?.borderColor
      if (color) { chart.ctx.shadowColor = color; chart.ctx.shadowBlur = 10 }
    },
    afterDatasetsDraw(chart) { chart.ctx.restore() },
  },
]

const trafficLegendItems = computed(() => {
  return knownIfaces.value.flatMap((iface, idx) => {
    const color = IFACE_COLORS[idx % IFACE_COLORS.length]
    return [
      { label: `${iface} ↑`, color },
      { label: `${iface} ↓`, color },
    ]
  })
})

function toggleTrafficSeries(label) {
  if (hiddenTrafficSeries.value.has(label)) {
    hiddenTrafficSeries.value.delete(label)
  } else {
    hiddenTrafficSeries.value.add(label)
  }
  rebuildTrafficChart()
}

function rebuildTrafficChart() {
  const w = trafficWindowSize.value
  const labels = traffic.labels.slice(-w)
  const datasets = []

  knownIfaces.value.forEach((iface, idx) => {
    const color = IFACE_COLORS[idx % IFACE_COLORS.length]
    const s = traffic.series[iface]
    if (!s) return

    const sentLabel = `${iface} ↑`
    const recvLabel = `${iface} ↓`

    datasets.push({
      label: sentLabel,
      data: s.sent.slice(-w),
      borderColor: color,
      borderWidth: 1.5,
      tension: 0.3,
      pointRadius: 0,
      fill: false,
      hidden: hiddenTrafficSeries.value.has(sentLabel),
    })
    datasets.push({
      label: recvLabel,
      data: s.recv.slice(-w),
      borderColor: color,
      borderWidth: 2,
      borderDash: [4, 3],
      tension: 0.3,
      pointRadius: 0,
      fill: false,
      hidden: hiddenTrafficSeries.value.has(recvLabel),
    })
  })

  trafficChartData.value = { labels, datasets }
}

function pushTrafficPoint(bpsMap) {
  const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  traffic.labels.push(now)
  if (traffic.labels.length > TRAFFIC_BUFFER) traffic.labels.shift()

  for (const [iface, bps] of Object.entries(bpsMap)) {
    if (!traffic.series[iface]) {
      traffic.series[iface] = { sent: [], recv: [] }
      if (!knownIfaces.value.includes(iface)) {
        knownIfaces.value.push(iface)
      }
    }
    traffic.series[iface].sent.push(bps.sent_bps ?? 0)
    traffic.series[iface].recv.push(bps.recv_bps ?? 0)
    if (traffic.series[iface].sent.length > TRAFFIC_BUFFER) {
      traffic.series[iface].sent.shift()
      traffic.series[iface].recv.shift()
    }
  }

  rebuildTrafficChart()
}

// ── WebSocket ──
let ws = null

function connectWs() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const token = localStorage.getItem('access_token') || ''
  ws = new WebSocket(`${proto}://${location.host}/api/ws/network?token=${token}`)

  ws.onmessage = (evt) => {
    try {
      const data = JSON.parse(evt.data)
      if (data.interfaces) interfaces.value = data.interfaces
      if (data.bps) {
        liveBps.value = data.bps
        pushTrafficPoint(data.bps)
      }
      error.value = ''
    } catch { /* ignore parse errors */ }
  }
  ws.onerror = () => { error.value = 'Live connection error — retrying...' }
  ws.onclose = () => { if (ws) setTimeout(connectWs, 5000) }
}

function disconnectWs() {
  if (ws) { const old = ws; ws = null; old.close() }
}

// ── REST fetches ──
async function fetchConnections() {
  try {
    const { data } = await api.get('/network/connections')
    connections.value = data
  } catch { /* non-critical */ }
}

async function fetchConnSummary() {
  try {
    const { data } = await api.get('/network/connections/summary')
    connSummary.value = data.counts
  } catch { /* non-critical */ }
}

async function fetchInterfaces() {
  try {
    const { data } = await api.get('/network/interfaces')
    interfaces.value = data
    error.value = ''
  } catch { error.value = 'Failed to fetch network interfaces' }
}

async function fetchDevices() {
  try {
    const { data } = await api.get('/network/devices')
    devices.value = data
  } catch { /* non-critical */ }
}

async function fetchNetConfig() {
  try {
    const { data } = await api.get('/network/config')
    netConfig.value = data
  } catch { /* non-critical */ }
}

// ── Computed ──
const totalConnections = computed(() => Object.values(connSummary.value).reduce((a, b) => a + b, 0))
const statusOptions = computed(() => Object.keys(connSummary.value))

const filteredConnections = computed(() => {
  let list = connections.value

  if (!showLocal.value) {
    list = list.filter(c => {
      const localIp = c.local_addr.split(':')[0]
      const remoteIp = (c.remote_addr || '').split(':')[0]
      return localIp !== '127.0.0.1' && localIp !== '::1' &&
             remoteIp !== '127.0.0.1' && remoteIp !== '::1'
    })
  }

  if (connStatusFilter.value) list = list.filter(c => c.status === connStatusFilter.value)
  if (connProtoFilter.value) list = list.filter(c => c.proto === connProtoFilter.value)
  if (connSearch.value) {
    const q = connSearch.value.toLowerCase()
    list = list.filter(c => c.local_addr.includes(q) || (c.remote_addr || '').includes(q))
  }
  return list
})

// ── Helpers ──
function formatBytes(b) {
  if (b >= 1e12) return `${(b / 1e12).toFixed(2)} TB`
  if (b >= 1e9) return `${(b / 1e9).toFixed(2)} GB`
  if (b >= 1e6) return `${(b / 1e6).toFixed(2)} MB`
  if (b >= 1e3) return `${(b / 1e3).toFixed(1)} KB`
  return `${b} B`
}

function formatBps(bps) {
  if (!bps || bps < 0) return '0 B'
  return formatBytes(Math.round(bps))
}

function isExternal(addr) {
  if (!addr) return false
  const ip = addr.split(':')[0]
  return !ip.startsWith('127.') && !ip.startsWith('10.') &&
    !ip.startsWith('192.168.') && !ip.startsWith('172.') && ip !== ''
}

function ifaceIcon(name) {
  if (/^(eth|en|em)\d/i.test(name)) return 'pi-server'
  if (/^(wlan|wl|wifi|ath)\d*/i.test(name)) return 'pi-wifi'
  if (/^(tun|tap|vpn)/i.test(name)) return 'pi-shield'
  if (/^(docker|br-|veth|virbr)/i.test(name)) return 'pi-box'
  return 'pi-globe'
}

function stateBadgeClass(state) {
  const map = {
    ESTABLISHED: 'badge-green', LISTEN: 'badge-blue', TIME_WAIT: 'badge-yellow',
    CLOSE_WAIT: 'badge-yellow', SYN_SENT: 'badge-neutral', FIN_WAIT1: 'badge-neutral',
    FIN_WAIT2: 'badge-neutral', CLOSED: 'badge-neutral', NONE: 'badge-neutral',
  }
  return map[state] ?? 'badge-neutral'
}

// ── Polling ──
const { start: startConns, stop: stopConns } = usePolling(() => {
  fetchConnections(); fetchConnSummary()
}, 10000)
const { start: startDevices, stop: stopDevices } = usePolling(fetchDevices, 30000)

onMounted(() => {
  fetchInterfaces()
  fetchConnections()
  fetchConnSummary()
  fetchDevices()
  fetchNetConfig()
  connectWs()
  startConns()
  startDevices()
})

onUnmounted(() => {
  stopConns()
  stopDevices()
  disconnectWs()
})
</script>

<style scoped>
.network-view { display: flex; flex-direction: column; gap: 16px; }

/* ── Interface cards grid ── */
.iface-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
}
:deep(.iface-card .p-card-body) { padding: 0; }
:deep(.iface-card .p-card-content) { padding: 14px 16px; }
.iface-card {
  border: 1px solid var(--p-surface-border);
  transition: border-color 0.2s, box-shadow 0.2s;
}
.iface-card:hover { border-color: color-mix(in srgb, var(--brand-orange) 40%, transparent); box-shadow: 0 0 16px color-mix(in srgb, var(--brand-orange) 8%, transparent); }
.iface-down { opacity: 0.5; }

.iface-header { display: flex; align-items: center; justify-content: space-between; }
.iface-name-group { display: flex; align-items: center; gap: 7px; }
.iface-icon { font-size: 14px; color: var(--brand-orange); }
.iface-name { font-family: var(--font-mono); font-size: var(--text-base); font-weight: 700; color: var(--brand-orange); }

.iface-meta { margin-top: 6px; display: flex; flex-direction: column; gap: 1px; }
.iface-ip { font-family: var(--font-mono); font-size: var(--text-sm); color: var(--p-text-color); }
.iface-mac { font-family: var(--font-mono); font-size: var(--text-2xs); color: var(--p-text-muted-color); letter-spacing: 0.5px; }

.bps-block {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 10px 0 0;
  padding: 8px 10px;
  background: var(--p-surface-hover);
  border-radius: 6px;
  border: 1px solid var(--p-surface-border);
}
.bps-item { display: flex; align-items: center; gap: 4px; flex: 1; }
.bps-sep { width: 1px; height: 24px; background: var(--p-surface-border); }
.bps-arrow { font-size: 13px; font-weight: 700; line-height: 1; }
.bps-up-arrow { color: #f97316; }
.bps-dn-arrow { color: #3b82f6; }
.bps-val { font-family: var(--font-mono); font-size: var(--text-xs); font-weight: 600; }
.bps-up-val { color: #f97316; }
.bps-dn-val { color: #3b82f6; }
.bps-waiting { justify-content: center; }
.bps-waiting-text { font-family: var(--font-mono); font-size: var(--text-2xs); color: var(--p-text-muted-color); opacity: 0.5; }

.iface-divider { margin: 10px 0 !important; }
.iface-stats { display: flex; flex-direction: column; gap: 4px; }
.stat-row { display: flex; justify-content: space-between; align-items: center; }
.stat-label { font-family: var(--font-mono); font-size: var(--text-2xs); letter-spacing: 1px; color: var(--p-text-muted-color); }
.stat-val { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-color); }
.stat-error .stat-label { color: var(--p-red-400); }
.stat-error .stat-val { color: var(--p-red-400); }

/* ── General card layout ── */
:deep(.net-card .p-card-body) { padding: 0; }
:deep(.net-card .p-card-content) { padding: 14px 16px; }
.card-section-header { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.section-icon { font-size: 12px; color: var(--brand-orange); flex-shrink: 0; }
.section-title { font-family: var(--font-mono); font-size: var(--text-2xs); letter-spacing: 2px; text-transform: uppercase; color: var(--p-text-muted-color); flex: 1; }
.section-extra { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-muted-color); }
.header-controls { display: flex; gap: 8px; align-items: center; }
.search-field { position: relative; display: flex; align-items: center; }
.search-icon { position: absolute; left: 8px; font-size: 11px; color: var(--p-text-muted-color); pointer-events: none; }
.search-input {
  padding: 5px 10px 5px 28px; width: 180px;
  background: var(--p-surface-900); border: 1px solid var(--p-surface-border);
  border-radius: var(--radius-base); font-family: var(--font-mono); font-size: var(--text-sm);
  color: var(--p-text-color); outline: none; transition: var(--transition-fast);
}
.search-input:focus { border-color: var(--brand-orange); }
.section-divider { margin: 10px 0 !important; }

/* ── Traffic Analysis (ECG) ── */
.chart-container {
  height: 280px;
  position: relative;
}
.ecg-chart {
  height: 100%;
  width: 100%;
}
.live-dot-wrapper { display: flex; align-items: center; gap: 5px; font-family: var(--font-mono); font-size: var(--text-2xs); letter-spacing: 1.5px; color: #22c55e; }
.live-dot { width: 6px; height: 6px; border-radius: 50%; background: #22c55e; box-shadow: 0 0 6px #22c55e; animation: pulse-dot 1.4s ease-in-out infinite; }
@keyframes pulse-dot { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.5; transform: scale(0.8); } }
.ecg-legend { display: flex; flex-wrap: wrap; gap: 14px; margin-top: 8px; }
.ecg-legend-item {
  display: flex; align-items: center; gap: 5px;
  font-family: var(--font-mono); font-size: var(--text-2xs);
  color: var(--p-text-muted-color); letter-spacing: 1px;
  cursor: pointer; user-select: none; transition: opacity 0.2s;
}
.ecg-legend-item:hover { opacity: 0.7; }
.ecg-legend-item::before { content: ''; display: inline-block; width: 14px; height: 2px; background: var(--c); box-shadow: 0 0 5px var(--c); border-radius: 1px; }
.legend-hidden { opacity: 0.25; }

/* ── Two-column grid ── */
.two-col-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 800px) { .two-col-grid { grid-template-columns: 1fr; } }

/* ── Connection summary ── */
.conn-summary { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; min-height: 40px; }
.conn-state-item { display: flex; align-items: center; gap: 6px; }
.state-tag { font-family: var(--font-mono); font-size: 11px; }
.state-count { font-family: var(--font-mono); font-size: var(--text-sm); font-weight: 700; color: var(--p-text-color); }

/* ── Device detection ── */
.device-list { display: flex; flex-direction: column; gap: 6px; }
.device-row { display: flex; align-items: center; gap: 10px; padding: 7px 10px; border-radius: 6px; background: var(--p-surface-hover); }
.device-icon-wrap { width: 28px; height: 28px; background: color-mix(in srgb, var(--brand-orange) 10%, transparent); border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.device-icon { font-size: 12px; color: var(--brand-orange); }
.device-info { flex: 1; display: flex; flex-direction: column; gap: 2px; }
.device-ip { font-family: var(--font-mono); font-size: var(--text-sm); color: var(--p-text-color); font-weight: 600; }
.device-mac { font-family: var(--font-mono); font-size: var(--text-2xs); color: var(--p-text-muted-color); }
.device-iface-tag { font-family: var(--font-mono); font-size: 10px; }

/* ── History CTA ── */
.history-cta {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 16px; border-radius: 8px;
  border: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
  text-decoration: none; color: var(--p-text-muted-color);
  font-family: var(--font-mono); font-size: var(--text-xs); letter-spacing: 0.5px;
  transition: border-color 0.15s, color 0.15s, background 0.15s; cursor: pointer;
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

/* ── Connections table ── */
.conn-search { width: 180px; }
.status-select { width: 140px; }
.proto-select { width: 100px; }
:deep(.conn-table .p-datatable-thead th) { padding: 6px 10px; background: transparent; }
:deep(.conn-table .p-datatable-column-header-content) {
  font-family: var(--font-mono); font-size: var(--text-2xs);
  letter-spacing: 1.5px; color: var(--p-text-muted-color);
  text-transform: uppercase; font-weight: 600;
}
:deep(.conn-table .p-datatable-tbody td) { padding: 5px 10px; }
.cell-mono { font-family: var(--font-mono); font-size: var(--text-sm); }
.cell-empty { color: var(--p-text-muted-color); font-size: var(--text-sm); font-family: var(--font-mono); }
.remote-external { color: #f97316; font-family: var(--font-mono); font-size: var(--text-sm); }

/* ── Configuration ── */
.config-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
@media (max-width: 900px) { .config-grid { grid-template-columns: 1fr 1fr; } }
@media (max-width: 600px) { .config-grid { grid-template-columns: 1fr; } }
.config-section { display: flex; flex-direction: column; gap: 8px; }
.config-section-label { font-family: var(--font-mono); font-size: var(--text-2xs); letter-spacing: 1.5px; color: var(--p-text-muted-color); text-transform: uppercase; border-bottom: 1px solid var(--p-surface-border); padding-bottom: 5px; margin-bottom: 2px; }
.config-items { display: flex; flex-direction: column; gap: 5px; }
.config-item { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.config-key { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-muted-color); }
.config-val { font-family: var(--font-mono); font-size: var(--text-sm); color: var(--p-text-color); font-weight: 500; }

/* Internet gateway badge */
.iface-badges { display: flex; align-items: center; gap: 6px; margin-top: 5px; flex-wrap: wrap; }
.iface-badge-internet { font-family: var(--font-mono); font-size: 10px; }
.iface-subnet { font-family: var(--font-mono); font-size: var(--text-2xs); color: var(--p-text-muted-color); }

/* Chart controls */
.chart-controls { display: flex; align-items: center; gap: 8px; margin-left: auto; }
:deep(.window-select .p-select-label) { padding: 4px 8px; font-size: var(--text-xs); font-family: var(--font-mono); }

/* Local toggle */
:deep(.local-toggle) { font-family: var(--font-mono); font-size: var(--text-2xs) !important; }
:deep(.local-toggle .p-button-label) { font-size: var(--text-2xs); }
</style>
