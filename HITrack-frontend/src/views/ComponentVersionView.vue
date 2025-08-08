<template>
  <div class="component-version-detail">
    <!-- Back Button -->
    <v-btn
      variant="text"
      @click="goBack"
      class="mb-4"
      prepend-icon="mdi-arrow-left"
    >
      Back to Component
    </v-btn>

    <!-- Loading State -->
    <div v-if="loading" class="loading-container">
      <v-progress-circular indeterminate size="64" color="primary"></v-progress-circular>
      <p class="mt-4">Loading version details...</p>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="error-container">
      <v-icon size="64" color="error">mdi-alert-circle</v-icon>
      <h3 class="mt-4">Error Loading Version</h3>
      <p class="text-grey">{{ error }}</p>
      <v-btn @click="loadVersion" class="mt-4">Retry</v-btn>
    </div>

    <!-- Version Details -->
    <div v-else-if="version" class="version-content">
      <!-- Header Section -->
      <v-card class="header-card mb-6">
        <v-card-text>
          <div class="version-header">
            <div class="version-info">
              <h1 class="text-h4 mb-2">
                {{ version.component?.name }} {{ version.version }}
              </h1>
              <div class="version-meta">
                <v-chip
                  size="small"
                  :color="getTypeColor(version.component?.type)"
                  class="mr-2"
                >
                  {{ version.component?.type }}
                </v-chip>
                <span class="text-caption text-grey">
                  Created: {{ formatDate(version.created_at) }}
                </span>
              </div>
            </div>
            <div class="version-stats">
              <div class="stat-card">
                <div class="stat-value">{{ version.used_count || 0 }}</div>
                <div class="stat-label">Used In</div>
              </div>
              <div class="stat-card">
                <div class="stat-value">{{ version.vulnerabilities_count || 0 }}</div>
                <div class="stat-label">Vulnerabilities</div>
              </div>
              <div class="stat-card">
                <div class="stat-value">
                  <span v-if="locationsLoading">
                    <v-progress-circular size="16" width="2" indeterminate></v-progress-circular>
                  </span>
                  <span v-else>{{ version?.locations_count || versionLocations.length }}</span>
                </div>
                <div class="stat-label">Locations</div>
              </div>
            </div>
          </div>
        </v-card-text>
      </v-card>

      <!-- Content Grid -->
      <v-row>
        <!-- Locations Section -->
        <v-col cols="12" md="6">
          <v-card class="info-card">
            <v-card-title class="d-flex align-center">
              <v-icon class="mr-2" color="primary">mdi-map-marker</v-icon>
              Locations
              <v-chip v-if="route.query.fromImage" size="small" color="info" variant="tonal" class="mx-2">
                <v-icon size="12" class="mr-1">mdi-filter</v-icon>
                Filtered by Image
              </v-chip>
              <v-spacer></v-spacer>
              <v-chip size="small" color="primary">
                <span v-if="locationsLoading">
                  <v-progress-circular size="12" width="2" indeterminate></v-progress-circular>
                </span>
                <span v-else>{{ version?.locations_count || versionLocations.length }}</span>
              </v-chip>
            </v-card-title>
            
            <v-card-text>
              <div v-if="locationsLoading" class="loading-state">
                <v-progress-circular indeterminate color="primary" size="32"></v-progress-circular>
                <p class="text-grey mt-2">Loading locations...</p>
              </div>
              <div v-else-if="versionLocations.length === 0" class="empty-state">
                <v-icon size="48" color="grey">mdi-map-marker-off</v-icon>
                <p class="text-grey mt-2">
                  <span v-if="route.query.fromImage">No locations found in this image</span>
                  <span v-else>No locations found</span>
                </p>
                <v-btn v-if="route.query.fromImage" 
                       @click="showAllLocations" 
                       variant="outlined" 
                       color="primary" 
                       size="small" 
                       class="mt-2">
                  Show All Locations
                </v-btn>
              </div>
              
              <div v-else class="locations-list">
                <!-- Show filter notice and option to see all -->
                <div v-if="route.query.fromImage" class="filter-notice mb-3">
                  <v-alert type="info" variant="tonal" density="compact">
                    <div class="d-flex align-center justify-space-between">
                      <span>Showing locations from specific image only</span>
                      <v-btn @click="showAllLocations" 
                             variant="text" 
                             size="small" 
                             color="primary">
                        Show All
                      </v-btn>
                    </div>
                  </v-alert>
                </div>
                <v-expansion-panels variant="accordion">
                  <v-expansion-panel
                    v-for="(location, index) in versionLocations"
                    :key="index"
                    class="location-panel"
                  >
                    <v-expansion-panel-title>
                      <div class="location-header">
                        <v-icon size="small" class="mr-2">mdi-file</v-icon>
                        <span class="location-path">{{ location.path }}</span>
                        <v-chip
                          size="small"
                          :color="getEvidenceColor(location.evidence_type)"
                          variant="tonal"
                          class="ml-auto evidence-chip"
                        >
                          {{ location.evidence_type }}
                        </v-chip>
                      </div>
                    </v-expansion-panel-title>
                    
                    <v-expansion-panel-text>
                      <div class="location-details">
                        <div class="detail-row">
                          <span class="detail-label">Image:</span>
                          <span class="detail-value">{{ location.image?.name || 'Unknown' }}</span>
                        </div>
                        
                        <div class="detail-row" v-if="location.layer_id">
                          <span class="detail-label">Layer ID:</span>
                          <span class="detail-value font-mono text-caption">{{ location.layer_id }}</span>
                        </div>
                        
                        <div class="detail-row" v-if="location.access_path">
                          <span class="detail-label">Access Path:</span>
                          <span class="detail-value font-mono text-caption">{{ location.access_path }}</span>
                        </div>
                        
                        <div class="detail-row" v-if="location.annotations && Object.keys(location.annotations).length">
                          <span class="detail-label">Annotations:</span>
                          <pre class="detail-value text-caption">{{ JSON.stringify(location.annotations, null, 2) }}</pre>
                        </div>
                      </div>
                    </v-expansion-panel-text>
                  </v-expansion-panel>
                </v-expansion-panels>
              </div>
            </v-card-text>
          </v-card>
        </v-col>

        <!-- Vulnerabilities Section -->
        <v-col cols="12" md="6">
          <v-card class="info-card">
            <v-card-title class="d-flex align-center">
              <v-icon class="mr-2" color="warning">mdi-shield-alert</v-icon>
              Vulnerabilities
              <v-spacer></v-spacer>
              <v-chip size="small" color="warning">
                <span v-if="vulnerabilitiesLoading">
                  <v-progress-circular size="12" width="2" indeterminate></v-progress-circular>
                </span>
                <span v-else>{{ version?.vulnerabilities_count || versionVulnerabilities.length }}</span>
              </v-chip>
            </v-card-title>
            
            <v-card-text>
              <div v-if="vulnerabilitiesLoading" class="loading-state">
                <v-progress-circular indeterminate color="primary" size="32"></v-progress-circular>
                <p class="text-grey mt-2">Loading vulnerabilities...</p>
              </div>
              <div v-else-if="versionVulnerabilities.length === 0" class="empty-state">
                <v-icon size="48" color="success">mdi-shield-check</v-icon>
                <p class="text-grey mt-2">No vulnerabilities found</p>
              </div>
              
              <div v-else class="vulnerabilities-list">
                <v-list>
                  <v-list-item
                    v-for="vulnerability in versionVulnerabilities"
                    :key="vulnerability.uuid"
                    @click="onVulnerabilityClick(vulnerability)"
                    class="vulnerability-item"
                  >
                    <template v-slot:prepend>
                      <v-icon :color="getSeverityColor(vulnerability.severity)">
                        mdi-shield-alert
                      </v-icon>
                    </template>
                    
                    <v-list-item-title class="vulnerability-title">
                      {{ vulnerability.vulnerability_id }}
                    </v-list-item-title>
                    
                    <v-list-item-subtitle class="vulnerability-subtitle">
                      {{ vulnerability.description?.substring(0, 100) }}{{ vulnerability.description?.length > 100 ? '...' : '' }}
                    </v-list-item-subtitle>
                    
                    <template v-slot:append>
                      <v-chip
                        size="small"
                        :color="getSeverityColor(vulnerability.severity)"
                        variant="tonal"
                      >
                        {{ vulnerability.severity }}
                      </v-chip>
                    </template>
                  </v-list-item>
                </v-list>
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- Images Section -->
      <v-row class="mt-6">
        <v-col cols="12">
          <v-card class="info-card">
            <v-card-title class="d-flex align-center">
              <v-icon class="mr-2" color="info">mdi-docker</v-icon>
              Used In Images
              <v-spacer></v-spacer>
              <v-chip size="small" color="info">{{ version.images?.length || 0 }}</v-chip>
            </v-card-title>
            
            <v-card-text>
              <div v-if="!version.images || version.images.length === 0" class="empty-state">
                <v-icon size="48" color="grey">mdi-docker</v-icon>
                <p class="text-grey mt-2">No images found</p>
              </div>
              
              <div v-else class="images-list">
                <v-list>
                  <v-list-item
                    v-for="image in version.images"
                    :key="image.uuid"
                    @click="goToImage(image.uuid)"
                    class="image-item"
                  >
                    <template v-slot:prepend>
                      <v-icon color="info">mdi-docker</v-icon>
                    </template>
                    
                    <v-list-item-title class="image-title">
                      {{ image.name || image.digest?.substring(0, 12) || image.uuid }}
                    </v-list-item-title>
                    
                    <v-list-item-subtitle class="image-subtitle">
                      {{ image.digest?.substring(0, 20) || 'No digest' }}
                    </v-list-item-subtitle>
                  </v-list-item>
                </v-list>
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/plugins/axios'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const locationsLoading = ref(false)
const vulnerabilitiesLoading = ref(false)
const error = ref(null)
const version = ref(null)
const versionLocations = ref([])
const versionVulnerabilities = ref([])

