import { ComponentCustomProperties } from 'vue'
import { NotificationService } from './plugins/notifications'

declare module '@vue/runtime-core' {
  interface ComponentCustomProperties {
    $formatDate: (date: string) => string
    $notify: NotificationService
  }
} 