<template>
  <div class="pipelines-view">
    <Splitter class="pipelines-splitter">

      <!-- ── Panel 1: Lista de pipelines ── -->
      <SplitterPanel :size="25" :minSize="18">
        <div class="list-panel">
          <div class="list-panel-header">
            <i class="pi pi-sitemap list-header-icon" />
            <span class="list-header-label">PIPELINES</span>
            <span v-if="pipelines.length" class="list-header-count">{{ pipelines.length }}</span>
            <Button v-if="isAdmin" icon="pi pi-plus" text rounded size="small"
              v-tooltip.right="'New pipeline'" @click="startNewPipeline" />
            <Button v-if="isAdmin" icon="pi pi-upload" text rounded size="small"
              v-tooltip.right="'Import pipeline from JSON'" @click="triggerImport" />
            <input ref="importInputRef" type="file" accept=".json" style="display:none" @change="onImportFile" />
            <Button icon="pi pi-refresh" text rounded size="small" :loading="loading"
              v-tooltip.right="'Refresh'" @click="loadPipelines" />
          </div>

          <!-- Skeletons de carga -->
          <div v-if="loading && !pipelines.length" class="pipeline-list">
            <div v-for="i in 4" :key="i" class="skeleton-card">
              <Skeleton height="13px" width="65%" style="margin-bottom: 6px;" />
              <Skeleton height="10px" width="40%" />
            </div>
          </div>

          <div v-else class="pipeline-list">
            <!-- Explanatory empty state -->
            <div v-if="!pipelines.length" class="empty-state">
              <i class="pi pi-sitemap empty-icon" />
              <span class="empty-title">No pipelines yet</span>
              <span class="empty-text">
                A pipeline is a chain of steps that run in order.<br/>
                You can combine shell commands, saved scripts, and automation modules (move files, send emails, etc.).
              </span>
              <Button v-if="isAdmin" label="Create first pipeline" size="small"
                icon="pi pi-plus" @click="startNewPipeline" />
            </div>

            <div
              v-for="p in pipelines" :key="p.id"
              class="pipeline-card"
              :class="{ 'pipeline-card--active': selectedPipeline?.id === p.id }"
              @click="selectPipeline(p)"
            >
              <div class="pipeline-card-name">
                <span class="status-dot" :class="statusDotClass(p)" />
                <span class="pipeline-card-title">{{ p.name }}</span>
              </div>
              <div class="pipeline-card-footer">
                <span class="pipeline-card-meta">{{ p.step_count }} step{{ p.step_count !== 1 ? 's' : '' }}</span>
                <span v-if="p.last_run_at" class="pipeline-card-time">{{ timeAgo(p.last_run_at) }}</span>
              </div>
            </div>
          </div>
        </div>
      </SplitterPanel>

      <!-- ── Panel 2: Editor ── -->
      <SplitterPanel :size="50" :minSize="35">
        <div class="editor-panel">

          <!-- No selection -->
          <div v-if="!selectedPipeline && !editingNew" class="empty-editor">
            <i class="pi pi-sitemap" style="font-size: 40px; opacity: 0.18; color: var(--p-text-muted-color);" />
            <span class="empty-editor-title">Select a pipeline</span>
            <span class="empty-editor-sub">or create a new one with the <i class="pi pi-plus" style="font-size:10px" /> button</span>
          </div>

          <template v-else>
            <!-- Toolbar -->
            <div class="editor-toolbar">
              <div class="editor-toolbar-left">
                <i class="pi pi-sitemap" style="color: var(--brand-orange); flex-shrink: 0;" />
                <input
                  v-model="form.name"
                  class="pipeline-name-input"
                  placeholder="Pipeline name"
                  :disabled="!isAdmin"
                />
                <span v-if="isDirty" class="unsaved-indicator" v-tooltip.right="'Unsaved changes'">●</span>
              </div>
              <div class="editor-toolbar-right">
                <Button
                  v-if="selectedPipeline && !editingNew"
                  icon="pi pi-play" label="Run"
                  size="small" severity="success"
                  @click="runPipeline" :loading="running"
                />
                <Button
                  v-if="isAdmin"
                  icon="pi pi-check" :label="editingNew ? 'Create' : 'Save'"
                  size="small"
                  @click="savePipeline" :loading="saving"
                  :disabled="!form.name.trim()"
                />
                <Button
                  v-if="selectedPipeline && !editingNew"
                  icon="pi pi-download" text rounded size="small"
                  v-tooltip.left="'Export as JSON'"
                  @click="exportPipeline"
                />
                <Button
                  v-if="isAdmin && selectedPipeline"
                  icon="pi pi-trash" text rounded size="small"
                  severity="danger" v-tooltip.left="'Delete pipeline'"
                  @click="confirmDelete"
                />
              </div>
            </div>

            <!-- Description -->
            <div class="editor-description">
              <InputText
                v-model="form.description"
                placeholder="Pipeline description (optional)"
                size="small" fluid :disabled="!isAdmin"
              />
            </div>

            <!-- Steps header -->
            <div class="steps-header">
              <span class="steps-label">STEPS</span>
              <span v-if="form.steps.length" class="steps-count-badge">{{ form.steps.length }}</span>
              <div style="flex: 1" />
              <Button v-if="isAdmin" icon="pi pi-plus" text rounded size="small"
                label="Add step" @click="addStep" />
            </div>

            <!-- Steps list (scrollable) -->
            <div class="steps-list">
              <!-- Empty steps state -->
              <div v-if="!form.steps.length" class="empty-steps">
                <i class="pi pi-list-check" style="font-size: 28px; opacity: 0.25;" />
                <span>This pipeline has no steps yet.</span>
                <span class="empty-steps-hint">
                  Each step can be a <strong>shell command</strong> (e.g. <code>systemctl restart nginx</code>),
                  a <strong>saved script</strong>, or a <strong>module</strong> such as move files, compress, send emails, etc.
                </span>
                <Button v-if="isAdmin" label="Add first step" size="small"
                  icon="pi pi-plus" @click="addStep" />
              </div>

              <!-- Steps accordion -->
              <div
                v-for="(step, idx) in form.steps" :key="step._key"
                class="step-card"
                :class="{ 'step-card--open': activeStepIdx === idx }"
              >
                <!-- Header (always visible, click to open/close) -->
                <div class="step-card-header" @click="toggleStep(idx)">
                  <span class="step-order">{{ idx + 1 }}</span>

                  <div class="step-card-info">
                    <div class="step-card-info-top">
                      <span class="step-type-badge" :class="`step-type-badge--${step.step_type}`">
                        {{ stepIcon(step) }} {{ stepTypeShort(step) }}
                      </span>
                      <span class="step-name">{{ step.name || '(unnamed)' }}</span>
                    </div>
                    <div v-if="activeStepIdx !== idx" class="step-card-subtitle">
                      <span :class="conditionClass(step)" class="step-condition-text">{{ conditionLabel(step) }}</span>
                      <span v-if="stepPreview(step)" class="step-preview-sep">·</span>
                      <span v-if="stepPreview(step)" class="step-preview-text">{{ stepPreview(step) }}</span>
                    </div>
                  </div>

                  <div class="step-card-actions" @click.stop>
                    <template v-if="isAdmin">
                      <Button icon="pi pi-chevron-up" text rounded size="small"
                        v-tooltip.top="'Move up'" :disabled="idx === 0" @click="moveStep(idx, -1)" />
                      <Button icon="pi pi-chevron-down" text rounded size="small"
                        v-tooltip.top="'Move down'" :disabled="idx === form.steps.length - 1" @click="moveStep(idx, 1)" />
                      <Button icon="pi pi-trash" text rounded size="small"
                        severity="danger" v-tooltip.top="'Delete step'" @click="removeStep(idx)" />
                    </template>
                  </div>

                  <div class="step-chevron">
                    <i class="pi" :class="activeStepIdx === idx ? 'pi-chevron-up' : 'pi-chevron-down'" />
                  </div>
                </div>

                <!-- Cuerpo animado -->
                <Transition :css="false" @enter="onAccordionEnter" @leave="onAccordionLeave">
                  <div v-if="activeStepIdx === idx" class="step-body">
                    <StepConfigEditor
                      v-model="form.steps[idx]"
                      :favorites="favorites"
                      :pipelines="pipelines"
                      :disabled="!isAdmin"
                    />
                  </div>
                </Transition>
              </div>
            </div>
          </template>
        </div>
      </SplitterPanel>

      <!-- ── Panel 3: Flujo + Historial ── -->
      <SplitterPanel :size="25" :minSize="18">
        <div class="flow-panel">

          <!-- Diagrama de flujo -->
          <div class="flow-section">
            <div class="section-label">FLOW</div>
            <div v-if="form.steps.length" class="flow-diagram">
              <template v-for="(step, idx) in form.steps" :key="step._key">
                <div
                  class="flow-node" :class="`flow-node--${step.step_type}`"
                  @click="toggleStep(idx)" style="cursor: pointer;"
                  v-tooltip.left="stepPreview(step) || undefined"
                >
                  <span class="flow-node-icon">{{ stepIcon(step) }}</span>
                  <span class="flow-node-name">{{ step.name || stepTypeShort(step) }}</span>
                </div>
                <div v-if="idx < form.steps.length - 1" class="flow-connector">
                  <div class="flow-line" :class="connectorClass(step)" />
                  <span class="flow-connector-label" :class="connectorClass(step)">
                    {{ conditionArrow(step) }}
                  </span>
                </div>
              </template>
            </div>
            <div v-else class="flow-empty">
              <span>The flow appears here when there are steps.</span>
            </div>
          </div>

          <!-- Historial de ejecuciones -->
          <div class="runs-section">
            <div class="section-label">
              RUNS
              <span v-if="hasRunningRun" class="running-indicator">
                <i class="pi pi-spin pi-spinner" style="font-size: 9px;" /> running
              </span>
            </div>

            <div v-if="!recentRuns.length" class="runs-empty">
              <span>No runs recorded.</span>
              <span v-if="selectedPipeline && !editingNew" class="runs-empty-hint">
                Press "Run" to execute this pipeline manually.
              </span>
            </div>

            <div v-else class="runs-list">
              <div
                v-for="run in recentRuns" :key="run.id"
                class="run-item" :class="`run-item--${run.status}`"
                @click="openRunDetail(run.id)"
              >
                <div class="run-item-left">
                  <i class="pi run-status-icon" :class="runStatusIcon(run.status)" />
                  <div class="run-item-info">
                    <span class="run-item-label">{{ runStatusLabel(run.status) }}</span>
                    <span class="run-item-time">{{ timeAgo(run.started_at) }}</span>
                  </div>
                </div>
                <div class="run-item-right">
                  <span v-if="run.status === 'running'" class="run-live-badge">live</span>
                  <span v-else-if="run.ended_at" class="run-duration">
                    {{ duration(run.started_at, run.ended_at) }}
                  </span>
                  <i class="pi pi-chevron-right run-chevron" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </SplitterPanel>

    </Splitter>

    <!-- Run detail dialog -->
    <Dialog
      v-model:visible="showRunDetail" modal
      header="Run Detail"
      :style="{ width: '720px', maxWidth: '95vw' }"
      :draggable="false"
    >
      <div v-if="runDetail" class="run-detail">
        <!-- Resumen del run -->
        <div class="run-detail-summary">
          <span class="run-detail-badge" :class="`run-detail-badge--${runDetail.status}`">
            <i class="pi" :class="runStatusIcon(runDetail.status)" />
            {{ runStatusLabel(runDetail.status) }}
          </span>
          <span class="run-detail-meta">
            Triggered by <strong>{{ runDetail.triggered_by }}</strong>
          </span>
          <span v-if="runDetail.ended_at" class="run-detail-meta">
            Total duration: <strong>{{ duration(runDetail.started_at, runDetail.ended_at) }}</strong>
          </span>
        </div>

        <!-- Step runs -->
        <div class="step-runs-list">
          <div
            v-for="sr in runDetail.step_runs" :key="sr.id"
            class="step-run-card" :class="`step-run-card--${sr.status}`"
          >
            <div class="step-run-header">
              <span class="step-run-number">#{{ sr.step_order + 1 }}</span>
              <i class="pi step-run-icon" :class="runStatusIcon(sr.status)" />
              <span class="step-run-name">
                {{ getStepNameByOrder(sr.step_order) || `Step ${sr.step_order + 1}` }}
              </span>
              <span class="step-run-status-badge" :class="`step-run-status--${sr.status}`">
                {{ runStatusLabel(sr.status) }}
              </span>
              <span v-if="sr.ended_at" class="step-run-duration">
                {{ duration(sr.started_at, sr.ended_at) }}
              </span>
            </div>
            <div v-if="sr.status === 'skipped'" class="step-run-skipped">
              <i class="pi pi-info-circle" />
              This step was skipped due to the conditions of the previous step.
            </div>
            <pre v-if="sr.output" class="step-run-output">{{ sr.output }}</pre>
          </div>
        </div>
      </div>
    </Dialog>

    <ConfirmDialog />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import Splitter from 'primevue/splitter'
