import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from './auth.js'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../api/client.js', () => ({
  default: { post: vi.fn() }
}))

describe('auth store', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('starts unauthenticated', () => {
    const auth = useAuthStore()
    expect(auth.isAuthenticated).toBe(false)
    expect(auth.token).toBeNull()
  })

  it('sets token on successful login', async () => {
    const api = (await import('../api/client.js')).default
    // Create a real-looking JWT with payload {username: "admin", role: "admin"}
    const payload = btoa(JSON.stringify({ username: 'admin', role: 'admin' }))
    const fakeToken = `header.${payload}.sig`
    api.post.mockResolvedValue({ data: { access_token: fakeToken, token_type: 'bearer' } })
    const auth = useAuthStore()
    await auth.login('admin', 'pass')
    expect(auth.token).toBe(fakeToken)
    expect(auth.isAuthenticated).toBe(true)
    expect(auth.username).toBe('admin')
    expect(auth.role).toBe('admin')
  })

  it('clears token on logout', () => {
    const auth = useAuthStore()
    auth.token = 'tok123'
    auth.logout()
    expect(auth.token).toBeNull()
    expect(auth.isAuthenticated).toBe(false)
  })
})
