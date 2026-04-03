<template>
  <div class="network-view">

    <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>

    <!-- ── Live Interface Cards ── -->
    <div class="iface-grid">
      <Card v-for="iface in interfaces" :key="iface.name" class="iface-card" :class="{ 'iface-down': !iface.is_up }">
        <template #content>
          <div class="iface-header">
            <span class="iface-name">{{ iface.name }}</span>
            <Tag :value="iface.is_up ? 'UP' : 'DOWN'" :severity="iface.is_up ? 'success' : 'danger'" class="iface-tag" />
          </div>
          <div class="iface-ip">{{ iface.ip || 'No IP' }}</div>
          <div class="iface-mac">{{ iface.mac || '—' }}</div>
          <Divider class="iface-divider" />
          <div class="iface-stats">
            <div class="stat-row">
              <span class="stat-label">↑ SENT</span>
              <span class="stat-val">{{ formatBytes(iface.bytes_sent) }}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">↓ RECV</span>
              <span class="stat-val">{{ formatBytes(iface.bytes_recv) }}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">SPEED</span>
              <span class="stat-val">{{ iface.speed_mbps ? `${iface.speed_mbps} Mbps` : '—' }}</span>
            </div>
            <div class="stat-row" v-if="iface.errin + iface.errout + iface.dropin + iface.dropout > 0">
              <span class="stat-label error-label">⚠ ERRORS</span>
              <span class="stat-val error-val">
                err {{ iface.errin + iface.errout }} / drop {{ iface.dropin + iface.dropout }}
              </span>
            </div>
          </div>
          <!-- live bps from WS -->
          <div class="bps-row" v-if="liveBps[iface.name]">
            <span class="bps-item bps-up">↑ {{ formatBps(liveBps[iface.name].sent_bps) }}/s</span>
            <span class="bps-item bps-down">↓ {{ formatBps(liveBps[iface.name].recv_bps) }}/s</span>
          </div>
        </template>
      </Card>
    </div>

    <!-- ── Bandwidth History Chart ── -->
    <Card class="net-card">
      <template #content>
        <div class="card-section-header">
          <i class="pi pi-chart-line section-icon" />
          <span class="section-title">BANDWIDTH HISTORY</span>
          <div class="header-controls">
            <Select v-model="selectedIface" :options="ifaceOptions" placeholder="All interfaces"
              :show-clear="true" class="iface-select" />
            <Select v-model="historyHours" :options="hourOptions" class="hours-select" />
          </div>
        </div>
        <Divider class="section-divider" />
        <div class="chart-container">
          <Line v-if="bandwidthChartData.labels.length > 0"
            :data="bandwidthChartData" :options="bandwidthChartOptions" />
          <div v-else class="empty-chart">
            <i class="pi pi-chart-line empty-icon" />
            <span>No bandwidth history yet — sampling every 60s</span>
          </div>
        </div>
      </template>
    </Card>

    <!-- ── Connection State Summary ── -->
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
            <Tag :value="state" :severity="stateColor(state)" class="state-tag" />
            <span class="state-count">{{ count }}</span>
          </div>
          <span v-if="Object.keys(connSummary).length === 0" class="cell-empty">No connections</span>
        </div>
      </template>
    </Card>

    <!-- ── Active Connections Table ── -->
    <Card class="net-card">
      <template #content>
        <div class="card-section-header">
          <i class="pi pi-arrows-h section-icon" />
          <span class="section-title">ACTIVE CONNECTIONS</span>
          <div class="header-controls">
            <InputText v-model="connSearch" placeholder="Filter address..." class="conn-search" size="small" />
            <Select v-model="connStatusFilter" :options="statusOptions" placeholder="All states"
              :show-clear="true" class="status-select" />
            <Select v-model="connProtoFilter" :options="['TCP','UDP']" placeholder="All proto"
              :show-clear="true" class="proto-select" />
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
              <Tag :value="data.proto" :severity="data.proto === 'TCP' ? 'info' : 'secondary'" />
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
              <Tag :value="data.status" :severity="stateColor(data.status)" />
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

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import Message from 'primevue/message'
import Card from 'primevue/card'
import Divider from 'primevue/divider'
import Tag from 'primevue/tag'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Select from 'primevue/select'
import InputText from 'primevue/inputtext'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  LineElement,
  PointElement,
  LinearScale,
  CategoryScale,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'
import { usePolling } from '../composables/usePolling.js'
import api from '../api/client.js'

ChartJS.register(LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Legend, Filler)

