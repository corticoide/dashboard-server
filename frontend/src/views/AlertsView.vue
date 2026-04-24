<template>
  <div class="alerts-view">
    <div class="page-header">
      <div class="page-title">
        <i class="pi pi-bell page-icon" />
        <span>ALERTS</span>
      </div>
      <Button
        v-if="auth.hasPermission('alerts', 'write')"
        label="New Rule"
        icon="pi pi-plus"
        size="small"
        @click="startNew"
      />
    </div>

    <!-- Summary bar -->
    <div class="summary-bar">
      <div class="summary-pill">
        <span class="pill-count">{{ rules.length }}</span>
        <span class="pill-label">RULES</span>
      </div>
      <div class="summary-pill pill-firing" v-if="activeCount > 0">
        <span class="pill-dot dot-firing" />
        <span class="pill-count">{{ activeCount }}</span>
        <span class="pill-label">FIRING</span>
      </div>
      <div class="summary-pill pill-ok">
        <span class="pill-dot dot-ok" />
        <span class="pill-count">{{ okCount }}</span>
        <span class="pill-label">OK</span>
      </div>
      <div class="summary-pill pill-disabled" v-if="disabledCount > 0">
        <span class="pill-count">{{ disabledCount }}</span>
        <span class="pill-label">DISABLED</span>
      </div>
    </div>

    <div v-if="error" class="banner banner-error"><i class="pi pi-times-circle" />{{ error }}</div>

    <Splitter class="alerts-splitter" :gutter-size="6">
      <!-- Left: rule list -->
      <SplitterPanel :size="32" :min-size="22">
        <div class="rule-panel">
          <div class="list-panel-header">
            <i class="pi pi-list-check list-header-icon" />
            <span class="list-header-label">RULES</span>
            <span v-if="rules.length" class="list-header-count">{{ rules.length }}</span>
          </div>
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
              <div class="rule-icon-wrap" :class="`ctype-${rule.condition_type}`">
                <i :class="['pi', conditionIcon(rule.condition_type)]" />
              </div>
              <div class="rule-info">
                <span class="rule-name">{{ rule.name }}</span>
                <span class="rule-meta">{{ conditionSummary(rule) }}</span>
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
              <span class="empty-hint">Create a rule to monitor CPU, RAM, disk, services or processes.</span>
            </div>
          </div>
        </div>
      </SplitterPanel>

      <!-- Right: editor + fire history -->
      <SplitterPanel :size="68" :min-size="40">
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
                <span v-if="!isNew" :class="form.enabled ? 'badge-green' : 'badge-neutral'">
                  {{ form.enabled ? 'ENABLED' : 'DISABLED' }}
                </span>
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

            <div class="form-body">
              <div class="form-section">
                <span class="form-section-label">IDENTIFICATION</span>
                <div class="form-row">
                  <div class="form-field">
                    <label>Rule name</label>
                    <InputText v-model="form.name" size="small" :disabled="!canEdit" placeholder="e.g. High CPU Alert" />
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
                </div>
              </div>

              <div class="form-section">
                <span class="form-section-label">TRIGGER</span>
                <div class="form-row">
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
                </div>
              </div>

              <div class="form-section">
                <span class="form-section-label">NOTIFICATION</span>
                <div class="form-row form-row--mixed">
                  <div class="form-field form-field--grow">
                    <label>Alert email</label>
                    <InputText v-model="form.email_to" size="small" :disabled="!canEdit" placeholder="you@example.com" />
                  </div>
                  <div class="form-field form-field--checkbox">
                    <Checkbox v-model="form.notify_on_recovery" :binary="true" :disabled="!canEdit" />
                    <label>Notify on recovery</label>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Fire history -->
          <div class="fire-history-card" v-if="selectedRule && !isNew">
            <div class="card-header">
              <div class="card-header-title">
                <i class="pi pi-history" />
                FIRE HISTORY
              </div>
              <span class="card-header-count" v-if="fires.length > 0">{{ fires.length }} events</span>
            </div>
            <DataTable :value="fires" size="small" class="fire-table" :loading="firesLoading">
              <Column field="status" header="Status" style="width: 120px">
                <template #body="{ data }">
                  <div class="fire-status-cell">
                    <span class="fire-dot" :class="data.status === 'active' ? 'fire-dot--active' : 'fire-dot--recovered'" />
                    <span :class="data.status === 'active' ? 'badge-red' : 'badge-green'">
                      {{ data.status === 'active' ? 'ACTIVE' : 'RECOVERED' }}
                    </span>
                  </div>
                </template>
              </Column>
              <Column field="detail" header="Detail" />
              <Column field="fired_at" header="Fired at" style="width: 155px">
                <template #body="{ data }">
                  <span v-tooltip.top="formatTs(data.fired_at)" class="cell-mono ts-cell">
                    {{ relativeTs(data.fired_at) }}
                  </span>
                </template>
              </Column>
              <Column header="Duration" style="width: 90px">
                <template #body="{ data }">
                  <span :class="durationBadgeClass(data)">{{ duration(data) }}</span>
                </template>
              </Column>
              <template #empty>
                <div class="fire-empty">
                  <i class="pi pi-check-circle" style="font-size: 18px; opacity: 0.35;" />
                  <span>No fires recorded for this rule.</span>
                </div>
              </template>
            </DataTable>
          </div>

          <div v-if="!selectedRule && !isNew" class="select-prompt">
            <div class="select-prompt-icon">
              <i class="pi pi-bell" />
            </div>
            <span class="select-prompt-text">Select a rule to view or edit it</span>
            <span class="select-prompt-hint">or create a new one with the button above</span>
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
const disabledCount = computed(() => rules.value.filter(r => !r.enabled).length)
const okCount = computed(() => rules.value.filter(r => r.enabled && !r.has_active_fire).length)

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

