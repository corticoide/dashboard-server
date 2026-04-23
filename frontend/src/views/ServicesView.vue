<template>
  <div class="services-view">
    <Message v-if="error" severity="error" :closable="true" @close="error = ''">{{ error }}</Message>

    <Splitter class="services-splitter">

      <!-- ── Left: unit list ──────────────────────────────────────── -->
      <SplitterPanel :size="32" :minSize="22">
        <div class="list-panel">

          <div class="panel-header">
            <i class="pi pi-cog header-icon" />
            <span class="header-label">systemctl list-units</span>
            <span class="header-count">{{ filtered.length }}</span>
            <Button icon="pi pi-refresh" text rounded size="small" :loading="loading" @click="loadServices" />
          </div>

          <div class="search-bar">
            <IconField>
              <InputIcon class="pi pi-search" />
              <InputText v-model="filter" placeholder="Filter units…" size="small" fluid />
            </IconField>
          </div>

          <div class="state-pills">
            <button class="state-pill" :class="{ active: stateFilter === 'all' }" @click="stateFilter = 'all'">
              ALL<span class="pill-n">{{ services.length }}</span>
            </button>
            <button class="state-pill pill-green" :class="{ active: stateFilter === 'active' }" @click="stateFilter = stateFilter === 'active' ? 'all' : 'active'">
              ACTIVE<span class="pill-n">{{ counts.active }}</span>
            </button>
            <button class="state-pill pill-red" :class="{ active: stateFilter === 'failed' }" @click="stateFilter = stateFilter === 'failed' ? 'all' : 'failed'">
              FAILED<span class="pill-n">{{ counts.failed }}</span>
            </button>
          </div>

          <div class="col-headers">
            <span class="ch-dot"></span>
            <span class="ch-unit">UNIT</span>
            <span class="ch-sub">SUB</span>
            <span class="ch-boot">BOOT</span>
          </div>

          <div class="panel-scroll">
            <div v-if="!filtered.length" class="empty-state">
              <i class="pi pi-inbox empty-icon" />
              <span class="empty-text">No units{{ filter ? ` matching "${filter}"` : '' }}</span>
            </div>
            <div
              v-for="svc in filtered" :key="svc.name"
              class="unit-row"
              :class="{
                'unit-row--selected': selectedService?.name === svc.name,
                'unit-row--failed':   svc.active_state === 'failed',
                'unit-row--inactive': svc.active_state === 'inactive',
              }"
              @click="selectService(svc)"
            >
              <span class="unit-dot" :class="`unit-dot--${svc.active_state}`" />
              <span class="unit-name">{{ svc.name }}</span>
              <span class="unit-sub">{{ svc.sub_state }}</span>
              <span class="unit-boot">{{ svc.enabled }}</span>
            </div>
          </div>

        </div>
      </SplitterPanel>

      <!-- ── Right: status + logs ─────────────────────────────────── -->
      <SplitterPanel :size="68">

        <div v-if="!selectedService" class="empty-detail">
          <i class="pi pi-cog empty-icon" />
          <span class="empty-text">Select a unit to inspect</span>
        </div>

        <div v-else class="detail-panel">

          <!-- Action bar -->
          <div class="action-bar">
            <div class="sudo-wrap" v-tooltip.bottom="'Required for start / stop / restart'">
              <i class="pi pi-lock sudo-icon" />
              <Password v-model="sudoPassword" placeholder="sudo password" :feedback="false" toggle-mask size="small" />
            </div>
            <Button label="Start" size="small" severity="success" outlined
              :loading="actionLoading[selectedService.name] === 'start'"
              :disabled="!!actionLoading[selectedService.name] || isRunning(selectedService)"
              @click="runAction(selectedService.name, 'start')" />
            <Button label="Stop" size="small" severity="warn" outlined
              :loading="actionLoading[selectedService.name] === 'stop'"
              :disabled="!!actionLoading[selectedService.name] || !isRunning(selectedService)"
              @click="runAction(selectedService.name, 'stop')" />
            <Button label="Restart" size="small" severity="secondary" outlined
              :loading="actionLoading[selectedService.name] === 'restart'"
              :disabled="!!actionLoading[selectedService.name] || !isRunning(selectedService)"
              @click="runAction(selectedService.name, 'restart')" />
          </div>

          <!-- systemctl status block -->
          <div class="status-block">
            <div class="status-title-line">
              <span class="status-dot" :class="`status-dot--${selectedService.active_state}`" />
              <span class="status-svc-name">{{ selectedService.name }}</span>
              <span v-if="selectedService.description" class="status-desc">- {{ selectedService.description }}</span>
            </div>
            <div class="status-kv">
              <div class="kv-row">
                <span class="kv-key">   Loaded</span>
                <span class="kv-val">loaded ({{ selectedService.enabled }})</span>
              </div>
              <div class="kv-row">
                <span class="kv-key">   Active</span>
                <span class="kv-val" :class="`kv-active--${selectedService.active_state}`">
                  {{ selectedService.active_state }} ({{ selectedService.sub_state }})
                </span>
              </div>
            </div>
          </div>

          <!-- log section -->
          <div class="log-section">
            <div class="log-header">
              <i class="pi pi-terminal log-icon" />
              <span class="log-label">journalctl -u {{ selectedService.name }} -n 80</span>
              <Button icon="pi pi-refresh" text rounded size="small" :loading="logsLoading" @click="loadLogs(selectedService.name)" />
            </div>
            <pre class="log-output">{{ logLines }}</pre>
          </div>

        </div>

      </SplitterPanel>

    </Splitter>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import Splitter from 'primevue/splitter'
