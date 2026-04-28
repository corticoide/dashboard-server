<template>
  <div class="settings-view">

    <!-- Header -->
    <div class="page-header">
      <div class="page-title">
        <i class="pi pi-sliders-h page-icon" />
        <span>SETTINGS</span>
      </div>
      <span class="page-subtitle">Admin only — changes take effect immediately</span>
    </div>

    <!-- Load error -->
    <div v-if="loadError" class="banner banner-error">
      <i class="pi pi-times-circle" /> {{ loadError }}
    </div>

    <!-- Loading skeleton -->
    <template v-if="loading">
      <div class="skeleton-row">
        <div class="skeleton-card" />
        <div class="skeleton-card" />
      </div>
      <div class="skeleton-card skeleton-card--wide" />
    </template>

    <template v-else>
      <!-- Two-column: Retention + SMTP -->
      <div class="settings-columns">

        <!-- ── Data Retention ─────────────────────────────────── -->
        <div class="scard">
          <div class="scard-head">
            <div class="icon-ring"><i class="pi pi-database" /></div>
            <div class="scard-head-text">
              <span class="scard-title">DATA RETENTION</span>
              <span class="scard-desc">How long each data type is kept before auto-deletion</span>
            </div>
          </div>

          <div class="scard-body">
            <div class="retention-grid">
              <div v-for="field in retentionFields" :key="field.key" class="rfield">
                <div class="rfield-meta">
                  <i :class="['pi', field.icon, 'rfield-icon']" />
                  <span class="rfield-label">{{ field.label }}</span>
                </div>
                <div class="rfield-input">
                  <InputNumber
                    v-model="retention[field.key]"
                    :min="1"
                    :max="3650"
                    fluid
                    :input-class="'rfield-num'"
                  />
                  <span class="rfield-unit">days</span>
                </div>
              </div>
            </div>
          </div>

          <div class="scard-foot">
            <transition name="fade">
              <span v-if="saved.retention" class="foot-ok">
                <i class="pi pi-check-circle" /> Saved
              </span>
            </transition>
            <Button
              label="Save Retention"
              icon="pi pi-check"
              size="small"
              @click="saveRetention"
              :loading="saving.retention"
            />
          </div>
        </div>

        <!-- ── SMTP Configuration ──────────────────────────────── -->
        <div class="scard">
          <div class="scard-head">
            <div class="icon-ring"><i class="pi pi-envelope" /></div>
            <div class="scard-head-text">
              <span class="scard-title">SMTP CONFIGURATION</span>
              <span class="scard-desc">Outbound email for alert notifications</span>
            </div>
          </div>

          <div class="scard-body">
            <!-- Connection -->
            <div class="field-group">
              <span class="group-label">CONNECTION</span>
              <div class="field-row-2">
                <div class="field">
                  <label class="field-label">HOST</label>
                  <InputText v-model="smtp.host" placeholder="smtp.example.com" fluid />
                </div>
                <div class="field field--port">
                  <label class="field-label">PORT</label>
                  <InputNumber v-model="smtp.port" :min="1" :max="65535" fluid />
                </div>
              </div>
            </div>

            <!-- Auth -->
            <div class="field-group">
              <span class="group-label">AUTHENTICATION</span>
              <div class="field">
                <label class="field-label">USERNAME</label>
                <InputText v-model="smtp.user" placeholder="user@example.com" fluid />
              </div>
              <div class="field">
                <label class="field-label">PASSWORD</label>
                <Password
                  v-model="smtp.password"
                  :feedback="false"
                  toggleMask
                  :placeholder="smtp.passwordSet ? '(leave empty to keep current)' : 'Enter password'"
                  fluid
                />
              </div>
            </div>

            <!-- Sender -->
            <div class="field-group">
              <span class="group-label">SENDER</span>
              <div class="field">
                <label class="field-label">FROM ADDRESS</label>
                <InputText v-model="smtp.from" placeholder="noreply@example.com" fluid />
              </div>
            </div>

            <!-- Test email -->
            <div class="field-group smtp-test-group">
              <span class="group-label">SEND TEST EMAIL</span>
              <div class="test-row">
                <InputText
                  v-model="smtp.testTo"
                  placeholder="recipient@example.com"
                  class="test-input"
                />
                <Button
                  label="Send"
                  icon="pi pi-send"
                  size="small"
                  outlined
                  @click="testSmtp"
                  :loading="saving.smtpTest"
                  :disabled="!smtp.testTo"
                />
              </div>
              <transition name="fade">
                <div
                  v-if="smtpTestResult"
                  :class="['banner', smtpTestResult.ok ? 'banner-success' : 'banner-error']"
                >
                  <i :class="['pi', smtpTestResult.ok ? 'pi-check-circle' : 'pi-times-circle']" />
                  {{ smtpTestResult.message }}
                </div>
              </transition>
            </div>
          </div>

          <div class="scard-foot">
            <transition name="fade">
              <span v-if="saved.smtp" class="foot-ok">
                <i class="pi pi-check-circle" /> Saved
              </span>
            </transition>
            <Button
              label="Save SMTP"
              icon="pi pi-check"
              size="small"
              @click="saveSmtp"
              :loading="saving.smtp"
            />
          </div>
        </div>

      </div>

      <!-- ── System Timezone ──────────────────────────────────────── -->
      <div class="scard scard--hz">
        <div class="scard-head">
          <div class="icon-ring"><i class="pi pi-globe" /></div>
          <div class="scard-head-text">
            <span class="scard-title">SYSTEM TIMEZONE</span>
            <span class="scard-desc">Changes the OS timezone via timedatectl — requires root</span>
          </div>
        </div>

        <div class="scard-body tz-body">

          <div class="tz-current-block">
            <span class="field-label">CURRENT</span>
            <div class="tz-current-value">
              <i class="pi pi-map-marker tz-pin" />
              <span class="tz-name">{{ timezone.current || '—' }}</span>
            </div>
          </div>

          <div class="tz-divider" />

          <div class="tz-set-block">
            <label class="field-label">SET TIMEZONE</label>
            <div class="tz-set-row">
              <Select
                v-model="timezone.selected"
                :options="timezone.available"
                filter
                filterPlaceholder="Search timezone..."
                placeholder="Select a timezone"
                class="tz-select"
              />
              <Button
                label="Apply"
                icon="pi pi-check"
                size="small"
                @click="applyTimezone"
                :loading="saving.timezone"
                :disabled="!timezone.selected || timezone.selected === timezone.current"
              />
            </div>
            <transition name="fade">
              <div v-if="tzError" class="banner banner-error" style="margin-top:8px">
                <i class="pi pi-times-circle" /> {{ tzError }}
              </div>
              <div v-else-if="saved.timezone" class="banner banner-success" style="margin-top:8px">
                <i class="pi pi-check-circle" /> Timezone updated to {{ timezone.current }}
              </div>
            </transition>
          </div>

        </div>
      </div>

    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import Button      from 'primevue/button'
