<template>
  <Splitter style="height: calc(100vh - var(--header-height) - 48px)">

    <!-- ── Left: favorites list ─────────────────────────────────────────── -->
    <SplitterPanel :size="25" :minSize="20">
      <Listbox
        :model-value="listboxItem"
        :options="store.favorites"
        optionLabel="path"
        :filter="true"
        filterPlaceholder="Search scripts…"
        emptyMessage="No scripts favorited yet."
        emptyFilterMessage="No results."
        class="w-full h-full border-noround"
        @change="onListboxChange"
      >
        <template #option="{ option }">
          <div class="list-option">
            <Tag :value="shortRunner(option.runner)" severity="info" class="runner-tag" />
            <div class="option-info">
              <span class="option-name">{{ fileName(option.path) }}</span>
              <span class="option-dir">{{ dirName(option.path) }}</span>
            </div>
            <div class="option-flags">
              <Badge v-if="!option.exists"    value="!" severity="danger"  v-tooltip="'File not found'" />
              <Badge v-if="option.admin_only" value="A" severity="help"    v-tooltip="'Admin only'" />
              <Badge v-if="option.run_as_root" value="R" severity="warn"   v-tooltip="'Runs as root'" />
            </div>
          </div>
        </template>
      </Listbox>
    </SplitterPanel>

    <!-- ── Right: detail + execution ───────────────────────────────────── -->
    <SplitterPanel :size="75">
      <!-- Nothing selected -->
      <div v-if="!selected" class="empty-detail">
        <i class="pi pi-code empty-detail-icon" />
        <span class="empty-detail-text">Select a script from the list</span>
      </div>

      <!-- Script selected -->
      <div v-else class="detail-panel">

        <!-- Header toolbar -->
        <Toolbar class="detail-toolbar">
          <template #start>
            <Tag :value="selected.runner" severity="info" class="runner-tag" />
            <span class="detail-filename">{{ fileName(selected.path) }}</span>
            <Button
              :label="selected.path"
              text size="small"
              icon="pi pi-folder-open"
              class="path-btn"
              v-tooltip.bottom="'Open in Files'"
              @click="openInFiles(selected.path)"
            />
          </template>
          <template #end v-if="isAdmin">
            <ToggleButton
              v-model="selected.run_as_root"
              onLabel="Root ON" offLabel="Root OFF"
              onIcon="pi pi-lock" offIcon="pi pi-unlock"
              class="mr-2"
              size="small"
              @change="toggleFlag('run_as_root')"
            />
            <ToggleButton
              v-model="selected.admin_only"
              onLabel="Admin Only" offLabel="All Users"
              onIcon="pi pi-shield" offIcon="pi pi-users"
              class="mr-2"
              size="small"
              @change="toggleFlag('admin_only')"
            />
            <Button
              icon="pi pi-star-fill"
              label="Remove"
              severity="secondary"
              outlined
              size="small"
              @click="removeFavorite"
            />
          </template>
        </Toolbar>

        <!-- Execution bar -->
        <div class="exec-section">
          <InputGroup>
            <InputGroupAddon><i class="pi pi-terminal" /></InputGroupAddon>
            <InputText v-model="scriptArgs" placeholder="Arguments (space-separated)" />
            <Password
              v-if="selected.run_as_root"
              v-model="sudoPassword"
              placeholder="sudo password"
              :feedback="false"
              toggleMask
            />
            <Button
              :label="polling ? 'Running…' : 'Run'"
              :icon="polling ? 'pi pi-spin pi-spinner' : 'pi pi-play'"
              :disabled="polling || !selected.exists"
              :severity="polling ? 'warning' : 'success'"
              @click="runScript"
            />
            <Button
              v-if="execId && !polling"
              icon="pi pi-trash"
              severity="secondary"
              v-tooltip.top="'Clear output'"
              @click="clearOutput"
            />
          </InputGroup>
          <Message v-if="!selected.exists" severity="warn" :closable="false" class="mt-2">
            Script not found on disk — it may have been moved or deleted.
          </Message>
        </div>

        <!-- Tabs -->
        <Tabs v-model:value="activeTab" class="detail-tabs">
          <TabList>
            <Tab value="0">Output</Tab>
            <Tab value="1" @click="loadHistory">History</Tab>
          </TabList>

          <TabPanels class="tab-panels-wrap">
            <!-- Output panel -->
            <TabPanel value="0" class="output-panel">
              <div v-if="!execId" class="empty-run">
                <i class="pi pi-play-circle empty-run-icon" />
                <span class="empty-run-text">Press Run to execute the script.</span>
              </div>
              <template v-else>
                <div class="terminal-status">
                  <Tag v-if="polling"                    value="RUNNING"           severity="warning" icon="pi pi-spin pi-spinner" />
                  <Tag v-else-if="currentExitCode === 0" value="EXIT 0 ✓"          severity="success" />
                  <Tag v-else-if="currentExitCode != null" :value="`EXIT ${currentExitCode}`" severity="danger" />
                  <span class="exec-time">{{ execStarted }}</span>
                </div>
                <pre ref="terminalEl" class="terminal-output">{{ outputLines.join('\n') }}</pre>
              </template>
            </TabPanel>

            <!-- History panel -->
            <TabPanel value="1" class="history-panel">
              <DataTable
                :value="history"
                :loading="historyLoading"
                v-model:expanded-rows="expandedHistoryRows"
                dataKey="id"
                size="small"
                removableSort
                class="history-table"
              >
                <template #empty>
                  <div class="history-empty">No executions yet.</div>
                </template>

                <Column expander style="width: 2rem" />

                <Column header="EXIT" style="width: 70px">
                  <template #body="{ data }">
                    <Tag
                      :value="String(data.exit_code ?? '…')"
                      :severity="data.exit_code === 0 ? 'success' : data.exit_code == null ? 'warn' : 'danger'"
                    />
                  </template>
                </Column>

                <Column field="started_at" header="DATE" sortable>
                  <template #body="{ data }">
                    <span class="cell-date">{{ formatDate(data.started_at) }}</span>
                  </template>
                </Column>

                <Column header="DURATION">
                  <template #body="{ data }">
                    <span class="cell-duration">{{ duration(data) }}</span>
                  </template>
                </Column>

                <Column field="triggered_by" header="USER">
                  <template #body="{ data }">
                    <Chip :label="data.triggered_by" class="history-chip" />
                  </template>
                </Column>

                <Column header="ROOT" style="width: 50px">
                  <template #body="{ data }">
                    <i v-if="data.run_as_root" class="pi pi-lock root-lock" />
                  </template>
                </Column>

                <template #expansion="{ data }">
                  <pre class="history-output">{{ data.output || '(no output)' }}</pre>
                </template>
              </DataTable>
            </TabPanel>
          </TabPanels>
        </Tabs>

      </div>
    </SplitterPanel>

  </Splitter>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import Splitter from 'primevue/splitter'
