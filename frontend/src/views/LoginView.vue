<template>
  <div class="login-page">

    <!-- Subtle background grid -->
    <div class="bg-grid" aria-hidden="true" />

    <div class="login-wrap">

      <!-- Card -->
      <div class="login-card">

        <!-- Brand -->
        <div class="brand-block">
          <div class="brand-icon-ring">
            <i class="pi pi-desktop brand-icon" />
          </div>
          <h1 class="brand-name">SERVERDASH</h1>
          <p class="brand-sub">Server Management Interface</p>
        </div>

        <!-- Divider -->
        <div class="card-divider" />

        <!-- Form -->
        <form @submit.prevent="handleLogin" class="login-form" novalidate>

          <div class="field">
            <label for="username" class="field-label">Username</label>
            <InputText
              id="username"
              v-model="username"
              autocomplete="username"
              placeholder="admin"
              :disabled="loading"
              class="field-input"
              autofocus
            />
          </div>

          <div class="field">
            <label for="password" class="field-label">Password</label>
            <Password
              inputId="password"
              v-model="password"
              :feedback="false"
              toggleMask
              fluid
              autocomplete="current-password"
              :disabled="loading"
              placeholder="••••••••"
              class="field-input"
            />
          </div>

          <!-- Error -->
          <Transition name="err-slide">
            <div v-if="error" class="error-banner" role="alert" aria-live="assertive">
              <i class="pi pi-exclamation-circle error-icon" />
              <span>{{ error }}</span>
            </div>
          </Transition>

          <Button
            type="submit"
            :loading="loading"
            :disabled="loading || !username || !password"
            class="submit-btn"
          >
            <template #default>
              <i v-if="!loading" class="pi pi-lock btn-icon" />
              <span>{{ loading ? 'Connecting…' : 'Authenticate' }}</span>
            </template>
          </Button>

        </form>
      </div>

      <!-- Footer hint -->
      <p class="login-footer">Secure connection · TLS encrypted</p>

    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Button from 'primevue/button'
import { useAuthStore } from '../stores/auth.js'

const auth = useAuthStore()
const router = useRouter()
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    router.push('/')
  } catch {
    error.value = 'Invalid credentials. Check your username and password.'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* ── Page ───────────────────────────────────────────────────────────────────── */
.login-page {
  min-height: 100dvh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--p-surface-ground);
  position: relative;
  overflow: hidden;
}

/* Subtle dot grid background */
.bg-grid {
  position: absolute;
  inset: 0;
  background-image:
    radial-gradient(circle, color-mix(in srgb, var(--brand-orange) 8%, transparent) 0%, transparent 70%),
    radial-gradient(ellipse at 20% 50%, color-mix(in srgb, var(--p-surface-800, #1e1e2e) 60%, transparent) 0%, transparent 60%);
  pointer-events: none;
}

.login-wrap {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  animation: card-enter 0.3s ease-out both;
}

@keyframes card-enter {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}

@media (prefers-reduced-motion: reduce) {
  .login-wrap { animation: none; }
}

/* ── Card ───────────────────────────────────────────────────────────────────── */
.login-card {
  width: 380px;
  background: var(--p-surface-card);
  border: 1px solid var(--p-surface-border);
  border-radius: 14px;
  overflow: hidden;
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--brand-orange) 12%, transparent),
    0 20px 60px -12px rgba(0, 0, 0, 0.5);
  /* orange accent top bar */
  padding-top: 3px;
  background-image: linear-gradient(
    to bottom,
    var(--brand-orange) 0px,
    var(--brand-orange) 3px,
    var(--p-surface-card) 3px
  );
}

/* ── Brand ──────────────────────────────────────────────────────────────────── */
.brand-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 32px 28px 24px;
}

.brand-icon-ring {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  background: color-mix(in srgb, var(--brand-orange) 14%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand-orange) 30%, transparent);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 4px;
}

.brand-icon {
  font-size: 22px;
  color: var(--brand-orange);
}

.brand-name {
  font-family: var(--font-mono);
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 4px;
  color: var(--p-text-color);
  margin: 0;
}

.brand-sub {
  font-family: var(--font-ui, 'Fira Sans', sans-serif);
  font-size: 12px;
  color: var(--p-text-muted-color);
  margin: 0;
  letter-spacing: 0.3px;
}

.card-divider {
  height: 1px;
  background: var(--p-surface-border);
  margin: 0 28px;
}

/* ── Form ───────────────────────────────────────────────────────────────────── */
.login-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 24px 28px 28px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-label {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--p-text-muted-color);
}

:deep(.field-input.p-inputtext),
:deep(.field-input .p-inputtext) {
  width: 100%;
  height: 42px;
  font-family: var(--font-mono);
  font-size: 13px;
  background: var(--p-surface-ground);
  border-color: var(--p-surface-border);
  border-radius: 7px;
  transition: border-color 0.15s, box-shadow 0.15s;
}

:deep(.field-input.p-inputtext:focus),
:deep(.field-input .p-inputtext:focus) {
  border-color: var(--brand-orange);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--brand-orange) 18%, transparent);
}

:deep(.p-password) {
  display: flex;
  width: 100%;
}
:deep(.p-password-input) {
  flex: 1;
  min-width: 0;
  width: 100% !important;
}

/* ── Error ──────────────────────────────────────────────────────────────────── */
.error-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 7px;
  background: color-mix(in srgb, #ef4444 12%, transparent);
  border: 1px solid color-mix(in srgb, #ef4444 30%, transparent);
  font-family: var(--font-mono);
  font-size: 12px;
  color: #f87171;
}
.error-icon { font-size: 13px; flex-shrink: 0; }

.err-slide-enter-active { transition: opacity 0.2s ease, transform 0.2s ease; }
.err-slide-leave-active { transition: opacity 0.15s ease, transform 0.15s ease; }
.err-slide-enter-from { opacity: 0; transform: translateY(-4px); }
.err-slide-leave-to   { opacity: 0; transform: translateY(-4px); }

/* ── Button ─────────────────────────────────────────────────────────────────── */
.submit-btn {
  width: 100%;
  height: 44px;
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 1.5px;
  border-radius: 8px;
  margin-top: 2px;
  justify-content: center;
  gap: 8px;
}
.btn-icon { font-size: 13px; }

/* ── Footer ─────────────────────────────────────────────────────────────────── */
.login-footer {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--p-text-muted-color);
  opacity: 0.5;
  letter-spacing: 0.5px;
  margin: 0;
}
</style>
