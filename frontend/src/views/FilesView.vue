<template>
  <div class="files-view">

    <!-- Tree + List horizontal split layout -->
    <Splitter layout="horizontal" class="files-splitter">

      <!-- Left: directory tree -->
      <SplitterPanel :size="22" :minSize="12" class="tree-panel">
        <div class="tree-panel-header">
          <i class="pi pi-folder tree-header-icon" />
          <span class="tree-header-label">FILESYSTEM</span>
          <button
            class="fav-filter-btn"
            :class="{ active: favoritesOnly }"
            v-tooltip.right="favoritesOnly ? 'Show all files' : 'Show script favorites only'"
            @click="favoritesOnly = !favoritesOnly"
          >
            <i class="pi pi-star" />
          </button>
          <div class="sudo-inline" v-tooltip.right="'sudo password for protected paths'">
            <i class="pi pi-lock sudo-icon" />
            <Password
              v-model="sudoPassword"
              placeholder="sudo"
              :feedback="false"
              toggleMask
              size="small"
              class="sudo-pass"
            />
          </div>
        </div>

        <!-- Favorites mode: flat list of script favorites -->
        <div v-if="favoritesOnly" class="fav-list">
          <div v-if="scriptsStore.favorites.length === 0" class="fav-empty">
            <i class="pi pi-star fav-empty-icon" />
            <span class="fav-empty-text">No script favorites yet.</span>
          </div>
          <button
            v-for="fav in scriptsStore.favorites"
            :key="fav.path"
            class="fav-item"
            @click="openFavorite(fav)"
          >
            <i class="pi pi-file-code fav-item-icon" />
            <div class="fav-item-info">
              <span class="fav-item-name">{{ basename(fav.path) }}</span>
              <span class="fav-item-dir">{{ dirname(fav.path) }}</span>
            </div>
          </button>
        </div>

        <!-- Normal mode: directory tree -->
        <div v-else class="tree-scroll">
          <DirTree
            :node="{ name: '/', path: '/' }"
            :current-path="currentPath"
            :depth="0"
            @navigate="navigateTo"
          />
        </div>
      </SplitterPanel>

      <!-- Right: file list -->
      <SplitterPanel :size="78" :minSize="40">
        <div class="list-panel">
          <FileList
            :path="currentPath"
            :entries="entries"
            :loading="loading"
            :user-role="auth.role"
            :sudo-password="sudoPassword"
            @navigate="navigateTo"
            @select-file="openFile"
            @refresh="loadDir"
          />
        </div>
      </SplitterPanel>

    </Splitter>

    <!-- Monaco Editor Drawer -->
    <Drawer
      :visible="editorVisible"
      position="right"
      style="width: 55%"
      :modal="false"
      @update:visible="handleEditorVisibleChange"
    >
      <template #header>
        <div class="editor-header-content">
          <i class="pi pi-file-edit" style="color: var(--brand-orange);" />
          <span class="editor-filename">{{ openedFile?.name }}</span>
          <Tag v-if="editorDirty" value="unsaved" severity="warn" rounded />
        </div>
      </template>

      <template #footer v-if="editorDirty && canEdit">
        <div class="editor-footer">
          <Button label="Save" icon="pi pi-save" @click="saveFile" />
          <Button label="Discard" severity="secondary" text @click="discardFile" />
        </div>
      </template>

      <div v-if="fileLoading" class="editor-loading">
        <i class="pi pi-spin pi-spinner editor-spinner" />
      </div>
      <VueMonacoEditor
        v-else-if="openedFile"
        v-model:value="editorContent"
        :language="editorLanguage"
        theme="vs-dark"
        :options="monacoOptions"
        class="monaco-editor-wrap"
        @change="editorDirty = true"
      />
    </Drawer>

  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { VueMonacoEditor, loader } from '@guolao/vue-monaco-editor'
