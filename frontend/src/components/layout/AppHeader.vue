<template>
  <header class="header">
    <span class="page-title">{{ pageTitle }}</span>
    <div class="header-right">
      <button class="theme-btn" @click="toggleTheme" :title="isDark ? 'Switch to light' : 'Switch to dark'">
        {{ isDark ? '☀️' : '🌙' }}
      </button>
      <span class="username">{{ auth.username }}</span>
      <button class="logout-btn" @click="handleLogout">Sign out</button>
    </div>
  </header>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth.js'

defineProps({ pageTitle: String })

const auth = useAuthStore()
const router = useRouter()

const savedTheme = localStorage.getItem('theme') || 'dark'
document.documentElement.setAttribute('data-theme', savedTheme)
const isDark = ref(savedTheme !== 'light')

function toggleTheme() {
  isDark.value = !isDark.value
  const theme = isDark.value ? 'dark' : 'light'
  document.documentElement.setAttribute('data-theme', theme)
  localStorage.setItem('theme', theme)
}

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.header {
  height: var(--header-height);
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  position: fixed;
  top: 0; right: 0;
  left: var(--sidebar-width);
  transition: left 0.2s ease;
  z-index: 99;
}
.page-title { font-weight: 600; font-size: 15px; }
.header-right { display: flex; align-items: center; gap: 12px; }
.username { color: var(--text-muted); font-size: 13px; }
.theme-btn, .logout-btn {
  background: none; border: 1px solid var(--border);
  color: var(--text-muted); border-radius: 6px;
  padding: 4px 10px; cursor: pointer; font-size: 12px;
}
.theme-btn:hover, .logout-btn:hover { color: var(--text); border-color: var(--text-muted); }
</style>
