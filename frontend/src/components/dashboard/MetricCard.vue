<template>
  <div class="metric-card">
    <div class="metric-label">{{ label }}</div>
    <div class="metric-value">{{ value }}<span class="unit">{{ unit }}</span></div>
    <div class="bar-track">
      <div class="bar-fill" :style="{ width: `${value}%`, background: colorVar }"></div>
    </div>
    <div v-if="subtitle" class="metric-subtitle">{{ subtitle }}</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({
  label: String,
  value: Number,
  unit: { type: String, default: '%' },
  color: { type: String, default: 'blue' },
  subtitle: String,
})
const colorVar = computed(() => ({
  blue: 'var(--accent-blue)',
  green: 'var(--accent-green)',
  yellow: 'var(--accent-yellow)',
  red: 'var(--accent-red)',
}[props.color] || 'var(--accent-blue)'))
</script>

<style scoped>
.metric-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; padding: 20px;
}
.metric-label { font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }
.metric-value { font-size: 32px; font-weight: 700; margin-bottom: 12px; }
.unit { font-size: 16px; color: var(--text-muted); margin-left: 2px; }
.bar-track { height: 6px; background: var(--surface-2); border-radius: 3px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 3px; transition: width 0.4s ease; }
.metric-subtitle { font-size: 12px; color: var(--text-muted); margin-top: 8px; }
</style>
