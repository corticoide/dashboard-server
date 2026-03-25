<template>
  <aside :class="['sidebar', { collapsed }]">
    <!-- Brand -->
    <div class="brand">
      <div class="brand-icon">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--accent-blue)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>
        </svg>
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
    <button class="toggle-btn" @click="$emit('toggle')" :title="collapsed ? 'Expand' : 'Collapse'">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/>
      </svg>
    </button>

    <!-- Nav -->
    <nav class="nav">
      <div class="nav-section-label">MONITOR</div>
      <RouterLink to="/" class="nav-item" title="Dashboard">
        <svg class="nav-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>
        </svg>
        <span class="nav-label">Dashboard</span>
      </RouterLink>
      <RouterLink to="/services" class="nav-item" title="Services">
        <svg class="nav-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/>
        </svg>
        <span class="nav-label">Services</span>
      </RouterLink>
      <RouterLink to="/files" class="nav-item disabled" title="Files">
        <svg class="nav-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
        </svg>
        <span class="nav-label">Files</span>
      </RouterLink>
      <div class="nav-section-label">MANAGE</div>
      <RouterLink to="/scripts" class="nav-item disabled" title="Scripts">
        <svg class="nav-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>
        </svg>
        <span class="nav-label">Scripts</span>
      </RouterLink>
      <RouterLink to="/crontab" class="nav-item disabled" title="Crontab">
        <svg class="nav-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
        </svg>
        <span class="nav-label">Crontab</span>
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

/* Brand */
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 12px;
  border-bottom: 1px solid var(--border);
  min-height: var(--header-height);
}
.brand-icon {
  width: 32px; height: 32px;
  background: var(--surface-2);
  border: 1px solid var(--border-bright);
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
  color: var(--accent-blue);
}
.brand-status {
  display: flex; align-items: center; gap: 4px;
}
.status-dot {
  width: 5px; height: 5px;
  border-radius: 50%;
  background: var(--accent-green);
  box-shadow: var(--glow-green);
  animation: pulse 2.5s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
.status-label {
  font-family: var(--font-mono);
  font-size: 8px; letter-spacing: 1.5px;
  color: var(--accent-green);
}

/* Toggle */
.toggle-btn {
  background: none; border: none;
  color: var(--text-muted); padding: 10px 18px;
  cursor: pointer; text-align: left; width: 100%;
  transition: color 0.15s;
}
.toggle-btn:hover { color: var(--text); }

/* Nav */
.nav { flex: 1; padding: 4px 8px; overflow-y: auto; }
.nav-section-label {
  font-family: var(--font-mono);
  font-size: 9px; letter-spacing: 1.5px;
  color: var(--text-dim);
  padding: 10px 8px 4px;
  white-space: nowrap; overflow: hidden;
}
.sidebar.collapsed .nav-section-label { visibility: hidden; }

.nav-item {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 10px;
  color: var(--text-muted);
  border-radius: 5px; margin: 1px 0;
  transition: background 0.15s, color 0.15s;
  white-space: nowrap;
  position: relative;
}
.nav-item:hover:not(.disabled) {
  background: var(--surface-2);
  color: var(--text);
}
.nav-item.router-link-active:not(.disabled) {
  background: var(--surface-3);
  color: var(--accent-blue);
  border-left: 2px solid var(--accent-blue);
  padding-left: 8px;
}
.nav-item.disabled {
  opacity: 0.35;
  cursor: not-allowed;
  pointer-events: none;
}
.nav-icon { flex-shrink: 0; }
.nav-label { font-size: 13px; font-weight: 500; }
.sidebar.collapsed .nav-label { display: none; }
.sidebar.collapsed .brand-text { display: none; }
</style>