import * as monaco from 'monaco-editor'
import editorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker'
import jsonWorker from 'monaco-editor/esm/vs/language/json/json.worker?worker'
import cssWorker from 'monaco-editor/esm/vs/language/css/css.worker?worker'
import htmlWorker from 'monaco-editor/esm/vs/language/html/html.worker?worker'
import tsWorker from 'monaco-editor/esm/vs/language/typescript/ts.worker?worker'

// Use locally bundled Monaco instead of CDN (required for CSP 'self' compliance)
self.MonacoEnvironment = {
  getWorker(_, label) {
    if (label === 'json') return new jsonWorker()
    if (label === 'css' || label === 'scss' || label === 'less') return new cssWorker()
    if (label === 'html' || label === 'handlebars' || label === 'razor') return new htmlWorker()
    if (label === 'typescript' || label === 'javascript') return new tsWorker()
    return new editorWorker()
  },
}
loader.config({ monaco })
import { useRoute } from 'vue-router'
import { useRouter } from 'vue-router'
import { useScriptsStore } from '../stores/scripts.js'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import Password from 'primevue/password'
import Button from 'primevue/button'
import Splitter from 'primevue/splitter'
import SplitterPanel from 'primevue/splitterpanel'
import Drawer from 'primevue/drawer'
import Tag from 'primevue/tag'
import DirTree from '../components/files/DirTree.vue'
import FileList from '../components/files/FileList.vue'
import api from '../api/client.js'
import { useAuthStore } from '../stores/auth.js'

const toast = useToast()
const confirm = useConfirm()
const auth = useAuthStore()
const route = useRoute()

const router = useRouter()
const scriptsStore = useScriptsStore()
const favoritesOnly = ref(false)

const currentPath  = ref(route.query.dir || '/')
const entries      = ref([])
const loading      = ref(false)
const sudoPassword = ref('')

async function loadDir() {
  loading.value = true
  try {
    const { data } = await api.get('/files/list', { params: { path: currentPath.value } })
    entries.value = data.entries
  } catch {
    entries.value = []
  } finally {
    loading.value = false
  }
}

function navigateTo(path) {
  currentPath.value = path
  loadDir()
}

async function openFavorite(fav) {
  const dir = fav.path.split('/').slice(0, -1).join('/') || '/'
  favoritesOnly.value = false
  currentPath.value = dir
  await loadDir()
  const entry = entries.value.find(e => e.path === fav.path)
  if (entry) openFile(entry)
}
function basename(p) { return p.split('/').pop() }
function dirname(p) { const parts = p.split('/'); parts.pop(); return parts.join('/') || '/' }

// Editor
const editorVisible  = ref(false)
const openedFile     = ref(null)
const editorContent  = ref('')
const editorLanguage = ref('plaintext')
const editorDirty    = ref(false)
const fileLoading    = ref(false)

const canEdit = auth.role === 'admin'
const monacoOptions = {
  readOnly: !canEdit,
  minimap: { enabled: false },
  fontSize: 13,
  fontFamily: "'Fira Code', monospace",
  scrollBeyondLastLine: false,
  lineNumbers: 'on',
  wordWrap: 'on',
}

function sudoHeaders() {
  return sudoPassword.value ? { 'X-Sudo-Password': sudoPassword.value } : {}
}

function handleEditorVisibleChange(val) {
  if (!val && editorDirty.value) {
    confirm.require({
      message: 'Discard unsaved changes?',
      header: 'Unsaved Changes',
      icon: 'pi pi-exclamation-triangle',
      acceptLabel: 'Discard',
      rejectLabel: 'Keep editing',
      accept: () => _closeEditor(),
    })
  } else {
    editorVisible.value = val
    if (!val) _closeEditor()
  }
}

function _closeEditor() {
  editorVisible.value = false
  openedFile.value    = null
  editorContent.value = ''
  editorDirty.value   = false
}

async function openFile(entry) {
  openedFile.value  = entry
  editorDirty.value = false
  fileLoading.value = true
  editorVisible.value = true
  try {
    const { data } = await api.get('/files/content', {
      params: { path: entry.path },
      headers: sudoHeaders(),
    })
    editorContent.value  = data.content
    editorLanguage.value = data.language
  } catch (e) {
    editorContent.value  = `// Error: ${e.response?.data?.detail || e.message}`
    editorLanguage.value = 'plaintext'
  } finally {
    fileLoading.value = false
  }
}

