<template>
  <div class="crontab-view">

    <!-- ── Left panel: crontab entries list ──────────────────────────── -->
    <div class="entries-panel">
      <div class="panel-header">
        <span class="panel-title">CRONTAB ENTRIES</span>
        <span class="count-badge">{{ entries.length }}</span>
      </div>
      <div v-if="loading" class="panel-state">Loading…</div>
      <div v-else-if="loadError" class="panel-state error">{{ loadError }}</div>
      <div v-else-if="entries.length === 0" class="panel-state muted">
        No cron jobs configured.
      </div>
      <div v-else class="entries-list">
        <div
          v-for="e in entries" :key="e.id"
          class="entry-card"
          :class="{ selected: editing?.id === e.id }"
          @click="startEdit(e)"
        >
          <!-- Schedule expression / special -->
          <div class="entry-schedule">
            <code class="cron-expr">{{ entryExpr(e) }}</code>
            <span v-if="matchedFavorite(e)" class="fav-star" title="Linked to Script Favorites">★</span>
          </div>
          <div class="entry-desc muted-sm">{{ describeEntry(e) }}</div>
          <!-- Command (truncated) -->
          <div class="entry-cmd">{{ e.command }}</div>
          <div v-if="e.comment" class="entry-comment muted-sm"># {{ e.comment }}</div>
          <!-- Actions -->
          <div class="entry-actions" @click.stop>
            <button v-if="isAdmin" class="row-btn" title="Edit" @click="startEdit(e)">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            </button>
            <button v-if="isAdmin" class="row-btn btn-danger" title="Delete" @click="confirmDelete(e)">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>
            </button>
          </div>
        </div>
      </div>
      <div v-if="isAdmin" class="panel-footer">
        <button class="add-btn" @click="startNew">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          New entry
        </button>
      </div>
    </div>

    <!-- ── Right panel: visual editor ────────────────────────────────── -->
    <div class="editor-panel" v-if="form && isAdmin">
      <div class="editor-header">
        <span class="panel-title">{{ editing ? 'EDIT ENTRY' : 'NEW ENTRY' }}</span>
        <button class="icon-btn" @click="cancelEdit">✕</button>
      </div>

      <!-- Special / regular toggle -->
      <div class="section">
        <div class="row">
          <label class="radio-opt" :class="{ on: !form.is_special }">
            <input type="radio" :checked="!form.is_special" @change="form.is_special = false" />
            <span>Regular schedule</span>
          </label>
          <label class="radio-opt" :class="{ on: form.is_special }">
            <input type="radio" :checked="form.is_special" @change="form.is_special = true" />
            <span>Special string</span>
          </label>
        </div>
      </div>

      <!-- Special string picker -->
      <div v-if="form.is_special" class="section">
        <div class="section-title">SPECIAL STRING</div>
        <div class="presets-grid">
          <button
            v-for="sp in specialOptions" :key="sp.value"
            class="preset-btn"
            :class="{ active: form.special === sp.value }"
            @click="form.special = sp.value"
          >
            <span class="preset-expr">{{ sp.value }}</span>
            <span class="preset-label">{{ sp.label }}</span>
          </button>
        </div>
      </div>

      <!-- Visual cron picker for regular schedules -->
      <template v-else>
        <!-- Quick presets -->
        <div class="section">
          <div class="section-title">QUICK PRESETS</div>
          <div class="presets-row">
            <button
              v-for="p in quickPresets" :key="p.label"
              class="preset-chip"
              :class="{ active: currentExpr === p.expr }"
              @click="applyPreset(p)"
            >{{ p.label }}</button>
          </div>
        </div>

        <!-- Field editors -->
        <div class="section">
          <div class="section-title">SCHEDULE FIELDS</div>
          <div class="fields-grid">
            <div v-for="f in fieldDefs" :key="f.key" class="field-card">
              <div class="field-label">{{ f.label }}</div>
              <select class="field-type" v-model="fieldTypes[f.key]" @change="onTypeChange(f.key)">
                <option value="every">Every {{ f.unit }}</option>
                <option value="step">Every N {{ f.unit }}s</option>
                <option value="at">At specific</option>
                <option value="range">Range</option>
              </select>
              <!-- Every N input -->
              <input
                v-if="fieldTypes[f.key] === 'step'"
                v-model="fieldValues[f.key].step"
                type="number"
                :min="1" :max="f.max"
                class="field-input"
                placeholder="N"
                @input="syncExpr"
              />
              <!-- At specific: number input or select for named fields -->
              <template v-else-if="fieldTypes[f.key] === 'at'">
                <select v-if="f.names" class="field-input" v-model="fieldValues[f.key].at" @change="syncExpr">
                  <option v-for="(name, idx) in f.names" :key="idx" :value="String(idx + f.nameOffset)">{{ name }}</option>
                </select>
                <input v-else v-model="fieldValues[f.key].at" type="number"
                  :min="f.min" :max="f.max" class="field-input" @input="syncExpr" />
              </template>
              <!-- Range -->
              <template v-else-if="fieldTypes[f.key] === 'range'">
                <div class="range-row">
                  <input v-model="fieldValues[f.key].from" type="number" :min="f.min" :max="f.max" class="field-input half" @input="syncExpr" />
                  <span class="range-dash">–</span>
                  <input v-model="fieldValues[f.key].to" type="number" :min="f.min" :max="f.max" class="field-input half" @input="syncExpr" />
                </div>
              </template>
              <!-- Expression preview for this field -->
              <div class="field-expr">{{ fieldExpr(f.key) }}</div>
            </div>
          </div>
        </div>

        <!-- Live expression + description -->
        <div class="section">
          <div class="section-title">EXPRESSION</div>
          <div class="expr-preview">
            <code class="expr-code">{{ currentExpr }}</code>
            <span class="expr-desc">{{ currentDesc }}</span>
          </div>
          <!-- Manual override -->
          <div class="manual-row">
            <span class="muted-sm">Manual:</span>
            <input
              v-model="manualExpr"
              class="manual-input"
              placeholder="* * * * *"
              @input="onManualInput"
            />
            <button class="icon-btn-sm" @click="applyManual" title="Apply manual expression">Apply</button>
          </div>
        </div>
      </template>

      <!-- Command + comment -->
      <div class="section">
        <div class="section-title">COMMAND</div>
        <!-- Script favorites dropdown -->
        <div v-if="scriptsStore.favorites.length" class="fav-shortcuts">
          <span class="muted-sm">From favorites:</span>
          <button
            v-for="fav in scriptsStore.favorites.filter(f => f.exists)" :key="fav.id"
            class="fav-chip"
            @click="form.command = buildCommand(fav)"
          >{{ fileName(fav.path) }}</button>
        </div>
        <input v-model="form.command" class="cmd-input" placeholder="/path/to/script.sh" />
        <div class="section-title" style="margin-top:10px">COMMENT (optional)</div>
        <input v-model="form.comment" class="cmd-input" placeholder="Description of this job" />
      </div>

      <!-- Save / Cancel -->
      <div class="editor-footer">
        <div v-if="saveError" class="err-msg">{{ saveError }}</div>
        <div class="footer-row">
          <button class="save-btn" @click="saveEntry" :disabled="saving">
            {{ saving ? 'Saving…' : (editing ? 'Update' : 'Add Entry') }}
          </button>
          <button class="cancel-btn" @click="cancelEdit">Cancel</button>
        </div>
      </div>
    </div>

    <!-- Empty state for right panel -->
    <div class="editor-panel empty-panel" v-else-if="!isAdmin">
      <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" class="empty-icon">
        <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
      </svg>
      <span class="muted">Admin access required to edit crontab.</span>
    </div>
    <div class="editor-panel empty-panel" v-else>
      <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" class="empty-icon">
        <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
      </svg>
      <span class="muted">Select an entry to edit, or click <strong>New entry</strong>.</span>
    </div>

    <!-- Delete confirmation modal -->
    <div v-if="deleteTarget" class="modal-overlay" @click.self="deleteTarget = null">
      <div class="modal">
        <div class="modal-title">Delete cron entry?</div>
        <pre class="modal-code">{{ entryExpr(deleteTarget) }} {{ deleteTarget.command }}</pre>
        <div class="modal-actions">
          <button class="save-btn danger" @click="doDelete">Delete</button>
          <button class="cancel-btn" @click="deleteTarget = null">Cancel</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted } from 'vue'
