<template>
  <div class="file-list">
    <div class="list-toolbar">
      <div class="breadcrumb">
        <span v-for="(seg, i) in segments" :key="seg.path" class="breadcrumb-item">
          <span v-if="i > 0" class="breadcrumb-sep">/</span>
          <button class="breadcrumb-btn" @click="$emit('navigate', seg.path)">{{ seg.label }}</button>
        </span>
      </div>
      <div class="toolbar-actions">
        <!-- Upload: operator+ -->
        <label v-if="canUpload" class="action-btn btn-blue" title="Upload file">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
          Upload
          <input type="file" class="hidden-input" @change="uploadFile" multiple />
        </label>
        <!-- New Folder: admin only -->
        <button v-if="canAdmin" class="action-btn btn-muted" @click="showMkdir = true" title="New folder">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/><line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/></svg>
          New Folder
        </button>
      </div>
    </div>

    <div v-if="showMkdir" class="mkdir-bar">
      <input v-model="mkdirName" ref="mkdirInput" class="mkdir-input" placeholder="folder name"
        @keydown.enter="createDir" @keydown.esc="showMkdir = false" />
      <button class="action-btn btn-green" @click="createDir">Create</button>
      <button class="action-btn btn-muted" @click="showMkdir = false">Cancel</button>
    </div>

    <div class="table-wrap">
      <table class="files-table">
        <thead>
          <tr>
            <th class="th-name" @click="sort('name')">NAME <span class="sort-arrow">{{ sortArrow('name') }}</span></th>
            <th @click="sort('size')">SIZE <span class="sort-arrow">{{ sortArrow('size') }}</span></th>
            <th>PERMISSIONS</th>
            <th>OWNER</th>
            <th @click="sort('modified')">MODIFIED <span class="sort-arrow">{{ sortArrow('modified') }}</span></th>
            <th>ACTIONS</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="6" class="loading-cell">
              <div class="skeleton" v-for="i in 5" :key="i"></div>
            </td>
          </tr>
          <template v-else>
            <!-- Parent directory ".." row -->
            <tr v-if="parentPath" class="file-row parent-row" @dblclick="$emit('navigate', parentPath)">
              <td class="name-cell">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" class="icon-dir">
                  <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                </svg>
                <span class="parent-label">.. (parent directory)</span>
              </td>
              <td class="mono-cell">—</td>
              <td class="mono-cell">—</td>
              <td class="mono-cell">—</td>
              <td class="mono-cell">—</td>
              <td class="actions-cell"></td>
            </tr>
            <tr v-if="sorted.length === 0 && !parentPath">
              <td colspan="6" class="empty-cell">Empty directory</td>
            </tr>
            <tr
              v-for="entry in sorted" :key="entry.path"
              class="file-row"
              :class="{ selected: selectedPath === entry.path }"
              @click="handleRowClick(entry)"
              @dblclick="handleDblClick(entry)"
            >
              <td class="name-cell">
                <svg v-if="entry.is_dir" width="14" height="14" viewBox="0 0 24 24" fill="currentColor" class="icon-dir">
                  <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                </svg>
                <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="icon-file">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
                </svg>
                <span>{{ entry.name }}</span>
              </td>
              <td class="mono-cell">{{ entry.is_dir ? '—' : formatSize(entry.size) }}</td>
              <td class="mono-cell perm-cell">{{ entry.permissions }}</td>
              <td class="mono-cell">{{ entry.owner }}</td>
              <td class="mono-cell">{{ formatDate(entry.modified) }}</td>
              <td class="actions-cell" @click.stop>
                <!-- Favorite star: files only, for Phase 4 -->
                <button
                  v-if="!entry.is_dir"
                  class="row-btn star-btn"
                  :class="{ starred: isFavorite(entry.path) }"
                  @click="toggleFavorite(entry.path)"
                  :title="isFavorite(entry.path) ? 'Remove from favorites' : 'Add to favorites'"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" :fill="isFavorite(entry.path) ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="2">
                    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                  </svg>
                </button>
                <!-- Download: files only, all authenticated users -->
                <button v-if="!entry.is_dir" class="row-btn" title="Download" @click="downloadFile(entry)">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                </button>
                <!-- Rename: admin only -->
                <button v-if="canAdmin" class="row-btn" title="Rename" @click="startRename(entry)">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                </button>
                <!-- Delete: admin only -->
                <button v-if="canAdmin" class="row-btn btn-danger" title="Delete" @click="confirmDelete(entry)">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>
                </button>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <div v-if="renameEntry" class="modal-overlay" @click.self="renameEntry = null">
      <div class="modal">
        <div class="modal-title">Rename</div>
        <input v-model="renameValue" class="modal-input" @keydown.enter="doRename" @keydown.esc="renameEntry = null" />
        <div class="modal-actions">
          <button class="action-btn btn-blue" @click="doRename">Rename</button>
          <button class="action-btn btn-muted" @click="renameEntry = null">Cancel</button>
        </div>
      </div>
    </div>

    <div v-if="deleteEntry" class="modal-overlay" @click.self="deleteEntry = null">
      <div class="modal">
        <div class="modal-title">Delete "{{ deleteEntry.name }}"?</div>
        <p class="modal-body">{{ deleteEntry.is_dir ? 'Directory and all its contents will be deleted.' : 'This action cannot be undone.' }}</p>
        <div class="modal-actions">
          <button class="action-btn btn-danger-solid" @click="doDelete">Delete</button>
          <button class="action-btn btn-muted" @click="deleteEntry = null">Cancel</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../../api/client.js'
