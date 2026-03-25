<template>
  <aside :class="['sidebar', { collapsed }]">
    <button class="toggle-btn" @click="$emit('toggle')" title="Toggle sidebar">
      <span class="icon">☰</span>
    </button>
    <nav>
      <RouterLink to="/" class="nav-item" title="Dashboard">
        <span class="icon">⬛</span>
        <span class="label">Dashboard</span>
      </RouterLink>
    </nav>
  </aside>
</template>

<script setup>
defineProps({ collapsed: Boolean })
defineEmits(['toggle'])
</script>

<style scoped>
.sidebar {
  width: var(--sidebar-width);
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  height: 100vh;
  position: fixed;
  top: 0; left: 0;
  transition: width 0.2s ease;
  z-index: 100;
  overflow: hidden;
}
.sidebar.collapsed { width: var(--sidebar-collapsed-width); }
.toggle-btn {
  background: none; border: none; color: var(--text-muted);
  padding: 16px; cursor: pointer; font-size: 16px; text-align: left;
  width: 100%;
}
.toggle-btn:hover { color: var(--text); }
.nav-item {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 16px; color: var(--text-muted);
  border-radius: 6px; margin: 2px 8px;
  transition: background 0.15s, color 0.15s;
  white-space: nowrap;
}
.nav-item:hover, .nav-item.router-link-active {
  background: var(--surface-2); color: var(--text);
}
.sidebar.collapsed .label { display: none; }
.icon { font-size: 16px; flex-shrink: 0; }
</style>
