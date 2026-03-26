<template>
  <div class="services-view">

    <Toolbar class="services-toolbar">
      <template #start>
        <div class="toolbar-start">
          <IconField>
            <InputIcon class="pi pi-search" />
            <InputText v-model="filter" placeholder="Filter services…" size="small" />
          </IconField>
          <SelectButton
            v-model="stateFilter"
            :options="stateOptions"
            option-label="label"
            option-value="value"
            size="small"
          />
        </div>
      </template>
      <template #end>
        <div class="toolbar-end">
          <Password
            v-model="sudoPassword"
            placeholder="sudo password"
            :feedback="false"
            toggle-mask
            input-class="sudo-input"
            size="small"
          />
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

    <Message
      v-if="error"
      severity="error"
      :closable="true"
      class="mb-3"
      @close="error = ''"
    >{{ error }}</Message>

    <DataTable
      :value="filtered"
      :loading="loading"
      striped-rows
      v-model:expanded-rows="expandedRows"
      data-key="name"
      :row-class="rowClass"
      size="small"
      @row-expand="onRowExpand"
    >
      <Column expander style="width: 2.5rem" />

      <Column field="name" header="SERVICE" sortable>
        <template #body="{ data }">
          <span class="font-mono" style="font-size: 12px; font-weight: 600;">{{ data.name }}</span>
        </template>
      </Column>

      <Column field="active_state" header="STATE" sortable>
        <template #body="{ data }">
          <Tag :value="data.active_state" :severity="stateSeverity(data.active_state)" />
        </template>
      </Column>

      <Column field="sub_state" header="SUB">
        <template #body="{ data }">
          <span class="font-mono" style="font-size: 11px; color: var(--p-text-muted-color);">{{ data.sub_state }}</span>
        </template>
      </Column>

      <Column field="enabled" header="ENABLED">
        <template #body="{ data }">
          <Badge
            :value="data.enabled"
            :severity="data.enabled === 'enabled' ? 'success' : 'secondary'"
          />
        </template>
      </Column>

      <Column field="description" header="DESCRIPTION" style="max-width: 260px">
        <template #body="{ data }">
          <span
            class="desc-cell"
            style="font-size: 12px; color: var(--p-text-muted-color);"
          >{{ data.description }}</span>
        </template>
      </Column>

      <Column header="ACTIONS">
        <template #body="{ data }">
          <ButtonGroup>
            <Button
              label="Start"
              size="small"
              severity="success"
              text
              :loading="actionLoading[data.name]"
              @click="runAction(data.name, 'start')"
            />
            <Button
              label="Stop"
              size="small"
              severity="warning"
              text
              :loading="actionLoading[data.name]"
              @click="runAction(data.name, 'stop')"
            />
            <Button
              label="Restart"
              size="small"
              severity="info"
              text
              :loading="actionLoading[data.name]"
              @click="runAction(data.name, 'restart')"
            />
          </ButtonGroup>
        </template>
      </Column>

      <template #expansion="slotProps">
        <div class="log-expansion">
          <div class="log-header">
            <span class="font-mono" style="font-size: 11px; color: var(--p-text-muted-color);">
              {{ slotProps.data.name }} — journald logs
            </span>
            <Button
              icon="pi pi-times"
              text
              rounded
              size="small"
              @click="collapseRow(slotProps.data.name)"
            />
          </div>
          <ScrollPanel style="height: 300px">
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
import SelectButton from 'primevue/selectbutton'
import Password from 'primevue/password'
import Button from 'primevue/button'
import ButtonGroup from 'primevue/buttongroup'
import Message from 'primevue/message'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import Badge from 'primevue/badge'
import ScrollPanel from 'primevue/scrollpanel'
import api from '../api/client.js'

const toast = useToast()

const services = ref([])
const loading = ref(false)
const error = ref('')
const filter = ref('')
const stateFilter = ref('all')
const expandedRows = ref({})
const logsByService = ref({})
const actionLoading = ref({})
const sudoPassword = ref('')

const stateOptions = [
  { value: 'all',      label: 'All' },
  { value: 'active',   label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
  { value: 'failed',   label: 'Failed' },
]

function stateSeverity(state) {
  return {
    active:       'success',
    failed:       'danger',
    activating:   'warn',
    inactive:     'secondary',
    deactivating: 'contrast',
  }[state] || 'secondary'
}

function rowClass(data) {
  if (data.active_state === 'failed') return 'row-failed'
  return ''
}

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
  actionLoading.value[name] = true
  error.value = ''
  try {
    await api.post(`/services/${name}/${action}`, {
      sudo_password: sudoPassword.value || null,
    })
    const { data } = await api.get('/services/')
    services.value = data
    delete logsByService.value[name]
    if (expandedRows.value[name]) {
      const logResp = await api.get(`/services/${name}/logs?lines=80`)
      logsByService.value[name] = logResp.data.lines
    }
    toast.add({ severity: 'success', summary: 'Done', detail: `${action} ${name}`, life: 3000 })
  } catch (e) {
    const msg = e.response?.data?.detail || `Failed to ${action} ${name}`
    toast.add({ severity: 'error', summary: 'Error', detail: msg, life: 5000 })
    if (e.response?.status === 500 && msg.toLowerCase().includes('password')) {
      sudoPassword.value = ''
    }
  } finally {
    actionLoading.value[name] = false
  }
}

const filtered = computed(() => services.value.filter(s => {
  const matchesText = filter.value === '' ||
    s.name.toLowerCase().includes(filter.value.toLowerCase()) ||
    s.description.toLowerCase().includes(filter.value.toLowerCase())
  const matchesState = stateFilter.value === 'all' || s.active_state === stateFilter.value
  return matchesText && matchesState
}))

onMounted(loadServices)
</script>

<style scoped>
.services-view { display: flex; flex-direction: column; gap: 14px; }

.services-toolbar { flex-wrap: wrap; gap: 8px; }

.toolbar-start { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.toolbar-end   { display: flex; align-items: center; gap: 8px; }

:deep(.sudo-input) { width: 130px; font-family: var(--font-mono); font-size: 12px; }

.desc-cell {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 260px;
}

/* Failed row highlight */
:deep(.row-failed td) {
  background: color-mix(in srgb, var(--p-red-500) 6%, transparent) !important;
}

/* Log expansion panel */
.log-expansion { padding: 4px 0; }
.log-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 4px 8px 8px;
}
.log-content {
  font-family: var(--font-mono);
  font-size: 11px; line-height: 1.7;
  margin: 0; padding: 0 12px 8px;
  white-space: pre-wrap; word-break: break-all;
  color: var(--p-text-muted-color);
}
</style>
