<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <div class="d-flex align-center justify-space-between mb-4">
          <h1 class="text-h4">Task Management</h1>
        </div>
        
        <!-- Action Cards Section -->
        <v-card class="mb-6" elevation="2" style="border-radius: 12px;">
          <v-card-title class="d-flex align-center pa-4">
            <v-icon class="mr-3" color="primary" size="24">mdi-cog</v-icon>
            <span class="text-h6">Task Controls</span>
          </v-card-title>
          <v-card-text class="pa-4">
            <v-row>
              <v-col cols="12" md="3">
                <v-btn
                  block
                  color="success"
                  prepend-icon="mdi-play"
                  @click="runTestTask"
                  :loading="testTaskLoading"
                  size="large"
                  class="action-btn"
                >
                  Run Test Task
                </v-btn>
              </v-col>
              <v-col cols="12" md="3">
                <v-btn
                  block
                  color="error"
                  prepend-icon="mdi-alert"
                  @click="runFailingTask"
                  :loading="failingTaskLoading"
                  size="large"
                  class="action-btn"
                >
                  Run Failing Task
                </v-btn>
              </v-col>
              <v-col cols="12" md="3">
                <v-btn
                  block
                  color="info"
                  prepend-icon="mdi-test-tube"
                  @click="testEndpoint"
                  :loading="testEndpointLoading"
                  size="large"
                  class="action-btn"
                >
                  Test Endpoint
                </v-btn>
              </v-col>
              <v-col cols="12" md="3">
                <v-btn
                  block
                  color="warning"
                  prepend-icon="mdi-bug"
                  @click="testDirectAPI"
                  size="large"
                  class="action-btn"
                >
                  Test Direct API
                </v-btn>
              </v-col>
            </v-row>
            
            <v-row class="mt-4">
              <v-col cols="12" md="6">
                <v-btn
                  block
                  color="primary"
                  prepend-icon="mdi-update"
                  @click="updateAllComponentsLatestVersions"
                  :loading="updateComponentsLoading"
                  size="large"
                  class="action-btn"
                >
                  Update All Components Latest Versions
                </v-btn>
              </v-col>
              <v-col cols="12" md="6">
                <v-btn
                  block
                  color="secondary"
                  prepend-icon="mdi-refresh"
                  @click="loadTasks"
                  :loading="loading"
                  size="large"
                  class="action-btn"
                >
                  Refresh Tasks
                </v-btn>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Statistics Cards -->
    <v-row>
      <v-col cols="12" md="3">
        <MetricCard
          title="Total Tasks"
          :value="statistics.total_tasks"
          icon="mdi-clipboard-list"
          color="primary"
        />
      </v-col>
      <v-col cols="12" md="3">
        <MetricCard
          title="Successful"
          :value="statistics.successful_tasks"
          icon="mdi-check-circle"
          color="success"
          :subtitle="statistics.total_tasks > 0 ? `${Math.round((statistics.successful_tasks / statistics.total_tasks) * 100)}% of total` : undefined"
        />
      </v-col>
      <v-col cols="12" md="3">
        <MetricCard
          title="Failed"
          :value="statistics.failed_tasks"
          icon="mdi-alert-circle"
          color="error"
          :subtitle="statistics.total_tasks > 0 ? `${Math.round((statistics.failed_tasks / statistics.total_tasks) * 100)}% of total` : undefined"
        />
      </v-col>
      <v-col cols="12" md="3">
        <MetricCard
          title="Running"
          :value="statistics.running_tasks"
          icon="mdi-sync"
          color="warning"
          :subtitle="statistics.total_tasks > 0 ? `${Math.round((statistics.running_tasks / statistics.total_tasks) * 100)}% of total` : undefined"
        />
      </v-col>
    </v-row>

    <!-- Additional Task Metrics -->
    <v-row class="mt-4">
      <v-col cols="12" md="3">
        <MetricCard
          title="Average Duration"
          :value="Math.round(statistics.average_duration || 0)"
          icon="mdi-clock-outline"
          color="info"
          subtitle="seconds"
        />
      </v-col>
      <v-col cols="12" md="3">
        <MetricCard
          title="Pending Tasks"
          :value="statistics.pending_tasks"
          icon="mdi-clock"
          color="warning"
          :subtitle="statistics.total_tasks > 0 ? `${Math.round((statistics.pending_tasks / statistics.total_tasks) * 100)}% of total` : undefined"
        />
      </v-col>
      <v-col cols="12" md="3">
        <MetricCard
          title="Recent Tasks"
          :value="statistics.recent_tasks?.length || 0"
          icon="mdi-history"
          color="primary"
          subtitle="last 24h"
        />
      </v-col>
      <v-col cols="12" md="3">
        <MetricCard
          title="Success Rate"
          :value="statistics.total_tasks > 0 ? Math.round((statistics.successful_tasks / statistics.total_tasks) * 100) : 0"
          icon="mdi-chart-line"
          color="success"
          format="percentage"
          subtitle="overall"
        />
      </v-col>
    </v-row>

    <!-- Task List -->
    <v-row>
      <v-col cols="12">
        <v-card elevation="2" style="border-radius: 12px;">
          <v-card-title class="d-flex align-center">
            <v-icon class="mr-3" color="primary" size="24">mdi-format-list-bulleted</v-icon>
            <span class="text-h6">Recent Tasks</span>
            <v-spacer></v-spacer>
            <v-text-field
              v-model="search"
              append-icon="mdi-magnify"
              label="Search tasks..."
              single-line
              hide-details
              style="max-width: 300px"
              class="ml-4"
              outlined
              dense
            ></v-text-field>
          </v-card-title>
          <v-card-text class="pa-0">
            <v-data-table
              :headers="headers"
              :items="tasks"
              :loading="loading"
              :options.sync="options"
              :server-items-length="totalTasks"
              :items-per-page="options.itemsPerPage"
              :page.sync="options.page"
              class="elevation-0 task-table"
              dense
              :footer-props="{
                'items-per-page-options': [10, 25, 50, 100],
                'items-per-page-text': 'Tasks per page:'
              }"
            >
              <template v-slot:item.task_name="{ item }">
                <div class="d-flex align-center">
                  <v-icon 
                    :color="getStatusColor(item.status)" 
                    size="16" 
                    class="mr-2"
                  >
                    {{ getTaskIcon(item.task_name) }}
                  </v-icon>
                  <span class="font-weight-medium">{{ item.task_name || 'Unknown Task' }}</span>
                </div>
              </template>
              
              <template v-slot:item.status="{ item }">
                <v-chip
                  :color="getStatusColor(item.status)"
                  text-color="white"
                  small
                  class="font-weight-medium"
                >
                  {{ item.status }}
                </v-chip>
              </template>
              
              <template v-slot:item.duration="{ item }">
                <div class="text-center">
                  <span v-if="item.duration" class="font-weight-medium">
                    {{ formatDuration(item.duration) }}
                  </span>
                  <span v-else class="text--disabled">-</span>
                </div>
              </template>
              
              <template v-slot:item.result_summary="{ item }">
                <div v-if="item.result_summary" class="text-caption">
                  <div v-if="typeof item.result_summary === 'object'">
                    <div v-if="item.result_summary.message" class="mb-1">
                      {{ item.result_summary.message }}
                    </div>
                    <div v-if="item.result_summary.status" class="text--secondary">
                      Status: {{ item.result_summary.status }}
                    </div>
                  </div>
                  <div v-else>
                    {{ item.result_summary }}
                  </div>
                </div>
                <span v-else class="text-caption text--disabled">No result</span>
              </template>
              
              <template v-slot:item.created="{ item }">
                <div class="text-center">
                  <div class="font-weight-medium">{{ formatDate(item.created) }}</div>
                </div>
              </template>
              
              <template v-slot:item.actions="{ item }">
                <div class="d-flex justify-center">
                  <v-btn
                    icon
                    small
                    @click="viewTaskDetails(item)"
                    class="mr-1 action-icon-btn"
                    color="primary"
                  >
                    <v-icon>mdi-eye</v-icon>
                  </v-btn>
                  <v-btn
                    v-if="item.status === 'error'"
                    icon
                    small
                    color="warning"
                    @click="retryTask(item)"
                    class="action-icon-btn mr-1"
                  >
                    <v-icon>mdi-refresh</v-icon>
                  </v-btn>
                  <v-btn
                    v-if="item.status === 'in_process' || item.status === 'pending'"
                    icon
                    small
                    color="error"
                    @click="stopTask(item)"
                    class="action-icon-btn"
                    :loading="stoppingTasks.includes(item.task_id)"
                  >
                    <v-icon>mdi-stop</v-icon>
                  </v-btn>
                </div>
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
                    {{ item.schedule_info.minute }} {{ item.schedule_info.hour }} {{ item.schedule_info.day_of_month }} {{ item.schedule_info.month_of_year }} {{ item.schedule_info.day_of_week }}
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
                  @click="runPeriodicTaskNow(item)"
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
import { defineComponent, ref, reactive, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/plugins/axios'
import type { TaskResult, TaskStatistics, PeriodicTask } from '@/types/interfaces'
import { formatDate, formatDuration } from '@/utils/dateUtils'
import MetricCard from '@/components/MetricCard.vue'
import { notificationService } from '@/plugins/notifications'

export default defineComponent({
  name: 'TaskManagementView',
  setup() {
    const router = useRouter()
    const loading = ref(false)
    const periodicLoading = ref(false)
    const testTaskLoading = ref(false)
    const failingTaskLoading = ref(false)
    const testEndpointLoading = ref(false)
    const updateComponentsLoading = ref(false)
    const stoppingTasks = ref<string[]>([])
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

    const runTestTask = async () => {
      testTaskLoading.value = true
      try {
        await api.post('/test-tasks/run_test_task/')
        await loadTasks()
        await loadStatistics()
        notificationService.success('Test task started successfully')
      } catch (error) {
        console.error('Error running test task:', error)
        notificationService.error(`Failed to start test task: ${error}`)
      } finally {
        testTaskLoading.value = false
      }
    }

    const runFailingTask = async () => {
      failingTaskLoading.value = true
      try {
        await api.post('/test-tasks/run_failing_task/')
        await loadTasks()
        await loadStatistics()
      } catch (error) {
        console.error('Error running failing task:', error)
      } finally {
        failingTaskLoading.value = false
      }
    }

    const testEndpoint = async () => {
      testEndpointLoading.value = true
      try {
        await api.get('/test/endpoint/')
      } catch (error) {
        console.error('Error testing endpoint:', error)
      } finally {
        testEndpointLoading.value = false
      }
    }

    const testDirectAPI = async () => {
      try {
        await api.get('/test/direct/')
      } catch (error) {
        console.error('Error testing direct API:', error)
      }
    }

    const updateAllComponentsLatestVersions = async () => {
      updateComponentsLoading.value = true
      try {
        await api.post('/test-tasks/update_all_components_latest_versions/')
        notificationService.success('Update all components task started successfully')
        // Reload tasks after a short delay
        setTimeout(async () => {
          await loadTasks()
          await loadStatistics()
        }, 3000)
      } catch (error) {
        console.error('Error updating all components latest versions:', error)
        notificationService.error(`Failed to start update task: ${error}`)
      } finally {
        updateComponentsLoading.value = false
      }
    }

    const viewTaskDetails = (task: TaskResult) => {
      selectedTask.value = task
      taskDetailsDialog.value = true
    }

    const retryTask = async (task: TaskResult) => {
      try {
        await api.post(`/tasks/${task.task_id}/retry_task/`)
        await loadTasks()
        await loadStatistics()
        notificationService.success(`Task "${task.task_name}" retry initiated`)
      } catch (error) {
        console.error('Error retrying task:', error)
        notificationService.error(`Failed to retry task "${task.task_name}": ${error}`)
      }
    }

    const stopTask = async (task: TaskResult) => {
      stoppingTasks.value.push(task.task_id)
      try {
        await api.post(`/tasks/${task.task_id}/stop_task/`)
        await loadTasks()
        await loadStatistics()
        notificationService.success(`Task "${task.task_name}" stopped successfully`)
      } catch (error) {
        console.error('Error stopping task:', error)
        notificationService.error(`Failed to stop task "${task.task_name}": ${error}`)
      } finally {
        const index = stoppingTasks.value.indexOf(task.task_id)
        if (index > -1) {
          stoppingTasks.value.splice(index, 1)
        }
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

    const getTaskIcon = (taskName: string) => {
      if (taskName.includes('Test Task')) return 'mdi-test-tube'
      if (taskName.includes('Failing Task')) return 'mdi-alert'
      if (taskName.includes('Test Endpoint')) return 'mdi-web'
      if (taskName.includes('Test Direct API')) return 'mdi-api'
      if (taskName.includes('Scan')) return 'mdi-magnify'
      if (taskName.includes('Update')) return 'mdi-update'
      if (taskName.includes('Process')) return 'mdi-cog'
      if (taskName.includes('Parse')) return 'mdi-file-document'
      if (taskName.includes('Delete')) return 'mdi-delete'
      if (taskName.includes('Cleanup')) return 'mdi-broom'
      return 'mdi-help-circle'
    }

    const togglePeriodicTask = async (task: PeriodicTask) => {
      try {
        await api.post(`/periodic-tasks/${task.id}/toggle/`)
        await loadPeriodicTasks()
      } catch (error) {
        console.error('Error toggling periodic task:', error)
      }
    }

    const runPeriodicTaskNow = async (task: PeriodicTask) => {
      try {
        await api.post(`/periodic-tasks/${task.id}/run_now/`)
        await loadPeriodicTasks()
      } catch (error) {
        console.error('Error running periodic task now:', error)
      }
    }

    // Watch for changes in search and options
    watch(search, () => {
      loadTasks()
    })

    watch(options, () => {
      loadTasks()
    }, { deep: true })

    onMounted(() => {
      loadTasks()
      loadStatistics()
      loadPeriodicTasks()
    })

            return {
          loading,
          periodicLoading,
          testTaskLoading,
          failingTaskLoading,
          testEndpointLoading,
          updateComponentsLoading,
          stoppingTasks,
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
          loadTasks,
          loadStatistics,
          loadPeriodicTasks,
          runTestTask,
          runFailingTask,
          testEndpoint,
          testDirectAPI,
          updateAllComponentsLatestVersions,
          viewTaskDetails,
          retryTask,
          stopTask,
          getStatusColor,
          togglePeriodicTask,
          runPeriodicTaskNow,
          formatDate,
          formatDuration,
          getTaskIcon
        }
  }
})
</script>

<style scoped>
/* Custom styles for better alignment */
.v-data-table {
  border-radius: 8px;
}

.v-data-table th {
  font-weight: 600 !important;
  background-color: #f5f5f5 !important;
}

.v-data-table td {
  padding: 12px 16px !important;
  vertical-align: middle !important;
}

/* Center align specific columns */
.v-data-table td:nth-child(3), /* Status */
.v-data-table td:nth-child(5), /* Duration */
.v-data-table td:nth-child(6), /* Created */
.v-data-table td:nth-child(7) { /* Actions */
  text-align: center !important;
}

/* Task name column styling */
.v-data-table td:nth-child(2) { /* Task Name */
  font-weight: 500;
  max-width: 250px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Task ID column styling */
.v-data-table td:nth-child(1) { /* Task ID */
  font-family: 'Courier New', monospace;
  font-size: 0.85em;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Result summary column styling */
.v-data-table td:nth-child(4) { /* Result */
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Button group styling */
.gap-2 > * {
  margin-right: 8px;
}

.gap-2 > *:last-child {
  margin-right: 0;
}

/* Statistics cards styling */
.v-card-text.text-center {
  padding: 20px !important;
}

.v-card-text.text-center .text-h4 {
  margin-top: 8px;
  font-weight: 600;
}

/* Search field styling */
.v-text-field {
  margin-top: 0 !important;
}

/* Status chip styling */
.v-chip {
  font-weight: 500 !important;
  min-width: 60px !important;
  justify-content: center !important;
}

/* Action buttons styling */
.v-btn--icon.v-size--small {
  margin: 0 2px;
}

/* Dialog styling */
.v-dialog .v-card__title {
  border-bottom: 1px solid #e0e0e0;
  padding-bottom: 16px;
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .d-flex.flex-wrap {
    flex-direction: column;
  }
  
  .d-flex.flex-wrap > * {
    margin-bottom: 8px;
  }
  
  .v-data-table {
    font-size: 0.9em;
  }
}

/* Action card styling */
.action-btn {
  border-radius: 8px !important;
  font-weight: 500 !important;
  text-transform: none !important;
  letter-spacing: 0.5px !important;
  transition: all 0.3s ease !important;
}

.action-btn:hover {
  transform: translateY(-2px) !important;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15) !important;
}

.action-btn:active {
  transform: translateY(0) !important;
}

/* Task controls card styling */
.v-card-title {
  border-bottom: 1px solid #e0e0e0;
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
}

/* Metric cards spacing */
.mt-4 {
  margin-top: 16px !important;
}

/* Improved table card styling */
.v-card {
  border-radius: 12px !important;
  overflow: hidden !important;
}

.v-card-title {
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  border-bottom: 1px solid #e0e0e0;
  padding: 16px 20px !important;
}

/* Search field improvements */
.v-text-field {
  margin-top: 0 !important;
}

.v-text-field .v-input__control {
  border-radius: 8px !important;
}

/* Status chip improvements */
.v-chip {
  font-weight: 500 !important;
  min-width: 60px !important;
  justify-content: center !important;
  border-radius: 16px !important;
}

/* Dialog improvements */
.v-dialog .v-card__title {
  border-bottom: 1px solid #e0e0e0;
  padding-bottom: 16px;
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
}

/* Loading states */
.v-btn--loading {
  opacity: 0.8;
}

/* Hover effects for cards */
.v-card:hover {
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1) !important;
  transition: all 0.3s ease !important;
}

/* Task management header styling */
.text-h4 {
  font-weight: 600 !important;
  color: #2c3e50 !important;
  margin-bottom: 8px !important;
}

/* Responsive improvements */
@media (max-width: 960px) {
  .action-btn {
    margin-bottom: 8px;
  }
  
  .v-col {
    padding: 8px !important;
  }
}

@media (max-width: 600px) {
  .v-card-title {
    padding: 12px 16px !important;
  }
  
  .v-card-text {
    padding: 12px !important;
  }
  
  .text-h4 {
    font-size: 1.5rem !important;
  }
}

/* Action icon button styling */
.action-icon-btn {
  transition: all 0.2s ease !important;
}

.action-icon-btn:hover {
  transform: scale(1.1) !important;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15) !important;
}

/* Task table styling */
.task-table {
  border-radius: 0 !important;
}

.task-table .v-data-table__wrapper {
  border-radius: 0 !important;
}

.task-table .v-data-table__wrapper table {
  border-collapse: separate !important;
  border-spacing: 0 !important;
}

.task-table .v-data-table__wrapper table tbody tr:hover {
  background-color: #f8f9fa !important;
}

.task-table .v-data-table__wrapper table tbody tr td {
  border-bottom: 1px solid #e0e0e0 !important;
}

/* Task name column with icon */
.task-table .v-data-table__wrapper table tbody tr td:nth-child(2) {
  padding-left: 16px !important;
}

/* Status chip improvements */
.task-table .v-chip {
  font-size: 0.75rem !important;
  height: 24px !important;
  min-width: 70px !important;
}

/* Result summary column */
.task-table .v-data-table__wrapper table tbody tr td:nth-child(4) {
  max-width: 200px !important;
  overflow: hidden !important;
  text-overflow: ellipsis !important;
  white-space: nowrap !important;
}

/* Duration column */
.task-table .v-data-table__wrapper table tbody tr td:nth-child(5) {
  font-family: 'Courier New', monospace !important;
  font-size: 0.9em !important;
}

/* Created date column */
.task-table .v-data-table__wrapper table tbody tr td:nth-child(6) {
  font-size: 0.85em !important;
  color: #666 !important;
}

/* Actions column */
.task-table .v-data-table__wrapper table tbody tr td:nth-child(7) {
  padding: 8px 16px !important;
}

/* Table header styling */
.task-table .v-data-table__wrapper table thead th {
  background-color: #f8f9fa !important;
  font-weight: 600 !important;
  color: #2c3e50 !important;
  border-bottom: 2px solid #e0e0e0 !important;
}

/* Search field improvements */
.v-text-field--outlined .v-input__control {
  border-radius: 8px !important;
}

.v-text-field--outlined .v-input__control .v-input__slot {
  border-radius: 8px !important;
}

/* Loading overlay */
.v-data-table__progress {
  background-color: rgba(33, 150, 243, 0.1) !important;
}

/* Pagination styling */
.v-data-footer {
  background-color: #f8f9fa !important;
  border-top: 1px solid #e0e0e0 !important;
}

.v-data-footer__select {
  margin-right: 16px !important;
}

/* Empty state styling */
.v-data-table__empty-wrapper {
  padding: 40px 20px !important;
  text-align: center !important;
}

.v-data-table__empty-wrapper .v-icon {
  font-size: 48px !important;
  color: #ccc !important;
  margin-bottom: 16px !important;
}
</style> 