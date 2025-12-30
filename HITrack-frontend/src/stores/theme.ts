import { defineStore } from 'pinia'

export type ThemeMode = 'normal' | 'retrowave' | 'matrix'

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
    isRetrowave: (state) => state.mode === 'retrowave' && state.isActive,
    isMatrix: (state) => state.mode === 'matrix' && state.isActive,
    isThemeActive: (state) => state.isActive
  },

  actions: {
    toggleTheme() {
      if (!this.isActive) {
        this.mode = 'retrowave'
        this.isActive = true
      } else if (this.mode === 'retrowave') {
        this.mode = 'normal'
        this.isActive = false
      }
      
      this.applyTheme()
    },

    setTheme(mode: ThemeMode) {
      this.mode = mode
      this.isActive = mode !== 'normal'
      this.applyTheme()
    },

    applyTheme() {
      const body = document.body
      
      // Remove existing theme classes
      body.classList.remove('retrowave-theme', 'vice-city-theme')
      
      if (this.isActive) {
        body.classList.add(`${this.mode}-theme`)
      }
    },

    initKeyboardListener() {
      let keySequence = ''
      const targetSequence = 'retro'
      
      const handleKeyPress = (event: KeyboardEvent) => {
        // Only activate on dashboard page (home route)
        const currentPath = window.location.pathname
        if (currentPath !== '/' && currentPath !== '/home') {
          return
        }
        
        keySequence += event.key.toLowerCase()
        
        // Keep only the last 5 characters to prevent memory issues
        if (keySequence.length > 5) {
          keySequence = keySequence.slice(-5)
        }
        
        if (keySequence.includes(targetSequence)) {
          this.toggleTheme()
          keySequence = '' // Reset sequence
        }
      }
      
      document.addEventListener('keydown', handleKeyPress)
      
      // Return cleanup function
      return () => {
        document.removeEventListener('keydown', handleKeyPress)
      }
    }
  }
})
