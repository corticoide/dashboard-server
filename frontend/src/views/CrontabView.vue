<template>
  <div class="crontab-view">
    <Splitter class="crontab-splitter">

      <!-- ── Left: entries list ───────────────────────────────────────────── -->
      <SplitterPanel :size="30" :minSize="20">
        <div class="list-panel">
          <div class="list-panel-header">
            <i class="pi pi-clock list-header-icon" />
            <span class="list-header-label">CRON JOBS</span>
            <span class="list-header-count">{{ entries.length }}</span>
            <Button v-if="isAdmin" icon="pi pi-plus" text rounded size="small"
              v-tooltip.right="'New entry'" @click="startNew" />
            <Button icon="pi pi-refresh" text rounded size="small" :loading="loading"
              v-tooltip.right="'Refresh'" @click="loadEntries" />
          </div>
          <div class="filter-pills">
            <button class="filter-pill" :class="{ active: filterMode === 'all' }" @click="filterMode = 'all'">ALL</button>
            <button class="filter-pill filter-pill--active" :class="{ active: filterMode === 'active' }" @click="filterMode = 'active'">ACTIVE</button>
            <button class="filter-pill filter-pill--paused" :class="{ active: filterMode === 'paused' }" @click="filterMode = 'paused'">PAUSED</button>
          </div>
          <div class="table-wrap">
            <DataTable
              :value="filteredEntries" :loading="loading"
              selectionMode="single" v-model:selection="editingEntry"
              dataKey="id" size="small" scrollable scrollHeight="flex"
              class="entries-table" @row-select="onRowSelect"
              :rowClass="(data) => !data.enabled ? 'entry--paused' : ''"
            >
              <template #empty>
                <div class="empty-state">
                  <i class="pi pi-clock empty-icon" />
                  <span class="empty-text">No cron jobs configured.</span>
                </div>
              </template>
              <Column header="SCHEDULE">
                <template #body="{ data }">
                  <div class="schedule-cell">
                    <div class="expr-row">
                      <code class="cron-expr">{{ entryExpr(data) }}</code>
                      <button
                        v-if="matchedFavorite(data)"
                        class="star-link-btn"
                        v-tooltip.top="'View in Scripts'"
                        @click.stop="navigateToLinkedScript(data)"
                      >
                        <i class="pi pi-star star-icon" />
                      </button>
                    </div>
                    <span class="desc-cell">{{ describeEntry(data) }}</span>
                  </div>
                </template>
              </Column>
              <Column header="COMMAND" style="max-width: 140px">
                <template #body="{ data }">
                  <span
                    class="cmd-cell"
                    :class="{ 'cmd-cell--linked': matchedFavorite(data) }"
                    v-tooltip.top="matchedFavorite(data) ? 'Click star to open in Scripts' : data.command"
                  >{{ data.command }}</span>
                </template>
              </Column>
              <Column header="" style="width: 80px">
                <template #body="{ data }">
                  <span v-if="isAdmin" class="row-actions">
                    <Button
                      :icon="data.enabled ? 'pi pi-pause' : 'pi pi-play'"
                      text rounded size="small"
                      :severity="data.enabled ? 'warn' : 'success'"
                      :v-tooltip.left="data.enabled ? 'Pause' : 'Resume'"
                      @click.stop="toggleEntry(data)"
                    />
                    <Button icon="pi pi-trash" text rounded size="small"
                      severity="danger" v-tooltip.left="'Delete'" @click.stop="confirmDeleteEntry(data)" />
                  </span>
                </template>
              </Column>
            </DataTable>
          </div>
        </div>
      </SplitterPanel>

      <!-- ── Right: step wizard editor ───────────────────────────────────── -->
      <SplitterPanel :size="70">

        <!-- Empty: nothing to edit -->
        <div v-if="!form" class="empty-editor">
          <i class="pi pi-calendar empty-icon" />
          <span class="empty-text">
            {{ isAdmin
              ? 'Select an entry to edit, or click + to add a new one.'
              : 'Admin access required to edit crontab.' }}
          </span>
        </div>

        <!-- Non-admin -->
        <div v-else-if="!isAdmin" class="empty-editor">
          <Message severity="info" :closable="false">Admin access required to edit entries.</Message>
        </div>

        <!-- Step wizard -->
        <div v-else class="editor-wrap">

          <!-- Toolbar -->
          <Toolbar class="editor-toolbar">
            <template #start>
              <i class="pi pi-calendar editor-header-icon" />
              <span class="editor-mode-label">{{ editing ? 'EDIT ENTRY' : 'NEW ENTRY' }}</span>
              <code v-if="editing" class="editor-expr-badge">{{ entryExpr(editing) }}</code>
            </template>
            <template #end>
              <Button icon="pi pi-times" text rounded size="small"
                v-tooltip.left="'Cancel'" @click="cancelEdit" />
            </template>
          </Toolbar>

          <!-- Step indicator -->
          <div class="step-nav">
            <button class="step-pill" :class="{ active: step === 1, done: step > 1 }" @click="step = 1">
              <span class="step-num">
                <i v-if="step > 1" class="pi pi-check" />
                <span v-else>1</span>
              </span>
              <span class="step-text">SCHEDULE</span>
            </button>
            <div class="step-line" :class="{ active: step >= 2 }" />
            <button class="step-pill" :class="{ active: step === 2, done: step > 2 }"
              @click="step >= 2 ? step = 2 : null">
              <span class="step-num">
                <i v-if="step > 2" class="pi pi-check" />
                <span v-else>2</span>
              </span>
              <span class="step-text">COMMAND</span>
            </button>
            <div class="step-line" :class="{ active: step >= 3 }" />
            <button class="step-pill" :class="{ active: step === 3 }"
              @click="step >= 3 ? step = 3 : null">
              <span class="step-num">3</span>
              <span class="step-text">REVIEW</span>
            </button>
          </div>

          <!-- Step content (scrollable) -->
          <div class="step-content">

            <!-- ── Step 1: SCHEDULE ────────────────────────────────────────── -->
            <div v-show="step === 1" class="step-panel">

              <SelectButton
                v-model="formMode"
                :options="modeOptions"
                optionLabel="label"
                optionValue="value"
                class="mode-toggle mb-4"
              />

              <!-- SPECIAL mode -->
              <template v-if="formMode === 'special'">
                <div class="section-label">SELECT A SPECIAL SCHEDULE</div>
                <div class="special-grid">
                  <button
                    v-for="opt in specialOptions" :key="opt.value"
                    class="special-card"
                    :class="{ active: form.special === opt.value }"
                    @click="form.special = opt.value"
                  >
                    <code class="special-card-value">{{ opt.value }}</code>
                    <span class="special-card-label">{{ opt.label }}</span>
                  </button>
                </div>
              </template>

              <!-- REGULAR mode -->
              <template v-else>

                <!-- Quick presets -->
                <div class="section-label">QUICK PRESETS</div>
                <div class="presets-grid mb-4">
                  <button
                    v-for="p in quickPresets" :key="p.expr"
                    class="preset-card"
                    :class="{ active: selectedPreset === p.expr }"
                    @click="applyPreset(p)"
                  >
                    <span class="preset-card-label">{{ p.label }}</span>
                    <code class="preset-card-expr">{{ p.expr }}</code>
                  </button>
                </div>

                <!-- Field builder -->
                <div class="section-label">FIELD BUILDER</div>
                <div class="fields-grid mb-3">
                  <div v-for="f in fieldDefs" :key="f.key" class="field-card">
                    <div class="field-card-header">
                      <span class="field-card-label">{{ f.label }}</span>
                      <code class="field-card-expr">{{ fieldExpr(f.key) }}</code>
                    </div>
                    <Select
                      v-model="fieldTypes[f.key]"
                      :options="typeOptions(f)"
                      optionLabel="label" optionValue="value"
                      size="small" fluid
                    />
                    <InputNumber
                      v-if="fieldTypes[f.key] === 'step'"
                      v-model="fieldValues[f.key].step"
                      :min="1" :max="f.max"
                      fluid class="mt-1" size="small"
                    />
                    <Select
                      v-else-if="fieldTypes[f.key] === 'at' && f.names"
                      v-model="fieldValues[f.key].at"
                      :options="namedOptions(f)"
                      optionLabel="label" optionValue="value"
                      fluid class="mt-1" size="small"
                    />
                    <InputNumber
                      v-else-if="fieldTypes[f.key] === 'at'"
                      v-model="fieldValues[f.key].at"
                      :min="f.min" :max="f.max"
                      fluid class="mt-1" size="small"
                    />
                    <div v-else-if="fieldTypes[f.key] === 'range'" class="range-row mt-1">
                      <InputNumber v-model="fieldValues[f.key].from" :min="f.min" :max="f.max" size="small" fluid />
                      <span class="range-dash">–</span>
                      <InputNumber v-model="fieldValues[f.key].to" :min="f.min" :max="f.max" size="small" fluid />
                    </div>
                  </div>
                </div>

                <!-- Expression preview bar -->
                <div class="expr-preview-bar mb-3">
                  <div class="expr-preview-left">
                    <i class="pi pi-code" />
                    <code class="expr-preview-code">{{ currentExpr }}</code>
                  </div>
                  <span class="expr-preview-desc">{{ currentDesc }}</span>
                </div>

                <!-- Manual override (collapsible) -->
                <button class="manual-toggle" @click="showManual = !showManual">
                  <i class="pi pi-pencil" />
                  <span>Manual override</span>
                  <i :class="showManual ? 'pi pi-chevron-up' : 'pi pi-chevron-down'" class="toggle-chevron" />
                </button>
                <div v-if="showManual" class="manual-body mt-2">
                  <InputGroup>
                    <InputGroupAddon><i class="pi pi-pencil" /></InputGroupAddon>
                    <InputText v-model="manualExpr" placeholder="* * * * *" />
                    <Button label="Apply" @click="applyManual" />
                  </InputGroup>
                </div>

              </template>
            </div>

            <!-- ── Step 2: COMMAND ────────────────────────────────────────── -->
            <div v-show="step === 2" class="step-panel">

              <!-- Tab selector -->
              <div class="cmd-tabs">
                <button class="cmd-tab" :class="{ active: formTab === 'command' }" @click="formTab = 'command'">
                  COMANDO
                </button>
                <button class="cmd-tab cmd-tab--pipeline" :class="{ active: formTab === 'pipeline' }" @click="formTab = 'pipeline'">
                  ⚡ PIPELINE
                </button>
              </div>

              <!-- Tab: Command (existing UI) -->
              <template v-if="formTab === 'command'">
                <!-- Favorites (horizontal scrollable cards) -->
                <template v-if="scriptsStore.favorites.filter(f => f.exists).length">
                  <div class="section-label">FROM FAVORITES — click to use</div>
                  <div class="fav-scroll mb-4">
                    <button
                      v-for="fav in scriptsStore.favorites.filter(f => f.exists)"
                      :key="fav.id"
                      class="fav-card"
                      :class="{ active: form.command === buildCommand(fav) }"
                      v-tooltip.top="fav.path"
                      @click="form.command = buildCommand(fav)"
                    >
                      <code class="fav-card-runner">{{ runnerLabel(fav.path) }}</code>
                      <i class="pi pi-code fav-card-icon" />
                      <span class="fav-card-name">{{ fileName(fav.path) }}</span>
                    </button>
                  </div>
                </template>

                <!-- Command input -->
                <div class="section-label">COMMAND</div>
                <InputGroup class="mb-2">
                  <InputGroupAddon><i class="pi pi-terminal" /></InputGroupAddon>
                  <InputText v-model="form.command" placeholder="/path/to/script.sh or shell command" />
                  <Button v-if="form.command" icon="pi pi-times" severity="secondary"
                    v-tooltip.top="'Clear'" @click="form.command = ''" />
                </InputGroup>
                <span class="input-hint">Full path or shell command that cron will execute</span>
              </template>

              <!-- Tab: Pipeline -->
              <div v-if="formTab === 'pipeline'" class="pipeline-tab">
                <div class="section-label">SELECCIONÁ UN PIPELINE</div>
                <div class="pipeline-select-list">
                  <div
                    v-for="p in availablePipelines" :key="p.id"
                    class="pipeline-select-card"
                    :class="{ active: selectedPipelineId === p.id }"
                    @click="selectedPipelineId = p.id"
                  >
                    <span class="pipeline-select-name">⚡ {{ p.name }}</span>
                    <span class="pipeline-select-steps">{{ p.step_count }} pasos</span>
                  </div>
                  <div v-if="!availablePipelines.length" class="pipeline-select-empty">
                    No hay pipelines. Creá uno en la sección Pipelines.
                  </div>
                </div>
                <div v-if="pipelineCommand" class="pipeline-cmd-preview">
                  <span class="pipeline-cmd-label">COMANDO GENERADO</span>
                  <code class="pipeline-cmd-code">{{ pipelineCommand }}</code>
                </div>
              </div>

            </div>

            <!-- ── Step 3: REVIEW & SAVE ──────────────────────────────────── -->
            <div v-show="step === 3" class="step-panel">

              <!-- Summary -->
              <div class="section-label">SUMMARY</div>
              <div class="review-card mb-4">
                <div class="review-row">
                  <span class="review-label">SCHEDULE</span>
                  <div class="review-value-col">
                    <code class="review-expr">
                      {{ form.is_special ? form.special : currentExpr }}
                    </code>
                    <span class="review-desc">
                      {{ form.is_special
                        ? (SPECIAL_DESC[form.special?.toLowerCase()] || form.special)
                        : currentDesc }}
                    </span>
                  </div>
                </div>
                <div class="review-row">
                  <span class="review-label">COMMAND</span>
                  <code class="review-command">{{ form.command || '(empty)' }}</code>
                </div>
                <div v-if="form.comment" class="review-row">
                  <span class="review-label">COMMENT</span>
                  <span class="review-text">{{ form.comment }}</span>
                </div>
              </div>

              <!-- Comment input -->
              <div class="section-label">COMMENT (optional)</div>
              <InputText v-model="form.comment" placeholder="Description of this job" fluid class="mb-3" />

              <Message v-if="saveError" severity="error" :closable="false" class="mb-2">{{ saveError }}</Message>

            </div>
          </div>

          <!-- Step footer: navigation + primary action -->
          <div class="step-footer">
            <Button
              v-if="step > 1"
              label="Back" severity="secondary" text
              icon="pi pi-chevron-left"
              @click="step--"
            />
            <div class="step-footer-spacer" />
            <Button
              v-if="step < 3"
              label="Next"
              icon="pi pi-chevron-right" iconPos="right"
              @click="step++"
              :disabled="step === 2 && !form.command"
            />
            <Button
              v-else
              :label="editing ? 'Update Entry' : 'Add Entry'"
              icon="pi pi-check"
              :loading="saving"
              @click="saveEntry"
            />
          </div>

        </div>

      </SplitterPanel>

    </Splitter>
  </div>
