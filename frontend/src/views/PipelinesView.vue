<template>
  <div class="pipelines-view">
    <Splitter class="pipelines-splitter">

      <!-- ── Panel 1: Lista de pipelines ── -->
      <SplitterPanel :size="25" :minSize="18">
        <div class="list-panel">
          <div class="list-panel-header">
            <i class="pi pi-sitemap list-header-icon" />
            <span class="list-header-label">PIPELINES</span>
            <span class="list-header-count">{{ pipelines.length }}</span>
            <Button v-if="isAdmin" icon="pi pi-plus" text rounded size="small"
              v-tooltip.right="'New pipeline'" @click="startNewPipeline" />
            <Button icon="pi pi-refresh" text rounded size="small" :loading="loading"
              v-tooltip.right="'Refresh'" @click="loadPipelines" />
          </div>
          <div class="pipeline-list">
            <div
              v-for="p in pipelines" :key="p.id"
              class="pipeline-card"
              :class="{ 'pipeline-card--active': selectedPipeline?.id === p.id }"
              @click="selectPipeline(p)"
            >
              <div class="pipeline-card-name">
                <i class="pi pi-sitemap pipeline-card-icon" />
                {{ p.name }}
              </div>
              <div class="pipeline-card-meta">{{ p.step_count }} paso{{ p.step_count !== 1 ? 's' : '' }}</div>
              <div class="pipeline-card-status">
                <span v-if="p.last_run_status === 'success'" class="status-badge status-badge--success">✓ éxito</span>
                <span v-else-if="p.last_run_status === 'failed'" class="status-badge status-badge--error">✗ falló</span>
                <span v-else-if="p.last_run_status === 'running'" class="status-badge status-badge--running">◌ corriendo</span>
                <span v-else class="status-badge status-badge--none">— sin runs</span>
                <span v-if="p.last_run_at" class="pipeline-card-time">{{ timeAgo(p.last_run_at) }}</span>
              </div>
            </div>
            <div v-if="!pipelines.length && !loading" class="empty-state">
              <i class="pi pi-sitemap empty-icon" />
              <span class="empty-text">No hay pipelines.</span>
              <Button v-if="isAdmin" label="Crear pipeline" size="small" @click="startNewPipeline" />
            </div>
          </div>
        </div>
      </SplitterPanel>

      <!-- ── Panel 2: Editor de steps ── -->
      <SplitterPanel :size="50" :minSize="35">
        <div class="editor-panel">
          <div v-if="!selectedPipeline && !editingNew" class="empty-editor">
            <i class="pi pi-sitemap empty-icon" />
            <span class="empty-text">Seleccioná un pipeline o creá uno nuevo.</span>
          </div>
          <template v-else>
            <!-- Toolbar -->
            <div class="editor-toolbar">
              <div class="editor-toolbar-left">
                <i class="pi pi-sitemap" style="color: var(--brand-orange)" />
                <input
                  v-model="form.name"
                  class="pipeline-name-input"
                  placeholder="Nombre del pipeline"
                  :disabled="!isAdmin"
                />
              </div>
              <div class="editor-toolbar-right">
                <Button v-if="selectedPipeline && !editingNew" icon="pi pi-play" label="Ejecutar"
                  size="small" severity="success" @click="runPipeline" :loading="running" />
                <Button v-if="isAdmin" icon="pi pi-check" label="Guardar"
                  size="small" @click="savePipeline" :loading="saving" />
                <Button v-if="isAdmin && selectedPipeline" icon="pi pi-trash" text rounded size="small"
                  severity="danger" v-tooltip.left="'Eliminar pipeline'" @click="confirmDelete" />
              </div>
            </div>
            <div class="editor-description">
              <InputText v-model="form.description" placeholder="Descripción (opcional)"
                size="small" fluid :disabled="!isAdmin" />
            </div>

            <!-- Steps list -->
            <div class="steps-header">
              <span class="steps-label">PASOS</span>
              <Button v-if="isAdmin" icon="pi pi-plus" text rounded size="small"
                label="Agregar paso" @click="addStep" />
            </div>
            <div class="steps-list">
              <div
                v-for="(step, idx) in form.steps" :key="step._key"
                class="step-card"
                :class="{ 'step-card--active': activeStepIdx === idx }"
                @click="activeStepIdx = idx"
              >
                <div class="step-card-header">
                  <span class="step-drag-handle">⋮⋮</span>
                  <span class="step-order">{{ idx + 1 }}</span>
                  <span class="step-type-badge" :class="`step-type-badge--${step.step_type}`">
                    {{ step.step_type.toUpperCase() }}
                  </span>
                  <span class="step-name">{{ step.name || '(sin nombre)' }}</span>
                  <span class="step-condition">{{ conditionLabel(step) }}</span>
                  <Button v-if="isAdmin" icon="pi pi-trash" text rounded size="small"
                    severity="danger" @click.stop="removeStep(idx)" />
                </div>
                <div class="step-card-preview">{{ stepPreview(step) }}</div>
              </div>
              <div v-if="!form.steps.length" class="empty-steps">
                <span>No hay pasos. Hacé click en "Agregar paso".</span>
              </div>
            </div>

            <!-- Step config drawer (inline, shown when a step is selected) -->
            <div v-if="activeStepIdx !== null && form.steps[activeStepIdx]" class="step-drawer">
              <StepConfigEditor
                v-model="form.steps[activeStepIdx]"
                :favorites="favorites"
                :pipelines="pipelines"
                :disabled="!isAdmin"
              />
            </div>
          </template>
        </div>
      </SplitterPanel>

      <!-- ── Panel 3: Mini-flujo + historial ── -->
      <SplitterPanel :size="25" :minSize="18">
        <div class="flow-panel">
          <div class="flow-section">
            <div class="flow-label">FLUJO</div>
            <div class="flow-diagram">
              <template v-for="(step, idx) in form.steps" :key="step._key">
                <div class="flow-node" :class="`flow-node--${step.step_type}`">
                  {{ stepIcon(step) }} {{ step.name || step.step_type }}
                </div>
                <div v-if="idx < form.steps.length - 1" class="flow-arrow">
                  <span :class="conditionClass(step)">{{ conditionArrow(step) }}</span>
                </div>
              </template>
              <div v-if="!form.steps.length" class="flow-empty">Sin pasos</div>
            </div>
          </div>
          <div class="runs-section">
            <div class="flow-label">ÚLTIMAS RUNS</div>
            <div class="runs-list">
              <div v-for="run in recentRuns" :key="run.id" class="run-item"
                @click="openRunDetail(run.id)">
                <span :class="run.status === 'success' ? 'run-ok' : run.status === 'failed' ? 'run-fail' : 'run-running'">
                  {{ run.status === 'success' ? '✓' : run.status === 'failed' ? '✗' : '◌' }}
                </span>
                <span class="run-time">{{ timeAgo(run.started_at) }}</span>
                <span v-if="run.ended_at" class="run-duration">
                  {{ duration(run.started_at, run.ended_at) }}
                </span>
              </div>
              <div v-if="!recentRuns.length" class="runs-empty">Sin ejecuciones</div>
            </div>
          </div>
        </div>
      </SplitterPanel>

    </Splitter>

    <!-- Run detail dialog -->
    <Dialog v-model:visible="showRunDetail" modal header="Detalle de ejecución"
      :style="{ width: '700px' }">
      <div v-if="runDetail" class="run-detail">
        <div class="run-detail-status">
          Estado: <strong>{{ runDetail.status }}</strong> ·
          Disparado por: <strong>{{ runDetail.triggered_by }}</strong>
        </div>
        <div v-for="sr in runDetail.step_runs" :key="sr.id" class="step-run-card"
          :class="`step-run-card--${sr.status}`">
          <div class="step-run-header">
            <span class="step-run-order">{{ sr.step_order + 1 }}</span>
            <span class="step-run-status">{{ sr.status }}</span>
            <span v-if="sr.ended_at" class="step-run-duration">
              {{ duration(sr.started_at, sr.ended_at) }}
            </span>
          </div>
          <pre v-if="sr.output" class="step-run-output">{{ sr.output }}</pre>
        </div>
      </div>
    </Dialog>

    <ConfirmDialog />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import Splitter from 'primevue/splitter'