import InputText   from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Password    from 'primevue/password'
import Select      from 'primevue/select'
import api from '../api/client.js'

// ── Retention field descriptors ──────────────────────────────────
const retentionFields = [
  { key: 'log',     label: 'Execution Logs',  icon: 'pi-list' },
  { key: 'metrics', label: 'Metrics History', icon: 'pi-chart-line' },
  { key: 'network', label: 'Network History', icon: 'pi-wifi' },
  { key: 'alerts',  label: 'Alert Fires',     icon: 'pi-bell' },
]

// ── State ────────────────────────────────────────────────────────
const loading   = ref(true)
const loadError = ref(null)

const retention = ref({ log: 30, metrics: 30, network: 30, alerts: 90 })

const smtp = ref({
  host: '', port: 587, user: '', password: '', from: '',
  passwordSet: false, testTo: '',
})

const timezone = ref({ current: '', selected: '', available: [] })

const saving = ref({ retention: false, smtp: false, smtpTest: false, timezone: false })
const saved  = ref({ retention: false, smtp: false, timezone: false })

const smtpTestResult = ref(null)
const tzError        = ref(null)

function flash(key) {
  saved.value[key] = true
  setTimeout(() => { saved.value[key] = false }, 3000)
}

// ── Data loading ─────────────────────────────────────────────────
async function loadSettings() {
  try {
    const { data } = await api.get('/settings')
    retention.value = {
      log:     data.log_retention_days,
      metrics: data.metrics_retention_days,
      network: data.network_retention_days,
      alerts:  data.alerts_retention_days,
    }
    smtp.value = {
      host:        data.smtp_host,
      port:        data.smtp_port,
      user:        data.smtp_user,
      password:    '',
      from:        data.smtp_from,
      passwordSet: data.smtp_password_set,
      testTo:      '',
    }
  } catch (e) {
    loadError.value = e.response?.data?.detail || 'Failed to load settings'
  }
}

