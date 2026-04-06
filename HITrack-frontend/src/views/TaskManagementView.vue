<template>
  <div class="task-management">
    <v-container fluid class="page-shell page-shell--wide">
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
              <v-col cols="12" md="3">
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
              <v-col cols="12" md="3">
                <v-btn
                  block
                  color="indigo"
                  prepend-icon="mdi-package-variant-closed"
                  @click="updateDebComponentsLatestVersions"
                  :loading="updateDebComponentsLoading"
                  size="large"
                  class="action-btn"
                >
                  Update Deb Latest Versions
                </v-btn>
              </v-col>
              <v-col cols="12" md="3">
                <v-btn
                  block
                  color="deep-orange"
                  prepend-icon="mdi-wrench-check"
                  @click="recalculateVulnerabilityFixAvailability"
                  :loading="recalculateFixAvailabilityLoading"
                  size="large"
                  class="action-btn"
                >
                  Recalculate Fix Availability
                </v-btn>
              </v-col>
              <v-col cols="12" md="3">
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

            <v-row class="mt-4">
              <v-col cols="12" md="3">
                <v-btn
                  block
                  color="cyan-darken-1"
                  prepend-icon="mdi-family-tree"
                  @click="backfillImageLineageFields"
                  :loading="backfillImageLineageLoading"
                  size="large"
                  class="action-btn"
                >
                  Backfill Image Lineage
                </v-btn>
              </v-col>
              <v-col cols="12" md="3">
                <v-btn
                  block
                  color="cyan-darken-4"
                  prepend-icon="mdi-shield-search"
                  @click="backfillImageSbomSecurityMetadata"
                  :loading="backfillImageSbomSecurityLoading"
                  size="large"
                  class="action-btn"
                >
                  Backfill SBOM Security Metadata
                </v-btn>
              </v-col>
              <v-col cols="12" md="3">
                <v-btn
                  block
                  color="teal"
                  prepend-icon="mdi-chart-box-outline"
                  @click="collectRootCauseAnalyticsSnapshot"
                  :loading="collectRootCauseAnalyticsLoading"
                  size="large"
                  class="action-btn"
                >
                  Refresh Root Cause Snapshots
                </v-btn>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>
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
            <v-data-table-server
              :headers="headers"
              :items="tasks"
              :items-length="totalTasks"
              :loading="loading"
              :items-per-page="taskItemsPerPage"
              :page="taskPage"
              v-model:sort-by="taskSortBy"
              class="elevation-0 task-table"
              dense
              hide-default-footer
              @update:options="onTaskOptionsUpdate"
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
              

              
              <template v-slot:item.created="{ item }">
                <div class="text-center">
                  <div class="font-weight-medium">{{ formatDate(item.created) }}</div>
                </div>
              </template>
              
              <template v-slot:item.actions="{ item }">
                <div class="d-flex justify-center">
                  <v-btn
                    icon
                    x-small
                    @click="viewTaskDetails(item)"
                    class="mr-1 action-icon-btn"
                    color="primary"
                  >
                    <v-icon>mdi-eye</v-icon>
                  </v-btn>
                  <v-btn
                    v-if="item.status === 'error'"
                    icon
                    x-small
                    color="warning"
                    @click="retryTask(item)"
                    class="action-icon-btn mr-1"
                  >
                    <v-icon>mdi-refresh</v-icon>
                  </v-btn>
                  <v-btn
                    v-if="item.status === 'in_process' || item.status === 'pending'"
                    icon
                    x-small
                    color="error"
                    @click="stopTask(item)"
                    class="action-icon-btn"
                    :loading="stoppingTasks.includes(item.task_id)"
                  >
                    <v-icon>mdi-stop</v-icon>
                  </v-btn>
                </div>
              </template>
            </v-data-table-server>
            <div class="d-flex align-center justify-end px-4 py-3 gap-4">
              <v-select
                :items="[10, 25, 50, 100]"
                v-model="taskItemsPerPage"
                label="Tasks per page"
                density="compact"
                variant="outlined"
                hide-details
                style="width: 90px"
                @update:model-value="onTaskItemsPerPageChange"
              />
              <span class="text-body-2">
                {{ taskRangeStart }}-{{ taskRangeEnd }} of {{ totalTasks }}
              </span>
              <v-pagination
                v-model="taskPage"
                :length="taskPageCount"
                :total-visible="7"
                density="comfortable"
              />
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Task Details Dialog -->
    <v-dialog v-model="taskDetailsDialog" max-width="1200px" persistent>
      <v-card>
        <v-card-title class="d-flex align-center pa-4">
          <v-icon class="mr-3" color="primary" size="24">mdi-information</v-icon>
          <span class="text-h5">Task Details</span>
          <v-spacer></v-spacer>
          <v-btn icon @click="taskDetailsDialog = false" color="grey">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>
        
        <v-divider></v-divider>
        
        <v-card-text class="pa-6">
          <v-row v-if="selectedTask">
            <!-- Basic Task Information -->
            <v-col cols="12">
              <v-card class="mb-4" elevation="1" style="border-radius: 8px;">
                <v-card-title class="text-h6 pa-4 pb-2">
                  <v-icon class="mr-2" color="primary">mdi-play-circle</v-icon>
                  Basic Information
                </v-card-title>
                <v-card-text class="pa-4 pt-0">
                  <v-row>
                    <v-col cols="12" md="6">
                      <div class="info-item">
                        <span class="info-label">Task ID:</span>
                        <span class="info-value task-id">{{ selectedTask.task_id }}</span>
                      </div>
                    </v-col>
                    <v-col cols="12" md="6">
                      <div class="info-item">
                        <span class="info-label">Status:</span>
                        <v-chip
                          :color="getStatusColor(selectedTask.status)"
                          text-color="white"
                          size="small"
                          class="ml-2"
                        >
                          {{ selectedTask.status }}
                        </v-chip>
                      </div>
                    </v-col>
                    <v-col cols="12" md="6">
                      <div class="info-item">
                        <span class="info-label">Created:</span>
                        <span class="info-value">{{ formatDate(selectedTask.created) }}</span>
                      </div>
                    </v-col>
                    <v-col cols="12" md="6">
                      <div class="info-item">
                        <span class="info-label">Updated:</span>
                        <span class="info-value">{{ selectedTask.updated ? formatDate(selectedTask.updated) : '-' }}</span>
                      </div>
                    </v-col>
                    <v-col cols="12" md="6" v-if="selectedTask.duration">
                      <div class="info-item">
                        <span class="info-label">Duration:</span>
                        <span class="info-value duration">{{ formatDuration(selectedTask.duration) }}</span>
                      </div>
                    </v-col>
                    <v-col cols="12" md="6" v-if="selectedTask.task_name">
                      <div class="info-item">
                        <span class="info-label">Task Name:</span>
                        <span class="info-value">{{ selectedTask.task_name }}</span>
                      </div>
                    </v-col>
                  </v-row>
                </v-card-text>
              </v-card>
            </v-col>

            <!-- Result Summary -->
            <v-col cols="12" v-if="selectedTask.result_summary">
              <v-card class="mb-4" elevation="1" style="border-radius: 8px;">
                <v-card-title class="text-h6 pa-4 pb-2">
                  <v-icon class="mr-2" color="success">mdi-chart-box</v-icon>
                  Result Summary
                </v-card-title>
                <v-card-text class="pa-0">
                  <TaskResultDisplay :result="selectedTask.result_summary" />
                </v-card-text>
              </v-card>
            </v-col>

            <!-- Error Details -->
            <v-col cols="12" v-if="selectedTask.traceback">
              <v-card class="mb-4" elevation="1" style="border-radius: 8px;">
                <v-card-title class="text-h6 pa-4 pb-2">
                  <v-icon class="mr-2" color="error">mdi-alert-circle</v-icon>
                  Error Details
                </v-card-title>
                <v-card-text class="pa-4">
                  <pre class="error-text">{{ selectedTask.traceback }}</pre>
                </v-card-text>
              </v-card>
            </v-col>
          </v-row>
        </v-card-text>
        
        <v-divider></v-divider>
        
        <v-card-actions class="pa-4">
          <v-spacer></v-spacer>
          <v-btn
            color="primary"
            @click="taskDetailsDialog = false"
            prepend-icon="mdi-close"
          >
            Close
          </v-btn>
        </v-card-actions>
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
            <v-data-table-server
              :headers="periodicHeaders"
              :items="periodicTasks"
              :items-length="totalPeriodicTasks"
              :loading="periodicLoading"
              :items-per-page="periodicItemsPerPage"
              :page="periodicPage"
              v-model:sort-by="periodicSortBy"
              hide-default-footer
              @update:options="onPeriodicOptionsUpdate"
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
                  x-small
                  @click="runPeriodicTaskNow(item)"
                >
                  <v-icon>mdi-play</v-icon>
                </v-btn>
              </template>
            </v-data-table-server>
            <div class="d-flex align-center justify-end px-4 py-3 gap-4">
              <v-select
                :items="[10, 25, 50, 100]"
                v-model="periodicItemsPerPage"
                label="Items per page"
                density="compact"
                variant="outlined"
                hide-details
                style="width: 90px"
                @update:model-value="onPeriodicItemsPerPageChange"
              />
              <span class="text-body-2">
                {{ periodicRangeStart }}-{{ periodicRangeEnd }} of {{ totalPeriodicTasks }}
              </span>
              <v-pagination
                v-model="periodicPage"
                :length="periodicPageCount"
                :total-visible="7"
                density="comfortable"
              />
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
    </v-container>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, reactive, onMounted, onUnmounted, watch, computed } from 'vue'
