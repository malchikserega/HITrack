<template>
  <div class="component-matrix-view">
    <v-container fluid class="pa-0">
      <v-row justify="center">
        <v-col cols="12" md="11" lg="10" xl="9">
          <h1 class="text-h4 mb-4 font-weight-black">Component Matrix</h1>
          <v-card class="mb-4 d-flex flex-column wide-card">
            <v-card-text>
              <v-select
                v-model="comparisonType"
                :items="[
                  { title: 'Repository Comparison', value: 'repository' },
                  { title: 'Image Comparison', value: 'image' }
                ]"
                label="Comparison Type"
                class="mb-4"
              />
              
              <v-autocomplete
                v-if="comparisonType === 'repository'"
                v-model="selectedRepos"
                :items="repositories"
                item-title="name"
                item-value="uuid"
                label="Select repositories"
                multiple
                chips
                clearable
                class="mb-4"
                :loading="reposLoading"
                :disabled="reposLoading"
              />

              <template v-if="comparisonType === 'repository' && selectedRepos.length > 0">
                <v-card v-for="repo in selectedRepos" :key="repo" class="mb-4">
                  <v-card-text>
                    <div class="d-flex align-center mb-2">
                      <span class="text-subtitle-1 font-weight-medium">{{ getRepoName(repo) }}</span>
                      <v-spacer></v-spacer>
                      <v-btn
                        size="small"
                        color="primary"
                        variant="text"
                        @click="loadTags(repo)"
                        :loading="loadingTags[repo]"
                      >
                        <v-icon>mdi-refresh</v-icon>
                      </v-btn>
                    </div>
                    <v-autocomplete
                      v-model="selectedTags[repo]"
                      :items="availableTags[repo] || []"
                      item-title="tag"
                      item-value="tag"
                      label="Select tag(s)"
                      :loading="loadingTags[repo]"
                      :disabled="loadingTags[repo]"
                      clearable
                      multiple
                    >
                      <template v-slot:item="{ props, item }">
                        <v-list-item v-bind="props">
                          <v-chip
                            :color="getProcessingStatusColor(item.raw.processing_status)"
                            size="x-small"
                            class="mr-2"
                          >
                            <v-icon size="x-small" class="mr-1">
                              {{ getProcessingStatusIcon(item.raw.processing_status) }}
                            </v-icon>
                            Processing — {{ item.raw.processing_status }}
                          </v-chip>
                        </v-list-item>
                      </template>
                    </v-autocomplete>
                  </v-card-text>
                </v-card>
              </template>

              <v-autocomplete
                v-if="comparisonType === 'image'"
                v-model="selectedImages"
                :items="images"
                item-title="name"
                item-value="uuid"
                label="Select images"
                multiple
                chips
                clearable
                class="mb-4"
                :loading="imagesLoading"
                :disabled="imagesLoading"
                :search="imagesSearchRef"
                @update:search="val => imagesSearchRef = val"
              >
                <template #item="{ item, props }">
                  <v-list-item v-bind="props">
                    <template #prepend>
                      <v-chip
                        :color="item.raw.has_sbom === true || item.raw.has_sbom === 'true' ? 'success' : 'error'"
                        size="x-small"
                        class="mr-2"
                      >
                        <v-icon size="small" class="mr-1">
                          {{ item.raw.has_sbom === true || item.raw.has_sbom === 'true' ? 'mdi-check' : 'mdi-alert' }}
                        </v-icon>
                        {{ item.raw.has_sbom === true || item.raw.has_sbom === 'true' ? 'SBOM' : 'No SBOM' }}
                      </v-chip>
                    </template>
                  </v-list-item>
                </template>
                <template #selection="{ item, index }">
                  <v-chip
                    :key="item.raw.uuid"
                    :color="item.raw.has_sbom === true || item.raw.has_sbom === 'true' ? 'success' : 'error'"
                    size="small"
                    class="mr-1"
                  >
                    <v-icon size="small" class="mr-1">
                      {{ item.raw.has_sbom === true || item.raw.has_sbom === 'true' ? 'mdi-check' : 'mdi-alert' }}
                    </v-icon>
                    {{ item.raw.name }}
                  </v-chip>
                </template>
              </v-autocomplete>
              <v-btn 
                color="primary" 
                :disabled="(comparisonType === 'repository' && selectedRepos.length === 0) || 
                          (comparisonType === 'image' && selectedImages.length === 0) || 
                          loading" 
                @click="fetchMatrix" 
                :loading="loading"
              >
                Build Matrix
              </v-btn>
            </v-card-text>
          </v-card>

          <v-card v-if="matrixData" class="wide-card">
            <v-card-text>
              <div class="d-flex align-center mb-2">
                <v-text-field
                  v-model="searchQuery"
                  label="Search components"
                  prepend-inner-icon="mdi-magnify"
                  clearable
                  class="mb-4"
                  density="compact"
                />
                <v-spacer />
                <v-btn
                  class="ml-2"
                  color="secondary"
                  variant="text"
                  :disabled="!matrixData"
                  @click="exportMatrixToExcel"
                  style="min-width: 0;"
                >
                  <v-icon>mdi-file-chart-outline</v-icon>
                  <span style="opacity: 0.6; font-size: 0.9em; margin-left: 4px;">xlsx</span>
                </v-btn>
                <v-btn
                  class="ml-2"
                  color="secondary"
                  variant="text"
                  :disabled="!matrixData"
                  @click="exportMatrixToImage"
                  style="min-width: 0;"
                >
                  <v-icon>mdi-image</v-icon>
                  <span style="opacity: 0.6; font-size: 0.9em; margin-left: 4px;">png</span>
                </v-btn>
              </div>
              <div class="matrix-scroll">
                <table class="matrix-table">
                  <thead>
                    <tr>
                      <th class="sticky-col">Component</th>
                      <th v-for="col in matrixData.columns" :key="col.label">{{ col.label }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="component in filteredComponents" :key="component">
                      <td class="sticky-col">
                        <div class="d-flex align-center">
                          {{ component }}
                          <v-chip
                            size="x-small"
                            :color="getTypeColor(matrixData.component_types[component])"
                            class="mr-2"
                          >
                            {{ matrixData.component_types[component] }}
                          </v-chip>
                        </div>
                      </td>
                      <td
                        v-for="col in matrixData.columns"
                        :key="col.label"
                        :class="getCellBgClass(matrixData.matrix[component][col.label])"
                      >
                        <div class="d-flex align-center justify-center">
                          <v-chip
                            v-if="matrixData.matrix[component][col.label].version"
                            color="primary"
                            size="small"
                            class="font-weight-medium mr-1"
                          >
                            {{ matrixData.matrix[component][col.label].version }}
                            <v-tooltip v-if="matrixData.matrix[component][col.label].has_vuln" location="top">
                              <template #activator="{ props }">
                                <v-icon
                                  v-bind="props"
                                  color="error"
                                  size="x-small"
                                  class="ml-1"
                                  style="vertical-align: middle;"
                                >
                                  mdi-spider
                                </v-icon>
                              </template>
                              Vulnerable
                            </v-tooltip>
                          </v-chip>
                          <v-tooltip v-if="matrixData.matrix[component][col.label].version && matrixData.matrix[component][col.label].latest_version" location="top">
                            <template #activator="{ props }">
                              <v-icon
                                v-if="matrixData.matrix[component][col.label].latest_version"
                                v-bind="props"
                                :color="getVersionStatusColor(matrixData.matrix[component][col.label])"
                                size="small"
                              >
                                {{ getVersionStatusIcon(matrixData.matrix[component][col.label]) }}
                              </v-icon>
                            </template>
                            <span v-if="matrixData.matrix[component][col.label].version !== matrixData.matrix[component][col.label].latest_version">
                              New version available: {{ matrixData.matrix[component][col.label].latest_version }}
                            </span>
                            <span v-else>
                              Version is up to date
                            </span>
                          </v-tooltip>
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </v-container>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import type { Ref } from 'vue'
import api from '../plugins/axios'
import { notificationService } from '../plugins/notifications'
import * as XLSX from 'xlsx'
import html2canvas from 'html2canvas'

const comparisonType = ref('repository')
const repositories = ref<any[]>([])
const images = ref<any[]>([])
const reposLoading = ref(false)
const imagesLoading = ref(false)
const imagesPage = ref(1)
const imagesPageSize = 100
const imagesTotal = ref(0)
const imagesSearchRef = ref('')
const imagesMenu = ref<HTMLElement | null>(null)
const selectedRepos = ref<string[]>([])
const selectedImages = ref<string[]>([])
const loading = ref(false)
const matrixData = ref<any | null>(null)
const searchQuery = ref('')
const selectedTags = ref<{ [key: string]: string[] }>({})
const availableTags = ref<{ [key: string]: any[] }>({})
const loadingTags = ref<{ [key: string]: boolean }>({})

// Computed property for filtered components
const filteredComponents = computed(() => {
  if (!matrixData.value) return []
  if (!searchQuery.value) return matrixData.value.components
  const query = searchQuery.value.toLowerCase()
  return matrixData.value.components.filter((component: string) => 
    component.toLowerCase().includes(query)
  )
})

watch(comparisonType, () => {
  selectedRepos.value = []
  selectedImages.value = []
  matrixData.value = null
  if (comparisonType.value === 'image') {
    fetchImages(true)
  }
})

const fetchRepositories = async () => {
  reposLoading.value = true
  try {
    const resp = await api.get('repositories/', { params: { page_size: 100 } })
    repositories.value = resp.data.results
  } catch (e) {
    notificationService.error('Failed to fetch repositories')
  } finally {
    reposLoading.value = false
  }
}

const fetchImages = async (reset = false) => {
  if (imagesLoading.value) return
  imagesLoading.value = true
  try {
    if (reset) {
      images.value = []
      imagesPage.value = 1
    }
    const params: any = {
      page: imagesPage.value,
      page_size: imagesPageSize,
      dropdown: 1,
    }
    if (imagesSearchRef.value) params.search = imagesSearchRef.value
    const resp = await api.get('images/', { params })
    if (reset) {
      images.value = resp.data.results
    } else {
      images.value = [...images.value, ...resp.data.results]
    }
    imagesTotal.value = resp.data.count
  } catch (e) {
    notificationService.error('Failed to fetch images')
  } finally {
    imagesLoading.value = false
  }
}

const getCellBgClass = (versionData: any) => {
  if (!versionData || !versionData.version || !versionData.latest_version) return ''
  if (versionData.version === versionData.latest_version) {
    return 'cell-up-to-date'
  }
  return 'cell-outdated'
}

const getVersionStatusColor = (versionData: any) => {
  if (!versionData.latest_version) return ''
  if (versionData.version === versionData.latest_version) return 'success'
  return 'error'
}

const getVersionStatusIcon = (versionData: any) => {
  if (!versionData.latest_version) return ''
  if (versionData.version === versionData.latest_version) return 'mdi-check'
  return 'mdi-arrow-up-bold'
}

const getRepoName = (uuid: string) => {
  const repo = repositories.value.find(r => r.uuid === uuid)
  return repo ? repo.name : uuid
}

const loadTags = async (repoUuid: string) => {
  loadingTags.value[repoUuid] = true
  try {
    const resp = await api.get(`repositories/${repoUuid}/tags-list/`)
    availableTags.value[repoUuid] = resp.data.results || []
  } catch (e) {
    notificationService.error('Failed to fetch repository tags')
    availableTags.value[repoUuid] = []
  } finally {
    loadingTags.value[repoUuid] = false
  }
}

watch(selectedRepos, (newRepos, oldRepos) => {
  // Load tags for newly selected repos
  newRepos.forEach(repo => {
    if (!oldRepos.includes(repo)) {
      loadTags(repo)
    }
  })
  // Clear tags for unselected repos
  oldRepos.forEach(repo => {
    if (!newRepos.includes(repo)) {
      delete selectedTags.value[repo]
      delete availableTags.value[repo]
    }
  })
})

const fetchMatrix = async () => {
  if (comparisonType.value === 'repository' && selectedRepos.value.length === 0) return
  if (comparisonType.value === 'image' && selectedImages.value.length === 0) return

  if (comparisonType.value === 'repository') {
    const missingTagRepo = selectedRepos.value.find(repo => !selectedTags.value[repo] || selectedTags.value[repo].length === 0)
    if (missingTagRepo) {
      notificationService.error('Please select a tag for each repository')
      return
    }
  }

  loading.value = true
  try {
    const data = {
      type: comparisonType.value,
      ...(comparisonType.value === 'repository' 
        ? { repository_tags: selectedRepos.value.flatMap(repo =>
            (selectedTags.value[repo] || []).map(tag => ({
              repo_uuid: repo,
              tag
            }))
          ) }
        : { image_uuids: selectedImages.value }
      )
    }
    const resp = await api.post('component-matrix/', data)
    matrixData.value = resp.data
  } catch (e) {
    notificationService.error('Failed to fetch component matrix')
  } finally {
    loading.value = false
  }
}

const exportMatrixToExcel = () => {
  if (!matrixData.value) return
  const header = ['Component', 'Type', ...matrixData.value.columns.map((col: any) => col.label)]
  const rows = matrixData.value.components.map((component: string) => {
    const row = [
      component,
      matrixData.value.component_types[component] || 'unknown',
      ...matrixData.value.columns.map((col: any) => {
        const cell = matrixData.value.matrix[component][col.label]
        let value = cell.version || ''
        if (cell.has_vuln) value += ' (vuln)'
        if (cell.latest_version && cell.version !== cell.latest_version) value += ` (latest: ${cell.latest_version})`
        return value
      })
    ]
    return row
  })
  const worksheet = XLSX.utils.aoa_to_sheet([header, ...rows])
  worksheet['!cols'] = header.map(() => ({ wch: 40 }))
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, worksheet, 'Component Matrix')
  XLSX.writeFile(workbook, 'component_matrix.xlsx')
}

