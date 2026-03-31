<template>
  <Card class="card">
    <!-- Header -->
    <template #header>
      <div class="card-section-header">
        <div class="section-icon">
          <i class="pi pi-users" />
        </div>
        <div class="section-title">Manage Users</div>
      </div>
    </template>

    <!-- Toolbar -->
    <div class="toolbar">
      <Button label="+ Create User" icon="pi pi-plus" @click="showCreateDialog = true" />
    </div>

    <!-- DataTable -->
    <DataTable
      :value="users"
      :loading="loading"
      responsive-layout="scroll"
      class="p-datatable-striped"
      paginator
      :rows="10"
      :row-options="{ selectable: false }"
    >
      <Column field="id" header="ID" :sortable="true" style="width: 60px" />
      <Column field="username" header="Username" :sortable="true" />
      <Column field="role" header="Role" :sortable="true">
        <template #body="{ data }">
          <Tag :value="data.role" :severity="getRoleSeverity(data.role)" />
        </template>
      </Column>
      <Column header="Status">
        <template #body="{ data }">
          <Tag :value="data.is_active ? 'Active' : 'Inactive'" :severity="data.is_active ? 'success' : 'warning'" />
        </template>
      </Column>
      <Column field="created_at" header="Created" :sortable="true">
        <template #body="{ data }">
          {{ formatDate(data.created_at) }}
        </template>
      </Column>
      <Column header="Actions" style="width: 140px">
        <template #body="{ data }">
          <Button
            icon="pi pi-pencil"
            class="p-button-rounded p-button-text"
            @click="editUser(data)"
            v-tooltip="'Edit'"
          />
          <Button
            icon="pi pi-trash"
            class="p-button-rounded p-button-text p-button-danger"
            @click="confirmDelete(data)"
            :disabled="data.username === auth.username"
            v-tooltip="data.username === auth.username ? 'Cannot delete yourself' : 'Delete'"
          />
        </template>
      </Column>
    </DataTable>
  </Card>

  <!-- Create Dialog -->
  <Dialog v-model:visible="showCreateDialog" header="Create User" :modal="true" :style="{ width: '400px' }">
    <div class="space-y-4">
      <div>
        <label class="block text-sm font-medium mb-1">Username</label>
        <InputText v-model="createForm.username" class="w-full" placeholder="Enter username" />
      </div>
      <div>
        <label class="block text-sm font-medium mb-1">Password</label>
        <Password v-model="createForm.password" class="w-full" placeholder="Enter password" :feedback="false" />
      </div>
      <div>
        <label class="block text-sm font-medium mb-1">Role</label>
        <Select v-model="createForm.role" :options="roleOptions" option-label="label" option-value="value" class="w-full" />
      </div>
    </div>
    <template #footer>
      <Button label="Cancel" @click="showCreateDialog = false" class="p-button-text" />
      <Button label="Create" @click="createUser" :loading="creatingUser" />
    </template>
  </Dialog>

  <!-- Edit Dialog -->
  <Dialog v-model:visible="showEditDialog" header="Edit User" :modal="true" :style="{ width: '400px' }">
    <div class="space-y-4">
      <div>
        <label class="block text-sm font-medium mb-1">Username</label>
        <div class="p-3 bg-surface-100 rounded">{{ editForm.username }}</div>
      </div>
      <div>
        <label class="block text-sm font-medium mb-1">Role</label>
        <Select v-model="editForm.role" :options="roleOptions" option-label="label" option-value="value" class="w-full" />
      </div>
      <div>
        <label class="flex items-center gap-2">
          <ToggleSwitch v-model="editForm.is_active" />
          <span class="text-sm">Active</span>
        </label>
      </div>
      <div>
        <label class="block text-sm font-medium mb-1">New Password (optional)</label>
        <Password v-model="editForm.password" class="w-full" placeholder="Leave blank to keep current password" :feedback="false" />
      </div>
    </div>
    <template #footer>
      <Button label="Cancel" @click="showEditDialog = false" class="p-button-text" />
      <Button label="Save" @click="saveUser" :loading="savingUser" />
    </template>
  </Dialog>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { useAuthStore } from '../stores/auth.js'