import SplitterPanel from 'primevue/splitterpanel'
import IconField from 'primevue/iconfield'
import InputIcon from 'primevue/inputicon'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Button from 'primevue/button'
import Message from 'primevue/message'
import api from '../api/client.js'

const toast = useToast()

const services      = ref([])
const loading       = ref(false)
const error         = ref('')
const filter        = ref('')
const stateFilter   = ref('all')
const actionLoading = ref({})
const sudoPassword  = ref('')

const selectedService = ref(null)
const logsByService   = ref({})
const logsLoading     = ref(false)

function isRunning(svc) {
  return ['active', 'activating', 'reloading'].includes(svc.active_state)
}

const counts = computed(() => ({
  active:   services.value.filter(s => s.active_state === 'active').length,
  failed:   services.value.filter(s => s.active_state === 'failed').length,
  inactive: services.value.filter(s => s.active_state === 'inactive').length,
}))

const filtered = computed(() => services.value.filter(s => {
  const matchesText  = filter.value === '' ||
    s.name.toLowerCase().includes(filter.value.toLowerCase()) ||
    s.description.toLowerCase().includes(filter.value.toLowerCase())
  const matchesState = stateFilter.value === 'all' || s.active_state === stateFilter.value
  return matchesText && matchesState
}))

const logLines = computed(() => {
  if (!selectedService.value) return ''
  const lines = logsByService.value[selectedService.value.name]
  if (!lines) return 'Loading…'
  return lines.join('\n')
})

async function loadServices() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get('/services/')
    services.value = data
    if (selectedService.value) {
      selectedService.value = data.find(s => s.name === selectedService.value.name) || selectedService.value
    }
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load services'
  } finally {
    loading.value = false
  }
}

async function selectService(svc) {
  selectedService.value = svc
  if (!logsByService.value[svc.name]) {
    await loadLogs(svc.name)
  }
}

async function loadLogs(name) {
  logsLoading.value = true
  try {
    const { data } = await api.get(`/services/${name}/logs?lines=80`)
    logsByService.value[name] = data.lines
  } catch {
    logsByService.value[name] = ['Failed to load logs']
  } finally {
    logsLoading.value = false
  }
}

