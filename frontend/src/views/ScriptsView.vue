<template>
  <div class="scripts-view">
    <Splitter class="scripts-splitter">

      <!-- ── Left: favorites list ─────────────────────────────────────────── -->
      <SplitterPanel :size="25" :minSize="20">
        <div class="list-panel">

          <!-- Panel header -->
          <div class="list-panel-header">
            <i class="pi pi-code list-header-icon" />
            <span class="list-header-label">SCRIPTS</span>
            <span class="list-header-count">{{ store.favorites.length }}</span>
            <Button
              icon="pi pi-plus"
              text rounded size="small"
              class="list-header-add"
              v-tooltip.right="'Add script from Files'"
              @click="router.push('/files')"
            />
          </div>

          <!-- Shell prompt bar -->
          <div class="prompt-bar">
            <span class="prompt-user">root@srv-01</span><span class="prompt-sep">:</span><span class="prompt-path">/opt/scripts</span><span class="prompt-dollar"> $ ls -la</span>
          </div>

          <!-- Running indicator strip -->
          <div v-if="polling" class="running-strip">
            <span class="running-dot" />
            <span class="running-label">RUNNING {{ fileName(selected?.path) }}</span>
          </div>

          <!-- Listbox wrapper -->
          <div class="listbox-wrap">
            <Listbox
              :model-value="listboxItem"
              :options="store.favorites"
              optionLabel="path"
              :filter="true"
              filterPlaceholder="Search scripts…"
              emptyMessage="No scripts favorited yet."
              emptyFilterMessage="No results."
              class="scripts-listbox"
              @change="onListboxChange"
            >
              <template #option="{ option }">
                <div class="list-option" :class="{ 'option--running': polling && selected?.id === option.id }">
                  <span class="perms-str">{{ option.run_as_root ? '-rwsr-xr-x' : '-rwxr-xr-x' }}</span>
                  <Tag :value="shortRunner(option.runner)" :severity="runnerSeverity(option.runner)" class="runner-tag" />
                  <div class="option-info">
                    <span class="option-name">{{ fileName(option.path) }}</span>
                    <span class="option-dir">{{ dirName(option.path) }}</span>
                  </div>
                  <div class="option-flags">
                    <span v-if="polling && selected?.id === option.id" class="option-pulse" />
                    <Badge v-if="!option.exists"     value="!" severity="danger" v-tooltip="'File not found'" />
                    <Badge v-if="option.admin_only"  value="A" severity="help"   v-tooltip="'Admin only'" />
                    <Badge v-if="option.run_as_root" value="R" severity="warn"   v-tooltip="'Runs as root'" />
                  </div>
                  <button
                    v-if="cronCountFor(option.path) > 0"
                    class="cron-count-badge"
                    v-tooltip.right="`${cronCountFor(option.path)} cron job(s) — click to view`"
                    @click.stop="router.push('/crontab')"
                  >
                    <i class="pi pi-clock" />
                    {{ cronCountFor(option.path) }}
                  </button>
                </div>
              </template>
            </Listbox>
          </div>

        </div>
      </SplitterPanel>

      <!-- ── Right: detail + execution ───────────────────────────────────── -->
      <SplitterPanel :size="75">

        <!-- Nothing selected -->
        <div v-if="!selected" class="empty-detail">
          <i class="pi pi-code empty-icon" />
          <span class="empty-text">Select a script from the list</span>
        </div>

        <!-- Script selected -->
        <div v-else class="detail-panel">

          <!-- Header toolbar -->
          <Toolbar class="detail-toolbar">
            <template #start>
              <Tag :value="selected.runner" :severity="runnerSeverity(selected.runner)" class="runner-tag" />
              <span class="detail-filename">{{ fileName(selected.path) }}</span>
              <Button
                :label="selected.path"
                text size="small"
                icon="pi pi-folder-open"
                class="path-btn"
                v-tooltip.bottom="'Open in Files'"
                @click="openInFiles(selected.path)"
              />
              <button
                v-if="cronCountFor(selected.path) > 0"
                class="cron-toolbar-badge"
                v-tooltip.bottom="`${cronCountFor(selected.path)} cron job(s) — click to manage`"
                @click="router.push('/crontab')"
              >
                <i class="pi pi-clock" />
                {{ cronCountFor(selected.path) }} cron
              </button>
            </template>
            <template #end v-if="isAdmin">
              <ToggleButton
                v-model="selected.run_as_root"
                onLabel="Root ON" offLabel="Root OFF"
                onIcon="pi pi-lock" offIcon="pi pi-unlock"
                class="mr-2" size="small"
                @change="toggleFlag('run_as_root')"
              />
              <ToggleButton
                v-model="selected.admin_only"
                onLabel="Admin Only" offLabel="All Users"
                onIcon="pi pi-shield" offIcon="pi pi-users"
                class="mr-2" size="small"
                @change="toggleFlag('admin_only')"
              />
              <Button
                icon="pi pi-star-fill"
                label="Remove"
                severity="secondary"
                outlined size="small"
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
                  <i class="pi pi-play-circle empty-icon" />
                  <span class="empty-text">Press Run to execute the script.</span>
                </div>
                <template v-else>
                  <!-- Terminal header (matches log-panel-header pattern) -->
                  <div class="terminal-header">
                    <div class="terminal-header-title">
                      <i class="pi pi-terminal" />
                      <span class="terminal-script-name">{{ fileName(selected.path) }}</span>
                      <span class="terminal-source">output</span>
                    </div>
                    <div class="terminal-header-meta">
                      <Tag v-if="polling"                      value="RUNNING"                   severity="warning" icon="pi pi-spin pi-spinner" />
                      <Tag v-else-if="currentExitCode === 0"   value="EXIT 0 ✓"                  severity="success" />
                      <Tag v-else-if="currentExitCode != null" :value="`EXIT ${currentExitCode}`" severity="danger" />
                      <span class="exec-time">{{ execStarted }}</span>
                    </div>
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
                    <div class="empty-state">
                      <i class="pi pi-history empty-icon" />
                      <span class="empty-text">No executions yet.</span>
                    </div>
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
                    <div class="history-expansion">
                      <div class="history-expansion-header">
                        <i class="pi pi-terminal" />
                        <span class="history-expansion-date">{{ formatDate(data.started_at) }}</span>
                        <Tag
                          :value="data.exit_code === 0 ? 'EXIT 0' : data.exit_code == null ? '…' : `EXIT ${data.exit_code}`"
                          :severity="data.exit_code === 0 ? 'success' : data.exit_code == null ? 'warn' : 'danger'"
                        />
                      </div>
                      <pre class="history-output">{{ data.output || '(no output)' }}</pre>
                    </div>
                  </template>
                </DataTable>
              </TabPanel>

            </TabPanels>
          </Tabs>

        </div>
      </SplitterPanel>

    </Splitter>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
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
const route = useRoute()
const toast = useToast()
const confirm = useConfirm()