</template>

<script setup>
import { ref, computed, reactive, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import Splitter from 'primevue/splitter'
import SplitterPanel from 'primevue/splitterpanel'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Toolbar from 'primevue/toolbar'
import SelectButton from 'primevue/selectbutton'
import Select from 'primevue/select'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import InputGroup from 'primevue/inputgroup'
import InputGroupAddon from 'primevue/inputgroupaddon'
import Divider from 'primevue/divider'
import Message from 'primevue/message'
import api from '../api/client.js'
import { useAuthStore } from '../stores/auth.js'
import { useScriptsStore } from '../stores/scripts.js'

const router = useRouter()
const toast = useToast()
const confirm = useConfirm()
const auth = useAuthStore()
const scriptsStore = useScriptsStore()
const isAdmin = computed(() => auth.isAdmin)

// ── Wizard state ──────────────────────────────────────────────────────────────
const step = ref(1)
const showManual = ref(false)

const entries = ref([])
const filterMode = ref('all')
const filteredEntries = computed(() => {
  if (filterMode.value === 'active') return entries.value.filter(e => e.enabled)
  if (filterMode.value === 'paused') return entries.value.filter(e => !e.enabled)
  return entries.value
})
const loading = ref(false)
const saving = ref(false)
const saveError = ref('')
const editing = ref(null)
const editingEntry = ref(null)
const form = ref(null)
const formMode = ref('regular')

// Pipelines para la tab de integración
const availablePipelines = ref([])
const formTab = ref('command')  // 'command' | 'pipeline'
const selectedPipelineId = ref(null)

watch(selectedPipelineId, async (id) => {
  if (!id || formTab.value !== 'pipeline') return
  try {
    const { data } = await api.get(`/api/pipelines/${id}/cron-command`)
    form.value.command = data.command
  } catch {
    // fallback silencioso
  }
})

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

function applyPreset(p) {
  selectedPreset.value = p.expr
  applyExprToFields(p.expr)
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
function navigateToLinkedScript(entry) {
  const fav = scriptsStore.favorites.find(f => entry.command && entry.command.includes(f.path))
  if (fav) router.push({ path: '/scripts', query: { select: fav.path } })
}
function fileName(path) { return path.split('/').pop() }
function runnerLabel(path) {
  const runners = { '.py': 'python3', '.sh': 'bash', '.rb': 'ruby', '.pl': 'perl', '.js': 'node' }
  const ext = path.slice(path.lastIndexOf('.')).toLowerCase()
  return runners[ext] || 'exec'
}
function buildCommand(fav) {
  const runners = { '.py':'python3', '.sh':'bash', '.rb':'ruby', '.pl':'perl', '.js':'node' }
  const ext = fav.path.slice(fav.path.lastIndexOf('.')).toLowerCase()
  const runner = runners[ext]
  return runner ? `${runner} ${fav.path}` : fav.path
}

async function loadPipelinesList() {
  try {
    const { data } = await api.get('/pipelines')
    availablePipelines.value = data
  } catch { /* silencioso */ }
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
  step.value = 1
  showManual.value = false
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
  step.value = 1
  showManual.value = false
}

function cancelEdit() {
  form.value = null
  editing.value = null
  editingEntry.value = null
  step.value = 1
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

async function toggleEntry(entry) {
  try {
    const { data } = await api.patch(`/crontab/${entry.id}/toggle`)
    entries.value = data
    const updated = data.find(e => e.id === entry.id)
    toast.add({
      severity: updated?.enabled ? 'success' : 'warn',
      summary: updated?.enabled ? 'Resumed' : 'Paused',
      detail: `Entry "${entryExpr(entry)}" ${updated?.enabled ? 'resumed' : 'paused'}.`,
      life: 3000,
    })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Toggle failed', detail: e.response?.data?.detail || 'Failed', life: 5000 })
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
    toast.add({ severity: 'success', summary: 'Deleted', detail: `Entry "${entryExpr(entry)}" deleted.`, life: 3000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Delete failed', detail: e.response?.data?.detail || 'Delete failed', life: 5000 })
  }
}

onMounted(() => {
  loadEntries()
  scriptsStore.loadFavorites()
  loadPipelinesList()
})
</script>

<style scoped>
/* ── View container ──────────────────────────── */
.crontab-view {
  height: calc(100vh - var(--header-height) - 48px);
  display: flex;
  flex-direction: column;
}
.crontab-splitter {
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
  background: var(--p-surface-card);
  overflow: hidden;
}
.list-panel-header {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 10px 10px 8px;
  border-bottom: 1px solid var(--p-surface-border);
  flex-shrink: 0;
}
.list-header-icon { font-size: 12px; color: var(--brand-orange); }
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
.table-wrap {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
:deep(.entries-table) { height: 100%; }
:deep(.entries-table .p-datatable-wrapper) { height: 100%; }
:deep(.entries-table .p-datatable-thead th) { background: transparent; }
:deep(.entries-table .p-datatable-column-header-content) {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 1.5px;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
  font-weight: 600;
}
:deep(.entries-table .p-datatable-tbody td) { padding: 5px 10px; }

.schedule-cell { display: flex; flex-direction: column; gap: 2px; }
.expr-row { display: flex; align-items: center; gap: 5px; }
.expr-cell { display: flex; align-items: center; gap: 5px; }
.cron-expr { font-family: var(--font-mono); font-size: var(--text-sm); color: var(--brand-orange); font-weight: 600; }
.star-icon { color: var(--p-yellow-500); font-size: var(--text-xs); }
.desc-cell { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-muted-color); }
.cmd-cell {
  font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-muted-color);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: block;
}

/* ── Empty states ────────────────────────────── */
.empty-state,
.empty-editor {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 24px;
}
.empty-icon { font-size: 28px; opacity: 0.4; color: var(--p-text-muted-color); }
.empty-text  { font-size: var(--text-sm); font-family: var(--font-mono); color: var(--p-text-muted-color); text-align: center; }

/* ── Editor wrap ─────────────────────────────── */
.editor-wrap { height: 100%; display: flex; flex-direction: column; overflow: hidden; background: var(--p-surface-card); }
.editor-toolbar { border-radius: 0; flex-shrink: 0; }
.editor-header-icon { font-size: 12px; color: var(--brand-orange); margin-right: 2px; }
.editor-mode-label {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  letter-spacing: 1.5px;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
}
.editor-expr-badge {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--brand-orange);
  background: color-mix(in srgb, var(--brand-orange) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand-orange) 30%, transparent);
  border-radius: 4px;
  padding: 2px 8px;
  margin-left: 8px;
}

/* ── Step indicator ──────────────────────────── */
.step-nav {
  display: flex;
  align-items: center;
  padding: 16px 24px;
  border-bottom: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
  flex-shrink: 0;
  gap: 0;
}
.step-pill {
  display: flex;
  align-items: center;
  gap: 10px;
  background: none;
  border: none;
  cursor: pointer;
  padding: 6px 10px;
  border-radius: 8px;
  transition: background 0.15s;
}
.step-pill:hover { background: var(--p-surface-hover); }
.step-pill.active .step-num {
  background: var(--brand-orange);
  color: #fff;
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--brand-orange) 25%, transparent);
}
.step-pill.done .step-num { background: var(--p-green-500); color: #fff; }
.step-num {
  width: 26px; height: 26px;
  border-radius: 50%;
  background: var(--p-surface-border);
  color: var(--p-text-muted-color);
  border: 1px solid var(--p-surface-border);
  display: flex; align-items: center; justify-content: center;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  flex-shrink: 0;
  transition: background 0.2s, color 0.2s, box-shadow 0.2s;
}
.step-num .pi { font-size: var(--text-2xs); }
.step-text {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 1.5px;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
  white-space: nowrap;
}
.step-pill.active .step-text { color: var(--p-text-color); font-weight: 600; }
.step-line {
  flex: 1;
  height: 2px;
  background: var(--p-surface-border);
  margin: 0 4px;
  border-radius: 1px;
  transition: background 0.3s;
}
.step-line.active { background: color-mix(in srgb, var(--brand-orange) 60%, transparent); }

/* ── Step content ────────────────────────────── */
.step-content {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}
.step-panel { padding: 24px 28px; }

/* ── Step footer ─────────────────────────────── */
.step-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 24px;
  border-top: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
  flex-shrink: 0;
}
.step-footer-spacer { flex: 1; }