import api from '../api/client.js'
import { useAuthStore } from '../stores/auth.js'
import { useScriptsStore } from '../stores/scripts.js'

const auth = useAuthStore()
const scriptsStore = useScriptsStore()
const isAdmin = auth.role === 'admin'

const entries = ref([])
const loading = ref(false)
const loadError = ref('')
const saving = ref(false)
const saveError = ref('')
const editing = ref(null)   // CrontabEntry being edited (null = new)
const deleteTarget = ref(null)

// Form state
const form = ref(null)

// ── Field definitions ─────────────────────────────────────────────────────────

const fieldDefs = [
  { key: 'minute',  label: 'MINUTE',  unit: 'minute',  min: 0,  max: 59,  names: null, nameOffset: 0 },
  { key: 'hour',    label: 'HOUR',    unit: 'hour',    min: 0,  max: 23,  names: null, nameOffset: 0 },
  { key: 'dom',     label: 'DAY',     unit: 'day',     min: 1,  max: 31,  names: null, nameOffset: 0 },
  { key: 'month',   label: 'MONTH',   unit: 'month',   min: 1,  max: 12,
    names: ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],
    nameOffset: 1 },
  { key: 'dow',     label: 'WEEKDAY', unit: 'weekday', min: 0,  max: 6,
    names: ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'],
    nameOffset: 0 },
]

