<template>
  <div class="dashboard">
    <p v-if="error" class="error-banner">{{ error }}</p>
    <div class="metrics-grid">
      <MetricCard label="CPU" :value="metrics.cpu_percent" unit="%" color="blue" />
      <MetricCard
        label="RAM"
        :value="metrics.ram_percent"
        unit="%"
        color="green"
        :subtitle="`${metrics.ram_used_gb} / ${metrics.ram_total_gb} GB`"
      />
      <MetricCard
        label="Disk"
        :value="metrics.disk_percent"
        unit="%"
        color="yellow"
        :subtitle="`${metrics.disk_used_gb} / ${metrics.disk_total_gb} GB`"
      />
      <UptimeDisplay :seconds="metrics.uptime_seconds" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import MetricCard from '../components/dashboard/MetricCard.vue'
import UptimeDisplay from '../components/dashboard/UptimeDisplay.vue'
import { usePolling } from '../composables/usePolling.js'
import api from '../api/client.js'

const metrics = ref({
  cpu_percent: 0, ram_percent: 0, ram_used_gb: 0, ram_total_gb: 0,
  disk_percent: 0, disk_used_gb: 0, disk_total_gb: 0, uptime_seconds: 0
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
</script>

<style scoped>
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}
.error-banner {
  background: var(--accent-red); color: #fff;
  padding: 10px 16px; border-radius: 6px; margin-bottom: 16px;
}
</style>
