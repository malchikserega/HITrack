<template>
  <div class="home">
    <v-container fluid>
      <!-- Header -->
      <v-row>
        <v-col cols="12">
          <div class="d-flex align-center justify-space-between mb-6">
            <div>
              <h1 class="text-h3 font-weight-black mb-2">Metrics</h1>
              <p class="text-body-1 text-medium-emphasis">Choose the red pill, choose the blue pill...</p>
            </div>
            <v-btn
              color="primary"
              prepend-icon="mdi-refresh"
              @click="refreshData"
              :loading="loading"
            >
              Refresh Data
            </v-btn>
          </div>
        </v-col>
      </v-row>

      <!-- Metrics Row -->
      <v-row>
        <v-col cols="12">
          <v-row justify="center">
            <v-col cols="12" sm="6" md="3">
              <MetricCard
                title="Critical Vulnerabilities"
                :value="dashboardData.security_metrics?.critical_vulnerabilities || 0"
                icon="mdi-alert-circle"
                color="error"
                :clickable="true"
                :clickAction="viewCriticalVulnerabilities"
              />
            </v-col>
            <v-col cols="12" sm="6" md="3">
              <MetricCard
                title="Fixable Vulnerabilities"
                :value="dashboardData.security_metrics?.fixable_vulnerabilities || 0"
                icon="mdi-check-circle"
                color="success"
                :subtitle="`${dashboardData.security_metrics?.fixable_percentage || 0}% of total`"
                :clickable="true"
                :clickAction="viewFixableVulnerabilities"
              />
            </v-col>
            <v-col cols="12" sm="6" md="3">
              <MetricCard
                title="Total Images"
                :value="dashboardData.basic_stats?.images || 0"
                icon="mdi-docker"
                color="info"
                :clickable="true"
                :clickAction="viewImages"
              />
            </v-col>
            <v-col cols="12" sm="6" md="3">
              <MetricCard
                title="Total Repositories"
                :value="dashboardData.basic_stats?.repositories || 0"
                icon="mdi-git"
                color="primary"
                :clickable="true"
                :clickAction="viewRepositories"
              />
            </v-col>
          </v-row>
        </v-col>
      </v-row>

      <!-- Additional Security Metrics -->
      <v-row>
        <v-col cols="12">
          <v-row justify="center">
            <v-col cols="12" sm="6" md="3">
              <MetricCard
                title="CISA KEV Vulnerabilities"
                :value="dashboardData.security_metrics?.cisa_kev_vulnerabilities || 0"
                icon="mdi-shield-alert"
                color="error"
                :subtitle="`${dashboardData.security_metrics?.cisa_kev_percentage || 0}% of total`"
                :clickable="true"
                :clickAction="viewCisaKevVulnerabilities"
              />
            </v-col>
            <v-col cols="12" sm="6" md="3">
              <MetricCard
                title="Exploit Available"
                :value="dashboardData.security_metrics?.exploit_available_vulnerabilities || 0"
                icon="mdi-bug"
                color="warning"
                :subtitle="`${dashboardData.security_metrics?.exploit_percentage || 0}% of total`"
                :clickable="true"
                :clickAction="viewExploitVulnerabilities"
              />
            </v-col>
            <v-col cols="12" sm="6" md="3">
              <MetricCard
                title="Ransomware Vulnerabilities"
                :value="dashboardData.security_metrics?.ransomware_vulnerabilities || 0"
                icon="mdi-lock-alert"
                color="error"
                :subtitle="`${dashboardData.security_metrics?.ransomware_percentage || 0}% of total`"
                :clickable="true"
                :clickAction="viewRansomwareVulnerabilities"
              />
            </v-col>
            <v-col cols="12" sm="6" md="3">
              <MetricCard
                title="Vulnerabilities with Details"
                :value="dashboardData.security_metrics?.vulnerabilities_with_details || 0"
                icon="mdi-information"
                color="info"
                :subtitle="`${dashboardData.security_metrics?.details_percentage || 0}% of total`"
                :clickable="true"
                :clickAction="viewVulnerabilitiesWithDetails"
              />
            </v-col>
          </v-row>
        </v-col>
      </v-row>

      <!-- Charts Row 1 -->
      <v-row>
        <v-col cols="12" md="6">
          <SeverityDistributionChart :data="dashboardData.severity_distribution || []" />
        </v-col>
        <v-col cols="12" md="6">
          <VulnerabilityTrendChart :data="dashboardData.vulnerability_trends || []" />
        </v-col>
      </v-row>

      <!-- Charts Row 2 -->
      <v-row>
        <v-col cols="12" md="6">
          <v-card class="chart-card" elevation="2">
            <v-card-title class="text-h6 font-weight-bold pa-4 pb-2">
              Top Vulnerable Components
            </v-card-title>
            <v-card-text class="pa-4 pt-0">
              <div v-if="!dashboardData.top_vulnerable_components || dashboardData.top_vulnerable_components.length === 0" class="text-center pa-8">
                <v-icon size="48" color="grey">mdi-cube-outline</v-icon>
                <p class="text-body-2 text-medium-emphasis mt-2">No vulnerable components found</p>
              </div>
              <v-list v-else class="component-list">
                <v-list-item
                  v-for="(component, index) in dashboardData.top_vulnerable_components"
                  :key="index"
                  class="component-item"
                >
                  <template #prepend>
                    <v-avatar color="error" size="32">
                      <span class="text-white font-weight-bold">{{ index + 1 }}</span>
                    </v-avatar>
                  </template>
                  
                  <v-list-item-title class="component-title">
                    {{ component.name }}
                  </v-list-item-title>
                  
                  <v-list-item-subtitle class="component-subtitle">
                    Version: {{ component.version }}
                  </v-list-item-subtitle>
                  
                  <template #append>
                    <v-chip
                      color="error"
                      size="small"
                      variant="tonal"
                    >
                      {{ component.vulnerability_count }} vulns
                    </v-chip>
                  </template>
                </v-list-item>
              </v-list>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="6">
          <v-card class="chart-card" elevation="2">
            <v-card-title class="text-h6 font-weight-bold pa-4 pb-2">
              Top 10 Vulnerabilities by EPSS
            </v-card-title>
            <v-card-text class="pa-4 pt-0">
              <div v-if="!dashboardData.top_vulnerabilities_by_epss || dashboardData.top_vulnerabilities_by_epss.length === 0" class="text-center pa-8">
                <v-icon size="48" color="grey">mdi-shield-alert</v-icon>
                <p class="text-body-2 text-medium-emphasis mt-2">No vulnerabilities with EPSS data found</p>
              </div>
              <v-list v-else class="vulnerability-list">
                <v-list-item
                  v-for="(vuln, index) in dashboardData.top_vulnerabilities_by_epss"
                  :key="index"
                  class="vulnerability-item clickable"
                  @click="viewVulnerabilityDetail(vuln.uuid)"
                >
                  <template #prepend>
                    <v-avatar :color="getSeverityColor(vuln.severity)" size="32">
                      <span class="text-white font-weight-bold">{{ index + 1 }}</span>
                    </v-avatar>
                  </template>
                  
                  <v-list-item-title class="vulnerability-title">
                    {{ vuln.vulnerability_id }}
                  </v-list-item-title>
                  
                  <v-list-item-subtitle class="vulnerability-subtitle">
                    {{ vuln.description }}
                  </v-list-item-subtitle>
                  
                  <template #append>
                    <div class="vulnerability-epss">
                      <v-chip
                        :size="'small'"
                        :color="getEpssColor(vuln.epss)"
                        class="mr-2"
                      >
                        EPSS: {{ vuln.epss }}
                      </v-chip>
                      <!-- EPSS Source Indicator -->
                      <v-tooltip v-if="vuln.details?.epss_data_source" location="top">
                        <template v-slot:activator="{ props }">
                          <v-icon
                            v-bind="props"
                            size="16"
                            :color="getEpssSourceColor(vuln.details.epss_data_source)"
                            class="epss-source-icon"
                          >
                            {{ getEpssSourceIcon(vuln.details.epss_data_source) }}
                          </v-icon>
                        </template>
                        <span>{{ getEpssSourceDisplay(vuln.details.epss_data_source) }}</span>
                      </v-tooltip>
                    </div>
                  </template>
                </v-list-item>
              </v-list>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- Activity and Quick Actions -->
      <v-row>
        <v-col cols="12" md="6">
          <RecentActivityFeed :activities="dashboardData.recent_activities || []" />
        </v-col>
        <v-col cols="12" md="3">
          <RecentTasksCard />
        </v-col>
        <v-col cols="12" md="3">
          <v-card class="quick-actions-card" elevation="2">
            <v-card-title class="text-h6 font-weight-bold pa-4 pb-2">
              Quick Actions
            </v-card-title>
            <v-card-text class="pa-4 pt-0">
              <div class="actions-grid">
                <v-btn
                  block
                  color="primary"
                  prepend-icon="mdi-refresh"
                  @click="scanAllRepositories"
                  :loading="scanning"
                  class="action-btn"
                >
                  Scan All Repositories
                </v-btn>
                
                <v-btn
                  block
                  color="secondary"
                  prepend-icon="mdi-file-document"
                  @click="generateReport"
                  class="action-btn"
                >
                  Generate Security Report
                </v-btn>
                
                <v-btn
                  block
                  color="info"
                  prepend-icon="mdi-plus"
                  @click="addRepository"
                  class="action-btn"
                >
                  Add Repository
                </v-btn>
                
                <v-btn
                  block
                  color="warning"
                  prepend-icon="mdi-alert"
                  @click="viewCriticalVulnerabilities"
                  class="action-btn"
                >
                  View Critical Issues
                </v-btn>
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </v-container>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../plugins/axios'
import { notificationService } from '../plugins/notifications'
import { useTheme } from 'vuetify'
import { useThemeStore } from '../stores/theme'

