<template>
  <div class="recent-activities-page">
    <v-container fluid class="page-shell wide-page-shell">
      <div class="page-header">
        <div>
          <h1 class="text-h4 font-weight-bold mb-2">Recent Activities</h1>
          <p class="text-body-1 text-medium-emphasis">
            Latest repository scans and newly discovered vulnerabilities from the last 30 days.
          </p>
        </div>
        <v-btn
          variant="text"
          color="primary"
          prepend-icon="mdi-arrow-left"
          @click="goBackToDashboard"
        >
          Back to Dashboard
        </v-btn>
      </div>

      <v-card elevation="2" class="activities-card">
        <v-card-text class="pb-0">
          <div class="filters-bar">
            <v-select
              v-model="selectedActivityType"
              :items="activityTypeOptions"
              label="Event Type"
              variant="outlined"
              density="comfortable"
              hide-details
              class="activity-type-filter"
            />
          </div>
        </v-card-text>
        <v-card-text class="pa-0">
          <v-data-table-server
            :headers="headers"
            :items="activities"
            :items-length="totalItems"
            :items-per-page="itemsPerPage"
            :page="page"
            :loading="loading"
            item-value="target_uuid"
            class="activities-table"
            @update:options="onTableOptionsUpdate"
          >
            <template #item.type="{ item }">
              <v-chip
                :color="getActivityTypeColor(item.type)"
                size="small"
                variant="tonal"
              >
                {{ getActivityTypeLabel(item.type) }}
              </v-chip>
            </template>

            <template #item.title="{ item }">
              <button
                type="button"
                class="activity-link"
                :class="{ 'activity-link--disabled': !hasActivityRoute(item) }"
                :disabled="!hasActivityRoute(item)"
                @click="openActivity(item)"
              >
                {{ item.title }}
              </button>
            </template>

            <template #item.timestamp="{ item }">
              <div class="timestamp-cell">
                <div>{{ formatTimestamp(item.timestamp) }}</div>
                <div class="timestamp-cell__relative">{{ formatRelativeTime(item.timestamp) }}</div>
              </div>
            </template>

            <template #item.state="{ item }">
              <v-chip
                v-if="item.severity"
                :color="getSeverityColor(item.severity)"
                size="small"
                variant="tonal"
              >
                {{ item.severity }}
              </v-chip>
              <v-chip
                v-else-if="item.status"
                :color="getStatusColor(item.status)"
                size="small"
                variant="tonal"
              >
                {{ formatStatusLabel(item.status) }}
              </v-chip>
              <span v-else class="text-medium-emphasis">-</span>
            </template>

            <template #item.actions="{ item }">
              <v-btn
                v-if="hasActivityRoute(item)"
                icon="mdi-open-in-new"
                size="small"
                variant="text"
                color="primary"
                @click="openActivity(item)"
              />
              <span v-else class="text-medium-emphasis">-</span>
            </template>
          </v-data-table-server>
        </v-card-text>
      </v-card>
    </v-container>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { DataTableHeader, DataTableSortItem } from 'vuetify'

import api from '../plugins/axios'
import { notificationService } from '../plugins/notifications'
import type { PaginatedResponse, RecentActivity } from '../types/interfaces'

const router = useRouter()
type ActivityTypeFilter = 'all' | 'scan' | 'vulnerability'

const activities = ref<RecentActivity[]>([])
const loading = ref(false)
const page = ref(1)
const itemsPerPage = ref(50)
const totalItems = ref(0)
const selectedActivityType = ref<ActivityTypeFilter>('all')

const activityTypeOptions = [
  { title: 'All Events', value: 'all' },
  { title: 'Repository Scans', value: 'scan' },
  { title: 'New Vulnerabilities', value: 'vulnerability' },
]

const headers: DataTableHeader[] = [
  { title: 'Activity', key: 'title', sortable: false },
  { title: 'Type', key: 'type', sortable: false, width: 140 },
  { title: 'When', key: 'timestamp', sortable: false, width: 240 },
  { title: 'Status', key: 'state', sortable: false, width: 180 },
  { title: 'Actions', key: 'actions', sortable: false, width: 100, align: 'end' },
]

const fetchActivities = async () => {
  loading.value = true
  try {
    const response = await api.get<PaginatedResponse<RecentActivity>>('stats/recent-activities/', {
      params: {
        page: page.value,
        page_size: itemsPerPage.value,
        type: selectedActivityType.value === 'all' ? undefined : selectedActivityType.value,
      },
    })
    activities.value = response.data.results || []
    totalItems.value = response.data.count || 0
  } catch (error) {
    console.error('Error fetching recent activities:', error)
    notificationService.error('Failed to load recent activities')
  } finally {
    loading.value = false
  }
}

