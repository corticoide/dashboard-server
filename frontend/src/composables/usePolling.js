export function usePolling(fn, intervalMs) {
  let timer = null
  let active = false

  function tick() {
    if (!document.hidden) fn()
  }

  function onVisibilityChange() {
    if (!active) return
    if (!document.hidden) fn()
  }

  function start() {
    active = true
    fn()
    timer = setInterval(tick, intervalMs)
    document.addEventListener('visibilitychange', onVisibilityChange)
  }

  function stop() {
    active = false
    if (timer) {
      clearInterval(timer)
      timer = null
    }
    document.removeEventListener('visibilitychange', onVisibilityChange)
  }

  return { start, stop }
}