const isAdmin = computed(() => auth.isAdmin)

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

const cronEntries = ref([])

onMounted(async () => {
  await store.loadFavorites()
  loadCronEntries()
  // Handle deep-link from LogsView: ?select=<path>
  if (route.query.select) {
    const target = store.favorites.find(f => f.path === route.query.select)
    if (target) {
      listboxItem.value = target
      selected.value = { ...target }
    }
  }
})
onUnmounted(() => closeWs())

// ── Cron entries ──────────────────────────────────────────────────────────────

async function loadCronEntries() {
  try {
    const { data } = await api.get('/crontab/')
    cronEntries.value = data
  } catch {}
}

function cronCountFor(path) {
  if (!path) return 0
  return cronEntries.value.filter(e => e.command && e.command.includes(path)).length
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function fileName(path) { return path.split('/').pop() }
function dirName(path) { const p = path.split('/'); p.pop(); return p.join('/') || '/' }
function shortRunner(runner) {
  if (!runner) return '?'
  const name = runner.split('/').pop()
  return name.length > 8 ? name.slice(0, 7) + '…' : name
}
function runnerSeverity(runner) {
  if (!runner) return 'secondary'
  const name = runner.split('/').pop().toLowerCase()
  if (name.startsWith('python')) return 'info'
  if (['bash', 'sh', 'zsh', 'dash'].includes(name)) return 'warn'
  if (['node', 'nodejs', 'deno', 'bun'].includes(name)) return 'success'
  return 'secondary'
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
/* ── View container ──────────────────────────── */
.scripts-view {
  height: calc(100vh - var(--header-height) - 48px);
  display: flex;
  flex-direction: column;
}

.scripts-splitter {
  flex: 1;
  min-height: 0;
  border-radius: 8px;
  overflow: hidden;
}

/* ── Left panel ──────────────────────────────── */
.list-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  border-right: 1px solid var(--p-surface-border);
  background: var(--p-surface-900);
  overflow: hidden;
}

/* Shell prompt bar */
.prompt-bar {
  padding: 5px 10px;
  border-bottom: 1px solid var(--p-surface-border);
  flex-shrink: 0;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  line-height: 1.4;
}
.prompt-user   { color: var(--p-green-500); font-weight: 600; }
.prompt-sep    { color: var(--p-text-muted-color); }
.prompt-path   { color: var(--p-blue-500); }
.prompt-dollar { color: var(--p-text-muted-color); }

.list-panel-header {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 10px 10px 8px;
  border-bottom: 1px solid var(--p-surface-border);
  flex-shrink: 0;
}
.list-header-icon {
  font-size: var(--text-sm);
  color: var(--brand-orange);
}
.list-header-label {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 2px;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
  flex: 1;
}
.list-header-count {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  font-weight: 600;
  color: var(--brand-orange);
  background: color-mix(in srgb, var(--brand-orange) 12%, transparent);
  border-radius: 4px;
  padding: 1px 6px;
  line-height: 1.6;
}

/* ── Running strip ───────────────────────────── */
.running-strip {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 5px 10px;
  background: color-mix(in srgb, var(--p-orange-500) 8%, transparent);
  border-bottom: 1px solid color-mix(in srgb, var(--p-orange-500) 25%, transparent);
  flex-shrink: 0;
}
.running-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--p-orange-400);
  animation: pulse-dot 1s ease-in-out infinite;
  flex-shrink: 0;
}
.running-label {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 1.5px;
  color: var(--p-orange-400);
  text-transform: uppercase;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; box-shadow: 0 0 0 0 color-mix(in srgb, var(--p-orange-400) 50%, transparent); }
  50%       { opacity: 0.8; box-shadow: 0 0 0 4px transparent; }
}

