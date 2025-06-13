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

              <v-autocomplete
                v-else
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
              >
                <template v-slot:item="{ props, item }">
                  <v-list-item v-bind="props">
                    <template v-slot:prepend>
                      <v-chip
                        :color="item.raw.has_sbom ? 'success' : 'error'"
                        size="x-small"
                        class="mr-2"
                      >
                        <v-icon size="small" class="mr-1">
                          {{ item.raw.has_sbom ? 'mdi-check' : 'mdi-alert' }}
                        </v-icon>
                        {{ item.raw.has_sbom ? 'SBOM' : 'No SBOM' }}
                      </v-chip>
                    </template>
                  </v-list-item>
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
                      <td class="sticky-col">{{ component }}</td>
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
import api from '../plugins/axios'
import { notificationService } from '../plugins/notifications'
import * as XLSX from 'xlsx'

const comparisonType = ref('repository')
const repositories = ref<any[]>([])
const images = ref<any[]>([])
const reposLoading = ref(false)
const imagesLoading = ref(false)
const selectedRepos = ref<string[]>([])
const selectedImages = ref<string[]>([])
const loading = ref(false)
const matrixData = ref<any | null>(null)
const searchQuery = ref('')

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
})

const fetchRepositories = async () => {
  reposLoading.value = true
  try {
    const resp = await api.get('repositories/', { params: { page_size: 1000 } })
    repositories.value = resp.data.results
  } catch (e) {
    notificationService.error('Failed to fetch repositories')
  } finally {
    reposLoading.value = false
  }
}

const fetchImages = async () => {
  imagesLoading.value = true
  try {
    const resp = await api.get('images/', { params: { page_size: 1000, dropdown: 1 } })
    images.value = resp.data.results
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

const fetchMatrix = async () => {
  if (comparisonType.value === 'repository' && selectedRepos.value.length === 0) return
  if (comparisonType.value === 'image' && selectedImages.value.length === 0) return
  loading.value = true
  try {
    const data = {
      type: comparisonType.value,
      ...(comparisonType.value === 'repository' 
        ? { repository_uuids: selectedRepos.value }
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
  const header = ['Component', ...matrixData.value.columns.map((col: any) => col.label)]
  const rows = matrixData.value.components.map((component: string) => {
    const row = [component]
    matrixData.value.columns.forEach((col: any) => {
      const cell = matrixData.value.matrix[component][col.label]
      let value = cell.version || ''
      if (cell.has_vuln) value += ' (vuln)'
      if (cell.latest_version && cell.version !== cell.latest_version) value += ` (latest: ${cell.latest_version})`
      row.push(value)
    })
    return row
  })
  const worksheet = XLSX.utils.aoa_to_sheet([header, ...rows])
  worksheet['!cols'] = header.map(() => ({ wch: 40 }))
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, worksheet, 'Component Matrix')
  XLSX.writeFile(workbook, 'component_matrix.xlsx')
}

onMounted(() => {
  fetchRepositories()
  fetchImages()
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