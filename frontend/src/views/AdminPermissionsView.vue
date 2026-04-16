<template>
  <div class="permissions-view">
    <Card class="permissions-card">
      <template #content>

        <div class="card-section-header">
          <i class="pi pi-shield section-icon" />
          <span class="section-title">PERMISSION MATRIX</span>
        </div>
        <Divider class="section-divider" />

        <div v-if="loading" class="loading-state">
          <ProgressSpinner style="width:32px;height:32px" />
        </div>

        <div v-else>
          <DataTable :value="rows" size="small" :show-gridlines="true">
            <template #empty>
              <span class="cell-empty">No permissions found</span>
            </template>

            <Column header="Resource" style="width: 130px">
              <template #body="{ data }">
                <span class="cell-mono">{{ data.resource }}</span>
              </template>
            </Column>

            <Column header="Action" style="width: 110px">
              <template #body="{ data }">
                <Tag :value="data.action" :severity="actionSeverity(data.action)" />
              </template>
            </Column>

            <Column header="Admin" style="width: 80px; text-align:center">
              <template #body>
                <Checkbox :modelValue="true" :disabled="true" binary />
              </template>
            </Column>

            <Column header="Operator" style="width: 90px; text-align:center">
              <template #body="{ data }">
                <Checkbox
                  :modelValue="hasPermission('operator', data.resource, data.action)"
                  binary
                  @change="toggle('operator', data.resource, data.action)"
                />
              </template>
            </Column>

            <Column header="Read-only" style="width: 90px; text-align:center">
              <template #body="{ data }">
                <Checkbox
                  :modelValue="hasPermission('readonly', data.resource, data.action)"
                  binary
                  @change="toggle('readonly', data.resource, data.action)"
                />
              </template>
            </Column>
          </DataTable>
        </div>

        <div v-if="error" class="error-msg">{{ error }}</div>

      </template>
    </Card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api/client.js'
import Card from 'primevue/card'
import Divider from 'primevue/divider'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import Checkbox from 'primevue/checkbox'
import ProgressSpinner from 'primevue/progressspinner'

// All resource×action combinations managed by the permission system
const MATRIX_ROWS = [
  { resource: 'system',    action: 'read' },
  { resource: 'services',  action: 'read' },
  { resource: 'services',  action: 'write' },
  { resource: 'services',  action: 'execute' },
  { resource: 'files',     action: 'read' },
  { resource: 'files',     action: 'write' },
  { resource: 'files',     action: 'delete' },
  { resource: 'network',   action: 'read' },
  { resource: 'scripts',   action: 'read' },
  { resource: 'scripts',   action: 'write' },
  { resource: 'scripts',   action: 'delete' },
  { resource: 'scripts',   action: 'execute' },
  { resource: 'crontab',   action: 'read' },
  { resource: 'crontab',   action: 'write' },
  { resource: 'crontab',   action: 'delete' },
  { resource: 'logs',      action: 'read' },
  { resource: 'pipelines', action: 'read' },
  { resource: 'pipelines', action: 'write' },
  { resource: 'pipelines', action: 'delete' },
  { resource: 'pipelines', action: 'execute' },
  { resource: 'users',     action: 'read' },
  { resource: 'users',     action: 'write' },
  { resource: 'users',     action: 'delete' },
]

const rows = ref(MATRIX_ROWS)
const loading = ref(true)
const error = ref(null)

// permissions[role] = Set of "resource|action" strings for O(1) lookup
const permissions = ref({ operator: new Set(), readonly: new Set() })

function key(resource, action) {
  return `${resource}|${action}`
}

function hasPermission(role, resource, action) {
  return permissions.value[role]?.has(key(resource, action)) ?? false
}

async function loadPermissions() {
  loading.value = true
  error.value = null
  try {
    const { data } = await api.get('/admin/permissions')
    permissions.value.operator = new Set(data.operator.map(p => key(p.resource, p.action)))
    permissions.value.readonly = new Set(data.readonly.map(p => key(p.resource, p.action)))
  } catch {
    error.value = 'Failed to load permissions'
  } finally {
    loading.value = false
  }
}

async function toggle(role, resource, action) {
  const k = key(resource, action)
  const current = new Set(permissions.value[role])
  if (current.has(k)) {
    current.delete(k)
  } else {
    current.add(k)
  }
  permissions.value[role] = current

  const payload = [...current].map(k => {
    const [res, act] = k.split('|')
    return { resource: res, action: act }
  })

  try {
    await api.put(`/admin/permissions/${role}`, payload)
  } catch {
    // Revert optimistic update on failure
    error.value = 'Failed to save permission change'
    await loadPermissions()
  }
}

function actionSeverity(action) {
  return { read: 'info', write: 'warn', delete: 'danger', execute: 'success' }[action] ?? 'secondary'
}

onMounted(loadPermissions)
</script>

<style scoped>
.permissions-view {
  padding: 16px;
  max-width: 900px;
}
.permissions-card {
  border: 1px solid var(--p-surface-border);
}
.card-section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-bottom: 4px;
}
.section-icon {
  color: var(--brand-orange);
  font-size: var(--text-base);
}
.section-title {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: 2px;
  color: var(--p-text-muted-color);
}
.section-divider {
  margin: 8px 0 16px;
}
.loading-state {
  display: flex;
  justify-content: center;
  padding: 32px;
}
.cell-mono {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
}
.cell-empty {
  color: var(--p-text-muted-color);
  font-size: var(--text-sm);
}
.error-msg {
  color: var(--p-red-500);
  font-size: var(--text-sm);
  margin-top: 12px;
}
</style>