import SplitterPanel from 'primevue/splitterpanel'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Dialog from 'primevue/dialog'
import ConfirmDialog from 'primevue/confirmdialog'
import api from '../api/client.js'
import { useAuthStore } from '../stores/auth.js'
import StepConfigEditor from '../components/pipelines/StepConfigEditor.vue'

const toast = useToast()
const confirm = useConfirm()
const auth = useAuthStore()
const isAdmin = auth.role === 'admin'

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

const form = ref({ name: '', description: '', steps: [] })

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

async function loadPipelines() {
  loading.value = true
  try {
    const { data } = await api.get('/pipelines')
    pipelines.value = data
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: 'No se pudieron cargar los pipelines', life: 4000 })
  } finally {
    loading.value = false
  }
}

async function selectPipeline(p) {
  selectedPipeline.value = p
  editingNew.value = false
  activeStepIdx.value = null
  const { data } = await api.get(`/pipelines/${p.id}`)
  form.value = {
    name: data.name,
    description: data.description,
    steps: data.steps.map(s => ({ ...s, _key: newStepKey() })),
  }
  const runsRes = await api.get(`/pipelines/${p.id}/runs`)
  recentRuns.value = runsRes.data.slice(0, 5)
}

function startNewPipeline() {
  selectedPipeline.value = null
  editingNew.value = true
  activeStepIdx.value = null
  recentRuns.value = []
  form.value = { name: '', description: '', steps: [] }
}

