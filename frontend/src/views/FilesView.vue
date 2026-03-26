<template>
  <div class="files-view">

    <!-- Tree + List horizontal split layout -->
    <Splitter layout="horizontal" class="files-splitter">

      <!-- Left: directory tree -->
      <SplitterPanel :size="22" :minSize="12" class="tree-panel">
        <div class="tree-panel-header">
          <i class="pi pi-folder tree-header-icon" />
          <span class="tree-header-label">FILESYSTEM</span>
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
        <div class="tree-scroll">
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
import { VueMonacoEditor } from '@guolao/vue-monaco-editor'
import { useRoute } from 'vue-router'
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

onMounted(loadDir)
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
  font-size: 11px;
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
  font-size: 10px;
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
.editor-spinner { font-size: 24px; }
.monaco-editor-wrap { height: calc(100vh - 120px); }
</style>