/* ── Listbox wrapper ─────────────────────────── */
.listbox-wrap {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
:deep(.scripts-listbox) {
  height: 100%;
  border-radius: 0;
  border: none;
}
:deep(.scripts-listbox .p-listbox-list-wrapper) {
  height: calc(100% - 42px);
}

/* ── Permissions string ──────────────────────── */
.perms-str {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  color: var(--p-surface-600);
  letter-spacing: 0;
  flex-shrink: 0;
}

/* ── List item ───────────────────────────────── */
.list-option { display: flex; align-items: center; gap: 8px; width: 100%; }
.option--running .option-name { color: var(--p-orange-400); }

.runner-tag { font-size: var(--text-2xs); flex-shrink: 0; }

.option-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.option-name {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  font-weight: 600;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  transition: color 0.15s;
}
.option-dir {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--p-text-muted-color);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.option-flags { display: flex; gap: 3px; flex-shrink: 0; align-items: center; }
.option-pulse {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--p-orange-400);
  animation: pulse-dot 1s ease-in-out infinite;
  flex-shrink: 0;
}

/* ── Empty states ────────────────────────────── */
.empty-detail,
.empty-run {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--p-text-muted-color);
  padding: 32px 16px;
}
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 32px 16px;
  color: var(--p-text-muted-color);
}
.empty-icon { font-size: 28px; opacity: 0.4; color: var(--p-text-muted-color); }
.empty-text  { font-size: var(--text-sm); font-family: var(--font-mono); color: var(--p-text-muted-color); }

