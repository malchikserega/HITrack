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
  </v-app>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from './stores/auth'
import { notificationService } from './plugins/notifications'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const isAuthenticated = computed(() => authStore.isAuthenticated)
const drawer = ref(false)

const menuItems = [
  { title: 'Home', path: '/' },
  { title: 'Repositories', path: '/repositories' },
  { title: 'Images', path: '/images' },
  { title: 'Components', path: '/components' },
  { title: 'Vulnerabilities', path: '/vulnerabilities' },
  { title: 'Azure Container Registry', path: '/acr' }
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

onMounted(async () => {
  // Check authentication status on app start
  const isAuth = await authStore.checkAuth()
  if (!isAuth && route.meta.requiresAuth) {
    router.push('/login')
  } else if (isAuth && route.path === '/login') {
    router.push('/')
  }
})
</script>

<style>
body {
  font-family: 'Roboto', sans-serif;
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
</style> 