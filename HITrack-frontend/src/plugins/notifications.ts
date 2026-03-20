import { ref } from 'vue'
import type { App } from 'vue'

export type NotificationType = 'success' | 'error' | 'warning' | 'info'

export interface NotificationOptions {
  title?: string
  timeout?: number
  location?: string
  icon?: string
  dedupeKey?: string
}

export interface SnackbarState {
  id: number
  show: boolean
  type: NotificationType
  title: string
  message: string
  color: string
  timeout: number
  location: string
  icon: string
  dedupeKey: string
}

export class NotificationService {
  private static instance: NotificationService
  private notifications = ref<SnackbarState[]>([])
  private nextId = 0
  private removalTimers = new Map<number, ReturnType<typeof setTimeout>>()
  private readonly maxVisibleNotifications = 4

  private colorMap: Record<NotificationType, string> = {
    success: 'success',
    error: 'error',
    warning: 'warning',
    info: 'info',
  }

  private defaultTimeouts: Record<NotificationType, number> = {
    success: 2800,
    info: 3400,
    warning: 4200,
    error: 5200,
  }

  private defaultTitles: Record<NotificationType, string> = {
    success: 'Success',
    error: 'Action Failed',
    warning: 'Attention Needed',
    info: 'Update',
  }

  private defaultIcons: Record<NotificationType, string> = {
    success: 'mdi-check-circle-outline',
    error: 'mdi-alert-circle-outline',
    warning: 'mdi-alert-outline',
    info: 'mdi-information-outline',
  }

  private constructor() {}

  static getInstance(): NotificationService {
    if (!NotificationService.instance) {
      NotificationService.instance = new NotificationService()
    }
    return NotificationService.instance
  }

  private scheduleRemoval(id: number, timeout: number) {
    const existingTimer = this.removalTimers.get(id)
    if (existingTimer) {
      clearTimeout(existingTimer)
    }

    if (timeout <= 0) {
      return
    }

    const timer = setTimeout(() => {
      this.removeNotification(id)
    }, timeout + 300)
    this.removalTimers.set(id, timer)
  }

  show(
    message: string,
    type: NotificationType = 'success',
    timeout?: number,
    options: NotificationOptions = {},
  ) {
    const trimmedMessage = message.trim()
    const resolvedTimeout = timeout ?? options.timeout ?? this.defaultTimeouts[type]
    const dedupeKey = options.dedupeKey ?? `${type}:${trimmedMessage}`
    const existingNotification = this.notifications.value.find(
      (notification) => notification.dedupeKey === dedupeKey,
    )

    if (existingNotification) {
      existingNotification.show = true
      existingNotification.type = type
      existingNotification.title = options.title ?? this.defaultTitles[type]
      existingNotification.message = trimmedMessage
      existingNotification.color = this.colorMap[type]
      existingNotification.timeout = resolvedTimeout
      existingNotification.location = options.location ?? 'top end'
      existingNotification.icon = options.icon ?? this.defaultIcons[type]
      this.scheduleRemoval(existingNotification.id, resolvedTimeout)
      return existingNotification.id
    }

    const id = this.nextId++
    if (this.notifications.value.length >= this.maxVisibleNotifications) {
      this.removeNotification(this.notifications.value[0].id)
    }

    this.notifications.value.push({
      id,
      show: true,
      type,
      title: options.title ?? this.defaultTitles[type],
      message: trimmedMessage,
      color: this.colorMap[type],
      timeout: resolvedTimeout,
      location: options.location ?? 'top end',
      icon: options.icon ?? this.defaultIcons[type],
      dedupeKey,
    })

    this.scheduleRemoval(id, resolvedTimeout)
    return id
  }

  success(message: string, timeout?: number, options: NotificationOptions = {}) {
    return this.show(message, 'success', timeout, options)
  }

  error(message: string, timeout?: number, options: NotificationOptions = {}) {
    return this.show(message, 'error', timeout, options)
  }

  warning(message: string, timeout?: number, options: NotificationOptions = {}) {
    return this.show(message, 'warning', timeout, options)
  }

  info(message: string, timeout?: number, options: NotificationOptions = {}) {
    return this.show(message, 'info', timeout, options)
  }

  queued(message: string, timeout = 3400, options: NotificationOptions = {}) {
    return this.info(message, timeout, {
      title: 'Queued',
      icon: 'mdi-timer-sand',
      ...options,
    })
  }

  started(message: string, timeout = 3400, options: NotificationOptions = {}) {
    return this.info(message, timeout, {
      title: 'Started',
      icon: 'mdi-progress-clock',
      ...options,
    })
  }

  conflict(message: string, timeout = 4200, options: NotificationOptions = {}) {
    return this.warning(message, timeout, {
      title: 'Already Running',
      icon: 'mdi-clock-alert-outline',
      ...options,
    })
  }

  completed(message: string, timeout = 2800, options: NotificationOptions = {}) {
    return this.success(message, timeout, {
      title: 'Done',
      icon: 'mdi-check-circle-outline',
      ...options,
    })
  }

  copied(message = 'Copied to clipboard', timeout = 1800, options: NotificationOptions = {}) {
    return this.success(message, timeout, {
      title: 'Copied',
      icon: 'mdi-content-copy',
      dedupeKey: 'copied',
      ...options,
    })
  }

  getSnackbar() {
    return this.notifications
  }

  removeNotification(id: number) {
    const timer = this.removalTimers.get(id)
    if (timer) {
      clearTimeout(timer)
      this.removalTimers.delete(id)
    }

    const index = this.notifications.value.findIndex(
      (notification) => notification.id === id,
    )
    if (index !== -1) {
      this.notifications.value.splice(index, 1)
    }
  }

  clearAll() {
    for (const timer of this.removalTimers.values()) {
      clearTimeout(timer)
    }
    this.removalTimers.clear()
    this.notifications.value = []
  }
}

const notificationService = NotificationService.getInstance()

export const notificationPlugin = {
  install: (app: App) => {
    app.config.globalProperties.$notify = notificationService
  },
}

export { notificationService }