function durationBadgeClass(fire) {
  const end = fire.recovered_at ? new Date(fire.recovered_at + 'Z') : new Date()
  const start = new Date(fire.fired_at + 'Z')
  const mins = (end - start) / 60000
  if (mins < 5)   return 'badge-green'
  if (mins < 60)  return 'badge-yellow'
  return 'badge-red'
}

onMounted(loadRules)
</script>

<style scoped>
.alerts-view { display: flex; flex-direction: column; height: 100%; gap: 12px; }

/* ── Page header ─────────────────────────────────── */
.page-header { display: flex; align-items: center; justify-content: space-between; }
.page-title {
  display: flex; align-items: center; gap: 10px;
  font-family: var(--font-mono); font-size: var(--text-sm);
  font-weight: 700; letter-spacing: 2px; color: var(--p-text-muted-color);
}
.page-icon { color: var(--brand-orange); font-size: var(--text-lg); }

/* ── Summary bar ─────────────────────────────────── */
.summary-bar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.summary-pill {
  display: flex; align-items: center; gap: 6px;
  padding: 4px 12px; border-radius: 20px;
  border: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
  font-family: var(--font-mono);
}
.pill-firing {
  border-color: color-mix(in srgb, var(--p-red-500) 35%, transparent);
  background: color-mix(in srgb, var(--p-red-500) 7%, transparent);
}
.pill-ok {
  border-color: color-mix(in srgb, var(--p-green-500) 25%, transparent);
  background: color-mix(in srgb, var(--p-green-500) 5%, transparent);
}
.pill-disabled { opacity: 0.65; }
.pill-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.dot-firing { background: var(--p-red-500); animation: pulse 1.5s ease-in-out infinite; }
.dot-ok { background: var(--p-green-500); }
.pill-count { font-size: var(--text-base); font-weight: 700; color: var(--p-text-color); line-height: 1; }
.pill-label { font-size: var(--text-2xs); letter-spacing: 1.5px; color: var(--p-text-muted-color); }

/* ── Splitter ────────────────────────────────────── */
.alerts-splitter { flex: 1; border-radius: 8px; overflow: hidden; min-height: 0; }

