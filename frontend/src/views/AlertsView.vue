<template>
  <div class="alerts-view">
    <div class="page-header">
      <div class="page-title">
        <i class="pi pi-bell page-icon" />
        <span>ALERTS</span>
        <Tag :value="`${rules.length} rules`" severity="secondary" />
        <Tag v-if="activeCount > 0" :value="`${activeCount} firing`" severity="danger" />
      </div>
      <Button
        v-if="auth.hasPermission('alerts', 'write')"
        label="New Rule"
        icon="pi pi-plus"
        size="small"
        @click="startNew"
      />
    </div>

    <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>

    <Splitter class="alerts-splitter" :gutter-size="6">
      <!-- Left: rule list -->
      <SplitterPanel :size="30" :min-size="20">
        <div class="rule-list">
          <div
            v-for="rule in rules"
            :key="rule.id"
            class="rule-item"
            :class="{
              selected: selectedRule?.id === rule.id,
              'item-firing': rule.has_active_fire,
              'item-disabled': !rule.enabled,
            }"
            @click="selectRule(rule)"
          >
            <div class="rule-item-left">
              <i :class="['pi', conditionIcon(rule.condition_type), 'cond-icon']" />
              <div class="rule-info">
                <span class="rule-name">{{ rule.name }}</span>
                <span class="rule-meta">{{ conditionSummary(rule) }}</span>
              </div>
            </div>
            <span
              class="status-dot"
              :class="{
                'dot-active': rule.has_active_fire,
                'dot-ok': !rule.has_active_fire && rule.enabled,
                'dot-disabled': !rule.enabled,
              }"
            />
          </div>
          <div v-if="rules.length === 0" class="empty-state">
            <i class="pi pi-bell-slash empty-icon" />
            <span>No alert rules configured.</span>
          </div>
        </div>
      </SplitterPanel>

      <!-- Right: editor + fire history -->
      <SplitterPanel :size="70" :min-size="40">
        <div class="right-panel">

          <div v-if="selectedRule || isNew" class="editor-card">
            <!-- Active fire banner -->
            <div v-if="selectedRule?.has_active_fire" class="fire-banner">
              <i class="pi pi-exclamation-triangle" />
              <span>This rule is currently <strong>FIRING</strong></span>
            </div>

            <div class="editor-header">
              <div class="editor-title-group">
                <span class="editor-title">{{ isNew ? 'NEW RULE' : 'EDIT RULE' }}</span>
                <Tag
                  v-if="!isNew"
                  :value="form.enabled ? 'ENABLED' : 'DISABLED'"
                  :severity="form.enabled ? 'success' : 'secondary'"
                />
              </div>
              <div class="editor-actions" v-if="auth.hasPermission('alerts', 'write')">
                <Button
                  v-if="!isNew"
                  :label="form.enabled ? 'Disable' : 'Enable'"
                  :icon="form.enabled ? 'pi pi-pause' : 'pi pi-play'"
                  size="small"
                  severity="secondary"
                  @click="toggleRule"
                />
                <Button
                  v-if="!isNew"
                  icon="pi pi-trash"
                  size="small"
                  severity="danger"
                  text
                  v-tooltip.top="'Delete rule'"
                  @click="deleteRule"
                />
                <Button label="Save" icon="pi pi-check" size="small" @click="saveRule" :loading="saving" />
              </div>
            </div>

            <div class="form-grid">
              <div class="form-field">
                <label>Name</label>
                <InputText v-model="form.name" size="small" :disabled="!canEdit" />
              </div>
              <div class="form-field">
                <label>Condition type</label>
                <Select
                  v-model="form.condition_type"
                  :options="conditionOptions"
                  option-label="label"
                  option-value="value"
                  size="small"
                  :disabled="!canEdit"
                />
              </div>
              <div class="form-field" v-if="['cpu','ram','disk'].includes(form.condition_type)">
                <label>Threshold (%)</label>
                <InputNumber v-model="form.threshold" :min="1" :max="100" size="small" :disabled="!canEdit" />
              </div>
              <div class="form-field" v-else>
                <label>Target name</label>
                <InputText v-model="form.target" size="small" :disabled="!canEdit" placeholder="e.g. nginx" />
              </div>
              <div class="form-field">
                <label>Cooldown (minutes)</label>
                <InputNumber v-model="form.cooldown_minutes" :min="1" size="small" :disabled="!canEdit" />
              </div>
              <div class="form-field">
                <label>Alert email</label>
                <InputText v-model="form.email_to" size="small" :disabled="!canEdit" placeholder="you@example.com" />
              </div>
              <div class="form-field form-field--checkbox">
                <Checkbox v-model="form.notify_on_recovery" :binary="true" :disabled="!canEdit" />
                <label>Notify on recovery</label>
              </div>
            </div>
          </div>

          <!-- Fire history -->
          <div class="fire-history" v-if="selectedRule && !isNew">
            <div class="section-label">FIRE HISTORY</div>
            <DataTable :value="fires" size="small" class="fire-table" :loading="firesLoading">
              <Column field="status" header="Status" style="width: 120px">
                <template #body="{ data }">
                  <Tag
                    :value="data.status === 'active' ? 'ACTIVE' : 'RECOVERED'"
                    :severity="data.status === 'active' ? 'danger' : 'success'"
                  />
                </template>
              </Column>
              <Column field="detail" header="Detail" />
              <Column field="fired_at" header="Fired" style="width: 155px">
                <template #body="{ data }">
                  <span v-tooltip.top="formatTs(data.fired_at)" class="cell-mono ts-cell">
                    {{ relativeTs(data.fired_at) }}
                  </span>
                </template>
              </Column>
              <Column header="Duration" style="width: 90px">
                <template #body="{ data }">
                  <Tag :value="duration(data)" :severity="durationSeverity(data)" />
                </template>
              </Column>
              <template #empty>
                <div class="empty-state small">
                  <i class="pi pi-check-circle empty-icon" />
                  <span>No fires recorded.</span>
                </div>
              </template>
            </DataTable>
          </div>

          <div v-if="!selectedRule && !isNew" class="empty-state center">
            <i class="pi pi-bell empty-icon large" />
            <span>Select a rule or create a new one.</span>
          </div>
        </div>
      </SplitterPanel>
    </Splitter>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useConfirm } from 'primevue/useconfirm'
