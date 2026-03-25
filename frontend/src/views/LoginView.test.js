import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import LoginView from './LoginView.vue'

const mockLogin = vi.fn()
vi.mock('../stores/auth.js', () => ({
  useAuthStore: () => ({ login: mockLogin, isAuthenticated: false })
}))

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginView },
    { path: '/', component: { template: '<div>home</div>' } }
  ]
})

describe('LoginView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockLogin.mockReset()
  })

  it('renders username and password fields', async () => {
    const wrapper = mount(LoginView, { global: { plugins: [router] } })
    expect(wrapper.find('input[type="text"]').exists()).toBe(true)
    expect(wrapper.find('input[type="password"]').exists()).toBe(true)
  })

  it('calls login with form values on submit', async () => {
    mockLogin.mockResolvedValue(undefined)
    const wrapper = mount(LoginView, { global: { plugins: [router] } })
    await wrapper.find('input[type="text"]').setValue('admin')
    await wrapper.find('input[type="password"]').setValue('pass')
    await wrapper.find('form').trigger('submit')
    expect(mockLogin).toHaveBeenCalledWith('admin', 'pass')
  })

  it('shows error message on login failure', async () => {
    mockLogin.mockRejectedValue(new Error('Invalid credentials'))
    const wrapper = mount(LoginView, { global: { plugins: [router] } })
    await wrapper.find('form').trigger('submit')
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Invalid credentials')
  })
})
