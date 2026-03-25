<template>
  <div class="login-page">
    <div class="login-card">
      <div class="brand-header">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--accent-blue)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>
        </svg>
        <div>
          <div class="brand-name">SERVERDASH</div>
          <div class="brand-sub">Server Management Interface</div>
        </div>
      </div>

      <form @submit.prevent="handleLogin">
        <div class="field">
          <label>USERNAME</label>
          <input type="text" v-model="username" autocomplete="username" required placeholder="admin" />
        </div>
        <div class="field">
          <label>PASSWORD</label>
          <input type="password" v-model="password" autocomplete="current-password" required placeholder="••••••••" />
        </div>
        <p v-if="error" class="error">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          {{ error }}
        </p>
        <button type="submit" :disabled="loading">
          <span v-if="!loading">AUTHENTICATE</span>
          <span v-else>CONNECTING…</span>
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
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
  background: var(--bg);
  background-image:
    radial-gradient(circle at 20% 50%, rgba(14, 165, 233, 0.04) 0%, transparent 50%),
    radial-gradient(circle at 80% 20%, rgba(34, 197, 94, 0.03) 0%, transparent 40%);
}
.login-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-top: 2px solid var(--accent-blue);
  border-radius: 10px;
  padding: 36px 32px;
  width: 340px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.4);
}

.brand-header {
  display: flex; align-items: center; gap: 12px;
  margin-bottom: 28px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--border);
}
.brand-name {
  font-family: var(--font-mono);
  font-size: 13px; font-weight: 600;
  letter-spacing: 3px;
  color: var(--accent-blue);
}
.brand-sub {
  font-size: 11px; color: var(--text-muted);
  margin-top: 2px;
}

.field { margin-bottom: 14px; }
.field label {
  display: block;
  font-family: var(--font-mono);
  font-size: 9px; letter-spacing: 1.5px;
  color: var(--text-muted);
  margin-bottom: 6px;
}
.field input {
  width: 100%; padding: 9px 12px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 5px;
  color: var(--text);
  font-family: var(--font-mono);
  font-size: 13px;
  transition: border-color 0.15s;
}
.field input::placeholder { color: var(--text-dim); }
.field input:focus {
  outline: none;
  border-color: var(--accent-blue);
  box-shadow: var(--glow-blue);
}

.error {
  display: flex; align-items: center; gap: 6px;
  color: var(--accent-red);
  font-size: 12px;
  margin-bottom: 12px;
  padding: 8px 10px;
  background: rgba(239, 68, 68, 0.07);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 5px;
}

button[type="submit"] {
  width: 100%; padding: 10px;
  background: var(--accent-blue);
  color: #fff;
  border: none; border-radius: 5px;
  font-family: var(--font-mono);
  font-size: 11px; letter-spacing: 2px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s, box-shadow 0.15s;
}
button[type="submit"]:hover:not(:disabled) {
  box-shadow: var(--glow-blue);
  opacity: 0.9;
}
button[type="submit"]:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