import SplitterPanel from 'primevue/splitterpanel'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Dialog from 'primevue/dialog'
import ConfirmDialog from 'primevue/confirmdialog'
import Skeleton from 'primevue/skeleton'
import api from '../api/client.js'
import { useAuthStore } from '../stores/auth.js'
import StepConfigEditor from '../components/pipelines/StepConfigEditor.vue'

const toast = useToast()
const confirm = useConfirm()
const auth = useAuthStore()
const isAdmin = computed(() => auth.isAdmin)

const pipelines = ref([])
const loading = ref(false)
const saving = ref(false)
const running = ref(false)
const selectedPipeline = ref(null)
const editingNew = ref(false)
const activeStepIdx = ref(null)
const recentRuns = ref([])
const showRunDetail = ref(false)
const runDetail = ref(null)
const favorites = ref([])
const importInputRef = ref(null)

const form = ref({ name: '', description: '', steps: [] })
// Snapshot para detectar cambios sin guardar
const savedForm = ref(null)

const isDirty = computed(() => {
  if (!savedForm.value) {
    return editingNew.value && (form.value.name.trim() !== '' || form.value.steps.length > 0)
  }
  return JSON.stringify(form.value) !== JSON.stringify(savedForm.value)
})

const hasRunningRun = computed(() => recentRuns.value.some(r => r.status === 'running'))