// ── State ──
const error = ref('')
const interfaces = ref([])
const connections = ref([])
const connSummary = ref({})
const bandwidthHistory = ref([])
const liveBps = ref({})   // { iface: { sent_bps, recv_bps } }
const historyHours = ref(24)
const selectedIface = ref(null)
const connSearch = ref('')
const connStatusFilter = ref(null)
const connProtoFilter = ref(null)
const hourOptions = [1, 6, 12, 24, 72, 168, 720]

// ── WebSocket for live bandwidth ──
let ws = null
let prevIfaceSnapshot = {}

function connectWs() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const token = localStorage.getItem('access_token') || ''
  ws = new WebSocket(`${proto}://${location.host}/api/ws/network?token=${token}`)

  ws.onmessage = (evt) => {
    try {
      const data = JSON.parse(evt.data)
      // data: { interfaces: [...], bps: { eth0: { sent_bps, recv_bps } } }
      if (data.interfaces) interfaces.value = data.interfaces
      if (data.bps) liveBps.value = data.bps
      error.value = ''
    } catch { /* ignore parse errors */ }
  }

  ws.onerror = () => { error.value = 'Live connection error — retrying...' }
  ws.onclose = () => {
    // Reconnect after 5s if not intentionally closed
    if (ws) setTimeout(connectWs, 5000)
  }
}

function disconnectWs() {
  if (ws) {
    const old = ws
    ws = null
    old.close()
  }
}

// ── REST fetches (less frequent) ──
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

async function fetchBandwidth() {
  try {
    const params = { hours: historyHours.value }
    if (selectedIface.value) params.interface = selectedIface.value
    const { data } = await api.get('/network/bandwidth', { params })
    bandwidthHistory.value = data
  } catch { /* non-critical */ }
}

// Fallback polling for interfaces if WS not available
async function fetchInterfaces() {
  try {
    const { data } = await api.get('/network/interfaces')
    interfaces.value = data
    error.value = ''
  } catch { error.value = 'Failed to fetch network interfaces' }
}

watch(historyHours, fetchBandwidth)
watch(selectedIface, fetchBandwidth)

// ── Computed ──
const ifaceOptions = computed(() => interfaces.value.map(i => i.name))

const totalConnections = computed(() =>
  Object.values(connSummary.value).reduce((a, b) => a + b, 0)
)

const statusOptions = computed(() => Object.keys(connSummary.value))

const filteredConnections = computed(() => {
  let list = connections.value
  if (connStatusFilter.value) list = list.filter(c => c.status === connStatusFilter.value)
  if (connProtoFilter.value) list = list.filter(c => c.proto === connProtoFilter.value)
  if (connSearch.value) {
    const q = connSearch.value.toLowerCase()
    list = list.filter(c =>
      c.local_addr.includes(q) || c.remote_addr.includes(q)
    )
  }
  return list
})

