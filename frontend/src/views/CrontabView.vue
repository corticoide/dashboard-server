<template>
  <Splitter style="height: calc(100vh - var(--header-height) - 48px)">

    <!-- ── Left: entries list ───────────────────────────────────────────── -->
    <SplitterPanel :size="30" :minSize="20">
      <DataTable
        :value="entries"
        :loading="loading"
        selectionMode="single"
        v-model:selection="editingEntry"
        dataKey="id"
        size="small"
        scrollable
        scrollHeight="flex"
        class="entries-table"
        @row-select="onRowSelect"
      >
        <template #empty>
          <div class="flex align-items-center justify-content-center py-4" style="color: var(--p-text-muted-color);">
            No cron jobs configured.
          </div>
        </template>

        <Column header="Expression">
          <template #body="{ data }">
            <div class="flex align-items-center gap-1">
              <code class="font-mono text-primary cron-expr">{{ entryExpr(data) }}</code>
              <i v-if="matchedFavorite(data)" class="pi pi-star" style="color: var(--p-yellow-500); font-size: 11px;" />
            </div>
          </template>
        </Column>

        <Column header="Description">
          <template #body="{ data }">
            <span style="font-size: 11px; color: var(--p-text-muted-color);">{{ describeEntry(data) }}</span>
          </template>
        </Column>

        <Column header="Command" style="max-width: 160px">
          <template #body="{ data }">
            <span class="font-mono cmd-cell">{{ data.command }}</span>
          </template>
        </Column>

        <Column header="" style="width: 50px">
          <template #body="{ data }">
            <Button
              v-if="isAdmin"
              icon="pi pi-trash"
              text rounded size="small"
              severity="danger"
              @click.stop="confirmDeleteEntry(data)"
            />
          </template>
        </Column>

        <template #footer v-if="isAdmin">
          <Button label="New Entry" icon="pi pi-plus" fluid outlined @click="startNew" />
        </template>
      </DataTable>
    </SplitterPanel>

    <!-- ── Right: visual editor ─────────────────────────────────────────── -->
    <SplitterPanel :size="70">
      <!-- Empty state -->
      <div v-if="!form" class="empty-editor">
        <i class="pi pi-calendar text-5xl" style="color: var(--p-text-muted-color);" />
        <span style="color: var(--p-text-muted-color);">
          {{ isAdmin ? 'Select an entry to edit, or click New Entry.' : 'Admin access required to edit crontab.' }}
        </span>
      </div>

      <!-- Non-admin with entry selected -->
      <div v-else-if="!isAdmin" class="empty-editor">
        <Message severity="info" :closable="false">Admin access required to edit entries.</Message>
      </div>

      <!-- Editor -->
      <div v-else class="editor-wrap">
        <!-- Header -->
        <Toolbar class="editor-toolbar">
          <template #start>
            <span class="font-mono text-xs" style="letter-spacing: 1.5px; color: var(--p-text-muted-color);">
              {{ editing ? 'EDIT ENTRY' : 'NEW ENTRY' }}
            </span>
          </template>
          <template #end>
            <Button icon="pi pi-times" text rounded size="small" @click="cancelEdit" />
          </template>
        </Toolbar>

        <div class="editor-body">
          <!-- Mode toggle -->
          <SelectButton
            v-model="formMode"
            :options="modeOptions"
            optionLabel="label"
            optionValue="value"
            class="mb-4"
          />

          <!-- Special string picker -->
          <template v-if="formMode === 'special'">
            <SelectButton
              v-model="form.special"
              :options="specialOptions"
              optionLabel="label"
              optionValue="value"
              :allowEmpty="false"
              class="mb-4 special-select"
            />
          </template>

          <!-- Regular schedule -->
          <template v-else>
            <!-- Quick presets -->
            <div class="mb-3">
              <div class="section-label">QUICK PRESETS</div>
              <Listbox
                v-model="selectedPreset"
                :options="quickPresets"
                optionLabel="label"
                optionValue="expr"
                class="preset-listbox"
                @change="onPresetChange"
              />
            </div>

            <!-- Field cards -->
            <div class="fields-grid mb-3">
              <Card v-for="f in fieldDefs" :key="f.key" class="field-card">
                <template #title>
                  <span class="font-mono" style="font-size: 9px; letter-spacing: 1.5px; color: var(--p-text-muted-color);">{{ f.label }}</span>
                </template>
                <template #content>
                  <Select
                    v-model="fieldTypes[f.key]"
                    :options="typeOptions(f)"
                    optionLabel="label"
                    optionValue="value"
                    size="small"
                    fluid
                  />
                  <!-- Step -->
                  <InputNumber
                    v-if="fieldTypes[f.key] === 'step'"
                    v-model="fieldValues[f.key].step"
                    :min="1" :max="f.max"
                    fluid class="mt-2" size="small"
                  />
                  <!-- At — named (month/dow) -->
                  <Select
                    v-else-if="fieldTypes[f.key] === 'at' && f.names"
                    v-model="fieldValues[f.key].at"
                    :options="namedOptions(f)"
                    optionLabel="label"
                    optionValue="value"
                    fluid class="mt-2" size="small"
                  />
                  <!-- At — numeric -->
                  <InputNumber
                    v-else-if="fieldTypes[f.key] === 'at'"
                    v-model="fieldValues[f.key].at"
                    :min="f.min" :max="f.max"
                    fluid class="mt-2" size="small"
                  />
                  <!-- Range -->
                  <div v-else-if="fieldTypes[f.key] === 'range'" class="range-row mt-2">
                    <InputNumber v-model="fieldValues[f.key].from" :min="f.min" :max="f.max" size="small" fluid />
                    <span class="range-dash">–</span>
                    <InputNumber v-model="fieldValues[f.key].to" :min="f.min" :max="f.max" size="small" fluid />
                  </div>
                  <div class="field-expr font-mono text-primary font-bold text-center mt-2">
                    {{ fieldExpr(f.key) }}
                  </div>
                </template>
              </Card>
            </div>

            <!-- Expression preview + manual override -->
            <div class="mb-3">
              <div class="flex align-items-center gap-2 mb-2">
                <Chip :label="currentExpr" icon="pi pi-code" class="font-mono" style="font-size: 13px;" />
                <Tag :value="currentDesc" severity="secondary" />
              </div>
              <div class="section-label">MANUAL OVERRIDE</div>
              <InputGroup>
                <InputGroupAddon><i class="pi pi-pencil" /></InputGroupAddon>
                <InputText v-model="manualExpr" placeholder="* * * * *" class="font-mono" />
                <Button label="Apply" @click="applyManual" />
              </InputGroup>
            </div>
          </template>

          <!-- Command -->
          <Fieldset legend="COMMAND" class="mb-3">
            <div v-if="scriptsStore.favorites.length" class="fav-chips mb-2">
              <span style="font-size: 11px; color: var(--p-text-muted-color);">From favorites:</span>
              <Chip
                v-for="fav in scriptsStore.favorites.filter(f => f.exists)"
                :key="fav.id"
                :label="fileName(fav.path)"
                icon="pi pi-code"
                class="fav-chip"
                @click="form.command = buildCommand(fav)"
              />
            </div>
            <InputText v-model="form.command" placeholder="/path/to/script.sh" fluid />
          </Fieldset>

          <!-- Comment -->
          <Fieldset legend="COMMENT (optional)" class="mb-3">
            <InputText v-model="form.comment" placeholder="Description of this job" fluid />
          </Fieldset>

          <!-- Footer -->
          <Divider />
          <div class="flex gap-2 justify-content-end align-items-center">
            <Message v-if="saveError" severity="error" :closable="false" class="save-error">{{ saveError }}</Message>
            <Button label="Cancel" severity="secondary" text @click="cancelEdit" />
            <Button
              :label="editing ? 'Update' : 'Add Entry'"
              icon="pi pi-check"
              :loading="saving"
              @click="saveEntry"
            />
          </div>
        </div>
      </div>
    </SplitterPanel>

  </Splitter>
