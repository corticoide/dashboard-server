<template>
  <div class="services-view">

    <!-- Summary bar -->
    <div class="summary-bar">
      <button class="summary-pill pill-active" :class="{ active: stateFilter === 'active' }" @click="stateFilter = stateFilter === 'active' ? 'all' : 'active'">
        <span class="pill-dot dot-active"></span>
        <span class="pill-count">{{ counts.active }}</span>
        <span class="pill-label">ACTIVE</span>
      </button>
      <button class="summary-pill pill-failed" :class="{ active: stateFilter === 'failed' }" @click="stateFilter = stateFilter === 'failed' ? 'all' : 'failed'">
        <span class="pill-dot dot-failed"></span>
        <span class="pill-count">{{ counts.failed }}</span>
        <span class="pill-label">FAILED</span>
      </button>
      <button class="summary-pill pill-inactive" :class="{ active: stateFilter === 'inactive' }" @click="stateFilter = stateFilter === 'inactive' ? 'all' : 'inactive'">
        <span class="pill-dot dot-inactive"></span>
        <span class="pill-count">{{ counts.inactive }}</span>
        <span class="pill-label">INACTIVE</span>
      </button>
      <span class="summary-total">{{ services.length }} total</span>
    </div>

    <!-- Toolbar -->
    <Toolbar class="services-toolbar">
      <template #start>
        <div class="toolbar-start">
          <IconField>
            <InputIcon class="pi pi-search" />
            <InputText v-model="filter" placeholder="Filter services…" size="small" />
          </IconField>
        </div>
      </template>
      <template #end>
        <div class="toolbar-end">
          <div class="sudo-field" v-tooltip.bottom="'Required for start/stop/restart'">
            <i class="pi pi-lock sudo-icon" />
            <Password
              v-model="sudoPassword"
              placeholder="sudo password"
              :feedback="false"
              toggle-mask
              size="small"
              fluid
            />
          </div>
          <Button
            icon="pi pi-refresh"
            rounded
            text
            size="small"
            :loading="loading"
            v-tooltip.bottom="'Refresh'"
            @click="loadServices"
          />
        </div>
      </template>
    </Toolbar>

    <Message v-if="error" severity="error" :closable="true" @close="error = ''">{{ error }}</Message>

    <DataTable
      :value="filtered"
      :loading="loading"
      v-model:expanded-rows="expandedRows"
      data-key="name"
      :row-class="rowClass"
      size="small"
      removableSort
      @row-expand="onRowExpand"
      class="services-table"
    >
      <template #empty>
        <div class="empty-state">
          <i class="pi pi-inbox empty-icon" />
          <span class="empty-text">No services match "{{ filter }}"</span>
        </div>
      </template>

      <Column expander style="width: 2.5rem" />

      <Column field="name" header="SERVICE" sortable style="min-width: 180px">
        <template #body="{ data }">
          <span class="svc-name">{{ data.name }}</span>
        </template>
      </Column>

      <Column field="active_state" header="STATE" sortable style="width: 120px">
        <template #body="{ data }">
          <div class="state-cell">
            <span class="state-dot" :class="`state-dot--${data.active_state}`"></span>
            <Tag :value="data.active_state" :severity="stateSeverity(data.active_state)" class="state-tag" />
          </div>
        </template>
      </Column>

      <Column field="sub_state" header="SUB" style="width: 100px">
        <template #body="{ data }">
          <span class="cell-sub">{{ data.sub_state }}</span>
        </template>
      </Column>

      <Column field="enabled" header="BOOT" style="width: 90px">
        <template #body="{ data }">
          <Badge
            :value="data.enabled"
            :severity="data.enabled === 'enabled' ? 'success' : 'secondary'"
          />
        </template>
      </Column>

      <Column field="description" header="DESCRIPTION" style="max-width: 240px">
        <template #body="{ data }">
          <span class="cell-desc">{{ data.description }}</span>
        </template>
      </Column>

      <Column header="ACTIONS" style="width: 200px">
        <template #body="{ data }">
          <div class="action-group">
            <Button
              label="Start"
              size="small"
              severity="success"
              outlined
              :loading="actionLoading[data.name] === 'start'"
              :disabled="!!actionLoading[data.name] || isRunning(data)"
              @click="runAction(data.name, 'start')"
              class="action-btn"
            />
            <Button
              label="Stop"
              size="small"
              severity="warning"
              outlined
              :loading="actionLoading[data.name] === 'stop'"
              :disabled="!!actionLoading[data.name] || !isRunning(data)"
              @click="runAction(data.name, 'stop')"
              class="action-btn"
            />
            <Button
              label="Restart"
              size="small"
              severity="secondary"
              outlined
              :loading="actionLoading[data.name] === 'restart'"
              :disabled="!!actionLoading[data.name] || !isRunning(data)"
              @click="runAction(data.name, 'restart')"
              class="action-btn"
            />
          </div>
        </template>
      </Column>

      <template #expansion="slotProps">
        <div class="log-panel">
          <div class="log-panel-header">
            <div class="log-panel-title">
              <i class="pi pi-terminal" />
              <span class="log-svc-name">{{ slotProps.data.name }}</span>
              <span class="log-source">journald</span>
            </div>
            <Button icon="pi pi-times" text rounded size="small" @click="collapseRow(slotProps.data.name)" />
          </div>
          <ScrollPanel class="log-scroll">
            <pre class="log-content">{{ (logsByService[slotProps.data.name] || ['Loading…']).join('\n') }}</pre>
          </ScrollPanel>
        </div>
      </template>
    </DataTable>

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import Toolbar from 'primevue/toolbar'
import IconField from 'primevue/iconfield'
import InputIcon from 'primevue/inputicon'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Button from 'primevue/button'
import Message from 'primevue/message'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import Badge from 'primevue/badge'
import ScrollPanel from 'primevue/scrollpanel'
import api from '../api/client.js'

