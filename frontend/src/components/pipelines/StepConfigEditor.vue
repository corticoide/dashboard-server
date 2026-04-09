<template>
  <div class="step-config">

    <!-- Nombre del paso -->
    <div class="config-row">
      <label class="config-label">NOMBRE DEL PASO</label>
      <InputText v-model="local.name" size="small" fluid
        placeholder="ej. Reiniciar nginx, Comprimir backups..."
        :disabled="disabled" />
    </div>

    <!-- Tipo de paso -->
    <div class="config-row">
      <label class="config-label">TIPO</label>
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
      <label class="config-label">COMANDO</label>
      <InputText v-model="local.config.command" size="small" fluid
        placeholder="systemctl restart nginx"
        :disabled="disabled" />
      <span class="config-hint">Se ejecuta en el shell del sistema con <code>/bin/sh -c</code>. Podés usar variables de entorno.</span>
    </div>

    <!-- ── Script ────────────────────────────────────────────────────── -->
    <div v-if="local.step_type === 'script'" class="config-row">
      <label class="config-label">SCRIPT FAVORITO</label>
      <Select v-model="local.config.favorite_id"
        :options="favoriteOptions"
        optionLabel="label" optionValue="value"
        size="small" fluid :disabled="disabled"
        placeholder="Seleccioná un script..."
      />
      <span class="config-hint">Ejecuta un script guardado en tus favoritos. Podés agregar scripts desde la sección Scripts.</span>
    </div>

    <!-- ── Módulo ─────────────────────────────────────────────────────── -->
    <template v-if="local.step_type === 'module'">
      <div class="config-row">
        <label class="config-label">MÓDULO</label>
        <Select v-model="local.config.module"
          :options="moduleOptions"
          optionLabel="label" optionValue="value"
          size="small" fluid :disabled="disabled"
          placeholder="Elegí un módulo..."
          @change="onModuleChange"
        />
        <span v-if="local.config.module" class="config-hint">{{ moduleHints[local.config.module] }}</span>
      </div>

      <!-- load_env / delete_file / check_exists base: path -->
      <div v-if="['load_env', 'delete_file', 'check_exists', 'mkdir'].includes(local.config.module)" class="config-row">
        <label class="config-label">RUTA</label>
        <InputText v-model="local.config.path" size="small" fluid
          placeholder="/ruta/al/archivo"
          :disabled="disabled" />
      </div>

      <!-- check_exists: tipo -->
      <div v-if="local.config.module === 'check_exists'" class="config-row">
        <label class="config-label">TIPO A VERIFICAR</label>
        <Select v-model="local.config.type"
          :options="[{ l: 'Archivo', v: 'file' }, { l: 'Directorio', v: 'dir' }, { l: 'Cualquiera', v: 'any' }]"
          optionLabel="l" optionValue="v"
          size="small" fluid :disabled="disabled" />
        <span class="config-hint">Si no existe, el paso falla. Usá las condiciones para controlar qué pasa después.</span>
      </div>

      <!-- move_file / copy_file / compress: src + dst -->
      <template v-if="['move_file', 'copy_file', 'compress'].includes(local.config.module)">
        <div class="config-row">
          <label class="config-label">ORIGEN</label>
          <InputText v-model="local.config.src" size="small" fluid
            placeholder="/origen/archivo.txt"
            :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">DESTINO</label>
          <InputText v-model="local.config.dst" size="small" fluid
            placeholder="/destino/"
            :disabled="disabled" />
        </div>
      </template>

      <!-- compress: formato -->
      <div v-if="local.config.module === 'compress'" class="config-row">
        <label class="config-label">FORMATO</label>
        <Select v-model="local.config.format"
          :options="[{ l: 'tar.gz', v: 'tar.gz' }, { l: 'zip', v: 'zip' }]"
          optionLabel="l" optionValue="v"
          size="small" fluid :disabled="disabled" />
      </div>

      <!-- decompress: src + dst -->
      <template v-if="local.config.module === 'decompress'">
        <div class="config-row">
          <label class="config-label">ARCHIVO A DESCOMPRIMIR</label>
          <InputText v-model="local.config.src" size="small" fluid
            placeholder="/ruta/archivo.tar.gz"
            :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">DIRECTORIO DESTINO</label>
          <InputText v-model="local.config.dst" size="small" fluid
            placeholder="/destino/"
            :disabled="disabled" />
        </div>
      </template>

      <!-- write_file -->
      <template v-if="local.config.module === 'write_file'">
        <div class="config-row">
          <label class="config-label">RUTA DEL ARCHIVO</label>
          <InputText v-model="local.config.path" size="small" fluid
            placeholder="/ruta/archivo.txt"
            :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">CONTENIDO</label>
          <Textarea v-model="local.config.content" rows="4" size="small" fluid
            placeholder="Contenido a escribir..."
            :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">MODO DE ESCRITURA</label>
          <Select v-model="local.config.mode"
            :options="[{ l: 'Sobrescribir (reemplaza todo)', v: 'overwrite' }, { l: 'Agregar al final', v: 'append' }]"
            optionLabel="l" optionValue="v"
            size="small" fluid :disabled="disabled" />
        </div>
      </template>

      <!-- rename_file -->
      <template v-if="local.config.module === 'rename_file'">
        <div class="config-row">
          <label class="config-label">RUTA ORIGINAL</label>
          <InputText v-model="local.config.path" size="small" fluid :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">NUEVO NOMBRE</label>
          <InputText v-model="local.config.new_name" size="small" fluid
            placeholder="nuevo-nombre.txt"
            :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">PREFIJO TIMESTAMP</label>
          <ToggleButton v-model="local.config.use_timestamp"
            onLabel="Sí — agrega fecha al inicio"
            offLabel="No"
            size="small" :disabled="disabled" />
          <span class="config-hint">Si está activo, el archivo quedará algo como <code>20260409_nuevo-nombre.txt</code>.</span>
        </div>
      </template>

      <!-- delay -->
      <div v-if="local.config.module === 'delay'" class="config-row">
        <label class="config-label">TIEMPO DE ESPERA (segundos)</label>
        <InputNumber v-model="local.config.seconds"
          :min="0" :max="3600"
          size="small" fluid :disabled="disabled"
          placeholder="5" />
        <span class="config-hint">El pipeline pausa esta cantidad de segundos antes de continuar al siguiente paso.</span>
      </div>

      <!-- log -->
      <template v-if="local.config.module === 'log'">
        <div class="config-row">
          <label class="config-label">MENSAJE</label>
          <InputText v-model="local.config.message" size="small" fluid
            placeholder="Iniciando proceso de backup..."
            :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">NIVEL</label>
          <Select v-model="local.config.level"
            :options="[{ l: 'Info', v: 'info' }, { l: 'Warn — advertencia', v: 'warn' }, { l: 'Error — indica fallo', v: 'error' }]"
            optionLabel="l" optionValue="v"
            size="small" fluid :disabled="disabled" />
        </div>
      </template>

      <!-- email -->
      <template v-if="local.config.module === 'email'">
        <div class="config-row">
          <label class="config-label">DESTINATARIO</label>
          <InputText v-model="local.config.to" size="small" fluid
            placeholder="admin@miservidor.com"
            :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">ASUNTO</label>
          <InputText v-model="local.config.subject" size="small" fluid
            placeholder="Backup completado"
            :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">CUERPO DEL EMAIL</label>
          <Textarea v-model="local.config.body" rows="3" size="small" fluid
            placeholder="El proceso finalizó correctamente."
            :disabled="disabled" />
        </div>
        <div class="config-row">
          <label class="config-label">ADJUNTO <span class="config-optional">(opcional)</span></label>
          <InputText v-model="local.config.attachment" size="small" fluid
            placeholder="/ruta/al/archivo.zip"
            :disabled="disabled" />
        </div>
      </template>

      <!-- call_pipeline -->
      <div v-if="local.config.module === 'call_pipeline'" class="config-row">
        <label class="config-label">PIPELINE A LLAMAR</label>
        <Select v-model="local.config.pipeline_id"
          :options="pipelineOptions"
          optionLabel="label" optionValue="value"
          size="small" fluid :disabled="disabled"
          placeholder="Seleccioná un pipeline..."
        />
        <span class="config-hint">Ejecuta otro pipeline como sub-proceso. El paso espera a que termine antes de continuar.</span>
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
            <span>si éxito</span>
          </div>
          <div class="conditions-cell conditions-cell--value">
            <Select v-model="local.on_success"
              :options="[
                { l: '→ continuar', v: 'continue' },
                { l: '⏹ detener', v: 'stop' },
              ]"
              optionLabel="l" optionValue="v"
              size="small" fluid :disabled="disabled" />
          </div>
        </div>
        <div class="conditions-divider" />
        <div class="conditions-row">
          <div class="conditions-cell conditions-cell--label">
            <i class="pi pi-times-circle conditions-icon--fail" />
            <span>si falla</span>
          </div>
          <div class="conditions-cell conditions-cell--value">
            <Select v-model="local.on_failure"
              :options="[
                { l: '⏹ detener', v: 'stop' },
                { l: '→ continuar', v: 'continue' },
              ]"
              optionLabel="l" optionValue="v"
              size="small" fluid :disabled="disabled" />
          </div>
        </div>
      </div>
      <span class="conditions-hint">
        Afectan al <strong>paso siguiente</strong>, no a este.
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
  { label: 'Módulo', value: 'module' },
]

