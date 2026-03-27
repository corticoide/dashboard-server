<template>
  <Card class="metric-card" :class="`accent-${resolvedColor}`">
    <template #content>
      <span class="card-label">{{ label }}</span>

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
/* Card root: accent left border */
.metric-card {
  border-left: 3px solid var(--p-surface-border) !important;
  transition: border-left-color 0.3s;
}
.metric-card.accent-green  { border-left-color: var(--p-green-500) !important; }
.metric-card.accent-yellow { border-left-color: var(--p-yellow-500) !important; }
.metric-card.accent-red    { border-left-color: var(--p-red-500) !important; }
.metric-card.accent-blue   { border-left-color: var(--p-blue-500) !important; }

/* Card content layout */
:deep(.metric-card .p-card-body) { padding: 0; }
:deep(.metric-card .p-card-content) {
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.card-label {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 2px;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
  width: 100%;
}

/* Arc gauge */
.gauge-wrap {
  position: relative; width: 100%; max-width: 120px;
}
.gauge-svg { width: 100%; display: block; }
.gauge-track { stroke: var(--p-surface-border); opacity: 0.6; }
.gauge-fill { transition: stroke-dashoffset 0.5s ease, stroke 0.3s ease; }

.gauge-center {
  position: absolute;
  bottom: 0; left: 50%; transform: translateX(-50%);
  display: flex; align-items: baseline; gap: 1px;
  pointer-events: none;
}
.gauge-value {
  font-family: var(--font-mono);
  font-size: var(--text-2xl);
  font-weight: 600;
  color: var(--p-text-color);
  line-height: 1;
}
.gauge-unit {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--p-text-muted-color);
}

.subtitle-tag { font-family: var(--font-mono); font-size: var(--text-2xs); }

.metric-bar { width: 100%; height: 4px; }
:deep(.metric-bar .p-progressbar-track) { background: var(--p-surface-border); height: 4px; border-radius: 2px; }
:deep(.metric-bar .p-progressbar-value) { height: 4px; border-radius: 2px; transition: width 0.5s ease, background 0.3s; }
</style>
