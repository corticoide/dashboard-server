<template>
  <div class="file-list">
    <!-- Toolbar: breadcrumb + actions -->
    <Toolbar class="list-toolbar">
      <template #start>
        <Breadcrumb :model="breadcrumbItems" :home="homeItem" class="list-breadcrumb" />
      </template>
      <template #end>
        <div class="toolbar-end">
          <FileUpload
            v-if="canUpload"
            mode="basic"
            :auto="true"
            chooseLabel="Upload"
            chooseIcon="pi pi-upload"
            :customUpload="true"
            @uploader="uploadFile"
            size="small"
          />
          <Button
            v-if="canAdmin"
            label="New Folder"
            icon="pi pi-folder-plus"
            outlined
            size="small"
            @click="showMkdirDialog = true"
          />
        </div>
      </template>
    </Toolbar>

    <!-- File table -->
    <DataTable
      :value="props.entries || []"
      v-model:selection="selectedEntry"
      v-model:sortField="sortKey"
      v-model:sortOrder="sortDir"
      :loading="loading"
      selectionMode="single"
      dataKey="path"
      size="small"
      stripedRows
      scrollable
      scrollHeight="flex"
      removableSort
      class="file-table"
      @row-select="onRowSelect"
      @row-dblclick="onRowDblClick"
    >
      <template #empty>
        <div class="empty-state">
          <i class="pi pi-folder-open empty-icon" />
          <span class="empty-text">Empty directory</span>
        </div>
      </template>

      <Column field="name" header="Name" sortable style="min-width: 220px">
        <template #body="{ data }">
          <div class="name-cell">
            <svg v-if="data.is_dir" width="14" height="14" viewBox="0 0 24 24" fill="currentColor" class="icon-dir">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            </svg>
            <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="icon-file">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
            </svg>
            <span class="name-text" :class="{ 'name-dir': data.is_dir }">{{ data.name }}</span>
            <Tag v-if="isFavorite(data.path)" value="★" severity="warn" rounded class="fav-tag" />
          </div>
        </template>
      </Column>

      <Column field="size" header="Size" sortable style="width: 100px">
        <template #body="{ data }">
          <span class="cell-mono cell-meta">{{ data.is_dir ? '—' : formatSize(data.size) }}</span>
        </template>
      </Column>

      <Column field="permissions" header="Perms" style="width: 110px">
        <template #body="{ data }">
          <span class="cell-mono cell-meta cell-perms">{{ data.permissions }}</span>
        </template>
      </Column>

      <Column field="owner" header="Owner" style="width: 100px">
        <template #body="{ data }">
          <Chip :label="data.owner" class="owner-chip" />
        </template>
      </Column>

      <Column field="modified" header="Modified" sortable style="width: 150px">
        <template #body="{ data }">
          <span class="cell-meta">{{ formatDate(data.modified) }}</span>
        </template>
      </Column>

      <Column header="Actions" style="width: 140px; text-align: right">
        <template #body="{ data }">
          <div class="actions-cell" @click.stop>
            <Button
              v-if="!data.is_dir"
              :icon="isFavorite(data.path) ? 'pi pi-star-fill' : 'pi pi-star'"
              text rounded size="small"
              :class="isFavorite(data.path) ? 'text-yellow-500' : ''"
              v-tooltip.top="'Toggle favorite'"
              @click.stop="toggleFavorite(data.path)"
            />
            <Button
              v-if="!data.is_dir"
              icon="pi pi-download"
              text rounded size="small"
              v-tooltip.top="'Download'"
              @click.stop="downloadFile(data)"
            />
            <Button
              v-if="canAdmin"
              icon="pi pi-pencil"
              text rounded size="small"
              severity="secondary"
              v-tooltip.top="'Rename'"
              @click.stop="startRename(data)"
            />
            <Button
              v-if="canAdmin"
              icon="pi pi-trash"
              text rounded size="small"
              severity="danger"
              v-tooltip.top="'Delete'"
              @click.stop="confirmDelete(data)"
            />
          </div>
        </template>
      </Column>
    </DataTable>

    <!-- New Folder dialog -->
    <Dialog
      v-model:visible="showMkdirDialog"
      header="New Folder"
      :modal="true"
      :draggable="false"
      style="width: 350px"
    >
      <InputText
        v-model="mkdirName"
        placeholder="folder name"
        fluid
        autofocus
        @keydown.enter="createDir"
      />
      <template #footer>
        <Button label="Cancel" text @click="showMkdirDialog = false" />
        <Button label="Create" icon="pi pi-check" @click="createDir" />
      </template>
    </Dialog>

    <!-- Rename dialog -->
    <Dialog
      v-model:visible="showRenameDialog"
      header="Rename"
      :modal="true"
      :draggable="false"
      style="width: 400px"
    >
      <InputText
        v-model="renameValue"
        fluid
        autofocus
        @keydown.enter="doRename"
      />
      <template #footer>
        <Button label="Cancel" text @click="showRenameDialog = false" />
        <Button label="Rename" icon="pi pi-check" @click="doRename" />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import Toolbar from 'primevue/toolbar'