function addStep() {
  const s = emptyStep()
  s.order = form.value.steps.length
  form.value.steps.push(s)
  activeStepIdx.value = form.value.steps.length - 1
}

function removeStep(idx) {
  form.value.steps.splice(idx, 1)
  if (activeStepIdx.value >= form.value.steps.length) {
    activeStepIdx.value = form.value.steps.length - 1
  }
}

async function savePipeline() {
  if (!form.value.name.trim()) {
    toast.add({ severity: 'warn', summary: 'Nombre requerido', life: 3000 })
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
    toast.add({ severity: 'success', summary: 'Guardado', life: 3000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error al guardar', detail: e.response?.data?.detail, life: 5000 })
  } finally {
    saving.value = false
  }
}

async function runPipeline() {
  if (!selectedPipeline.value) return
  running.value = true
  try {
    const { data } = await api.post(`/pipelines/${selectedPipeline.value.id}/run`)
    toast.add({ severity: 'info', summary: 'Pipeline iniciado', detail: `Run ID: ${data.run_id}`, life: 4000 })
    setTimeout(async () => {
      await selectPipeline(selectedPipeline.value)
      await loadPipelines()
    }, 2000)
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.response?.data?.detail, life: 5000 })
  } finally {
    running.value = false
  }
}

async function openRunDetail(runId) {
  const { data } = await api.get(`/pipelines/runs/${runId}`)
  runDetail.value = data
  showRunDetail.value = true
}

function confirmDelete() {
  confirm.require({
    message: `¿Eliminar pipeline "${selectedPipeline.value.name}"?`,
    header: 'Confirmar eliminación',
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: 'Eliminar', rejectLabel: 'Cancelar',
    acceptClass: 'p-button-danger',
    accept: async () => {
      await api.delete(`/pipelines/${selectedPipeline.value.id}`)
      selectedPipeline.value = null
      editingNew.value = false
      form.value = { name: '', description: '', steps: [] }
      recentRuns.value = []
      await loadPipelines()
      toast.add({ severity: 'success', summary: 'Eliminado', life: 3000 })
    },
  })
}

