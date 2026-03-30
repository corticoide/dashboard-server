import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useDebounce } from '../useDebounce.js'

describe('useDebounce', () => {
  beforeEach(() => { vi.useFakeTimers() })
  afterEach(() => { vi.useRealTimers() })

  it('does not call fn before delay elapses', () => {
    const fn = vi.fn()
    const debounced = useDebounce(fn, 400)
    debounced()
    expect(fn).not.toHaveBeenCalled()
  })

  it('calls fn once after delay', () => {
    const fn = vi.fn()
    const debounced = useDebounce(fn, 400)
    debounced()
    vi.advanceTimersByTime(400)
    expect(fn).toHaveBeenCalledTimes(1)
  })

  it('collapses rapid calls into one', () => {
    const fn = vi.fn()
    const debounced = useDebounce(fn, 400)
    debounced()
    debounced()
    debounced()
    vi.advanceTimersByTime(400)
    expect(fn).toHaveBeenCalledTimes(1)
  })

  it('passes arguments through', () => {
    const fn = vi.fn()
    const debounced = useDebounce(fn, 100)
    debounced('hello', 42)
    vi.advanceTimersByTime(100)
    expect(fn).toHaveBeenCalledWith('hello', 42)
  })
})
