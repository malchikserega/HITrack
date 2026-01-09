import { defineStore } from 'pinia'

export type ThemeMode = 'normal' | 'matrix'

interface ThemeState {
  mode: ThemeMode
  isActive: boolean
}

export const useThemeStore = defineStore('theme', {
  state: (): ThemeState => ({
    mode: 'normal',
    isActive: false
  }),

  getters: {
    currentTheme: (state) => state.mode,
    isMatrix: (state) => state.mode === 'matrix' && state.isActive,
    isThemeActive: (state) => state.isActive
  },

  actions: {
    setTheme(mode: ThemeMode) {
      this.mode = mode
      this.isActive = mode !== 'normal'
      this.applyTheme()
    },

    applyTheme() {
      const body = document.body
      
      // Remove existing theme classes
      body.classList.remove('vice-city-theme')
      
      if (this.isActive) {
        body.classList.add(`${this.mode}-theme`)
      }
    }
  }
})
