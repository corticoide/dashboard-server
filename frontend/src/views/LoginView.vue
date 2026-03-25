<template>
  <div class="login-page">
    <div class="login-card">
      <h1 class="login-title">ServerDash</h1>
      <p class="login-subtitle">Sign in to continue</p>
      <form @submit.prevent="handleLogin">
        <div class="field">
          <label>Username</label>
          <input type="text" v-model="username" autocomplete="username" required />
        </div>
        <div class="field">
          <label>Password</label>
          <input type="password" v-model="password" autocomplete="current-password" required />
        </div>
        <p v-if="error" class="error">{{ error }}</p>
        <button type="submit" :disabled="loading">
          {{ loading ? 'Signing in…' : 'Sign in' }}
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
}
.login-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 40px;
  width: 360px;
}
.login-title { font-size: 24px; margin-bottom: 4px; }
.login-subtitle { color: var(--text-muted); margin-bottom: 28px; }
.field { margin-bottom: 16px; }
.field label { display: block; margin-bottom: 6px; font-size: 13px; color: var(--text-muted); }
.field input {
  width: 100%; padding: 8px 12px;
  background: var(--surface-2); border: 1px solid var(--border);
  border-radius: 6px; color: var(--text); font-size: 14px;
}
.field input:focus { outline: none; border-color: var(--accent-blue); }
.error { color: var(--accent-red); font-size: 13px; margin-bottom: 12px; }
button {
  width: 100%; padding: 10px;
  background: var(--accent-blue); color: #fff;
  border: none; border-radius: 6px; font-size: 14px; cursor: pointer;
}
button:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
