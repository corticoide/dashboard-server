import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import PrimeVue from 'primevue/config'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import LoginView from './LoginView.vue'

const mockLogin = vi.fn()
vi.mock('../stores/auth.js', () => ({
  useAuthStore: () => ({ login: mockLogin, isAuthenticated: false })
}))

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/login', component: LoginView },
    { path: '/', component: { template: '<div>home</div>' } }
  ]
})

function mountLogin() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(LoginView, {
    global: { plugins: [router, pinia, [PrimeVue, { theme: 'none' }]] }
  })
}

describe('LoginView', () => {
  beforeEach(() => {
    mockLogin.mockReset()
  })

  it('renders username and password fields', async () => {
    const wrapper = mountLogin()
    expect(wrapper.find('input[type="text"]').exists()).toBe(true)
    expect(wrapper.find('input[type="password"]').exists()).toBe(true)
  })

  it('calls login with form values on submit', async () => {
    mockLogin.mockResolvedValue(undefined)
    const wrapper = mountLogin()
    await wrapper.find('input[type="text"]').setValue('admin')
    await wrapper.find('input[type="password"]').setValue('pass')
    await wrapper.find('form').trigger('submit')
    expect(mockLogin).toHaveBeenCalledWith('admin', 'pass')
  })

  it('shows error message on login failure', async () => {
    mockLogin.mockRejectedValue(new Error('Invalid credentials'))
    const wrapper = mountLogin()
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('Invalid credentials')
  })
})