let _pollTimer = null
let _stepKey = 0
function newStepKey() { return ++_stepKey }

function emptyStep() {
  return {
    _key: newStepKey(),
    name: '',
    step_type: 'shell',
    config: { command: '' },
    on_success: 'continue',
    on_failure: 'stop',
    order: 0,
  }
}

// ── Helpers de estado ──────────────────────────────────────────────────────

function statusDotClass(p) {
  if (p.last_run_status === 'success') return 'status-dot--success'
  if (p.last_run_status === 'failed') return 'status-dot--error'
  if (p.last_run_status === 'running') return 'status-dot--running'
  return 'status-dot--none'
}

function runStatusIcon(status) {
  if (status === 'success') return 'pi-check-circle'
  if (status === 'failed') return 'pi-times-circle'
  if (status === 'running') return 'pi-spin pi-spinner'
  if (status === 'skipped') return 'pi-minus-circle'
  return 'pi-circle'
}

function runStatusLabel(status) {
  const m = { success: 'Success', failed: 'Failed', running: 'Running', skipped: 'Skipped' }
  return m[status] || status
}

function getStepNameByOrder(order) {
  return form.value.steps[order]?.name || null
}

// ── Carga de datos ─────────────────────────────────────────────────────────

async function loadPipelines() {
  loading.value = true
  try {
    const { data } = await api.get('/pipelines')
    pipelines.value = data
  } catch {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Could not load pipelines', life: 4000 })
  } finally {
    loading.value = false
  }
}

