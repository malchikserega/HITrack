<template>
  <v-card class="activity-card" elevation="2">
    <v-card-title class="text-h6 font-weight-bold pa-4 pb-2 d-flex align-center justify-space-between">
      <span>Recent Activity</span>
      <v-btn
        v-if="showViewAll"
        variant="text"
        color="primary"
        size="small"
        @click="emit('view-all')"
      >
        View All
      </v-btn>
    </v-card-title>
    <v-card-text class="pa-4 pt-0">
      <div v-if="!activities || activities.length === 0" class="text-center pa-8">
        <v-icon size="48" color="grey">mdi-clock-outline</v-icon>
        <p class="text-body-2 text-medium-emphasis mt-2">No recent activity</p>
      </div>
      <v-list v-else class="activity-list">
        <v-list-item
          v-for="(activity, index) in activities"
          :key="index"
          :to="getActivityRoute(activity) || undefined"
          :link="hasActivityRoute(activity)"
          class="activity-item"
          :class="{ 'activity-item--link': hasActivityRoute(activity) }"
        >
          <template #prepend>
            <v-avatar :color="getActivityColor(activity.type)" size="32">
              <v-icon :icon="getActivityIcon(activity.type)" size="16" color="white" />
            </v-avatar>
          </template>
          
          <v-list-item-title class="activity-title">
            {{ activity.title }}
          </v-list-item-title>
          
          <v-list-item-subtitle class="activity-subtitle">
            {{ formatTimestamp(activity.timestamp) }}
          </v-list-item-subtitle>
          
          <template #append>
            <v-chip
              v-if="activity.severity"
              :color="getSeverityColor(activity.severity)"
              size="small"
              variant="tonal"
            >
              {{ activity.severity }}
            </v-chip>
            <v-chip
              v-else-if="activity.status"
              :color="getStatusColor(activity.status)"
              size="small"
              variant="tonal"
            >
              {{ activity.status }}
            </v-chip>
          </template>
        </v-list-item>
      </v-list>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
// Simple date formatting function
const formatDistanceToNow = (date: Date) => {
  const now = new Date()
  const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000)
  
  if (diffInSeconds < 60) return 'just now'
  if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)} minutes ago`
  if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)} hours ago`
  if (diffInSeconds < 2592000) return `${Math.floor(diffInSeconds / 86400)} days ago`
  
  return date.toLocaleDateString()
}

interface Activity {
  type: 'scan' | 'vulnerability'
  title: string
  timestamp: string
  severity?: string
  status?: string
  target_type?: 'repository' | 'vulnerability' | 'image' | 'component' | 'repository_tag' | 'release'
  target_uuid?: string
}

interface Props {
  activities: Activity[]
  showViewAll?: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'view-all'): void
}>()

const hasActivityRoute = (activity: Activity) => Boolean(getActivityRoute(activity))

const getActivityRoute = (activity: Activity) => {
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

const getActivityIcon = (type: string) => {
  switch (type) {
    case 'scan':
      return 'mdi-refresh'
    case 'vulnerability':
      return 'mdi-bug'
    default:
      return 'mdi-information'
  }
}

const getActivityColor = (type: string) => {
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

const formatTimestamp = (timestamp: string) => {
  try {
    return formatDistanceToNow(new Date(timestamp))
  } catch {
    return 'Unknown time'
  }
}
</script>

<style scoped>
.activity-card {
  border-radius: 12px;
  height: 100%;
}

.activity-list {
  background: transparent;
}

.activity-item {
  border-radius: 8px;
  margin-bottom: 8px;
  transition: background-color 0.2s ease;
}

.activity-item:hover {
  background-color: rgba(0, 0, 0, 0.04);
}

.activity-item--link {
  cursor: pointer;
}

.activity-item--link:hover .activity-title {
  text-decoration: underline;
}

.activity-title {
  font-weight: 500;
  color: #2c3e50;
  line-height: 1.3;
}

.activity-subtitle {
  color: #7f8c8d;
  font-size: 0.875rem;
}
</style> 
