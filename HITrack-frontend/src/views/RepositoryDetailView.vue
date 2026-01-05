<template>
  <v-container>
    <v-row>
      <v-col cols="12">
        <v-btn variant="text" @click="goBack" class="mb-2">
          <v-icon left>mdi-arrow-left</v-icon>Back
        </v-btn>
        
        <!-- Repository Info with Loading -->
        <div v-if="repositoryLoading" class="d-flex align-center mb-4">
          <v-progress-circular indeterminate color="primary" size="24" class="mr-3"></v-progress-circular>
          <span class="text-body-1">Loading repository information...</span>
        </div>
        
        <div v-else>
          <h1 class="text-h4 font-weight-black mb-2">Repository: {{ repository?.name }}</h1>
          <v-chip class="mr-2">Type: {{ repository?.repository_type }}</v-chip>
          <v-chip class="mr-2">Tags: {{ repository?.tag_count }}</v-chip>
          <v-chip class="mr-2">URL: {{ repository?.url }}</v-chip>
        </div>
      </v-col>
    </v-row>
    <v-row>
      <v-col cols="12" md="6">
        <div v-if="chartsLoading" class="d-flex flex-column align-center justify-center pa-8">
          <v-progress-circular indeterminate color="primary" size="48"></v-progress-circular>
          <span class="text-body-1 mt-3">Loading charts...</span>
        </div>
        <div v-else class="chart-container">
          <!-- Chart Header with consistent height -->
          <div class="chart-header">
            <h3 class="text-h6 font-weight-bold chart-title">Components vs Vulnerabilities</h3>
            <div class="chart-spacer"></div>
          </div>
          

          
          <div class="chart-wrapper">
            <Bar :data="barChartData" :options="barChartOptions" />
          </div>
        </div>
      </v-col>
      <v-col cols="12" md="6">
        <div v-if="chartsLoading" class="d-flex flex-column align-center justify-center pa-8">
          <v-progress-circular indeterminate color="primary" size="48"></v-progress-circular>
          <span class="text-body-1 mt-3">Loading charts...</span>
        </div>
        <div v-else class="chart-container">
          <!-- Chart Header with Filter -->
          <div class="chart-header">
            <h3 class="text-h6 font-weight-bold chart-title">Vulnerability Trend Analysis</h3>
            <v-btn
              :color="showOnlyVulnerableVersions ? 'primary' : 'grey'"
              :variant="showOnlyVulnerableVersions ? 'elevated' : 'outlined'"
              size="small"
              prepend-icon="mdi-filter-variant"
              @click="showOnlyVulnerableVersions = !showOnlyVulnerableVersions"
              :disabled="chartsLoading"
              class="chart-filter-btn"
            >
              {{ showOnlyVulnerableVersions ? 'Show All' : 'Vulnerable Only' }}
            </v-btn>
          </div>
          

          
          <div class="chart-wrapper">
            <Bar :data="comboChartData as any" :options="comboChartOptions" />
          </div>
        </div>
      </v-col>
    </v-row>
    <v-row>
      <v-col cols="12">
        <div class="d-flex align-center mb-2">
          <h2 class="text-h6 font-weight-bold mb-0">Tags</h2>
          <v-progress-circular v-if="tagsLoading" indeterminate color="primary" size="20" class="ml-3"></v-progress-circular>
        </div>
        <div class="d-flex align-center mb-2">
          <v-text-field
            v-model="tagSearch"
            append-inner-icon="mdi-magnify"
            label="Search tags"
            hide-details
            density="compact"
            class="mr-4"
            style="max-width: 300px;"
            @keyup.enter="fetchTags"
            @click:append-inner="fetchTags"
          />
          <v-spacer></v-spacer>
          <v-btn
            color="primary"
            prepend-icon="mdi-plus"
            @click="showAddTagDialog = true"
            :loading="creatingTag"
          >
            Add New Tag
          </v-btn>
          <v-tooltip :text="getScanTooltip()" location="top">
            <template v-slot:activator="{ props }">
              <div v-bind="props">
                <v-btn
                  icon="mdi-refresh"
                  variant="tonal"
                  size="default"
                  color="primary"
                  :disabled="isScanDisabled()"
                  :loading="scanning"
                  @click="onScanRepository"
                  class="ml-2"
                />
              </div>
            </template>
          </v-tooltip>
          <v-select
            :items="[10, 20, 50, 100]"
            v-model="tagsPerPage"
            label="Items per page"
            style="max-width: 150px"
            hide-details
            density="compact"
            variant="outlined"
            class="ml-4"
            @update:model-value="onTagsPerPageChange"
          />
        </div>
        <v-data-table
          :headers="headers"
          :items="tags"
          :loading="tagsLoading"
          :items-per-page="tagsPerPage"
          :page="tagsPage"
          :server-items-length="tagsTotal"
          hide-default-footer
          item-class="clickable-row"
          @click:row="onTagRowClick"
          @update:sort-by="onSortChange"
        >
          <template #item.tag="{ item }">
            <div class="d-flex align-center">
              <span class="font-weight-medium">{{ item.tag }}</span>
              <div v-if="item.releases && item.releases.length > 0" class="ml-2 d-flex gap-1">
                <v-chip
                  v-for="release in item.releases"
                  :key="release.uuid"
                  size="x-small"
                  color="success"
                  variant="tonal"
                  class="release-chip"
                >
                  {{ release.name }}
                </v-chip>
              </div>
            </div>
          </template>
          <template #item.processing_status="{ item }">
            <v-chip
              size="x-small"
              :color="getTagStatusColor(item.processing_status || 'none')"
              class="ml-2"
              variant="tonal"
              style="font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;"
            >
              {{ getProcessingStatusTooltip(item.processing_status || 'none') }}
            </v-chip>
          </template>
          <template #item.actions="{ item }">
            <v-tooltip :text="getActionTooltip(item, 'process')">
              <template v-slot:activator="{ props }">
                <v-btn
                  v-bind="props"
                  icon="mdi-code-tags"
                  variant="tonal"
                  size="x-small"
                  color="primary"
                  :disabled="isActionDisabled(item, 'process')"
                  @click.stop="onProcessTag(item)"
                />
              </template>
            </v-tooltip>
            <v-tooltip :text="getActionTooltip(item, 'rescan')">
              <template v-slot:activator="{ props }">
                <v-btn
                  v-bind="props"
                  icon="mdi-cog-refresh"
                  variant="tonal"
                  size="x-small"
                  color="info"
                  class="ml-2"
                  :disabled="isActionDisabled(item, 'rescan')"
                  @click.stop="onRescanTagImages(item)"
                />
              </template>
            </v-tooltip>
            <v-tooltip text="Reanalyze SBOM for all images in this tag">
              <template v-slot:activator="{ props }">
                <v-btn
                  v-bind="props"
                  icon="mdi-file-document-refresh"
                  variant="tonal"
                  size="x-small"
                  color="warning"
                  class="ml-2"
                  :disabled="isActionDisabled(item, 'rescan')"
                  :loading="reanalyzingSbom === item.uuid"
                  @click.stop="onReanalyzeSbom(item)"
                />
              </template>
            </v-tooltip>
            <v-tooltip text="Delete tag">
              <template v-slot:activator="{ props }">
                <v-btn
                  v-bind="props"
                  icon="mdi-delete"
                  variant="tonal"
                  size="x-small"
                  color="error"
                  class="ml-2"
                  :loading="deletingTag === item.uuid"
                  @click.stop="onDeleteTag(item)"
                />
              </template>
            </v-tooltip>
          </template>
          <template v-slot:item.updated_at="{ item }">
            {{ $formatDate(item.updated_at) }}
          </template>
        </v-data-table>
        <div class="d-flex align-center justify-end mt-2 gap-4">
          <v-pagination
            v-model="tagsPage"
            :length="tagsPageCount"
            @update:model-value="fetchTags"
            :total-visible="7"
            density="comfortable"
          />
        </div>
      </v-col>
    </v-row>

    <!-- Add New Tag Dialog -->
    <v-dialog 
      v-model="showAddTagDialog" 
      max-width="500px" 
      persistent
      @keydown.esc="cancelAddTag"
    >
      <v-card>
        <v-card-title class="text-h6 font-weight-bold pa-4 pb-2">
          <v-icon class="mr-2" color="primary">mdi-tag-plus</v-icon>
          Add New Tag
        </v-card-title>
        <v-card-text class="pa-4 pt-0">
          <v-form ref="addTagForm" @submit.prevent="createNewTag">
            <v-text-field
              v-model="newTagName"
              label="Tag Name"
              placeholder="Enter tag name (e.g., v1.0.0, latest)"
              :rules="tagNameRules"
              required
              autofocus
              @keyup.enter="createNewTag"
            />
            <v-textarea
              v-model="newTagDescription"
              label="Description (Optional)"
              placeholder="Brief description of this tag"
              rows="3"
              auto-grow
            />
          </v-form>
        </v-card-text>
        <v-card-actions class="pa-4 pt-0">
          <v-spacer></v-spacer>
          <v-btn
            variant="text"
            @click="cancelAddTag"
            :disabled="creatingTag"
          >
            Cancel
          </v-btn>
          <v-btn
            color="primary"
            @click="createNewTag"
            :loading="creatingTag"
            :disabled="!newTagName || !isValidTagName"
          >
            Create Tag
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete Tag Confirmation Dialog -->
    <v-dialog 
      v-model="showDeleteDialog" 
      max-width="400px" 
      persistent
      @keydown.esc="cancelDelete"
    >
      <v-card>
        <v-card-title class="text-h6 font-weight-bold pa-4 pb-2">
          <v-icon class="mr-2" color="error">mdi-delete-alert</v-icon>
          Delete Tag
        </v-card-title>
        <v-card-text class="pa-4 pt-0">
          <p class="text-body-1">
            Are you sure you want to delete tag <strong>"{{ tagToDelete?.tag }}"</strong>?
          </p>
          <p class="text-body-2 text-medium-emphasis mt-2">
            This action cannot be undone and will remove all associated data.
          </p>
        </v-card-text>
        <v-card-actions class="pa-4 pt-0">
          <v-spacer></v-spacer>
          <v-btn
            variant="text"
            @click="cancelDelete"
            :disabled="!!deletingTag"
          >
            Cancel
          </v-btn>
          <v-btn
            color="error"
            @click="confirmDelete"
            :loading="!!deletingTag"
          >
            Delete
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../plugins/axios'
import { notificationService } from '../plugins/notifications'
import { Bar, Line } from 'vue-chartjs'
import type { RepositoryTag } from '../types/interfaces'
import {
  Chart as ChartJS,
  Title,
  Tooltip,
  Legend,
  BarElement,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  LineController,
  Filler
} from 'chart.js'
import type { ChartData } from 'chart.js'

