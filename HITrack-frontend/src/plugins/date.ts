import type { App } from 'vue'

export default {
  install: (app: App) => {
    app.config.globalProperties.$formatDate = (date: string) => {
      if (!date) return ''
      return new Date(date).toLocaleString()
    }
  }
} 