import MetricCard from '../components/MetricCard.vue'
import SeverityDistributionChart from '../components/SeverityDistributionChart.vue'
import VulnerabilityTrendChart from '../components/VulnerabilityTrendChart.vue'
import RecentActivityFeed from '../components/RecentActivityFeed.vue'
import RecentTasksCard from '../components/RecentTasksCard.vue'
import { getVulnerabilityTypeColor, getSeverityColor, getEpssColor, getEpssSourceColor, getEpssSourceIcon, getEpssSourceDisplay } from '../utils/colors'

const router = useRouter()
const theme = useTheme()
const themeStore = useThemeStore()

// Data
const dashboardData = ref<any>({})
const loading = ref(false)
const scanning = ref(false)

// Easter egg
let keyBuffer = ''

function handleKeydown(e: KeyboardEvent) {
  const tag = (e.target as HTMLElement)?.tagName?.toLowerCase()
  if (tag === 'input' || tag === 'textarea' || (e.target as HTMLElement)?.isContentEditable) return
  keyBuffer += e.key
  if (keyBuffer.length > 4) keyBuffer = keyBuffer.slice(-4)
  if (keyBuffer === '1337') {
    theme.global.name.value = 'matrix'
    keyBuffer = ''
  }
}

const fetchDashboardData = async () => {
  loading.value = true
  try {
    const response = await api.get('stats/dashboard_metrics/')
    dashboardData.value = response.data
  } catch (error) {
    console.error('Error fetching dashboard data:', error)
    notificationService.error('Failed to fetch dashboard data')
  } finally {
    loading.value = false
  }
}