function discardFile() { _closeEditor() }

async function saveFile() {
  try {
    await api.put(
      `/files/content?path=${encodeURIComponent(openedFile.value.path)}`,
      { content: editorContent.value },
      { headers: sudoHeaders() },
    )
    editorDirty.value = false
    toast.add({ severity: 'success', summary: 'Saved', detail: openedFile.value.name, life: 3000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Save failed', detail: e.response?.data?.detail || e.message, life: 5000 })
  }
}

onMounted(() => {
  loadDir()
  scriptsStore.loadFavorites()
})
</script>

<style scoped>
.files-view {
  display: flex;
  flex-direction: column;
  height: calc(100vh - var(--header-height) - 48px);
}

.files-splitter {
  flex: 1;
  min-height: 0;
  border-radius: 8px;
  overflow: hidden;
}

/* ── Tree panel ──────────────────────────────── */
.tree-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  border-right: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
  overflow: hidden;
}

.tree-panel-header {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 10px 10px 8px;
  border-bottom: 1px solid var(--p-surface-border);
  flex-shrink: 0;
}
.tree-header-icon {
  font-size: 12px;
  color: var(--brand-orange);
}
.tree-header-label {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 2px;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
  flex: 1;
}

.sudo-inline {
  display: flex;
  align-items: center;
  gap: 4px;
}
.sudo-icon {
  font-size: var(--text-xs);
  color: var(--p-text-muted-color);
  flex-shrink: 0;
}
:deep(.sudo-pass) {
  display: flex;
  width: 80px;
}
:deep(.sudo-pass .p-password-input) {
  flex: 1;
  min-width: 0;
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  padding: 4px 6px;
}

.tree-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}

/* ── List panel ──────────────────────────────── */
.list-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* ── Editor drawer ───────────────────────────── */
.editor-header-content {
  display: flex;
  align-items: center;
  gap: 10px;
}
.editor-filename {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  font-weight: 600;
}
.editor-footer {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  padding: 8px 0;
}
.editor-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: var(--p-text-muted-color);
}
.editor-spinner { font-size: var(--text-2xl); }
.monaco-editor-wrap { height: calc(100vh - 120px); }

/* ── Favorites filter button ──────────────── */
.fav-filter-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border: none;
  background: transparent;
  border-radius: 4px;
  cursor: pointer;
  color: var(--p-text-muted-color);
  font-size: var(--text-xs);
  padding: 0;
  transition: color 0.15s, background 0.15s;
  flex-shrink: 0;
}
.fav-filter-btn:hover { color: var(--brand-orange); background: color-mix(in srgb, var(--brand-orange) 12%, transparent); }
.fav-filter-btn.active { color: var(--brand-orange); background: color-mix(in srgb, var(--brand-orange) 15%, transparent); }

/* ── Favorites list ───────────────────────── */
.fav-list {
  flex: 1;
  overflow-y: auto;
  padding: 6px 4px;
}

.fav-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 24px 12px;
  color: var(--p-text-muted-color);
}
.fav-empty-icon { font-size: 28px; opacity: 0.4; }
.fav-empty-text { font-family: var(--font-mono); font-size: var(--text-sm); text-align: center; }

.fav-item {
  display: flex;
  align-items: center;
  gap: 7px;
  width: 100%;
  padding: 6px 8px;
  border: none;
  background: transparent;
  border-radius: 5px;
  cursor: pointer;
  text-align: left;
  transition: background 0.15s, color 0.15s;
}
.fav-item:hover { background: color-mix(in srgb, var(--brand-orange) 10%, transparent); }
.fav-item-icon {
  font-size: 12px;
  color: var(--brand-orange);
  flex-shrink: 0;
}
.fav-item-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.fav-item-name {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--p-text-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.fav-item-dir {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  color: var(--p-text-muted-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 1px;
}
</style>
