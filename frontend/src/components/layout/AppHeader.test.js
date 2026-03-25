import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import AppHeader from './AppHeader.vue'

vi.mock('../../stores/auth.js', () => ({
  useAuthStore: () => ({ username: 'admin', role: 'admin', logout: vi.fn() })
}))

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/', component: { template: '<div/>' } },
    { path: '/login', component: { template: '<div/>' } }
  ]
})

describe('AppHeader', () => {
  beforeAll(async () => { await router.push('/') })
  beforeEach(() => setActivePinia(createPinia()))

  it('displays the username', async () => {
    await router.isReady()
    const wrapper = mount(AppHeader, { props: { pageTitle: 'Dashboard' }, global: { plugins: [router] } })
    expect(wrapper.text()).toContain('admin')
  })

  it('displays the page title', async () => {
    await router.isReady()
    const wrapper = mount(AppHeader, { props: { pageTitle: 'System Overview' }, global: { plugins: [router] } })
    expect(wrapper.text()).toContain('System Overview')
  })
})