const exportMatrixToImage = async () => {
  if (!matrixData.value) return
  
  try {
    const table = document.querySelector('.matrix-table')
    if (!table) return

    // Set a higher scale for better resolution
    const canvas = await html2canvas(table as HTMLElement, {
      scale: 2, // Higher scale for better resolution
      useCORS: true, // Enable CORS for images
      logging: false, // Disable logging
      backgroundColor: '#ffffff', // White background
      windowWidth: table.scrollWidth,
      windowHeight: table.scrollHeight,
    })

    // Convert canvas to blob
    canvas.toBlob((blob) => {
      if (!blob) return
      
      // Create download link
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'component_matrix.png'
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
    }, 'image/png', 1.0)
  } catch (error) {
    notificationService.error('Failed to generate image')
    console.error('Error generating image:', error)
  }
}

function getProcessingStatusColor(status: string) {
  switch (status) {
    case 'success': return 'success';
    case 'pending': return 'warning';
    case 'in_process': return 'info';
    case 'error': return 'error';
    default: return 'grey';
  }
}

function getProcessingStatusIcon(status: string) {
  switch (status) {
    case 'success': return 'mdi-check-circle';
    case 'pending': return 'mdi-timer-sand';
    case 'in_process': return 'mdi-progress-clock';
    case 'error': return 'mdi-alert-circle';
    default: return 'mdi-help-circle';
  }
}

