<template>
  <v-app>
    <v-navigation-drawer v-model="drawer" app class="drawer-accent bg-secondary">
      <v-list>
        <v-list-item v-for="item in menuItems" :key="item.path" link>
          <router-link :to="item.path" style="text-decoration: none; color: inherit; width: 100%; display: block;">
            <v-list-item-title>{{ item.title }}</v-list-item-title>
          </router-link>
        </v-list-item>
      </v-list>
    </v-navigation-drawer>

    <v-app-bar app color="primary" dark>
      <v-app-bar-nav-icon @click="drawer = !drawer" />
      <router-link to="/" style="text-decoration: none;">
        <v-app-bar-title class="logo-text">
          <span class="hi">HI</span><span class="track">Track</span>
        </v-app-bar-title>
      </router-link>
      <v-spacer></v-spacer>
      <v-btn v-if="isMatrix" icon @click="toggleMatrix" class="mr-2">
        <v-icon>{{ isMatrix ? 'mdi-alpha-m' : 'mdi-alpha-m' }}</v-icon>
      </v-btn>
      <v-btn v-if="isMatrix" icon @click="toggleMatrixAnimation" class="mr-2">
        <v-icon>{{ matrixAnimation ? 'mdi-animation' : 'mdi-animation-outline' }}</v-icon>
      </v-btn>
      <template v-if="isAuthenticated">
        <v-btn @click="handleLogout" text>
          Logout
        </v-btn>
      </template>
      <v-btn v-else :to="{ path: '/login' }" text>
        Login
      </v-btn>
    </v-app-bar>

    <v-main>
      <router-view></router-view>
    </v-main>

    <!-- Global notification snackbars -->
    <div class="notification-container">
      <v-snackbar
        v-for="(notification, index) in notifications"
        :key="index"
        v-model="notification.show"
        :color="notification.color"
        :timeout="notification.timeout"
        :location="(notification.location as any)"
        class="notification-snackbar"
        :style="{ bottom: `${index * 60}px` }"
      >
        {{ notification.message }}
        <template v-slot:actions>
          <v-btn
            color="white"
            variant="text"
            @click="removeNotification(index)"
          >
            Close
          </v-btn>
        </template>
      </v-snackbar>
    </div>

    <div ref="matrixBgRef" class="matrix-bg" :style="{ display: isMatrix && matrixAnimation ? 'block' : 'none' }">
      <canvas ref="matrixCanvasRef" id="matrix-canvas" style="width:100vw;height:100vh;display:block;"></canvas>
    </div>

  </v-app>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, onUnmounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from './stores/auth'
import { useThemeStore } from './stores/theme'
import { notificationService } from './plugins/notifications'
import api from './plugins/axios'
import { useTheme } from 'vuetify'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const themeStore = useThemeStore()

const isAuthenticated = computed(() => authStore.isAuthenticated)
const drawer = ref(false)

const theme = useTheme()

// Matrix mode
const isMatrix = computed(() => theme.global.name.value === 'matrix')
function toggleMatrix() {
  theme.global.name.value = isMatrix.value ? 'light' : 'matrix'
}

// Matrix animation
const matrixAnimation = ref(false)
function toggleMatrixAnimation() {
  matrixAnimation.value = !matrixAnimation.value
}

const matrixBgRef = ref<HTMLElement | null>(null)
const matrixCanvasRef = ref<HTMLCanvasElement | null>(null)
let animationFrameId: number | null = null
let ctx: CanvasRenderingContext2D | null = null
let columns: number[] = []
let fontSize = 18
let drops: number[] = []
const matrixChars = 'アァカサタナハマヤャラワガザダバパイィキシチニヒミリヰギジヂビピウゥクスツヌフムユュルグズヅブプエェケセテネヘメレヱゲゼデベペオォコソトノホモヨョロヲゴゾドボポヴッンABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'.split('')

function startMatrixRain() {
  const canvas = matrixCanvasRef.value
  if (!canvas) return
  ctx = canvas.getContext('2d')
  if (!ctx) return
  canvas.width = window.innerWidth
  canvas.height = window.innerHeight
  fontSize = 18
  const columnsCount = Math.floor(canvas.width / fontSize)
  drops = Array(columnsCount).fill(1)
  columns = Array.from({ length: columnsCount }, (_, i) => i)
  function draw() {
    if (!ctx || !canvas) return
    ctx.fillStyle = 'rgba(0, 0, 0, 0.15)'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.font = `${fontSize}px 'Share Tech Mono', monospace`
    ctx.fillStyle = '#39FF14'
    columns.forEach((col, i) => {
      const text = matrixChars[Math.floor(Math.random() * matrixChars.length)]
      ctx?.fillText(text, col * fontSize, drops[i] * fontSize)
      if (drops[i] * fontSize > canvas.height && Math.random() > 0.975) {
        drops[i] = 0
      }
      drops[i]++
    })
    animationFrameId = requestAnimationFrame(draw)
  }
  draw()
}

