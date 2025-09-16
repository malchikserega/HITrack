<template>
  <v-card class="chart-card" elevation="2">
    <v-card-title class="text-h6 font-weight-bold pa-4 pb-2 d-flex align-center justify-space-between">
      Recent Tasks
      <v-btn
        icon
        small
        @click="refreshTasks"
        :loading="loading"
      >
        <v-icon>mdi-refresh</v-icon>
      </v-btn>
    </v-card-title>
    <v-card-text class="pa-4 pt-0">
      <div v-if="loading" class="text-center pa-8">
        <v-progress-circular indeterminate color="primary"></v-progress-circular>
        <p class="text-body-2 text-medium-emphasis mt-2">Loading tasks...</p>
      </div>
      <div v-else-if="!tasks || tasks.length === 0" class="text-center pa-8">
        <v-icon size="48" color="grey">mdi-clock-outline</v-icon>
        <p class="text-body-2 text-medium-emphasis mt-2">No recent tasks found</p>
      </div>
      <v-list v-else class="task-list">
        <v-list-item
          v-for="task in tasks"
          :key="task.task_id"
          class="task-item clickable"
          @click="viewTaskDetails(task)"
        >
          <template #prepend>
            <v-avatar :color="getStatusColor(task.status)" size="32">
              <v-icon color="white" size="16">
                {{ getStatusIcon(task.status) }}
              </v-icon>
            </v-avatar>
          </template>
          
          <v-list-item-title class="task-title">
            {{ task.task_name }}
          </v-list-item-title>
          
          <v-list-item-subtitle class="task-subtitle">
            {{ formatDate(task.created) }}
            <span v-if="task.duration" class="ml-2">
              • {{ formatDuration(task.duration) }}
            </span>
          </v-list-item-subtitle>
          
          <template #append>
            <v-chip
              :color="getStatusColor(task.status)"
              size="small"
              variant="tonal"
            >
              {{ task.status }}
            </v-chip>
          </template>
        </v-list-item>
      </v-list>
      
      <div class="text-center mt-4">
        <v-btn
          color="primary"
          variant="text"
          @click="viewAllTasks"
        >
          View All Tasks
        </v-btn>
      </div>
    </v-card-text>
  </v-card>
</template>

<script lang="ts">
import { defineComponent, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/plugins/axios'
import type { TaskResultList } from '@/types/interfaces'
import { formatDate, formatDuration } from '@/utils/dateUtils'

export default defineComponent({
  name: 'RecentTasksCard',
  setup() {
    const router = useRouter()
    const loading = ref(false)
    const tasks = ref<TaskResultList[]>([])

    const loadTasks = async () => {
      loading.value = true
      try {
        const response = await api.get('/tasks/', {
          params: {
            page_size: 5,
            ordering: '-created'
          }
        })
        tasks.value = response.data.results
      } catch (error) {
        console.error('Error loading tasks:', error)
      } finally {
        loading.value = false
      }
    }

    const getStatusColor = (status: string) => {
      switch (status) {
        case 'success':
          return 'success'
        case 'error':
          return 'error'
        case 'pending':
          return 'warning'
        case 'in_process':
          return 'info'
        default:
          return 'grey'
      }
    }

    const getStatusIcon = (status: string) => {
      switch (status) {
        case 'success':
          return 'mdi-check'
        case 'error':
          return 'mdi-alert'
        case 'pending':
          return 'mdi-clock'
        case 'in_process':
          return 'mdi-sync'
        default:
          return 'mdi-help'
      }
    }

    const viewTaskDetails = (task: TaskResultList) => {
      router.push(`/tasks?task_id=${task.task_id}`)
    }

    const viewAllTasks = () => {
      router.push('/tasks')
    }

    const refreshTasks = () => {
      loadTasks()
    }

    onMounted(() => {
      loadTasks()
    })

    return {
      loading,
      tasks,
      getStatusColor,
      getStatusIcon,
      viewTaskDetails,
      viewAllTasks,
      refreshTasks,
      formatDate,
      formatDuration
    }
  }
})
</script>

<style scoped>
.task-list {
  max-height: 400px;
  overflow-y: auto;
}

.task-item {
  border-radius: 8px;
  margin-bottom: 8px;
  transition: all 0.2s ease;
}

.task-item:hover {
  background-color: rgba(0, 0, 0, 0.04);
}

.task-title {
  font-weight: 600;
  font-size: 0.9rem;
}

.task-subtitle {
  font-size: 0.8rem;
  color: rgba(0, 0, 0, 0.6);
}

.clickable {
  cursor: pointer;
}
</style> 