import SplitterPanel from 'primevue/splitterpanel'
import Listbox from 'primevue/listbox'
import Tag from 'primevue/tag'
import Badge from 'primevue/badge'
import Toolbar from 'primevue/toolbar'
import Button from 'primevue/button'
import ToggleButton from 'primevue/togglebutton'
import InputGroup from 'primevue/inputgroup'
import InputGroupAddon from 'primevue/inputgroupaddon'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Message from 'primevue/message'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Chip from 'primevue/chip'
import api from '../api/client.js'
import { useScriptsStore } from '../stores/scripts.js'
import { useAuthStore } from '../stores/auth.js'

const store = useScriptsStore()
const auth = useAuthStore()
const router = useRouter()
const toast = useToast()
const confirm = useConfirm()

const isAdmin = auth.role === 'admin'

// Listbox binding (actual store object) vs. working copy (for mutation)
const listboxItem = ref(null)
const selected = ref(null)

const sudoPassword = ref('')
const scriptArgs = ref('')
const activeTab = ref('0')

// Execution state
const execId = ref(null)
const polling = ref(false)
const outputLines = ref([])
const currentExitCode = ref(null)
const execStarted = ref('')
const activeWs = ref(null)
const terminalEl = ref(null)

// History state
const history = ref([])
const historyLoading = ref(false)
const expandedHistoryRows = ref({})

