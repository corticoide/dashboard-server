<template>
  <Card class="uptime-card">
    <template #title>
      <div class="uptime-header">
        <i class="pi pi-clock" style="color: var(--p-text-muted-color); font-size: 13px;" />
        <span class="uptime-label">Uptime</span>
      </div>
    </template>
    <template #content>
      <span class="uptime-value">{{ formatted }}</span>
    </template>
  </Card>
</template>

<script setup>
import { computed } from 'vue'
import Card from 'primevue/card'

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
.uptime-header {
  display: flex; align-items: center; gap: 6px;
}
.uptime-label {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--p-text-muted-color);
}
.uptime-value {
  font-size: 28px;
  font-weight: 700;
  font-family: var(--font-mono);
}
</style>