async function selectPipeline(p) {
  selectedPipeline.value = p
  editingNew.value = false
  activeStepIdx.value = null
  stopPolling()
  try {
    const [detailRes, runsRes] = await Promise.all([
      api.get(`/pipelines/${p.id}`),
      api.get(`/pipelines/${p.id}/runs`),
    ])
    const formData = {
      name: detailRes.data.name,
      description: detailRes.data.description || '',
      steps: detailRes.data.steps.map(s => ({ ...s, _key: newStepKey() })),
    }
    form.value = formData
    savedForm.value = JSON.parse(JSON.stringify(formData))
    recentRuns.value = runsRes.data.slice(0, 8)
    if (hasRunningRun.value) startPolling()
  } catch {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Could not load pipeline', life: 4000 })
  }
}

function startNewPipeline() {
  selectedPipeline.value = null
  editingNew.value = true
  activeStepIdx.value = null
  recentRuns.value = []
  stopPolling()
  form.value = { name: '', description: '', steps: [] }
  savedForm.value = null
}

// ── Step editing ──────────────────────────────────────────────────────────

function toggleStep(idx) {
  activeStepIdx.value = activeStepIdx.value === idx ? null : idx
}

function onAccordionEnter(el, done) {
  el.style.height = '0px'
  el.style.overflow = 'hidden'
  el.style.opacity = '0'
  el.offsetHeight // force reflow so the transition starts from 0
  el.style.transition = 'height 0.22s ease, opacity 0.18s ease'
  el.style.height = el.scrollHeight + 'px'
  el.style.opacity = '1'
  el.addEventListener('transitionend', () => {
    el.style.height = 'auto'
    el.style.overflow = ''
    done()
  }, { once: true })
}

function onAccordionLeave(el, done) {
  el.style.height = el.scrollHeight + 'px'
  el.style.overflow = 'hidden'
  el.offsetHeight // fuerza reflow
  el.style.transition = 'height 0.18s ease, opacity 0.15s ease'
  el.style.height = '0px'
  el.style.opacity = '0'
  el.addEventListener('transitionend', done, { once: true })
}

function addStep() {
  const s = emptyStep()
  s.order = form.value.steps.length
  form.value.steps.push(s)
  activeStepIdx.value = form.value.steps.length - 1
}

function removeStep(idx) {
  form.value.steps.splice(idx, 1)
  if (activeStepIdx.value === idx) {
    activeStepIdx.value = null
  } else if (activeStepIdx.value > idx) {
    activeStepIdx.value--
  }
}

function moveStep(idx, dir) {
  const target = idx + dir
  if (target < 0 || target >= form.value.steps.length) return
  const steps = [...form.value.steps]
  ;[steps[idx], steps[target]] = [steps[target], steps[idx]]
  form.value.steps = steps
  activeStepIdx.value = target
}

// ── Save / create ─────────────────────────────────────────────────────────

async function savePipeline() {
  if (!form.value.name.trim()) {
    toast.add({ severity: 'warn', summary: 'Name required', detail: 'The pipeline must have a name', life: 3000 })
    return
  }
  saving.value = true
  try {
    const body = {
      name: form.value.name,
      description: form.value.description,
      steps: form.value.steps.map((s, i) => ({
        name: s.name, step_type: s.step_type, config: s.config,
        on_success: s.on_success, on_failure: s.on_failure, order: i,
      })),
    }
    if (editingNew.value) {
      const { data } = await api.post('/pipelines', body)
      await loadPipelines()
      await selectPipeline(data)
      editingNew.value = false
    } else {
      await api.put(`/pipelines/${selectedPipeline.value.id}`, body)
      await loadPipelines()
      await selectPipeline(selectedPipeline.value)
    }
    toast.add({ severity: 'success', summary: 'Saved', life: 3000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Save error', detail: e.response?.data?.detail, life: 5000 })
  } finally {
    saving.value = false
  }
}

// ── Run pipeline ──────────────────────────────────────────────────────────

async function runPipeline() {
  if (!selectedPipeline.value) return
  running.value = true
  try {
    await api.post(`/pipelines/${selectedPipeline.value.id}/run`)
    toast.add({ severity: 'info', summary: 'Pipeline started', detail: 'Running...', life: 3000 })
    const runsRes = await api.get(`/pipelines/${selectedPipeline.value.id}/runs`)
    recentRuns.value = runsRes.data.slice(0, 8)
    await loadPipelines()
    startPolling()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.response?.data?.detail, life: 5000 })
  } finally {
    running.value = false
  }
}

function startPolling() {
  stopPolling()
  _pollTimer = setInterval(async () => {
    if (!selectedPipeline.value) { stopPolling(); return }
    try {
      const runsRes = await api.get(`/pipelines/${selectedPipeline.value.id}/runs`)
      recentRuns.value = runsRes.data.slice(0, 8)
      await loadPipelines()
      if (!hasRunningRun.value) stopPolling()
    } catch {
      stopPolling()
    }
  }, 2500)
}

