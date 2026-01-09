<template>
  <div class="login">
    <v-container>
      <v-row justify="center">
        <v-col cols="12" sm="8" md="6" lg="4">
          <!-- Main Logo Display -->
          <div class="text-center mb-8">
            <v-img
              src="/logo.png?v=1"
              alt="HITrack Logo"
              class="main-logo mx-auto mb-4"
              max-width="200"
              max-height="200"
              contain
            ></v-img>
            <h1 class="text-h2 font-weight-bold mb-2">HITrack</h1>
          </div>
          
          <v-card class="elevation-8 login-card">
            <v-card-title class="text-center pa-6">
            </v-card-title>
            <v-card-text class="pa-6">
              <v-form
                ref="form"
                v-model="isFormValid"
                @submit.prevent="handleLogin"
              >
                <v-text-field
                  v-model="username"
                  label="Username"
                  name="username"
                  prepend-icon="mdi-account"
                  type="text"
                  :rules="[rules.required]"
                  :error-messages="errors.username"
                  @input="clearError('username')"
                  required
                  variant="outlined"
                  class="mb-4"
                  color="primary"
                ></v-text-field>

                <v-text-field
                  v-model="password"
                  label="Password"
                  name="password"
                  prepend-icon="mdi-lock"
                  :type="showPassword ? 'text' : 'password'"
                  :append-icon="showPassword ? 'mdi-eye' : 'mdi-eye-off'"
                  @click:append="showPassword = !showPassword"
                  :rules="[rules.required]"
                  :error-messages="errors.password"
                  @input="clearError('password')"
                  required
                  variant="outlined"
                  class="mb-4"
                  color="primary"
                ></v-text-field>

                <v-alert
                  v-if="error"
                  type="error"
                  class="mt-4 mb-4"
                  closable
                  @click:close="error = ''"
                >
                  {{ error }}
                </v-alert>

                <v-btn
                  color="primary"
                  type="submit"
                  :loading="loading"
                  :disabled="!isFormValid || loading"
                  size="large"
                  block
                  class="mt-4"
                >
                  Sign In
                </v-btn>
              </v-form>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </v-container>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useThemeStore } from '../stores/theme'
import { notificationService } from '../plugins/notifications'

const router = useRouter()
const authStore = useAuthStore()
const themeStore = useThemeStore()
const form = ref<HTMLFormElement | null>(null)

const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)
const isFormValid = ref(false)
const showPassword = ref(false)

const errors = reactive({
  username: '',
  password: ''
})

const rules = {
  required: (v: string) => !!v || 'This field is required'
}

const clearError = (field: keyof typeof errors) => {
  errors[field] = ''
  error.value = ''
}

const validateForm = () => {
  if (!form.value) return false
  return form.value.validate()
}

const handleLogin = async () => {
  if (!validateForm()) return

  loading.value = true
  error.value = ''

  try {
    const { success, error: loginError } = await authStore.login(username.value, password.value)
    
    if (success) {
      notificationService.success('Successfully logged in')
      // Use replace instead of push to prevent returning to login page
      router.replace({ name: 'home' })
    } else {
      error.value = loginError || 'Invalid username or password'
      notificationService.error(loginError || 'Invalid username or password')
    }
  } catch (e) {
    console.error('Login error:', e)
    const errorMessage = 'An error occurred during login'
    error.value = errorMessage
    notificationService.error(errorMessage)
  } finally {
    loading.value = false
  }
}

// Watch for authentication state changes
watch(
  () => authStore.isAuthenticated,
  (isAuthenticated) => {
    if (isAuthenticated) {
      router.replace({ name: 'home' })
    }
  }
)

onMounted(async () => {
  // Check if user is already authenticated
  const isAuth = await authStore.checkAuth()
  if (isAuth) {
    router.push('/')
  }
})
</script>

<style scoped>
.login {
  min-height: 100vh;
  display: flex;
  align-items: center;
  padding: 20px 0;
  background: #ffffff;
}


.main-logo {
  background: transparent !important;
  border: none !important;
  filter: drop-shadow(0 0 20px rgba(0, 191, 255, 0.7)) drop-shadow(0 0 40px rgba(255, 20, 147, 0.5));
  transition: transform 0.2s ease;
  width: 200px !important;
  height: 200px !important;
}

.main-logo:hover {
  transform: scale(1.05);
  filter: drop-shadow(0 0 30px rgba(0, 191, 255, 0.9)) drop-shadow(0 0 60px rgba(255, 20, 147, 0.7));
}


@media (max-width: 600px) {
  .main-logo {
    max-width: 150px !important;
    max-height: 150px !important;
    width: 150px !important;
    height: 150px !important;
  }
  
  h1 {
    font-size: 2rem !important;
  }
  
  .login {
    padding: 10px 0;
  }
}
</style> 