async function loadTimezone() {
  try {
    const { data } = await api.get('/settings/timezone')
    timezone.value.current   = data.current
    timezone.value.selected  = data.current
    timezone.value.available = data.available
  } catch {
    // non-fatal
  }
}

// ── Save actions ─────────────────────────────────────────────────
async function saveRetention() {
  saving.value.retention = true
  try {
    await api.put('/settings', {
      log_retention_days:     retention.value.log,
      metrics_retention_days: retention.value.metrics,
      network_retention_days: retention.value.network,
      alerts_retention_days:  retention.value.alerts,
    })
    flash('retention')
  } catch (e) {
    loadError.value = e.response?.data?.detail || 'Failed to save retention settings'
  } finally {
    saving.value.retention = false
  }
}

async function saveSmtp() {
  saving.value.smtp = true
  try {
    const payload = {
      smtp_host: smtp.value.host,
      smtp_port: smtp.value.port,
      smtp_user: smtp.value.user,
      smtp_from: smtp.value.from,
    }
    if (smtp.value.password) payload.smtp_password = smtp.value.password
    await api.put('/settings', payload)
    if (smtp.value.password) smtp.value.passwordSet = true
    smtp.value.password = ''
    flash('smtp')
  } catch (e) {
    loadError.value = e.response?.data?.detail || 'Failed to save SMTP settings'
  } finally {
    saving.value.smtp = false
  }
}

async function testSmtp() {
  smtpTestResult.value  = null
  saving.value.smtpTest = true
  try {
    await api.post('/settings/test-smtp', {
      host:      smtp.value.host,
      port:      smtp.value.port,
      user:      smtp.value.user,
      password:  smtp.value.password,
      from_addr: smtp.value.from,
      to_addr:   smtp.value.testTo,
    })
    smtpTestResult.value = { ok: true, message: 'Test email sent successfully' }
  } catch (e) {
    smtpTestResult.value = {
      ok: false,
      message: e.response?.data?.detail || 'SMTP test failed',
    }
  } finally {
    saving.value.smtpTest = false
  }
}

async function applyTimezone() {
  tzError.value         = null
  saved.value.timezone  = false
  saving.value.timezone = true
  try {
    await api.put('/settings/timezone', { timezone: timezone.value.selected })
    timezone.value.current = timezone.value.selected
    flash('timezone')
  } catch (e) {
    tzError.value = e.response?.data?.detail || 'Failed to set timezone'
  } finally {
    saving.value.timezone = false
  }
}

onMounted(async () => {
  await Promise.all([loadSettings(), loadTimezone()])
  loading.value = false
})
</script>

<style scoped>
/* ── Root ──────────────────────────────────────────────────────── */
.settings-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 14px;
  animation: sd-enter 0.25s ease-out;
}

/* ── Page header subtitle ───────────────────────────────────────── */
.page-subtitle {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 1px;
  color: var(--p-text-muted-color);
  opacity: 0.6;
}

/* ── Skeleton ───────────────────────────────────────────────────── */
.skeleton-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
.skeleton-card {
  height: 320px;
  background: var(--p-surface-card);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-2xl);
  animation: shimmer 1.4s ease-in-out infinite;
}
.skeleton-card--wide {
  height: 120px;
}
@keyframes shimmer {
  0%, 100% { opacity: 0.5; }
  50%       { opacity: 1; }
}

/* ── Two-column grid ────────────────────────────────────────────── */
.settings-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
@media (max-width: 900px) {
  .settings-columns { grid-template-columns: 1fr; }
  .skeleton-row     { grid-template-columns: 1fr; }
}