const refreshData = () => {
  fetchDashboardData()
}

const scanAllRepositories = async () => {
  scanning.value = true
  try {
    // This would be implemented based on your API
    notificationService.success('Repository scan initiated')
  } catch (error) {
    notificationService.error('Failed to initiate scan')
  } finally {
    scanning.value = false
  }
}

const generateReport = () => {
  router.push('/reports')
}

const addRepository = () => {
  router.push('/acr')
}

const viewCriticalVulnerabilities = () => {
  router.push('/vulnerabilities?severity=CRITICAL')
}

const viewFixableVulnerabilities = () => {
  router.push('/vulnerabilities?fixable=true')
}

const viewCisaKevVulnerabilities = () => {
  router.push('/vulnerabilities?cisa_kev=true')
}

const viewExploitVulnerabilities = () => {
  router.push('/vulnerabilities?exploit_available=true')
}

const viewRansomwareVulnerabilities = () => {
  router.push('/vulnerabilities?ransomware=true')
}

const viewImages = () => {
  router.push('/images')
}

const viewRepositories = () => {
  router.push('/repositories')
}

const viewVulnerabilitiesWithDetails = () => {
  router.push('/vulnerabilities?has_details=true')
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

const getStatusIcon = (status: string) => {
  switch (status) {
    case 'success':
      return 'mdi-check-circle'
    case 'error':
      return 'mdi-alert-circle'
    case 'in_process':
      return 'mdi-sync'
    case 'pending':
      return 'mdi-clock'
    default:
      return 'mdi-help-circle'
  }
}

const formatStatusLabel = (status: string) => {
  switch (status) {
    case 'success':
      return 'Successfully Scanned'
    case 'error':
      return 'Scan Failed'
    case 'in_process':
      return 'Scanning'
    case 'pending':
      return 'Pending'
    default:
      return 'Unknown'
  }
}

const viewVulnerabilityDetail = (vulnerabilityId: string) => {
  router.push(`/vulnerabilities/${vulnerabilityId}`)
}

onMounted(() => {
  fetchDashboardData()
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.home {
  padding: 20px;
  background: #ffffff;
  min-height: 100vh;
}


/* Matrix theme override */
.v-theme--matrix .home {
  background: #000 !important;
}

.v-theme--matrix .chart-card {
  background: #000 !important;
  border: 1px solid #39FF14 !important;
}

.v-theme--matrix .quick-actions-card {
  background: #000 !important;
  border: 1px solid #39FF14 !important;
}

/* Matrix theme for all cards */
.v-theme--matrix :deep(.v-card) {
  background: #000 !important;
  border: 1px solid #39FF14 !important;
}

.v-theme--matrix :deep(.metric-card) {
  background: #000 !important;
  border: 1px solid #39FF14 !important;
}

.v-theme--matrix :deep(.trend-chart-card) {
  background: #000 !important;
  border: 1px solid #39FF14 !important;
}

.v-theme--matrix :deep(.severity-chart-card) {
  background: #000 !important;
  border: 1px solid #39FF14 !important;
}

.chart-card {
  border-radius: 12px;
  height: 100%;
}

.component-list {
  background: transparent;
}

.component-item {
  border-radius: 8px;
  margin-bottom: 8px;
  transition: background-color 0.2s ease;
}

.component-item:hover {
  background-color: rgba(0, 0, 0, 0.04);
}

.component-title {
  font-weight: 500;
  color: #2c3e50;
  line-height: 1.3;
}

.vulnerability-list {
  background: transparent;
}

.vulnerability-item {
  border-radius: 8px;
  margin-bottom: 8px;
  transition: background-color 0.2s ease;
}

.vulnerability-item.clickable {
  cursor: pointer;
}

.vulnerability-item.clickable:hover {
  background-color: rgba(0, 0, 0, 0.08);
  transform: translateX(4px);
  transition: all 0.2s ease;
}

.vulnerability-title {
  font-weight: 500;
  color: #2c3e50;
  line-height: 1.3;
}

.vulnerability-subtitle {
  color: #666666;
  line-height: 1.2;
  margin-top: 4px;
}

.vulnerability-epss {
  display: flex;
  align-items: center;
}

.epss-source-icon {
  margin-left: 4px;
}

.component-subtitle {
  color: #7f8c8d;
  font-size: 0.875rem;
}

.status-grid {
  display: grid;
  gap: 16px;
}

.status-item {
  display: flex;
  align-items: center;
  padding: 12px;
  border-radius: 8px;
  background-color: rgba(0, 0, 0, 0.02);
  transition: background-color 0.2s ease;
}

.status-item:hover {
  background-color: rgba(0, 0, 0, 0.04);
}

.status-icon {
  margin-right: 12px;
}

.status-info {
  flex: 1;
}

.status-label {
  font-weight: 500;
  color: #2c3e50;
  font-size: 0.875rem;
}

.status-count {
  color: #7f8c8d;
  font-size: 0.75rem;
}

.quick-actions-card {
  border-radius: 12px;
  height: 100%;
}

.actions-grid {
  display: grid;
  gap: 12px;
}

.action-btn {
  height: 48px;
  border-radius: 8px;
  font-weight: 500;
}


</style> 