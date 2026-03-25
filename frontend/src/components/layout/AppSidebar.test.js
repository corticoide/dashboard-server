import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { describe, it, expect, beforeAll } from 'vitest'
import AppSidebar from './AppSidebar.vue'

const router = createRouter({
  history: createMemoryHistory(),
  routes: [{ path: '/', component: { template: '<div/>' } }]
})

describe('AppSidebar', () => {
  beforeAll(async () => { await router.push('/') })

  it('renders nav links', async () => {
    await router.isReady()
    const wrapper = mount(AppSidebar, { props: { collapsed: false }, global: { plugins: [router] } })
    expect(wrapper.text()).toContain('Dashboard')
  })

  it('applies collapsed class when collapsed prop is true', async () => {
    await router.isReady()
    const wrapper = mount(AppSidebar, { props: { collapsed: true }, global: { plugins: [router] } })
    expect(wrapper.classes()).toContain('collapsed')
  })

  it('emits toggle event when toggle button clicked', async () => {
    await router.isReady()
    const wrapper = mount(AppSidebar, { props: { collapsed: false }, global: { plugins: [router] } })
    await wrapper.find('.toggle-btn').trigger('click')
    expect(wrapper.emitted('toggle')).toBeTruthy()
  })
})