function conditionLabel(step) {
  const s = step.on_success, f = step.on_failure
  if (s === 'continue' && f === 'continue') return 'siempre →'
  if (s === 'continue' && f === 'stop') return 'si éxito →'
  if (s === 'stop' && f === 'continue') return 'si falla →'
  return '→'
}

function conditionArrow(step) { return conditionLabel(step) }
function conditionClass(step) {
  if (step.on_success === 'continue' && step.on_failure === 'continue') return 'arrow-always'
  if (step.on_success === 'continue') return 'arrow-success'
  return 'arrow-failure'
}

function stepIcon(step) {
  if (step.step_type === 'script') return '⚙'
  if (step.step_type === 'shell') return '$'
  const mod = step.config?.module
  const icons = { load_env: '📄', email: '✉', compress: '📦', move_file: '↗', copy_file: '⧉',
    delete_file: '🗑', mkdir: '📁', write_file: '✏', rename_file: '✎', decompress: '📂',
    check_exists: '?', delay: '⏱', log: '📝', call_pipeline: '⚡' }
  return icons[mod] || '◆'
}

function stepPreview(step) {
  if (step.step_type === 'shell') return step.config?.command || ''
  if (step.step_type === 'script') return step.config?.path || `script #${step.config?.favorite_id}`
  if (step.step_type === 'module') return `${step.config?.module || 'módulo'}`
  return ''
}

function timeAgo(dt) {
  if (!dt) return ''
  const diff = Date.now() - new Date(dt).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'ahora'
  if (mins < 60) return `hace ${mins}m`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `hace ${hrs}h`
  return `hace ${Math.floor(hrs / 24)}d`
}

function duration(start, end) {
  const ms = new Date(end).getTime() - new Date(start).getTime()
  if (ms < 1000) return `${ms}ms`
  const s = (ms / 1000).toFixed(1)
  return `${s}s`
}

onMounted(async () => {
  await loadPipelines()
  try {
    const { data } = await api.get('/scripts/favorites')
    favorites.value = data
  } catch { /* ignore */ }
})
</script>

<style scoped>
.pipelines-view {
  height: calc(100vh - var(--header-height) - 48px);
  display: flex;
  flex-direction: column;
}
.pipelines-splitter { flex: 1; min-height: 0; border-radius: 8px; overflow: hidden; }

/* ── Panel 1 ── */
.list-panel { display: flex; flex-direction: column; height: 100%; background: var(--p-surface-card); border-right: 1px solid var(--p-surface-border); overflow: hidden; }
.list-panel-header { display: flex; align-items: center; gap: 7px; padding: 10px; border-bottom: 1px solid var(--p-surface-border); flex-shrink: 0; }
.list-header-icon { font-size: 12px; color: var(--brand-orange); }
.list-header-label { font-family: var(--font-mono); font-size: var(--text-2xs); letter-spacing: 2px; color: var(--p-text-muted-color); flex: 1; }
.list-header-count { font-family: var(--font-mono); font-size: var(--text-2xs); font-weight: 600; color: var(--brand-orange); background: color-mix(in srgb, var(--brand-orange) 12%, transparent); border-radius: 4px; padding: 1px 6px; }
.pipeline-list { flex: 1; overflow-y: auto; padding: 6px; }
.pipeline-card { padding: 8px 10px; border-radius: 6px; cursor: pointer; margin-bottom: 4px; border: 1px solid transparent; transition: background 0.15s, border-color 0.15s; }
.pipeline-card:hover { background: var(--p-surface-hover); }
.pipeline-card--active { background: color-mix(in srgb, var(--brand-orange) 8%, transparent); border-color: color-mix(in srgb, var(--brand-orange) 30%, transparent); }
.pipeline-card-name { display: flex; align-items: center; gap: 6px; font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-color); margin-bottom: 3px; }
.pipeline-card-icon { color: var(--brand-orange); font-size: 10px; }
.pipeline-card-meta { font-family: var(--font-mono); font-size: var(--text-2xs); color: var(--p-text-muted-color); margin-bottom: 4px; }
.pipeline-card-status { display: flex; align-items: center; gap: 6px; }
.status-badge { font-family: var(--font-mono); font-size: 8px; letter-spacing: 0.5px; padding: 1px 5px; border-radius: 3px; }
.status-badge--success { background: color-mix(in srgb, var(--p-green-500) 15%, transparent); color: var(--p-green-500); }
.status-badge--error { background: color-mix(in srgb, var(--p-red-500) 15%, transparent); color: var(--p-red-500); }
.status-badge--running { background: color-mix(in srgb, var(--p-blue-500) 15%, transparent); color: var(--p-blue-500); }
.status-badge--none { background: color-mix(in srgb, var(--p-text-muted-color) 10%, transparent); color: var(--p-text-muted-color); }
.pipeline-card-time { font-family: var(--font-mono); font-size: 9px; color: var(--p-text-muted-color); }