import api from '@/plugins/axios'
import type { TaskResult, TaskStatistics, PeriodicTask } from '@/types/interfaces'
import { formatDate, formatDuration } from '@/utils/dateUtils'
import { notificationService } from '@/plugins/notifications'
import type { DataTableSortItem } from 'vuetify'

export default defineComponent({
  name: 'TaskManagementView',
  setup() {
    const loading = ref(false)
    const periodicLoading = ref(false)
    const testTaskLoading = ref(false)
    const failingTaskLoading = ref(false)
    const testEndpointLoading = ref(false)
    const updateComponentsLoading = ref(false)
    const updateDebComponentsLoading = ref(false)
    const backfillImageLineageLoading = ref(false)
    const backfillImageSbomSecurityLoading = ref(false)
    const recalculateFixAvailabilityLoading = ref(false)
    const collectRootCauseAnalyticsLoading = ref(false)
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
    const hasActiveTasks = computed(() =>
      tasks.value.some(task => ['pending', 'in_process'].includes(task.status))
    )
    let refreshTimer: number | null = null

    const taskPage = ref(1)
    const taskItemsPerPage = ref(10)
    const taskSortBy = ref<DataTableSortItem[]>([{ key: 'created', order: 'desc' }])
    const totalTasks = ref(0)
    const periodicPage = ref(1)
    const periodicItemsPerPage = ref(10)
    const periodicSortBy = ref<DataTableSortItem[]>([{ key: 'name', order: 'asc' }])
    const totalPeriodicTasks = ref(0)

    const normalizeSortBy = (items?: readonly DataTableSortItem[]): DataTableSortItem[] =>
      (items || []).map((item) => ({
        key: String(item.key),
        order: item.order === 'desc' ? 'desc' : 'asc',
      }))

    const areSortByEqual = (left: readonly DataTableSortItem[], right: readonly DataTableSortItem[]) =>
      JSON.stringify(normalizeSortBy(left)) === JSON.stringify(normalizeSortBy(right))

    const taskOrderingMap: Record<string, string> = {
      task_id: 'task_id',
      task_name: 'task_name',
      status: 'status',
      created: 'date_created',
    }

    const periodicOrderingMap: Record<string, string> = {
      name: 'name',
      task: 'task',
      enabled: 'enabled',
      last_run_at: 'last_run_at',
      total_run_count: 'total_run_count',
    }

    const taskPageCount = computed(() => Math.ceil(totalTasks.value / taskItemsPerPage.value) || 1)
    const periodicPageCount = computed(() => Math.ceil(totalPeriodicTasks.value / periodicItemsPerPage.value) || 1)
    const taskRangeStart = computed(() => totalTasks.value === 0 ? 0 : ((taskPage.value - 1) * taskItemsPerPage.value) + 1)
    const taskRangeEnd = computed(() => totalTasks.value === 0 ? 0 : Math.min(taskPage.value * taskItemsPerPage.value, totalTasks.value))
    const periodicRangeStart = computed(() => totalPeriodicTasks.value === 0 ? 0 : ((periodicPage.value - 1) * periodicItemsPerPage.value) + 1)
    const periodicRangeEnd = computed(() => totalPeriodicTasks.value === 0 ? 0 : Math.min(periodicPage.value * periodicItemsPerPage.value, totalPeriodicTasks.value))

    const headers = [
      { title: 'Task ID', key: 'task_id', sortable: true },
      { title: 'Task Name', key: 'task_name', sortable: true },
      { title: 'Status', key: 'status', sortable: true },
      { title: 'Duration', key: 'duration', sortable: false },
      { title: 'Created', key: 'created', sortable: true },
      { title: 'Actions', key: 'actions', sortable: false }
    ]

    const periodicHeaders = [
      { title: 'Name', key: 'name', sortable: true },
      { title: 'Task', key: 'task', sortable: true },
      { title: 'Enabled', key: 'enabled', sortable: true },
      { title: 'Schedule', key: 'schedule_info', sortable: false },
      { title: 'Next Run', key: 'next_run', sortable: false },
      { title: 'Last Run', key: 'last_run_at', sortable: true },
      { title: 'Run Count', key: 'total_run_count', sortable: true },
      { title: 'Actions', key: 'actions', sortable: false }
    ]

    function debounce(fn: Function, delay: number) {
      let timeout: ReturnType<typeof setTimeout> | null = null
      return (...args: any[]) => {
        if (timeout) clearTimeout(timeout)
        timeout = setTimeout(() => fn(...args), delay)
      }
    }

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
          page_size: taskItemsPerPage.value || 10,
          page: taskPage.value || 1
        }
        
        // Add search parameter if provided
        if (search.value) {
          params.search = search.value
        }
        
        // Add sorting parameters
        if (taskSortBy.value.length > 0) {
          const sortField = taskOrderingMap[String(taskSortBy.value[0].key)]
          if (sortField) {
            params.ordering = `${taskSortBy.value[0].order === 'desc' ? '-' : ''}${sortField}`
          }
        }
        
        const response = await api.get('/tasks/', { params })
        tasks.value = response.data.results || []
        totalTasks.value = response.data.count || 0
      } catch (error) {
        console.error('Error loading tasks:', error)
      } finally {
        loading.value = false
      }
    }

    const loadPeriodicTasks = async () => {
      periodicLoading.value = true
      try {
        const params: any = {
          page_size: periodicItemsPerPage.value || 10,
          page: periodicPage.value || 1,
        }

        if (periodicSortBy.value.length > 0) {
          const sortField = periodicOrderingMap[String(periodicSortBy.value[0].key)]
          if (sortField) {
            params.ordering = `${periodicSortBy.value[0].order === 'desc' ? '-' : ''}${sortField}`
          }
        }

        const response = await api.get('/periodic-tasks/', { params })
        periodicTasks.value = response.data.results || []
        totalPeriodicTasks.value = response.data.count || 0
      } catch (error) {
        console.error('Error loading periodic tasks:', error)
      } finally {
        periodicLoading.value = false
      }
    }

    const startAutoRefresh = () => {
      if (refreshTimer !== null) return
      refreshTimer = window.setInterval(() => {
        if (!loading.value) {
          loadTasks()
          loadStatistics()
        }
      }, 5000)
    }

    const stopAutoRefresh = () => {
      if (refreshTimer === null) return
      window.clearInterval(refreshTimer)
      refreshTimer = null
    }

    const upsertPendingTask = (taskId: string, taskName: string) => {
      if (!taskId) return

      const pendingTask: TaskResult = {
        task_id: taskId,
        task_name: taskName,
        status: 'pending',
        created: new Date().toISOString(),
      }

      const existingIndex = tasks.value.findIndex(task => task.task_id === taskId)
      if (existingIndex >= 0) {
        tasks.value.splice(existingIndex, 1, { ...tasks.value[existingIndex], ...pendingTask })
        return
      }

      tasks.value = [pendingTask, ...tasks.value].slice(0, taskItemsPerPage.value || 10)
      totalTasks.value += 1
    }

    const runTestTask = async () => {
      testTaskLoading.value = true
      try {
        const response = await api.post('/test-tasks/run_test_task/')
        if (response.data?.task_id) {
          upsertPendingTask(response.data.task_id, 'Test Task')
        }
        notificationService.started('Test task started.')
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
        const response = await api.post('/test-tasks/run_failing_task/')
        if (response.data?.task_id) {
          upsertPendingTask(response.data.task_id, 'Test Failing Task')
        }
        notificationService.started('Failing test task started.')
      } catch (error) {
        console.error('Error running failing task:', error)
        notificationService.error(`Failed to start failing task: ${error}`)
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
        const response = await api.post('/test-tasks/update_all_components_latest_versions/')
        if (response.data?.task_id) {
          upsertPendingTask(response.data.task_id, 'Update All Components Latest Versions')
        }
        notificationService.started('Update all components task started.')
      } catch (error) {
        console.error('Error updating all components latest versions:', error)
        notificationService.error(`Failed to start update task: ${error}`)
      } finally {
        updateComponentsLoading.value = false
      }
    }

    const updateDebComponentsLatestVersions = async () => {
      updateDebComponentsLoading.value = true
      try {
        const response = await api.post('/test-tasks/update_deb_components_latest_versions/')
        if (response.data?.task_id) {
          upsertPendingTask(response.data.task_id, 'Update Deb Components Latest Versions')
        }
        notificationService.started('Update deb components task started.')
      } catch (error) {
        console.error('Error updating deb components latest versions:', error)
        notificationService.error(`Failed to start deb update task: ${error}`)
      } finally {
        updateDebComponentsLoading.value = false
      }
    }

    const recalculateVulnerabilityFixAvailability = async () => {
      recalculateFixAvailabilityLoading.value = true
      try {
        const response = await api.post('/test-tasks/recalculate_vulnerability_fix_availability/')
        if (response.data?.task_id) {
          upsertPendingTask(response.data.task_id, 'Recalculate Vulnerability Fix Availability')
        }
        notificationService.started('Fix availability recalculation task started.')
      } catch (error) {
        console.error('Error recalculating vulnerability fix availability:', error)
        notificationService.error(`Failed to start fix availability recalculation: ${error}`)
      } finally {
        recalculateFixAvailabilityLoading.value = false
      }
    }

    const backfillImageLineageFields = async () => {
      backfillImageLineageLoading.value = true
      try {
        const response = await api.post('/test-tasks/backfill_image_lineage_fields/')
        if (response.data?.task_id) {
          upsertPendingTask(response.data.task_id, 'Backfill Image Lineage Fields')
        }
        notificationService.started('Image lineage backfill task started.')
      } catch (error) {
        console.error('Error backfilling image lineage fields:', error)
        notificationService.error(`Failed to start image lineage backfill: ${error}`)
      } finally {
        backfillImageLineageLoading.value = false
      }
    }

    const backfillImageSbomSecurityMetadata = async () => {
      backfillImageSbomSecurityLoading.value = true
      try {
        const response = await api.post('/test-tasks/backfill_image_sbom_security_metadata/')
        if (response.data?.task_id) {
          upsertPendingTask(response.data.task_id, 'Backfill Image SBOM Security Metadata')
        }
        notificationService.started('Image SBOM security metadata backfill task started.')
      } catch (error) {
        console.error('Error backfilling image SBOM security metadata:', error)
        notificationService.error(`Failed to start SBOM security metadata backfill: ${error}`)
      } finally {
        backfillImageSbomSecurityLoading.value = false
      }
    }

    const collectRootCauseAnalyticsSnapshot = async () => {
      collectRootCauseAnalyticsLoading.value = true
      try {
        const response = await api.post('/test-tasks/collect_root_cause_analytics_snapshot/')
        if (response.data?.task_id) {
          upsertPendingTask(response.data.task_id, 'Collect Root Cause Analytics Snapshot')
        }
        notificationService.started('Root cause analytics snapshot task started.')
      } catch (error) {
        console.error('Error collecting root cause analytics snapshot:', error)
        notificationService.error(`Failed to start root cause snapshot task: ${error}`)
      } finally {
        collectRootCauseAnalyticsLoading.value = false
      }
    }

    const viewTaskDetails = (task: TaskResult) => {
      selectedTask.value = task
      taskDetailsDialog.value = true
    }

    const retryTask = async (task: TaskResult) => {
      try {
        const response = await api.post(`/tasks/${task.task_id}/retry_task/`)
        if (response.data?.new_task_id) {
          upsertPendingTask(response.data.new_task_id, task.task_name)
        }
        notificationService.queued(`Task "${task.task_name}" retry was queued.`)
      } catch (error) {
        console.error('Error retrying task:', error)
        notificationService.error(`Failed to retry task "${task.task_name}": ${error}`)
      }
    }

    const stopTask = async (task: TaskResult) => {
      stoppingTasks.value.push(task.task_id)
      try {
        await api.post(`/tasks/${task.task_id}/stop_task/`)
        const existingTask = tasks.value.find(item => item.task_id === task.task_id)
        if (existingTask) {
          existingTask.status = 'revoked'
        }
        notificationService.completed(`Task "${task.task_name}" was stopped.`)
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
        case 'revoked':
          return 'secondary'
        case 'pending':
          return 'warning'
        case 'in_process':
          return 'info'
        default:
          return 'grey'
      }
    }

    const getTaskIcon = (taskName: string) => {
      const safeTaskName = taskName || ''
      if (safeTaskName.includes('Test Task')) return 'mdi-test-tube'
      if (safeTaskName.includes('Failing Task')) return 'mdi-alert'
      if (safeTaskName.includes('Test Endpoint')) return 'mdi-web'
      if (safeTaskName.includes('Test Direct API')) return 'mdi-api'
      if (safeTaskName.includes('Scan')) return 'mdi-magnify'
      if (safeTaskName.includes('Update')) return 'mdi-update'
      if (safeTaskName.includes('Recalculate')) return 'mdi-wrench-check'
      if (safeTaskName.includes('Process')) return 'mdi-cog'
      if (safeTaskName.includes('Parse')) return 'mdi-file-document'
      if (safeTaskName.includes('Delete')) return 'mdi-delete'
      if (safeTaskName.includes('Cleanup')) return 'mdi-broom'
      return 'mdi-help-circle'
    }

    const debouncedLoadTasks = debounce(loadTasks, 300)

    const onTaskItemsPerPageChange = (value: number) => {
      taskItemsPerPage.value = value
      taskPage.value = 1
    }

    const onPeriodicItemsPerPageChange = (value: number) => {
      periodicItemsPerPage.value = value
      periodicPage.value = 1
    }

    const onTaskOptionsUpdate = (options: { page: number; itemsPerPage: number; sortBy: DataTableSortItem[] }) => {
      const nextSortBy = normalizeSortBy(options.sortBy)

      if (
        taskPage.value === options.page &&
        taskItemsPerPage.value === options.itemsPerPage &&
        areSortByEqual(taskSortBy.value, nextSortBy)
      ) {
        return
      }

      taskPage.value = options.page
      taskItemsPerPage.value = options.itemsPerPage
      if (!areSortByEqual(taskSortBy.value, nextSortBy)) {
        taskSortBy.value = nextSortBy
      }
    }

    const onPeriodicOptionsUpdate = (options: { page: number; itemsPerPage: number; sortBy: DataTableSortItem[] }) => {
      const nextSortBy = normalizeSortBy(options.sortBy)

      if (
        periodicPage.value === options.page &&
        periodicItemsPerPage.value === options.itemsPerPage &&
        areSortByEqual(periodicSortBy.value, nextSortBy)
      ) {
        return
      }

      periodicPage.value = options.page
      periodicItemsPerPage.value = options.itemsPerPage
      if (!areSortByEqual(periodicSortBy.value, nextSortBy)) {
        periodicSortBy.value = nextSortBy
      }
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
        const response = await api.post(`/periodic-tasks/${task.id}/run_now/`)
        if (response.data?.task_id) {
          upsertPendingTask(response.data.task_id, task.name || task.task)
        }
        await loadPeriodicTasks()
        notificationService.started(`Periodic task "${task.name}" started.`)
      } catch (error) {
        console.error('Error running periodic task now:', error)
        notificationService.error(`Failed to run periodic task "${task.name}"`)
      }
    }

    watch(search, () => {
      taskPage.value = 1
      debouncedLoadTasks()
    })

    watch([taskPage, taskItemsPerPage, taskSortBy], loadTasks)

    watch([periodicPage, periodicItemsPerPage, periodicSortBy], loadPeriodicTasks)

    watch(hasActiveTasks, (isActive) => {
      if (isActive) {
        startAutoRefresh()
      } else {
        stopAutoRefresh()
      }
    }, { immediate: true })

    onMounted(() => {
      Promise.all([loadTasks(), loadStatistics(), loadPeriodicTasks()])
    })

    onUnmounted(() => {
      stopAutoRefresh()
    })



    

    return {
          loading,
          periodicLoading,
          testTaskLoading,
          failingTaskLoading,
          testEndpointLoading,
          updateComponentsLoading,
          updateDebComponentsLoading,
          backfillImageLineageLoading,
          backfillImageSbomSecurityLoading,
          recalculateFixAvailabilityLoading,
          collectRootCauseAnalyticsLoading,
          stoppingTasks,
          tasks,
          periodicTasks,
          statistics,
          search,
          taskDetailsDialog,
          selectedTask,
          hasActiveTasks,
          taskPage,
          taskItemsPerPage,
          taskSortBy,
          totalTasks,
          periodicPage,
          periodicItemsPerPage,
          periodicSortBy,
          totalPeriodicTasks,
          taskPageCount,
          periodicPageCount,
          taskRangeStart,
          taskRangeEnd,
          periodicRangeStart,
          periodicRangeEnd,
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
          updateDebComponentsLatestVersions,
          backfillImageLineageFields,
          backfillImageSbomSecurityMetadata,
          recalculateVulnerabilityFixAvailability,
          collectRootCauseAnalyticsSnapshot,
          viewTaskDetails,
          retryTask,
          stopTask,
          getStatusColor,
          togglePeriodicTask,
          runPeriodicTaskNow,
          onTaskOptionsUpdate,
          onPeriodicOptionsUpdate,
          onTaskItemsPerPageChange,
          onPeriodicItemsPerPageChange,
          formatDate,
          formatDuration,
          getTaskIcon
        }
  }
})
</script>