/* ── Section label ───────────────────────────── */
.section-label {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 2px;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
  margin-bottom: 12px;
  margin-top: 4px;
}

/* ── Mode toggle ─────────────────────────────── */
.mode-toggle { width: 100%; }
:deep(.mode-toggle .p-selectbutton) { width: 100%; display: flex; }
:deep(.mode-toggle .p-togglebutton) { flex: 1; }

/* ── Quick presets grid ──────────────────────── */
.presets-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}
@media (max-width: 800px) {
  .presets-grid { grid-template-columns: repeat(2, 1fr); }
}
.preset-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  padding: 12px 14px;
  background: var(--p-surface-card);
  border: 1px solid var(--p-surface-border);
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
  text-align: left;
}
.preset-card:hover {
  border-color: color-mix(in srgb, var(--brand-orange) 50%, transparent);
  background: var(--p-surface-hover);
}
.preset-card.active {
  border-color: var(--brand-orange);
  background: color-mix(in srgb, var(--brand-orange) 10%, transparent);
}
.preset-card-label {
  font-size: var(--text-xs);
  color: var(--p-text-color);
  font-weight: 500;
  line-height: 1.2;
}
.preset-card-expr {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  color: var(--p-text-muted-color);
  letter-spacing: 0.5px;
}
.preset-card.active .preset-card-label { color: var(--brand-orange); }
.preset-card.active .preset-card-expr  { color: var(--brand-orange); opacity: 0.8; }