function stopPolling() {
  if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null }
}

// ── Detalle de run ─────────────────────────────────────────────────────────

async function openRunDetail(runId) {
  try {
    const { data } = await api.get(`/pipelines/runs/${runId}`)
    runDetail.value = data
    showRunDetail.value = true
  } catch {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Could not load run detail', life: 3000 })
  }
}

// ── Delete pipeline ───────────────────────────────────────────────────────

function confirmDelete() {
  confirm.require({
    message: `Delete pipeline "${selectedPipeline.value.name}"? This action cannot be undone.`,
    header: 'Confirm deletion',
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: 'Delete', rejectLabel: 'Cancel',
    acceptClass: 'p-button-danger',
    accept: async () => {
      try {
        await api.delete(`/pipelines/${selectedPipeline.value.id}`)
        selectedPipeline.value = null
        editingNew.value = false
        form.value = { name: '', description: '', steps: [] }
        savedForm.value = null
        recentRuns.value = []
        stopPolling()
        await loadPipelines()
        toast.add({ severity: 'success', summary: 'Pipeline deleted', life: 3000 })
      } catch (e) {
        toast.add({ severity: 'error', summary: 'Delete error', detail: e.response?.data?.detail, life: 5000 })
      }
    },
  })
}

// ── Export / Import ───────────────────────────────────────────────────────

async function exportPipeline() {
  try {
    const { data } = await api.get(`/pipelines/${selectedPipeline.value.id}/export`)
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${data.name.replace(/[^a-z0-9]/gi, '_')}.json`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Export error', detail: e.response?.data?.detail, life: 4000 })
  }
}

function triggerImport() {
  importInputRef.value.click()
}

async function onImportFile(e) {
  const file = e.target.files[0]
  if (!file) return
  e.target.value = ''
  try {
    const text = await file.text()
    const data = JSON.parse(text)
    const { data: created } = await api.post('/pipelines/import', data)
    await loadPipelines()
    const found = pipelines.value.find(p => p.id === created.id)
    if (found) await selectPipeline(found)
    toast.add({ severity: 'success', summary: 'Pipeline imported', detail: `"${created.name}" created successfully`, life: 3000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Import error', detail: e.response?.data?.detail || 'Invalid JSON or incorrect structure', life: 5000 })
  }
}

// ── Step helpers ──────────────────────────────────────────────────────────

function conditionLabel(step) {
  const s = step.on_success, f = step.on_failure
  if (s === 'continue' && f === 'continue') return 'always continues →'
  if (s === 'continue' && f === 'stop') return 'continues on success →'
  if (s === 'stop' && f === 'continue') return 'continues on failure →'
  return '→'
}

function conditionArrow(step) {
  const s = step.on_success, f = step.on_failure
  if (s === 'continue' && f === 'continue') return 'always'
  if (s === 'continue' && f === 'stop') return 'on success'
  if (s === 'stop' && f === 'continue') return 'on failure'
  return '↓'
}

function conditionClass(step) {
  if (step.on_success === 'continue' && step.on_failure === 'continue') return 'connector--always'
  if (step.on_success === 'continue') return 'connector--success'
  return 'connector--failure'
}

function connectorClass(step) { return conditionClass(step) }

function stepIcon(step) {
  if (step.step_type === 'script') return '⚙'
  if (step.step_type === 'shell') return '$'
  const mod = step.config?.module
  const icons = {
    load_env: '📄', email: '✉', compress: '📦', move_file: '↗', copy_file: '⧉',
    delete_file: '🗑', mkdir: '📁', write_file: '✏', rename_file: '✎', decompress: '📂',
    check_exists: '?', delay: '⏱', log: '📝', call_pipeline: '⚡',
  }
  return icons[mod] || '◆'
}

function stepTypeShort(step) {
  if (step.step_type === 'shell') return 'Shell'
  if (step.step_type === 'script') return 'Script'
  if (step.step_type === 'module') {
    const labels = {
      load_env: '.env', email: 'Email', compress: 'Compress', move_file: 'Move',
      copy_file: 'Copy', delete_file: 'Delete', mkdir: 'Mkdir', write_file: 'Write',
      rename_file: 'Rename', decompress: 'Decompr.', check_exists: 'Check',
      delay: 'Wait', log: 'Log', call_pipeline: 'Pipeline',
    }
    return labels[step.config?.module] || 'Module'
  }
  return step.step_type
}

function stepPreview(step) {
  if (step.step_type === 'shell') return step.config?.command ? `$ ${step.config.command}` : ''
  if (step.step_type === 'script') return step.config?.favorite_id ? `script #${step.config.favorite_id}` : ''
  if (step.step_type === 'module') {
    const m = step.config?.module
    if (!m) return ''
    if ((m === 'move_file' || m === 'copy_file') && step.config?.src) return `${step.config.src} → ${step.config.dst || '?'}`
    if (m === 'shell' || m === 'load_env' || m === 'delete_file' || m === 'mkdir') return step.config?.path || ''
    if (m === 'delay' && step.config?.seconds != null) return `${step.config.seconds}s`
    if (m === 'log') return step.config?.message || ''
    if (m === 'email') return step.config?.to || ''
    return ''
  }
  return ''
}

// ── Helpers de tiempo ──────────────────────────────────────────────────────

function utcDate(dt) {
  if (!dt) return null
  // Normalize datetimes without 'Z' (SQLite UTC naive) so the browser treats them as UTC
  return new Date(dt.endsWith('Z') ? dt : dt + 'Z')
}

function timeAgo(dt) {
  const d = utcDate(dt)
  if (!d) return ''
  const diff = Date.now() - d.getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

function duration(start, end) {
  const ms = utcDate(end).getTime() - utcDate(start).getTime()
  if (ms < 1000) return `${ms}ms`
  const s = ms / 1000
  if (s < 60) return `${s.toFixed(1)}s`
  const m = Math.floor(s / 60)
  return `${m}m ${Math.round(s % 60)}s`
}

// ── Lifecycle ──────────────────────────────────────────────────────────────

onMounted(async () => {
  await loadPipelines()
  try {
    const { data } = await api.get('/scripts/favorites')
    favorites.value = data
  } catch { /* favorite scripts are optional */ }
})

onUnmounted(() => stopPolling())
</script>

<style scoped>
.pipelines-view {
  height: calc(100vh - var(--header-height) - 48px);
  display: flex;
  flex-direction: column;
}
.pipelines-splitter { flex: 1; min-height: 0; border-radius: 8px; overflow: hidden; }

/* ─── Panel 1: Lista ──────────────────────────────────────────────────── */
.list-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--p-surface-card);
  border-right: 1px solid var(--p-surface-border);
  overflow: hidden;
}
.list-panel-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px;
  border-bottom: 1px solid var(--p-surface-border);
  flex-shrink: 0;
}
.list-header-icon { font-size: 12px; color: var(--brand-orange); }
.list-header-label {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 2px;
  color: var(--p-text-muted-color);
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
}
.pipeline-list { flex: 1; overflow-y: auto; padding: 6px; }

