import { defineStore } from 'pinia'
import api from '../plugins/axios'

interface AuthState {
  token: string | null
  refreshToken: string | null
  user: User | null
}

interface User {
  id: number
  username: string
  email: string
  groups: string[]
  can_write: boolean
  is_admin: boolean
}

interface LoginResponse {
  access: string
  refresh: string
}

interface ApiError {
  message: string
  code?: string
  details?: Record<string, string[]>
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    token: sessionStorage.getItem('token') || null,
    refreshToken: null,
    user: null
  }),

  getters: {
    isAuthenticated: (state) => !!state.token,
    currentUser: (state) => state.user,
    canWrite: (state) => Boolean(state.user?.can_write),
    isAdmin: (state) => Boolean(state.user?.is_admin)
  },

  actions: {
    async login(username: string, password: string): Promise<{ success: boolean; error?: string }> {
      try {
        const response = await api.post<LoginResponse>('auth/token/', {
          username,
          password
        })

        const { access } = response.data
        
        this.token = access
        sessionStorage.setItem('token', access)
        // Update axios default headers
        api.defaults.headers.common['Authorization'] = `Bearer ${access}`
        await this.loadCurrentUser()

        return { success: true }
      } catch (error) {
        this.clearSession()
        const apiError = error as { response?: { data: ApiError } }
        const errorMessage = apiError.response?.data?.message
          || (apiError.response?.data as { detail?: string } | undefined)?.detail
          || 'Authentication failed'
        return { success: false, error: errorMessage }
      }
    },

    async checkAuth(): Promise<boolean> {
      if (!this.token) return this.refreshAuth()

      try {
        await api.post('auth/token/verify/', {
          token: this.token
        })
        if (!this.user) await this.loadCurrentUser()
        return true
      } catch (error) {
        return await this.refreshAuth()
      }
    },

    async refreshAuth(): Promise<boolean> {
      try {
        const response = await api.post<LoginResponse>('auth/token/refresh/')

        const { access } = response.data
        
        this.token = access
        sessionStorage.setItem('token', access)
        if (this.user) {
          this.user = { ...this.user }
        }

        
        // Update axios default headers
        api.defaults.headers.common['Authorization'] = `Bearer ${access}`
        await this.loadCurrentUser()

        return true
      } catch (error) {
        this.clearSession()
        return false
      }
    },

    async loadCurrentUser() {
      const response = await api.get<User>('auth/me/')
      this.user = response.data
    },

    clearSession() {
      this.token = null
      this.refreshToken = null
      this.user = null
      sessionStorage.removeItem('token')
      
      // Clear axios default headers
      delete api.defaults.headers.common['Authorization']
    },

    async logout() {
      try {
        await api.post('auth/logout/')
      } finally {
        this.clearSession()
      }
    }
  }
})
