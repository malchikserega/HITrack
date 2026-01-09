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
      <div class="main-loading-animation">
        <v-progress-circular indeterminate size="80" color="primary" width="4"></v-progress-circular>
        <div class="main-loading-text">
          <h2 class="text-h4 mb-3">Loading Component Version</h2>
          <p class="text-grey">Fetching component details...</p>
        </div>
      </div>
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
              <div class="d-flex align-center">
                <v-icon class="mr-2" color="primary">mdi-map-marker</v-icon>
                <span class="font-weight-bold">Locations</span>
                <v-progress-circular 
                  v-if="locationsLoading" 
                  indeterminate 
                  color="primary" 
                  size="20" 
                  width="2" 
                  class="ml-3"
                ></v-progress-circular>
                <v-progress-circular 
                  v-else-if="!locationsLoading && versionLocations.length === 0 && !version" 
                  indeterminate 
                  color="grey" 
                  size="16" 
                  width="2" 
                  class="ml-3"
                ></v-progress-circular>
              </div>
              
              <v-chip v-if="route.query.fromImage" size="small" color="info" variant="tonal" class="mx-2">
                <v-icon size="12" class="mr-1">mdi-filter</v-icon>
                Filtered by Image
              </v-chip>
              
              <v-spacer></v-spacer>
              
              <v-chip size="small" color="primary" variant="elevated">
                <span v-if="locationsLoading">
                  <v-progress-circular size="12" width="2" indeterminate></v-progress-circular>
                </span>
                <span v-else>{{ version?.locations_count || versionLocations.length }}</span>
              </v-chip>
            </v-card-title>
            
            <v-card-text>
              <div v-if="locationsLoading" class="loading-state">
                <div class="loading-animation">
                  <v-progress-circular indeterminate color="primary" size="48"></v-progress-circular>
                  <div class="loading-text">
                    <h4 class="text-h6 mb-2">Loading Locations</h4>
                    <p class="text-grey">Discovering where this component is used...</p>
                  </div>
                </div>
              </div>
              <div v-else-if="!locationsLoading && versionLocations.length === 0 && !version" class="initializing-state">
                <div class="initializing-animation">
                  <v-progress-circular indeterminate color="grey" size="32"></v-progress-circular>
                  <div class="initializing-text">
                    <p class="text-grey">Initializing locations...</p>
                  </div>
                </div>
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
                <!-- Expandable location display -->
                <div v-if="versionLocations.length > 0">
                  <div class="location-item mb-3" v-for="(loc, index) in versionLocations" :key="`loc-${index}`">
                    <v-card class="location-card" v-if="loc && loc.path">
                      <v-card-title 
                        class="d-flex align-center py-3 cursor-pointer" 
                        @click="toggleLocation(index)"
                      >
                        <v-icon size="small" class="mr-2">mdi-file</v-icon>
                        <span class="location-path">{{ loc.path }}</span>
                        <v-chip
                          size="small"
                          :color="getEvidenceColor(loc.evidence_type || 'unknown')"
                          variant="tonal"
                          class="ml-auto mr-2"
                        >
                          {{ loc.evidence_type || 'UNKNOWN' }}
                        </v-chip>
                        <v-icon 
                          :icon="expandedLocations[index] ? 'mdi-chevron-up' : 'mdi-chevron-down'"
                          size="small"
                          class="expand-icon"
                        ></v-icon>
                      </v-card-title>
                      
                      <v-card-text class="pt-0" v-show="expandedLocations[index]">
                        <div class="location-details">
                          <div class="detail-row">
                            <span class="detail-label">Image:</span>
                            <span class="detail-value">{{ loc.image?.name || 'Unknown' }}</span>
                          </div>
                          
                          <div class="detail-row" v-if="loc.layer_id">
                            <span class="detail-label">Layer ID:</span>
                            <span class="detail-value font-mono text-caption">{{ loc.layer_id }}</span>
                          </div>
                          
                          <div class="detail-row" v-if="loc.access_path">
                            <span class="detail-label">Access Path:</span>
                            <span class="detail-value font-mono text-caption">{{ loc.access_path }}</span>
                          </div>
                          
                          <div class="detail-row" v-if="loc.annotations && Object.keys(loc.annotations).length">
                            <span class="detail-label">Annotations:</span>
                            <pre class="detail-value text-caption">{{ JSON.stringify(loc.annotations, null, 2) }}</pre>
                          </div>
                        </div>
                      </v-card-text>
                    </v-card>
                  </div>
                  
                  <!-- Load More Button -->
                  <div v-if="locationsHasMore" class="text-center mt-4">
                    <v-btn
                      @click="loadMoreLocations"
                      :loading="locationsLoadingMore"
                      :disabled="locationsLoadingMore"
                      variant="outlined"
                      color="primary"
                      class="load-more-btn"
                    >
                      <v-icon v-if="!locationsLoadingMore" class="mr-2">mdi-arrow-down</v-icon>
                      {{ locationsLoadingMore ? 'Loading...' : 'Load More Locations' }}
                    </v-btn>
                  </div>
                </div>
                <div v-else class="text-center py-4">
                  <v-icon size="48" color="grey">mdi-map-marker-off</v-icon>
                  <p class="text-grey mt-2">No locations found</p>
                </div>
              </div>
            </v-card-text>
          </v-card>
        </v-col>

        <!-- Vulnerabilities Section -->
        <v-col cols="12" md="6">
          <v-card class="info-card">
            <v-card-title class="d-flex align-center">
              <div class="d-flex align-center">
                <v-icon class="mr-2" color="warning">mdi-shield-alert</v-icon>
                <span class="font-weight-bold">Vulnerabilities</span>
                <v-progress-circular 
                  v-if="vulnerabilitiesLoading" 
                  indeterminate 
                  color="warning" 
                  size="20" 
                  width="2" 
                  class="ml-3"
                ></v-progress-circular>
                <v-progress-circular 
                  v-else-if="!vulnerabilitiesLoading && versionVulnerabilities.length === 0 && !version" 
                  indeterminate 
                  color="grey" 
                  size="16" 
                  width="2" 
                  class="ml-3"
                ></v-progress-circular>
              </div>
              
              <v-spacer></v-spacer>
              
              <v-chip size="small" color="warning" variant="elevated">
                <span v-if="vulnerabilitiesLoading">
                  <v-progress-circular size="12" width="2" indeterminate></v-progress-circular>
                </span>
                <span v-else>{{ version?.vulnerabilities_count || versionVulnerabilities.length }}</span>
              </v-chip>
            </v-card-title>
            
            <v-card-text>
              <div v-if="vulnerabilitiesLoading" class="loading-state">
                <div class="loading-animation">
                  <v-progress-circular indeterminate color="warning" size="48"></v-progress-circular>
                  <div class="loading-text">
                    <h4 class="text-h6 mb-2">Loading Vulnerabilities</h4>
                    <p class="text-grey">Analyzing security issues...</p>
                  </div>
                </div>
              </div>
              <div v-else-if="!vulnerabilitiesLoading && versionVulnerabilities.length === 0 && !version" class="initializing-state">
                <div class="initializing-animation">
                  <v-progress-circular indeterminate color="grey" size="32"></v-progress-circular>
                  <div class="initializing-text">
                    <p class="text-grey">Initializing vulnerabilities...</p>
                  </div>
                </div>
              </div>
              <div v-else-if="versionVulnerabilities.length === 0" class="empty-state">
                <v-icon size="48" color="success">mdi-shield-check</v-icon>
                <p class="text-grey mt-2">No vulnerabilities found</p>
              </div>
              
              <div v-else class="vulnerabilities-list">


                
                <!-- Simple vulnerability display without v-for -->
                <div v-if="versionVulnerabilities.length > 0">
                  <div class="vulnerability-item mb-3" v-for="(vuln, index) in versionVulnerabilities" :key="`vuln-${index}`">
                    <v-card class="vulnerability-card" v-if="vuln && (vuln.uuid || vuln.vulnerability_id)" @click="onVulnerabilityClick(vuln)">
                      <v-card-title class="d-flex align-center py-3">
                        <v-icon :color="getSeverityColor(vuln.severity || 'unknown')" class="mr-2">
                          mdi-shield-alert
                        </v-icon>
                        <span class="vulnerability-title">{{ vuln.vulnerability_id || 'Unknown' }}</span>
                        <v-chip
                          size="small"
                          :color="getSeverityColor(vuln.severity || 'unknown')"
                          variant="tonal"
                          class="ml-auto"
                        >
                          {{ vuln.severity || 'UNKNOWN' }}
                        </v-chip>
                      </v-card-title>
                      
                      <v-card-text class="pt-0">
                        <p class="vulnerability-subtitle">
                          {{ vuln.description?.substring(0, 100) || 'No description available' }}{{ vuln.description?.length > 100 ? '...' : '' }}
                        </p>
                      </v-card-text>
                    </v-card>
                  </div>
                </div>
                <div v-else class="text-center py-4">
                  <v-icon size="48" color="success">mdi-shield-check</v-icon>
                  <p class="text-grey mt-2">No vulnerabilities found</p>
                </div>
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
                              <v-chip size="small" color="info">{{ versionImages.length || 0 }}</v-chip>
            </v-card-title>
            
            <v-card-text>
              <div v-if="!versionImages || versionImages.length === 0" class="empty-state">
                <v-icon size="48" color="grey">mdi-docker</v-icon>
                <p class="text-grey mt-2">No images found</p>
              </div>
              
              <div v-else class="images-list">

                
                <v-list v-if="versionImages && versionImages.length > 0">
                  <v-list-item
                    v-for="image in versionImages"
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
                    
                    <template v-slot:append>
                      <v-icon color="primary">mdi-chevron-right</v-icon>
                    </template>
                  </v-list-item>
                </v-list>
                
                <div v-if="!versionImages || versionImages.length === 0" class="empty-state">
                  <v-icon size="48" color="grey">mdi-docker</v-icon>
                  <p class="text-grey mt-2">No images found</p>
                </div>
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/plugins/axios'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const locationsLoading = ref(false)
const vulnerabilitiesLoading = ref(false)
const error = ref(null)
const version = ref(null)
const versionLocations = ref<Location[]>([])
const versionVulnerabilities = ref<Vulnerability[]>([])
const versionImages = ref<any[]>([])
  const expandedLocations = ref<{ [key: number]: boolean }>({})
  const locationsNextPage = ref<string | null>(null)
  const locationsHasMore = ref(false)
  const locationsLoadingMore = ref(false)
  
  // Computed properties to help Vue recognize the data
