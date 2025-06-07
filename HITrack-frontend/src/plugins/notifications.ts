import { ref } from 'vue'
import type { App } from 'vue'

interface SnackbarState {
  show: boolean
  message: string
  color: string
  timeout: number
  location: string
}

class NotificationService {
  private static instance: NotificationService
  private notifications = ref<SnackbarState[]>([])
  private nextId = 0

  private colorMap: Record<string, string> = {
    success: 'success',
    error: 'error',
    warning: 'warning',
    info: 'info'
  }

  private constructor() {}

  static getInstance(): NotificationService {
    if (!NotificationService.instance) {
      NotificationService.instance = new NotificationService()
    }
    return NotificationService.instance
  }

  show(message: string, type: string = 'success', timeout: number = 3000) {
    const id = this.nextId++
    this.notifications.value.push({
      show: true,
      message,
      color: this.colorMap[type] || 'success',
      timeout,
      location: 'top'
    })
    return id
  }

  success(message: string, timeout: number = 3000) {
    return this.show(message, 'success', timeout)
  }

  error(message: string, timeout: number = 3000) {
    return this.show(message, 'error', timeout)
  }

  warning(message: string, timeout: number = 3000) {
    return this.show(message, 'warning', timeout)
  }

  info(message: string, timeout: number = 3000) {
    return this.show(message, 'info', timeout)
  }

  getSnackbar() {
    return this.notifications
  }

  removeNotification(index: number) {
    this.notifications.value.splice(index, 1)
  }
}

const notificationService = NotificationService.getInstance()

export const notificationPlugin = {
  install: (app: App) => {
    app.config.globalProperties.$notify = notificationService
  }
}

export { notificationService } 