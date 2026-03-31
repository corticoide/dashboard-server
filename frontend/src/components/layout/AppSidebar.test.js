import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { describe, it, expect, beforeAll, beforeEach } from 'vitest'
import AppSidebar from './AppSidebar.vue'
import { useAuthStore } from '../../stores/auth.js'

const router = createRouter({
  history: createMemoryHistory(),
  routes: [{ path: '/', component: { template: '<div/>' } }]
})

describe('AppSidebar', () => {
  let pinia

  beforeAll(async () => { await router.push('/') })

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    const auth = useAuthStore()
    auth.role = 'admin'
  })

  function mountSidebar(props = {}) {
    return mount(AppSidebar, {
      props: { collapsed: false, ...props },
      global: { plugins: [router, pinia] }
    })
  }

  it('renders nav links', async () => {
    await router.isReady()
    const wrapper = mountSidebar()
    expect(wrapper.text()).toContain('Dashboard')
  })

  it('applies collapsed class when collapsed prop is true', async () => {
    await router.isReady()
    const wrapper = mountSidebar({ collapsed: true })
    expect(wrapper.classes()).toContain('collapsed')
  })

  it('emits toggle event when toggle button clicked', async () => {
    await router.isReady()
    const wrapper = mountSidebar()
    await wrapper.find('.toggle-btn').trigger('click')
    expect(wrapper.emitted('toggle')).toBeTruthy()
  })
})