const locationsList = computed(() => versionLocations.value)
const vulnerabilitiesList = computed(() => versionVulnerabilities.value)
const imagesList = computed(() => versionImages.value)

// Type definitions for template variables
interface Vulnerability {
  uuid?: string
  vulnerability_id?: string
  severity?: string
  description?: string
}

interface Location {
  uuid?: string
  path?: string
  evidence_type?: string
  image?: any
  layer_id?: string
  access_path?: string
  annotations?: any
}

const loadVersion = async () => {
  loading.value = true
  error.value = null
  
  try {
    // Load main version data first (lightweight)
    const response = await api.get(`/component-versions/${route.params.uuid}/`)
    version.value = response.data
    
  } catch (err) {
    console.error('Error loading version:', err)
    error.value = 'Failed to load version details'
  } finally {
    loading.value = false
  }
}

const loadAllData = async () => {
  // Load locations, vulnerabilities, and images in parallel
  await Promise.all([
    loadLocations(),
    loadVulnerabilities(),
    loadImages()
  ])
}

const loadLocations = async (isLoadMore = false) => {
  if (isLoadMore) {
    locationsLoadingMore.value = true
  } else {
    locationsLoading.value = true
  }
  
  try {
    // Check if we're filtering by specific image (came from ImageDetailView)
    const fromImageUuid = route.query.fromImage
    let url = `/component-versions/${route.params.uuid}/locations/`
    
    // Add image filter if specified
    if (fromImageUuid) {
      url += `?image=${fromImageUuid}`
    }
    
    // Add page parameter for load more
    if (isLoadMore && locationsNextPage.value) {
      url = locationsNextPage.value
    }
    
    const locationsResponse = await api.get(url)
    
    // Handle pagination metadata
    if (locationsResponse.data.next) {
      locationsNextPage.value = locationsResponse.data.next
      locationsHasMore.value = true
    } else {
      locationsNextPage.value = null
      locationsHasMore.value = false
    }
    
    // Handle new API response format with pagination
    let newLocations = []
    if (locationsResponse.data.results && locationsResponse.data.results.locations) {
      // Backend format: results.locations contains the array
      newLocations = locationsResponse.data.results.locations
    } else if (locationsResponse.data.results && Array.isArray(locationsResponse.data.results)) {
      // Paginated response with direct array
      newLocations = locationsResponse.data.results
    } else if (locationsResponse.data.locations) {
      // Non-paginated response with locations array
      newLocations = locationsResponse.data.locations
    } else if (locationsResponse.data.results && typeof locationsResponse.data.results === 'object') {
      // Results is an object, try to extract locations from it
      if (Array.isArray(locationsResponse.data.results)) {
        newLocations = locationsResponse.data.results
      } else {
        // Try to find any array property in results
        const resultKeys = Object.keys(locationsResponse.data.results)
        for (const key of resultKeys) {
          if (Array.isArray(locationsResponse.data.results[key])) {
            newLocations = locationsResponse.data.results[key]
            break
          }
        }
        if (newLocations.length === 0) {
          newLocations = locationsResponse.data || []
        }
      }
    } else {
      // Fallback to old format
      newLocations = locationsResponse.data || []
    }
    
    // Append or replace locations based on whether it's load more
    if (isLoadMore) {
      versionLocations.value = [...versionLocations.value, ...newLocations]
    } else {
      versionLocations.value = newLocations
      // Reset expanded states for new locations
      expandedLocations.value = {}
    }
    
  } catch (err) {
    console.error('Error loading locations:', err)
    if (!isLoadMore) {
      versionLocations.value = []
    }
  } finally {
    if (isLoadMore) {
      locationsLoadingMore.value = false
    } else {
      locationsLoading.value = false
    }
  }
}

