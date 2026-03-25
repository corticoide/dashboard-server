<template>
  <div class="metric-card" :class="`accent-${resolvedColor}`">
    <div class="card-label">{{ label }}</div>
    <!-- Arc gauge -->
    <div class="gauge-wrap">
      <svg class="gauge-svg" viewBox="0 0 100 56" xmlns="http://www.w3.org/2000/svg">
        <!-- Track -->
        <path class="gauge-track" d="M 8,50 A 42,42 0 0,1 92,50"
          fill="none" stroke-width="5" stroke-linecap="round"/>
        <!-- Fill -->
        <path class="gauge-fill bar-fill" d="M 8,50 A 42,42 0 0,1 92,50"
          fill="none" stroke-width="5" stroke-linecap="round"
          :style="{ strokeDasharray: ARC_LEN, strokeDashoffset: dashOffset, stroke: accentColor }"/>
      </svg>
      <div class="gauge-center">
        <span class="gauge-value">{{ displayValue }}</span>
        <span class="gauge-unit">{{ unit }}</span>
      </div>
    </div>
    <div v-if="subtitle" class="card-subtitle">{{ subtitle }}</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  label: String,
  value: Number,
  unit: { type: String, default: '%' },
  color: { type: String, default: 'auto' },
  subtitle: String,
})

// Arc length for path "M 8,50 A 42,42 0 0,1 92,50" (semicircle r=42) ≈ π*42
const ARC_LEN = 131.95

const resolvedColor = computed(() => {
  if (props.color !== 'auto') return props.color
  if (props.value >= 85) return 'red'
  if (props.value >= 60) return 'yellow'
  return 'green'
})

const accentColor = computed(() => ({
  blue:   'var(--accent-blue)',
  green:  'var(--accent-green)',
  yellow: 'var(--accent-yellow)',
  red:    'var(--accent-red)',
}[resolvedColor.value] || 'var(--accent-blue)'))

const dashOffset = computed(() => ARC_LEN * (1 - Math.min(Math.max(props.value, 0), 100) / 100))
const displayValue = computed(() => typeof props.value === 'number' ? props.value.toFixed(0) : '—')
</script>

<style scoped>
.metric-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-top: 2px solid var(--border-bright);
  border-radius: 8px;
  padding: 16px 16px 12px;
  display: flex; flex-direction: column; align-items: center;
  gap: 4px;
  transition: border-top-color 0.3s;
}
.metric-card.accent-blue  { border-top-color: var(--accent-blue); }
.metric-card.accent-green { border-top-color: var(--accent-green); }
.metric-card.accent-yellow{ border-top-color: var(--accent-yellow); }
.metric-card.accent-red   { border-top-color: var(--accent-red); }

.card-label {
  font-family: var(--font-mono);
  font-size: 9px; letter-spacing: 2px;
  color: var(--text-muted);
  text-transform: uppercase;
  align-self: flex-start;
}

/* Arc gauge */
.gauge-wrap {
  position: relative; width: 100%; max-width: 120px;
}
.gauge-svg { width: 100%; display: block; }
.gauge-track { stroke: var(--surface-3); }
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
  color: var(--text-bright);
  line-height: 1;
}
.gauge-unit {
  font-family: var(--font-mono);
  font-size: 11px; color: var(--text-muted);
}

.card-subtitle {
  font-size: 11px;
  font-family: var(--font-mono);
  color: var(--text-muted);
  letter-spacing: 0.5px;
}
</style>