async function runAction(name, action) {
  actionLoading.value[name] = action
  error.value = ''
  try {
    await api.post(`/services/${name}/${action}`, { sudo_password: sudoPassword.value || null })
    const { data } = await api.get('/services/')
    services.value = data
    delete logsByService.value[name]
    if (selectedService.value?.name === name) {
      selectedService.value = data.find(s => s.name === name) || selectedService.value
      await loadLogs(name)
    }
    toast.add({ severity: 'success', summary: 'Done', detail: `${action} → ${name}`, life: 3000 })
  } catch (e) {
    const msg = e.response?.data?.detail || `Failed to ${action} ${name}`
    toast.add({ severity: 'error', summary: 'Error', detail: msg, life: 5000 })
    if (e.response?.status === 500 && msg.toLowerCase().includes('password')) sudoPassword.value = ''
  } finally {
    delete actionLoading.value[name]
  }
}

onMounted(loadServices)
</script>

<style scoped>
.services-view {
  height: calc(100vh - var(--header-height) - 48px);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.services-splitter {
  flex: 1;
  min-height: 0;
  border-radius: 8px;
  overflow: hidden;
}

/* ── Left panel ─────────────────────────────── */
.list-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--p-surface-900);
  border-right: 1px solid var(--p-surface-border);
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 10px 12px 9px;
  border-bottom: 1px solid var(--p-surface-border);
  flex-shrink: 0;
}
.header-icon  { font-size: 12px; color: var(--brand-orange); }
.header-label {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--p-text-muted-color);
  flex: 1;
}
.header-count {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  font-weight: 600;
  color: var(--brand-orange);
  background: color-mix(in srgb, var(--brand-orange) 12%, transparent);
  border-radius: 4px;
  padding: 1px 6px;
  line-height: 1.6;
}

.search-bar {
  padding: 8px 10px;
  border-bottom: 1px solid var(--p-surface-border);
  flex-shrink: 0;
}
:deep(.search-bar .p-inputtext) {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  width: 100%;
}

.state-pills {
  display: flex;
  gap: 4px;
  padding: 6px 10px;
  border-bottom: 1px solid var(--p-surface-border);
  flex-shrink: 0;
}
.state-pill {
  display: flex;
  align-items: center;
  gap: 5px;
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 1px;
  padding: 2px 8px;
  border-radius: 3px;
  border: 1px solid transparent;
  background: none;
  color: var(--p-text-muted-color);
  cursor: pointer;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}
.state-pill:hover { background: var(--p-surface-hover); color: var(--p-text-color); }
.state-pill.active { color: var(--p-text-color); border-color: var(--p-surface-border); background: var(--p-surface-hover); }
.pill-green.active { color: var(--p-green-500); border-color: var(--p-green-500); background: color-mix(in srgb, var(--p-green-500) 10%, transparent); }
.pill-red.active   { color: var(--p-red-500);   border-color: var(--p-red-500);   background: color-mix(in srgb, var(--p-red-500)   10%, transparent); }
.pill-n { font-weight: 700; font-size: var(--text-xs); margin-left: 2px; }

/* column header row */
.col-headers {
  display: grid;
  grid-template-columns: 18px 1fr 70px 60px;
  gap: 8px;
  padding: 4px 12px;
  border-bottom: 1px solid var(--p-surface-border);
  flex-shrink: 0;
}
.ch-unit, .ch-sub, .ch-boot {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 1.5px;
  color: var(--p-surface-600);
  text-transform: uppercase;
}

.panel-scroll { flex: 1; overflow-y: auto; min-height: 0; }

/* ── Unit rows ──────────────────────────────── */
.unit-row {
  display: grid;
  grid-template-columns: 18px 1fr 70px 60px;
  gap: 8px;
  align-items: center;
  padding: 6px 12px;
  cursor: pointer;
  transition: background 0.12s;
  border-left: 2px solid transparent;
}
.unit-row:hover { background: color-mix(in srgb, var(--brand-orange) 6%, transparent); }
.unit-row--selected {
  background: color-mix(in srgb, var(--brand-orange) 12%, transparent);
  border-left-color: var(--brand-orange);
}
.unit-row--failed  { background: color-mix(in srgb, var(--p-red-500) 5%, transparent); }
.unit-row--inactive { opacity: 0.55; }