onMounted(() => store.loadFavorites())
onUnmounted(() => closeWs())

// ── Helpers ──────────────────────────────────────────────────────────────────

function fileName(path) { return path.split('/').pop() }
function dirName(path) { const p = path.split('/'); p.pop(); return p.join('/') || '/' }
function shortRunner(runner) {
  if (!runner) return '?'
  const name = runner.split('/').pop()
  return name.length > 8 ? name.slice(0, 7) + '…' : name
}
function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' })
}
function duration(exec) {
  if (!exec.ended_at || !exec.started_at) return exec.running ? 'running' : '—'
  const ms = new Date(exec.ended_at) - new Date(exec.started_at)
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`
}

// ── Selection ─────────────────────────────────────────────────────────────────

function onListboxChange(e) {
  closeWs()
  execId.value = null
  outputLines.value = []
  currentExitCode.value = null
  activeTab.value = '0'
  history.value = []
  expandedHistoryRows.value = {}
  listboxItem.value = e.value
  selected.value = e.value ? { ...e.value } : null
}

function openInFiles(path) {
  router.push({ path: '/files', query: { dir: dirName(path) } })
}

// ── Execution ─────────────────────────────────────────────────────────────────

function closeWs() {
  if (activeWs.value) { activeWs.value.close(); activeWs.value = null }
  polling.value = false
}

function runScript() {
  if (!selected.value || polling.value) return
  const args = scriptArgs.value.trim() ? scriptArgs.value.trim().split(/\s+/) : []
  outputLines.value = []
  currentExitCode.value = null
  execStarted.value = formatDate(new Date().toISOString())
  execId.value = Date.now()
  activeTab.value = '0'
  polling.value = true

  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const url = `${proto}://${window.location.host}/api/scripts/favorites/${selected.value.id}/run-ws?token=${encodeURIComponent(auth.token)}`
  const ws = new WebSocket(url)
  activeWs.value = ws

  ws.onopen = () => ws.send(JSON.stringify({
    sudo_password: selected.value.run_as_root ? (sudoPassword.value || null) : null,
    args,
  }))

  ws.onmessage = async (event) => {
    let msg
    try { msg = JSON.parse(event.data) } catch { return }
    if (msg.type === 'line') {
      outputLines.value.push(msg.content)
      await nextTick()
      if (terminalEl.value) terminalEl.value.scrollTop = terminalEl.value.scrollHeight
    } else if (msg.type === 'done') {
      currentExitCode.value = msg.exit_code
      activeWs.value = null
      polling.value = false
    } else if (msg.type === 'error') {
      outputLines.value.push(`Error: ${msg.detail}`)
      activeWs.value = null
      polling.value = false
    }
  }

  ws.onclose = () => {
    if (activeWs.value === ws) { activeWs.value = null; polling.value = false }
  }
  ws.onerror = () => {
    outputLines.value.push('WebSocket connection error')
    activeWs.value = null
    polling.value = false
  }
}

function clearOutput() {
  execId.value = null
  outputLines.value = []
  currentExitCode.value = null
}

// ── Admin config ──────────────────────────────────────────────────────────────

async function toggleFlag(flag) {
  if (!selected.value) return
  const newVal = selected.value[flag]  // ToggleButton already flipped the v-model
  try {
    const updated = await store.updateFavorite(selected.value.id, { [flag]: newVal })
    selected.value = { ...updated }
    listboxItem.value = store.favorites.find(f => f.id === updated.id) || null
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Update failed', detail: e.response?.data?.detail || 'Update failed', life: 5000 })
    selected.value[flag] = !newVal  // revert
  }
}

function removeFavorite() {
  if (!selected.value) return
  confirm.require({
    message: `Remove "${fileName(selected.value.path)}" from favorites?`,
    header: 'Remove Favorite',
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: 'Remove',
    rejectLabel: 'Cancel',
    acceptClass: 'p-button-danger',
    accept: async () => {
      await store.removeFavoriteByPath(selected.value.path)
      selected.value = null
      listboxItem.value = null
    },
  })
}

// ── History ───────────────────────────────────────────────────────────────────

