<template>
  <div class="users-view">
    <Card class="users-card">
      <template #content>

        <!-- Section header -->
        <div class="card-section-header">
          <i class="pi pi-users section-icon" />
          <span class="section-title">USER MANAGEMENT</span>
        </div>
        <Divider class="section-divider" />

        <Toolbar class="users-toolbar">
          <template #start>
            <IconField>
              <InputIcon class="pi pi-search" />
              <InputText v-model="userFilter" placeholder="Filter users…" size="small" />
            </IconField>
          </template>
          <template #end>
            <Button label="New User" icon="pi pi-plus" size="small" @click="showCreateDialog = true" />
          </template>
        </Toolbar>

        <!-- Data table -->
        <DataTable
          :value="filteredUsers"
          :loading="loading"
          size="small"
          :show-gridlines="false"
          :paginator="users.length > 10"
          :rows="10"
          sort-field="id"
          :sort-order="1"
        >
          <template #empty>
            <span class="cell-empty">No users found</span>
          </template>

          <Column field="id" header="ID" :sortable="true" style="width: 60px">
            <template #body="{ data }">
              <span class="cell-mono cell-muted">#{{ data.id }}</span>
            </template>
          </Column>

          <Column field="username" header="Username" :sortable="true">
            <template #body="{ data }">
              <div class="user-cell">
                <span class="user-avatar">{{ data.username[0].toUpperCase() }}</span>
                <span class="cell-name">{{ data.username }}</span>
              </div>
            </template>
          </Column>

          <Column field="role" header="Role" :sortable="true" style="width: 120px">
            <template #body="{ data }">
              <Tag :value="data.role" :severity="roleSeverity(data.role)" />
            </template>
          </Column>

          <Column header="Status" style="width: 100px">
            <template #body="{ data }">
              <Tag
                :value="data.is_active ? 'Active' : 'Inactive'"
                :severity="data.is_active ? 'success' : 'secondary'"
              />
            </template>
          </Column>

          <Column field="created_at" header="Created" :sortable="true" style="width: 160px">
            <template #body="{ data }">
              <span class="cell-mono cell-muted">{{ formatDate(data.created_at) }}</span>
            </template>
          </Column>

          <Column header="" style="width: 90px">
            <template #body="{ data }">
              <div class="row-actions">
                <Button
                  icon="pi pi-pencil"
                  text
                  rounded
                  size="small"
                  @click="openEdit(data)"
                  v-tooltip.top="'Edit'"
                />
                <Button
                  icon="pi pi-trash"
                  text
                  rounded
                  size="small"
                  severity="danger"
                  :disabled="data.username === auth.username"
                  @click="confirmDelete(data)"
                  v-tooltip.top="data.username === auth.username ? 'Cannot delete yourself' : 'Delete'"
                />
              </div>
            </template>
          </Column>
        </DataTable>

      </template>
    </Card>

    <!-- Create Dialog -->
    <Dialog v-model:visible="showCreateDialog" header="Create User" :modal="true" :style="{ width: '420px' }">
      <div class="dialog-form">
        <div class="form-field">
          <label>Username</label>
          <InputText v-model="createForm.username" placeholder="Enter username" fluid />
        </div>
        <div class="form-field">
          <label>Password</label>
          <Password v-model="createForm.password" placeholder="Enter password" :feedback="false" fluid toggleMask />
        </div>
        <div class="form-field">
          <label>Role</label>
          <Select v-model="createForm.role" :options="roleOptions" option-label="label" option-value="value" fluid />
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" text @click="showCreateDialog = false" />
        <Button label="Create" icon="pi pi-check" :loading="creatingUser" @click="createUser" />
      </template>
    </Dialog>

    <!-- Edit Dialog -->
    <Dialog v-model:visible="showEditDialog" :header="`Edit — ${editForm.username}`" :modal="true" :style="{ width: '420px' }">
      <div class="dialog-form">
        <div class="form-field">
          <label>Role</label>
          <Select v-model="editForm.role" :options="roleOptions" option-label="label" option-value="value" fluid />
        </div>
        <div class="form-field">
          <label>Status</label>
          <div class="toggle-row">
            <ToggleSwitch v-model="editForm.is_active" />
            <span class="toggle-label">{{ editForm.is_active ? 'Active' : 'Inactive' }}</span>
          </div>
        </div>
        <div class="form-field">
          <label>New Password <span class="optional">(optional)</span></label>
          <Password v-model="editForm.password" placeholder="Leave blank to keep current" :feedback="false" fluid toggleMask />
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" text @click="showEditDialog = false" />
        <Button label="Save" icon="pi pi-check" :loading="savingUser" @click="saveUser" />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { useAuthStore } from '../stores/auth.js'
import api from '../api/client.js'

import Card from 'primevue/card'
import Divider from 'primevue/divider'
import Toolbar from 'primevue/toolbar'
import IconField from 'primevue/iconfield'
import InputIcon from 'primevue/inputicon'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Select from 'primevue/select'
import ToggleSwitch from 'primevue/toggleswitch'

const toast = useToast()
const confirm = useConfirm()
const auth = useAuthStore()

const users = ref([])
const loading = ref(false)
const userFilter = ref('')

const filteredUsers = computed(() => {
  if (!userFilter.value.trim()) return users.value
  const q = userFilter.value.toLowerCase()
  return users.value.filter(u =>
    u.username.toLowerCase().includes(q) ||
    u.role.toLowerCase().includes(q)
  )
})
const showCreateDialog = ref(false)
const showEditDialog = ref(false)
const creatingUser = ref(false)
const savingUser = ref(false)

