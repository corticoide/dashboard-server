<template>
  <header class="app-header" :class="{ 'sidebar-collapsed': props.sidebarCollapsed }">
    <Toolbar class="header-toolbar">
      <template #start>
        <span class="page-title">{{ pageTitle }}</span>
      </template>
      <template #end>
        <div class="header-right">
          <Badge value="LIVE" severity="success" class="live-badge" />
          <Button
            :icon="isDark ? 'pi pi-sun' : 'pi pi-moon'"
            text
            rounded
            size="small"
            :title="isDark ? 'Switch to light' : 'Switch to dark'"
            @click="toggleTheme"
          />
          <Chip :label="auth.username" icon="pi pi-user" class="user-chip" />
          <Button
            label="Sign out"
            icon="pi pi-sign-out"
            text
            severity="danger"
            size="small"
            @click="handleLogout"
          />
        </div>
      </template>
    </Toolbar>
  </header>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import Toolbar from 'primevue/toolbar'
import Button from 'primevue/button'
import Badge from 'primevue/badge'
import Chip from 'primevue/chip'
import { useAuthStore } from '../../stores/auth.js'

const props = defineProps({ pageTitle: String, sidebarCollapsed: Boolean })

const auth = useAuthStore()
const router = useRouter()

const savedTheme = localStorage.getItem('theme') || 'dark'
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
.app-header {
  position: fixed;
  top: 0; right: 0;
  left: var(--sidebar-width);
  height: var(--header-height);
  z-index: 99;
  transition: left 0.2s ease;
}
.app-header.sidebar-collapsed {
  left: var(--sidebar-collapsed-width);
}
.header-toolbar {
  height: 100%;
  border-radius: 0;
  border-left: none;
  border-top: none;
  border-right: none;
}
.page-title {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--p-text-muted-color);
}
.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}
.user-chip {
  font-size: 12px;
  font-family: var(--font-mono);
}
</style>
