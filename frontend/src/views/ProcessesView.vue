<template>
  <div class="processes-view">
    <div class="page-header">
      <div class="page-title">
        <i class="pi pi-server page-icon" />
        <span>PROCESSES</span>
        <Tag :value="`${processes.length} shown`" severity="secondary" />
        <Tag v-if="truncated" value="CAPPED AT 500" severity="warning" />
      </div>
      <div class="header-actions">
        <IconField>
          <InputIcon class="pi pi-search" />
          <InputText v-model="filterTerm" placeholder="Filter by name…" size="small" />
        </IconField>
      </div>
    </div>

    <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>

    <DataTable
      :value="filteredProcesses"
      size="small"
      class="proc-table"
      :loading="loading"
      scrollable
      scroll-height="flex"
    >
      <template #empty>No processes found.</template>

      <Column field="name" header="Name" sortable style="min-width: 160px">
        <template #body="{ data }">
          <span class="proc-name">{{ data.name }}</span>
          <Tag v-if="data.watched" value="WATCHED" severity="info" class="ml-2" />
        </template>
      </Column>
      <Column field="pid" header="PID" sortable style="width: 80px">
        <template #body="{ data }"><span class="cell-mono">{{ data.pid }}</span></template>
      </Column>
      <Column field="cpu_percent" header="CPU %" sortable style="width: 90px">
        <template #body="{ data }">
          <span :class="['cell-mono', { 'val-high': data.cpu_percent > 50 }]">
            {{ data.cpu_percent.toFixed(1) }}
          </span>
        </template>
      </Column>
      <Column field="memory_mb" header="RAM MB" sortable style="width: 90px">
        <template #body="{ data }"><span class="cell-mono">{{ data.memory_mb.toFixed(0) }}</span></template>
      </Column>
      <Column field="username" header="User" style="width: 110px">
        <template #body="{ data }"><span class="cell-mono">{{ data.username }}</span></template>
      </Column>
      <Column field="status" header="Status" style="width: 100px">
        <template #body="{ data }">
          <Tag :value="data.status" :severity="statusSeverity(data.status)" />
        </template>
      </Column>
      <Column header="Actions" style="width: 130px" v-if="canExecute">
        <template #body="{ data }">
          <div class="row-actions">
            <Button
              v-if="!data.watched"
              icon="pi pi-eye"
              size="small"
              text
              severity="info"
              v-tooltip.top="'Watch'"
              @click="openWatchDialog(data)"
            />
            <Button
              v-else
              icon="pi pi-eye-slash"
              size="small"
              text
              severity="secondary"
              v-tooltip.top="'Unwatch'"
              @click="unwatch(data)"
            />
            <Button
              icon="pi pi-times-circle"
              size="small"
              text
              severity="danger"
              v-tooltip.top="'Kill'"
              @click="killProcess(data)"
            />
          </div>
        </template>
      </Column>
    </DataTable>

    <!-- Watch dialog -->
    <Dialog v-model:visible="watchDialog" header="WATCH PROCESS" :modal="true" style="width: 380px">
      <div class="dialog-form">
        <div class="form-field">
          <label>Process</label>
          <InputText :value="watchTarget?.name" disabled size="small" />
        </div>
        <div class="form-field">
          <label>Alert email</label>
          <InputText v-model="watchForm.email_to" size="small" placeholder="you@example.com" />
        </div>
        <div class="form-field">
          <label>Cooldown (minutes)</label>
          <InputNumber v-model="watchForm.cooldown_minutes" :min="1" size="small" />
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" size="small" severity="secondary" @click="watchDialog = false" />
        <Button label="Watch" icon="pi pi-eye" size="small" :loading="watchSaving" @click="saveWatch" />
      </template>
    </Dialog>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useConfirm } from 'primevue/useconfirm'
