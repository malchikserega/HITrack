<template>
  <v-card class="activity-card" elevation="2">
    <v-card-title class="text-h6 font-weight-bold pa-4 pb-2">
      Recent Activity
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
          class="activity-item"
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
}

interface Props {
  activities: Activity[]
}

const props = defineProps<Props>()

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