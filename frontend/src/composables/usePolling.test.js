import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { usePolling } from './usePolling.js'

describe('usePolling', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('calls fn immediately on start', () => {
    const fn = vi.fn().mockResolvedValue(undefined)
    const { start, stop } = usePolling(fn, 5000)
    start()
    expect(fn).toHaveBeenCalledTimes(1)
    stop()
  })

  it('calls fn again after interval', () => {
    const fn = vi.fn().mockResolvedValue(undefined)
    const { start, stop } = usePolling(fn, 5000)
    start()
    vi.advanceTimersByTime(5000)
    expect(fn).toHaveBeenCalledTimes(2)
    stop()
  })

  it('stops calling fn after stop()', () => {
    const fn = vi.fn().mockResolvedValue(undefined)
    const { start, stop } = usePolling(fn, 5000)
    start()
    stop()
    vi.advanceTimersByTime(10000)
    expect(fn).toHaveBeenCalledTimes(1)
  })
})
