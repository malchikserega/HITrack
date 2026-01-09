<template>
  <div class="component-detail">
    <v-container>
      <v-row>
        <v-col cols="12">
          <v-btn variant="text" @click="router.back()" class="mb-2">
            ← Back
          </v-btn>
          
          <h1 class="text-h4 mb-4 font-weight-black">Component Details</h1>
        </v-col>
      </v-row>
      
      <v-row>
        <v-col cols="12">
          <v-alert v-if="error" type="error" class="mb-4">{{ error }}</v-alert>
          <v-progress-circular v-if="loading" indeterminate color="primary" class="my-8" size="48" />
          
          <div v-if="component && !loading">
            <!-- Component Info Card -->
            <v-card class="mb-6 pa-4">
              <div class="d-flex align-center justify-space-between mb-4">
                <div>
                  <h2 class="text-h5 font-weight-bold">{{ component.name }}</h2>
                  <p class="text-grey">Component Information</p>
                </div>
                <v-chip
                  :color="getTypeColor(component.type)"
                  size="large"
                  variant="tonal"
                >
                  {{ component.type }}
                </v-chip>
              </div>
              
              <div class="component-stats">
                <div class="stat-item">
                  <div class="stat-value">{{ component?.versions_count || componentVersions.length }}</div>
                  <div class="stat-label">Versions</div>
                </div>
                <div class="stat-item">
                  <div class="stat-value">{{ totalImages }}</div>
                  <div class="stat-label">Images</div>
                </div>

              </div>
            </v-card>

            <!-- Tabs -->
            <v-card>
              <v-tabs v-model="activeTab" color="primary" grow>
                <v-tab value="versions">
                  <v-icon start>mdi-package-variant</v-icon>
                  Versions
                </v-tab>
              </v-tabs>

              <v-window v-model="activeTab">
                <!-- Versions Tab -->
                <v-window-item value="versions">
                  <v-card-text>
                    <v-data-table
                      :headers="versionHeaders"
                      :items="componentVersions"
                      :loading="versionsLoading"
                      class="elevation-1"
                      hover
                      density="comfortable"
                      @click:row="onVersionClick"
                    >
                      <template v-slot:item.version="{ item }">
                        <v-chip size="small" color="primary" variant="tonal">
                          {{ item.version }}
                        </v-chip>
                      </template>
                      <template v-slot:item.used_count="{ item }">
                        <v-chip size="small" color="info" variant="tonal">
                          {{ item.used_count }}
                        </v-chip>
                      </template>
                      <template v-slot:item.vulnerabilities_count="{ item }">
                        <v-chip
                          size="small"
                          :color="item.vulnerabilities_count > 0 ? 'error' : 'success'"
                          variant="tonal"
                        >
                          {{ item.vulnerabilities_count }}
                        </v-chip>
                      </template>
                                    <template v-slot:item.created_at="{ item }">
                <span class="date-text">
                  {{ formatDate(item.created_at) }}
                </span>
              </template>
              <template v-slot:item.actions="{ item }">
                <div class="action-buttons">
                  <v-tooltip location="top" text="View version details">
                    <template v-slot:activator="{ props }">
                      <v-btn
                        size="small"
                        color="info"
                        variant="tonal"
                        icon
                        @click.stop="goToVersionDetail(item)"
                        class="action-btn"
                        v-bind="props"
                      >
                        <v-icon size="18">mdi-information</v-icon>
                      </v-btn>
                    </template>
                  </v-tooltip>
                  
                  <v-tooltip location="top" text="View locations where this version is found">
                    <template v-slot:activator="{ props }">
                      <v-btn
                        size="small"
                        color="primary"
                        variant="tonal"
                        icon
                        @click.stop="showVersionLocationsModal(item)"
                        class="action-btn"
                        v-bind="props"
                      >
                        <v-icon size="18">mdi-map-marker</v-icon>
                      </v-btn>
                    </template>
                  </v-tooltip>
                  
                  <v-tooltip location="top" text="View vulnerabilities for this version">
                    <template v-slot:activator="{ props }">
                      <v-btn
                        size="small"
                        color="warning"
                        variant="tonal"
                        icon
                        @click.stop="showVersionVulnerabilitiesModal(item)"
                        class="action-btn"
                        v-bind="props"
                      >
                        <v-icon size="18">mdi-shield-alert</v-icon>
                      </v-btn>
                    </template>
                  </v-tooltip>
                </div>
              </template>
                    </v-data-table>
                  </v-card-text>
                </v-window-item>
              </v-window>
            </v-card>
          </div>
        </v-col>
      </v-row>
    </v-container>

    <!-- Version Locations Modal -->
    <v-dialog v-model="showLocationsModal" max-width="800px">
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon class="mr-2">mdi-map-marker</v-icon>
          Component Locations
          <v-spacer></v-spacer>
          <v-btn icon @click="showLocationsModal = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>
        
        <v-card-text v-if="selectedVersion">
          <div class="component-info-section">
            <h3 class="text-h6 mb-3">
              {{ selectedVersion.component?.name }} {{ selectedVersion.version }}
            </h3>
            <div class="d-flex align-center mb-3">
              <v-chip size="small" :color="getTypeColor(selectedVersion.component?.type)" class="mr-2">
                {{ selectedVersion.component?.type }}
              </v-chip>
              <span class="text-caption text-grey">Version Details</span>
            </div>
            
            <div v-if="selectedVersion.purl" class="mb-3">
              <strong class="text-subtitle-2">PURL:</strong> 
              <div class="font-mono mt-1">{{ selectedVersion.purl }}</div>
            </div>
            
            <div v-if="selectedVersion.cpes && selectedVersion.cpes.length" class="mb-3">
              <strong class="text-subtitle-2">CPEs:</strong>
              <div class="mt-2">
                <v-chip
                  v-for="cpe in selectedVersion.cpes"
                  :key="cpe"
                  size="small"
                  color="secondary"
                  variant="tonal"
                  class="mr-1 mb-1"
                >
                  {{ cpe }}
                </v-chip>
              </div>
            </div>
          </div>

          <v-divider class="mb-4"></v-divider>

          <div v-if="versionLocations.length === 0" class="empty-state">
            <v-icon size="64" color="grey">mdi-map-marker-off</v-icon>
            <h3 class="mt-4">No Location Data</h3>
            <p class="text-grey">No location information available for this version.</p>
          </div>
          
          <div v-else>
            <h4 class="text-h6 mb-3">
              <v-icon class="mr-2">mdi-file-tree</v-icon>
              File Locations ({{ versionLocations.length }})
            </h4>
            
            <v-expansion-panels>
              <v-expansion-panel
                v-for="(location, index) in versionLocations"
                :key="index"
              >
                <v-expansion-panel-title>
                  <div class="d-flex align-center">
                    <v-icon
                      :color="getEvidenceColor(location.evidence_type || 'unknown')"
                      class="mr-3"
                      size="20"
                    >
                      {{ getEvidenceIcon(location.evidence_type || 'unknown') }}
                    </v-icon>
                    <span class="file-path">{{ location.path || 'No path' }}</span>
                    <v-chip
                      size="small"
                      :color="getEvidenceColor(location.evidence_type || 'unknown')"
                      variant="tonal"
                      class="ml-auto evidence-chip"
                    >
                      {{ location.evidence_type || 'unknown' }}
                    </v-chip>
                  </div>
                </v-expansion-panel-title>
                
                <v-expansion-panel-text>
                  <div class="location-details">
                    <div class="detail-row">
                      <span class="detail-label">Image:</span>
                      <span class="detail-value">{{ location.image?.name || location.image?.uuid || 'Unknown' }}</span>
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
                    
                    <!-- Raw location data for debugging -->
                    <div class="detail-row mt-3">
                      <span class="detail-label">Raw Data:</span>
                      <pre class="detail-value text-caption">{{ JSON.stringify(location, null, 2) }}</pre>
                    </div>
                  </div>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>
          </div>
        </v-card-text>
        
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="primary" @click="showLocationsModal = false">
            Close
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Version Vulnerabilities Modal -->
    <v-dialog v-model="showVulnerabilitiesModal" max-width="1000px">
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon class="mr-2">mdi-shield-alert</v-icon>
          Version Vulnerabilities
          <v-spacer></v-spacer>
          <v-btn icon @click="showVulnerabilitiesModal = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>
        
        <v-card-text v-if="selectedVersion">
          <div class="component-info-section">
            <h3 class="text-h6 mb-3">
              {{ selectedVersion.component?.name }} {{ selectedVersion.version }}
            </h3>
            <div class="d-flex align-center mb-3">
              <v-chip size="small" :color="getTypeColor(selectedVersion.component?.type)" class="mr-2">
                {{ selectedVersion.component?.type }}
              </v-chip>
              <span class="text-caption text-grey">Version Details</span>
            </div>
          </div>

          <v-divider class="mb-4"></v-divider>

          <div v-if="versionVulnerabilities.length === 0" class="empty-state">
            <v-icon size="64" color="success">mdi-shield-check</v-icon>
            <h3 class="mt-4">No Vulnerabilities</h3>
            <p class="text-grey">This version has no known vulnerabilities.</p>
          </div>
          
          <div v-else>
            <h4 class="text-h6 mb-3">
              <v-icon class="mr-2">mdi-shield-alert</v-icon>
              Vulnerabilities ({{ versionVulnerabilities.length }})
            </h4>
            
            <v-data-table
              :headers="vulnerabilityHeaders"
              :items="versionVulnerabilities"
              class="elevation-1"
              density="comfortable"
              @click:row="onVulnerabilityClick"
            >
              <template v-slot:item.vulnerability_id="{ item }">
                <div class="vulnerability-id">
                  <span class="font-mono text-caption">{{ item.vulnerability_id || item.uuid || 'N/A' }}</span>
                </div>
              </template>
              
              <template v-slot:item.severity="{ item }">
                <v-chip
                  size="small"
                  :color="getSeverityColor(item.severity)"
                  variant="tonal"
                >
                  {{ item.severity || 'UNKNOWN' }}
                </v-chip>
              </template>
              
              <template v-slot:item.vulnerability_type="{ item }">
                <span>{{ item.vulnerability_type || item.type || 'N/A' }}</span>
              </template>
              
              <template v-slot:item.affected_versions="{ item }">
                <div v-if="item.affected_versions && item.affected_versions.length > 0">
                  <v-chip
                    v-for="version in item.affected_versions"
                    :key="version"
                    size="small"
                    color="warning"
                    variant="tonal"
                    class="mr-1 mb-1"
                  >
                    {{ version }}
                  </v-chip>
                </div>
                <span v-else class="text-grey text-caption">No specific versions</span>
              </template>
              
              <template v-slot:item.description="{ item }">
                <div class="vulnerability-description">
                  <span v-if="item.description" class="text-truncate d-block" style="max-width: 200px;">
                    {{ item.description }}
                  </span>
                  <span v-else class="text-grey text-caption">No description</span>
                </div>
              </template>
              
              <template v-slot:item.actions="{ item }">
                <v-tooltip location="top" text="View vulnerability details">
                  <template v-slot:activator="{ props }">
                    <v-btn
                      size="small"
                      color="primary"
                      variant="outlined"
                      @click.stop="onVulnerabilityClick(null, { item })"
                      v-bind="props"
                    >
                      <v-icon size="small" class="mr-1">mdi-shield-alert</v-icon>
                      Details
                    </v-btn>
                  </template>
                </v-tooltip>
              </template>
            </v-data-table>
          </div>
        </v-card-text>
        
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="primary" @click="showVulnerabilitiesModal = false">
            Close
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/plugins/axios'


