<template>
  <v-card 
    class="metric-card" 
    elevation="2" 
    :color="cardColor"
    :class="{ 'clickable': clickable }"
    @click="handleClick"
  >
    <div v-if="subtitle" class="metric-badge">
      {{ subtitle }}
    </div>
    <v-card-text class="text-center pa-4">
      <div class="metric-icon mb-3">
        <v-icon :color="iconColor" size="48">{{ icon }}</v-icon>
      </div>
      <div class="metric-value text-h4 font-weight-bold mb-2">
        {{ formattedValue }}
      </div>
      <div class="metric-title text-body-1 font-weight-medium">{{ title }}</div>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  title: string
  value: number
  icon: string
  color?: 'primary' | 'success' | 'warning' | 'error' | 'info'
  subtitle?: string
  format?: 'number' | 'percentage' | 'decimal'
  clickable?: boolean
  clickAction?: () => void
}

const props = withDefaults(defineProps<Props>(), {
  color: 'primary',
  format: 'number',
  clickable: false
})

const cardColor = computed(() => {
  const colors = {
    primary: '#f8f9fa',
    success: '#f1f8e9',
    warning: '#fff8e1',
    error: '#ffebee',
    info: '#e3f2fd'
  }
  return colors[props.color]
})

const iconColor = computed(() => {
  const colors = {
    primary: '#1976d2',
    success: '#4caf50',
    warning: '#ff9800',
    error: '#f44336',
    info: '#2196f3'
  }
  return colors[props.color]
})

const formattedValue = computed(() => {
  switch (props.format) {
    case 'percentage':
      return `${props.value}%`
    case 'decimal':
      // For EPSS show "N/A" if value is 0, otherwise format
      if (props.value === 0) {
        return 'N/A'
      }
      return props.value.toFixed(3)
    default:
      return props.value.toLocaleString()
  }
})

const handleClick = () => {
  if (props.clickable && props.clickAction) {
    props.clickAction()
  }
}
</script>

<style scoped>
.metric-card {
  border-radius: 12px;
  transition: all 0.3s ease;
  min-height: 140px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.metric-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
}

.metric-card.clickable {
  cursor: pointer;
}

.metric-card.clickable:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.15);
}

/* Matrix theme override */
.v-theme--matrix .metric-card {
  background: #000 !important;
  border: 1px solid #39FF14 !important;
}

.v-theme--matrix .metric-card .metric-value {
  color: #39FF14 !important;
}

.v-theme--matrix .metric-card .metric-title {
  color: #39FF14 !important;
}

.v-theme--matrix .metric-card .metric-badge {
  color: #39FF14 !important;
  background: rgba(57, 255, 20, 0.1) !important;
}

.metric-icon {
  display: flex;
  justify-content: center;
}

.metric-value {
  color: #2c3e50;
  line-height: 1.2;
}

.metric-title {
  color: #34495e;
  line-height: 1.3;
}

.metric-card {
  border-radius: 12px;
  transition: all 0.3s ease;
  min-height: 140px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  position: relative;
}

.metric-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  background: rgba(0, 0, 0, 0.1);
  color: #666666;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 500;
  z-index: 1;
}
</style> 