const toast = useToast()

const services    = ref([])
const loading     = ref(false)
const error       = ref('')
const filter      = ref('')
const stateFilter = ref('all')
const expandedRows   = ref({})
const logsByService  = ref({})
const actionLoading  = ref({})
const sudoPassword   = ref('')

function isRunning(svc) {
  return ['active', 'activating', 'reloading'].includes(svc.active_state)
}

function stateSeverity(state) {
  return { active: 'success', failed: 'danger', activating: 'warn', inactive: 'secondary', deactivating: 'contrast' }[state] || 'secondary'
}

function rowClass(data) {
  if (data.active_state === 'failed')   return 'row-failed'
  if (data.active_state === 'inactive') return 'row-inactive'
  return ''
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

async function loadServices() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get('/services/')
    services.value = data
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load services'
  } finally {
    loading.value = false
  }
}

async function onRowExpand(event) {
  const name = event.data.name
  if (!logsByService.value[name]) {
    try {
      const { data } = await api.get(`/services/${name}/logs?lines=80`)
      logsByService.value[name] = data.lines
    } catch {
      logsByService.value[name] = ['Failed to load logs']
    }
  }
}

function collapseRow(name) {
  const updated = { ...expandedRows.value }
  delete updated[name]
  expandedRows.value = updated
}