.unit-dot {
  width: 7px; height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
  margin: auto;
}
.unit-dot--active      { background: var(--p-green-500);  animation: pulse-dot 2s ease-in-out infinite; }
.unit-dot--failed      { background: var(--p-red-500); }
.unit-dot--activating  { background: var(--p-yellow-500); animation: pulse-dot 1s ease-in-out infinite; }
.unit-dot--deactivating{ background: var(--p-yellow-500); }
.unit-dot--inactive    { background: var(--p-surface-500); }

@keyframes pulse-dot {
  0%, 100% { opacity: 1; box-shadow: 0 0 0 0 color-mix(in srgb, var(--p-green-500) 50%, transparent); }
  50%       { opacity: 0.8; box-shadow: 0 0 0 4px transparent; }
}

.unit-name {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--p-text-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.unit-sub  { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-muted-color); }
.unit-boot { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-muted-color); }

/* ── Empty states ───────────────────────────── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 32px 16px;
  color: var(--p-text-muted-color);
}
.empty-icon { font-size: 28px; opacity: 0.4; }
.empty-text { font-family: var(--font-mono); font-size: var(--text-sm); text-align: center; }

.empty-detail {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--p-text-muted-color);
}

/* ── Right detail panel ─────────────────────── */
.detail-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--p-surface-900);
}

/* action bar */
.action-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--p-surface-border);
  background: var(--p-surface-800);
  flex-shrink: 0;
  flex-wrap: wrap;
}
.sudo-wrap { display: flex; align-items: center; gap: 6px; margin-right: 4px; }
.sudo-icon { font-size: var(--text-sm); color: var(--p-text-muted-color); }
:deep(.sudo-wrap .p-password) { display: flex; width: 140px; }
:deep(.sudo-wrap .p-password-input) { flex: 1; min-width: 0; font-family: var(--font-mono); font-size: var(--text-xs); }

/* systemctl status block */
.status-block {
  padding: 14px 16px 12px;
  border-bottom: 1px solid var(--p-surface-border);
  flex-shrink: 0;
}
.status-title-line {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.status-dot {
  width: 9px; height: 9px;
  border-radius: 50%;
  flex-shrink: 0;
}
.status-dot--active      { background: var(--p-green-500);  animation: pulse-dot 2s ease-in-out infinite; }
.status-dot--failed      { background: var(--p-red-500); }
.status-dot--activating  { background: var(--p-yellow-500); animation: pulse-dot 1s ease-in-out infinite; }
.status-dot--inactive    { background: var(--p-surface-500); }

.status-svc-name {
  font-family: var(--font-mono);
  font-size: var(--text-base);
  font-weight: 700;
  color: var(--p-text-color);
}
.status-desc {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--p-text-muted-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-kv { display: flex; flex-direction: column; gap: 2px; }
.kv-row    { display: flex; align-items: baseline; gap: 4px; }
.kv-key {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--p-text-muted-color);
  min-width: 80px;
}
.kv-val { font-family: var(--font-mono); font-size: var(--text-sm); color: var(--p-text-color); }
.kv-active--active      { color: var(--p-green-500); }
.kv-active--failed      { color: var(--p-red-500); }
.kv-active--activating  { color: var(--p-yellow-500); }
.kv-active--inactive    { color: var(--p-text-muted-color); }

/* log section */
.log-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.log-header {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 7px 12px 6px;
  border-bottom: 1px solid color-mix(in srgb, var(--brand-orange) 25%, transparent);
  flex-shrink: 0;
}
.log-icon  { font-size: 12px; color: var(--brand-orange); }
.log-label { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-muted-color); flex: 1; }

.log-output {
  flex: 1;
  overflow-y: auto;
  padding: 10px 16px 12px;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  line-height: 1.7;
  color: var(--p-text-muted-color);
  white-space: pre-wrap;
  word-break: break-all;
  background: var(--p-surface-900);
  margin: 0;
}
</style>