function stopMatrixRain() {
  if (animationFrameId) {
    cancelAnimationFrame(animationFrameId)
    animationFrameId = null
  }
  const canvas = matrixCanvasRef.value
  if (ctx && canvas) {
    ctx.clearRect(0, 0, canvas.width, canvas.height)
  }
}

function handleResize() {
  if (matrixCanvasRef.value && isMatrix.value && matrixAnimation.value) {
    stopMatrixRain()
    startMatrixRain()
  }
}

onMounted(async () => {
  // Initialize theme system
  themeStore.applyTheme()
  
  watch([isMatrix, matrixAnimation], async ([matrix, anim]) => {
    await nextTick()
    if (matrix && anim) {
      startMatrixRain()
      window.addEventListener('resize', handleResize)
    } else {
      stopMatrixRain()
      window.removeEventListener('resize', handleResize)
    }
  }, { immediate: true })
  
  // Initialize authentication
  if (authStore.token) {
    api.defaults.headers.common['Authorization'] = `Bearer ${authStore.token}`
  }
  
  // Check authentication status on app start
  const isAuth = await authStore.checkAuth()
  if (!isAuth && route.meta.requiresAuth) {
    router.push('/login')
  } else if (isAuth && route.path === '/login') {
    router.push('/')
  }
})

onUnmounted(() => {
  stopMatrixRain()
  window.removeEventListener('resize', handleResize)
})

const menuItems = [
  { title: 'Home', path: '/' },
  { title: 'Repositories', path: '/repositories' },
  { title: 'Images', path: '/images' },
  { title: 'Components', path: '/components' },
  { title: 'Vulnerabilities', path: '/vulnerabilities' },
  { title: 'Releases', path: '/releases' },
  { title: 'Task Management', path: '/tasks' },
  { title: 'Container Registries', path: '/acr' },
  { title: 'Report Generator', path: '/reports' },
  { title: 'Component Matrix', path: '/component-matrix' }
]

const notifications = ref<Array<{
  show: boolean;
  message: string;
  color: string;
  timeout: number;
  location: string;
}>>([])

// Watch for changes in notification service
watch(
  () => notificationService.getSnackbar(),
  (newValue) => {
    notifications.value = newValue.value
  },
  { deep: true }
)

const removeNotification = (index: number) => {
  notificationService.removeNotification(index)
}

const handleLogout = async () => {
  authStore.logout()
  notificationService.success('Successfully logged out')
  router.push('/login')
}

// Watch for authentication changes
watch(isAuthenticated, (newValue) => {
  if (newValue && route.path === '/login') {
    router.push('/')
  }
})

</script>

<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
@import './assets/themes.css';
body {
  font-family: 'Roboto', sans-serif;
  background-color: #ffffff !important;
}

/* Ensure white background for main theme */
.v-application {
  background-color: #ffffff !important;
}

.v-main {
  background-color: #ffffff !important;
}

.v-main__wrap {
  background-color: #ffffff !important;
}

/* Override any other background colors for main theme */
.v-application:not(.v-theme--matrix) {
  background-color: #ffffff !important;
}

.v-application:not(.v-theme--matrix) .v-main {
  background-color: #ffffff !important;
}

.v-application:not(.v-theme--matrix) .v-main__wrap {
  background-color: #ffffff !important;
}

/* Fix tooltips and overlays for main theme - more specific selectors */
.v-application:not(.v-theme--matrix) .v-tooltip .v-overlay__content,
.v-application:not(.v-theme--matrix) .v-tooltip__content,
.v-application:not(.v-theme--matrix) .v-overlay__content[data-v-tooltip],
.v-application:not(.v-theme--matrix) .v-tooltip .v-overlay__content .v-tooltip__content {
  background: #333333 !important;
  color: #ffffff !important;
  border: 1px solid #666666 !important;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3) !important;
}

.v-application:not(.v-theme--matrix) .v-menu .v-overlay__content {
  background: #ffffff !important;
  color: #000000 !important;
  border: 1px solid #e0e0e0 !important;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15) !important;
}

.v-application:not(.v-theme--matrix) .v-dialog .v-card {
  background: #ffffff !important;
  color: #000000 !important;
}

.v-application:not(.v-theme--matrix) .v-snackbar .v-snackbar__wrapper {
  background: #333333 !important;
  color: #ffffff !important;
}