const loadVersion = async () => {
  loading.value = true
  error.value = null
  
  try {
    // Load main version data first - this is now optimized and includes images but not locations/vulnerabilities
    const response = await api.get(`/component-versions/${route.params.uuid}/`)
    version.value = response.data
    
    // Start lazy loading locations and vulnerabilities in parallel, but don't block the UI
    loadLocations()
    loadVulnerabilities()
    
  } catch (err) {
    console.error('Error loading version:', err)
    error.value = 'Failed to load version details'
  } finally {
    loading.value = false
  }
}

const loadLocations = async () => {
  locationsLoading.value = true
  try {
    // Check if we're filtering by specific image (came from ImageDetailView)
    const fromImageUuid = route.query.fromImage
    let url = `/component-versions/${route.params.uuid}/locations/`
    
    // Add image filter if specified
    if (fromImageUuid) {
      url += `?image=${fromImageUuid}`
    }
    
    const locationsResponse = await api.get(url)
    versionLocations.value = locationsResponse.data.locations || []
  } catch (err) {
    console.error('Error loading locations:', err)
    versionLocations.value = []
  } finally {
    locationsLoading.value = false
  }
}

const loadVulnerabilities = async () => {
  vulnerabilitiesLoading.value = true
  try {
    const vulnerabilitiesResponse = await api.get(`/component-versions/${route.params.uuid}/vulnerabilities/`)
    versionVulnerabilities.value = vulnerabilitiesResponse.data || []
  } catch (err) {
    console.error('Error loading vulnerabilities:', err)
    versionVulnerabilities.value = []
  } finally {
    vulnerabilitiesLoading.value = false
  }
}

