<template>
  <div class="step-config">

    <!-- Step name -->
    <div class="config-row">
      <label class="config-label">STEP NAME</label>
      <InputText v-model="local.name" size="small" fluid
        placeholder="e.g. Restart nginx, Compress backups..."
        :disabled="disabled" />
    </div>

    <!-- Tipo de paso -->
    <div class="config-row">
      <label class="config-label">TYPE</label>
      <SelectButton
        v-model="local.step_type"
        :options="typeOptions"
        optionLabel="label" optionValue="value"
        size="small" :disabled="disabled"
        @change="onTypeChange"
      />
      <span class="config-hint">{{ typeHints[local.step_type] }}</span>
    </div>

    <!-- ── Shell ─────────────────────────────────────────────────────── -->
    <div v-if="local.step_type === 'shell'" class="config-row">
      <label class="config-label">COMMAND</label>
      <InputText v-model="local.config.command" size="small" fluid
        placeholder="systemctl restart nginx"
        :disabled="disabled" />
      <span class="config-hint">Runs in the system shell via <code>/bin/sh -c</code>. You can use environment variables.</span>
    </div>

    <!-- ── Script ────────────────────────────────────────────────────── -->
    <div v-if="local.step_type === 'script'" class="config-row">
      <label class="config-label">FAVORITE SCRIPT</label>
      <Select v-model="local.config.favorite_id"
        :options="favoriteOptions"
        optionLabel="label" optionValue="value"
        size="small" fluid :disabled="disabled"
        placeholder="Select a script..."
      />
      <span class="config-hint">Runs a script saved in your favorites. You can add scripts from the Scripts section.</span>
    </div>

    <!-- ── Module ─────────────────────────────────────────────────────── -->
    <template v-if="local.step_type === 'module'">
      <div class="config-row">
        <label class="config-label">MODULE</label>
        <Select v-model="local.config.module"
          :options="moduleOptions"
          optionLabel="label" optionValue="value"
          size="small" fluid :disabled="disabled"
          placeholder="Choose a module..."
          @change="onModuleChange"
        />
        <span v-if="local.config.module" class="config-hint">{{ moduleHints[local.config.module] }}</span>
      </div>

      <!-- load_env / delete_file / check_exists base: path -->
      <div v-if="['load_env', 'delete_file', 'check_exists', 'mkdir'].includes(local.config.module)" class="config-row">
        <label class="config-label">PATH</label>
        <InputText v-model="local.config.path" size="small" fluid
          placeholder="/path/to/file"
          :disabled="disabled" />
      </div>

      <!-- check_exists: tipo -->
      <div v-if="local.config.module === 'check_exists'" class="config-row">
        <label class="config-label">TYPE TO CHECK</label>
        <Select v-model="local.config.type"
          :options="[{ l: 'File', v: 'file' }, { l: 'Directory', v: 'dir' }, { l: 'Any', v: 'any' }]"
          optionLabel="l" optionValue="v"
          size="small" fluid :disabled="disabled" />
        <span class="config-hint">If it does not exist, the step fails. Use conditions to control what happens next.</span>
      </div>

      <!-- move_file / copy_file / compress: src + dst -->
      <template v-if="['move_file', 'copy_file', 'compress'].includes(local.config.module)">
        <div class="config-row">
          <label class="config-label">SOURCE</label>
          <InputText v-model="local.config.src" size="small" fluid
            placeholder="/source/file.txt"
            :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">DESTINATION</label>
          <InputText v-model="local.config.dst" size="small" fluid
            placeholder="/destination/"
            :disabled="disabled" />
        </div>
      </template>

      <!-- compress: formato -->
      <div v-if="local.config.module === 'compress'" class="config-row">
        <label class="config-label">FORMAT</label>
        <Select v-model="local.config.format"
          :options="[{ l: 'tar.gz', v: 'tar.gz' }, { l: 'zip', v: 'zip' }]"
          optionLabel="l" optionValue="v"
          size="small" fluid :disabled="disabled" />
      </div>

      <!-- decompress: src + dst -->
      <template v-if="local.config.module === 'decompress'">
        <div class="config-row">
          <label class="config-label">FILE TO DECOMPRESS</label>
          <InputText v-model="local.config.src" size="small" fluid
            placeholder="/path/archive.tar.gz"
            :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">DESTINATION DIRECTORY</label>
          <InputText v-model="local.config.dst" size="small" fluid
            placeholder="/destination/"
            :disabled="disabled" />
        </div>
      </template>

      <!-- write_file -->
      <template v-if="local.config.module === 'write_file'">
        <div class="config-row">
          <label class="config-label">FILE PATH</label>
          <InputText v-model="local.config.path" size="small" fluid
            placeholder="/path/to/file.txt"
            :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">CONTENT</label>
          <Textarea v-model="local.config.content" rows="4" size="small" fluid
            placeholder="Content to write..."
            :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">WRITE MODE</label>
          <Select v-model="local.config.mode"
            :options="[{ l: 'Overwrite (replaces all)', v: 'overwrite' }, { l: 'Append to end', v: 'append' }]"
            optionLabel="l" optionValue="v"
            size="small" fluid :disabled="disabled" />
        </div>
      </template>

      <!-- rename_file -->
      <template v-if="local.config.module === 'rename_file'">
        <div class="config-row">
          <label class="config-label">ORIGINAL PATH</label>
          <InputText v-model="local.config.path" size="small" fluid :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">NEW NAME</label>
          <InputText v-model="local.config.new_name" size="small" fluid
            placeholder="new-name.txt"
            :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">TIMESTAMP PREFIX</label>
          <ToggleButton v-model="local.config.use_timestamp"
            onLabel="Yes — prepend date"
            offLabel="No"
            size="small" :disabled="disabled" />
          <span class="config-hint">When enabled, the file will be named something like <code>20260409_new-name.txt</code>.</span>
        </div>
      </template>

      <!-- delay -->
      <div v-if="local.config.module === 'delay'" class="config-row">
        <label class="config-label">WAIT TIME (seconds)</label>
        <InputNumber v-model="local.config.seconds"
          :min="0" :max="3600"
          size="small" fluid :disabled="disabled"
          placeholder="5" />
        <span class="config-hint">The pipeline pauses for this many seconds before continuing to the next step.</span>
      </div>

      <!-- log -->
      <template v-if="local.config.module === 'log'">
        <div class="config-row">
          <label class="config-label">MESSAGE</label>
          <InputText v-model="local.config.message" size="small" fluid
            placeholder="Starting backup process..."
            :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">LEVEL</label>
          <Select v-model="local.config.level"
            :options="[{ l: 'Info', v: 'info' }, { l: 'Warn — warning', v: 'warn' }, { l: 'Error — indicates failure', v: 'error' }]"
            optionLabel="l" optionValue="v"
            size="small" fluid :disabled="disabled" />
        </div>
      </template>

      <!-- email -->
      <template v-if="local.config.module === 'email'">
        <div class="config-row">
          <label class="config-label">RECIPIENT</label>
          <InputText v-model="local.config.to" size="small" fluid
            placeholder="admin@myserver.com"
            :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">SUBJECT</label>
          <InputText v-model="local.config.subject" size="small" fluid
            placeholder="Backup completed"
            :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">EMAIL BODY</label>
          <Textarea v-model="local.config.body" rows="3" size="small" fluid
            placeholder="The process completed successfully."
            :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">ATTACHMENT <span class="config-optional">(optional)</span></label>
          <InputText v-model="local.config.attachment" size="small" fluid
            placeholder="/path/to/file.zip"
            :disabled="disabled" />
        </div>
      </template>

      <!-- call_pipeline -->
      <div v-if="local.config.module === 'call_pipeline'" class="config-row">
        <label class="config-label">PIPELINE TO CALL</label>
        <Select v-model="local.config.pipeline_id"
          :options="pipelineOptions"
          optionLabel="label" optionValue="value"
          size="small" fluid :disabled="disabled"
          placeholder="Select a pipeline..."
        />
        <span class="config-hint">Runs another pipeline as a sub-process. The step waits for it to finish before continuing.</span>
      </div>
    </template>

    <!-- ── Condiciones de flujo ────────────────────────────────────────── -->
    <div class="conditions-section">
      <div class="conditions-title">
        <i class="pi pi-code" style="font-size: 9px;" />
        CONDICIONES DE FLUJO
      </div>
      <div class="conditions-table">
        <div class="conditions-row">
          <div class="conditions-cell conditions-cell--label">
            <i class="pi pi-check-circle conditions-icon--success" />
            <span>on success</span>
          </div>
          <div class="conditions-cell conditions-cell--value">
            <Select v-model="local.on_success"
              :options="[
                { l: '→ continue', v: 'continue' },
                { l: '⏹ stop', v: 'stop' },
              ]"
              optionLabel="l" optionValue="v"
              size="small" fluid :disabled="disabled" />
          </div>
        </div>
        <div class="conditions-divider" />
        <div class="conditions-row">
          <div class="conditions-cell conditions-cell--label">
            <i class="pi pi-times-circle conditions-icon--fail" />
            <span>on failure</span>
          </div>
          <div class="conditions-cell conditions-cell--value">
            <Select v-model="local.on_failure"
              :options="[
                { l: '⏹ stop', v: 'stop' },
                { l: '→ continue', v: 'continue' },
              ]"
              optionLabel="l" optionValue="v"
              size="small" fluid :disabled="disabled" />
          </div>
        </div>
      </div>
      <span class="conditions-hint">
        Affect the <strong>next step</strong>, not this one.
      </span>
    </div>

  </div>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Select from 'primevue/select'
