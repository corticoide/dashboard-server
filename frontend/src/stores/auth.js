import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api/client.js'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('access_token'))
  const username = ref(localStorage.getItem('username') || null)
  const role = ref(localStorage.getItem('role') || null)

  const isAuthenticated = computed(() => !!token.value)

  async function login(usernameInput, password) {
    const { data } = await api.post('/auth/login', { username: usernameInput, password })
    token.value = data.access_token
    localStorage.setItem('access_token', data.access_token)
    const payload = JSON.parse(atob(data.access_token.split('.')[1]))
    username.value = payload.username
    role.value = payload.role
    localStorage.setItem('username', payload.username)
    localStorage.setItem('role', payload.role)
  }

  function logout() {
    token.value = null
    username.value = null
    role.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('username')
    localStorage.removeItem('role')
  }

  return { token, username, role, isAuthenticated, login, logout }
})