const showAllLocations = () => {
  // Remove the fromImage query parameter to show all locations
  router.replace({ 
    name: 'component-version', 
    params: route.params,
    query: { ...route.query, fromImage: undefined }
  })
  // Reload locations without image filter
  loadLocations()
}

const goBack = () => {
  const fromPage = sessionStorage.getItem('fromPage')
  if (fromPage) {
    sessionStorage.removeItem('fromPage')
    router.push(fromPage)
  } else {
    router.push({ name: 'components' })
  }
}

const onVulnerabilityClick = (vulnerability: any) => {
  // Store current page info for back navigation
  const currentRoute = router.currentRoute.value
  const queryString = currentRoute.query ? '?' + new URLSearchParams(currentRoute.query as Record<string, string>).toString() : ''
  const fromPage = `${currentRoute.path}${queryString}`
  sessionStorage.setItem('fromPage', fromPage)
  
  if (vulnerability && vulnerability.uuid) {
    router.push({ name: 'vulnerability-detail', params: { uuid: vulnerability.uuid } })
  } else if (vulnerability && vulnerability.vulnerability_id) {
    router.push({ name: 'vulnerabilities', query: { search: vulnerability.vulnerability_id } })
  }
}

const goToImage = (imageUuid: string) => {
  router.push({ name: 'image-detail', params: { uuid: imageUuid } })
}

