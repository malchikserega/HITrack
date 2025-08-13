<template>
  <div class="task-result-display">
    <!-- Main Content -->
    <div class="result-content">
      <!-- Task Name -->
      <div v-if="result.task_name" class="task-name">
        <v-icon class="task-icon">mdi-play-circle</v-icon>
        {{ result.task_name }}
      </div>

      <!-- Message -->
      <div v-if="result.message" class="message">
        <v-icon class="message-icon">mdi-information</v-icon>
        {{ result.message }}
      </div>

      <!-- Raw Result Data (Code Block Style) -->
      <div class="raw-result-section">
        <div class="code-block-header">
          <span class="code-block-title">Result Data</span>
          <v-btn
            icon
            small
            @click="toggleRawData"
            class="expand-btn"
            :color="showRawData ? 'primary' : 'grey'"
          >
            <v-icon>{{ showRawData ? 'mdi-chevron-up' : 'mdi-chevron-down' }}</v-icon>
          </v-btn>
        </div>
        
        <v-expand-transition>
          <div v-show="showRawData" class="code-block-content">
            <pre class="json-code">{{ formatJsonData() }}</pre>
          </div>
        </v-expand-transition>
      </div>

      <!-- Timestamp -->
      <div v-if="result.timestamp" class="timestamp-section">
        <v-icon class="timestamp-icon">mdi-clock</v-icon>
        <span class="timestamp-text">{{ formatTimestamp(result.timestamp) }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

interface TaskResult {
  task_name?: string
  message?: string
  timestamp?: string
  [key: string]: any
}

interface Props {
  result: TaskResult
}

const props = defineProps<Props>()

// State for raw data display
const showRawData = ref(false)

// Helper functions
const toggleRawData = () => {
  showRawData.value = !showRawData.value
}

const formatJsonData = (): string => {
  try {
    return JSON.stringify(props.result, null, 2)
  } catch {
    return 'Error formatting data'
  }
}

const formatTimestamp = (timestamp: string): string => {
  try {
    return new Date(timestamp).toLocaleString()
  } catch {
    return timestamp
  }
}
</script>

<style scoped>
.task-result-display {
  font-family: 'Roboto', sans-serif;
}

.result-content {
  padding: 20px;
}

.task-name {
  display: flex;
  align-items: center;
  font-size: 20px;
  font-weight: 600;
  color: #333;
  margin-bottom: 20px;
  padding: 16px;
  background: #f5f5f5;
  border-radius: 8px;
}

.task-icon {
  margin-right: 12px;
  color: #2196f3;
}

.message {
  display: flex;
  align-items: center;
  font-size: 16px;
  color: #666;
  margin-bottom: 24px;
  padding: 16px;
  background: #e3f2fd;
  border-radius: 8px;
  border-left: 4px solid #2196f3;
}

.message-icon {
  margin-right: 12px;
  color: #2196f3;
}

/* Raw Result Data Styling */
.raw-result-section {
  margin-top: 20px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  overflow: hidden;
}

.code-block-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f5f5f5;
  border-bottom: 1px solid #e0e0e0;
}

.code-block-title {
  font-weight: 600;
  color: #333;
  font-size: 14px;
}

.expand-btn {
  transition: all 0.2s ease;
}

.code-block-content {
  background: #f8f9fa;
  border-top: 1px solid #e0e0e0;
}

.json-code {
  margin: 0;
  padding: 16px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 12px;
  line-height: 1.4;
  color: #333;
  background: #f8f9fa;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 400px;
  overflow-y: auto;
}

.timestamp-section {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 24px;
  padding: 16px;
  background: #f5f5f5;
  border-radius: 8px;
  color: #666;
  font-size: 14px;
}

.timestamp-icon {
  margin-right: 8px;
  color: #999;
}
</style>