import { useAuthStore } from '../stores/auth.js'
import api from '../api/client.js'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import Message from 'primevue/message'
import Splitter from 'primevue/splitter'
import SplitterPanel from 'primevue/splitterpanel'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Select from 'primevue/select'
import Checkbox from 'primevue/checkbox'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'

const auth = useAuthStore()
const confirm = useConfirm()

const rules = ref([])
const fires = ref([])
const selectedRule = ref(null)
const isNew = ref(false)
const saving = ref(false)
const firesLoading = ref(false)
const error = ref(null)

const emptyForm = () => ({
  name: '',
  enabled: true,
  condition_type: 'cpu',
  threshold: 85,
  target: '',
  cooldown_minutes: 60,
  notify_on_recovery: true,
  email_to: '',
})

const form = ref(emptyForm())

const canEdit = computed(() => auth.hasPermission('alerts', 'write'))
const activeCount = computed(() => rules.value.filter(r => r.has_active_fire).length)

const conditionOptions = [
  { label: 'CPU %',           value: 'cpu' },
  { label: 'RAM %',           value: 'ram' },
  { label: 'Disk %',          value: 'disk' },
  { label: 'Service Down',    value: 'service_down' },
  { label: 'Process Missing', value: 'process_missing' },
]

const CONDITION_ICONS = {
  cpu:              'pi-microchip',
  ram:              'pi-database',
  disk:             'pi-hdd',
  service_down:     'pi-cog',
  process_missing:  'pi-code',
}