</template>

<script setup>
import { ref, computed, reactive, watch, onMounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import Splitter from 'primevue/splitter'
import SplitterPanel from 'primevue/splitterpanel'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Toolbar from 'primevue/toolbar'
import SelectButton from 'primevue/selectbutton'
import Listbox from 'primevue/listbox'
import Card from 'primevue/card'
import Select from 'primevue/select'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import InputGroup from 'primevue/inputgroup'
import InputGroupAddon from 'primevue/inputgroupaddon'
import Fieldset from 'primevue/fieldset'
import Divider from 'primevue/divider'
import Message from 'primevue/message'
import Tag from 'primevue/tag'
import Chip from 'primevue/chip'
import api from '../api/client.js'
import { useAuthStore } from '../stores/auth.js'
import { useScriptsStore } from '../stores/scripts.js'

const toast = useToast()
const confirm = useConfirm()
const auth = useAuthStore()
const scriptsStore = useScriptsStore()
const isAdmin = auth.role === 'admin'

const entries = ref([])
const loading = ref(false)
const saving = ref(false)
const saveError = ref('')
const editing = ref(null)
const editingEntry = ref(null)  // DataTable selection binding
const form = ref(null)
const formMode = ref('regular')  // 'regular' | 'special'

const modeOptions = [
  { label: 'Regular schedule', value: 'regular' },
  { label: 'Special string',   value: 'special' },
]

watch(formMode, (val) => {
  if (form.value) form.value.is_special = val === 'special'
})

// ── Field definitions ─────────────────────────────────────────────────────────

const fieldDefs = [
  { key: 'minute', label: 'MINUTE',  unit: 'minute',  min: 0, max: 59, names: null, nameOffset: 0 },
  { key: 'hour',   label: 'HOUR',    unit: 'hour',    min: 0, max: 23, names: null, nameOffset: 0 },
  { key: 'dom',    label: 'DAY',     unit: 'day',     min: 1, max: 31, names: null, nameOffset: 0 },
  { key: 'month',  label: 'MONTH',   unit: 'month',   min: 1, max: 12,
    names: ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'], nameOffset: 1 },
  { key: 'dow',    label: 'WEEKDAY', unit: 'weekday', min: 0, max: 6,
    names: ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'], nameOffset: 0 },
]

const fieldTypes = reactive({ minute:'every', hour:'every', dom:'every', month:'every', dow:'every' })
const fieldValues = reactive({
  minute: { step: 5,  at: 0, from: 0, to: 30 },
  hour:   { step: 2,  at: 0, from: 0, to: 12 },
  dom:    { step: 1,  at: 1, from: 1, to: 15 },
  month:  { step: 1,  at: 1, from: 1, to: 6  },
  dow:    { step: 1,  at: 1, from: 1, to: 5  },
})
const manualExpr = ref('* * * * *')
const selectedPreset = ref(null)

function typeOptions(f) {
  return [
    { label: `Every ${f.unit}`, value: 'every' },
    { label: `Every N ${f.unit}s`, value: 'step' },
    { label: 'At specific', value: 'at' },
    { label: 'Range', value: 'range' },
  ]
}
function namedOptions(f) {
  return f.names.map((name, idx) => ({ label: `${idx + f.nameOffset} – ${name}`, value: idx + f.nameOffset }))
}

// ── Quick presets ─────────────────────────────────────────────────────────────

const quickPresets = [
  { label: 'Every minute',   expr: '* * * * *' },
  { label: 'Every 5 min',    expr: '*/5 * * * *' },
  { label: 'Every 15 min',   expr: '*/15 * * * *' },
  { label: 'Hourly',         expr: '0 * * * *' },
  { label: 'Daily midnight', expr: '0 0 * * *' },
  { label: 'Daily 6 AM',     expr: '0 6 * * *' },
  { label: 'Weekly Mon',     expr: '0 0 * * 1' },
  { label: 'Monthly 1st',    expr: '0 0 1 * *' },
]

const specialOptions = [
  { value: '@reboot',   label: 'At system reboot' },
  { value: '@hourly',   label: 'Every hour' },
  { value: '@daily',    label: 'Every day (midnight)' },
  { value: '@midnight', label: 'Every day (midnight, alias)' },
  { value: '@weekly',   label: 'Every week (Sunday midnight)' },
  { value: '@monthly',  label: 'Every month (1st midnight)' },
  { value: '@yearly',   label: 'Every year (Jan 1st midnight)' },
]

function onPresetChange(e) {
  if (e.value) applyExprToFields(e.value)
}

// ── Expression logic ──────────────────────────────────────────────────────────

function fieldExpr(key) {
  const t = fieldTypes[key], v = fieldValues[key]
  if (t === 'every') return '*'
  if (t === 'step')  return `*/${v.step || 1}`
  if (t === 'at')    return String(v.at ?? 0)
  if (t === 'range') return `${v.from}-${v.to}`
  return '*'
}

const currentExpr = computed(() => fieldDefs.map(f => fieldExpr(f.key)).join(' '))

function applyExprToFields(expr) {
  const parts = expr.trim().split(/\s+/)
  if (parts.length !== 5) return
  const keys = ['minute','hour','dom','month','dow']
  keys.forEach((key, i) => {
    const val = parts[i]
    if (val === '*') {
      fieldTypes[key] = 'every'
    } else if (val.startsWith('*/')) {
      fieldTypes[key] = 'step'
      fieldValues[key].step = parseInt(val.slice(2)) || 1
    } else if (val.includes('-')) {
      fieldTypes[key] = 'range'
      const [a, b] = val.split('-')
      fieldValues[key].from = parseInt(a) || 0
      fieldValues[key].to = parseInt(b) || 0
    } else {
      fieldTypes[key] = 'at'
      fieldValues[key].at = parseInt(val) || 0
    }
  })
  manualExpr.value = expr
}

function applyManual() { applyExprToFields(manualExpr.value) }

// ── Human-readable description ────────────────────────────────────────────────

const WEEKDAY_LONG = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday']
const MONTH_LONG = ['January','February','March','April','May','June','July','August','September','October','November','December']
function fmt2(n) { return String(n).padStart(2,'0') }
function timeStr(h, m) {
  const hh = parseInt(h), mm = parseInt(m)
  if (isNaN(hh) || isNaN(mm)) return `${h}:${m}`
  const suf = hh < 12 ? 'AM' : 'PM'
  const dh = hh === 0 ? 12 : hh > 12 ? hh - 12 : hh
  return `${dh}:${fmt2(mm)} ${suf}`
}
function describeDow(dow) {
  if (dow === '*') return null
  if (dow.startsWith('*/')) return `every ${dow.slice(2)} weekdays`
  const days = dow.split(',').map(d => WEEKDAY_LONG[parseInt(d)] || d)
  return days.length === 1 ? `on ${days[0]}s` : `on ${days.join(' & ')}`
}
function describeDom(dom) {
  if (dom === '*') return null
  const n = parseInt(dom)
  if (!isNaN(n)) {
    const suf = n === 1 ? 'st' : n === 2 ? 'nd' : n === 3 ? 'rd' : 'th'
    return `on the ${n}${suf}`
  }
  return `on day ${dom}`
}
function describeMonth(month) {
  if (month === '*') return null
  return `in ${month.split(',').map(m => MONTH_LONG[parseInt(m) - 1] || m).join(', ')}`
}
function describeSchedule(min, hour, dom, month, dow) {
  if (min==='*' && hour==='*' && dom==='*' && month==='*' && dow==='*') return 'Every minute'
  if (min.startsWith('*/') && hour==='*' && dom==='*' && month==='*' && dow==='*') {
    const n = min.slice(2); return n==='1' ? 'Every minute' : `Every ${n} minutes`
  }
  if (hour.startsWith('*/') && (min==='0'||min==='00') && dom==='*' && month==='*' && dow==='*') {
    return `Every ${hour.slice(2)} hours (at :00)`
  }
  const simpleTime = !/[*\/,\-]/.test(min) && !/[*\/,\-]/.test(hour)
  if (simpleTime) {
    const parts = [timeStr(hour, min)]
    const dowStr = describeDow(dow), domStr = describeDom(dom), monStr = describeMonth(month)
    if (dowStr) parts.push(dowStr)
    else if (domStr) parts.push(domStr)
    else parts.push('daily')
    if (monStr) parts.push(monStr)
    return parts.join(', ')
  }
  return `${min} ${hour} ${dom} ${month} ${dow}`
}
const SPECIAL_DESC = {
  '@reboot': 'At system reboot', '@hourly': 'Every hour (at :00)',
  '@daily': 'Every day at midnight', '@midnight': 'Every day at midnight',
  '@weekly': 'Every Sunday at midnight', '@monthly': 'Every 1st at midnight',
  '@yearly': 'Every Jan 1st at midnight', '@annually': 'Every Jan 1st at midnight',
}
function describeEntry(e) {
  if (e.is_special) return SPECIAL_DESC[e.special?.toLowerCase()] || e.special
  return describeSchedule(e.minute, e.hour, e.dom, e.month, e.dow)
}
function entryExpr(e) {
  if (e.is_special) return e.special
  return `${e.minute} ${e.hour} ${e.dom} ${e.month} ${e.dow}`
}
const currentDesc = computed(() => {
  const parts = currentExpr.value.split(' ')
  return parts.length === 5 ? describeSchedule(...parts) : ''
})

// ── Favorites integration ─────────────────────────────────────────────────────

function matchedFavorite(e) {
  return scriptsStore.favorites.some(f => e.command.includes(f.path))
}
function fileName(path) { return path.split('/').pop() }
function buildCommand(fav) {
  const runners = { '.py':'python3', '.sh':'bash', '.rb':'ruby', '.pl':'perl', '.js':'node' }
  const ext = fav.path.slice(fav.path.lastIndexOf('.')).toLowerCase()
  const runner = runners[ext]
  return runner ? `${runner} ${fav.path}` : fav.path
}

// ── CRUD ──────────────────────────────────────────────────────────────────────

async function loadEntries() {
  loading.value = true
  try {
    const { data } = await api.get('/crontab/')
    entries.value = data
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Load failed', detail: e.response?.data?.detail || 'Failed to load crontab', life: 5000 })
  } finally {
    loading.value = false
  }
}

function startNew() {
  editing.value = null
  editingEntry.value = null
  form.value = { minute:'*', hour:'*', dom:'*', month:'*', dow:'*', command:'', comment:'', is_special:false, special:'@daily' }
  formMode.value = 'regular'
  applyExprToFields('* * * * *')
  manualExpr.value = '* * * * *'
  selectedPreset.value = null
  saveError.value = ''
}

function onRowSelect(e) {
  if (!isAdmin) return
  startEdit(e.data)
}

function startEdit(e) {
  if (!isAdmin) return
  editing.value = e
  form.value = {
    minute: e.minute, hour: e.hour, dom: e.dom, month: e.month, dow: e.dow,
    command: e.command, comment: e.comment || '',
    is_special: e.is_special, special: e.special || '@daily',
  }
  formMode.value = e.is_special ? 'special' : 'regular'
  if (!e.is_special) {
    applyExprToFields(entryExpr(e))
    manualExpr.value = entryExpr(e)
  }
  selectedPreset.value = null
  saveError.value = ''
}

function cancelEdit() {
  form.value = null
  editing.value = null
  editingEntry.value = null
}

async function saveEntry() {
  if (!form.value) return
  saving.value = true
  saveError.value = ''
  const body = {
    ...form.value,
    ...(form.value.is_special ? {} : {
      minute: fieldExpr('minute'), hour: fieldExpr('hour'), dom: fieldExpr('dom'),
      month: fieldExpr('month'), dow: fieldExpr('dow'),
    }),
  }
  try {
    const { data } = editing.value
      ? await api.put(`/crontab/${editing.value.id}`, body)
      : await api.post('/crontab/', body)
    entries.value = data
    toast.add({ severity: 'success', summary: 'Saved', detail: 'Crontab entry updated.', life: 3000 })
    cancelEdit()
  } catch (e) {
    saveError.value = e.response?.data?.detail || 'Save failed'
  } finally {
    saving.value = false
  }
}

function confirmDeleteEntry(entry) {
  confirm.require({
    message: `Delete entry "${entryExpr(entry)} ${entry.command}"?`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: 'Delete',
    rejectLabel: 'Cancel',
    acceptClass: 'p-button-danger',
    accept: () => doDelete(entry),
  })
}

async function doDelete(entry) {
  try {
    const { data } = await api.delete(`/crontab/${entry.id}`)
    entries.value = data
    if (editing.value?.id === entry.id) cancelEdit()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Delete failed', detail: e.response?.data?.detail || 'Delete failed', life: 5000 })
  }
}

onMounted(() => {
  loadEntries()
  scriptsStore.loadFavorites()
})
</script>

<style scoped>
/* Entries DataTable fills its splitter panel */
:deep(.entries-table) { height: 100%; }
:deep(.entries-table .p-datatable-wrapper) { height: calc(100% - 52px); }

.cron-expr { font-size: 12px; }
.cmd-cell { font-size: 11px; color: var(--p-text-muted-color); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: block; }

/* Empty state */
.empty-editor {
  height: 100%; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 12px; padding: 24px;
}

/* Editor */
.editor-wrap { height: 100%; display: flex; flex-direction: column; overflow: hidden; }
.editor-toolbar { border-radius: 0; flex-shrink: 0; }
.editor-body { flex: 1; overflow-y: auto; padding: 16px; }

/* Special SelectButton full-width */
.special-select { width: 100%; }
:deep(.special-select .p-selectbutton) { display: flex; flex-wrap: wrap; gap: 6px; }

/* Quick presets listbox compact */
.preset-listbox { max-height: 160px; }
.section-label {
  font-family: var(--font-mono); font-size: 9px; letter-spacing: 1.5px;
  color: var(--p-text-muted-color); margin-bottom: 6px; text-transform: uppercase;
}

/* Field cards grid */
.fields-grid {
  display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px;
}
@media (max-width: 900px) {
  .fields-grid { grid-template-columns: repeat(3, 1fr); }
}
.field-card :deep(.p-card-body) { padding: 10px; }
.field-card :deep(.p-card-title) { font-size: 9px; margin-bottom: 6px; padding: 0; }
.field-card :deep(.p-card-content) { padding: 0; display: flex; flex-direction: column; gap: 4px; }
.field-expr { font-size: 16px; }

.range-row { display: flex; align-items: center; gap: 4px; }
.range-dash { color: var(--p-text-muted-color); flex-shrink: 0; }

/* Favorites chips */
.fav-chips { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.fav-chip { cursor: pointer; }
.fav-chip:hover { filter: brightness(1.15); }

.save-error { font-size: 12px; margin: 0; }
</style>