/* ── Card shell ─────────────────────────────────────────────────── */
.scard {
  background: var(--p-surface-card);
  border: 1px solid var(--border-strong);
  border-left: 3px solid color-mix(in srgb, var(--brand-orange) 35%, transparent);
  border-radius: var(--radius-2xl);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: border-left-color 0.2s, box-shadow 0.2s;
}
.scard:hover {
  border-left-color: var(--brand-orange);
  box-shadow: 0 0 0 1px var(--orange-tint-08),
              0 8px 24px -8px rgba(0, 0, 0, 0.35);
}
.scard--hz { flex-direction: column; }

/* Card header */
.scard-head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 2px solid var(--border-strong);
  background: var(--surface-header);
}
.scard-head-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.scard-title {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 600;
  letter-spacing: 2px;
  color: var(--p-text-color);
}
.scard-desc {
  font-family: var(--font-ui);
  font-size: var(--text-2xs);
  color: var(--p-text-muted-color);
  opacity: 0.75;
}

/* Card body */
.scard-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 18px 16px;
  flex: 1;
}

/* Card footer */
.scard-foot {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  padding: 10px 16px;
  border-top: 1px solid var(--border-strong);
  background: var(--surface-header);
}
.foot-ok {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: #4ade80;
  flex: 1;
}

/* ── Retention grid ─────────────────────────────────────────────── */
.retention-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.rfield {
  background: var(--p-surface-ground);
  border: 1px solid var(--border-strong);
  border-left: 2px solid color-mix(in srgb, var(--brand-orange) 25%, transparent);
  border-radius: var(--radius-lg);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: var(--transition-fast);
}
.rfield:focus-within {
  border-left-color: var(--brand-orange);
  border-color: color-mix(in srgb, var(--brand-orange) 30%, transparent);
  background: var(--orange-tint-05);
}
.rfield-meta {
  display: flex;
  align-items: center;
  gap: 6px;
}
.rfield-icon {
  font-size: var(--text-sm);
  color: var(--brand-orange);
  opacity: 0.75;
}
.rfield-label {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 1px;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
}
.rfield-input {
  display: flex;
  align-items: center;
  gap: 7px;
}
.rfield-unit {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--p-text-muted-color);
  white-space: nowrap;
  flex-shrink: 0;
}

/* ── Field primitives ───────────────────────────────────────────── */
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.field-label {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 1.5px;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
}

/* ── Field group (SMTP sub-sections) ────────────────────────────── */
.field-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 14px;
  border-top: 1px solid var(--border-strong);
}
.field-group:first-child {
  padding-top: 0;
  border-top: none;
}
.group-label {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 2px;
  color: var(--brand-orange);
  opacity: 1;
  text-transform: uppercase;
  font-weight: 600;
}

/* Host + Port in a row */
.field-row-2 {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
}
.field--port { width: 100px; }

/* SMTP test sub-section */
.smtp-test-group {
  background: var(--p-surface-900);
  border-radius: var(--radius-base);
  padding: 12px;
  border: 1px solid var(--border-strong) !important;
}
.test-row {
  display: flex;
  gap: 8px;
}
.test-input { flex: 1; }

/* ── Timezone body ──────────────────────────────────────────────── */
.tz-body {
  flex-direction: row;
  align-items: flex-start;
  gap: 0;
  padding: 0;
}
.tz-current-block {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 18px 20px;
  min-width: 200px;
  flex-shrink: 0;
}
.tz-current-value {
  display: flex;
  align-items: center;
  gap: 8px;
}
.tz-pin {
  color: var(--brand-orange);
  font-size: var(--text-base);
}
.tz-name {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--brand-orange);
}
.tz-divider {
  width: 1px;
  background: var(--border-strong);
  align-self: stretch;
  flex-shrink: 0;
}
.tz-set-block {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 18px 20px;
  flex: 1;
}
.tz-set-row {
  display: flex;
  gap: 10px;
  align-items: center;
}
.tz-select { flex: 1; }

@media (max-width: 700px) {
  .tz-body       { flex-direction: column; }
  .tz-divider    { width: auto; height: 1px; }
  .retention-grid { grid-template-columns: 1fr; }
  .field-row-2   { grid-template-columns: 1fr; }
  .field--port   { width: 100%; }
}

/* ── Fade transition ────────────────────────────────────────────── */
.fade-enter-active, .fade-leave-active { transition: opacity 0.3s ease; }
.fade-enter-from, .fade-leave-to       { opacity: 0; }
</style>