/* ── Special options grid ────────────────────── */
.special-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}
.special-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px 16px;
  background: var(--p-surface-card);
  border: 1px solid var(--p-surface-border);
  border-radius: 8px;
  cursor: pointer;
  text-align: left;
  transition: border-color 0.15s, background 0.15s;
}
.special-card:hover {
  border-color: color-mix(in srgb, var(--brand-orange) 50%, transparent);
  background: var(--p-surface-hover);
}
.special-card.active {
  border-color: var(--brand-orange);
  background: color-mix(in srgb, var(--brand-orange) 10%, transparent);
}
.special-card-value {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  font-weight: 700;
  color: var(--brand-orange);
}
.special-card-label {
  font-size: var(--text-xs);
  color: var(--p-text-muted-color);
  line-height: 1.3;
}

/* ── Field builder cards ─────────────────────── */
.fields-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; }
@media (max-width: 900px) { .fields-grid { grid-template-columns: repeat(3, 1fr); } }
.field-card {
  background: var(--p-surface-card);
  border: 1px solid var(--p-surface-border);
  border-radius: 8px;
  padding: 14px 14px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.field-card-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 4px;
}
.field-card-label {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 1.5px;
  color: var(--p-text-muted-color);
}
.field-card-expr {
  font-family: var(--font-mono);
  font-size: var(--text-lg);
  font-weight: 700;
  color: var(--brand-orange);
  line-height: 1;
}