/* Skeleton */
.skeleton-card { padding: 10px; margin-bottom: 4px; }

/* Pipeline cards */
.pipeline-card {
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 4px;
  border: 1px solid transparent;
  transition: background 0.15s, border-color 0.15s;
}
.pipeline-card:hover { background: var(--p-surface-hover); }
.pipeline-card--active {
  background: color-mix(in srgb, var(--brand-orange) 8%, transparent);
  border-color: color-mix(in srgb, var(--brand-orange) 30%, transparent);
}
.pipeline-card-name {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 5px;
}
.pipeline-card-title {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--p-text-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pipeline-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.pipeline-card-meta {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  color: var(--p-text-muted-color);
}
.pipeline-card-time {
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--p-text-muted-color);
}

/* Status dot */
.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}
.status-dot--success { background: var(--p-green-500); }
.status-dot--error { background: var(--p-red-400); }
.status-dot--running {
  background: var(--p-blue-400);
  animation: pulse 1.4s ease-in-out infinite;
}
.status-dot--none { background: var(--p-surface-border); }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

/* Empty state */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 28px 16px;
}
.empty-icon { font-size: 30px; opacity: 0.25; color: var(--p-text-muted-color); }
.empty-title {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--p-text-color);
  font-weight: 600;
}
.empty-text {
  font-size: var(--text-xs);
  color: var(--p-text-muted-color);
  text-align: center;
  line-height: 1.6;
}

/* ─── Panel 2: Editor ─────────────────────────────────────────────────── */
.editor-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--p-surface-card);
  overflow: hidden;
}
.empty-editor {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
}
.empty-editor-title {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--p-text-muted-color);
}
.empty-editor-sub {
  font-size: var(--text-xs);
  color: var(--p-text-muted-color);
  opacity: 0.7;
}

/* Toolbar */
.editor-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px solid var(--p-surface-border);
  flex-shrink: 0;
  gap: 8px;
}
.editor-toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}
.editor-toolbar-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.pipeline-name-input {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--p-text-color);
  background: transparent;
  border: none;
  outline: none;
  flex: 1;
  min-width: 0;
}
.pipeline-name-input:focus { border-bottom: 1px solid var(--brand-orange); }
.unsaved-indicator {
  color: var(--brand-orange);
  font-size: 10px;
  cursor: default;
  flex-shrink: 0;
}

/* Description */
.editor-description {
  padding: 8px 12px;
  border-bottom: 1px solid var(--p-surface-border);
  flex-shrink: 0;
}

/* Steps header */
.steps-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px 4px;
  flex-shrink: 0;
}
.steps-label {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 2px;
  color: var(--p-text-muted-color);
}
.steps-count-badge {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  font-weight: 600;
  background: color-mix(in srgb, var(--brand-orange) 12%, transparent);
  color: var(--brand-orange);
  border-radius: 4px;
  padding: 1px 6px;
}

/* Steps list */
.steps-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 12px 12px;
}

/* Empty steps */
.empty-steps {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 32px 16px;
  color: var(--p-text-muted-color);
  text-align: center;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
}
.empty-steps-hint {
  font-size: var(--text-2xs);
  line-height: 1.6;
  max-width: 340px;
}
.empty-steps-hint code {
  background: var(--p-surface-ground);
  padding: 1px 4px;
  border-radius: 3px;
  font-family: var(--font-mono);
}