import Breadcrumb from 'primevue/breadcrumb'
import FileUpload from 'primevue/fileupload'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import Chip from 'primevue/chip'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import api from '../../api/client.js'
import { useScriptsStore } from '../../stores/scripts.js'

const toast = useToast()
const confirm = useConfirm()
const scriptsStore = useScriptsStore()

const props = defineProps({
  path: String,
  entries: Array,
  loading: Boolean,
  userRole: { type: String, default: 'readonly' },
  sudoPassword: { type: String, default: '' },
})
const emit = defineEmits(['navigate', 'select-file', 'refresh'])

const canAdmin = computed(() => props.userRole === 'admin')
const canUpload = computed(() => props.userRole === 'admin' || props.userRole === 'operator')

const selectedEntry = ref(null)
const sortKey = ref(null)
const sortDir = ref(null)
const showMkdirDialog = ref(false)
const mkdirName = ref('')
const showRenameDialog = ref(false)
const renameValue = ref('')
const renameTarget = ref(null)

// Breadcrumb
const homeItem = { icon: 'pi pi-home', command: () => emit('navigate', '/') }
const breadcrumbItems = computed(() => {
  if (!props.path || props.path === '/') return []
  const parts = props.path.split('/').filter(Boolean)
  let acc = ''
  return parts.map(part => {
    acc += '/' + part
    const path = acc
    return { label: part, command: () => emit('navigate', path) }
  })
})

// Favorites
onMounted(() => scriptsStore.loadFavorites())
function isFavorite(path) { return scriptsStore.isFavorite(path) }
async function toggleFavorite(path) {
  if (scriptsStore.isFavorite(path)) await scriptsStore.removeFavoriteByPath(path)
  else await scriptsStore.addFavorite(path)
}

// Row handlers
function onRowSelect(e) {
  if (!e.data.is_dir) emit('select-file', e.data)
}
function onRowDblClick(e) {
  if (e.data.is_dir) emit('navigate', e.data.path)
  else emit('select-file', e.data)
}

