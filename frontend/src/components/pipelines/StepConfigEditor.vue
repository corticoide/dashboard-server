<template>
  <div class="step-config">
    <div class="config-row">
      <label class="config-label">NOMBRE DEL PASO</label>
      <InputText v-model="local.name" size="small" fluid :disabled="disabled" />
    </div>

    <div class="config-row">
      <label class="config-label">TIPO</label>
      <SelectButton
        v-model="local.step_type"
        :options="typeOptions"
        optionLabel="label" optionValue="value"
        size="small" :disabled="disabled"
        @change="onTypeChange"
      />
    </div>

    <!-- Shell config -->
    <div v-if="local.step_type === 'shell'" class="config-row">
      <label class="config-label">COMANDO</label>
      <InputText v-model="local.config.command" size="small" fluid
        placeholder="systemctl restart nginx" :disabled="disabled" />
    </div>

    <!-- Script config -->
    <div v-if="local.step_type === 'script'" class="config-row">
      <label class="config-label">SCRIPT FAVORITO</label>
      <Select v-model="local.config.favorite_id" :options="favoriteOptions"
        optionLabel="label" optionValue="value" size="small" fluid :disabled="disabled" />
    </div>

    <!-- Module config -->
    <template v-if="local.step_type === 'module'">
      <div class="config-row">
        <label class="config-label">MÓDULO</label>
        <Select v-model="local.config.module" :options="moduleOptions"
          optionLabel="label" optionValue="value" size="small" fluid :disabled="disabled"
          @change="onModuleChange" />
      </div>
      <template v-if="local.config.module === 'load_env' || local.config.module === 'check_exists' || local.config.module === 'delete_file'">
        <div class="config-row">
          <label class="config-label">RUTA</label>
          <InputText v-model="local.config.path" size="small" fluid placeholder="/path/to/file" :disabled="disabled" />
        </div>
      </template>
      <template v-if="local.config.module === 'check_exists'">
        <div class="config-row">
          <label class="config-label">TIPO</label>
          <Select v-model="local.config.type" :options="[{l:'Archivo',v:'file'},{l:'Directorio',v:'dir'},{l:'Cualquiera',v:'any'}]"
            optionLabel="l" optionValue="v" size="small" fluid :disabled="disabled" />
        </div>
      </template>
      <template v-if="['move_file','copy_file','compress'].includes(local.config.module)">
        <div class="config-row">
          <label class="config-label">ORIGEN</label>
          <InputText v-model="local.config.src" size="small" fluid placeholder="{VAR}/archivo.txt" :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">DESTINO</label>
          <InputText v-model="local.config.dst" size="small" fluid placeholder="/destino/" :disabled="disabled" />
        </div>
      </template>
      <template v-if="local.config.module === 'compress'">
        <div class="config-row">
          <label class="config-label">FORMATO</label>
          <Select v-model="local.config.format" :options="[{l:'tar.gz',v:'tar.gz'},{l:'zip',v:'zip'}]"
            optionLabel="l" optionValue="v" size="small" fluid :disabled="disabled" />
        </div>
      </template>
      <template v-if="local.config.module === 'decompress'">
        <div class="config-row">
          <label class="config-label">ARCHIVO</label>
          <InputText v-model="local.config.src" size="small" fluid placeholder="/archivo.tar.gz" :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">DIRECTORIO DESTINO</label>
          <InputText v-model="local.config.dst" size="small" fluid placeholder="/destino/" :disabled="disabled" />
        </div>
      </template>
      <template v-if="local.config.module === 'mkdir'">
        <div class="config-row">
          <label class="config-label">RUTA</label>
          <InputText v-model="local.config.path" size="small" fluid placeholder="/nuevo/directorio" :disabled="disabled" />
        </div>
      </template>
      <template v-if="local.config.module === 'write_file'">
        <div class="config-row">
          <label class="config-label">RUTA</label>
          <InputText v-model="local.config.path" size="small" fluid :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">CONTENIDO</label>
          <Textarea v-model="local.config.content" rows="3" size="small" fluid :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">MODO</label>
          <Select v-model="local.config.mode" :options="[{l:'Sobrescribir',v:'overwrite'},{l:'Agregar',v:'append'}]"
            optionLabel="l" optionValue="v" size="small" fluid :disabled="disabled" />
        </div>
      </template>
      <template v-if="local.config.module === 'rename_file'">
        <div class="config-row">
          <label class="config-label">RUTA ORIGINAL</label>
          <InputText v-model="local.config.path" size="small" fluid :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">NUEVO NOMBRE</label>
          <InputText v-model="local.config.new_name" size="small" fluid :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">PREFIJO TIMESTAMP</label>
          <ToggleButton v-model="local.config.use_timestamp" onLabel="Sí" offLabel="No" size="small" :disabled="disabled" />
        </div>
      </template>
      <template v-if="local.config.module === 'delay'">
        <div class="config-row">
          <label class="config-label">SEGUNDOS</label>
          <InputNumber v-model="local.config.seconds" :min="0" :max="3600" size="small" fluid :disabled="disabled" />
        </div>
      </template>
      <template v-if="local.config.module === 'log'">
        <div class="config-row">
          <label class="config-label">MENSAJE</label>
          <InputText v-model="local.config.message" size="small" fluid :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">NIVEL</label>
          <Select v-model="local.config.level" :options="[{l:'Info',v:'info'},{l:'Warn',v:'warn'},{l:'Error',v:'error'}]"
            optionLabel="l" optionValue="v" size="small" fluid :disabled="disabled" />
        </div>
      </template>
      <template v-if="local.config.module === 'email'">
        <div class="config-row">
          <label class="config-label">DESTINATARIO</label>
          <InputText v-model="local.config.to" size="small" fluid placeholder="admin@host" :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">ASUNTO</label>
          <InputText v-model="local.config.subject" size="small" fluid :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">CUERPO</label>
          <Textarea v-model="local.config.body" rows="3" size="small" fluid :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">ADJUNTO (opcional)</label>
          <InputText v-model="local.config.attachment" size="small" fluid placeholder="/ruta/archivo" :disabled="disabled" />
        </div>
      </template>
      <template v-if="local.config.module === 'call_pipeline'">
        <div class="config-row">
          <label class="config-label">PIPELINE</label>
          <Select v-model="local.config.pipeline_id" :options="pipelineOptions"
            optionLabel="label" optionValue="value" size="small" fluid :disabled="disabled" />
        </div>
      </template>
    </template>

    <!-- Conditions -->
    <div class="config-row">
      <label class="config-label">SI EL PASO ANTERIOR TUVO ÉXITO</label>
      <Select v-model="local.on_success"
        :options="[{l:'Continuar (ejecutar este paso)',v:'continue'},{l:'Detener (saltar este paso)',v:'stop'}]"
        optionLabel="l" optionValue="v" size="small" fluid :disabled="disabled" />
    </div>
    <div class="config-row">
      <label class="config-label">SI EL PASO ANTERIOR FALLÓ</label>
      <Select v-model="local.on_failure"
        :options="[{l:'Detener pipeline',v:'stop'},{l:'Continuar (ejecutar de todas formas)',v:'continue'}]"
        optionLabel="l" optionValue="v" size="small" fluid :disabled="disabled" />
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