import { useScriptsStore } from '../../stores/scripts.js'

const scriptsStore = useScriptsStore()

const props = defineProps({
  path: String,
  entries: Array,
  loading: Boolean,
  userRole: { type: String, default: 'readonly' },
  sudoPassword: { type: String, default: '' },
})
const emit = defineEmits(['navigate', 'selectFile', 'refresh'])

const canAdmin = computed(() => props.userRole === 'admin')
const canUpload = computed(() => props.userRole === 'admin' || props.userRole === 'operator')

const selectedPath = ref(null)
const sortKey = ref('name')
const sortDir = ref(1)
const showMkdir = ref(false)
const mkdirName = ref('')
const renameEntry = ref(null)
const renameValue = ref('')
const deleteEntry = ref(null)

// Favorites backed by the scripts store (synced with backend DB)
onMounted(() => scriptsStore.loadFavorites())

function isFavorite(path) {
  return scriptsStore.isFavorite(path)
}

async function toggleFavorite(path) {
  if (scriptsStore.isFavorite(path)) {
    await scriptsStore.removeFavoriteByPath(path)
  } else {
    await scriptsStore.addFavorite(path)
  }
}

const parentPath = computed(() => {
  if (!props.path || props.path === '/') return null
  const parts = props.path.split('/').filter(Boolean)
  parts.pop()
  return parts.length === 0 ? '/' : '/' + parts.join('/')
})

const segments = computed(() => {
  if (!props.path) return []
  if (props.path === '/') return [{ label: '/', path: '/' }]
  const parts = props.path.split('/').filter(Boolean)
  const segs = [{ label: '/', path: '/' }]
  let acc = ''
  for (const part of parts) {
    acc += '/' + part
    segs.push({ label: part, path: acc })
  }
  return segs
})

const sorted = computed(() => {
  if (!props.entries) return []
  return [...props.entries].sort((a, b) => {
    if (a.is_dir !== b.is_dir) return a.is_dir ? -1 : 1
    let va = a[sortKey.value] ?? ''
    let vb = b[sortKey.value] ?? ''
    if (sortKey.value === 'size') { va = va ?? -1; vb = vb ?? -1 }
    if (sortKey.value === 'modified') { va = new Date(va); vb = new Date(vb) }
    return va < vb ? -sortDir.value : va > vb ? sortDir.value : 0
  })
})