function conditionIcon(type) {
  return CONDITION_ICONS[type] ?? 'pi-bell'
}

function conditionSummary(rule) {
  if (['cpu', 'ram', 'disk'].includes(rule.condition_type)) {
    const label = { cpu: 'CPU', ram: 'RAM', disk: 'Disk' }[rule.condition_type]
    return `${label} > ${rule.threshold}% · ${rule.cooldown_minutes}min`
  }
  const label = rule.condition_type === 'service_down' ? 'service' : 'process'
  return `${label} ${rule.target || '—'} · ${rule.cooldown_minutes}min`
}

async function loadRules() {
  try {
    const r = await api.get('/alerts/rules')
    rules.value = r.data
    error.value = null
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load alert rules'
  }
}

async function loadFires(ruleId) {
  firesLoading.value = true
  try {
    const r = await api.get('/alerts/fires', { params: { rule_id: ruleId } })
    fires.value = r.data
  } catch {
    fires.value = []
  } finally {
    firesLoading.value = false
  }
}

function selectRule(rule) {
  isNew.value = false
  selectedRule.value = rule
  form.value = { ...rule }
  loadFires(rule.id)
}

function startNew() {
  isNew.value = true
  selectedRule.value = null
  form.value = emptyForm()
  fires.value = []
}

async function saveRule() {
  saving.value = true
  try {
    if (isNew.value) {
      await api.post('/alerts/rules', form.value)
    } else {
      await api.put(`/alerts/rules/${selectedRule.value.id}`, form.value)
    }
    await loadRules()
    isNew.value = false
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to save rule'
  } finally {
    saving.value = false
  }
}

async function toggleRule() {
  try {
    await api.patch(`/alerts/rules/${selectedRule.value.id}/toggle`)
    await loadRules()
    selectedRule.value = rules.value.find(r => r.id === selectedRule.value.id) || null
    if (selectedRule.value) form.value = { ...selectedRule.value }
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to toggle rule'
  }
}

function deleteRule() {
  confirm.require({
    message: `Delete rule "${selectedRule.value.name}"? This will also remove all fire history.`,
    header: 'Delete Rule',
    icon: 'pi pi-exclamation-triangle',
    acceptSeverity: 'danger',
    acceptLabel: 'Delete',
    accept: async () => {
      try {
        await api.delete(`/alerts/rules/${selectedRule.value.id}`)
        selectedRule.value = null
        isNew.value = false
        fires.value = []
        await loadRules()
      } catch (e) {
        error.value = e.response?.data?.detail || 'Failed to delete rule'
      }
    },
  })
}

function formatTs(ts) {
  if (!ts) return '—'
  return new Date(ts + 'Z').toLocaleString()
}

