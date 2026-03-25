export function usePolling(fn, intervalMs) {
  let timer = null

  function start() {
    fn()
    timer = setInterval(fn, intervalMs)
  }

  function stop() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  return { start, stop }
}