import SelectButton from 'primevue/selectbutton'
import Textarea from 'primevue/textarea'
import ToggleButton from 'primevue/togglebutton'

const props = defineProps({
  modelValue: Object,
  favorites: Array,
  pipelines: Array,
  disabled: Boolean,
})
const emit = defineEmits(['update:modelValue'])

const local = reactive({ ...props.modelValue, config: { ...(props.modelValue?.config || {}) } })

watch(local, (val) => emit('update:modelValue', { ...val }), { deep: true })
watch(() => props.modelValue, (val) => {
  if (!val) return
  Object.assign(local, val)
  Object.assign(local.config, val.config || {})
}, { deep: true })

const typeOptions = [
  { label: 'Shell', value: 'shell' },
  { label: 'Script', value: 'script' },
  { label: 'Module', value: 'module' },
]

const typeHints = {
  shell: 'Runs a shell command directly on the server.',
  script: 'Runs one of your scripts saved in favorites.',
  module: 'Predefined actions: move files, send emails, compress, etc.',
}

const moduleOptions = [
  { label: '📄 Load .env — environment variables', value: 'load_env' },
  { label: '↗ Move file', value: 'move_file' },
  { label: '⧉ Copy file', value: 'copy_file' },
  { label: '🗑 Delete file', value: 'delete_file' },
  { label: '📁 Create directory', value: 'mkdir' },
  { label: '✏ Write file', value: 'write_file' },
  { label: '✎ Rename file', value: 'rename_file' },
  { label: '📦 Compress (tar.gz / zip)', value: 'compress' },
  { label: '📂 Decompress', value: 'decompress' },
  { label: '? Check file/dir existence', value: 'check_exists' },
  { label: '⏱ Wait N seconds', value: 'delay' },
  { label: '📝 Log message', value: 'log' },
  { label: '✉ Send email', value: 'email' },
  { label: '⚡ Call another pipeline', value: 'call_pipeline' },
]

