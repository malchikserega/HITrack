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
    token: localStorage.getItem('token') || null,
    refreshToken: localStorage.getItem('refreshToken') || null,
    user: null
  }),

  getters: {
    isAuthenticated: (state) => !!state.token,
    currentUser: (state) => state.user
  },

  actions: {
    async login(username: string, password: string): Promise<{ success: boolean; error?: string }> {
      try {
        const response = await api.post<LoginResponse>('auth/token/', {
          username,
          password
        })

        const { access, refresh } = response.data
        
        this.token = access
        this.refreshToken = refresh
        this.user = {
          id: 0,
          username: username,
          email: ''
        }

        localStorage.setItem('token', access)
        localStorage.setItem('refreshToken', refresh)

        return { success: true }
      } catch (error) {
        const apiError = error as { response?: { data: ApiError } }
        const errorMessage = apiError.response?.data?.message || 'Authentication failed'
        return { success: false, error: errorMessage }
      }
    },

    async checkAuth(): Promise<boolean> {
      if (!this.token) {
        this.logout()
        return false
      }

      try {
        await api.post('auth/token/verify/', {
          token: this.token
        })
        return true
      } catch (error) {
        return this.refreshToken ? await this.refreshAuth() : false
      }
    },

    async refreshAuth(): Promise<boolean> {
      if (!this.refreshToken) {
        this.logout()
        return false
      }

      try {
        const response = await api.post<LoginResponse>('auth/token/refresh/', {
          refresh: this.refreshToken
        })

        const { access } = response.data
        
        this.token = access
        if (this.user) {
          this.user = { ...this.user }
        }

        localStorage.setItem('token', access)

        return true
      } catch (error) {
        this.logout()
        return false
      }
    },

    logout() {
      this.token = null
      this.refreshToken = null
      this.user = null
      localStorage.removeItem('token')
      localStorage.removeItem('refreshToken')
    }
  }
}) 