const hasActivityRoute = (activity: RecentActivity) => Boolean(getActivityRoute(activity))

const getActivityRoute = (activity: RecentActivity) => {
  if (!activity.target_type || !activity.target_uuid) {
    return null
  }

  switch (activity.target_type) {
    case 'repository':
      return { name: 'RepositoryDetail', params: { uuid: activity.target_uuid } }
    case 'vulnerability':
      return { name: 'vulnerability-detail', params: { uuid: activity.target_uuid } }
    case 'image':
      return { name: 'image-detail', params: { uuid: activity.target_uuid } }
    case 'component':
      return { name: 'component-detail', params: { uuid: activity.target_uuid } }
    case 'repository_tag':
      return { name: 'tag-images', params: { uuid: activity.target_uuid } }
    case 'release':
      return { name: 'releases' }
    default:
      return null
  }
}

const openActivity = (activity: RecentActivity) => {
  const route = getActivityRoute(activity)
  if (!route) {
    return
  }
  router.push(route)
}

const onTableOptionsUpdate = (options: { page: number; itemsPerPage: number; sortBy: DataTableSortItem[] }) => {
  const pageChanged = page.value !== options.page
  const itemsPerPageChanged = itemsPerPage.value !== options.itemsPerPage
  if (!pageChanged && !itemsPerPageChanged) {
    return
  }

  page.value = options.page
  itemsPerPage.value = options.itemsPerPage
}

const goBackToDashboard = () => {
  router.push('/')
}

const formatTimestamp = (timestamp: string) => {
  try {
    return new Date(timestamp).toLocaleString()
  } catch {
    return 'Unknown time'
  }
}

const formatRelativeTime = (timestamp: string) => {
  try {
    const date = new Date(timestamp)
    const now = new Date()
    const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000)

    if (diffInSeconds < 60) return 'just now'
    if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)} minutes ago`
    if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)} hours ago`
    return `${Math.floor(diffInSeconds / 86400)} days ago`
  } catch {
    return ''
  }
}

const getActivityTypeLabel = (type: string) => {
  switch (type) {
    case 'scan':
      return 'Repository Scan'
    case 'vulnerability':
      return 'Vulnerability'
    default:
      return type
  }
}

const getActivityTypeColor = (type: string) => {
  switch (type) {
    case 'scan':
      return 'primary'
    case 'vulnerability':
      return 'error'
    default:
      return 'grey'
  }
}

const getSeverityColor = (severity: string) => {
  switch (severity?.toUpperCase()) {
    case 'CRITICAL':
      return 'error'
    case 'HIGH':
      return 'warning'
    case 'MEDIUM':
      return 'info'
    case 'LOW':
      return 'success'
    default:
      return 'grey'
  }
}

const getStatusColor = (status: string) => {
  switch (status) {
    case 'success':
      return 'success'
    case 'error':
      return 'error'
    case 'in_process':
      return 'warning'
    case 'pending':
      return 'info'
    default:
      return 'grey'
  }
}

const formatStatusLabel = (status: string) => {
  switch (status) {
    case 'success':
      return 'Success'
    case 'error':
      return 'Error'
    case 'in_process':
      return 'Processing'
    case 'pending':
      return 'Pending'
    default:
      return status
  }
}

watch([page, itemsPerPage], fetchActivities)
watch(selectedActivityType, () => {
  if (page.value !== 1) {
    page.value = 1
    return
  }
  fetchActivities()
})

onMounted(() => {
  fetchActivities()
})
</script>

<style scoped>
.page-shell {
  padding-top: 24px;
  padding-bottom: 32px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}

.activities-card {
  overflow: hidden;
}

.filters-bar {
  display: flex;
  justify-content: flex-start;
  padding: 16px 16px 0;
}

.activity-type-filter {
  max-width: 280px;
}

.activities-table {
  width: 100%;
}

.activity-link {
  padding: 0;
  border: 0;
  background: none;
  color: #1f2937;
  text-align: left;
  font: inherit;
  font-weight: 500;
  cursor: pointer;
}

.activity-link:hover {
  text-decoration: underline;
}

.activity-link--disabled {
  color: #6b7280;
  cursor: default;
}

.activity-link--disabled:hover {
  text-decoration: none;
}

.timestamp-cell {
  line-height: 1.2;
}

.timestamp-cell__relative {
  color: #6b7280;
  font-size: 0.85rem;
  margin-top: 4px;
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: stretch;
  }

  .activity-type-filter {
    max-width: 100%;
    width: 100%;
  }
}
</style>