/* ── Left panel ──────────────────────────────────── */
.rule-panel {
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
.list-header-count {
  font-family: var(--font-mono); font-size: var(--text-2xs);
  font-weight: 600; color: var(--brand-orange);
  background: color-mix(in srgb, var(--brand-orange) 12%, transparent);
  border-radius: 4px; padding: 1px 6px;
}

.rule-list { flex: 1; padding: 6px; display: flex; flex-direction: column; gap: 2px; overflow-y: auto; }

.rule-item {
  display: flex; align-items: center;
  gap: 9px; padding: 8px 9px;
  border-radius: 6px; cursor: pointer;
  border: 1px solid transparent;
  border-left: 3px solid transparent;
  transition: background 0.12s, border-color 0.12s;
}
.rule-item:hover { background: var(--p-surface-hover); border-left-color: var(--p-surface-border); }
.rule-item.selected {
  background: color-mix(in srgb, var(--brand-orange) 8%, transparent);
  border-color: color-mix(in srgb, var(--brand-orange) 20%, transparent);
  border-left-color: var(--brand-orange);
}
.rule-item.item-firing {
  border-left-color: var(--p-red-500);
  background: color-mix(in srgb, var(--p-red-500) 4%, transparent);
}
.rule-item.item-firing.selected {
  background: color-mix(in srgb, var(--p-red-500) 8%, transparent);
  border-color: color-mix(in srgb, var(--p-red-500) 20%, transparent);
}
.rule-item.item-disabled { opacity: 0.5; }

/* Condition type icon */
.rule-icon-wrap {
  width: 30px; height: 30px; border-radius: 7px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px;
  background: var(--p-surface-hover);
  color: var(--p-text-muted-color);
  transition: background 0.12s;
}
.ctype-cpu            { background: color-mix(in srgb, var(--brand-orange) 14%, transparent); color: var(--brand-orange); }
.ctype-ram            { background: color-mix(in srgb, var(--p-blue-400)   14%, transparent); color: var(--p-blue-400); }
.ctype-disk           { background: color-mix(in srgb, var(--p-green-500)  14%, transparent); color: var(--p-green-500); }
.ctype-service_down   { background: color-mix(in srgb, var(--p-red-400)    14%, transparent); color: var(--p-red-400); }
.ctype-process_missing{ background: color-mix(in srgb, var(--p-purple-400) 14%, transparent); color: var(--p-purple-400); }

.rule-info { display: flex; flex-direction: column; gap: 2px; min-width: 0; flex: 1; }
.rule-name {
  font-size: var(--text-sm); font-weight: 500;
  color: var(--p-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.rule-meta { font-size: var(--text-xs); color: var(--p-text-muted-color); font-family: var(--font-mono); white-space: nowrap; }

.status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.dot-active  { background: var(--p-red-500); box-shadow: 0 0 5px var(--p-red-500); animation: pulse 1.5s ease-in-out infinite; }
.dot-ok      { background: var(--p-green-500); }
.dot-disabled{ background: var(--p-surface-border); }

@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.35; } }

/* ── Right panel ─────────────────────────────────── */
.right-panel { display: flex; flex-direction: column; gap: 10px; height: 100%; overflow-y: auto; padding: 8px; }

/* ── Editor card ─────────────────────────────────── */
.editor-card {
  background: var(--p-surface-card);
  border: 1px solid var(--p-surface-border);
  border-radius: 8px;
  overflow: hidden;
  flex-shrink: 0;
}

.fire-banner {
  display: flex; align-items: center; gap: 8px;
  padding: 7px 14px;
  background: color-mix(in srgb, var(--p-red-500) 10%, transparent);
  border-bottom: 1px solid color-mix(in srgb, var(--p-red-500) 25%, transparent);
  color: var(--p-red-400);
  font-size: var(--text-xs); font-family: var(--font-mono); letter-spacing: 0.5px;
}

.editor-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 9px 14px;
  border-bottom: 1px solid var(--p-surface-border);
  background: color-mix(in srgb, var(--p-surface-hover) 40%, transparent);
}
.editor-title-group { display: flex; align-items: center; gap: 8px; }
.editor-title {
  font-family: var(--font-mono); font-size: var(--text-xs);
  letter-spacing: 2px; color: var(--p-text-muted-color); font-weight: 600;
}
.editor-actions { display: flex; gap: 6px; align-items: center; }