/* ── Expression preview bar ──────────────────── */
.expr-preview-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: var(--p-surface-900);
  border-radius: 6px;
  border: 1px solid color-mix(in srgb, var(--brand-orange) 25%, transparent);
}
.expr-preview-left { display: flex; align-items: center; gap: 8px; color: var(--brand-orange); }
.expr-preview-code {
  font-family: var(--font-mono);
  font-size: var(--text-base);
  font-weight: 700;
  color: var(--brand-orange);
  letter-spacing: 1px;
}
.expr-preview-desc {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--p-text-muted-color);
}

/* ── Manual override toggle ──────────────────── */
.manual-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 7px 10px;
  background: none;
  border: 1px dashed var(--p-surface-border);
  border-radius: 6px;
  color: var(--p-text-muted-color);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s;
}
.manual-toggle:hover { border-color: var(--brand-orange); color: var(--p-text-color); }
.toggle-chevron { margin-left: auto; font-size: var(--text-2xs); }
.manual-body { }

/* ── Favorites scroll ────────────────────────── */
.fav-scroll {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 6px;
  scrollbar-width: thin;
}
.fav-scroll::-webkit-scrollbar { height: 4px; }
.fav-scroll::-webkit-scrollbar-thumb { background: var(--p-surface-400); border-radius: 2px; }
.fav-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  padding: 10px 14px;
  min-width: 90px;
  flex-shrink: 0;
  background: var(--p-surface-card);
  border: 1px solid var(--p-surface-border);
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
  text-align: center;
}
.fav-card:hover {
  border-color: color-mix(in srgb, var(--brand-orange) 50%, transparent);
  background: var(--p-surface-hover);
}
.fav-card.active {
  border-color: var(--brand-orange);
  background: color-mix(in srgb, var(--brand-orange) 10%, transparent);
}
.fav-card-runner {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  color: var(--brand-orange);
  letter-spacing: 0.5px;
  line-height: 1;
}
.fav-card-icon {
  font-size: var(--text-lg);
  color: var(--p-text-muted-color);
  opacity: 0.6;
}
.fav-card.active .fav-card-icon { color: var(--brand-orange); opacity: 1; }
.fav-card-name {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--p-text-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100px;
}
.input-hint {
  font-size: var(--text-xs);
  color: var(--p-text-muted-color);
  font-family: var(--font-mono);
}

