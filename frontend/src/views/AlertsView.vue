<template>
  <div class="alerts-view">
    <div class="page-header">
      <div class="page-title">
        <i class="pi pi-bell page-icon" />
        <span>ALERTS</span>
        <Tag :value="`${rules.length} rules`" severity="secondary" />
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
            :class="{ selected: selectedRule?.id === rule.id }"
            @click="selectRule(rule)"
          >
            <span
              class="status-dot"
              :class="{
                'dot-active': rule.has_active_fire,
                'dot-ok': !rule.has_active_fire && rule.enabled,
                'dot-disabled': !rule.enabled,
              }"
            />
            <div class="rule-info">
              <span class="rule-name">{{ rule.name }}</span>
              <span class="rule-meta">{{ rule.condition_type }} · {{ rule.cooldown_minutes }}min</span>
            </div>
          </div>
          <div v-if="rules.length === 0" class="empty-state">No alert rules configured.</div>
        </div>
      </SplitterPanel>

      <!-- Right: editor + fire history -->
      <SplitterPanel :size="70" :min-size="40">
        <div class="right-panel">
          <!-- Rule editor -->
          <div v-if="selectedRule || isNew" class="editor-card">
            <div class="editor-header">
              <span class="editor-title">{{ isNew ? 'NEW RULE' : 'EDIT RULE' }}</span>
              <div class="editor-actions" v-if="auth.hasPermission('alerts', 'write')">
                <Button
                  v-if="!isNew"
                  :label="form.enabled ? 'Disable' : 'Enable'"
                  size="small"
                  severity="secondary"
                  @click="toggleRule"
                />
                <Button
                  v-if="!isNew"
                  label="Delete"
                  icon="pi pi-trash"
                  size="small"
                  severity="danger"
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
                <label>Type</label>
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
                <label>Target (name)</label>
                <InputText v-model="form.target" size="small" :disabled="!canEdit" placeholder="nginx" />
              </div>
              <div class="form-field">
                <label>Cooldown (minutes)</label>
                <InputNumber v-model="form.cooldown_minutes" :min="1" size="small" :disabled="!canEdit" />
              </div>
              <div class="form-field">
                <label>Email to</label>
                <InputText v-model="form.email_to" size="small" :disabled="!canEdit" />
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
              <Column field="fired_at" header="Fired" style="width: 160px">
                <template #body="{ data }">{{ formatTs(data.fired_at) }}</template>
              </Column>
              <Column field="recovered_at" header="Recovered" style="width: 160px">
                <template #body="{ data }">{{ data.recovered_at ? formatTs(data.recovered_at) : '—' }}</template>
              </Column>
              <Column header="Duration" style="width: 100px">
                <template #body="{ data }">{{ duration(data) }}</template>
              </Column>
              <template #empty>No fires recorded for this rule.</template>
            </DataTable>
          </div>

          <div v-if="!selectedRule && !isNew" class="empty-state center">
            Select a rule to view details or click "New Rule" to create one.
          </div>
        </div>
      </SplitterPanel>
    </Splitter>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
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

const conditionOptions = [
  { label: 'CPU %',           value: 'cpu' },
  { label: 'RAM %',           value: 'ram' },
  { label: 'Disk %',          value: 'disk' },
  { label: 'Service Down',    value: 'service_down' },
  { label: 'Process Missing', value: 'process_missing' },
]

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

async function deleteRule() {
  if (!confirm(`Delete rule "${selectedRule.value.name}"?`)) return
  try {
    await api.delete(`/alerts/rules/${selectedRule.value.id}`)
    selectedRule.value = null
    isNew.value = false
    fires.value = []
    await loadRules()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to delete rule'
  }
}

function formatTs(ts) {
  if (!ts) return '—'
  return new Date(ts + 'Z').toLocaleString()
}

function duration(fire) {
  const end = fire.recovered_at ? new Date(fire.recovered_at + 'Z') : new Date()
  const start = new Date(fire.fired_at + 'Z')
  const secs = Math.floor((end - start) / 1000)
  if (secs < 60) return `${secs}s`
  if (secs < 3600) return `${Math.floor(secs / 60)}m`
  return `${Math.floor(secs / 3600)}h`
}

onMounted(loadRules)
</script>

<style scoped>
.alerts-view { display: flex; flex-direction: column; height: 100%; gap: 12px; }
.page-header { display: flex; align-items: center; justify-content: space-between; }
.page-title { display: flex; align-items: center; gap: 10px; font-family: var(--font-mono); font-size: var(--text-sm); font-weight: 700; letter-spacing: 2px; color: var(--p-text-muted-color); }
.page-icon { color: var(--brand-orange); font-size: var(--text-lg); }
.alerts-splitter { flex: 1; border: none; background: transparent; }
.rule-list { padding: 8px; display: flex; flex-direction: column; gap: 4px; height: 100%; overflow-y: auto; }
.rule-item { display: flex; align-items: center; gap: 10px; padding: 8px 10px; border-radius: 6px; cursor: pointer; border: 1px solid transparent; transition: background 0.15s, border-color 0.15s; }
.rule-item:hover { background: var(--p-surface-hover); }
.rule-item.selected { background: color-mix(in srgb, var(--brand-orange) 10%, transparent); border-color: color-mix(in srgb, var(--brand-orange) 30%, transparent); }
.status-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.dot-active { background: var(--p-red-500); box-shadow: 0 0 6px var(--p-red-500); animation: pulse 1.5s ease-in-out infinite; }
.dot-ok { background: var(--p-green-500); }
.dot-disabled { background: var(--p-surface-border); }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.rule-info { display: flex; flex-direction: column; gap: 2px; }
.rule-name { font-size: var(--text-sm); color: var(--p-text-color); }
.rule-meta { font-size: var(--text-xs); color: var(--p-text-muted-color); font-family: var(--font-mono); }
.right-panel { display: flex; flex-direction: column; gap: 12px; height: 100%; overflow-y: auto; padding: 8px; }
.editor-card { background: var(--p-surface-card); border: 1px solid var(--p-surface-border); border-radius: 8px; padding: 14px; }
.editor-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.editor-title { font-family: var(--font-mono); font-size: var(--text-xs); letter-spacing: 2px; color: var(--p-text-muted-color); font-weight: 600; }
.editor-actions { display: flex; gap: 8px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.form-field { display: flex; flex-direction: column; gap: 4px; }
.form-field label { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-muted-color); letter-spacing: 1px; }
.form-field--checkbox { flex-direction: row; align-items: center; gap: 8px; }
.fire-history { display: flex; flex-direction: column; gap: 8px; }
.section-label { font-family: var(--font-mono); font-size: var(--text-xs); letter-spacing: 2px; color: var(--p-text-muted-color); font-weight: 600; }
.empty-state { padding: 24px; text-align: center; color: var(--p-text-muted-color); font-size: var(--text-sm); }
.empty-state.center { flex: 1; display: flex; align-items: center; justify-content: center; }
</style>