/* Global tooltip fix - highest priority */
.v-tooltip .v-overlay__content,
.v-tooltip__content,
.v-overlay__content[data-v-tooltip] {
  background: #333333 !important;
  color: #ffffff !important;
  border: 1px solid #666666 !important;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3) !important;
}

/* Ensure all overlay elements are visible in main theme */
.v-application:not(.v-theme--matrix) .v-overlay__content:not(.v-tooltip .v-overlay__content) {
  background: #ffffff !important;
  color: #000000 !important;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15) !important;
}
.v-theme--matrix, .v-theme--matrix body {
  font-family: 'Share Tech Mono', monospace !important;
  color: #39FF14 !important;
}
.v-theme--matrix .v-main,
.v-theme--matrix .v-main__wrap,
.v-theme--matrix .v-application__wrap,
.v-theme--matrix .router-view {
  background: #000000 !important;
}

/* Matrix theme - ensure page containers have black background but keep normal element colors */
.v-theme--matrix .home,
.v-theme--matrix .images,
.v-theme--matrix .repositories,
.v-theme--matrix .vulnerabilities,
.v-theme--matrix .components,
.v-theme--matrix .task-management,
.v-theme--matrix .component-detail,
.v-theme--matrix .component-version-detail,
.v-theme--matrix .component-locations,
.v-theme--matrix .image-detail,
.v-theme--matrix .vulnerability-detail-container,
.v-theme--matrix .component-matrix-view,
.v-theme--matrix .releases-page,
.v-theme--matrix .report-generator,
.v-theme--matrix .not-found {
  background: #000000 !important;
}
.matrix-bg {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  z-index: 10;
  pointer-events: none;
  background: transparent;
}

.drawer-accent {
  color: #fff !important;
}

.notification-container {
  position: fixed;
  bottom: 0;
  right: 0;
  z-index: 1000;
}

.notification-snackbar {
  margin-bottom: 8px;
}

.logo-text {
  font-size: 3rem;
  font-weight: 900;
  letter-spacing: 0.5px;
}

.logo-text .hi {
  color: #ffffff;
  font-weight: 900;
}

.logo-text .track {
  color: #4CAF50;
  font-weight: 900;
}

.v-theme--matrix .v-navigation-drawer {
  background: #010 !important;
}
.v-theme--matrix .v-list-item-title,
.v-theme--matrix .v-list-item {
  color: #39FF14 !important;
  font-family: 'Share Tech Mono', monospace !important;
}
.v-theme--matrix .v-list-item--active,
.v-theme--matrix .v-list-item--active .v-list-item-title {
  color: #000 !important;
  background: #39FF14 !important;
  font-weight: bold;
}

.v-theme--matrix .matrix-table {
  background: #000 !important;
  color: #39FF14 !important;
  border-color: #39FF14 !important;
}
.v-theme--matrix .matrix-table th,
.v-theme--matrix .matrix-table td {
  background: #000 !important;
  color: #39FF14 !important;
  border: 1px solid #39FF14 !important;
}
.v-theme--matrix .matrix-table th {
  font-weight: bold;
}
.v-theme--matrix .v-chip,
.v-theme--matrix .v-chip .v-icon {
  background: #003300 !important;
  color: #39FF14 !important;
  border: none !important;
}
.v-theme--matrix .cell-up-to-date {
  background: #003300 !important;
}
.v-theme--matrix .cell-outdated {
  background: #330000 !important;
}

.v-theme--matrix .v-app-bar {
  background: #000 !important;
  color: #39FF14 !important;
  border-bottom: 2px solid #39FF14 !important;
}
.v-theme--matrix .v-app-bar .v-btn,
.v-theme--matrix .v-app-bar .v-icon,
.v-theme--matrix .v-app-bar .logo-text,
.v-theme--matrix .v-app-bar .logo-text .hi,
.v-theme--matrix .v-app-bar .logo-text .track {
  color: #39FF14 !important;
  font-family: 'Share Tech Mono', monospace !important;
}
.v-theme--matrix .v-app-bar .v-btn {
  background: transparent !important;
  box-shadow: none !important;
}

/* Matrix theme - only page backgrounds should be black, keep normal element colors */

/* Matrix theme - fix tooltips and overlays */
.v-theme--matrix .v-tooltip .v-overlay__content {
  background: #000000 !important;
  color: #39FF14 !important;
  border: 1px solid #39FF14 !important;
}

.v-theme--matrix .v-menu .v-overlay__content {
  background: #000000 !important;
  color: #39FF14 !important;
  border: 1px solid #39FF14 !important;
}

.v-theme--matrix .v-dialog .v-card {
  background: #000000 !important;
  color: #39FF14 !important;
  border: 1px solid #39FF14 !important;
}