const route = useRoute()
const router = useRouter()

const loading = ref(false)
const error = ref(null)
const component = ref(null)
const componentVersions = ref([])
const versionsLoading = ref(false)
const activeTab = ref('versions')
const showLocationsModal = ref(false)
const selectedVersion = ref(null)
const versionLocations = ref([])
const showVulnerabilitiesModal = ref(false)
const versionVulnerabilities = ref([])

const versionHeaders = [
  { title: 'Version', key: 'version', sortable: true },
  { title: 'Used In', key: 'used_count', sortable: true },
  { title: 'Vulnerabilities', key: 'vulnerabilities_count', sortable: true },
  { title: 'Created', key: 'created_at', sortable: true },
  { title: 'Actions', key: 'actions', sortable: false }
]

const vulnerabilityHeaders = [
  { title: 'ID', key: 'vulnerability_id', sortable: true },
  { title: 'Severity', key: 'severity', sortable: true },
  { title: 'Type', key: 'vulnerability_type', sortable: true },
  { title: 'Affected Versions', key: 'affected_versions', sortable: false },
  { title: 'Description', key: 'description', sortable: false },
  { title: 'Actions', key: 'actions', sortable: false }
]



const totalImages = computed(() => {
  // Use the optimized total_images field from component detail endpoint
  return component.value?.total_images || 0
})

