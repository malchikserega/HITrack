<template>
  <v-card class="severity-chart-card" elevation="3">
    <v-card-title class="text-h6 font-weight-bold pa-4 pb-2 d-flex align-center">
      <v-icon class="mr-2" color="error">mdi-shield-alert</v-icon>
      Vulnerabilities by Severity
    </v-card-title>
    <v-card-text class="pa-4 pt-0">
      <div v-if="!data || data.length === 0" class="text-center pa-8">
        <v-icon size="48" color="grey">mdi-chart-pie</v-icon>
        <p class="text-body-2 text-medium-emphasis mt-2">No vulnerability data available</p>
      </div>
      <div v-else class="severity-container">
        <!-- 3D Severity Cards -->
        <div class="severity-grid">
          <div
            v-for="(item, index) in severityData"
            :key="item.severity"
            class="severity-card"
            :class="`severity-${item.severity.toLowerCase()}`"
            @click="selectSeverity(item.severity)"
            :style="{ animationDelay: `${index * 0.1}s` }"
          >
            <div class="severity-icon">
              <v-icon :color="getSeverityIconColor(item.severity)" size="32">
                {{ getSeverityIcon(item.severity) }}
              </v-icon>
            </div>
            <div class="severity-content">
              <div class="severity-label">{{ getSeverityLabel(item.severity) }}</div>
              <div class="severity-count">{{ item.count }}</div>
              <div class="severity-percentage">{{ getPercentage(item.count) }}%</div>
            </div>
            <div class="severity-bar" :style="{ width: getPercentage(item.count) + '%' }"></div>
          </div>
        </div>



        <!-- Severity Stats -->
        <div class="stats-section mt-6">
          <div class="stats-grid">
            <div class="stat-item">
              <div class="stat-label">Total Vulnerabilities</div>
              <div class="stat-value">{{ totalVulnerabilities }}</div>
            </div>
            <div class="stat-item">
              <div class="stat-label">Critical & High</div>
              <div class="stat-value critical">{{ criticalHighCount }}</div>
            </div>
            <div class="stat-item">
              <div class="stat-label d-flex align-center">
                Risk Score
                <v-tooltip location="top" max-width="300">
                  <template v-slot:activator="{ props }">
                    <v-icon
                      v-bind="props"
                      size="16"
                      color="grey"
                      class="ml-1 cursor-help"
                    >
                      mdi-information-outline
                    </v-icon>
                  </template>
                  <div class="tooltip-content">
                    <div class="tooltip-title font-weight-bold mb-2">Risk Score Calculation</div>
                    <div class="tooltip-text">
                      <div class="mb-1">• Critical: 1.0 point each</div>
                      <div class="mb-1">• High: 0.75 points each</div>
                      <div class="mb-1">• Medium: 0.5 points each</div>
                      <div class="mb-2">• Low: 0.25 points each</div>
                      <div class="tooltip-formula">
                        Score = (Critical × 1.0) + (High × 0.75) + (Medium × 0.5) + (Low × 0.25)
                      </div>
                      <div class="tooltip-note mt-2">
                        <strong>Scale:</strong> No upper limit (Higher = More Risk)
                      </div>
                    </div>
                  </div>
                </v-tooltip>
              </div>
              <div class="stat-value" :class="getRiskScoreClass()">{{ riskScore }}</div>
            </div>
          </div>
        </div>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

interface SeverityData {
  severity: string
  count: number
}

interface Props {
  data: SeverityData[]
}

const props = defineProps<Props>()
const selectedSeverity = ref<string | null>(null)

const severityColors = {
  'CRITICAL': '#f44336',
  'HIGH': '#ff9800',
  'MEDIUM': '#ffc107',
  'LOW': '#4caf50',
  'UNKNOWN': '#9e9e9e'
}

const severityLabels = {
  'CRITICAL': 'Critical',
  'HIGH': 'High',
  'MEDIUM': 'Medium',
  'LOW': 'Low',
  'UNKNOWN': 'Unknown'
}

const severityIcons = {
  'CRITICAL': 'mdi-alert-circle',
  'HIGH': 'mdi-alert',
  'MEDIUM': 'mdi-information',
  'LOW': 'mdi-check-circle',
  'UNKNOWN': 'mdi-help-circle'
}

const severityData = computed(() => {
  if (!props.data) return []
  return props.data.sort((a, b) => {
    const order = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN']
    return order.indexOf(a.severity) - order.indexOf(b.severity)
  })
})

const totalVulnerabilities = computed(() => {
  return severityData.value.reduce((sum, item) => sum + item.count, 0)
})

const criticalHighCount = computed(() => {
  return severityData.value
    .filter(item => ['CRITICAL', 'HIGH'].includes(item.severity))
    .reduce((sum, item) => sum + item.count, 0)
})

const riskScore = computed(() => {
  const critical = severityData.value.find(item => item.severity === 'CRITICAL')?.count || 0
  const high = severityData.value.find(item => item.severity === 'HIGH')?.count || 0
  const medium = severityData.value.find(item => item.severity === 'MEDIUM')?.count || 0
  const low = severityData.value.find(item => item.severity === 'LOW')?.count || 0
  
  const rawScore = critical * 1 + high * 0.75 + medium * 0.5 + low * 0.25
  
  // No limits - show real score
  return Math.round(rawScore)
})