/* ── Review card ─────────────────────────────── */
.review-card {
  background: var(--p-surface-card);
  border: 1px solid var(--p-surface-border);
  border-radius: 8px;
  overflow: hidden;
}
.review-row {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--p-surface-border);
}
.review-row:last-child { border-bottom: none; }
.review-label {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 1.5px;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
  min-width: 72px;
  padding-top: 2px;
}
.review-value-col { display: flex; flex-direction: column; gap: 3px; }
.review-expr {
  font-family: var(--font-mono);
  font-size: var(--text-base);
  font-weight: 700;
  color: var(--brand-orange);
}
.review-desc {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--p-text-muted-color);
}
.review-command {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--p-text-color);
  word-break: break-all;
}
.review-text {
  font-size: var(--text-sm);
  color: var(--p-text-muted-color);
}

/* ── Misc ────────────────────────────────────── */
.range-row { display: flex; align-items: center; gap: 4px; }
.range-dash { color: var(--p-text-muted-color); flex-shrink: 0; }

.star-link-btn {
  background: none; border: none; padding: 0; cursor: pointer;
  display: inline-flex; align-items: center;
  transition: background 0.15s, color 0.15s;
}
.star-link-btn:hover .star-icon { color: var(--brand-orange); filter: brightness(1.3); }

