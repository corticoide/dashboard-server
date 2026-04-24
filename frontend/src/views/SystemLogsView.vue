<template>
  <div class="logs-view">
    <div class="page-header">
      <div class="page-title">
        <i class="pi pi-file-edit page-icon" />
        <span>SYSTEM LOGS</span>
        <div class="tail-indicator" v-if="selectedFile">
          <span class="tail-dot" :class="{ 'tail-dot--live': tailing, 'tail-dot--paused': !tailing }" />
          <span class="tail-label">{{ tailing ? 'LIVE' : 'PAUSED' }}</span>
        </div>
      </div>
      <div class="header-actions" v-if="selectedFile">
        <span class="line-count" v-if="lines.length > 0">{{ filteredLines.length }} lines</span>
        <Button
          :label="tailing ? 'Pause' : 'Resume'"
          :icon="tailing ? 'pi pi-pause' : 'pi pi-play'"
          size="small"
          severity="secondary"
          @click="toggleTail"
        />
        <div class="search-field">
          <i class="pi pi-search search-icon" />
          <input v-model="searchTerm" class="search-input" placeholder="Search…" />
        </div>
      </div>
    </div>

    <Splitter class="main-splitter" :gutter-size="6">
      <!-- Left: file tree -->
      <SplitterPanel :size="25" :min-size="15">
        <div class="file-tree">
          <div class="list-panel-header">
            <i class="pi pi-folder-open list-header-icon" />
            <span class="list-header-label">/VAR/LOG</span>
            <Button icon="pi pi-refresh" text rounded size="small" v-tooltip.right="'Refresh'" @click="loadTree" :loading="treeLoading" />
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
          <i class="pi pi-file-edit empty-icon" />
          <span>Select a log file from the tree.</span>
        </div>
        <div v-else class="log-panel">
          <div class="log-header">
            <div class="log-header-left">
              <i class="pi pi-file" style="font-size: 11px; color: var(--p-blue-400);" />
              <span class="log-filename">{{ selectedFile.name }}</span>
              <span class="log-path">{{ selectedFile.path }}</span>
            </div>
            <span class="log-size" v-if="selectedFile.size_bytes != null">{{ formatSize(selectedFile.size_bytes) }}</span>
          </div>
          <div ref="logContainer" class="log-output" @scroll="onScroll">
            <div
              v-for="(line, idx) in filteredLines"
              :key="idx"
              class="log-line"
              :class="lineClass(line)"
            ><span class="ln">{{ idx + 1 }}</span><span class="lc">{{ line }}</span></div>
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
import Splitter from 'primevue/splitter'
import SplitterPanel from 'primevue/splitterpanel'

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
            h('i', { class: open.value ? 'pi pi-folder-open tree-icon tree-icon--dir' : 'pi pi-folder tree-icon tree-icon--dir' }),
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

/* ── Header ──────────────────────────────────────── */
.page-header { display: flex; align-items: center; justify-content: space-between; }
.page-title {
  display: flex; align-items: center; gap: 10px;
  font-family: var(--font-mono); font-size: var(--text-sm);
  font-weight: 700; letter-spacing: 2px; color: var(--p-text-muted-color);
}
.page-icon { color: var(--brand-orange); font-size: var(--text-lg); }

/* Tail indicator */
.tail-indicator {
  display: flex; align-items: center; gap: 5px;
  padding: 3px 10px; border-radius: 20px;
  border: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
  font-family: var(--font-mono); font-size: var(--text-2xs); letter-spacing: 1.5px;
}
.tail-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.tail-dot--live   { background: var(--p-blue-400); animation: pulse-blue 1.4s ease-in-out infinite; }
.tail-dot--paused { background: var(--p-yellow-500); }
.tail-label { color: var(--p-text-muted-color); }
@keyframes pulse-blue {
  0%, 100% { opacity: 1; box-shadow: 0 0 0 0 color-mix(in srgb, var(--p-blue-400) 50%, transparent); }
  50%       { opacity: 0.7; box-shadow: 0 0 0 3px transparent; }
}

.header-actions { display: flex; align-items: center; gap: 8px; }
.search-field { position: relative; display: flex; align-items: center; }
.search-icon { position: absolute; left: 8px; font-size: 11px; color: var(--p-text-muted-color); pointer-events: none; }
.search-input {
  padding: 5px 10px 5px 28px; width: 180px;
  background: var(--p-surface-900); border: 1px solid var(--p-surface-border);
  border-radius: var(--radius-base); font-family: var(--font-mono); font-size: var(--text-sm);
  color: var(--p-text-color); outline: none; transition: var(--transition-fast);
}
.search-input:focus { border-color: var(--brand-orange); }
.line-count {
  font-family: var(--font-mono); font-size: var(--text-xs);
  color: var(--p-text-muted-color); letter-spacing: 0.5px;
}