const fieldTypes = reactive({ minute:'every', hour:'every', dom:'every', month:'every', dow:'every' })
const fieldValues = reactive({
  minute: { step:'5', at:'0', from:'0', to:'30' },
  hour:   { step:'2', at:'0', from:'0', to:'12' },
  dom:    { step:'1', at:'1', from:'1', to:'15' },
  month:  { step:'1', at:'1', from:'1', to:'6' },
  dow:    { step:'1', at:'1', from:'1', to:'5' },
})
const manualExpr = ref('* * * * *')

// ── Quick presets ─────────────────────────────────────────────────────────────

const quickPresets = [
  { label: 'Every minute',  expr: '* * * * *' },
  { label: 'Every 5 min',   expr: '*/5 * * * *' },
  { label: 'Every 15 min',  expr: '*/15 * * * *' },
  { label: 'Hourly',        expr: '0 * * * *' },
  { label: 'Daily midnight',expr: '0 0 * * *' },
  { label: 'Daily 6 AM',    expr: '0 6 * * *' },
  { label: 'Weekly Mon',    expr: '0 0 * * 1' },
  { label: 'Monthly 1st',   expr: '0 0 1 * *' },
]

const specialOptions = [
  { value: '@reboot',    label: 'At system reboot' },
  { value: '@hourly',    label: 'Every hour' },
  { value: '@daily',     label: 'Every day (midnight)' },
  { value: '@midnight',  label: 'Every day (midnight, alias)' },
  { value: '@weekly',    label: 'Every week (Sunday midnight)' },
  { value: '@monthly',   label: 'Every month (1st midnight)' },
  { value: '@yearly',    label: 'Every year (Jan 1st midnight)' },
]

// ── Computed expression & description ─────────────────────────────────────────

function fieldExpr(key) {
  const t = fieldTypes[key]
  const v = fieldValues[key]
  if (t === 'every') return '*'
  if (t === 'step')  return `*/${v.step || '1'}`
  if (t === 'at')    return v.at ?? '0'
  if (t === 'range') return `${v.from}-${v.to}`
  return '*'
}

const currentExpr = computed(() =>
  fieldDefs.map(f => fieldExpr(f.key)).join(' ')
)