/* Form sections */
.form-body { display: flex; flex-direction: column; }
.form-section { padding: 11px 14px; }
.form-section + .form-section { border-top: 1px solid var(--p-surface-border); }
.form-section-label {
  display: block;
  font-family: var(--font-mono); font-size: var(--text-2xs);
  letter-spacing: 2px; color: var(--p-text-muted-color);
  font-weight: 600; margin-bottom: 9px; opacity: 0.6;
}
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.form-row--mixed { align-items: end; }
.form-field { display: flex; flex-direction: column; gap: 4px; }
.form-field--grow { flex: 1; }
.form-field--checkbox { flex-direction: row !important; align-items: center; gap: 8px; padding-bottom: 3px; }
.form-field label {
  font-family: var(--font-mono); font-size: var(--text-xs);
  color: var(--p-text-muted-color); letter-spacing: 0.5px;
}

/* ── Fire history card ───────────────────────────── */
.fire-history-card {
  background: var(--p-surface-card);
  border: 1px solid var(--p-surface-border);
  border-radius: 8px;
  overflow: hidden;
  flex-shrink: 0;
}
.card-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 9px 14px;
  border-bottom: 1px solid var(--p-surface-border);
  background: color-mix(in srgb, var(--p-surface-hover) 40%, transparent);
}
.card-header-title {
  display: flex; align-items: center; gap: 6px;
  font-family: var(--font-mono); font-size: var(--text-xs);
  letter-spacing: 2px; color: var(--p-text-muted-color); font-weight: 600;
}
.card-header-title .pi { font-size: 11px; }
.card-header-count {
  font-family: var(--font-mono); font-size: var(--text-xs);
  color: var(--p-text-muted-color);
  background: var(--p-surface-hover);
  padding: 1px 7px; border-radius: 10px;
}

.fire-status-cell { display: flex; align-items: center; gap: 6px; }
.fire-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.fire-dot--active    { background: var(--p-red-500); box-shadow: 0 0 4px var(--p-red-500); animation: pulse 1.5s ease-in-out infinite; }
.fire-dot--recovered { background: var(--p-green-500); }

:deep(.fire-table .p-datatable-thead th) {
  background: transparent;
  padding: 7px 10px;
}
:deep(.fire-table .p-datatable-column-header-content) {
  font-family: var(--font-mono); font-size: var(--text-2xs);
  letter-spacing: 1.5px; color: var(--p-text-muted-color);
  text-transform: uppercase; font-weight: 600;
}
:deep(.fire-table .p-datatable-tbody td) { padding: 6px 10px; }

.fire-empty {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  padding: 20px; color: var(--p-text-muted-color); font-size: var(--text-sm);
  font-family: var(--font-mono);
}

.cell-mono { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-muted-color); }
.ts-cell { cursor: default; }

/* ── Select prompt (empty right panel) ───────────── */
.select-prompt {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 8px;
  color: var(--p-text-muted-color);
}
.select-prompt-icon {
  width: 48px; height: 48px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  background: var(--p-surface-hover);
  border: 1px solid var(--p-surface-border);
  font-size: 20px; color: var(--p-text-muted-color); opacity: 0.5;
  margin-bottom: 4px;
}
.select-prompt-text { font-size: var(--text-sm); color: var(--p-text-muted-color); }
.select-prompt-hint { font-size: var(--text-xs); font-family: var(--font-mono); color: var(--p-text-muted-color); opacity: 0.6; }

/* ── Rule list empty state ───────────────────────── */
.empty-state {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  padding: 28px 16px; color: var(--p-text-muted-color); font-size: var(--text-sm);
  text-align: center;
}
.empty-icon { font-size: 24px; opacity: 0.3; }
.empty-hint { font-size: var(--text-xs); font-family: var(--font-mono); opacity: 0.6; }
</style>