const formatDate = (dateString: string) => {
  if (!dateString) return 'Unknown'
  
  try {
    const date = new Date(dateString)
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch (err) {
    return dateString
  }
}

const getTypeColor = (type: string) => {
  const colors: { [key: string]: string } = {
    'apk': 'red',
    'deb': 'blue',
    'rpm': 'green',
    'java-archive': 'orange',
    'python': 'purple',
    'npm': 'pink',
    'gem': 'deep-purple',
    'go-module': 'cyan',
    'rust-crate': 'brown',
    'composer': 'indigo'
  }
  return colors[type?.toLowerCase()] || 'grey'
}

const getSeverityColor = (severity: string) => {
  const colors: { [key: string]: string } = {
    'critical': 'red',
    'high': 'orange',
    'medium': 'yellow',
    'low': 'green',
    'negligible': 'grey'
  }
  return colors[severity?.toLowerCase()] || 'grey'
}

const getEvidenceColor = (evidenceType: string) => {
  const colors: { [key: string]: string } = {
    'direct': 'green',
    'indirect': 'orange',
    'inherited': 'blue'
  }
  return colors[evidenceType?.toLowerCase()] || 'grey'
}

onMounted(() => {
  loadVersion()
})
</script>

<style scoped>
.component-version-detail {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.loading-container,
.error-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  text-align: center;
}

.version-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 20px;
}

.version-info {
  flex: 1;
  min-width: 300px;
}

