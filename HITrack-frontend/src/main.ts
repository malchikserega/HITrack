import './assets/main.css'
import './assets/animations.css'

import { createApp } from 'vue'
import type { App as VueApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import vuetify from './plugins/vuetify'
import { notificationPlugin } from './plugins/notifications'
import datePlugin from './plugins/date'
import { formatDate } from './utils/dateUtils'

// Vuetify
import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'

const app: VueApp = createApp(App)

// Add global error handler
app.config.errorHandler = (err: unknown, vm: any, info: string) => {
  console.error('Vue Error:', err, info)
}

// Add global warning handler
app.config.warnHandler = (msg: string, vm: any, trace: string) => {
  console.warn('Vue Warning:', msg, trace)
}

// Add global properties
app.config.globalProperties.$notify = notificationPlugin
app.config.globalProperties.$formatDate = formatDate

// Use plugins
app.use(createPinia())
app.use(router)
app.use(vuetify)
app.use(notificationPlugin)
app.use(datePlugin)

app.mount('#app') 