async function loadHistory() {
  if (!selected.value || activeTab.value !== '1') return
  historyLoading.value = true
  try {
    const { data } = await api.get(`/scripts/favorites/${selected.value.id}/history`)
    history.value = data
  } catch {
    history.value = []
  } finally {
    historyLoading.value = false
  }
}
</script>

<style scoped>
/* Listbox fills its splitter panel */
:deep(.p-listbox) { height: 100%; border-radius: 0; border-top: none; border-bottom: none; border-left: none; }
:deep(.p-listbox-list-wrapper) { height: calc(100% - 42px); }

/* List item */
.list-option { display: flex; align-items: center; gap: 8px; width: 100%; }
.runner-tag { font-size: var(--text-2xs); flex-shrink: 0; }
.option-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.option-name {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  font-weight: 600;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.option-dir {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--p-text-muted-color);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.option-flags { display: flex; gap: 3px; flex-shrink: 0; }

/* Empty detail state */
.empty-detail {
  height: 100%; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 12px;
}
.empty-detail-icon { font-size: 3rem; color: var(--p-text-muted-color); }
.empty-detail-text { font-size: var(--text-sm); color: var(--p-text-muted-color); }

/* Right detail panel */
.detail-panel { height: 100%; display: flex; flex-direction: column; overflow: hidden; }

.detail-toolbar { border-radius: 0; flex-shrink: 0; }
.detail-filename { font-family: var(--font-mono); font-size: var(--text-sm); font-weight: 600; margin: 0 6px; }
.path-btn { font-family: var(--font-mono) !important; font-size: var(--text-xs) !important; }

.exec-section { padding: 10px 14px; flex-shrink: 0; border-bottom: 1px solid var(--p-surface-border); }

/* Tabs fill remaining height */
.detail-tabs { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
:deep(.detail-tabs .p-tabpanels) { flex: 1; overflow: hidden; padding: 0; }
:deep(.detail-tabs .p-tablist) { flex-shrink: 0; }

.tab-panels-wrap { height: 100%; }

.output-panel { height: 100%; display: flex; flex-direction: column; overflow: hidden; }
.history-panel { height: 100%; overflow: hidden; }

/* Empty run state */
.empty-run {
  flex: 1; height: 100%;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 12px;
}
.empty-run-icon { font-size: 3rem; color: var(--p-text-muted-color); }
.empty-run-text { font-size: var(--text-sm); color: var(--p-text-muted-color); }

/* Terminal */
.terminal-status {
  display: flex; align-items: center; gap: 10px;
  padding: 6px 14px;
  background: var(--p-surface-100);
  border-bottom: 1px solid var(--p-surface-border);
  flex-shrink: 0;
}
.exec-time {
  margin-left: auto;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--p-text-muted-color);
}
.terminal-output {
  flex: 1; overflow-y: auto;
  padding: 12px 16px;
  font-family: var(--font-mono);
  font-size: var(--text-sm); line-height: 1.7;
  color: var(--p-text-muted-color);
  white-space: pre-wrap; word-break: break-all;
  background: var(--p-surface-900);
  margin: 0;
}

/* History table */
.history-table { height: 100%; }
.history-empty {
  display: flex; align-items: center; justify-content: center;
  padding: 24px;
  font-size: var(--text-sm);
  color: var(--p-text-muted-color);
}
.cell-date { font-family: var(--font-mono); font-size: var(--text-xs); }
.cell-duration { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-muted-color); }
:deep(.history-chip) { font-size: var(--text-xs) !important; }
.root-lock { color: var(--p-yellow-500); font-size: 13px; }
.history-output {
  font-family: var(--font-mono); font-size: var(--text-xs); line-height: 1.6;
  color: var(--p-text-muted-color);
  padding: 10px 16px; white-space: pre-wrap; word-break: break-all;
  background: var(--p-surface-50); margin: 0;
  max-height: 300px; overflow-y: auto;
}

/* DataTable header normalization */
:deep(.history-table .p-datatable-thead th) { background: transparent; }
:deep(.history-table .p-datatable-column-header-content) {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 1.5px;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
  font-weight: 600;
}
:deep(.history-table .p-datatable-tbody td) { padding: 5px 10px; }
</style>