function syncExpr() { /* reactivity through fieldTypes/fieldValues */ }

function onTypeChange(key) {
  // nothing extra needed; computed re-evaluates
}

function applyPreset(p) {
  applyExprToFields(p.expr)
}

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
      fieldValues[key].step = val.slice(2)
    } else if (val.includes('-')) {
      fieldTypes[key] = 'range'
      const [a, b] = val.split('-')
      fieldValues[key].from = a
      fieldValues[key].to = b
    } else {
      fieldTypes[key] = 'at'
      fieldValues[key].at = val
    }
  })
  manualExpr.value = expr
}

function onManualInput() { /* live-sync handled by applyManual */ }
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
  if (days.length >= 7) return 'every day'
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
  const months = month.split(',').map(m => MONTH_LONG[parseInt(m) - 1] || m)
  return `in ${months.join(', ')}`
}

function describeSchedule(min, hour, dom, month, dow) {
  if (min==='*' && hour==='*' && dom==='*' && month==='*' && dow==='*') return 'Every minute'
  if (min.startsWith('*/') && hour==='*' && dom==='*' && month==='*' && dow==='*') {
    const n = min.slice(2)
    return n === '1' ? 'Every minute' : `Every ${n} minutes`
  }
  if (hour.startsWith('*/') && (min==='0' || min==='00') && dom==='*' && month==='*' && dow==='*') {
    return `Every ${hour.slice(2)} hours (at :00)`
  }
  const simpleTime = !/[*\/,\-]/.test(min) && !/[*\/,\-]/.test(hour)
  if (simpleTime) {
    const parts = [timeStr(hour, min)]
    const dowStr = describeDow(dow)
    const domStr = describeDom(dom)
    const monStr = describeMonth(month)
    if (dowStr) parts.push(dowStr)
    else if (domStr) parts.push(domStr)
    else parts.push('daily')
    if (monStr) parts.push(monStr)
    return parts.join(', ')
  }
  return `${min} ${hour} ${dom} ${month} ${dow}`
}

const SPECIAL_DESC = {
  '@reboot':   'At system reboot',
  '@hourly':   'Every hour (at :00)',
  '@daily':    'Every day at midnight',
  '@midnight': 'Every day at midnight',
  '@weekly':   'Every Sunday at midnight',
  '@monthly':  'Every 1st at midnight',
  '@yearly':   'Every Jan 1st at midnight',
  '@annually': 'Every Jan 1st at midnight',
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
  if (parts.length === 5) return describeSchedule(...parts)
  return ''
})

// ── Favorites integration ─────────────────────────────────────────────────────

function matchedFavorite(e) {
  return scriptsStore.favorites.some(f => e.command.includes(f.path))
}

function fileName(path) { return path.split('/').pop() }

function buildCommand(fav) {
  // Prepend runner if not directly executable
  const runners = { '.py': 'python3', '.sh': 'bash', '.rb': 'ruby', '.pl': 'perl', '.js': 'node' }
  const ext = fav.path.slice(fav.path.lastIndexOf('.')).toLowerCase()
  const runner = runners[ext]
  return runner ? `${runner} ${fav.path}` : fav.path
}

// ── CRUD ──────────────────────────────────────────────────────────────────────

async function loadEntries() {
  loading.value = true
  loadError.value = ''
  try {
    const { data } = await api.get('/crontab/')
    entries.value = data
  } catch (e) {
    loadError.value = e.response?.data?.detail || 'Failed to load crontab'
  } finally {
    loading.value = false
  }
}

function startNew() {
  editing.value = null
  form.value = { minute:'*', hour:'*', dom:'*', month:'*', dow:'*', command:'', comment:'', is_special:false, special:'@daily' }
  resetFields('* * * * *')
  saveError.value = ''
}