const moduleHints = {
  load_env: 'Loads a .env file and makes its variables available to subsequent steps.',
  move_file: 'Moves a file or directory from one location to another.',
  copy_file: 'Copies a file or directory while preserving the original.',
  delete_file: 'Deletes the specified file or directory.',
  mkdir: 'Creates the directory (and any intermediate directories if they do not exist).',
  write_file: 'Writes text to a file, creating it if it does not exist.',
  rename_file: 'Renames a file within the same directory.',
  compress: 'Compresses a file or folder into tar.gz or zip.',
  decompress: 'Extracts the contents of a tar.gz or zip archive.',
  check_exists: 'Checks whether a file or directory exists. Fails if not found.',
  delay: 'Pauses the pipeline execution for N seconds.',
  log: 'Records a message in the execution log without running anything.',
  email: 'Sends an email using the server SMTP configuration.',
  call_pipeline: 'Runs another pipeline and waits for it to finish.',
}

const favoriteOptions = computed(() =>
  (props.favorites || []).map(f => ({ label: f.path.split('/').pop(), value: f.id }))
)
const pipelineOptions = computed(() =>
  (props.pipelines || []).map(p => ({ label: p.name, value: p.id }))
)

function onTypeChange() {
  local.config = {}
  if (local.step_type === 'shell') local.config.command = ''
  if (local.step_type === 'module') { local.config.module = 'log'; local.config.message = ''; local.config.level = 'info' }
}