ChartJS.register(
  Title,
  Tooltip,
  Legend,
  BarElement,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  LineController,
  Filler
)

const route = useRoute()
const router = useRouter()
const repository = ref<any>(null)
const loading = ref(true)
const repositoryLoading = ref(true)
const tagsLoading = ref(true)
const chartsLoading = ref(true)

const headers = [
  { title: 'Tag', key: 'tag', sortable: false },
  { title: 'Status', key: 'processing_status', sortable: false },
  { title: 'Vulnerabilities', key: 'findings', sortable: false },
  { title: 'Components', key: 'components', sortable: false },
  { title: 'Updated', key: 'updated_at', sortable: false },
  { title: 'Actions', key: 'actions', sortable: false }
]

const tags = ref<any[]>([])
const tagSearch = ref('')
const tagsPage = ref(1)
const tagsPerPage = ref(25)
const tagsTotal = ref(0)
interface SortItem { key: string; order: 'asc' | 'desc' }
const tagsSortBy = ref<SortItem[]>([{ key: 'tag', order: 'desc' }])
const tagsPageCount = computed(() => Math.ceil(tagsTotal.value / tagsPerPage.value) || 1)

const tagsForCharts = ref<any[]>([])
const showOnlyVulnerableVersions = ref(false)

// Add new tag functionality
const showAddTagDialog = ref(false)
const creatingTag = ref(false)
const reanalyzingSbom = ref<string | null>(null)
const newTagName = ref('')
const newTagDescription = ref('')
const addTagForm = ref<any>(null)
const deletingTag = ref<string | null>(null)
const showDeleteDialog = ref(false)
const tagToDelete = ref<any>(null)
const scanning = ref(false)