/* ── Panel 2 ── */
.editor-panel { display: flex; flex-direction: column; height: 100%; background: var(--p-surface-card); overflow: hidden; }
.editor-toolbar { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; border-bottom: 1px solid var(--p-surface-border); flex-shrink: 0; gap: 8px; }
.editor-toolbar-left { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0; }
.editor-toolbar-right { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.pipeline-name-input { font-family: var(--font-mono); font-size: var(--text-sm); font-weight: 600; color: var(--p-text-color); background: transparent; border: none; outline: none; flex: 1; min-width: 0; }
.pipeline-name-input:focus { border-bottom: 1px solid var(--brand-orange); }
.editor-description { padding: 8px 12px; border-bottom: 1px solid var(--p-surface-border); flex-shrink: 0; }
.steps-header { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px 4px; flex-shrink: 0; }
.steps-label { font-family: var(--font-mono); font-size: var(--text-2xs); letter-spacing: 2px; color: var(--p-text-muted-color); }
.steps-list { flex: 1; overflow-y: auto; padding: 4px 12px; }
.step-card { background: var(--p-surface-ground); border: 1px solid var(--p-surface-border); border-radius: 6px; padding: 8px 10px; margin-bottom: 6px; cursor: pointer; transition: border-color 0.15s; }
.step-card:hover { border-color: var(--p-text-muted-color); }
.step-card--active { border-color: var(--brand-orange); background: color-mix(in srgb, var(--brand-orange) 5%, var(--p-surface-ground)); }
.step-card-header { display: flex; align-items: center; gap: 6px; margin-bottom: 3px; }
.step-drag-handle { color: var(--p-text-muted-color); cursor: grab; font-size: 12px; }
.step-order { font-family: var(--font-mono); font-size: var(--text-2xs); color: var(--p-text-muted-color); min-width: 14px; }
.step-type-badge { font-family: var(--font-mono); font-size: 8px; letter-spacing: 1px; padding: 1px 5px; border-radius: 3px; flex-shrink: 0; }
.step-type-badge--script { background: color-mix(in srgb, var(--brand-orange) 15%, transparent); color: var(--brand-orange); }
.step-type-badge--shell { background: color-mix(in srgb, var(--p-green-500) 15%, transparent); color: var(--p-green-500); }
.step-type-badge--module { background: color-mix(in srgb, var(--p-purple-500) 15%, transparent); color: var(--p-purple-500); }
.step-name { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-color); flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.step-condition { font-family: var(--font-mono); font-size: 9px; color: var(--p-text-muted-color); flex-shrink: 0; }
.step-card-preview { font-family: var(--font-mono); font-size: 9px; color: var(--p-text-muted-color); padding-left: 28px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.step-drawer { border-top: 1px solid var(--p-surface-border); padding: 12px; overflow-y: auto; max-height: 280px; flex-shrink: 0; }
.empty-steps { padding: 24px; text-align: center; font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-muted-color); }

/* ── Panel 3 ── */
.flow-panel { display: flex; flex-direction: column; height: 100%; background: var(--p-surface-card); border-left: 1px solid var(--p-surface-border); overflow: hidden; }
.flow-section { padding: 10px; border-bottom: 1px solid var(--p-surface-border); flex-shrink: 0; }
.flow-label { font-family: var(--font-mono); font-size: var(--text-2xs); letter-spacing: 2px; color: var(--p-text-muted-color); margin-bottom: 8px; }
.flow-diagram { display: flex; flex-direction: column; align-items: flex-start; gap: 2px; }
.flow-node { font-family: var(--font-mono); font-size: 10px; padding: 3px 10px; border-radius: 4px; border: 1px solid; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
.flow-node--script { background: color-mix(in srgb, var(--brand-orange) 12%, transparent); color: var(--brand-orange); border-color: color-mix(in srgb, var(--brand-orange) 30%, transparent); }
.flow-node--shell { background: color-mix(in srgb, var(--p-green-500) 12%, transparent); color: var(--p-green-500); border-color: color-mix(in srgb, var(--p-green-500) 30%, transparent); }
.flow-node--module { background: color-mix(in srgb, var(--p-purple-500) 12%, transparent); color: var(--p-purple-500); border-color: color-mix(in srgb, var(--p-purple-500) 30%, transparent); }
.flow-arrow { padding-left: 14px; font-family: var(--font-mono); font-size: 9px; }
.arrow-always { color: var(--p-text-muted-color); }
.arrow-success { color: var(--p-green-500); }
.arrow-failure { color: var(--p-red-400); }
.flow-empty { font-family: var(--font-mono); font-size: 10px; color: var(--p-text-muted-color); padding: 8px; }
.runs-section { flex: 1; padding: 10px; overflow-y: auto; }
.runs-list { display: flex; flex-direction: column; gap: 4px; }
.run-item { display: flex; align-items: center; gap: 6px; cursor: pointer; padding: 4px 6px; border-radius: 4px; }
.run-item:hover { background: var(--p-surface-hover); }
.run-ok { color: var(--p-green-500); font-size: 11px; }
.run-fail { color: var(--p-red-400); font-size: 11px; }
.run-running { color: var(--p-blue-400); font-size: 11px; }
.run-time { font-family: var(--font-mono); font-size: 9px; color: var(--p-text-muted-color); flex: 1; }
.run-duration { font-family: var(--font-mono); font-size: 9px; color: var(--p-text-muted-color); }
.runs-empty { font-family: var(--font-mono); font-size: 10px; color: var(--p-text-muted-color); padding: 4px; }

/* ── Empty states ── */
.empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; padding: 32px; }
.empty-icon { font-size: 28px; opacity: 0.4; color: var(--p-text-muted-color); }
.empty-text { font-size: var(--text-sm); font-family: var(--font-mono); color: var(--p-text-muted-color); text-align: center; }
.empty-editor { height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; }

/* ── Run detail dialog ── */
.run-detail { display: flex; flex-direction: column; gap: 12px; }
.run-detail-status { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--p-text-muted-color); }
.step-run-card { border: 1px solid var(--p-surface-border); border-radius: 6px; padding: 10px; }
.step-run-card--success { border-left: 3px solid var(--p-green-500); }
.step-run-card--failed { border-left: 3px solid var(--p-red-400); }
.step-run-card--skipped { border-left: 3px solid var(--p-text-muted-color); opacity: 0.6; }
.step-run-header { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; font-family: var(--font-mono); font-size: var(--text-xs); }
.step-run-order { color: var(--p-text-muted-color); }
.step-run-status { font-weight: 600; }
.step-run-duration { color: var(--p-text-muted-color); margin-left: auto; }
.step-run-output { font-family: var(--font-mono); font-size: 10px; background: var(--p-surface-ground); border-radius: 4px; padding: 8px; margin: 0; white-space: pre-wrap; max-height: 150px; overflow-y: auto; color: var(--p-text-muted-color); }
</style>