/* ── Splitter ─────────────────────────────────────── */
.main-splitter { flex: 1; border-radius: 8px; overflow: hidden; min-height: 0; }

/* ── File tree ────────────────────────────────────── */
.file-tree {
  display: flex; flex-direction: column; height: 100%;
  background: var(--p-surface-card);
  border-right: 1px solid var(--p-surface-border);
  overflow: hidden;
}
.list-panel-header {
  display: flex; align-items: center; gap: 6px;
  padding: 10px; border-bottom: 1px solid var(--p-surface-border);
  flex-shrink: 0;
}
.list-header-icon { font-size: 12px; color: var(--brand-orange); }
.list-header-label {
  font-family: var(--font-mono); font-size: var(--text-2xs);
  letter-spacing: 2px; color: var(--p-text-muted-color); flex: 1;
}
.tree-body { flex: 1; overflow-y: auto; padding: 4px; }

:deep(.tree-dir-label) {
  display: flex; align-items: center; gap: 6px;
  padding: 4px 8px; cursor: pointer; border-radius: 4px;
  font-size: var(--text-xs); color: var(--p-text-color);
  transition: background 0.12s;
}
:deep(.tree-dir-label:hover) { background: var(--p-surface-hover); }
:deep(.tree-children) { padding-left: 14px; }
:deep(.tree-file) {
  display: flex; align-items: center; gap: 6px;
  padding: 3px 8px; border-radius: 4px; cursor: pointer;
  font-size: var(--text-xs); color: var(--p-text-muted-color);
  transition: background 0.12s, color 0.12s;
}
:deep(.tree-file:hover) { background: var(--p-surface-hover); color: var(--p-text-color); }
:deep(.tree-file.selected) {
  background: color-mix(in srgb, var(--p-blue-400) 12%, transparent);
  color: var(--p-blue-400);
  border-left: 2px solid var(--p-blue-400);
  padding-left: 6px;
}
:deep(.tree-file.unreadable) { opacity: 0.4; cursor: not-allowed; }
:deep(.tree-file-name) { flex: 1; }
:deep(.tree-file-size) {
  font-family: var(--font-mono); font-size: 10px;
  color: var(--p-text-muted-color);
  background: var(--p-surface-hover);
  padding: 1px 5px; border-radius: 3px;
}
:deep(.tree-arrow) { font-size: 10px; width: 10px; color: var(--p-text-muted-color); }
:deep(.tree-icon) { font-size: var(--text-xs); color: var(--p-text-muted-color); }
:deep(.tree-icon--dir) { color: var(--p-yellow-500); }

/* ── Log panel ────────────────────────────────────── */
.log-panel { display: flex; flex-direction: column; height: 100%; }
.log-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 6px 12px;
  border-bottom: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
  gap: 8px;
}
.log-header-left { display: flex; align-items: center; gap: 6px; min-width: 0; }
.log-filename {
  font-family: var(--font-mono); font-size: var(--text-xs);
  font-weight: 600; color: var(--p-text-color);
  letter-spacing: 0.5px;
}
.log-path {
  font-family: var(--font-mono); font-size: var(--text-xs);
  color: var(--p-text-muted-color);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.log-size {
  font-family: var(--font-mono); font-size: 10px;
  color: var(--p-text-muted-color);
  background: var(--p-surface-hover); padding: 2px 6px; border-radius: 3px;
  flex-shrink: 0;
}

/* Log output */
.log-output {
  flex: 1; overflow-y: auto; padding: 6px 0;
  font-family: var(--font-mono); font-size: 12px; line-height: 1.6;
  background: var(--p-surface-ground);
}
.log-line {
  display: flex; gap: 0; align-items: baseline;
  white-space: pre-wrap; word-break: break-all;
  padding: 0; min-height: 1.6em;
}
.log-line:hover { background: color-mix(in srgb, var(--p-surface-border) 40%, transparent); }
.ln {
  flex-shrink: 0; width: 44px; text-align: right;
  padding-right: 12px;
  color: var(--p-text-muted-color); opacity: 0.35;
  user-select: none; font-size: 10px; line-height: 1.6;
  border-right: 1px solid var(--p-surface-border);
  margin-right: 12px;
}
.lc { flex: 1; color: var(--p-text-muted-color); }
.log-line.line-error .lc { color: var(--p-red-400); }
.log-line.line-error .ln  { opacity: 0.5; color: var(--p-red-400); }
.log-line.line-warn  .lc  { color: var(--p-orange-400); }

/* ── Empty state ──────────────────────────────────── */
.empty-state {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 8px;
  color: var(--p-text-muted-color); font-size: var(--text-sm);
  font-family: var(--font-mono);
}
.empty-icon { font-size: 28px; opacity: 0.3; }
</style>