function sort(key) {
  if (sortKey.value === key) sortDir.value *= -1
  else { sortKey.value = key; sortDir.value = 1 }
}
function sortArrow(key) {
  if (sortKey.value !== key) return ''
  return sortDir.value === 1 ? '↑' : '↓'
}

function handleRowClick(entry) {
  selectedPath.value = entry.path
  if (!entry.is_dir) emit('selectFile', entry)
}
function handleDblClick(entry) {
  if (entry.is_dir) emit('navigate', entry.path)
  else emit('selectFile', entry)
}

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

async function createDir() {
  if (!mkdirName.value.trim()) return
  const newPath = props.path === '/'
    ? `/${mkdirName.value.trim()}`
    : `${props.path}/${mkdirName.value.trim()}`
  try {
    await api.post('/files/mkdir', { path: newPath })
    showMkdir.value = false
    mkdirName.value = ''
    emit('refresh')
  } catch (e) {
    alert(e.response?.data?.detail || 'Failed to create folder')
  }
}

async function uploadFile(e) {
  const files = e.target.files
  for (const file of files) {
    const form = new FormData()
    form.append('file', file)
    try {
      await api.post(`/files/upload?path=${encodeURIComponent(props.path)}`, form)
    } catch (err) {
      alert(`Upload failed: ${err.response?.data?.detail || err.message || 'Unknown error'}`)
    }
  }
  e.target.value = ''
  emit('refresh')
}

async function downloadFile(entry) {
  try {
    const headers = {}
    if (props.sudoPassword) headers['X-Sudo-Password'] = props.sudoPassword
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
    alert(`Download failed: ${e.response?.data?.detail || e.message || 'Unknown error'}`)
  }
}

function startRename(entry) {
  renameEntry.value = entry
  renameValue.value = entry.name
}

async function doRename() {
  if (!renameValue.value.trim()) return
  const parts = renameEntry.value.path.split('/')
  parts[parts.length - 1] = renameValue.value.trim()
  const newPath = parts.join('/')
  try {
    await api.post('/files/rename', { source: renameEntry.value.path, destination: newPath })
    renameEntry.value = null
    emit('refresh')
  } catch (e) {
    alert(e.response?.data?.detail || 'Rename failed')
  }
}

function confirmDelete(entry) { deleteEntry.value = entry }

async function doDelete() {
  try {
    await api.delete(`/files/delete?path=${encodeURIComponent(deleteEntry.value.path)}`)
    deleteEntry.value = null
    emit('refresh')
  } catch (e) {
    alert(e.response?.data?.detail || 'Delete failed')
  }
}
</script>

