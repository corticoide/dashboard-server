import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import api from '../api/client.js'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('access_token'))
  const username = ref(localStorage.getItem('username') || null)
  const role = ref(localStorage.getItem('role') || null)
  const permissions = ref([])

  const isAuthenticated = computed(() => !!token.value)
  const isAdmin = computed(() => role.value === 'admin')

  function hasPermission(resource, action) {
    if (role.value === 'admin') return true
    return permissions.value.some(p => p.resource === resource && p.action === action)
  }

  async function fetchMe() {
    try {
      const { data } = await api.get('/auth/me')
      username.value = data.username
      role.value = data.role
      permissions.value = data.permissions
      localStorage.setItem('username', data.username)
      localStorage.setItem('role', data.role)
    } catch {
      /* token may be invalid */
    }
  }

  async function login(usernameInput, password) {
    const { data } = await api.post('/auth/login', { username: usernameInput, password })
    token.value = data.access_token
    localStorage.setItem('access_token', data.access_token)
    const payload = JSON.parse(atob(data.access_token.split('.')[1]))
    username.value = payload.username
    role.value = payload.role
    localStorage.setItem('username', payload.username)
    localStorage.setItem('role', payload.role)
    await fetchMe()
  }

  function logout() {
    token.value = null
    username.value = null
    role.value = null
    permissions.value = []
    localStorage.removeItem('access_token')
    localStorage.removeItem('username')
    localStorage.removeItem('role')
  }

  return { token, username, role, permissions, isAuthenticated, isAdmin, hasPermission, login, logout, fetchMe }
})
