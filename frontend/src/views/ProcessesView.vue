<template>
  <div class="processes-view">
    <div class="page-header">
      <div class="page-title">
        <i class="pi pi-server page-icon" />
        <span>PROCESSES</span>
        <span class="live-dot" :class="{ tick: liveTick }" title="Live" />
        <Tag :value="countLabel" severity="secondary" />
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
      :loading="initialLoading"
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
      <Column field="pid" header="PID" sortable style="width: 76px">
        <template #body="{ data }"><span class="cell-mono">{{ data.pid }}</span></template>
      </Column>
      <Column field="cpu_percent" header="CPU %" sortable style="width: 110px">
        <template #body="{ data }">
          <div class="bar-cell">
            <div class="bar-track">
              <div
                class="bar-fill"
                :class="{ 'bar-hot': data.cpu_percent > 50 }"
                :style="{ width: Math.min(data.cpu_percent, 100) + '%' }"
              />
            </div>
            <span class="cell-mono" :class="{ 'val-hot': data.cpu_percent > 50 }">
              {{ data.cpu_percent.toFixed(1) }}
            </span>
          </div>
        </template>
      </Column>
      <Column field="memory_mb" header="RAM MB" sortable style="width: 90px">
        <template #body="{ data }">
          <span class="cell-mono" :class="{ 'val-hot': data.memory_mb > 500 }">
            {{ data.memory_mb.toFixed(0) }}
          </span>
        </template>
      </Column>
      <Column field="username" header="User" style="width: 110px">
        <template #body="{ data }"><span class="cell-mono">{{ data.username }}</span></template>
      </Column>
      <Column field="status" header="Status" style="width: 100px">
        <template #body="{ data }">
          <Tag :value="data.status" :severity="statusSeverity(data.status)" />
        </template>
      </Column>
      <Column header="Actions" style="width: 110px" v-if="canExecute">
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
const initialLoading = ref(false)  // only true on first fetch (empty table)
const truncated = ref(false)
const error = ref(null)
const filterTerm = ref('')
const liveTick = ref(false)

let fetching = false

const watchDialog = ref(false)
const watchTarget = ref(null)
const watchSaving = ref(false)
const watchForm = ref({ email_to: '', cooldown_minutes: 60 })

const canExecute = computed(() => auth.hasPermission('processes', 'execute'))

const countLabel = computed(() => {
  const total = processes.value.length
  const shown = filteredProcesses.value.length
  return filterTerm.value ? `${shown} / ${total}` : `${total}`
})

const filteredProcesses = computed(() => {
  if (!filterTerm.value) return processes.value
  const term = filterTerm.value.toLowerCase()
  return processes.value.filter(p => p.name.toLowerCase().includes(term))
})

async function loadProcesses() {
  if (fetching) return
  fetching = true
  // Show DataTable skeleton only when the list is empty (first load)
  if (processes.value.length === 0) initialLoading.value = true
  try {
    const r = await api.get('/processes/')
    processes.value = r.data.slice(0, MAX_DISPLAY)
    truncated.value = r.data.length >= MAX_DISPLAY
    error.value = null
    // Brief pulse on the live dot
    liveTick.value = true
    setTimeout(() => { liveTick.value = false }, 400)
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load processes'
  } finally {
    initialLoading.value = false
    fetching = false
  }
}

function statusSeverity(status) {
  return {
    running:   'success',
    sleeping:  'secondary',
    disk_sleep: 'warn',
    stopped:   'warn',
    zombie:    'danger',
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

const { start, stop } = usePolling(loadProcesses, 2000)

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

/* Live dot */
.live-dot {
  width: 7px; height: 7px;
  border-radius: 50%;
  background: var(--p-green-500);
  flex-shrink: 0;
  transition: background 0.15s, box-shadow 0.15s;
}
.live-dot.tick {
  background: var(--p-green-400);
  box-shadow: 0 0 6px var(--p-green-400);
}

/* CPU bar */
.bar-cell { display: flex; align-items: center; gap: 6px; }
.bar-track {
  width: 40px; height: 4px;
  background: var(--p-surface-border);
  border-radius: 2px;
  overflow: hidden;
  flex-shrink: 0;
}
.bar-fill {
  height: 100%;
  background: var(--p-green-500);
  border-radius: 2px;
  transition: width 0.4s ease;
}
.bar-fill.bar-hot { background: var(--p-red-400); }

.proc-name { font-family: var(--font-mono); font-size: var(--text-sm); }
.cell-mono { font-family: var(--font-mono); font-size: var(--text-sm); color: var(--p-text-muted-color); }
.val-hot { color: var(--p-red-400); }
.row-actions { display: flex; gap: 2px; }
.ml-2 { margin-left: 6px; }
.dialog-form { display: flex; flex-direction: column; gap: 12px; padding: 8px 0; }
.form-field { display: flex; flex-direction: column; gap: 4px; }
.form-field label { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-muted-color); letter-spacing: 1px; }
</style>