function startEdit(e) {
  if (!isAdmin) return
  editing.value = e
  form.value = {
    minute: e.minute, hour: e.hour, dom: e.dom, month: e.month, dow: e.dow,
    command: e.command, comment: e.comment || '',
    is_special: e.is_special, special: e.special || '@daily',
  }
  if (!e.is_special) {
    resetFields(entryExpr(e))
  }
  saveError.value = ''
}

function resetFields(expr) {
  applyExprToFields(expr)
  manualExpr.value = expr
}

function cancelEdit() {
  form.value = null
  editing.value = null
}

async function saveEntry() {
  if (!form.value) return
  saving.value = true
  saveError.value = ''

  const body = {
    ...form.value,
    ...(form.value.is_special ? {} : {
      minute: fieldExpr('minute'),
      hour:   fieldExpr('hour'),
      dom:    fieldExpr('dom'),
      month:  fieldExpr('month'),
      dow:    fieldExpr('dow'),
    }),
  }

  try {
    let { data } = editing.value
      ? await api.put(`/crontab/${editing.value.id}`, body)
      : await api.post('/crontab/', body)
    entries.value = data
    cancelEdit()
  } catch (e) {
    saveError.value = e.response?.data?.detail || 'Save failed'
  } finally {
    saving.value = false
  }
}

function confirmDelete(e) { deleteTarget.value = e }

async function doDelete() {
  if (!deleteTarget.value) return
  try {
    const { data } = await api.delete(`/crontab/${deleteTarget.value.id}`)
    entries.value = data
    deleteTarget.value = null
    if (editing.value?.id === deleteTarget.value?.id) cancelEdit()
  } catch (e) {
    alert(e.response?.data?.detail || 'Delete failed')
    deleteTarget.value = null
  }
}

onMounted(() => {
  loadEntries()
  scriptsStore.loadFavorites()
})
</script>

<style scoped>
.crontab-view {
  display: flex;
  height: calc(100vh - var(--header-height) - 48px);
  overflow: hidden;
}

/* ── Left panel ─────────────────────────────────────────────────────────── */
.entries-panel {
  width: 300px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px 0 0 8px;
  overflow: hidden;
}
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: var(--surface-2);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.panel-title {
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 1.5px;
  color: var(--text-muted);
}
.count-badge {
  font-family: var(--font-mono);
  font-size: 10px;
  background: var(--surface-3);
  color: var(--text-muted);
  padding: 1px 6px;
  border-radius: 10px;
}
.panel-state {
  padding: 20px 16px;
  font-size: 12px;
  color: var(--text-muted);
  text-align: center;
}
.panel-state.error { color: var(--accent-red); }
.entries-list { flex: 1; overflow-y: auto; }
.entry-card {
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  transition: background 0.1s;
  position: relative;
}
.entry-card:hover { background: var(--surface-2); }
.entry-card.selected { background: var(--surface-3); border-left: 2px solid var(--accent-blue); padding-left: 12px; }
.entry-schedule { display: flex; align-items: center; gap: 6px; margin-bottom: 3px; }
.cron-expr { font-family: var(--font-mono); font-size: 12px; color: var(--accent-cyan); }
.fav-star { color: var(--accent-yellow); font-size: 13px; }
.entry-desc { font-size: 11px; color: var(--accent-blue); margin-bottom: 4px; }
.entry-cmd {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 260px;
}
.entry-comment { font-size: 10px; margin-top: 2px; }
.entry-actions {
  position: absolute;
  top: 8px; right: 8px;
  display: flex; gap: 2px;
  opacity: 0; transition: opacity 0.15s;
}
.entry-card:hover .entry-actions { opacity: 1; }
.row-btn {
  background: none; border: none; padding: 3px 5px;
  cursor: pointer; color: var(--text-dim); border-radius: 3px;
  transition: color 0.1s;
}
.row-btn:hover { color: var(--text); }
.row-btn.btn-danger:hover { color: var(--accent-red); }
.panel-footer {
  padding: 10px 14px;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}
