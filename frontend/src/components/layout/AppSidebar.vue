<template>
  <aside :class="['sidebar', { collapsed }]">

    <!-- Brand -->
    <div class="brand">
      <div class="brand-icon">
        <i class="pi pi-desktop" />
      </div>
      <div class="brand-text">
        <span class="brand-name">SERVERDASH</span>
        <span class="brand-status">
          <span class="status-dot"></span>
          <span class="status-label">ONLINE</span>
        </span>
      </div>
    </div>

    <!-- Toggle -->
    <button class="toggle-btn" :title="collapsed ? 'Expand' : 'Collapse'" @click="$emit('toggle')">
      <i class="pi pi-bars" />
    </button>

    <!-- Nav -->
    <nav class="nav">
      <div class="nav-section">
        <span class="nav-section-label">MONITOR</span>
        <RouterLink class="nav-item" to="/" :class="{ active: route.path === '/' }">
          <i class="pi pi-th-large nav-icon" />
          <span class="nav-label">Dashboard</span>
        </RouterLink>
        <RouterLink class="nav-item" to="/services" :class="{ active: route.path === '/services' }">
          <i class="pi pi-cog nav-icon" />
          <span class="nav-label">Services</span>
        </RouterLink>
        <RouterLink class="nav-item" to="/files" :class="{ active: route.path === '/files' }">
          <i class="pi pi-folder-open nav-icon" />
          <span class="nav-label">Files</span>
        </RouterLink>
      </div>

      <div class="nav-section">
        <span class="nav-section-label">MANAGE</span>
        <RouterLink class="nav-item" to="/scripts" :class="{ active: route.path === '/scripts' }">
          <i class="pi pi-code nav-icon" />
          <span class="nav-label">Scripts</span>
        </RouterLink>
        <RouterLink class="nav-item" to="/crontab" :class="{ active: route.path === '/crontab' }">
          <i class="pi pi-clock nav-icon" />
          <span class="nav-label">Crontab</span>
        </RouterLink>
        <RouterLink class="nav-item" to="/logs" :class="{ active: route.path === '/logs' }">
          <i class="pi pi-list nav-icon" />
          <span class="nav-label">Logs</span>
        </RouterLink>
      </div>
    </nav>

  </aside>
</template>

<script setup>
import { useRoute } from 'vue-router'
import { RouterLink } from 'vue-router'

defineProps({ collapsed: Boolean })
defineEmits(['toggle'])

const route = useRoute()
</script>

<style scoped>
.sidebar {
  width: var(--sidebar-width);
  display: flex;
  flex-direction: column;
  height: 100vh;
  position: fixed;
  top: 0; left: 0;
  transition: width 0.2s ease;
  z-index: 100;
  overflow: hidden;
  border-right: 1px solid var(--p-surface-border);
  background: var(--p-surface-card);
}
.sidebar.collapsed { width: var(--sidebar-collapsed-width); }

/* Brand */
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 12px;
  height: var(--header-height);
  border-bottom: 1px solid var(--p-surface-border);
  flex-shrink: 0;
}
.brand-icon {
  width: 30px; height: 30px;
  background: color-mix(in srgb, var(--brand-orange) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand-orange) 30%, transparent);
  border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  color: var(--brand-orange);
  font-size: var(--text-base);
}
.brand-text {
  display: flex; flex-direction: column; gap: 2px;
  white-space: nowrap; overflow: hidden;
}
.brand-name {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: 2.5px;
  color: var(--brand-orange);
}
.brand-status {
  display: flex; align-items: center; gap: 4px;
}
.status-dot {
  width: 5px; height: 5px;
  border-radius: 50%;
  background: var(--p-green-500);
  animation: blink 2.5s ease-in-out infinite;
}
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.status-label {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 1.5px;
  color: var(--p-green-500);
}

/* Toggle */
.toggle-btn {
  width: 100%;
  display: flex;
  align-items: center;
  padding: 10px 16px;
  background: transparent;
  border: none;
  border-bottom: 1px solid var(--p-surface-border);
  color: var(--p-text-muted-color);
  cursor: pointer;
  font-size: var(--text-base);
  transition: color 0.15s, background 0.15s;
  flex-shrink: 0;
}
.toggle-btn:hover {
  background: var(--p-surface-hover);
  color: var(--p-text-color);
}

/* Nav */
.nav {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.nav-section {
  padding: 8px 0 4px;
}
.nav-section + .nav-section {
  border-top: 1px solid var(--p-surface-border);
  margin-top: 4px;
  padding-top: 12px;
}

.nav-section-label {
  display: block;
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  font-weight: 600;
  letter-spacing: 2px;
  color: var(--p-text-muted-color);
  padding: 0 14px 6px;
  white-space: nowrap;
  overflow: hidden;
  opacity: 0.6;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  margin: 1px 8px;
  border-radius: 6px;
  text-decoration: none;
  color: var(--p-text-muted-color);
  font-size: var(--text-base);
  font-family: var(--font-ui);
  transition: background 0.15s, color 0.15s;
  white-space: nowrap;
  overflow: hidden;
  border-left: 2px solid transparent;
}
.nav-item:hover {
  background: var(--p-surface-hover);
  color: var(--p-text-color);
}
.nav-item.active {
  background: color-mix(in srgb, var(--brand-orange) 10%, transparent);
  color: var(--brand-orange);
  border-left-color: var(--brand-orange);
  font-weight: 500;
}
.nav-item.active .nav-icon {
  color: var(--brand-orange);
}

.nav-icon {
  font-size: var(--text-base);
  flex-shrink: 0;
  width: 18px;
  text-align: center;
  color: var(--p-text-muted-color);
  transition: color 0.15s;
}

.nav-label {
  flex: 1;
  overflow: hidden;
}

/* Collapsed state */
.sidebar.collapsed .brand-text    { display: none; }
.sidebar.collapsed .nav-section-label { display: none; }
.sidebar.collapsed .nav-section + .nav-section { border-top: none; }
.sidebar.collapsed .nav-label     { display: none; }
.sidebar.collapsed .nav-item {
  justify-content: center;
  padding: 9px 0;
  margin: 1px 8px;
  border-left-color: transparent;
}
.sidebar.collapsed .nav-item.active {
  background: color-mix(in srgb, var(--brand-orange) 10%, transparent);
}
.sidebar.collapsed .nav-item.active .nav-icon {
  color: var(--brand-orange);
}
</style>
