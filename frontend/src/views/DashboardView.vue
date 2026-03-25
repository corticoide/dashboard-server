<template>
  <div class="dashboard">
    <!-- Error banner -->
    <div v-if="error" class="error-banner">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
      {{ error }}
    </div>

    <!-- Gauge row -->
    <div class="gauge-row">
      <MetricCard
        label="CPU"
        :value="metrics.cpu_percent"
        unit="%"
        color="auto"
        :subtitle="metrics.cpu_count ? `${metrics.cpu_count} cores · ${metrics.cpu_arch}` : ''"
      />
      <MetricCard
        label="MEMORY"
        :value="metrics.ram_percent"
        unit="%"
        color="auto"
        :subtitle="`${metrics.ram_used_gb} / ${metrics.ram_total_gb} GB`"
      />
      <MetricCard
        label="DISK"
        :value="metrics.disk_percent"
        unit="%"
        color="auto"
        :subtitle="`${metrics.disk_used_gb} / ${metrics.disk_total_gb} GB`"
      />
    </div>

    <!-- System info panel -->
    <div class="info-panel">
      <div class="info-header">
        <span class="info-title">SYSTEM</span>
        <span class="info-subtitle">{{ metrics.os_name }}</span>
      </div>
      <div class="info-grid">
        <div class="info-item">
          <div class="info-key">HOSTNAME</div>
          <div class="info-val">{{ metrics.hostname || '—' }}</div>
        </div>
        <div class="info-item">
          <div class="info-key">UPTIME</div>
          <div class="info-val uptime-val">{{ uptimeFormatted }}</div>
        </div>
        <div class="info-item">
          <div class="info-key">ARCH</div>
          <div class="info-val">{{ metrics.cpu_arch || '—' }}</div>
        </div>
        <div class="info-item">
          <div class="info-key">CPU CORES</div>
          <div class="info-val">{{ metrics.cpu_count ?? '—' }}</div>
        </div>
      </div>

      <!-- Load average -->
      <div class="load-row">
        <span class="load-label">LOAD AVG</span>
        <div class="load-values">
          <span class="load-item" :class="loadClass(metrics.load_average?.[0])">
            {{ metrics.load_average?.[0] ?? '—' }}
            <span class="load-period">1m</span>
          </span>
          <span class="load-sep">·</span>
          <span class="load-item" :class="loadClass(metrics.load_average?.[1])">
            {{ metrics.load_average?.[1] ?? '—' }}
            <span class="load-period">5m</span>
          </span>
          <span class="load-sep">·</span>
          <span class="load-item" :class="loadClass(metrics.load_average?.[2])">
            {{ metrics.load_average?.[2] ?? '—' }}
            <span class="load-period">15m</span>
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import MetricCard from '../components/dashboard/MetricCard.vue'
import { usePolling } from '../composables/usePolling.js'
import api from '../api/client.js'

const metrics = ref({
  cpu_percent: 0, ram_percent: 0, ram_used_gb: 0, ram_total_gb: 0,
  disk_percent: 0, disk_used_gb: 0, disk_total_gb: 0, uptime_seconds: 0,
  load_average: [0, 0, 0], os_name: '', hostname: '', cpu_count: 0, cpu_arch: '',
})
const error = ref('')

async function fetchMetrics() {
  try {
    const { data } = await api.get('/system/metrics')
    metrics.value = data
    error.value = ''
  } catch {
    error.value = 'Failed to fetch metrics'
  }
}

const { start, stop } = usePolling(fetchMetrics, 5000)
onMounted(start)
onUnmounted(stop)

const uptimeFormatted = computed(() => {
  const s = metrics.value.uptime_seconds
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (d > 0) return `${d}d ${h}h ${m}m`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
})

function loadClass(val) {
  if (val == null) return ''
  const cpuCount = metrics.value.cpu_count || 1
  const ratio = val / cpuCount
  if (ratio >= 0.85) return 'load-high'
  if (ratio >= 0.6) return 'load-mid'
  return 'load-ok'
}
</script>

<style scoped>
.dashboard { display: flex; flex-direction: column; gap: 16px; }

.error-banner {
  display: flex; align-items: center; gap: 8px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid var(--accent-red);
  color: var(--accent-red);
  padding: 10px 14px; border-radius: 6px;
  font-size: 13px;
}

/* Gauges */
.gauge-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}
@media (max-width: 600px) {
  .gauge-row { grid-template-columns: 1fr; }
}

/* Info panel */
.info-panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
}
.info-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
}
.info-title {
  font-family: var(--font-mono);
  font-size: 9px; letter-spacing: 2px;
  color: var(--text-muted);
}
.info-subtitle {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-dim);
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 14px;
}
@media (max-width: 700px) {
  .info-grid { grid-template-columns: 1fr 1fr; }
}
.info-item {}
.info-key {
  font-family: var(--font-mono);
  font-size: 8px; letter-spacing: 1.5px;
  color: var(--text-dim);
  margin-bottom: 4px;
}
.info-val {
  font-family: var(--font-mono);
  font-size: 13px; font-weight: 500;
  color: var(--text-bright);
}
.uptime-val { color: var(--accent-green); }

/* Load average */
.load-row {
  display: flex; align-items: center; gap: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}
.load-label {
  font-family: var(--font-mono);
  font-size: 8px; letter-spacing: 1.5px;
  color: var(--text-dim);
  white-space: nowrap;
}
.load-values {
  display: flex; align-items: baseline; gap: 6px;
}
.load-sep { color: var(--text-dim); }
.load-item {
  font-family: var(--font-mono);
  font-size: 13px; font-weight: 500;
  display: flex; align-items: baseline; gap: 2px;
}
.load-period {
  font-size: 9px; color: var(--text-dim);
}
.load-ok  { color: var(--accent-green); }
.load-mid { color: var(--accent-yellow); }
.load-high { color: var(--accent-red); }
</style>