import api from '../api/client.js'

import Card from 'primevue/card'
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
const showCreateDialog = ref(false)
const showEditDialog = ref(false)
const creatingUser = ref(false)
const savingUser = ref(false)

const roleOptions = [
  { label: 'Admin', value: 'admin' },
  { label: 'Operator', value: 'operator' },
  { label: 'Readonly', value: 'readonly' },
]

const createForm = ref({
  username: '',
  password: '',
  role: 'readonly',
})

const editForm = ref({
  id: null,
  username: '',
  role: 'readonly',
  is_active: true,
  password: '',
})

const getRoleSeverity = (role) => {
  const map = { admin: 'danger', operator: 'warning', readonly: 'info' }
  return map[role] || 'info'
}

const formatDate = (date) => {
  if (!date) return '-'
  return new Date(date).toLocaleString()
}

const loadUsers = async () => {
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

const createUser = async () => {
  if (!createForm.value.username || !createForm.value.password) {
    toast.add({ severity: 'warn', summary: 'Validation', detail: 'Username and password required', life: 3000 })
    return
  }
  creatingUser.value = true
  try {
    await api.post('/admin/users', {
      username: createForm.value.username,
      password: createForm.value.password,
      role: createForm.value.role,
    })
    toast.add({ severity: 'success', summary: 'Success', detail: 'User created', life: 3000 })
    showCreateDialog.value = false
    createForm.value = { username: '', password: '', role: 'readonly' }
    await loadUsers()
  } catch (e) {
    const detail = e.response?.data?.detail || 'Failed to create user'
    toast.add({ severity: 'error', summary: 'Error', detail, life: 3000 })
  } finally {
    creatingUser.value = false
  }
}

const editUser = (user) => {
  editForm.value = {
    id: user.id,
    username: user.username,
    role: user.role,
    is_active: user.is_active,
    password: '',
  }
  showEditDialog.value = true
}

const saveUser = async () => {
  savingUser.value = true
  try {
    const payload = {
      role: editForm.value.role,
      is_active: editForm.value.is_active,
    }
    if (editForm.value.password) {
      payload.password = editForm.value.password
    }
    await api.patch(`/admin/users/${editForm.value.id}`, payload)
    toast.add({ severity: 'success', summary: 'Success', detail: 'User updated', life: 3000 })
    showEditDialog.value = false
    await loadUsers()
  } catch (e) {
    const detail = e.response?.data?.detail || 'Failed to update user'
    toast.add({ severity: 'error', summary: 'Error', detail, life: 3000 })
  } finally {
    savingUser.value = false
  }
}

const confirmDelete = (user) => {
  confirm.require({
    message: `Delete user "${user.username}"?`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    accept: () => deleteUser(user.id),
  })
}

const deleteUser = async (userId) => {
  try {
    await api.delete(`/admin/users/${userId}`)
    toast.add({ severity: 'success', summary: 'Success', detail: 'User deleted', life: 3000 })
    await loadUsers()
  } catch (e) {
    const detail = e.response?.data?.detail || 'Failed to delete user'
    toast.add({ severity: 'error', summary: 'Error', detail, life: 3000 })
  }
}

onMounted(() => {
  loadUsers()
})
</script>

<style scoped>
.card {
  margin: 0;
}

.card-section-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
}

.section-icon {
  width: 32px;
  height: 32px;
  background: color-mix(in srgb, var(--brand-orange) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand-orange) 30%, transparent);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--brand-orange);
  font-size: 18px;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--p-text-color);
}

.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
}

.space-y-4 > * + * {
  margin-top: 16px;
}

.w-full {
  width: 100%;
}

.p-3 {
  padding: 12px;
}

.bg-surface-100 {
  background: var(--p-surface-100);
}

.rounded {
  border-radius: 6px;
}

.text-sm {
  font-size: 14px;
}

.font-medium {
  font-weight: 500;
}

.mb-1 {
  margin-bottom: 4px;
}

.block {
  display: block;
}

.flex {
  display: flex;
}

.items-center {
  align-items: center;
}

.gap-2 {
  gap: 8px;
}
</style>