import { useAuthStore } from '../stores/auth.js'
import { usePolling } from '../composables/usePolling.js'
import api from '../api/client.js'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import Message from 'primevue/message'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import IconField from 'primevue/iconfield'
import InputIcon from 'primevue/inputicon'

const MAX_DISPLAY = 500

const auth = useAuthStore()
const confirm = useConfirm()

const processes = ref([])
const loading = ref(false)
const truncated = ref(false)
const error = ref(null)
const filterTerm = ref('')

const watchDialog = ref(false)
const watchTarget = ref(null)
const watchSaving = ref(false)
const watchForm = ref({ email_to: '', cooldown_minutes: 60 })

const canExecute = computed(() => auth.hasPermission('processes', 'execute'))

const filteredProcesses = computed(() => {
  if (!filterTerm.value) return processes.value
  const term = filterTerm.value.toLowerCase()
  return processes.value.filter(p => p.name.toLowerCase().includes(term))
})

async function loadProcesses() {
  if (loading.value) return
  loading.value = true
  try {
    const r = await api.get('/processes/')
    processes.value = r.data.slice(0, MAX_DISPLAY)
    truncated.value = r.data.length >= MAX_DISPLAY
    error.value = null
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load processes'
  } finally {
    loading.value = false
  }
}

function statusSeverity(status) {
  return {
    running:  'success',
    sleeping: 'secondary',
    disk_sleep: 'warn',
    stopped:  'warn',
    zombie:   'danger',
  }[status] ?? 'secondary'
}

function openWatchDialog(proc) {
  watchTarget.value = proc
  watchForm.value = { email_to: '', cooldown_minutes: 60 }
  watchDialog.value = true
}

async function saveWatch() {
  watchSaving.value = true
  try {
    await api.post('/processes/watch', {
      name: watchTarget.value.name,
      email_to: watchForm.value.email_to,
      cooldown_minutes: watchForm.value.cooldown_minutes,
    })
    watchDialog.value = false
    await loadProcesses()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to watch process'
  } finally {
    watchSaving.value = false
  }
}

async function unwatch(proc) {
  try {
    await api.delete(`/processes/watch/${encodeURIComponent(proc.name)}`)
    await loadProcesses()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to unwatch process'
  }
}

function killProcess(proc) {
  confirm.require({
    message: `Kill process "${proc.name}" (PID ${proc.pid})?`,
    header: 'Confirm Kill',
    icon: 'pi pi-exclamation-triangle',
    acceptSeverity: 'danger',
    accept: async () => {
      try {
        await api.post(`/processes/${proc.pid}/kill`)
        await loadProcesses()
      } catch (e) {
        error.value = e.response?.data?.detail || 'Failed to kill process'
      }
    },
  })
}

const { start, stop } = usePolling(loadProcesses, 5000)

onMounted(() => {
  loadProcesses()
  start()
})

onUnmounted(stop)
</script>

<style scoped>
.processes-view { display: flex; flex-direction: column; height: 100%; gap: 12px; }
.page-header { display: flex; align-items: center; justify-content: space-between; }
.page-title { display: flex; align-items: center; gap: 10px; font-family: var(--font-mono); font-size: var(--text-sm); font-weight: 700; letter-spacing: 2px; color: var(--p-text-muted-color); }
.page-icon { color: var(--p-green-400); font-size: var(--text-lg); }
.header-actions { display: flex; align-items: center; gap: 8px; }
.proc-table { flex: 1; }
.proc-name { font-family: var(--font-mono); font-size: var(--text-sm); }
.cell-mono { font-family: var(--font-mono); font-size: var(--text-sm); color: var(--p-text-muted-color); }
.val-high { color: var(--p-red-400); }
.row-actions { display: flex; gap: 4px; }
.ml-2 { margin-left: 6px; }
.dialog-form { display: flex; flex-direction: column; gap: 12px; padding: 8px 0; }
.form-field { display: flex; flex-direction: column; gap: 4px; }
.form-field label { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-muted-color); letter-spacing: 1px; }
</style>