const getTypeColor = (type: string) => {
  const colors = {
    'unknown': 'grey',
    'npm': 'red',
    'pypi': 'blue',
    'maven': 'green',
    'gem': 'purple',
    'go': 'cyan',
    'nuget': 'orange',
    'deb': 'grey',
    'dotnet': 'purple'
  }
  return colors[type?.toLowerCase()] || 'grey'
}

const getSeverityColor = (severity: string) => {
  const colors = {
    'CRITICAL': 'error',
    'HIGH': 'warning',
    'MEDIUM': 'orange',
    'LOW': 'info',
    'UNKNOWN': 'grey'
  }
  return colors[severity?.toUpperCase()] || 'grey'
}

const loadComponent = async () => {
  loading.value = true
  error.value = null
  
  try {
    const response = await api.get(`/components/${route.params.uuid}/`)
    component.value = response.data
  } catch (err) {
    console.error('Error loading component:', err)
    error.value = err.response?.data?.error || 'Failed to load component'
  } finally {
    loading.value = false
  }
}

const loadComponentVersions = async () => {
  versionsLoading.value = true
  
  try {
    const response = await api.get(`/components/${route.params.uuid}/versions/`)
    componentVersions.value = response.data
  } catch (err) {
    console.error('Error loading component versions:', err)
  } finally {
    versionsLoading.value = false
  }
}