.v-theme--matrix .v-snackbar .v-snackbar__wrapper {
  background: #000000 !important;
  color: #39FF14 !important;
  border: 1px solid #39FF14 !important;
}

.v-theme--matrix .v-tooltip__content {
  background: #000000 !important;
  color: #39FF14 !important;
  border: 1px solid #39FF14 !important;
}

/* Matrix theme - ensure all overlay elements are visible */
.v-theme--matrix .v-overlay__content {
  background: #000000 !important;
  color: #39FF14 !important;
  border: 1px solid #39FF14 !important;
}

/* Matrix theme - fix specific Vuetify components */
.v-theme--matrix .v-card {
  background: #000000 !important;
  color: #39FF14 !important;
  border: 1px solid #39FF14 !important;
}

.v-theme--matrix .v-sheet {
  background: #000000 !important;
  color: #39FF14 !important;
  border: 1px solid #39FF14 !important;
}

.v-theme--matrix .v-table {
  background: #000000 !important;
  color: #39FF14 !important;
  border: 1px solid #39FF14 !important;
}

.v-theme--matrix .v-table th,
.v-theme--matrix .v-table td {
  background: #000000 !important;
  color: #39FF14 !important;
  border: 1px solid #39FF14 !important;
}

.v-theme--matrix .v-table th {
  background: #001100 !important;
  color: #39FF14 !important;
  font-weight: bold !important;
  text-transform: uppercase !important;
  letter-spacing: 1px !important;
}

.v-theme--matrix .v-table tbody tr:hover {
  background: #001100 !important;
  color: #39FF14 !important;
}

.v-theme--matrix .v-table tbody tr:nth-child(even) {
  background: #000800 !important;
}

.v-theme--matrix .v-table tbody tr:nth-child(odd) {
  background: #000000 !important;
}

.v-theme--matrix .v-btn {
  background: #000000 !important;
  color: #39FF14 !important;
  border: 1px solid #39FF14 !important;
}

.v-theme--matrix .v-btn:hover {
  background: #001100 !important;
  color: #39FF14 !important;
  box-shadow: 0 0 10px rgba(57, 255, 20, 0.5) !important;
}

.v-theme--matrix .v-text-field .v-field {
  background: #000000 !important;
  color: #39FF14 !important;
  border: 1px solid #39FF14 !important;
}

.v-theme--matrix .v-text-field input {
  color: #39FF14 !important;
}

.v-theme--matrix .v-text-field .v-field__outline {
  color: #39FF14 !important;
}

.v-theme--matrix .v-list-item {
  background: #000000 !important;
  color: #39FF14 !important;
  border: 1px solid #39FF14 !important;
}

.v-theme--matrix .v-list-item:hover {
  background: #001100 !important;
  color: #39FF14 !important;
}

.v-theme--matrix .v-list-item-title {
  color: #39FF14 !important;
}

.v-theme--matrix .v-list-item-subtitle {
  color: #00FF41 !important;
}

.v-theme--matrix h1,
.v-theme--matrix h2,
.v-theme--matrix h3,
.v-theme--matrix h4,
.v-theme--matrix h5,
.v-theme--matrix h6 {
  color: #39FF14 !important;
}

.v-theme--matrix p,
.v-theme--matrix span,
.v-theme--matrix div {
  color: #39FF14 !important;
}

/* Matrix theme - specific table styling */
.v-theme--matrix .v-data-table {
  background: #000000 !important;
  color: #39FF14 !important;
  border: 1px solid #39FF14 !important;
}

.v-theme--matrix .v-data-table .v-data-table__wrapper {
  background: #000000 !important;
}

.v-theme--matrix .v-data-table .v-data-table__wrapper table {
  background: #000000 !important;
  color: #39FF14 !important;
  border: 1px solid #39FF14 !important;
}

.v-theme--matrix .v-data-table .v-data-table__wrapper table th {
  background: #001100 !important;
  color: #39FF14 !important;
  border: 1px solid #39FF14 !important;
  font-weight: bold !important;
  text-transform: uppercase !important;
  letter-spacing: 1px !important;
}

.v-theme--matrix .v-data-table .v-data-table__wrapper table td {
  background: #000000 !important;
  color: #39FF14 !important;
  border: 1px solid #39FF14 !important;
}

.v-theme--matrix .v-data-table .v-data-table__wrapper table tbody tr:hover {
  background: #001100 !important;
  color: #39FF14 !important;
}

.v-theme--matrix .v-data-table .v-data-table__wrapper table tbody tr:nth-child(even) {
  background: #000800 !important;
}

.v-theme--matrix .v-data-table .v-data-table__wrapper table tbody tr:nth-child(odd) {
  background: #000000 !important;
}

</style> 