.cmd-cell--linked {
  color: var(--p-text-color) !important;
  opacity: 0.85;
}

/* ── Filter pills ────────────────────────────── */
.filter-pills {
  display: flex;
  gap: 4px;
  padding: 6px 10px;
  border-bottom: 1px solid var(--p-surface-border);
  flex-shrink: 0;
}
.filter-pill {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 1.5px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 20px;
  border: 1px solid var(--p-surface-border);
  background: transparent;
  color: var(--p-text-muted-color);
  cursor: pointer;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}
.filter-pill:hover { background: var(--p-surface-hover); color: var(--p-text-color); }
.filter-pill.active { background: color-mix(in srgb, var(--p-text-muted-color) 15%, transparent); color: var(--p-text-color); border-color: var(--p-text-muted-color); }
.filter-pill--active.active { background: color-mix(in srgb, var(--p-green-500) 15%, transparent); color: var(--p-green-500); border-color: var(--p-green-500); }
.filter-pill--paused.active { background: color-mix(in srgb, var(--p-yellow-500) 15%, transparent); color: var(--p-yellow-500); border-color: var(--p-yellow-500); }

/* ── Paused row ──────────────────────────────── */
:deep(.entry--paused td) { opacity: 0.45; }
:deep(.entry--paused .cron-expr) { text-decoration: line-through; }

