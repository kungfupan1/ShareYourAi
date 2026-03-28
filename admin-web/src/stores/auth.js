import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as loginApi, getCurrentUser, logout as logoutApi } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))

  const isLoggedIn = computed(() => !!token.value)

  async function login(credentials) {
    const res = await loginApi(credentials)
    token.value = res.access_token
    user.value = res.user
    localStorage.setItem('token', res.access_token)
    localStorage.setItem('user', JSON.stringify(res.user))
    return res
  }

  async function fetchUser() {
    if (!token.value) return null
    try {
      const res = await getCurrentUser()
      user.value = res
      localStorage.setItem('user', JSON.stringify(res))
      return res
    } catch {
      logout()
      return null
    }
  }

  async function logout() {
    try {
      await logoutApi()
    } catch {}
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  return {
    token,
    user,
    isLoggedIn,
    login,
    fetchUser,
    logout
  }
})