const roleOptions = [
  { label: 'Admin', value: 'admin' },
  { label: 'Operator', value: 'operator' },
  { label: 'Readonly', value: 'readonly' },
]

const createForm = ref({ username: '', password: '', role: 'readonly' })
const editForm = ref({ id: null, username: '', role: 'readonly', is_active: true, password: '' })

const roleSeverity = (role) => ({ admin: 'danger', operator: 'warn', readonly: 'info' }[role] ?? 'secondary')

const formatDate = (d) => {
  if (!d) return '—'
  return new Date(d).toLocaleDateString() + ' ' + new Date(d).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

async function loadUsers() {
  loading.value = true
  try {
    const { data } = await api.get('/admin/users')
    users.value = data
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.response?.data?.detail || 'Failed to load users', life: 3000 })
  } finally {
    loading.value = false
  }
}

async function createUser() {
  if (!createForm.value.username || !createForm.value.password) {
    toast.add({ severity: 'warn', summary: 'Validation', detail: 'Username and password are required', life: 3000 })
    return
  }
  creatingUser.value = true
  try {
    await api.post('/admin/users', {
      username: createForm.value.username,
      password: createForm.value.password,
      role: createForm.value.role,
    })
    toast.add({ severity: 'success', summary: 'Created', detail: `User "${createForm.value.username}" created`, life: 3000 })
    showCreateDialog.value = false
    createForm.value = { username: '', password: '', role: 'readonly' }
    await loadUsers()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.response?.data?.detail || 'Failed to create user', life: 3000 })
  } finally {
    creatingUser.value = false
  }
}

function openEdit(user) {
  editForm.value = { id: user.id, username: user.username, role: user.role, is_active: user.is_active, password: '' }
  showEditDialog.value = true
}

async function saveUser() {
  savingUser.value = true
  try {
    const payload = { role: editForm.value.role, is_active: editForm.value.is_active }
    if (editForm.value.password) payload.password = editForm.value.password
    await api.patch(`/admin/users/${editForm.value.id}`, payload)
    toast.add({ severity: 'success', summary: 'Saved', detail: 'User updated', life: 3000 })
    showEditDialog.value = false
    await loadUsers()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.response?.data?.detail || 'Failed to update user', life: 3000 })
  } finally {
    savingUser.value = false
  }
}

function confirmDelete(user) {
  confirm.require({
    message: `Delete user "${user.username}"? This action cannot be undone.`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    rejectLabel: 'Cancel',
    acceptLabel: 'Delete',
    acceptClass: 'p-button-danger',
    accept: () => deleteUser(user.id),
  })
}

async function deleteUser(userId) {
  try {
    await api.delete(`/admin/users/${userId}`)
    toast.add({ severity: 'success', summary: 'Deleted', detail: 'User removed', life: 3000 })
    await loadUsers()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.response?.data?.detail || 'Failed to delete user', life: 3000 })
  }
}

onMounted(loadUsers)
</script>

<style scoped>
.users-view { display: flex; flex-direction: column; gap: 16px; }

:deep(.users-card .p-card-body) { padding: 0; }
:deep(.users-card .p-card-content) { padding: 14px 16px; }

/* Section header — consistent with other views */
.card-section-header { display: flex; align-items: center; gap: 8px; }
.section-icon { font-size: 12px; color: var(--brand-orange); flex-shrink: 0; }
.section-title {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--p-text-muted-color);
  flex: 1;
}
.section-divider { margin: 10px 0 !important; }

/* User cell */
.user-cell { display: flex; align-items: center; gap: 8px; }
.user-avatar {
  width: 26px; height: 26px;
  background: color-mix(in srgb, var(--brand-orange) 15%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand-orange) 30%, transparent);
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  color: var(--brand-orange);
  flex-shrink: 0;
}
.cell-name { font-size: var(--text-sm); color: var(--p-text-color); }
.cell-mono { font-family: var(--font-mono); font-size: var(--text-sm); }
.cell-muted { color: var(--p-text-muted-color); }
.cell-empty { font-size: var(--text-sm); color: var(--p-text-muted-color); }

/* DataTable overrides — consistent with rest of app */
:deep(.p-datatable-thead th) { padding: 6px 10px; background: transparent; }
:deep(.p-datatable-column-header-content) {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 1.5px;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
  font-weight: 600;
}
:deep(.p-datatable-tbody td) { padding: 5px 10px; font-family: var(--font-ui); font-size: var(--text-sm); }

/* Row actions */
.row-actions { display: flex; gap: 2px; }

/* Dialog form */
.dialog-form { display: flex; flex-direction: column; gap: 16px; padding: 4px 0 8px; }
.form-field { display: flex; flex-direction: column; gap: 6px; }
.form-field label { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-muted-color); letter-spacing: 0.5px; }
.optional { font-weight: 400; opacity: 0.6; }
.toggle-row { display: flex; align-items: center; gap: 10px; padding: 8px 0; }
.toggle-label { font-size: var(--text-sm); color: var(--p-text-color); }

/* ── Toolbar ── */
:deep(.users-toolbar) {
  background: transparent;
  border: none;
  padding: 0 0 12px 0;
}
:deep(.users-toolbar .p-toolbar-start),
:deep(.users-toolbar .p-toolbar-end) {
  gap: 8px;
}
</style>