function relativeTs(ts) {
  if (!ts) return '—'
  const secs = Math.floor((Date.now() - new Date(ts + 'Z')) / 1000)
  if (secs < 60)   return `${secs}s ago`
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`
  return `${Math.floor(secs / 86400)}d ago`
}

function duration(fire) {
  const end = fire.recovered_at ? new Date(fire.recovered_at + 'Z') : new Date()
  const start = new Date(fire.fired_at + 'Z')
  const secs = Math.floor((end - start) / 1000)
  if (secs < 60)   return `${secs}s`
  if (secs < 3600) return `${Math.floor(secs / 60)}m`
  return `${Math.floor(secs / 3600)}h`
}

function durationSeverity(fire) {
  const end = fire.recovered_at ? new Date(fire.recovered_at + 'Z') : new Date()
  const start = new Date(fire.fired_at + 'Z')
  const mins = (end - start) / 60000
  if (mins < 5)   return 'success'
  if (mins < 60)  return 'warn'
  return 'danger'
}

onMounted(loadRules)
</script>

<style scoped>
.alerts-view { display: flex; flex-direction: column; height: 100%; gap: 12px; }
.page-header { display: flex; align-items: center; justify-content: space-between; }
.page-title { display: flex; align-items: center; gap: 10px; font-family: var(--font-mono); font-size: var(--text-sm); font-weight: 700; letter-spacing: 2px; color: var(--p-text-muted-color); }
.page-icon { color: var(--brand-orange); font-size: var(--text-lg); }
.alerts-splitter { flex: 1; border: none; background: transparent; }

/* Rule list */
.rule-list { padding: 8px; display: flex; flex-direction: column; gap: 3px; height: 100%; overflow-y: auto; }
.rule-item {
  display: flex; align-items: center; justify-content: space-between;
  gap: 10px; padding: 8px 10px;
  border-radius: 6px; cursor: pointer;
  border: 1px solid transparent;
  border-left: 3px solid var(--p-surface-border);
  transition: background 0.15s, border-color 0.15s;
}
.rule-item:hover { background: var(--p-surface-hover); }
.rule-item.selected { background: color-mix(in srgb, var(--brand-orange) 10%, transparent); border-color: color-mix(in srgb, var(--brand-orange) 30%, transparent); border-left-color: var(--brand-orange); }
.rule-item.item-firing { border-left-color: var(--p-red-500); }
.rule-item.item-disabled { opacity: 0.55; }

.rule-item-left { display: flex; align-items: center; gap: 8px; min-width: 0; }
.cond-icon { font-size: var(--text-sm); color: var(--p-text-muted-color); flex-shrink: 0; }
.rule-info { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.rule-name { font-size: var(--text-sm); color: var(--p-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.rule-meta { font-size: var(--text-xs); color: var(--p-text-muted-color); font-family: var(--font-mono); white-space: nowrap; }

.status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.dot-active { background: var(--p-red-500); box-shadow: 0 0 6px var(--p-red-500); animation: pulse 1.5s ease-in-out infinite; }
.dot-ok { background: var(--p-green-500); }
.dot-disabled { background: var(--p-surface-border); }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

/* Right panel */
.right-panel { display: flex; flex-direction: column; gap: 12px; height: 100%; overflow-y: auto; padding: 8px; }

/* Editor card */
.editor-card { background: var(--p-surface-card); border: 1px solid var(--p-surface-border); border-radius: 8px; overflow: hidden; }
.fire-banner {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 14px;
  background: color-mix(in srgb, var(--p-red-500) 12%, transparent);
  border-bottom: 1px solid color-mix(in srgb, var(--p-red-500) 30%, transparent);
  color: var(--p-red-400);
  font-size: var(--text-xs);
  font-family: var(--font-mono);
  letter-spacing: 0.5px;
}
.editor-header { display: flex; align-items: center; justify-content: space-between; padding: 12px 14px; border-bottom: 1px solid var(--p-surface-border); }
.editor-title-group { display: flex; align-items: center; gap: 8px; }
.editor-title { font-family: var(--font-mono); font-size: var(--text-xs); letter-spacing: 2px; color: var(--p-text-muted-color); font-weight: 600; }
.editor-actions { display: flex; gap: 6px; align-items: center; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; padding: 14px; }
.form-field { display: flex; flex-direction: column; gap: 4px; }
.form-field label { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-muted-color); letter-spacing: 1px; }
.form-field--checkbox { flex-direction: row; align-items: center; gap: 8px; }

/* Fire history */
.fire-history { display: flex; flex-direction: column; gap: 8px; }
.section-label { font-family: var(--font-mono); font-size: var(--text-xs); letter-spacing: 2px; color: var(--p-text-muted-color); font-weight: 600; padding: 0 2px; }
.cell-mono { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-muted-color); }
.ts-cell { cursor: default; }

/* Empty states */
.empty-state { display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 20px; color: var(--p-text-muted-color); font-size: var(--text-sm); }
.empty-state.small { padding: 12px; }
.empty-state.center { flex: 1; justify-content: center; }
.empty-icon { font-size: 22px; opacity: 0.4; }
.empty-icon.large { font-size: 32px; }
</style>
