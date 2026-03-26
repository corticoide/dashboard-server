<template>
  <aside :class="['sidebar', { collapsed }]">
    <!-- Brand -->
    <div class="brand">
      <div class="brand-icon">
        <i class="pi pi-desktop" style="color: var(--p-primary-color); font-size: 18px;" />
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
    <Button
      :icon="collapsed ? 'pi pi-bars' : 'pi pi-bars'"
      text
      plain
      class="toggle-btn"
      :title="collapsed ? 'Expand' : 'Collapse'"
      @click="$emit('toggle')"
    />

    <!-- Nav -->
    <PanelMenu :model="menuItems" class="nav-menu" :pt="panelMenuPt" />
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Button from 'primevue/button'
import PanelMenu from 'primevue/panelmenu'

const props = defineProps({ collapsed: Boolean })
defineEmits(['toggle'])

const route = useRoute()
const router = useRouter()

const menuItems = computed(() => [
  {
    label: 'MONITOR',
    items: [
      {
        label: 'Dashboard',
        icon: 'pi pi-th-large',
        class: route.path === '/' ? 'nav-item-active' : '',
        command: () => router.push('/'),
      },
      {
        label: 'Services',
        icon: 'pi pi-cog',
        class: route.path === '/services' ? 'nav-item-active' : '',
        command: () => router.push('/services'),
      },
      {
        label: 'Files',
        icon: 'pi pi-folder-open',
        class: route.path === '/files' ? 'nav-item-active' : '',
        command: () => router.push('/files'),
      },
    ],
  },
  {
    label: 'MANAGE',
    items: [
      {
        label: 'Scripts',
        icon: 'pi pi-code',
        class: route.path === '/scripts' ? 'nav-item-active' : '',
        command: () => router.push('/scripts'),
      },
      {
        label: 'Crontab',
        icon: 'pi pi-clock',
        class: route.path === '/crontab' ? 'nav-item-active' : '',
        command: () => router.push('/crontab'),
      },
      {
        label: 'Logs',
        icon: 'pi pi-list',
        class: route.path === '/logs' ? 'nav-item-active' : '',
        command: () => router.push('/logs'),
      },
    ],
  },
])

// Pass-through to keep panels always expanded
const panelMenuPt = {
  headerAction: { style: 'display: none' },
}
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
  padding: 14px 12px;
  border-bottom: 1px solid var(--p-surface-border);
  min-height: var(--header-height);
  flex-shrink: 0;
}
.brand-icon {
  width: 32px; height: 32px;
  background: var(--p-surface-hover);
  border: 1px solid var(--p-surface-border);
  border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.brand-text {
  display: flex; flex-direction: column; gap: 2px;
  white-space: nowrap; overflow: hidden;
}
.brand-name {
  font-family: var(--font-mono);
  font-size: 11px; font-weight: 600;
  letter-spacing: 2px;
  color: var(--p-primary-color);
}
.brand-status {
  display: flex; align-items: center; gap: 4px;
}
.status-dot {
  width: 5px; height: 5px;
  border-radius: 50%;
  background: var(--p-green-500);
  animation: pulse 2.5s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
.status-label {
  font-family: var(--font-mono);
  font-size: 8px; letter-spacing: 1.5px;
  color: var(--p-green-500);
}

/* Toggle */
.toggle-btn {
  width: 100%;
  border-radius: 0 !important;
  justify-content: flex-start;
  padding: 10px 18px !important;
}

/* Nav */
.nav-menu {
  flex: 1;
  overflow-y: auto;
  border: none !important;
}

/* Hide group headers (labels like MONITOR / MANAGE) */
:deep(.p-panelmenu-header) {
  padding: 10px 8px 4px;
}
:deep(.p-panelmenu-header-content) {
  background: transparent !important;
  border: none !important;
}
:deep(.p-panelmenu-header-label) {
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 1.5px;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
}
:deep(.p-panelmenu-header-icon) { display: none; }

:deep(.p-panelmenu-content) {
  background: transparent !important;
  border: none !important;
  padding: 0 8px;
}

:deep(.p-menuitem-link) {
  border-radius: 5px;
  padding: 8px 10px;
  color: var(--p-text-muted-color) !important;
  gap: 10px;
}
:deep(.p-menuitem-link:hover) {
  background: var(--p-surface-hover) !important;
  color: var(--p-text-color) !important;
}
:deep(.nav-item-active .p-menuitem-link) {
  background: var(--p-surface-hover) !important;
  color: var(--p-primary-color) !important;
  border-left: 2px solid var(--p-primary-color);
  padding-left: 8px;
}

/* Collapsed: hide labels and group headers */
.sidebar.collapsed :deep(.p-panelmenu-header) { visibility: hidden; height: 0; padding: 0; overflow: hidden; }
.sidebar.collapsed :deep(.p-panelmenu-item-label) { display: none; }
.sidebar.collapsed .brand-text { display: none; }
</style>