.add-btn {
  display: flex; align-items: center; gap: 6px;
  background: none;
  border: 1px dashed var(--border-bright);
  color: var(--text-muted);
  padding: 6px 14px; border-radius: 5px;
  font-family: var(--font-mono); font-size: 11px;
  cursor: pointer; width: 100%; justify-content: center;
  transition: all 0.15s;
}
.add-btn:hover { border-color: var(--accent-blue); color: var(--accent-blue); }

/* ── Right panel ─────────────────────────────────────────────────────────── */
.editor-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: none;
  border-radius: 0 8px 8px 0;
  overflow-y: auto;
}
.editor-panel.empty-panel {
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--text-muted);
  font-size: 13px;
  overflow: hidden;
}
.empty-icon { color: var(--text-dim); }
.editor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: var(--surface-2);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  position: sticky; top: 0; z-index: 2;
}
.icon-btn {
  background: none; border: none; cursor: pointer;
  color: var(--text-muted); font-size: 14px; padding: 2px 6px;
  border-radius: 3px; transition: color 0.15s;
}
.icon-btn:hover { color: var(--text); }

/* ── Sections ────────────────────────────────────────────────────────────── */
.section { padding: 14px 16px; border-bottom: 1px solid var(--border); }
.section-title {
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 1.5px;
  color: var(--text-muted);
  margin-bottom: 10px;
}
.row { display: flex; gap: 12px; align-items: center; }
.radio-opt {
  display: flex; align-items: center; gap: 6px;
  cursor: pointer; font-size: 12px; color: var(--text-muted);
  padding: 5px 10px; border-radius: 5px;
  border: 1px solid var(--border); transition: all 0.15s;
}
.radio-opt input { display: none; }
.radio-opt.on { border-color: var(--accent-blue); color: var(--accent-blue); background: rgba(14,165,233,0.08); }

/* ── Presets ─────────────────────────────────────────────────────────────── */
.presets-row { display: flex; flex-wrap: wrap; gap: 6px; }
.preset-chip {
  background: var(--surface-2);
  border: 1px solid var(--border);
  color: var(--text-muted);
  padding: 4px 10px; border-radius: 4px;
  font-family: var(--font-mono); font-size: 11px;
  cursor: pointer; transition: all 0.15s;
}
.preset-chip:hover { border-color: var(--accent-blue); color: var(--accent-blue); }
.preset-chip.active { border-color: var(--accent-blue); color: var(--accent-blue); background: rgba(14,165,233,0.1); }
.presets-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.preset-btn {
  background: var(--surface-2); border: 1px solid var(--border);
  padding: 8px 10px; border-radius: 5px; cursor: pointer;
  text-align: left; transition: all 0.15s;
}
.preset-btn:hover, .preset-btn.active { border-color: var(--accent-blue); }
.preset-expr {
  display: block;
  font-family: var(--font-mono); font-size: 11px; color: var(--accent-cyan);
}
.preset-label { display: block; font-size: 11px; color: var(--text-muted); margin-top: 2px; }

/* ── Fields ──────────────────────────────────────────────────────────────── */
.fields-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; }
.field-card {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 6px; padding: 10px 8px;
  display: flex; flex-direction: column; gap: 6px;
}
.field-label {
  font-family: var(--font-mono);
  font-size: 9px; letter-spacing: 1px;
  color: var(--text-muted);
}
.field-type, .field-input {
  background: var(--surface);
  border: 1px solid var(--border-bright);
  color: var(--text); padding: 4px 6px;
  border-radius: 4px; font-family: var(--font-mono);
  font-size: 11px; outline: none; width: 100%;
  transition: border-color 0.15s;
}
.field-type:focus, .field-input:focus { border-color: var(--accent-blue); }
.field-input.half { width: calc(50% - 6px); }
.range-row { display: flex; align-items: center; gap: 4px; }
.range-dash { font-size: 11px; color: var(--text-muted); }
.field-expr {
  font-family: var(--font-mono); font-size: 13px;
  color: var(--accent-cyan); text-align: center;
  font-weight: 600;
}

