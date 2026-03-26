<template>
  <div class="login-page">
    <Card class="login-card">
      <template #header>
        <div class="brand-header">
          <i class="pi pi-desktop" style="font-size: 28px; color: var(--p-primary-color);" />
          <div>
            <div class="brand-name">SERVERDASH</div>
            <div class="brand-sub">Server Management Interface</div>
          </div>
        </div>
      </template>
      <template #content>
        <form @submit.prevent="handleLogin" class="login-form">
          <FloatLabel class="field">
            <InputText
              id="username"
              v-model="username"
              autocomplete="username"
              required
              class="w-full"
            />
            <label for="username">Username</label>
          </FloatLabel>

          <FloatLabel class="field">
            <Password
              inputId="password"
              v-model="password"
              :feedback="false"
              toggle-mask
              fluid
              autocomplete="current-password"
              required
            />
            <label for="password">Password</label>
          </FloatLabel>

          <Message v-if="error" severity="error" :closable="false" class="error-msg">
            {{ error }}
          </Message>

          <Button
            type="submit"
            :label="loading ? 'Connecting…' : 'Authenticate'"
            :loading="loading"
            :disabled="loading"
            class="w-full submit-btn"
            icon="pi pi-lock"
          />
        </form>
      </template>
    </Card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import Card from 'primevue/card'
import FloatLabel from 'primevue/floatlabel'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Message from 'primevue/message'
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
    error.value = 'Invalid credentials'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--p-surface-ground);
}

.login-card {
  width: 360px;
}

.brand-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 24px 24px 0;
  border-bottom: 1px solid var(--p-surface-border);
  padding-bottom: 16px;
}
.brand-name {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 3px;
  color: var(--p-primary-color);
}
.brand-sub {
  font-size: 11px;
  color: var(--p-text-muted-color);
  margin-top: 2px;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.field {
  width: 100%;
  margin-top: 8px;
}

.error-msg {
  margin: 0;
}

.submit-btn {
  font-family: var(--font-mono);
  letter-spacing: 1px;
}

:deep(.p-password) {
  display: flex;
  width: 100%;
}
:deep(.p-password-input) {
  flex: 1 1 0%;
  min-width: 0;
  width: 100% !important;
}
</style>
