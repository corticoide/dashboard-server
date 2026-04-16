<template>
  <div class="logs-view">
    <div class="page-header">
      <div class="page-title">
        <i class="pi pi-file-edit page-icon" />
        <span>SYSTEM LOGS</span>
        <Tag v-if="tailing" value="TAILING" severity="info" />
        <Tag v-else-if="selectedFile" value="PAUSED" severity="warning" />
      </div>
      <div class="header-actions" v-if="selectedFile">
        <Button
          :label="tailing ? 'Pause' : 'Resume'"
          :icon="tailing ? 'pi pi-pause' : 'pi pi-play'"
          size="small"
          severity="secondary"
          @click="toggleTail"
        />
        <IconField>
          <InputIcon class="pi pi-search" />
          <InputText v-model="searchTerm" placeholder="Search…" size="small" />
        </IconField>
      </div>
    </div>

    <Splitter class="main-splitter" :gutter-size="6">
      <!-- Left: file tree -->
      <SplitterPanel :size="25" :min-size="15">
        <div class="file-tree">
          <div class="tree-header">
            <span class="tree-label">/VAR/LOG</span>
            <Button icon="pi pi-refresh" size="small" text severity="secondary" @click="loadTree" :loading="treeLoading" />
          </div>
          <div class="tree-body">
            <TreeNode
              v-for="node in tree"
              :key="node.path"
              :node="node"
              :selected-path="selectedFile?.path"
              @select="openFile"
            />
          </div>
        </div>
      </SplitterPanel>

      <!-- Right: log output -->
      <SplitterPanel :size="75" :min-size="40">
        <div v-if="!selectedFile" class="empty-state">
          Select a log file from the tree on the left.
        </div>
        <div v-else class="log-panel">
          <div class="log-header">
            <span class="log-filename">{{ selectedFile.name }}</span>
          </div>
          <div ref="logContainer" class="log-output" @scroll="onScroll">
            <div
              v-for="(line, idx) in filteredLines"
              :key="idx"
              class="log-line"
              :class="lineClass(line)"
            >{{ line }}</div>
            <div ref="logBottom" />
          </div>
        </div>
      </SplitterPanel>
    </Splitter>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onUnmounted, defineComponent, h } from 'vue'
import api from '../api/client.js'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import Splitter from 'primevue/splitter'
import SplitterPanel from 'primevue/splitterpanel'
import InputText from 'primevue/inputtext'
import IconField from 'primevue/iconfield'
import InputIcon from 'primevue/inputicon'

// ── Recursive TreeNode ────────────────────────────────────────────────────────
const TreeNode = defineComponent({
  name: 'TreeNode',
  props: { node: Object, selectedPath: String },
  emits: ['select'],
  setup(props, { emit }) {
    const open = ref(false)
    return () => {
      const n = props.node
      if (n.is_dir) {
        return h('div', { class: 'tree-dir' }, [
          h('div', {
            class: 'tree-dir-label',
            onClick: () => { open.value = !open.value },
          }, [
            h('i', { class: open.value ? 'pi pi-chevron-down tree-arrow' : 'pi pi-chevron-right tree-arrow' }),
            h('i', { class: 'pi pi-folder tree-icon' }),
            h('span', n.name),
          ]),
          open.value
            ? h('div', { class: 'tree-children' },
                (n.children || []).map(c =>
                  h(TreeNode, { node: c, selectedPath: props.selectedPath, onSelect: (f) => emit('select', f) })
                )
              )
            : null,
        ])
      }
      return h('div', {
        class: [
          'tree-file',
          { selected: props.selectedPath === n.path, unreadable: !n.readable },
        ],
        onClick: () => n.readable && emit('select', n),
      }, [
        h('i', { class: 'pi pi-file tree-icon' }),
        h('span', { class: 'tree-file-name' }, n.name),
        n.size_bytes != null
          ? h('span', { class: 'tree-file-size' }, formatSize(n.size_bytes))
          : null,
      ])
    }
  },
})

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(0)}K`
  return `${(bytes / 1_048_576).toFixed(1)}M`
}

// ── State ─────────────────────────────────────────────────────────────────────
const tree = ref([])
const treeLoading = ref(false)
const selectedFile = ref(null)
const lines = ref([])
const tailing = ref(false)
const searchTerm = ref('')
const logContainer = ref(null)
const logBottom = ref(null)
const autoScroll = ref(true)

const MAX_LINES = 2000

let ws = null

// ── Computed ──────────────────────────────────────────────────────────────────
const filteredLines = computed(() => {
  if (!searchTerm.value) return lines.value
  const term = searchTerm.value.toLowerCase()
  return lines.value.filter(l => l.toLowerCase().includes(term))
})

// ── Tree ──────────────────────────────────────────────────────────────────────
async function loadTree() {
  treeLoading.value = true
  try {
    const r = await api.get('/system-logs/tree')
    tree.value = r.data
  } catch { /* /var/log may not be accessible */ }
  finally { treeLoading.value = false }
}

// ── File selection ────────────────────────────────────────────────────────────
async function openFile(file) {
  stopTail()
  selectedFile.value = file
  lines.value = []
  searchTerm.value = ''

  try {
    const r = await api.get('/system-logs/read', { params: { path: file.path, lines: 100 } })
    lines.value = r.data.lines.slice(-MAX_LINES)
  } catch { /* unreadable */ }

  await nextTick()
  scrollToBottom()
  startTail(file.path)
}

// ── WebSocket tail ────────────────────────────────────────────────────────────
function buildWsUrl(filePath) {
  const token = localStorage.getItem('access_token')
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  return `${protocol}//${host}/api/ws/log-tail?path=${encodeURIComponent(filePath)}&token=${token}`
}