const bandwidthChartData = computed(() => {
  // Group by interface for multi-line chart
  const ifaceSet = [...new Set(bandwidthHistory.value.map(p => p.interface))]
  const colors = ['#f97316', '#3b82f6', '#10b981', '#8b5cf6', '#ec4899']

  const labels = [...new Set(bandwidthHistory.value.map(p =>
    new Date(p.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  ))]

  const datasets = []
  ifaceSet.forEach((iface, idx) => {
    const color = colors[idx % colors.length]
    const pts = bandwidthHistory.value.filter(p => p.interface === iface)
    datasets.push({
      label: `${iface} ↓`,
      data: pts.map(p => +(p.bytes_recv / 1024 / 1024).toFixed(3)),
      borderColor: color,
      backgroundColor: color + '18',
      fill: true,
      tension: 0.3,
      pointRadius: 0,
    })
  })

  return { labels, datasets }
})

const bandwidthChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: { position: 'top' },
    tooltip: {
      callbacks: {
        label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(2)} MB`,
      },
    },
  },
  scales: {
    y: {
      beginAtZero: true,
      ticks: { callback: v => `${v} MB` },
    },
  },
}

// ── Helpers ──
function formatBytes(b) {
  if (b >= 1e12) return `${(b / 1e12).toFixed(2)} TB`
  if (b >= 1e9) return `${(b / 1e9).toFixed(2)} GB`
  if (b >= 1e6) return `${(b / 1e6).toFixed(2)} MB`
  if (b >= 1e3) return `${(b / 1e3).toFixed(1)} KB`
  return `${b} B`
}

function formatBps(bps) {
  if (!bps) return '0 B'
  return formatBytes(bps)
}

function isExternal(addr) {
  if (!addr) return false
  const ip = addr.split(':')[0]
  return !ip.startsWith('127.') && !ip.startsWith('10.') &&
    !ip.startsWith('192.168.') && !ip.startsWith('172.') && ip !== ''
}

function stateColor(state) {
  const map = {
    ESTABLISHED: 'success',
    LISTEN: 'info',
    TIME_WAIT: 'warn',
    CLOSE_WAIT: 'warn',
    SYN_SENT: 'secondary',
    FIN_WAIT1: 'secondary',
    FIN_WAIT2: 'secondary',
    CLOSED: 'secondary',
    NONE: 'secondary',
  }
  return map[state] ?? 'secondary'
}

// ── Polling for connections + summary (10s) ──
const { start: startConns, stop: stopConns } = usePolling(() => {
  fetchConnections()
  fetchConnSummary()
}, 10000)

// ── Polling for bandwidth history (60s) ──
const { start: startBw, stop: stopBw } = usePolling(fetchBandwidth, 60000)

// ── Fallback polling for interfaces if WS fails (10s) ──
const { start: startIface, stop: stopIface } = usePolling(fetchInterfaces, 10000)

onMounted(() => {
  fetchInterfaces()
  fetchConnections()
  fetchConnSummary()
  fetchBandwidth()
  connectWs()
  startConns()
  startBw()
})

onUnmounted(() => {
  stopConns()
  stopBw()
  stopIface()
  disconnectWs()
})
</script>

<style scoped>
.network-view { display: flex; flex-direction: column; gap: 16px; }

/* Interface cards grid */
.iface-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}
:deep(.iface-card .p-card-body) { padding: 0; }
:deep(.iface-card .p-card-content) { padding: 12px 14px; }
.iface-card { transition: box-shadow 0.2s; }
.iface-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.15); }
.iface-down { opacity: 0.55; }
.iface-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }
.iface-name { font-family: var(--font-mono); font-size: var(--text-base); font-weight: 700; color: var(--brand-orange); }
.iface-ip { font-family: var(--font-mono); font-size: var(--text-sm); color: var(--p-text-color); }
.iface-mac { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-muted-color); margin-top: 2px; }
.iface-divider { margin: 8px 0 !important; }
.iface-stats { display: flex; flex-direction: column; gap: 4px; }
.stat-row { display: flex; justify-content: space-between; align-items: center; }
.stat-label { font-family: var(--font-mono); font-size: var(--text-2xs); letter-spacing: 1px; color: var(--p-text-muted-color); }
.stat-val { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-color); }
.error-label { color: var(--p-red-400); }
.error-val { color: var(--p-red-400); }
.bps-row { display: flex; gap: 10px; margin-top: 8px; padding-top: 6px; border-top: 1px solid var(--p-surface-border); }
.bps-item { font-family: var(--font-mono); font-size: var(--text-xs); }
.bps-up { color: var(--p-orange-400); }
.bps-down { color: var(--p-blue-400); }

/* General card layout */
:deep(.net-card .p-card-body) { padding: 0; }
:deep(.net-card .p-card-content) { padding: 14px 16px; }
.card-section-header { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.section-icon { font-size: 12px; color: var(--brand-orange); flex-shrink: 0; }
.section-title { font-family: var(--font-mono); font-size: var(--text-2xs); letter-spacing: 2px; text-transform: uppercase; color: var(--p-text-muted-color); flex: 1; }
.section-extra { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-muted-color); }
.header-controls { display: flex; gap: 8px; align-items: center; }
.section-divider { margin: 10px 0 !important; }

/* Bandwidth chart */
.chart-container { height: 280px; position: relative; }
.empty-chart { height: 200px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; color: var(--p-text-muted-color); }
.empty-icon { font-size: 2rem; opacity: 0.3; }
.iface-select { width: 140px; }
.hours-select { width: 90px; }

/* Connection summary */
.conn-summary { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.conn-state-item { display: flex; align-items: center; gap: 6px; }
.state-tag { font-family: var(--font-mono); font-size: 11px; }
.state-count { font-family: var(--font-mono); font-size: var(--text-sm); font-weight: 700; color: var(--p-text-color); }

/* Connections table */
.conn-search { width: 200px; }
.status-select { width: 140px; }
.proto-select { width: 100px; }
.cell-mono { font-family: var(--font-mono); font-size: var(--text-sm); }
.cell-empty { color: var(--p-text-muted-color); font-size: var(--text-sm); }
.remote-external { color: var(--p-orange-400); font-family: var(--font-mono); font-size: var(--text-sm); }
</style>