const getSeverityColor = (severity: string) => {
  return severityColors[severity as keyof typeof severityColors] || '#9e9e9e'
}

const getSeverityIconColor = (severity: string) => {
  return severityColors[severity as keyof typeof severityColors] || '#9e9e9e'
}

const getSeverityIcon = (severity: string) => {
  return severityIcons[severity as keyof typeof severityIcons] || 'mdi-help-circle'
}

const getSeverityLabel = (severity: string) => {
  return severityLabels[severity as keyof typeof severityLabels] || severity
}

const getPercentage = (count: number) => {
  if (totalVulnerabilities.value === 0) return 0
  return Math.round((count / totalVulnerabilities.value) * 100)
}

const getRiskScoreClass = () => {
  if (riskScore.value >= 150) return 'critical'
  if (riskScore.value >= 100) return 'warning'
  if (riskScore.value >= 50) return 'info'
  return 'success'
}

const selectSeverity = (severity: string) => {
  selectedSeverity.value = selectedSeverity.value === severity ? null : severity
}


</script>

<style scoped>
.severity-chart-card {
  border-radius: 16px;
  height: 100%;
  background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
  border: 1px solid rgba(0, 0, 0, 0.05);
}

.severity-container {
  padding: 8px;
}

.severity-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
}

.severity-card {
  position: relative;
  padding: 20px;
  border-radius: 12px;
  background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
  border: 2px solid transparent;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  animation: slideInUp 0.6s ease-out forwards;
  opacity: 0;
  transform: translateY(20px);
}

.severity-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.15);
  border-color: rgba(0, 0, 0, 0.1);
}

.severity-card.severity-critical {
  background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%);
  border-color: #f44336;
}

.severity-card.severity-high {
  background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%);
  border-color: #ff9800;
}

.severity-card.severity-medium {
  background: linear-gradient(135deg, #fff8e1 0%, #ffecb3 100%);
  border-color: #ffc107;
}

.severity-card.severity-low {
  background: linear-gradient(135deg, #e8f5e8 0%, #c8e6c9 100%);
  border-color: #4caf50;
}

.severity-card.severity-unknown {
  background: linear-gradient(135deg, #f5f5f5 0%, #eeeeee 100%);
  border-color: #9e9e9e;
}

.severity-icon {
  margin-bottom: 12px;
  display: flex;
  justify-content: center;
}

.severity-content {
  text-align: center;
}

.severity-label {
  font-weight: 600;
  font-size: 0.875rem;
  color: #2c3e50;
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.severity-count {
  font-size: 2rem;
  font-weight: 700;
  color: #1a237e;
  margin-bottom: 4px;
}

.severity-percentage {
  font-size: 0.875rem;
  color: #666666;
  font-weight: 500;
}

.severity-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  height: 4px;
  background: linear-gradient(90deg, #1976d2, #42a5f5);
  border-radius: 0 0 10px 10px;
  transition: width 0.3s ease;
}



.stats-section {
  background: rgba(255, 255, 255, 0.8);
  border-radius: 12px;
  padding: 16px;
  border: 1px solid rgba(0, 0, 0, 0.05);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 16px;
}

.stat-item {
  text-align: center;
  padding: 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid rgba(0, 0, 0, 0.05);
}

.stat-label {
  font-size: 0.75rem;
  color: #666666;
  font-weight: 500;
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #2c3e50;
}

.stat-value.critical {
  color: #f44336;
}

.stat-value.warning {
  color: #ff9800;
}

.stat-value.info {
  color: #2196f3;
}

.stat-value.success {
  color: #4caf50;
}

@keyframes slideInUp {
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.cursor-help {
  cursor: help;
}

.tooltip-content {
  padding: 4px;
}

.tooltip-title {
  color: #1976d2;
  font-size: 0.875rem;
}

.tooltip-text {
  font-size: 0.75rem;
  line-height: 1.4;
}

.tooltip-formula {
  background: rgba(25, 118, 210, 0.1);
  padding: 8px;
  border-radius: 6px;
  font-family: 'Courier New', monospace;
  font-size: 0.7rem;
  color: #1976d2;
  font-weight: 600;
}

.tooltip-note {
  font-size: 0.7rem;
  color: #666666;
  border-top: 1px solid rgba(0, 0, 0, 0.1);
  padding-top: 8px;
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .severity-grid {
    grid-template-columns: 1fr;
  }
  
  .stats-grid {
    grid-template-columns: 1fr;
  }
}

/* Matrix theme override */
.v-theme--matrix .severity-chart-card {
  background: #000 !important;
  border: 1px solid #39FF14 !important;
}

.v-theme--matrix .severity-chart-card .v-card-title {
  color: #39FF14 !important;
}

.v-theme--matrix .severity-chart-card .severity-card {
  background: #000 !important;
  border: 1px solid #39FF14 !important;
}

.v-theme--matrix .severity-chart-card .severity-label {
  color: #39FF14 !important;
}

.v-theme--matrix .severity-chart-card .severity-count {
  color: #39FF14 !important;
}

.v-theme--matrix .severity-chart-card .severity-percentage {
  color: #39FF14 !important;
}

.v-theme--matrix .severity-chart-card .stat-value {
  color: #39FF14 !important;
}

.v-theme--matrix .severity-chart-card .stat-label {
  color: #39FF14 !important;
}
</style> 