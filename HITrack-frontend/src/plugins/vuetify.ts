import 'vuetify/styles'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import '@mdi/font/css/materialdesignicons.css'

export default createVuetify({
  components,
  directives,
  theme: {
    defaultTheme: 'light',
    themes: {
      light: {
        colors: {
          background: '#FFFFFF',
          surface: '#FFFFFF',
          'surface-bright': '#FFFFFF',
          'surface-light': '#FFFFFF',
          'surface-variant': '#FFFFFF',
          primary: '#000000',      
          secondary: '#232526',
        }
      },
      dark: {
        dark: true,
        colors: {
          background: '#18191A',
          primary: '#FFFFFF',
          secondary: '#232526',
        }
      },
      matrix: {
        dark: true,
        colors: {
          background: '#000000',
          primary: '#39FF14',
          secondary: '#00FF41',
          surface: '#000000',
          error: '#39FF14',
          success: '#39FF14',
          warning: '#39FF14',
          info: '#39FF14',
        }
      }
    }
  }
}) 