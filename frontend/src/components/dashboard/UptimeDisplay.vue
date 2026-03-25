<template>
  <div class="metric-card">
    <div class="metric-label">Uptime</div>
    <div class="metric-value uptime-value">{{ formatted }}</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({ seconds: Number })
const formatted = computed(() => {
  const s = props.seconds || 0
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  return [d && `${d}d`, h && `${h}h`, `${m}m`].filter(Boolean).join(' ') || '0m'
})
</script>

<style scoped>
.metric-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; padding: 20px;
}
.metric-label { font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }
.uptime-value { font-size: 28px; font-weight: 700; }
</style>
