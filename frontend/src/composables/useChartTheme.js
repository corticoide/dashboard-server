import { ref, computed, onMounted, onUnmounted } from 'vue'

export function useChartTheme() {
  const isDark = ref(true)

  function syncTheme() {
    isDark.value = document.documentElement.dataset.theme !== 'light'
  }

  let observer = null

  onMounted(() => {
    syncTheme()
    observer = new MutationObserver(syncTheme)
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme'],
    })
  })

  onUnmounted(() => {
    observer?.disconnect()
    observer = null
  })

  const chartBg = computed(() => isDark.value ? '#0a0e14' : '#f8fafc')
  const chartBorder = computed(() => isDark.value ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.08)')
  const axisColor = computed(() => isDark.value ? '#64748b' : '#94a3b8')
  const gridColorWeak = computed(() => isDark.value ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.05)')
  const gridColorMid = computed(() => isDark.value ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.08)')
  const legendColor = computed(() => isDark.value ? '#94a3b8' : '#64748b')
  const tooltipBg = computed(() => isDark.value ? '#1e293b' : '#ffffff')
  const tooltipText = computed(() => isDark.value ? '#e2e8f0' : '#1e293b')
  const tooltipBorder = computed(() => isDark.value ? '#334155' : '#e2e8f0')

  // Container inline style — reactive, replaces hardcoded CSS
  const containerStyle = computed(() => ({
    background: chartBg.value,
    borderRadius: '8px',
    padding: '6px',
    border: `1px solid ${chartBorder.value}`,
    transition: 'background 0.2s, border-color 0.2s',
  }))

  // Base scale options builder — call inside computed so it's reactive
  function buildScales(opts = {}) {
    const { yMin, yMax, yCallback, xMaxTicks = 6 } = opts
    return {
      x: {
        ticks: { maxTicksLimit: xMaxTicks, color: axisColor.value, font: { size: 10, family: 'Fira Code' } },
        grid: { color: gridColorWeak.value },
      },
      y: {
        ...(yMin != null ? { min: yMin } : { beginAtZero: true }),
        ...(yMax != null ? { max: yMax } : {}),
        ticks: {
          ...(yCallback ? { callback: yCallback } : {}),
          color: axisColor.value,
          font: { size: 10, family: 'Fira Code' },
        },
        grid: { color: gridColorMid.value },
      },
    }
  }

  function buildTooltip(labelCb) {
    return {
      backgroundColor: tooltipBg.value,
      titleColor: tooltipText.value,
      bodyColor: tooltipText.value,
      borderColor: tooltipBorder.value,
      borderWidth: 1,
      padding: 10,
      cornerRadius: 6,
      titleFont: { family: 'Fira Code', size: 11 },
      bodyFont: { family: 'Fira Code', size: 11 },
      ...(labelCb ? { callbacks: { label: labelCb } } : {}),
    }
  }

  function buildLegend(show = true) {
    if (!show) return { display: false }
    return {
      display: true,
      position: 'top',
      labels: {
        color: legendColor.value,
        font: { family: 'Fira Code', size: 11 },
        boxWidth: 12,
        padding: 16,
        usePointStyle: true,
        pointStyle: 'line',
      },
    }
  }

  return {
    isDark,
    chartBg,
    chartBorder,
    axisColor,
    gridColorWeak,
    gridColorMid,
    legendColor,
    containerStyle,
    buildScales,
    buildTooltip,
    buildLegend,
  }
}