/* ── Step cards (accordion) ────────────────────────────────────────── */
.step-card {
  border: 1px solid var(--p-surface-border);
  border-radius: 7px;
  margin-bottom: 6px;
  overflow: hidden;
  transition: border-color 0.15s, box-shadow 0.15s;
  background: var(--p-surface-ground);
}
.step-card:hover {
  border-color: color-mix(in srgb, var(--p-text-muted-color) 45%, transparent);
}
.step-card--open {
  border-color: var(--brand-orange);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--brand-orange) 18%, transparent);
}

/* Header — clickable area */
.step-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 10px 9px 12px;
  cursor: pointer;
  user-select: none;
  background: var(--p-surface-ground);
  transition: background 0.14s;
  min-height: 46px;
}
.step-card-header:hover {
  background: var(--p-surface-hover);
}
.step-card--open .step-card-header {
  background: color-mix(in srgb, var(--brand-orange) 5%, var(--p-surface-ground));
  border-bottom: 1px solid color-mix(in srgb, var(--brand-orange) 22%, transparent);
}

.step-order {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  color: var(--p-text-muted-color);
  min-width: 18px;
  text-align: center;
  flex-shrink: 0;
}

/* Info (type + name + subtitle) */
.step-card-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.step-card-info-top {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
.step-card-subtitle {
  display: flex;
  align-items: center;
  gap: 4px;
  overflow: hidden;
}
.step-condition-text {
  font-family: var(--font-mono);
  font-size: 9px;
  flex-shrink: 0;
}
.step-preview-sep {
  font-size: 9px;
  color: var(--p-text-muted-color);
  opacity: 0.4;
  flex-shrink: 0;
}
.step-preview-text {
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--p-text-muted-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.connector--always { color: var(--p-text-muted-color); opacity: 0.7; }
.connector--success { color: var(--p-green-500); }
.connector--failure { color: var(--p-red-400); }

/* Type badge */
.step-type-badge {
  font-family: var(--font-mono);
  font-size: 8px;
  letter-spacing: 0.5px;
  padding: 2px 6px;
  border-radius: 3px;
  flex-shrink: 0;
  white-space: nowrap;
}
.step-type-badge--script {
  background: color-mix(in srgb, var(--brand-orange) 15%, transparent);
  color: var(--brand-orange);
}
.step-type-badge--shell {
  background: color-mix(in srgb, var(--p-green-500) 15%, transparent);
  color: var(--p-green-500);
}
.step-type-badge--module {
  background: color-mix(in srgb, var(--p-purple-400) 15%, transparent);
  color: var(--p-purple-400);
}

.step-name {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--p-text-color);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Acciones (subir/bajar/eliminar) */
.step-card-actions {
  display: flex;
  align-items: center;
  gap: 0;
  flex-shrink: 0;
}

/* Chevron indicador */
.step-chevron {
  width: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: var(--p-text-muted-color);
  font-size: 11px;
  transition: color 0.15s, transform 0.22s ease;
}
.step-card--open .step-chevron {
  color: var(--brand-orange);
}

/* Step body (animated area) */
.step-body {
  padding: 14px;
  background: color-mix(in srgb, var(--p-surface-card) 55%, var(--p-surface-ground));
}

/* ─── Panel 3: Flujo + Historial ──────────────────────────────────────── */
.flow-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--p-surface-card);
  border-left: 1px solid var(--p-surface-border);
  overflow: hidden;
}
.section-label {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 2px;
  color: var(--p-text-muted-color);
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
}

/* Flujo */
.flow-section {
  padding: 12px;
  border-bottom: 1px solid var(--p-surface-border);
  max-height: 45%;
  overflow-y: auto;
  flex-shrink: 0;
}
.flow-diagram {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 0;
}
.flow-node {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border-radius: 5px;
  border: 1px solid;
  font-family: var(--font-mono);
  font-size: 10px;
  transition: opacity 0.15s;
}
.flow-node:hover { opacity: 0.8; }
.flow-node--script {
  background: color-mix(in srgb, var(--brand-orange) 10%, transparent);
  color: var(--brand-orange);
  border-color: color-mix(in srgb, var(--brand-orange) 28%, transparent);
}
.flow-node--shell {
  background: color-mix(in srgb, var(--p-green-500) 10%, transparent);
  color: var(--p-green-500);
  border-color: color-mix(in srgb, var(--p-green-500) 28%, transparent);
}
.flow-node--module {
  background: color-mix(in srgb, var(--p-purple-400) 10%, transparent);
  color: var(--p-purple-400);
  border-color: color-mix(in srgb, var(--p-purple-400) 28%, transparent);
}
.flow-node-icon { flex-shrink: 0; }
.flow-node-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}
.flow-connector {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 2px 0;
  gap: 0;
}
.flow-line {
  width: 2px;
  height: 10px;
  border-radius: 1px;
}
.flow-connector-label {
  font-family: var(--font-mono);
  font-size: 8px;
  letter-spacing: 0.5px;
}
.flow-line.connector--always,
.flow-connector-label.connector--always { background: var(--p-surface-border); color: var(--p-text-muted-color); }
.flow-line.connector--success,
.flow-connector-label.connector--success { background: var(--p-green-500); color: var(--p-green-500); }
.flow-line.connector--failure,
.flow-connector-label.connector--failure { background: var(--p-red-400); color: var(--p-red-400); }
.flow-empty {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  color: var(--p-text-muted-color);
  padding: 4px 0;
  line-height: 1.5;
}