const tagNameRules = [
  (v: string) => !!v || 'Tag name is required',
  (v: string) => v.length >= 1 || 'Tag name must be at least 1 character',
  (v: string) => v.length <= 255 || 'Tag name must be less than 255 characters',
  (v: string) => /^[a-zA-Z0-9._-]+$/.test(v) || 'Tag name can only contain letters, numbers, dots, underscores, and hyphens'
]

const isValidTagName = computed(() => {
  return newTagName.value && 
         newTagName.value.length >= 1 && 
         newTagName.value.length <= 255 && 
         /^[a-zA-Z0-9._-]+$/.test(newTagName.value)
})

const createNewTag = async () => {
  if (!isValidTagName.value) {
    notificationService.error('Please enter a valid tag name')
    return
  }

  creatingTag.value = true
  try {
    const response = await api.post(`repositories/${route.params.uuid}/create_tag/`, {
      tag: newTagName.value,
      description: newTagDescription.value
    })
    
    notificationService.success('Tag created successfully')
    showAddTagDialog.value = false
    resetAddTagForm()
    await fetchTags() // Refresh the tags list
  } catch (error: any) {
    console.error('Error creating tag:', error)
    if (error.response?.status === 409) {
      notificationService.error('Tag already exists')
    } else if (error.response?.data?.error) {
      notificationService.error(error.response.data.error)
    } else {
      notificationService.error('Failed to create tag')
    }
  } finally {
    creatingTag.value = false
  }
}