const local = reactive({ ...props.modelValue, config: { ...(props.modelValue.config || {}) } })

watch(local, (val) => emit('update:modelValue', { ...val }), { deep: true })
watch(() => props.modelValue, (val) => {
  Object.assign(local, val)
  Object.assign(local.config, val.config || {})
}, { deep: true })

const typeOptions = [
  { label: 'Shell', value: 'shell' },
  { label: 'Script', value: 'script' },
  { label: 'Módulo', value: 'module' },
]

const moduleOptions = [
  { label: '📄 Cargar .env', value: 'load_env' },
  { label: '↗ Mover archivo', value: 'move_file' },
  { label: '⧉ Copiar archivo', value: 'copy_file' },
  { label: '🗑 Eliminar archivo', value: 'delete_file' },
  { label: '📁 Crear directorio', value: 'mkdir' },
  { label: '✏ Escribir archivo', value: 'write_file' },
  { label: '✎ Renombrar archivo', value: 'rename_file' },
  { label: '📦 Comprimir', value: 'compress' },
  { label: '📂 Descomprimir', value: 'decompress' },
  { label: '? Verificar existencia', value: 'check_exists' },
  { label: '⏱ Esperar N segundos', value: 'delay' },
  { label: '📝 Log', value: 'log' },
  { label: '✉ Enviar email', value: 'email' },
  { label: '⚡ Llamar pipeline', value: 'call_pipeline' },
]

const favoriteOptions = computed(() =>
  (props.favorites || []).map(f => ({ label: f.path.split('/').pop(), value: f.id }))
)
const pipelineOptions = computed(() =>
  (props.pipelines || []).map(p => ({ label: p.name, value: p.id }))
)

function onTypeChange() {
  local.config = {}
  if (local.step_type === 'shell') local.config.command = ''
  if (local.step_type === 'module') local.config.module = 'log'
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
  if (m === 'email') { local.config.to = ''; local.config.subject = ''; local.config.body = '' }
  if (m === 'call_pipeline') local.config.pipeline_id = null
}
</script>

<style scoped>
.step-config { display: flex; flex-direction: column; gap: 10px; }
.config-row { display: flex; flex-direction: column; gap: 4px; }
.config-label { font-family: var(--font-mono); font-size: var(--text-2xs); letter-spacing: 1.5px; color: var(--p-text-muted-color); text-transform: uppercase; }
</style>