/* Historial */
.runs-section {
  flex: 1;
  padding: 12px;
  overflow-y: auto;
}
.running-indicator {
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--p-blue-400);
  text-transform: none;
  letter-spacing: 0;
}
.runs-empty {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 4px 0;
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  color: var(--p-text-muted-color);
}
.runs-empty-hint {
  font-size: 9px;
  opacity: 0.7;
  line-height: 1.5;
}
.runs-list { display: flex; flex-direction: column; gap: 3px; }
.run-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 8px;
  border-radius: 5px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: background 0.12s, border-color 0.12s;
}
.run-item:hover { background: var(--p-surface-hover); border-color: var(--p-surface-border); }
.run-item--running { border-color: color-mix(in srgb, var(--p-blue-400) 25%, transparent); }
.run-item-left { display: flex; align-items: center; gap: 8px; }
.run-item-right { display: flex; align-items: center; gap: 6px; }
.run-status-icon {
  font-size: 13px;
}
.run-item--success .run-status-icon { color: var(--p-green-500); }
.run-item--failed .run-status-icon { color: var(--p-red-400); }
.run-item--running .run-status-icon { color: var(--p-blue-400); }
.run-item-info { display: flex; flex-direction: column; gap: 1px; }
.run-item-label {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  color: var(--p-text-color);
}
.run-item-time {
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--p-text-muted-color);
}
.run-duration {
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--p-text-muted-color);
}
.run-live-badge {
  font-family: var(--font-mono);
  font-size: 8px;
  background: color-mix(in srgb, var(--p-blue-400) 18%, transparent);
  color: var(--p-blue-400);
  border: 1px solid color-mix(in srgb, var(--p-blue-400) 35%, transparent);
  border-radius: 3px;
  padding: 1px 5px;
  animation: pulse 1.4s ease-in-out infinite;
}
.run-chevron { font-size: 9px; color: var(--p-text-muted-color); opacity: 0.5; }

/* ─── Run detail dialog ───────────────────────────────────────────────── */
.run-detail { display: flex; flex-direction: column; gap: 14px; }
.run-detail-summary {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--p-surface-border);
}
.run-detail-badge {
  display: flex;
  align-items: center;
  gap: 5px;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 5px;
}
.run-detail-badge--success {
  background: color-mix(in srgb, var(--p-green-500) 15%, transparent);
  color: var(--p-green-500);
}
.run-detail-badge--failed {
  background: color-mix(in srgb, var(--p-red-400) 15%, transparent);
  color: var(--p-red-400);
}
.run-detail-badge--running {
  background: color-mix(in srgb, var(--p-blue-400) 15%, transparent);
  color: var(--p-blue-400);
}
.run-detail-meta {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--p-text-muted-color);
}
.step-runs-list { display: flex; flex-direction: column; gap: 8px; }
.step-run-card {
  border: 1px solid var(--p-surface-border);
  border-left: 3px solid var(--p-surface-border);
  border-radius: 6px;
  padding: 10px 12px;
  background: var(--p-surface-ground);
}
.step-run-card--success { border-left-color: var(--p-green-500); }
.step-run-card--failed { border-left-color: var(--p-red-400); }
.step-run-card--skipped { border-left-color: var(--p-text-muted-color); opacity: 0.65; }
.step-run-card--running { border-left-color: var(--p-blue-400); }
.step-run-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
}
.step-run-number { color: var(--p-text-muted-color); font-size: var(--text-2xs); }
.step-run-icon {
  font-size: 13px;
}
.step-run-card--success .step-run-icon { color: var(--p-green-500); }
.step-run-card--failed .step-run-icon { color: var(--p-red-400); }
.step-run-card--running .step-run-icon { color: var(--p-blue-400); }
.step-run-card--skipped .step-run-icon { color: var(--p-text-muted-color); }
.step-run-name { flex: 1; color: var(--p-text-color); font-weight: 500; }
.step-run-status-badge {
  font-size: 9px;
  padding: 1px 6px;
  border-radius: 3px;
}
.step-run-status--success { background: color-mix(in srgb, var(--p-green-500) 14%, transparent); color: var(--p-green-500); }
.step-run-status--failed { background: color-mix(in srgb, var(--p-red-400) 14%, transparent); color: var(--p-red-400); }
.step-run-status--skipped { background: color-mix(in srgb, var(--p-text-muted-color) 10%, transparent); color: var(--p-text-muted-color); }
.step-run-status--running { background: color-mix(in srgb, var(--p-blue-400) 14%, transparent); color: var(--p-blue-400); }
.step-run-duration { color: var(--p-text-muted-color); margin-left: auto; }
.step-run-skipped {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--p-text-muted-color);
  margin-top: 4px;
}
.step-run-output {
  font-family: var(--font-mono);
  font-size: 10px;
  background: var(--p-surface-card);
  border: 1px solid var(--p-surface-border);
  border-radius: 4px;
  padding: 8px 10px;
  margin: 6px 0 0;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 180px;
  overflow-y: auto;
  color: var(--p-text-muted-color);
  line-height: 1.5;
}
</style>