const cancelAddTag = () => {
  showAddTagDialog.value = false
  resetAddTagForm()
}

const resetAddTagForm = () => {
  newTagName.value = ''
  newTagDescription.value = ''
  if (addTagForm.value) {
    addTagForm.value.reset()
  }
}

const onDeleteTag = async (tag: any) => {
  if (!tag.uuid) {
    notificationService.error('Cannot delete tag: missing UUID')
    return
  }

  // Show confirmation dialog
  tagToDelete.value = tag
  showDeleteDialog.value = true
}

const cancelDelete = () => {
  showDeleteDialog.value = false
  tagToDelete.value = null
}

const confirmDelete = async () => {
  if (!tagToDelete.value?.uuid) {
    notificationService.error('Cannot delete tag: missing UUID')
    return
  }

  deletingTag.value = tagToDelete.value.uuid
  try {
    await api.delete(`repository-tags/${tagToDelete.value.uuid}/`)
    notificationService.success('Tag deleted successfully')
    await fetchTags() // Refresh the tags list
  } catch (error: any) {
    console.error('Error deleting tag:', error)
    if (error.response?.status === 404) {
      notificationService.error('Tag not found')
    } else if (error.response?.data?.error) {
      notificationService.error(error.response.data.error)
    } else {
      notificationService.error('Failed to delete tag')
    }
  } finally {
    deletingTag.value = null
    showDeleteDialog.value = false
    tagToDelete.value = null
  }
}