// Formatters
function formatSize(bytes) {
  if (bytes == null) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`
}
function formatDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

// Actions
async function uploadFile(e) {
  const files = e.files
  for (const file of files) {
    const form = new FormData()
    form.append('file', file)
    try {
      await api.post(`/files/upload?path=${encodeURIComponent(props.path)}`, form)
    } catch (err) {
      toast.add({
        severity: 'error',
        summary: 'Upload failed',
        detail: err.response?.data?.detail || err.message,
        life: 5000,
      })
    }
  }
  emit('refresh')
}

async function createDir() {
  if (!mkdirName.value.trim()) return
  const newPath = props.path === '/'
    ? `/${mkdirName.value.trim()}`
    : `${props.path}/${mkdirName.value.trim()}`
  try {
    await api.post('/files/mkdir', { path: newPath })
    showMkdirDialog.value = false
    mkdirName.value = ''
    emit('refresh')
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.response?.data?.detail || 'Failed to create folder', life: 5000 })
  }
}

async function downloadFile(entry) {
  try {
    const headers = props.sudoPassword ? { 'X-Sudo-Password': props.sudoPassword } : {}
    const resp = await api.get('/files/download', {
      params: { path: entry.path },
      responseType: 'blob',
      headers,
    })
    const url = URL.createObjectURL(resp.data)
    const a = document.createElement('a')
    a.href = url
    a.download = entry.name
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Download failed', detail: e.response?.data?.detail || e.message, life: 5000 })
  }
}

function startRename(entry) {
  renameTarget.value = entry
  renameValue.value = entry.name
  showRenameDialog.value = true
}

async function doRename() {
  if (!renameValue.value.trim()) return
  const parts = renameTarget.value.path.split('/')
  parts[parts.length - 1] = renameValue.value.trim()
  const newPath = parts.join('/')
  try {
    await api.post('/files/rename', { source: renameTarget.value.path, destination: newPath })
    showRenameDialog.value = false
    renameTarget.value = null
    emit('refresh')
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Rename failed', detail: e.response?.data?.detail || 'Rename failed', life: 5000 })
  }
}

function confirmDelete(entry) {
  confirm.require({
    message: entry.is_dir
      ? `Delete directory "${entry.name}" and all its contents?`
      : `Delete "${entry.name}"? This cannot be undone.`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    rejectLabel: 'Cancel',
    acceptLabel: 'Delete',
    acceptClass: 'p-button-danger',
    accept: () => doDelete(entry),
  })
}

async function doDelete(entry) {
  try {
    await api.delete(`/files/delete?path=${encodeURIComponent(entry.path)}`)
    emit('refresh')
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Delete failed', detail: e.response?.data?.detail || 'Delete failed', life: 5000 })
  }
}
</script>

<style scoped>
.file-list { display: flex; flex-direction: column; height: 100%; overflow: hidden; }

.list-toolbar { border-radius: 0; border-left: none; border-right: none; border-top: none; flex-shrink: 0; }
.list-breadcrumb { background: transparent; border: none; padding: 0; }
.toolbar-end { display: flex; align-items: center; gap: 8px; }

:deep(.file-table) { flex: 1; min-height: 0; cursor: default; }
:deep(.p-datatable-wrapper) { flex: 1; min-height: 0; }
:deep(.file-table .p-datatable-tbody tr) { cursor: pointer; }

/* DataTable header normalization */
:deep(.file-table .p-datatable-thead th) { background: transparent; }
:deep(.file-table .p-datatable-column-header-content) {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 1.5px;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
  font-weight: 600;
}
:deep(.file-table .p-datatable-tbody td) { padding: 5px 10px; }

/* Empty state */
.empty-state {
  display: flex; flex-direction: column; align-items: center;
  gap: 10px; padding: 48px;
  color: var(--p-text-muted-color);
}
.empty-icon { font-size: 28px; opacity: 0.4; }
.empty-text { font-family: var(--font-mono); font-size: var(--text-sm); }

/* Name cell */
.name-cell {
  display: flex; align-items: center; gap: 7px;
  font-size: var(--text-sm);
}
.name-text { color: var(--p-text-color); }
.name-dir  { font-weight: 500; }
.icon-dir  { color: var(--p-yellow-400); flex-shrink: 0; }
.icon-file { color: var(--p-text-muted-color); flex-shrink: 0; }
.fav-tag   { font-size: var(--text-2xs); }

/* Cell utilities */
.cell-mono  { font-family: var(--font-mono); }
.cell-meta  { font-size: var(--text-xs); color: var(--p-text-muted-color); }
.cell-perms { letter-spacing: 0.5px; }
:deep(.owner-chip) { font-size: var(--text-xs) !important; }

.actions-cell { display: flex; align-items: center; justify-content: flex-end; gap: 2px; }
</style>