.version-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.version-stats {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.stat-card {
  text-align: center;
  padding: 16px;
  background: linear-gradient(135deg, #f8f9fa, #e8e8e8);
  border-radius: 12px;
  border: 1px solid #e0e0e0;
  min-width: 80px;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: bold;
  color: #1976d2;
}

.stat-label {
  font-size: 0.75rem;
  color: #666;
  margin-top: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.info-card {
  height: 100%;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.empty-state,
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  text-align: center;
}

.locations-list,
.vulnerabilities-list {
  max-height: 400px;
  overflow-y: auto;
}

.location-panel {
  margin-bottom: 8px;
  border-radius: 8px;
}

.location-header {
  display: flex;
  align-items: center;
  width: 100%;
}

.location-path {
  flex: 1;
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.location-details {
  padding: 12px 0;
}

.detail-row {
  display: flex;
  margin-bottom: 12px;
  align-items: flex-start;
  padding: 8px 12px;
  background: #f8f9fa;
  border-radius: 6px;
  border-left: 3px solid #000000;
}

.detail-label {
  font-weight: 600;
  min-width: 120px;
  color: #424242;
  font-size: 0.875rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.detail-value {
  flex: 1;
  word-break: break-all;
  color: #212121;
  font-size: 0.875rem;
  line-height: 1.4;
}

.font-mono {
  font-family: 'Courier New', monospace;
  background: #f5f5f5;
  padding: 4px 8px;
  border-radius: 4px;
  border: 1px solid #e0e0e0;
}

.vulnerability-item {
  border-radius: 16px;
  margin-bottom: 16px;
  transition: all 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
  background: linear-gradient(135deg, #ffffff 0%, #fafbfc 100%);
  border: 1px solid #e8eaed;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  overflow: hidden;
  position: relative;
}

.vulnerability-item::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, #e3f2fd, #bbdefb, #90caf9, #64b5f6);
  opacity: 0;
  transition: opacity 0.4s ease;
}

.vulnerability-item:hover {
  background: linear-gradient(135deg, #ffffff 0%, #f5f9ff 100%);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  border-color: #90caf9;
}

.vulnerability-item:hover::before {
  opacity: 0.6;
}

.vulnerability-item:active {
  transform: translateY(0);
}

.vulnerability-title {
  font-weight: 600;
  font-family: 'Courier New', monospace;
  font-size: 0.95rem;
  color: #37474f;
  letter-spacing: 0.3px;
  margin-bottom: 6px;
}

.vulnerability-subtitle {
  color: #78909c;
  font-size: 0.875rem;
  line-height: 1.6;
  font-weight: 400;
  opacity: 0.7;
}

.images-list {
  max-height: 400px;
  overflow-y: auto;
}

.image-item {
  border-radius: 12px;
  margin-bottom: 8px;
  transition: all 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94);
  background: linear-gradient(135deg, #ffffff 0%, #fafbfc 100%);
  border: 1px solid #e8eaed;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  overflow: hidden;
  position: relative;
  cursor: pointer;
}

.image-item::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, #e3f2fd, #bbdefb, #90caf9, #64b5f6);
  opacity: 0;
  transition: opacity 0.4s ease;
}

.image-item:hover {
  background: linear-gradient(135deg, #ffffff 0%, #f5f9ff 100%);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  border-color: #90caf9;
}

.image-item:hover::before {
  opacity: 0.6;
}

.image-item:active {
  transform: translateY(0);
}

.image-title {
  font-weight: 600;
  color: #37474f;
  font-size: 0.95rem;
  letter-spacing: 0.3px;
  margin-bottom: 4px;
}

.image-subtitle {
  color: #78909c;
  font-size: 0.8rem;
  line-height: 1.4;
  font-weight: 400;
  opacity: 0.7;
  font-family: 'Courier New', monospace;
}

/* Matrix theme support */
:deep(.v-theme--matrix) .stat-value {
  color: #00ff41;
}

:deep(.v-theme--matrix) .stat-card {
  background: linear-gradient(135deg, #0a0a0a, #1a1a1a);
  border-color: #00ff41;
}

:deep(.v-theme--matrix) .info-card {
  background: #0a0a0a;
  border: 1px solid #00ff41;
}

:deep(.v-theme--matrix) .detail-row {
  background: #1a1a1a;
  border-left-color: #00ff41;
}

:deep(.v-theme--matrix) .vulnerability-item {
  background: linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 100%);
  border-color: #4caf50;
  box-shadow: 0 1px 3px rgba(76, 175, 80, 0.08);
}

:deep(.v-theme--matrix) .vulnerability-item:hover {
  background: linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 100%);
  border-color: #66bb6a;
  box-shadow: 0 3px 8px rgba(76, 175, 80, 0.15);
}

:deep(.v-theme--matrix) .vulnerability-item::before {
  background: linear-gradient(90deg, #4caf50, #66bb6a, #81c784, #a5d6a7);
}

:deep(.v-theme--matrix) .vulnerability-title {
  color: #81c784;
}

:deep(.v-theme--matrix) .vulnerability-subtitle {
  color: #bdbdbd;
}

:deep(.v-theme--matrix) .image-item {
  background: linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 100%);
  border-color: #4caf50;
  box-shadow: 0 1px 3px rgba(76, 175, 80, 0.08);
}

:deep(.v-theme--matrix) .image-item:hover {
  background: linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 100%);
  border-color: #66bb6a;
  box-shadow: 0 3px 8px rgba(76, 175, 80, 0.15);
}

:deep(.v-theme--matrix) .image-item::before {
  background: linear-gradient(90deg, #4caf50, #66bb6a, #81c784, #a5d6a7);
}

:deep(.v-theme--matrix) .image-title {
  color: #81c784;
}

:deep(.v-theme--matrix) .image-subtitle {
  color: #bdbdbd;
}
</style>
