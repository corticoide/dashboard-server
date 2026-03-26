<template>
  <div class="files-view">

    <!-- Sudo password bar -->
    <InputGroup class="sudo-bar">
      <InputGroupAddon>
        <i class="pi pi-lock" />
      </InputGroupAddon>
      <Password
        v-model="sudoPassword"
        placeholder="sudo password (for root-protected files)"
        :feedback="false"
        toggleMask
      />
      <Button
        v-if="sudoPassword"
        icon="pi pi-times"
        severity="secondary"
        @click="sudoPassword = ''"
      />
    </InputGroup>

    <!-- Tree + List split layout -->
    <Splitter
      layout="vertical"
      class="files-splitter"
    >
      <SplitterPanel :size="30" :minSize="10">
        <Panel
          v-model:collapsed="treeCollapsed"
          toggleable
          class="tree-panel"
        >
          <template #header>
            <span class="font-mono" style="font-size: 9px; letter-spacing: 1.5px; color: var(--p-text-muted-color); text-transform: uppercase;">
              Directory Tree
            </span>
          </template>
          <div class="tree-scroll">
            <DirTree
              :node="{ name: '/', path: '/' }"
              :current-path="currentPath"
              :depth="0"
              @navigate="navigateTo"
            />
          </div>
        </Panel>
      </SplitterPanel>

      <SplitterPanel :size="70" :minSize="30">
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
          <span class="font-mono font-semibold">{{ openedFile?.name }}</span>
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
        <i class="pi pi-spin pi-spinner" style="font-size: 1.5rem;" />
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
import { ref, computed, onMounted } from 'vue'
import { VueMonacoEditor } from '@guolao/vue-monaco-editor'
import { useRoute } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import InputGroup from 'primevue/inputgroup'
import InputGroupAddon from 'primevue/inputgroupaddon'
import Password from 'primevue/password'
import Button from 'primevue/button'
import Panel from 'primevue/panel'
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

const currentPath = ref(route.query.dir || '/')
const entries = ref([])
const loading = ref(false)
const sudoPassword = ref('')
const treeCollapsed = ref(false)

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

// Editor state
const editorVisible = ref(false)
const openedFile = ref(null)
const editorContent = ref('')
const editorLanguage = ref('plaintext')
const editorDirty = ref(false)
const fileLoading = ref(false)

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
    // Intercept close — ask user to confirm discard
    confirm.require({
      message: 'Discard unsaved changes?',
      header: 'Unsaved Changes',
      icon: 'pi pi-exclamation-triangle',
      acceptLabel: 'Discard',
      rejectLabel: 'Keep editing',
      accept: () => _closeEditor(),
      // reject: do nothing, drawer stays open (visible remains true)
    })
  } else {
    editorVisible.value = val
    if (!val) _closeEditor()
  }
}

function _closeEditor() {
  editorVisible.value = false
  openedFile.value = null
  editorContent.value = ''
  editorDirty.value = false
}

async function openFile(entry) {
  openedFile.value = entry
  editorDirty.value = false
  fileLoading.value = true
  editorVisible.value = true
  try {
    const { data } = await api.get('/files/content', {
      params: { path: entry.path },
      headers: sudoHeaders(),
    })
    editorContent.value = data.content
    editorLanguage.value = data.language
  } catch (e) {
    editorContent.value = `// Error: ${e.response?.data?.detail || e.message}`
    editorLanguage.value = 'plaintext'
  } finally {
    fileLoading.value = false
  }
}

function discardFile() {
  _closeEditor()
}

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
  display: flex; flex-direction: column;
  height: calc(100vh - var(--header-height) - 48px);
  gap: 10px;
}

.sudo-bar {
  flex-shrink: 0;
  max-width: 500px;
}

.files-splitter {
  flex: 1;
  min-height: 0;
  border-radius: 8px;
  overflow: hidden;
}

.tree-panel {
  height: 100%;
  border-radius: 0;
  border: none;
}
:deep(.tree-panel .p-panel-content) {
  height: calc(100% - 44px);
  padding: 4px 0;
  overflow-y: auto;
}

.tree-scroll {
  overflow-y: auto;
  height: 100%;
}

.list-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* Editor drawer */
.editor-header-content {
  display: flex; align-items: center; gap: 10px;
}
.editor-footer {
  display: flex; gap: 8px; justify-content: flex-end; padding: 8px 0;
}
.editor-loading {
  display: flex; align-items: center; justify-content: center;
  height: 200px; color: var(--p-text-muted-color);
}
.monaco-editor-wrap {
  height: calc(100vh - 120px);
}
</style>