const fetchTagsForCharts = async () => {
  chartsLoading.value = true
  try {
    const resp = await api.get(`repositories/${route.params.uuid}/tags-graph/`)
    tagsForCharts.value = resp.data
  } catch (e) {
    tagsForCharts.value = []
  } finally {
    chartsLoading.value = false
  }
}

// Filter data based on vulnerability filter
const filteredChartData = computed(() => {
  if (!showOnlyVulnerableVersions.value) {
    return tagsForCharts.value
  }
  
  return tagsForCharts.value.filter((tag: any) => 
    tag.findings && tag.findings > 0 && tag.components && tag.components > 0
  )
})

const tagLabels = computed(() => filteredChartData.value.map((tag: any) => tag.tag))
const findingsData = computed(() => filteredChartData.value.map((tag: any) => tag.findings))
const uniqueComponentsData = computed(() => filteredChartData.value.map((tag: any) => tag.components))

const barChartData = computed(() => ({
  labels: tagLabels.value,
  datasets: [
    {
      label: 'Vulnerabilities',
      borderColor: '#b39ddb',
      backgroundColor: 'rgba(179,154,226,0.42)',
      data: findingsData.value,
    },
    {
      label: 'Components',
      backgroundColor: 'rgba(174, 226, 255, 0.7)',
      borderColor: '#aee2ff',
      data: uniqueComponentsData.value,
    },
  ]
}))
const barChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: true },
    title: { display: false },
    tooltip: { enabled: true },
  },
  scales: {
    x: { stacked: false, grid: { display: false } },
    y: { stacked: false, beginAtZero: true, grid: { color: '#eee' } }
  },
  layout: {
    padding: {
      top: 0,
      bottom: 0,
      left: 0,
      right: 0
    }
  }
}

function movingAverage(arr: number[], windowSize = 5): number[] {
  return arr.map((_, idx, a) => {
    const start = Math.max(0, idx - Math.floor(windowSize / 2));
    const end = Math.min(a.length, idx + Math.ceil(windowSize / 2));
    const window = a.slice(start, end);
    return window.reduce((sum, v) => sum + v, 0) / window.length;
  });
}

const vulnTrendData = computed(() => movingAverage(findingsData.value, 5));

const comboChartData = computed(() => ({
  labels: tagLabels.value,
  datasets: [
    {
      type: 'bar',
      label: 'Components',
      backgroundColor: 'rgba(174, 226, 255, 0.7)',
      borderColor: '#aee2ff',
      data: uniqueComponentsData.value,
      order: 1,
      stack: 'combined',
    },
    {
      type: 'line',
      label: 'Vulnerabilities',
      borderColor: '#b39ddb',
      backgroundColor: 'rgba(179,157,219,0.15)',
      data: findingsData.value,
      tension: 0.3,
      fill: false,
      pointRadius: 6,
      pointBackgroundColor: '#b2f2e5',
      order: 2,
    },
    {
      type: 'line',
      label: 'Vuln Trend',
      borderColor: '#ff9800',
      backgroundColor: 'rgba(255,152,0,0.1)',
      data: vulnTrendData.value,
      borderDash: [8, 4],
      pointRadius: 0,
      fill: false,
      order: 3,
    }
  ]
}))
const comboChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: true },
    title: { display: false },
    tooltip: { enabled: true },
  },
  scales: {
    x: { grid: { display: false } },
    y: { beginAtZero: true, grid: { color: '#eee' } }
  },
  layout: {
    padding: {
      top: 0,
      bottom: 0,
      left: 0,
      right: 0
    }
  }
}

