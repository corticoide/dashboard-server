<template>
  <Card class="metric-card" :class="`accent-${resolvedColor}`">
    <template #title>
      <span class="card-label">{{ label }}</span>
    </template>
    <template #content>
      <!-- Arc gauge — custom SVG, no PrimeVue equivalent -->
      <div class="gauge-wrap">
        <svg class="gauge-svg" viewBox="0 0 100 56" xmlns="http://www.w3.org/2000/svg">
          <path class="gauge-track" d="M 8,50 A 42,42 0 0,1 92,50"
            fill="none" stroke-width="5" stroke-linecap="round"/>
          <path class="gauge-fill" d="M 8,50 A 42,42 0 0,1 92,50"
            fill="none" stroke-width="5" stroke-linecap="round"
            :style="{ strokeDasharray: ARC_LEN, strokeDashoffset: dashOffset, stroke: accentColor }"/>
        </svg>
        <div class="gauge-center">
          <span class="gauge-value">{{ displayValue }}</span>
          <span class="gauge-unit">{{ unit }}</span>
        </div>
      </div>

      <Tag v-if="subtitle" :value="subtitle" severity="secondary" class="subtitle-tag" />

      <ProgressBar
        :value="numValue"
        :show-value="false"
        class="metric-bar"
        :pt="{ value: { style: `background: ${accentColor}` } }"
      />
    </template>
  </Card>
</template>

<script setup>
import { computed } from 'vue'
import Card from 'primevue/card'
import Tag from 'primevue/tag'
import ProgressBar from 'primevue/progressbar'

const props = defineProps({
  label: String,
  value: Number,
  unit: { type: String, default: '%' },
  color: { type: String, default: 'auto' },
  subtitle: String,
})

const ARC_LEN = 131.95

const resolvedColor = computed(() => {
  if (props.color !== 'auto') return props.color
  if (props.value >= 85) return 'red'
  if (props.value >= 60) return 'yellow'
  return 'green'
})

const accentColor = computed(() => ({
  blue:   'var(--p-blue-500)',
  green:  'var(--p-green-500)',
  yellow: 'var(--p-yellow-500)',
  red:    'var(--p-red-500)',
}[resolvedColor.value] || 'var(--p-blue-500)'))

const numValue = computed(() => Math.min(Math.max(props.value ?? 0, 0), 100))
const dashOffset = computed(() => ARC_LEN * (1 - numValue.value / 100))
const displayValue = computed(() => typeof props.value === 'number' ? props.value.toFixed(0) : '—')
</script>

<style scoped>
.metric-card {
  border-top: 2px solid var(--p-surface-border);
  transition: border-top-color 0.3s;
}
.metric-card.accent-green  { border-top-color: var(--p-green-500); }
.metric-card.accent-yellow { border-top-color: var(--p-yellow-500); }
.metric-card.accent-red    { border-top-color: var(--p-red-500); }
.metric-card.accent-blue   { border-top-color: var(--p-blue-500); }

:deep(.p-card-body) {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  padding: 14px;
}
:deep(.p-card-title) { width: 100%; margin: 0; padding: 0; }
:deep(.p-card-content) {
  width: 100%; display: flex; flex-direction: column; align-items: center;
  gap: 8px; padding: 0;
}

.card-label {
  font-family: var(--font-mono);
  font-size: 9px; letter-spacing: 2px;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
}

/* Arc gauge */
.gauge-wrap {
  position: relative; width: 100%; max-width: 120px;
}
.gauge-svg { width: 100%; display: block; }
.gauge-track { stroke: var(--p-surface-400); }
.gauge-fill { transition: stroke-dashoffset 0.5s ease, stroke 0.3s ease; }

.gauge-center {
  position: absolute;
  bottom: 0; left: 50%; transform: translateX(-50%);
  display: flex; align-items: baseline; gap: 1px;
  pointer-events: none;
}
.gauge-value {
  font-family: var(--font-mono);
  font-size: 26px; font-weight: 600;
  color: var(--p-text-color);
  line-height: 1;
}
.gauge-unit {
  font-family: var(--font-mono);
  font-size: 11px; color: var(--p-text-muted-color);
}

.subtitle-tag { font-family: var(--font-mono); font-size: 10px; }

.metric-bar { width: 100%; height: 4px; }
:deep(.metric-bar .p-progressbar-track) { background: var(--p-surface-300); height: 4px; border-radius: 2px; }
:deep(.metric-bar .p-progressbar-value) { height: 4px; border-radius: 2px; transition: width 0.5s ease, background 0.3s; }
</style>