const loadVulnerabilities = async () => {
  vulnerabilitiesLoading.value = true
  try {
    const vulnerabilitiesResponse = await api.get(`/component-versions/${route.params.uuid}/vulnerabilities/`)
    
    // Handle new API response format with pagination
    if (vulnerabilitiesResponse.data.results && Array.isArray(vulnerabilitiesResponse.data.results)) {
      // Paginated response with direct array
      versionVulnerabilities.value = vulnerabilitiesResponse.data.results
    } else if (vulnerabilitiesResponse.data.results && vulnerabilitiesResponse.data.results.vulnerabilities) {
      // New format: results.vulnerabilities contains the array
      versionVulnerabilities.value = vulnerabilitiesResponse.data.results.vulnerabilities
    } else if (vulnerabilitiesResponse.data.total_count !== undefined) {
      // Non-paginated response with total_count
      versionVulnerabilities.value = vulnerabilitiesResponse.data.results || []
    } else {
      // Fallback to old format
      versionVulnerabilities.value = vulnerabilitiesResponse.data || []
    }
  } catch (err) {
    console.error('Error loading vulnerabilities:', err)
    versionVulnerabilities.value = []
  } finally {
    vulnerabilitiesLoading.value = false
  }
}

const loadImages = async () => {
  try {
    const imagesResponse = await api.get(`/component-versions/${route.params.uuid}/images/`)
    
    // Handle images API response
    if (imagesResponse.data.images && Array.isArray(imagesResponse.data.images)) {
      // Images array in response
      versionImages.value = imagesResponse.data.images
    } else if (imagesResponse.data.results && Array.isArray(imagesResponse.data.results)) {
      // Paginated response
      versionImages.value = imagesResponse.data.results
    } else {
      // Fallback
      versionImages.value = []
    }
  } catch (err) {
    console.error('Error loading images:', err)
    versionImages.value = []
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

const toggleLocation = (index: number) => {
  expandedLocations.value[index] = !expandedLocations.value[index]
}

const loadMoreLocations = async () => {
  if (locationsHasMore.value && !locationsLoadingMore.value) {
    await loadLocations(true)
  }
}

onMounted(async () => {
  // Load version data first (fast) - UI will show immediately
  await loadVersion()
  
  // Start loading additional data in background (non-blocking)
  loadAllData()
})
</script>

<style scoped>
.component-version-detail {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
  background: #ffffff;
  min-height: 100vh;
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

.cursor-pointer {
  cursor: pointer;
}

.expand-icon {
  transition: transform 0.2s ease;
}

.location-card {
  transition: all 0.2s ease;
}

.location-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.load-more-btn {
  min-width: 200px;
  transition: all 0.2s ease;
}

.load-more-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
}

.loading-animation {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  text-align: center;
}

.loading-text {
  margin-top: 16px;
  text-align: center;
}

.loading-text h4 {
  color: #1976d2;
  margin-bottom: 8px;
}

.loading-text p {
  color: #666;
  font-size: 0.9rem;
}

.main-loading-animation {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.main-loading-text h2 {
  color: #1976d2;
  font-weight: 600;
}

.main-loading-text p {
  color: #666;
  font-size: 1.1rem;
}

.initializing-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  text-align: center;
}

.initializing-animation {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px;
  text-align: center;
}

.initializing-text p {
  color: #999;
  font-size: 0.9rem;
  margin-top: 12px;
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