const fetchTags = async () => {
  tagsLoading.value = true
  try {
    const params: any = {
      page: tagsPage.value,
      page_size: tagsPerPage.value,
    }
    if (tagSearch.value) params.search = tagSearch.value
    if (tagsSortBy.value && tagsSortBy.value.length > 0) {
      params.ordering = tagsSortBy.value.map(s => s.order === 'desc' ? `-${s.key}` : s.key).join(',')
    }
    console.log('Request params:', params)
    const resp = await api.get(`repositories/${route.params.uuid}/tags-list/`, { params })
    console.log('API Response:', resp.data.results.map(tag => tag.tag))
    tags.value = resp.data.results
    tagsTotal.value = resp.data.count
  } catch (e) {
    tags.value = []
    tagsTotal.value = 0
  } finally {
    tagsLoading.value = false
  }
}

watch([tagSearch], () => {
  tagsPage.value = 1
  fetchTags()
})
watch([tagsPage, tagsPerPage], fetchTags)

const fetchRepository = async () => {
  repositoryLoading.value = true
  try {
    const resp = await api.get(`repositories/${route.params.uuid}/`)
    repository.value = resp.data
  } finally {
    repositoryLoading.value = false
    loading.value = false
  }
}

const goBack = () => router.back()
const navigateToTagImages = (item: any) => {
  router.push({ name: 'tag-images', params: { uuid: item.uuid } })
}

const isActionDisabled = (item: any, action: 'process' | 'rescan') => {
  if (['in_process', 'pending'].includes(item.processing_status)) {
    return true
  }
  return false
}

const getActionTooltip = (item: any, action: 'process' | 'rescan') => {
  const baseMessage = action === 'process' ? 'Process tag' : 'Rescan all images for this tag'
  if (['in_process', 'pending'].includes(item.processing_status)) {
    return `${baseMessage} (Tag is already queued for processing)`
  }
  return baseMessage
}

const onProcessTag = async (tag: any) => {
  if (!tag.uuid) {
    notificationService.error('Cannot process tag: missing UUID')
    return
  }
  if (isActionDisabled(tag, 'process')) {
    notificationService.warning(getActionTooltip(tag, 'process'))
    return
  }
  try {
    await api.post(`repository-tags/${tag.uuid}/process/`)
    notificationService.success('Tag processing started successfully')
    await fetchRepository()
  } catch (error: any) {
    console.error('Error processing tag:', error)
    notificationService.error('Failed to process tag')
  }
}

const onRescanTagImages = async (tag: any) => {
  if (!tag.uuid) return
  if (isActionDisabled(tag, 'rescan')) {
    notificationService.warning(getActionTooltip(tag, 'rescan'))
    return
  }
  try {
    const resp = await api.post(`repository-tags/${tag.uuid}/rescan-images/`)
    notificationService.success(resp.data.message || 'Rescan started')
    fetchTags()
  } catch (e: any) {
    if (e.response?.status === 409) {
      notificationService.warning(e.response.data.error || 'At least one image is already being scanned or queued for scanning')
    } else if (e.response?.status === 429) {
      notificationService.warning(e.response.data.error || 'Please wait before trying again')
    } else {
      notificationService.error('Failed to start rescan for tag images')
    }
  }
}

const onReanalyzeSbom = async (tag: any) => {
  if (!tag.uuid) return
  if (isActionDisabled(tag, 'rescan')) {
    notificationService.warning(getActionTooltip(tag, 'rescan'))
    return
  }
  
  // Set loading state briefly, then clear it immediately to allow parallel requests
  reanalyzingSbom.value = tag.uuid
  
  // Make request without blocking - don't await, handle response asynchronously
  api.post(`repository-tags/${tag.uuid}/reanalyze-sbom/`)
    .then((resp) => {
      // Show success message with details about skipped images if any
      const message = resp.data.message || `Reanalysis started for ${resp.data.count} images`
      if (resp.data.skipped_count && resp.data.skipped_count > 0) {
        notificationService.info(message)
      } else {
        notificationService.success(message)
      }
      // Refresh tags list after a short delay to allow backend to process
      setTimeout(() => {
        fetchTags()
      }, 500)
    })
    .catch((e: any) => {
      if (e.response?.status === 409) {
        // If all images are already being scanned, show warning
        // Otherwise this shouldn't happen with new logic, but keep for backward compatibility
        const errorMsg = e.response.data.error || 'All images are already being scanned or queued for scanning'
        if (e.response.data.skipped_count) {
          notificationService.info(`${errorMsg} (${e.response.data.skipped_count} images skipped)`)
        } else {
          notificationService.warning(errorMsg)
        }
      } else if (e.response?.status === 404) {
        notificationService.warning(e.response.data.error || 'No images with SBOM data found for this tag')
      } else {
        notificationService.error('Failed to start SBOM reanalysis')
      }
    })
    .finally(() => {
      // Clear loading state immediately after request is sent
      reanalyzingSbom.value = null
    })
}