const typeHints = {
  shell: 'Ejecuta un comando de shell directamente en el servidor.',
  script: 'Ejecuta uno de tus scripts guardados en favoritos.',
  module: 'Acciones predefinidas: mover archivos, enviar emails, comprimir, etc.',
}

const moduleOptions = [
  { label: '📄 Cargar .env — variables de entorno', value: 'load_env' },
  { label: '↗ Mover archivo', value: 'move_file' },
  { label: '⧉ Copiar archivo', value: 'copy_file' },
  { label: '🗑 Eliminar archivo', value: 'delete_file' },
  { label: '📁 Crear directorio', value: 'mkdir' },
  { label: '✏ Escribir archivo', value: 'write_file' },
  { label: '✎ Renombrar archivo', value: 'rename_file' },
  { label: '📦 Comprimir (tar.gz / zip)', value: 'compress' },
  { label: '📂 Descomprimir', value: 'decompress' },
  { label: '? Verificar existencia de archivo/dir', value: 'check_exists' },
  { label: '⏱ Esperar N segundos', value: 'delay' },
  { label: '📝 Registrar mensaje en log', value: 'log' },
  { label: '✉ Enviar email', value: 'email' },
  { label: '⚡ Llamar otro pipeline', value: 'call_pipeline' },
]

const moduleHints = {
  load_env: 'Carga un archivo .env y hace sus variables disponibles para los pasos siguientes.',
  move_file: 'Mueve un archivo o directorio de un lugar a otro.',
  copy_file: 'Copia un archivo o directorio preservando el original.',
  delete_file: 'Elimina el archivo o directorio indicado.',
  mkdir: 'Crea el directorio (y los intermedios si no existen).',
  write_file: 'Escribe texto en un archivo, creándolo si no existe.',
  rename_file: 'Renombra un archivo en el mismo directorio.',
  compress: 'Comprime un archivo o carpeta en tar.gz o zip.',
  decompress: 'Extrae el contenido de un archivo tar.gz o zip.',
  check_exists: 'Verifica si un archivo o directorio existe. Falla si no lo encuentra.',
  delay: 'Pausa la ejecución del pipeline por N segundos.',
  log: 'Registra un mensaje en el log de la ejecución, sin ejecutar nada.',
  email: 'Envía un email usando la configuración SMTP del servidor.',
  call_pipeline: 'Ejecuta otro pipeline y espera a que finalice.',
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
