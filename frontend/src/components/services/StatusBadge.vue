<template>
  <span class="badge" :class="stateClass">{{ state }}</span>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({ state: String })
const stateClass = computed(() => ({
  active: 'badge-active',
  inactive: 'badge-inactive',
  failed: 'badge-failed',
  activating: 'badge-activating',
  deactivating: 'badge-deactivating',
}[props.state] || 'badge-other'))
</script>

<style scoped>
.badge {
  display: inline-flex; align-items: center;
  padding: 2px 8px; border-radius: 4px;
  font-family: var(--font-mono); font-size: 10px;
  font-weight: 600; letter-spacing: 0.5px;
  text-transform: uppercase;
}
.badge-active     { background: rgba(34,197,94,0.12);  color: var(--accent-green);  border: 1px solid rgba(34,197,94,0.25); }
.badge-inactive   { background: rgba(74,96,128,0.15);  color: var(--text-muted);    border: 1px solid var(--border); }
.badge-failed     { background: rgba(239,68,68,0.12);  color: var(--accent-red);    border: 1px solid rgba(239,68,68,0.25); }
.badge-activating { background: rgba(14,165,233,0.12); color: var(--accent-blue);   border: 1px solid rgba(14,165,233,0.25); }
.badge-other      { background: var(--surface-2);      color: var(--text-muted);    border: 1px solid var(--border); }
</style>