/* ── Expression preview ──────────────────────────────────────────────────── */
.expr-preview {
  display: flex; align-items: center; gap: 14px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 6px; padding: 10px 14px;
  margin-bottom: 10px;
}
.expr-code {
  font-family: var(--font-mono); font-size: 15px;
  color: var(--accent-blue); font-weight: 600;
  white-space: nowrap;
}
.expr-desc { font-size: 12px; color: var(--text-muted); }
.manual-row {
  display: flex; align-items: center; gap: 8px;
}
.manual-input {
  flex: 1; background: var(--surface-2);
  border: 1px solid var(--border);
  padding: 5px 10px; border-radius: 4px;
  font-family: var(--font-mono); font-size: 12px;
  color: var(--text); outline: none; transition: border-color 0.15s;
}
.manual-input:focus { border-color: var(--accent-blue); }
.icon-btn-sm {
  background: var(--surface-2); border: 1px solid var(--border);
  color: var(--text-muted); padding: 5px 10px;
  border-radius: 4px; font-family: var(--font-mono);
  font-size: 11px; cursor: pointer; transition: all 0.15s;
  white-space: nowrap;
}
.icon-btn-sm:hover { border-color: var(--accent-blue); color: var(--accent-blue); }

/* ── Command ─────────────────────────────────────────────────────────────── */
.fav-shortcuts { display: flex; flex-wrap: wrap; align-items: center; gap: 5px; margin-bottom: 8px; }
.fav-chip {
  background: rgba(245,158,11,0.1);
  border: 1px solid rgba(245,158,11,0.3);
  color: var(--accent-yellow);
  padding: 2px 8px; border-radius: 3px;
  font-family: var(--font-mono); font-size: 10px;
  cursor: pointer; transition: all 0.15s;
}
.fav-chip:hover { background: rgba(245,158,11,0.2); }
.cmd-input {
  width: 100%; background: var(--surface-2);
  border: 1px solid var(--border-bright);
  padding: 7px 10px; border-radius: 5px;
  font-family: var(--font-mono); font-size: 13px;
  color: var(--text); outline: none; transition: border-color 0.15s;
}
.cmd-input:focus { border-color: var(--accent-blue); }
.cmd-input::placeholder { color: var(--text-dim); }

/* ── Footer ──────────────────────────────────────────────────────────────── */
.editor-footer {
  padding: 14px 16px;
  position: sticky; bottom: 0;
  background: var(--surface-2);
  border-top: 1px solid var(--border);
}
.err-msg { color: var(--accent-red); font-size: 12px; margin-bottom: 8px; }
.footer-row { display: flex; gap: 8px; }
.save-btn {
  background: var(--accent-blue); color: #fff;
  border: none; padding: 7px 20px; border-radius: 5px;
  font-family: var(--font-mono); font-size: 12px;
  cursor: pointer; transition: opacity 0.15s;
}
.save-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.save-btn.danger { background: var(--accent-red); }
.cancel-btn {
  background: none; border: 1px solid var(--border);
  color: var(--text-muted); padding: 7px 16px;
  border-radius: 5px; font-family: var(--font-mono);
  font-size: 12px; cursor: pointer; transition: all 0.15s;
}
.cancel-btn:hover { border-color: var(--border-bright); color: var(--text); }

/* ── Modal ───────────────────────────────────────────────────────────────── */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.55);
  display: flex; align-items: center; justify-content: center; z-index: 200;
}
.modal { background: var(--surface); border: 1px solid var(--border-bright); border-radius: 8px; padding: 24px; min-width: 340px; }
.modal-title { font-weight: 600; margin-bottom: 12px; font-size: 14px; }
.modal-code {
  font-family: var(--font-mono); font-size: 12px; color: var(--text-muted);
  background: var(--bg); padding: 8px 12px; border-radius: 4px;
  margin-bottom: 16px; white-space: pre-wrap; word-break: break-all;
}
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; }

/* ── Utilities ───────────────────────────────────────────────────────────── */
.muted { color: var(--text-muted); }
.muted-sm { font-size: 10px; color: var(--text-muted); font-family: var(--font-mono); }
</style>