const onImagesScroll = (e: Event) => {
  const el = e.target as HTMLElement
  if (!el) return
  if (el.scrollTop + el.clientHeight >= el.scrollHeight - 10) {
    if (images.value.length < imagesTotal.value && !imagesLoading.value) {
      imagesPage.value += 1
      fetchImages()
    }
  }
}

watch(imagesSearchRef, () => {
  fetchImages(true)
})

const getTypeColor = (type: string | undefined) => {
  if (!type) return 'grey'
  const colors: { [key: string]: string } = {
    'unknown': 'grey',
    'npm': 'red',
    'pypi': 'blue',
    'maven': 'green',
    'gem': 'purple',
    'go': 'cyan',
    'nuget': 'orange',
    'deb': 'grey'
  }
  return colors[type.toLowerCase()] || 'grey'
}

onMounted(() => {
  fetchRepositories()
})
</script>

<style scoped>
.component-matrix-view {
  padding: 20px;
}
.wide-card {
  width: 100%;
  max-width: 100%;
  min-width: 900px;
  box-sizing: border-box;
}
.matrix-scroll {
  width: 100%;
  overflow-x: auto;
  overflow-y: auto;
  max-height: 70vh;
}
.matrix-table {
  border-collapse: collapse;
  font-size: 0.65rem;
  min-width: 250px;
}
.matrix-table th, .matrix-table td {
  border: 1px solid #e0e0e0;
  padding: 4px 10px;
  text-align: center;
  white-space: nowrap;
}
.matrix-table th {
  background: #f8f9fa;
  font-weight: 700;
  position: sticky;
  top: 0;
  z-index: 2;
}
.sticky-col {
  position: sticky;
  left: 0;
  background: #fff;
  z-index: 3;
  font-weight: 700;
  text-align: left !important;
}
.matrix-table tr:hover td {
  background: #f5f5f5;
}
.cell-up-to-date {
  background-color: #e8f5e9 !important;
}
.cell-outdated {
  background-color: #ffebee !important;
}
</style>