const onVersionClick = (event: any, item: any) => {
  // Navigate to version detail or show version info
  // Currently not implemented
}

const onVulnerabilityClick = (event: any, item: any) => {
  // Navigate to vulnerability detail page
  const vulnerability = item.item || item
  
  // Store current page info for back navigation
  const currentRoute = router.currentRoute.value
  const queryString = currentRoute.query ? '?' + new URLSearchParams(currentRoute.query as Record<string, string>).toString() : ''
  const fromPage = `${currentRoute.path}${queryString}`
  sessionStorage.setItem('fromPage', fromPage)
  
  // Try different possible ID fields
  const vulnerabilityId = vulnerability?.uuid || 
                          vulnerability?.vulnerability_id || 
                          vulnerability?.id || 
                          vulnerability?.cve_id
  
  if (vulnerabilityId) {
    try {
      router.push({ name: 'vulnerability-detail', params: { uuid: vulnerabilityId } })
    } catch (err) {
      console.error('Navigation error:', err)
      // Fallback to search
      router.push({ name: 'vulnerabilities', query: { search: vulnerabilityId } })
    }
  } else {
    // Fallback to search by description or other fields
    const searchTerm = vulnerability?.description || 
                       vulnerability?.vulnerability_id || 
                       vulnerability?.type || 
                       'vulnerability'
    router.push({ name: 'vulnerabilities', query: { search: searchTerm } })
  }
}

const showVersionLocationsModal = async (version: any) => {
  selectedVersion.value = version
  showLocationsModal.value = true
  
  // Load locations for this specific version
  try {
    const response = await api.get(`/component-versions/${version.uuid}/locations/`)
    
    // Handle different response structures
    if (response.data.results && response.data.results.locations) {
      // New API structure
      versionLocations.value = response.data.results.locations || []
    } else if (response.data.locations) {
      // Direct locations array
      versionLocations.value = response.data.locations || []
    } else if (Array.isArray(response.data)) {
      // Direct array response
      versionLocations.value = response.data || []
    } else {
      // Fallback
      versionLocations.value = []
    }
  } catch (err) {
    console.error('Error loading version locations:', err)
    versionLocations.value = []
  }
}

const showVersionVulnerabilitiesModal = async (version: any) => {
  selectedVersion.value = version
  showVulnerabilitiesModal.value = true
  
  // Load vulnerabilities for this specific version
  try {
    const response = await api.get(`/component-versions/${version.uuid}/vulnerabilities/`)
    
    let vulnerabilities = []
    
    // Handle different response structures
    if (response.data.results && response.data.results.vulnerabilities) {
      // New API structure
      vulnerabilities = response.data.results.vulnerabilities || []
    } else if (response.data.vulnerabilities) {
      // Direct vulnerabilities array
      vulnerabilities = response.data.vulnerabilities || []
    } else if (Array.isArray(response.data)) {
      // Direct array response
      vulnerabilities = response.data || []
    } else if (response.data.results && Array.isArray(response.data.results)) {
      // Results is directly an array
      vulnerabilities = response.data.results || []
    } else {
      // Fallback
      vulnerabilities = []
    }
    
    // Force reactivity by creating a new array
    versionVulnerabilities.value = [...vulnerabilities]
    
  } catch (err) {
    console.error('Error loading version vulnerabilities:', err)
    versionVulnerabilities.value = []
  }
}