<style scoped>
.file-list { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
.list-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 12px; border-bottom: 1px solid var(--border); gap: 10px; flex-shrink: 0;
  background: var(--surface);
}
.breadcrumb { display: flex; align-items: center; overflow-x: auto; flex: 1; gap: 0; }
.breadcrumb-sep { color: var(--text-dim); padding: 0 2px; font-family: var(--font-mono); font-size: 11px; }
.breadcrumb-btn {
  background: none; border: none; padding: 2px 4px;
  font-family: var(--font-mono); font-size: 11px; color: var(--text-muted);
  cursor: pointer; border-radius: 3px; transition: color 0.1s; white-space: nowrap;
}
.breadcrumb-btn:hover { color: var(--accent-blue); }
.toolbar-actions { display: flex; gap: 6px; flex-shrink: 0; }
.action-btn {
  display: flex; align-items: center; gap: 5px;
  background: none; border: 1px solid var(--border);
  padding: 4px 10px; border-radius: 4px; font-size: 11px;
  font-family: var(--font-mono); cursor: pointer; color: var(--text-muted);
  transition: all 0.15s; text-decoration: none;
}
.btn-blue:hover { border-color: var(--accent-blue); color: var(--accent-blue); }
.btn-green:hover { border-color: var(--accent-green); color: var(--accent-green); }
.btn-muted:hover { border-color: var(--border-bright); color: var(--text); }
.btn-danger { border-color: transparent; }
.btn-danger:hover { border-color: var(--accent-red); color: var(--accent-red); }
.btn-danger-solid { background: var(--accent-red); color: #fff; border-color: var(--accent-red); }
.hidden-input { display: none; }
.mkdir-bar {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 12px; background: var(--surface-2); border-bottom: 1px solid var(--border); flex-shrink: 0;
}
.mkdir-input {
  flex: 1; max-width: 280px; background: var(--surface); border: 1px solid var(--border-bright);
  padding: 4px 8px; border-radius: 4px; font-family: var(--font-mono); font-size: 12px;
  color: var(--text); outline: none;
}
.mkdir-input:focus { border-color: var(--accent-blue); }
.table-wrap { flex: 1; overflow-y: auto; }
.files-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.files-table th {
  font-family: var(--font-mono); font-size: 9px; letter-spacing: 1.5px;
  color: var(--text-muted); text-align: left; padding: 8px 12px;
  border-bottom: 1px solid var(--border); background: var(--surface-2);
  cursor: pointer; user-select: none; white-space: nowrap; position: sticky; top: 0; z-index: 1;
}
.files-table th:hover { color: var(--text); }
.sort-arrow { color: var(--accent-blue); margin-left: 2px; }
.file-row { cursor: pointer; transition: background 0.1s; }
.file-row:hover { background: var(--surface-2); }
.file-row.selected { background: var(--surface-3); }
.file-row td { padding: 7px 12px; border-bottom: 1px solid var(--border); }
.parent-row { opacity: 0.7; }
.parent-row:hover { opacity: 1; }
.parent-label { color: var(--text-muted); font-style: italic; }
.name-cell { display: flex; align-items: center; gap: 7px; font-size: 12px; color: var(--text-bright); }
.icon-dir { color: var(--accent-yellow); flex-shrink: 0; }
.icon-file { color: var(--text-muted); flex-shrink: 0; }
.mono-cell { font-family: var(--font-mono); color: var(--text-muted); white-space: nowrap; }
.perm-cell { letter-spacing: 0.5px; }
.actions-cell { display: flex; gap: 4px; align-items: center; }
.row-btn {
  background: none; border: none; padding: 3px 5px; color: var(--text-dim);
  cursor: pointer; border-radius: 3px; display: flex; align-items: center; transition: color 0.1s;
  text-decoration: none;
}
.row-btn:hover { color: var(--text); }
.row-btn.btn-danger:hover { color: var(--accent-red); }
.star-btn { color: var(--text-dim); }
.star-btn:hover { color: var(--accent-yellow); }
.star-btn.starred { color: var(--accent-yellow); }
.loading-cell { padding: 12px; }
.skeleton { height: 14px; background: var(--surface-2); border-radius: 4px; margin-bottom: 8px; animation: shimmer 1.4s infinite; }
@keyframes shimmer { 0%,100%{opacity:.4} 50%{opacity:.8} }
.empty-cell { text-align: center; padding: 40px; color: var(--text-muted); }
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.55);
  display: flex; align-items: center; justify-content: center; z-index: 200;
}
.modal { background: var(--surface); border: 1px solid var(--border-bright); border-radius: 8px; padding: 24px; min-width: 320px; }
.modal-title { font-weight: 600; margin-bottom: 12px; font-size: 14px; }
.modal-body { color: var(--text-muted); font-size: 13px; margin-bottom: 16px; }
.modal-input {
  width: 100%; background: var(--surface-2); border: 1px solid var(--border-bright);
  padding: 7px 10px; border-radius: 5px; color: var(--text);
  font-family: var(--font-mono); font-size: 13px; outline: none; margin-bottom: 14px;
}
.modal-input:focus { border-color: var(--accent-blue); }
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; }
</style>