async function runAction(name, action) {
  actionLoading.value[name] = action
  error.value = ''
  try {
    await api.post(`/services/${name}/${action}`, { sudo_password: sudoPassword.value || null })
    const { data } = await api.get('/services/')
    services.value = data
    delete logsByService.value[name]
    if (expandedRows.value[name]) {
      const logResp = await api.get(`/services/${name}/logs?lines=80`)
      logsByService.value[name] = logResp.data.lines
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
.services-view { display: flex; flex-direction: column; gap: 12px; }

/* ── Summary bar ─────────────────────────────── */
.summary-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.summary-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 20px;
  border: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
  font-family: var(--font-mono);
}
.summary-pill:hover { background: var(--p-surface-hover); }

.pill-active.active  { border-color: var(--p-green-500);  background: color-mix(in srgb, var(--p-green-500) 10%, transparent); }
.pill-failed.active  { border-color: var(--p-red-500);    background: color-mix(in srgb, var(--p-red-500)   10%, transparent); }
.pill-inactive.active{ border-color: var(--p-surface-500);background: var(--p-surface-hover); }

.pill-dot {
  width: 7px; height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dot-active  { background: var(--p-green-500); animation: pulse-dot 2s ease-in-out infinite; }
.dot-failed  { background: var(--p-red-500); }
.dot-inactive{ background: var(--p-surface-400); }

@keyframes pulse-dot {
  0%, 100% { opacity: 1; box-shadow: 0 0 0 0 color-mix(in srgb, var(--p-green-500) 50%, transparent); }
  50%       { opacity: 0.8; box-shadow: 0 0 0 4px transparent; }
}

.pill-count {
  font-size: var(--text-base);
  font-weight: 700;
  color: var(--p-text-color);
  line-height: 1;
}
.pill-label {
  font-size: var(--text-2xs);
  letter-spacing: 1.5px;
  color: var(--p-text-muted-color);
}
.summary-total {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--p-text-muted-color);
  margin-left: 4px;
}

/* ── Toolbar ─────────────────────────────────── */
.services-toolbar { flex-wrap: wrap; gap: 8px; }
.toolbar-start { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.toolbar-end   { display: flex; align-items: center; gap: 8px; }

.sudo-field {
  display: flex;
  align-items: center;
  gap: 6px;
}
.sudo-icon {
  font-size: 12px;
  color: var(--p-text-muted-color);
}
:deep(.sudo-field .p-password) {
  display: flex;
  width: 140px;
}
:deep(.sudo-field .p-password-input) {
  flex: 1;
  min-width: 0;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
}

/* ── Table cells ─────────────────────────────── */
.svc-name {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--p-text-color);
}

.state-cell {
  display: flex;
  align-items: center;
  gap: 7px;
}
.state-dot {
  width: 7px; height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}
.state-dot--active      { background: var(--p-green-500); animation: pulse-dot 2s ease-in-out infinite; }
.state-dot--failed      { background: var(--p-red-500); }
.state-dot--activating  { background: var(--p-orange-400); animation: pulse-dot 1s ease-in-out infinite; }
.state-dot--deactivating{ background: var(--p-orange-400); }
.state-dot--inactive    { background: var(--p-surface-400); }
.state-tag { font-size: var(--text-xs) !important; }

.cell-sub {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--p-text-muted-color);
}
.cell-desc {
  font-size: var(--text-sm);
  color: var(--p-text-muted-color);
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 240px;
}

/* ── Action buttons ──────────────────────────── */
.action-group {
  display: flex;
  gap: 4px;
}
.action-btn {
  font-size: var(--text-xs) !important;
  padding: 4px 8px !important;
  font-family: var(--font-mono) !important;
  letter-spacing: 0.5px;
}

/* ── Row states ──────────────────────────────── */
:deep(.row-failed td) {
  background: color-mix(in srgb, var(--p-red-500) 5%, transparent) !important;
}
:deep(.row-inactive td) {
  opacity: 0.65;
}

/* ── Empty state ─────────────────────────────── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 32px 0;
  color: var(--p-text-muted-color);
}
.empty-icon { font-size: 28px; opacity: 0.4; }
.empty-text { font-size: var(--text-sm); font-family: var(--font-mono); }

/* ── Log expansion panel ─────────────────────── */
.log-panel {
  border-top: 1px solid var(--p-surface-border);
  background: var(--p-surface-900);
}
.log-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px 6px;
  border-bottom: 1px solid color-mix(in srgb, var(--brand-orange) 25%, transparent);
}
.log-panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--brand-orange);
  font-size: 13px;
}
.log-svc-name {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--brand-orange);
}
.log-source {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 1.5px;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
}
.log-scroll { height: 280px; }
.log-content {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  line-height: 1.7;
  margin: 0;
  padding: 10px 16px 12px;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--p-text-muted-color);
}

/* ── DataTable header normalization ──────────── */
:deep(.services-table .p-datatable-thead th) {
  background: transparent;
}
:deep(.services-table .p-datatable-column-header-content) {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 1.5px;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
  font-weight: 600;
}
</style>