/* ── Row actions ─────────────────────────────── */
.row-actions { display: flex; align-items: center; gap: 2px; }

/* ── Command/Pipeline tabs ───────────────────────── */
.cmd-tabs { display: flex; gap: 0; margin-bottom: 12px; border-bottom: 1px solid var(--p-surface-border); }
.cmd-tab { padding: 6px 14px; font-family: var(--font-mono); font-size: var(--text-2xs); letter-spacing: 1px; background: none; border: none; border-bottom: 2px solid transparent; color: var(--p-text-muted-color); cursor: pointer; transition: color 0.15s, border-color 0.15s; }
.cmd-tab:hover { color: var(--p-text-color); }
.cmd-tab.active { color: var(--brand-orange); border-bottom-color: var(--brand-orange); }
.cmd-tab--pipeline.active { color: var(--p-green-400); border-bottom-color: var(--p-green-400); }

/* ── Pipeline tab ────────────────────────────────── */
.pipeline-tab { display: flex; flex-direction: column; gap: 10px; }
.pipeline-select-list { display: flex; flex-direction: column; gap: 4px; max-height: 200px; overflow-y: auto; }
.pipeline-select-card { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; background: var(--p-surface-ground); border: 1px solid var(--p-surface-border); border-radius: 6px; cursor: pointer; transition: border-color 0.15s; }
.pipeline-select-card:hover { border-color: var(--p-text-muted-color); }
.pipeline-select-card.active { border-color: var(--p-green-400); background: color-mix(in srgb, var(--p-green-400) 8%, transparent); }
.pipeline-select-name { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-color); }
.pipeline-select-steps { font-family: var(--font-mono); font-size: 9px; color: var(--p-text-muted-color); }
.pipeline-select-empty { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-muted-color); padding: 12px; text-align: center; }
.pipeline-cmd-preview { background: var(--p-surface-ground); border: 1px solid var(--p-surface-border); border-radius: 6px; padding: 8px 12px; }
.pipeline-cmd-label { font-family: var(--font-mono); font-size: var(--text-2xs); letter-spacing: 1px; color: var(--p-text-muted-color); display: block; margin-bottom: 4px; }
.pipeline-cmd-code { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-cyan-400); }
</style>