const goToVersionDetail = (version: any) => {
  // Store current page info for back navigation
  const currentRoute = router.currentRoute.value
  const queryString = currentRoute.query ? '?' + new URLSearchParams(currentRoute.query as Record<string, string>).toString() : ''
  const fromPage = `${currentRoute.path}${queryString}`
  sessionStorage.setItem('fromPage', fromPage)
  
  router.push({ name: 'component-version', params: { uuid: version.uuid } })
}

const formatDate = (dateString: string) => {
  if (!dateString) return 'Unknown'
  
  try {
    const date = new Date(dateString)
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch (err) {
    return dateString
  }
}

const getEvidenceColor = (evidenceType: string) => {
  const colors = {
    'primary': 'success',
    'supporting': 'warning',
    'unknown': 'grey'
  }
  return colors[evidenceType] || 'grey'
}

const getEvidenceIcon = (evidenceType: string) => {
  const icons = {
    'primary': 'mdi-check-circle',
    'supporting': 'mdi-help-circle',
    'unknown': 'mdi-question-circle'
  }
  return icons[evidenceType] || 'mdi-question-circle'
}

onMounted(async () => {
  await loadComponent()
  await loadComponentVersions()
})
</script>

<style scoped>
/* Action buttons styling */
.action-buttons {
  display: flex;
  flex-direction: row;
  gap: 4px;
  justify-content: center;
  flex-wrap: wrap;
}

.action-btn {
  border-radius: 50% !important;
  min-width: 32px !important;
  width: 32px !important;
  height: 32px !important;
  transition: all 0.2s ease;
}

.action-btn:hover {
  transform: translateY(-2px) scale(1.05);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.date-text {
  font-size: 11px;
  color: #666;
  font-weight: 500;
}

.component-detail {
  padding: 20px;
  background: #ffffff;
  min-height: 100vh;
}


.component-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 16px;
  margin-top: 16px;
}

.stat-item {
  text-align: center;
  padding: 16px;
  background: #f5f5f5;
  border-radius: 8px;
}

.stat-value {
  font-size: 2rem;
  font-weight: bold;
  color: #1976d2;
}

.stat-label {
  font-size: 0.875rem;
  color: #666;
  margin-top: 4px;
}



:deep(.v-table) {
  background: transparent;
}

:deep(.v-table .v-table__wrapper > table) {
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 8px;
}



.location-details {
  padding: 12px 0;
}

/* Default styles (non-matrix) */
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

/* Modal specific styles */
.v-dialog .v-card-title {
  background: linear-gradient(135deg, #000000, #1a1a1a);
  color: white;
  padding: 16px 24px;
}

.v-dialog .v-card-title .v-icon {
  color: white;
}

.v-dialog .v-card-text {
  padding: 24px;
}

.v-dialog .v-expansion-panel {
  margin-bottom: 8px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.v-dialog .v-expansion-panel-title {
  padding: 12px 16px;
  font-weight: 500;
}

.v-dialog .v-expansion-panel-text {
  padding: 16px;
  background: #fafafa;
}

/* Component info section */
.component-info-section {
  background: linear-gradient(135deg, #f8f9fa, #e8e8e8);
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 16px;
  border: 1px solid #e0e0e0;
}

.component-info-section h3 {
  color: #000000;
  margin-bottom: 8px;
  font-weight: 600;
}

.component-info-section .v-chip {
  margin-right: 8px;
}

/* File path styling */
.file-path {
  font-family: 'Courier New', monospace;
  background: #f5f5f5;
  padding: 6px 10px;
  border-radius: 4px;
  border: 1px solid #e0e0e0;
  color: #424242;
  font-size: 0.8rem;
  word-break: break-all;
  line-height: 1.3;
}

/* Evidence type styling */
.evidence-chip {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* Empty state styling */
.empty-state {
  text-align: center;
  padding: 40px 20px;
}

.empty-state .v-icon {
  opacity: 0.5;
}

.empty-state h3 {
  color: #666;
  margin-top: 16px;
  font-weight: 500;
}

.empty-state p {
  color: #999;
  margin-top: 8px;
}

/* Matrix theme overrides */
.v-theme--matrix .detail-row {
  background: #0a0a0a;
  border-left: 3px solid #39FF14;
  border: 1px solid #39FF14;
  box-shadow: 0 0 10px rgba(57, 255, 20, 0.3);
}

.v-theme--matrix .detail-label {
  color: #39FF14;
  text-shadow: 0 0 5px #39FF14;
}

.v-theme--matrix .detail-value {
  color: #39FF14;
  text-shadow: 0 0 3px #39FF14;
}

.v-theme--matrix .font-mono {
  background: #0a0a0a;
  border: 1px solid #39FF14;
  color: #39FF14;
  box-shadow: 0 0 5px rgba(57, 255, 20, 0.2);
}

.v-theme--matrix .v-dialog .v-card-title {
  background: linear-gradient(135deg, #000000, #1a1a1a);
  color: #39FF14;
  border-bottom: 2px solid #39FF14;
  box-shadow: 0 0 15px rgba(57, 255, 20, 0.4);
}

.v-theme--matrix .v-dialog .v-card-title .v-icon {
  color: #39FF14;
  text-shadow: 0 0 5px #39FF14;
}

.v-theme--matrix .v-dialog .v-card-text {
  background: #000000;
  color: #39FF14;
}

.v-theme--matrix .v-dialog .v-expansion-panel {
  box-shadow: 0 0 10px rgba(57, 255, 20, 0.3);
  background: #0a0a0a;
  border: 1px solid #39FF14;
}

.v-theme--matrix .v-dialog .v-expansion-panel-title {
  color: #39FF14;
  background: #0a0a0a;
}

.v-theme--matrix .v-dialog .v-expansion-panel-text {
  background: #000000;
  color: #39FF14;
}

.v-theme--matrix .component-info-section {
  background: linear-gradient(135deg, #000000, #0a0a0a);
  border: 2px solid #39FF14;
  box-shadow: 0 0 15px rgba(57, 255, 20, 0.3);
}

.v-theme--matrix .component-info-section h3 {
  color: #39FF14;
  text-shadow: 0 0 5px #39FF14;
}

.v-theme--matrix .component-info-section .v-chip {
  background: #0a0a0a !important;
  border: 1px solid #39FF14 !important;
  color: #39FF14 !important;
}

.v-theme--matrix .file-path {
  background: #0a0a0a;
  border: 1px solid #39FF14;
  color: #39FF14;
  box-shadow: 0 0 5px rgba(57, 255, 20, 0.2);
  text-shadow: 0 0 3px #39FF14;
}

.v-theme--matrix .evidence-chip {
  background: #0a0a0a !important;
  border: 1px solid #39FF14 !important;
  color: #39FF14 !important;
  box-shadow: 0 0 5px rgba(57, 255, 20, 0.3) !important;
}

.v-theme--matrix .empty-state {
  color: #39FF14;
}

.v-theme--matrix .empty-state .v-icon {
  opacity: 0.7;
  color: #39FF14;
  text-shadow: 0 0 5px #39FF14;
}

.v-theme--matrix .empty-state h3 {
  color: #39FF14;
  text-shadow: 0 0 5px #39FF14;
}

.v-theme--matrix .empty-state p {
  color: #39FF14;
  opacity: 0.8;
}

/* Matrix theme overrides */
.v-theme--matrix .v-dialog .v-card {
  background: #000000 !important;
  border: 2px solid #39FF14 !important;
  box-shadow: 0 0 20px rgba(57, 255, 20, 0.4) !important;
}

.v-theme--matrix .v-dialog .v-card-actions {
  background: #0a0a0a;
  border-top: 1px solid #39FF14;
}

.v-theme--matrix .v-dialog .v-btn {
  background: #0a0a0a !important;
  border: 1px solid #39FF14 !important;
  color: #39FF14 !important;
  text-shadow: 0 0 3px #39FF14;
}

.v-theme--matrix .v-dialog .v-btn:hover {
  background: #39FF14 !important;
  color: #000000 !important;
  box-shadow: 0 0 10px rgba(57, 255, 20, 0.6) !important;
}

/* Glitch effect for text */
@keyframes glitch {
  0% { text-shadow: 0 0 5px #39FF14; }
  50% { text-shadow: 0 0 5px #39FF14, 2px 0 0 #ff00ff; }
  100% { text-shadow: 0 0 5px #39FF14; }
}

.v-theme--matrix .component-info-section h3 {
  animation: glitch 3s infinite;
}
</style>