function startTail(filePath) {
  stopTail()
  tailing.value = true
  ws = new WebSocket(buildWsUrl(filePath))

  ws.onmessage = (evt) => {
    if (!tailing.value) return
    const newLines = evt.data.split('\n').filter(l => l.length > 0)
    lines.value.push(...newLines)
    if (lines.value.length > MAX_LINES) {
      lines.value = lines.value.slice(-MAX_LINES)
    }
    if (autoScroll.value) {
      nextTick(scrollToBottom)
    }
  }

  ws.onclose = () => { tailing.value = false }
  ws.onerror = () => { tailing.value = false }
}

function stopTail() {
  if (ws) {
    ws.close()
    ws = null
  }
  tailing.value = false
}

function toggleTail() {
  if (tailing.value) {
    stopTail()
  } else if (selectedFile.value) {
    startTail(selectedFile.value.path)
  }
}

// ── Scroll behaviour ──────────────────────────────────────────────────────────
function scrollToBottom() {
  logBottom.value?.scrollIntoView({ behavior: 'instant' })
}

function onScroll() {
  if (!logContainer.value) return
  const { scrollTop, scrollHeight, clientHeight } = logContainer.value
  autoScroll.value = scrollHeight - scrollTop - clientHeight < 40
}

// ── Line colouring ────────────────────────────────────────────────────────────
function lineClass(line) {
  const u = line.toUpperCase()
  if (u.includes('ERROR') || u.includes('ERR ') || u.includes('CRITICAL') || u.includes('FATAL'))
    return 'line-error'
  if (u.includes('WARN'))
    return 'line-warn'
  return ''
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────
loadTree()
onUnmounted(stopTail)
</script>

<style scoped>
.logs-view { display: flex; flex-direction: column; height: 100%; gap: 12px; }
.page-header { display: flex; align-items: center; justify-content: space-between; }
.page-title { display: flex; align-items: center; gap: 10px; font-family: var(--font-mono); font-size: var(--text-sm); font-weight: 700; letter-spacing: 2px; color: var(--p-text-muted-color); }
.page-icon { color: var(--p-blue-400); font-size: var(--text-lg); }
.header-actions { display: flex; align-items: center; gap: 8px; }
.main-splitter { flex: 1; border: none; background: transparent; }
.file-tree { display: flex; flex-direction: column; height: 100%; }
.tree-header { display: flex; align-items: center; justify-content: space-between; padding: 8px 10px; border-bottom: 1px solid var(--p-surface-border); }
.tree-label { font-family: var(--font-mono); font-size: var(--text-xs); letter-spacing: 2px; color: var(--p-text-muted-color); }
.tree-body { flex: 1; overflow-y: auto; padding: 4px; }
:deep(.tree-dir-label) { display: flex; align-items: center; gap: 6px; padding: 4px 8px; cursor: pointer; border-radius: 4px; font-size: var(--text-xs); color: var(--p-text-color); }
:deep(.tree-dir-label:hover) { background: var(--p-surface-hover); }
:deep(.tree-children) { padding-left: 14px; }
:deep(.tree-file) { display: flex; align-items: center; gap: 6px; padding: 3px 8px; border-radius: 4px; cursor: pointer; font-size: var(--text-xs); color: var(--p-text-muted-color); }
:deep(.tree-file:hover) { background: var(--p-surface-hover); color: var(--p-text-color); }
:deep(.tree-file.selected) { background: color-mix(in srgb, var(--p-blue-400) 15%, transparent); color: var(--p-blue-400); }
:deep(.tree-file.unreadable) { opacity: 0.4; cursor: not-allowed; }
:deep(.tree-file-name) { flex: 1; }
:deep(.tree-file-size) { font-family: var(--font-mono); font-size: 10px; color: var(--p-text-muted-color); }
:deep(.tree-arrow) { font-size: 10px; width: 10px; color: var(--p-text-muted-color); }
:deep(.tree-icon) { font-size: var(--text-xs); color: var(--p-text-muted-color); }
.log-panel { display: flex; flex-direction: column; height: 100%; }
.log-header { padding: 6px 12px; border-bottom: 1px solid var(--p-surface-border); }
.log-filename { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-muted-color); letter-spacing: 1px; }
.log-output { flex: 1; overflow-y: auto; padding: 8px 12px; font-family: var(--font-mono); font-size: 12px; line-height: 1.6; background: var(--p-surface-ground); }
.log-line { white-space: pre-wrap; word-break: break-all; color: var(--p-text-muted-color); }
.log-line.line-error { color: var(--p-red-400); }
.log-line.line-warn  { color: var(--p-orange-400); }
.empty-state { flex: 1; display: flex; align-items: center; justify-content: center; color: var(--p-text-muted-color); font-size: var(--text-sm); }
</style>
