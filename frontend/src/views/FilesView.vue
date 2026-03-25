<template>
  <div class="files-view">
    <!-- Top panel: directory tree -->
    <div class="tree-panel" :style="{ height: treePanelHeight + 'px' }">
      <div class="panel-header">
        <span class="panel-title">DIRECTORY TREE</span>
      </div>
      <div class="tree-scroll">
        <DirTree
          :node="{ name: '/', path: '/' }"
          :current-path="currentPath"
          :depth="0"
          @navigate="navigateTo"
        />
      </div>
    </div>

    <!-- Draggable divider -->
    <div class="divider" @mousedown="startResize">
      <div class="divider-handle"></div>
    </div>

    <!-- Bottom panel: file list -->
    <div class="list-panel">
      <FileList
        :path="currentPath"
        :entries="entries"
        :loading="loading"
        @navigate="navigateTo"
        @select-file="openFile"
        @refresh="loadDir"
      />
    </div>

    <!-- Monaco editor panel -->
    <Transition name="slide-right">
      <div v-if="openedFile" class="editor-panel">
        <div class="editor-header">
          <span class="editor-filename">{{ openedFile.name }}</span>
          <div class="editor-actions">
            <span v-if="editorDirty" class="unsaved-dot" title="Unsaved changes"></span>
            <button v-if="editorDirty" class="editor-btn btn-green" @click="saveFile">Save</button>
            <button class="editor-btn btn-muted" @click="closeFile">✕</button>
          </div>
        </div>
        <div v-if="fileLoading" class="editor-loading">
          <span>Loading…</span>
        </div>
        <VueMonacoEditor
          v-else
          v-model:value="editorContent"
          :language="editorLanguage"
          theme="vs-dark"
          :options="monacoOptions"
          class="monaco-editor-wrap"
          @change="editorDirty = true"
        />
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { VueMonacoEditor } from '@guolao/vue-monaco-editor'
import DirTree from '../components/files/DirTree.vue'
import FileList from '../components/files/FileList.vue'
import api from '../api/client.js'
import { useAuthStore } from '../stores/auth.js'

const auth = useAuthStore()
const currentPath = ref('/')
const entries = ref([])
const loading = ref(false)

const treePanelHeight = ref(280)

function startResize(e) {
  const startY = e.clientY
  const startH = treePanelHeight.value
  function onMove(ev) {
    treePanelHeight.value = Math.max(120, Math.min(600, startH + ev.clientY - startY))
  }
  function onUp() {
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup', onUp)
  }
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
}

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

const openedFile = ref(null)
const editorContent = ref('')
const editorLanguage = ref('plaintext')
const editorDirty = ref(false)
const fileLoading = ref(false)

const canEdit = auth.role !== 'readonly'
const monacoOptions = {
  readOnly: !canEdit,
  minimap: { enabled: false },
  fontSize: 13,
  fontFamily: "'Fira Code', monospace",
  scrollBeyondLastLine: false,
  lineNumbers: 'on',
  wordWrap: 'on',
}

async function openFile(entry) {
  if (openedFile.value && editorDirty.value) {
    if (!confirm('Discard unsaved changes?')) return
  }
  openedFile.value = entry
  editorDirty.value = false
  fileLoading.value = true
  try {
    const { data } = await api.get('/files/content', { params: { path: entry.path } })
    editorContent.value = data.content
    editorLanguage.value = data.language
  } catch (e) {
    editorContent.value = `// Error: ${e.response?.data?.detail || e.message}`
    editorLanguage.value = 'plaintext'
  } finally {
    fileLoading.value = false
  }
}

function closeFile() {
  if (editorDirty.value && !confirm('Discard unsaved changes?')) return
  openedFile.value = null
  editorContent.value = ''
  editorDirty.value = false
}

async function saveFile() {
  try {
    await api.put(`/files/content?path=${encodeURIComponent(openedFile.value.path)}`,
      { content: editorContent.value })
    editorDirty.value = false
  } catch (e) {
    alert(`Save failed: ${e.response?.data?.detail || e.message}`)
  }
}

onMounted(loadDir)
</script>

<style scoped>
.files-view {
  display: flex; flex-direction: column;
  height: calc(100vh - var(--header-height) - 48px);
  overflow: hidden; position: relative;
}
.tree-panel {
  display: flex; flex-direction: column;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 8px 8px 0 0; overflow: hidden; flex-shrink: 0;
}
.panel-header {
  padding: 8px 12px; border-bottom: 1px solid var(--border);
  background: var(--surface-2); flex-shrink: 0;
}
.panel-title {
  font-family: var(--font-mono); font-size: 9px; letter-spacing: 1.5px; color: var(--text-muted);
}
.tree-scroll { overflow-y: auto; flex: 1; padding: 4px 0; }
.divider {
  height: 6px; background: var(--border); cursor: ns-resize;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  transition: background 0.15s;
}
.divider:hover { background: var(--accent-blue); }
.divider-handle { width: 32px; height: 2px; border-radius: 1px; background: var(--text-dim); }
.list-panel {
  flex: 1; overflow: hidden; background: var(--surface);
  border: 1px solid var(--border); border-top: none;
  border-radius: 0 0 8px 8px; display: flex; flex-direction: column;
}
.editor-panel {
  position: absolute; top: 0; right: 0; bottom: 0;
  width: 55%; background: var(--surface);
  border-left: 1px solid var(--border-bright);
  border-radius: 0 8px 8px 0;
  display: flex; flex-direction: column; z-index: 10;
  box-shadow: -8px 0 30px rgba(0,0,0,0.35);
}
.editor-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 14px; border-bottom: 1px solid var(--border);
  background: var(--surface-2); flex-shrink: 0;
}
.editor-filename { font-family: var(--font-mono); font-size: 12px; color: var(--text-bright); }
.editor-actions { display: flex; align-items: center; gap: 6px; }
.unsaved-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--accent-yellow); }
.editor-btn {
  background: none; border: 1px solid var(--border); padding: 3px 10px;
  border-radius: 4px; font-size: 11px; font-family: var(--font-mono);
  cursor: pointer; color: var(--text-muted); transition: all 0.15s;
}
.btn-green:hover { border-color: var(--accent-green); color: var(--accent-green); }
.btn-muted:hover { border-color: var(--border-bright); color: var(--text); }
.editor-loading {
  flex: 1; display: flex; align-items: center; justify-content: center;
  font-family: var(--font-mono); font-size: 12px; color: var(--text-muted);
}
.monaco-editor-wrap { flex: 1; min-height: 0; }
.slide-right-enter-active, .slide-right-leave-active { transition: transform 0.2s ease, opacity 0.2s ease; }
.slide-right-enter-from, .slide-right-leave-to { transform: translateX(20px); opacity: 0; }
</style>
