<template>
  <header class="header" :class="{ 'sidebar-collapsed': props.sidebarCollapsed }">
    <div class="header-left">
      <span class="page-title">{{ pageTitle }}</span>
    </div>
    <div class="header-right">
      <div class="conn-indicator" title="API connected">
        <span class="conn-dot"></span>
        <span class="conn-label">LIVE</span>
      </div>
      <button class="icon-btn" @click="toggleTheme" :title="isDark ? 'Switch to light' : 'Switch to dark'">
        <svg v-if="isDark" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
          <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
        </svg>
        <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
        </svg>
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

const props = defineProps({ pageTitle: String, sidebarCollapsed: Boolean })

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
.header.sidebar-collapsed {
  left: var(--sidebar-collapsed-width);
}
.page-title {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 1.5px;
  color: var(--text-muted);
  text-transform: uppercase;
}
.header-right {
  display: flex; align-items: center; gap: 14px;
}

/* Live indicator */
.conn-indicator {
  display: flex; align-items: center; gap: 5px;
  padding: 3px 8px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 4px;
}
.conn-dot {
  width: 5px; height: 5px;
  border-radius: 50%;
  background: var(--accent-green);
  box-shadow: var(--glow-green);
}
.conn-label {
  font-family: var(--font-mono);
  font-size: 9px; letter-spacing: 1px;
  color: var(--accent-green);
}

.username {
  color: var(--text-muted);
  font-size: 12px;
  font-family: var(--font-mono);
}
.icon-btn {
  background: none;
  border: 1px solid var(--border);
  color: var(--text-muted);
  border-radius: 5px;
  padding: 5px 7px;
  cursor: pointer;
  display: flex; align-items: center;
  transition: color 0.15s, border-color 0.15s;
}
.icon-btn:hover { color: var(--text); border-color: var(--border-bright); }

.logout-btn {
  background: none;
  border: 1px solid var(--border);
  color: var(--text-muted);
  border-radius: 5px;
  padding: 4px 10px;
  cursor: pointer;
  font-size: 12px;
  font-family: var(--font-ui);
  transition: color 0.15s, border-color 0.15s;
}
.logout-btn:hover { color: var(--accent-red); border-color: var(--accent-red); }
</style>