<style scoped>
.task-management {
  padding: 20px;
  background: #ffffff;
  min-height: 100vh;
}

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
.v-data-table td:nth-child(4), /* Duration */
.v-data-table td:nth-child(5), /* Created */
.v-data-table td:nth-child(6) { /* Actions */
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

/* Task Details Dialog Styling */
.info-item {
  display: flex;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
}

.info-item:last-child {
  border-bottom: none;
}

.info-label {
  font-weight: 600;
  color: #555;
  min-width: 120px;
  margin-right: 16px;
}

.info-value {
  color: #333;
  font-weight: 500;
}

.info-value.task-id {
  font-family: 'Courier New', monospace;
  font-size: 0.9em;
  background: #f5f5f5;
  padding: 4px 8px;
  border-radius: 4px;
  color: #666;
}

.info-value.duration {
  font-weight: 600;
  color: #2196f3;
}

.error-text {
  background: #fff5f5;
  border: 1px solid #fed7d7;
  border-radius: 6px;
  padding: 16px;
  font-family: 'Courier New', monospace;
  font-size: 0.85em;
  color: #c53030;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 300px;
  overflow-y: auto;
}

/* Dialog improvements */
.v-dialog .v-card {
  border-radius: 12px;
}



.v-dialog .v-card-title {
  background: linear-gradient(135deg, #f8f9fa, #e9ecef);
  border-radius: 12px 12px 0 0;
}

.v-dialog .v-card-actions {
  background: #f8f9fa;
  border-radius: 0 0 12px 12px;
}


</style> 
