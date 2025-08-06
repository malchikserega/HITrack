<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <div class="d-flex align-center justify-space-between mb-4">
          <h1 class="text-h4">Task Management</h1>
          <div>
            <v-btn
              color="success"
              prepend-icon="mdi-play"
              @click="runTestTask"
              :loading="testTaskLoading"
              class="mr-2"
            >
              Run Test Task
            </v-btn>
            <v-btn
              color="error"
              prepend-icon="mdi-alert"
              @click="runFailingTask"
              :loading="failingTaskLoading"
              class="mr-2"
            >
              Run Failing Task
            </v-btn>
            <v-btn
              color="info"
              prepend-icon="mdi-test-tube"
              @click="testEndpoint"
              :loading="testEndpointLoading"
            >
              Test Endpoint
            </v-btn>
            <v-btn
              color="warning"
              prepend-icon="mdi-bug"
              @click="testDirectAPI"
              class="ml-2"
            >
              Test Direct API
            </v-btn>
          </div>
        </div>
      </v-col>
    </v-row>

    <!-- Statistics Cards -->
    <v-row>
      <v-col cols="12" md="3">
        <v-card>
          <v-card-text>
            <div class="text-h6">Total Tasks</div>
            <div class="text-h4">{{ statistics.total_tasks }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card color="success">
          <v-card-text>
            <div class="text-h6">Successful</div>
            <div class="text-h4">{{ statistics.successful_tasks }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card color="error">
          <v-card-text>
            <div class="text-h6">Failed</div>
            <div class="text-h4">{{ statistics.failed_tasks }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card color="warning">
          <v-card-text>
            <div class="text-h6">Running</div>
            <div class="text-h4">{{ statistics.running_tasks }}</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Task List -->
    <v-row>
      <v-col cols="12">
        <v-card>
          <v-card-title>
            Recent Tasks
            <v-spacer></v-spacer>
            <v-text-field
              v-model="search"
              append-icon="mdi-magnify"
              label="Search"
              single-line
              hide-details
              style="max-width: 300px"
            ></v-text-field>
          </v-card-title>
          <v-card-text>
            <v-data-table
              :headers="headers"
              :items="tasks"
              :loading="loading"
              :options.sync="options"
              :server-items-length="totalTasks"
              :items-per-page="options.itemsPerPage"
              :page.sync="options.page"
              class="elevation-1"
            >
              <template v-slot:item.status="{ item }">
                <v-chip
                  :color="getStatusColor(item.status)"
                  text-color="white"
                  small
                >
                  {{ item.status }}
                </v-chip>
              </template>
              <template v-slot:item.duration="{ item }">
                <span v-if="item.duration">
                  {{ formatDuration(item.duration) }}
                </span>
                <span v-else>-</span>
              </template>
              <template v-slot:item.result_summary="{ item }">
                <div v-if="item.result_summary">
                  <div v-if="typeof item.result_summary === 'object'">
                    <div v-if="item.result_summary.message" class="text-caption">
                      {{ item.result_summary.message }}
                    </div>
                    <div v-if="item.result_summary.status" class="text-caption text--secondary">
                      Status: {{ item.result_summary.status }}
                    </div>
                  </div>
                  <div v-else class="text-caption">
                    {{ item.result_summary }}
                  </div>
                </div>
                <span v-else class="text-caption text--disabled">No result</span>
              </template>
              <template v-slot:item.created="{ item }">
                {{ formatDate(item.created) }}
              </template>
              <template v-slot:item.actions="{ item }">
                <v-btn
                  icon
                  small
                  @click="viewTaskDetails(item)"
                >
                  <v-icon>mdi-eye</v-icon>
                </v-btn>
                <v-btn
                  v-if="item.status === 'error'"
                  icon
                  small
                  color="warning"
                  @click="retryTask(item)"
                >
                  <v-icon>mdi-refresh</v-icon>
                </v-btn>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Task Details Dialog -->
    <v-dialog v-model="taskDetailsDialog" max-width="800px">
      <v-card>
        <v-card-title>
          Task Details
          <v-spacer></v-spacer>
          <v-btn icon @click="taskDetailsDialog = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>
        <v-card-text>
          <v-row v-if="selectedTask">
            <v-col cols="6">
              <strong>Task ID:</strong> {{ selectedTask.task_id }}
            </v-col>
            <v-col cols="6">
              <strong>Status:</strong>
              <v-chip
                :color="getStatusColor(selectedTask.status)"
                text-color="white"
                small
              >
                {{ selectedTask.status }}
              </v-chip>
            </v-col>
                         <v-col cols="6">
               <strong>Created:</strong> {{ formatDate(selectedTask.created) }}
             </v-col>
             <v-col cols="6">
               <strong>Updated:</strong> {{ selectedTask.updated ? formatDate(selectedTask.updated) : '-' }}
             </v-col>
            <v-col cols="6" v-if="selectedTask.duration">
              <strong>Duration:</strong> {{ formatDuration(selectedTask.duration) }}
            </v-col>
            <v-col cols="12" v-if="selectedTask.result_summary">
              <strong>Result Summary:</strong>
              <pre>{{ JSON.stringify(selectedTask.result_summary, null, 2) }}</pre>
            </v-col>
            <v-col cols="12" v-if="selectedTask.traceback">
              <strong>Traceback:</strong>
              <pre class="error-text">{{ selectedTask.traceback }}</pre>
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>
    </v-dialog>

    <!-- Periodic Tasks -->
    <v-row>
      <v-col cols="12">
        <v-card>
          <v-card-title>
            Periodic Tasks
          </v-card-title>
          <v-card-text>
            <v-data-table
              :headers="periodicHeaders"
              :items="periodicTasks"
              :loading="periodicLoading"
            >
              <template v-slot:item.enabled="{ item }">
                <v-switch
                  v-model="item.enabled"
                  @change="togglePeriodicTask(item)"
                ></v-switch>
              </template>
              <template v-slot:item.schedule_info="{ item }">
                <div v-if="item.schedule_info">
                  <div v-if="item.schedule_info.type === 'interval'">
                    Every {{ item.schedule_info.every }} {{ item.schedule_info.period }}
                  </div>
                  <div v-else-if="item.schedule_info.type === 'crontab'">
                    {{ formatCrontab(item.schedule_info) }}
                  </div>
                </div>
              </template>
                             <template v-slot:item.next_run="{ item }">
                 {{ item.next_run ? formatDate(item.next_run) : '-' }}
               </template>
              <template v-slot:item.actions="{ item }">
                <v-btn
                  icon
                  small
                  @click="runPeriodicTask(item)"
                >
                  <v-icon>mdi-play</v-icon>
                </v-btn>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script lang="ts">
import { defineComponent, ref, onMounted, reactive, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/plugins/axios'
import type { TaskResult, TaskStatistics, PeriodicTask } from '@/types/interfaces'
import { formatDate, formatDuration } from '@/utils/dateUtils'

export default defineComponent({
  name: 'TaskManagementView',
  setup() {
    const router = useRouter()
    const loading = ref(false)
    const periodicLoading = ref(false)
    const testTaskLoading = ref(false)
    const failingTaskLoading = ref(false)
    const testEndpointLoading = ref(false)
    const tasks = ref<TaskResult[]>([])
    const periodicTasks = ref<PeriodicTask[]>([])
    const statistics = reactive<TaskStatistics>({
      total_tasks: 0,
      successful_tasks: 0,
      failed_tasks: 0,
      pending_tasks: 0,
      running_tasks: 0,
      average_duration: 0,
      recent_tasks: []
    })
    const search = ref('')
    const taskDetailsDialog = ref(false)
    const selectedTask = ref<TaskResult | null>(null)
    const options = ref({
      page: 1,
      itemsPerPage: 10,
      sortBy: ['created'],
      sortDesc: [true]
    })
    const totalTasks = ref(0)

    const headers = [
      { text: 'Task ID', value: 'task_id' },
      { text: 'Task Name', value: 'task_name' },
      { text: 'Status', value: 'status' },
      { text: 'Result', value: 'result_summary' },
      { text: 'Duration', value: 'duration' },
      { text: 'Created', value: 'created' },
      { text: 'Actions', value: 'actions', sortable: false }
    ]

    const periodicHeaders = [
      { text: 'Name', value: 'name' },
      { text: 'Task', value: 'task' },
      { text: 'Enabled', value: 'enabled' },
      { text: 'Schedule', value: 'schedule_info' },
      { text: 'Next Run', value: 'next_run' },
      { text: 'Last Run', value: 'last_run_at' },
      { text: 'Run Count', value: 'total_run_count' },
      { text: 'Actions', value: 'actions', sortable: false }
    ]

    const loadStatistics = async () => {
      try {
        const response = await api.get('/tasks/statistics/')
        Object.assign(statistics, response.data)
      } catch (error) {
        console.error('Error loading statistics:', error)
      }
    }

    const loadTasks = async () => {
      loading.value = true
      try {
        const params: any = {
          page_size: options.value.itemsPerPage || 10,
          page: options.value.page || 1
        }
        
        // Add search parameter if provided
        if (search.value) {
          params.search = search.value
        }
        
        // Add sorting parameters
        if (options.value.sortBy && options.value.sortBy.length > 0) {
          params.ordering = options.value.sortDesc && options.value.sortDesc[0] 
            ? `-${options.value.sortBy[0]}` 
            : options.value.sortBy[0]
        }
        
        const response = await api.get('/tasks/', { params })
        tasks.value = response.data.results
        totalTasks.value = response.data.count
      } catch (error) {
        console.error('Error loading tasks:', error)
      } finally {
        loading.value = false
      }
    }

    const loadPeriodicTasks = async () => {
      periodicLoading.value = true
      try {
        const response = await api.get('/periodic-tasks/')
        periodicTasks.value = response.data.results
      } catch (error) {
        console.error('Error loading periodic tasks:', error)
      } finally {
        periodicLoading.value = false
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

    const viewTaskDetails = (task: TaskResult) => {
      selectedTask.value = task
      taskDetailsDialog.value = true
    }

    const retryTask = async (task: TaskResult) => {
      try {
        await api.post('/tasks/retry_task/', {
          task_id: task.task_id
        })
        // Reload tasks after retry
        await loadTasks()
        await loadStatistics()
      } catch (error) {
        console.error('Error retrying task:', error)
      }
    }

    const togglePeriodicTask = async (task: PeriodicTask) => {
      try {
        await api.post(`/periodic-tasks/${task.id}/toggle_enabled/`)
        // Reload periodic tasks
        await loadPeriodicTasks()
      } catch (error) {
        console.error('Error toggling periodic task:', error)
      } finally {
        task.enabled = !task.enabled
      }
    }

    const runPeriodicTask = async (task: PeriodicTask) => {
      try {
        await api.post(`/periodic-tasks/${task.id}/run_now/`)
        // Reload periodic tasks
        await loadPeriodicTasks()
      } catch (error) {
        console.error('Error running periodic task:', error)
      }
    }

    const runTestTask = async () => {
      testTaskLoading.value = true
      try {
        await api.post('/test-tasks/run_test_task/')
        // Reload tasks after a short delay
        setTimeout(async () => {
          await loadTasks()
          await loadStatistics()
        }, 3000)
      } catch (error) {
        console.error('Error running test task:', error)
      } finally {
        testTaskLoading.value = false
      }
    }

    const runFailingTask = async () => {
      failingTaskLoading.value = true
      try {
        await api.post('/test-tasks/run_failing_task/')
        // Reload tasks after a short delay
        setTimeout(async () => {
          await loadTasks()
          await loadStatistics()
        }, 3000)
      } catch (error) {
        console.error('Error running failing task:', error)
      } finally {
        failingTaskLoading.value = false
      }
    }

    const testEndpoint = async () => {
      testEndpointLoading.value = true
      try {
        const response = await api.get('/test/endpoint/')
        console.log('Test endpoint response:', response.data)
        // Reload tasks after a short delay
        setTimeout(async () => {
          await loadTasks()
          await loadStatistics()
        }, 3000)
      } catch (error) {
        console.error('Error testing endpoint:', error)
      } finally {
        testEndpointLoading.value = false
      }
    }

    const testDirectAPI = async () => {
      try {
        const response = await api.get('/test/direct/')
        console.log('Test direct API response:', response.data)
        // Reload tasks after a short delay
        setTimeout(async () => {
          await loadTasks()
          await loadStatistics()
        }, 3000)
      } catch (error) {
        console.error('Error testing direct API:', error)
      }
    }

    const formatCrontab = (schedule: any) => {
      if (schedule.type === 'crontab') {
        return `${schedule.minute} ${schedule.hour} ${schedule.day_of_month} ${schedule.month_of_year} ${schedule.day_of_week}`
      }
      return ''
    }

    // Watch for changes in search or options
    watch([search, options], () => {
      loadTasks()
    }, { deep: true })

    onMounted(() => {
      loadStatistics()
      loadTasks()
      loadPeriodicTasks()
    })

    return {
      loading,
      periodicLoading,
      testTaskLoading,
      failingTaskLoading,
      testEndpointLoading,
      tasks,
      periodicTasks,
      statistics,
      search,
      taskDetailsDialog,
      selectedTask,
      options,
      totalTasks,
      headers,
      periodicHeaders,
      getStatusColor,
      viewTaskDetails,
      retryTask,
      togglePeriodicTask,
      runPeriodicTask,
      runTestTask,
      runFailingTask,
      testEndpoint,
      testDirectAPI,
      formatDate,
      formatDuration,
      formatCrontab
    }
  }
})
</script>

<style scoped>
.error-text {
  color: #f44336;
  background-color: #ffebee;
  padding: 8px;
  border-radius: 4px;
  font-family: monospace;
  white-space: pre-wrap;
}

pre {
  background-color: #f5f5f5;
  padding: 8px;
  border-radius: 4px;
  font-family: monospace;
  white-space: pre-wrap;
  max-height: 200px;
  overflow-y: auto;
}
</style> 