function onModuleChange() {
  const m = local.config.module
  local.config = { module: m }
  if (m === 'load_env' || m === 'delete_file' || m === 'mkdir') local.config.path = ''
  if (m === 'move_file' || m === 'copy_file') { local.config.src = ''; local.config.dst = '' }
  if (m === 'compress') { local.config.src = ''; local.config.dst = ''; local.config.format = 'tar.gz' }
  if (m === 'decompress') { local.config.src = ''; local.config.dst = '' }
  if (m === 'write_file') { local.config.path = ''; local.config.content = ''; local.config.mode = 'overwrite' }
  if (m === 'rename_file') { local.config.path = ''; local.config.new_name = ''; local.config.use_timestamp = false }
  if (m === 'check_exists') { local.config.path = ''; local.config.type = 'file' }
  if (m === 'delay') local.config.seconds = 5
  if (m === 'log') { local.config.message = ''; local.config.level = 'info' }
  if (m === 'email') { local.config.to = ''; local.config.subject = ''; local.config.body = ''; local.config.attachment = '' }
  if (m === 'call_pipeline') local.config.pipeline_id = null
}
</script>

<style scoped>
.step-config {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.config-row {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.config-label {
  display: flex;
  align-items: center;
  gap: 5px;
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 1.5px;
  color: var(--p-text-muted-color);
}

.config-optional {
  font-weight: 400;
  letter-spacing: 0;
  opacity: 0.65;
  font-size: 9px;
}

.config-hint {
  font-size: var(--text-2xs);
  color: var(--p-text-muted-color);
  opacity: 0.8;
  line-height: 1.5;
}

.config-hint code {
  font-family: var(--font-mono);
  background: var(--p-surface-card);
  border: 1px solid var(--p-surface-border);
  padding: 0 4px;
  border-radius: 3px;
  font-size: 9px;
}

/* Conditions section */
.conditions-section {
  border-top: 1px solid var(--p-surface-border);
  padding-top: 10px;
  margin-top: 4px;
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.conditions-title {
  display: flex;
  align-items: center;
  gap: 5px;
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 1.5px;
  color: var(--p-text-muted-color);
  opacity: 0.7;
}

/* Table */
.conditions-table {
  background: var(--p-surface-ground);
  border: 1px solid var(--p-surface-border);
  border-radius: 5px;
  overflow: hidden;
  font-family: var(--font-mono);
  font-size: 10px;
}

.conditions-row {
  display: flex;
  align-items: center;
  min-height: 34px;
}

.conditions-divider {
  height: 1px;
  background: var(--p-surface-border);
}

.conditions-cell {
  padding: 5px 8px;
  display: flex;
  align-items: center;
  gap: 5px;
}

.conditions-cell--label {
  width: 90px;
  flex-shrink: 0;
  background: color-mix(in srgb, var(--p-surface-border) 30%, transparent);
  border-right: 1px solid var(--p-surface-border);
  color: var(--p-text-muted-color);
  font-size: 9px;
  letter-spacing: 0.5px;
  align-self: stretch;
}

.conditions-cell--value {
  flex: 1;
  min-width: 0;
  padding: 4px 6px;
}

.conditions-icon--success {
  font-size: 9px;
  color: var(--p-green-500);
  flex-shrink: 0;
}

.conditions-icon--fail {
  font-size: 9px;
  color: var(--p-red-400);
  flex-shrink: 0;
}

.conditions-hint {
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--p-text-muted-color);
  opacity: 0.65;
  line-height: 1.5;
}
</style>