const getProcessingStatusTooltip = (status: string) => {
  const statusMap: { [key: string]: string } = {
    'pending': 'Processing pending',
    'in_process': 'Processing in progress',
    'success': 'Processing completed',
    'error': 'Processing failed',
    'none': 'Start processing'
  }
  return statusMap[status] || 'Start processing'
}

const getTagStatusColor = (status: string) => {
  const map: { [key: string]: string } = {
    'pending': 'grey',
    'in_process': 'blue',
    'success': 'green',
    'error': 'red',
    'none': 'default',
  }
  return map[status] || 'default'
}

const onTagsPerPageChange = () => {
  tagsPage.value = 1
  fetchTags()
}

const onTagRowClick = (event: any, { item }: any) => {
  router.push({ name: 'tag-images', params: { uuid: item.uuid } })
}

const onSortChange = (newSortBy: any) => {
  tagsSortBy.value = newSortBy
  tagsPage.value = 1
  fetchTags()
}

const isScanDisabled = () => {
  return repository.value?.scan_status === 'in_process'
}

const getScanTooltip = () => {
  if (repository.value?.scan_status === 'in_process') {
    return 'Repository is already being scanned'
  }
  return 'Scan repository for new tags'
}

const onScanRepository = async () => {
  if (!repository.value?.uuid) {
    notificationService.error('Cannot scan repository: missing UUID')
    return
  }
  if (isScanDisabled()) {
    notificationService.warning(getScanTooltip())
    return
  }
  scanning.value = true
  try {
    await api.post(`repositories/${repository.value.uuid}/scan_tags/`)
    notificationService.success('Repository scan started successfully')
    await fetchRepository()
    await fetchTags()
  } catch (error: any) {
    if (error.response?.status === 409) {
      notificationService.warning(error.response.data.error || 'Repository is already being scanned')
    } else {
      console.error('Error starting repository scan:', error)
      notificationService.error('Failed to start repository scan')
    }
  } finally {
    scanning.value = false
  }
}

onMounted(async () => {
  // Load repository data first (lightweight)
  await fetchRepository()
  
  // Load tags and charts in parallel (heavier operations)
  await Promise.all([
    fetchTags(),
    fetchTagsForCharts()
  ])
})
</script>

<style scoped>
.clickable-row {
  cursor: pointer;
  transition: background-color 0.2s;
}
.clickable-row:hover {
  background-color: rgba(0, 0, 0, 0.04);
}

.release-chip {
  font-size: 0.6rem;
  height: 18px;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.v-theme--matrix .release-chip {
  color: #39FF14 !important;
  background: rgba(57, 255, 20, 0.1) !important;
  border: 1px solid #39FF14 !important;
}

/* Chart filter button styles */
.chart-filter-btn {
  transition: all 0.2s ease;
}

.chart-filter-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}

/* Chart header alignment */
.chart-header {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.chart-title {
  margin-bottom: 0;
  line-height: 1.2;
}

.chart-spacer {
  width: 120px;
  flex-shrink: 0;
}

/* Chart container alignment */
.chart-container {
  display: flex;
  flex-direction: column;
  height: 100%;
}



.chart-wrapper {
  flex: 1;
  min-height: 300px;
  display: flex;
  align-items: flex-start;
}
</style> 