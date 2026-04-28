<template>
  <header class="app-header" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
    <div class="header-inner">

      <!-- Left: page context -->
      <div class="header-left">
        <i :class="`pi ${pageIcon} header-page-icon`" aria-hidden="true" />
        <span class="header-page-title">{{ pageTitle }}</span>
      </div>

      <!-- Right: status + actions -->
      <div class="header-right">

        <!-- Live pulse -->
        <div class="live-indicator" aria-label="Live data feed active">
          <span class="live-dot" />
          <span class="live-label">LIVE</span>
        </div>

        <div class="h-divider" />

        <!-- Theme toggle -->
        <button
          class="header-icon-btn"
          @click="toggleTheme"
          :aria-label="isDark ? 'Switch to light mode' : 'Switch to dark mode'"
          v-tooltip.bottom="isDark ? 'Light mode' : 'Dark mode'"
        >
          <i :class="`pi ${isDark ? 'pi-sun' : 'pi-moon'}`" />
        </button>

        <div class="h-divider" />

        <!-- User pill -->
        <div class="user-pill">
          <div class="user-avatar" aria-hidden="true">{{ initial }}</div>
          <span class="user-name">{{ auth.username }}</span>
        </div>

        <!-- Sign out -->
        <button
          class="header-icon-btn sign-out-btn"
          @click="handleLogout"
          v-tooltip.bottom="'Sign out'"
          aria-label="Sign out"
        >
          <i class="pi pi-sign-out" />
        </button>

      </div>
    </div>
  </header>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth.js'

const props = defineProps({ pageTitle: String, sidebarCollapsed: Boolean })

const auth = useAuthStore()
const router = useRouter()

const PAGE_ICONS = {
  Dashboard: 'pi-chart-bar',
  Services:  'pi-server',
  Files:     'pi-folder',
  Scripts:   'pi-code',
  Crontab:   'pi-clock',
  Logs:      'pi-list',
  Settings:  'pi-sliders-h',
}
const pageIcon = computed(() => PAGE_ICONS[props.pageTitle] || 'pi-home')
const initial  = computed(() => auth.username?.charAt(0).toUpperCase() || '?')

const savedTheme = localStorage.getItem('theme') || 'dark'
const isDark = ref(savedTheme !== 'light')

function toggleTheme() {
  isDark.value = !isDark.value
  document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
}

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.app-header {
  position: fixed;
  top: 0; right: 0;
  left: var(--sidebar-width);
  height: var(--header-height);
  z-index: 99;
  background: color-mix(in srgb, var(--p-surface-card) 92%, transparent);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--p-surface-border);
  transition: left 0.2s ease;
}
.app-header.sidebar-collapsed { left: var(--sidebar-collapsed-width); }

.header-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 100%;
  padding: 0 20px 0 18px;
}

/* ── Left ───────────────────────────────── */
.header-left {
  display: flex;
  align-items: center;
  gap: 9px;
}
.header-page-icon {
  font-size: var(--text-sm);
  color: var(--brand-orange);
}
.header-page-title {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  font-weight: 600;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--p-text-color);
}

/* ── Right ──────────────────────────────── */
.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.h-divider {
  width: 1px;
  height: 18px;
  background: var(--p-surface-border);
  flex-shrink: 0;
}

/* Live indicator */
.live-indicator {
  display: flex;
  align-items: center;
  gap: 5px;
}
.live-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.5);
  animation: live-pulse 2s ease-in-out infinite;
}
@keyframes live-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.5); }
  50%       { box-shadow: 0 0 0 5px rgba(34, 197, 94, 0); }
}
@media (prefers-reduced-motion: reduce) { .live-dot { animation: none; } }
.live-label {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  font-weight: 600;
  letter-spacing: 1.5px;
  color: #22c55e;
}

/* Icon buttons */
.header-icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  color: var(--p-text-muted-color);
  font-size: var(--text-base);
  transition: background 0.15s, color 0.15s;
}
.header-icon-btn:hover {
  background: color-mix(in srgb, var(--p-text-color) 8%, transparent);
  color: var(--p-text-color);
}
.sign-out-btn:hover {
  background: color-mix(in srgb, #ef4444 12%, transparent);
  color: #f87171;
}

/* User pill */
.user-pill {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 4px 10px 4px 5px;
  border-radius: 20px;
  background: var(--p-surface-ground);
  border: 1px solid var(--p-surface-border);
}
.user-avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--brand-orange) 20%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand-orange) 40%, transparent);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  color: var(--brand-orange);
  flex-shrink: 0;
}
.user-name {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--p-text-muted-color);
  letter-spacing: 0.5px;
}
</style>