/* ── Right detail panel ──────────────────────── */
.detail-panel { height: 100%; display: flex; flex-direction: column; overflow: hidden; background: var(--p-surface-card); }

.detail-toolbar { border-radius: 0; flex-shrink: 0; }
.detail-filename {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  font-weight: 600;
  margin: 0 6px;
}
.path-btn {
  font-family: var(--font-mono) !important;
  font-size: var(--text-xs) !important;
}

.exec-section {
  padding: 10px 14px;
  flex-shrink: 0;
  border-bottom: 1px solid var(--p-surface-border);
}

/* ── Tabs ────────────────────────────────────── */
.detail-tabs { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
:deep(.detail-tabs .p-tabpanels) { flex: 1; overflow: hidden; padding: 0; }
:deep(.detail-tabs .p-tablist) { flex-shrink: 0; }
.tab-panels-wrap { height: 100%; }
.output-panel { height: 100%; display: flex; flex-direction: column; overflow: hidden; }
.history-panel { height: 100%; overflow: hidden; }

/* ── Terminal header (matches log-panel-header) ── */
.terminal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px 6px;
  border-bottom: 1px solid color-mix(in srgb, var(--brand-orange) 25%, transparent);
  background: var(--p-surface-900);
  flex-shrink: 0;
}
.terminal-header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--brand-orange);
  font-size: var(--text-sm);
}
.terminal-script-name {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--brand-orange);
}
.terminal-source {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 1.5px;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
}
.terminal-header-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}
.exec-time {
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

/* ── History table ───────────────────────────── */
.history-table { height: 100%; }
.cell-date     { font-family: var(--font-mono); font-size: var(--text-xs); }
.cell-duration { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-muted-color); }
:deep(.history-chip) { font-size: var(--text-xs) !important; }
.root-lock { color: var(--p-yellow-500); font-size: var(--text-sm); }

/* ── History expansion (matches log-panel pattern) ── */
.history-expansion {
  border-top: 1px solid var(--p-surface-border);
  background: var(--p-surface-900);
}
.history-expansion-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px 6px;
  border-bottom: 1px solid color-mix(in srgb, var(--brand-orange) 25%, transparent);
  color: var(--brand-orange);
  font-size: var(--text-sm);
}
.history-expansion-date {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--p-text-muted-color);
  flex: 1;
}
.history-output {
  font-family: var(--font-mono); font-size: var(--text-xs); line-height: 1.6;
  color: var(--p-text-muted-color);
  padding: 10px 16px; white-space: pre-wrap; word-break: break-all;
  background: var(--p-surface-900); margin: 0;
  max-height: 300px; overflow-y: auto;
}

/* Cron count badge in list item */
.cron-count-badge {
  display: inline-flex; align-items: center; gap: 3px;
  font-family: var(--font-mono); font-size: var(--text-2xs);
  color: var(--brand-orange);
  background: color-mix(in srgb, var(--brand-orange) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand-orange) 30%, transparent);
  border-radius: 10px; padding: 1px 6px;
  cursor: pointer; transition: background 0.15s, color 0.15s;
  flex-shrink: 0;
}
.cron-count-badge:hover { background: color-mix(in srgb, var(--brand-orange) 22%, transparent); }
.cron-count-badge .pi { font-size: var(--text-xs); }

/* Cron badge in toolbar */
.cron-toolbar-badge {
  display: inline-flex; align-items: center; gap: 5px;
  font-family: var(--font-mono); font-size: var(--text-xs);
  color: var(--brand-orange);
  background: color-mix(in srgb, var(--brand-orange) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand-orange) 30%, transparent);
  border-radius: 4px; padding: 3px 9px;
  cursor: pointer; transition: background 0.15s, color 0.15s;
  margin-left: 6px;
}
.cron-toolbar-badge:hover { background: color-mix(in srgb, var(--brand-orange) 20%, transparent); }
.cron-toolbar-badge .pi { font-size: var(--text-2xs); }

/* ── DataTable header normalization ──────────── */
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
