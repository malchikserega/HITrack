<template>
  <div class="login">
    <v-container>
      <v-row justify="center">
        <v-col cols="12" sm="8" md="6" lg="4">
          <v-card class="elevation-12">
            <v-toolbar color="primary" dark flat>
              <v-toolbar-title>Login</v-toolbar-title>
            </v-toolbar>
            <v-card-text>
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
                ></v-text-field>

                <v-alert
                  v-if="error"
                  type="error"
                  class="mt-3"
                  closable
                  @click:close="error = ''"
                >
                  {{ error }}
                </v-alert>

                <v-card-actions>
                  <v-spacer></v-spacer>
                  <v-btn
                    color="primary"
                    type="submit"
                    :loading="loading"
                    :disabled="!isFormValid || loading"
                  >
                    Login
                  </v-btn>
                </v-card-actions>
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
import { notificationService } from '../plugins/notifications'

const router = useRouter()
const authStore = useAuthStore()
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
    console.log('Attempting login...')
    const { success, error: loginError } = await authStore.login(username.value, password.value)
    console.log('Login response:', { success, loginError })
    
    if (success) {
      console.log('Login successful')
      notificationService.success('Successfully logged in')
      // Use replace instead of push to prevent returning to login page
      router.replace({ name: 'Home' })
      console.log('Redirect completed')
    } else {
      console.log('Login failed:', loginError)
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
      router.replace({ name: 'Home' })
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
  height: 100vh;
  display: flex;
  align-items: center;
  background-color: #f5f5f5;
}
</style> 