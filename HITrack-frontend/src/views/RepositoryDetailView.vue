<template>
  <v-container>
    <v-row>
      <v-col cols="12">
        <v-btn variant="text" @click="goBack" class="mb-2">
          <v-icon left>mdi-arrow-left</v-icon>Back
        </v-btn>
        <h1 class="text-h4 font-weight-black mb-2">Repository: {{ repository?.name }}</h1>
        <v-chip class="mr-2">Type: {{ repository?.repository_type }}</v-chip>
        <v-chip class="mr-2">Tags: {{ repository?.tag_count }}</v-chip>
        <v-chip class="mr-2">URL: {{ repository?.url }}</v-chip>
      </v-col>
    </v-row>
    <v-row>
      <v-col cols="12" md="6">
        <Bar :data="barChartData" :options="barChartOptions" />
      </v-col>
      <v-col cols="12" md="6">
        <Bar :data="comboChartData as any" :options="comboChartOptions" />
      </v-col>
    </v-row>
    <v-row>
      <v-col cols="12">
        <h2 class="text-h6 font-weight-bold mb-2">Tags</h2>
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
          <v-select
            :items="[10, 20, 50, 100]"
            v-model="tagsPerPage"
            label="Items per page"
            style="max-width: 150px"
            hide-details
            density="compact"
            variant="outlined"
            @update:model-value="onTagsPerPageChange"
          />
        </div>
        <v-data-table
          :headers="tagHeaders"
          :items="tags"
          :loading="tagsLoading"
          :items-per-page="tagsPerPage"
          :page="tagsPage"
          :sort-by.sync="tagsSortBy"
          hide-default-footer
          item-class="clickable-row"
          @click:row="onTagRowClick"
        >
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
            <v-tooltip text="Process tag">
              <template v-slot:activator="{ props }">
                <v-btn
                  v-bind="props"
                  icon="mdi-code-tags"
                  variant="tonal"
                  size="x-small"
                  color="primary"
                  :class="{ 'opacity-50': ['in_process', 'pending'].includes(item.processing_status) }"
                  :disabled="['in_process', 'pending'].includes(item.processing_status)"
                  @click.stop="onProcessTag(item)"
                />
              </template>
            </v-tooltip>
            <v-tooltip text="Rescan all images for this tag">
              <template v-slot:activator="{ props }">
                <v-btn
                  v-bind="props"
                  icon="mdi-cog-refresh"
                  variant="tonal"
                  size="x-small"
                  color="info"
                  class="ml-2"
                  :class="{ 'opacity-50': ['in_process', 'pending'].includes(item.processing_status) }"
                  :disabled="['in_process', 'pending'].includes(item.processing_status)"
                  @click.stop="onRescanTagImages(item)"
                />
              </template>
            </v-tooltip>
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
  LineController
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
  LineController
)

const route = useRoute()
const router = useRouter()
const repository = ref<any>(null)
const loading = ref(true)

const tagHeaders = [
  { title: 'Tag', key: 'tag' },
  { title: 'Status', key: 'processing_status', sortable: false },
  { title: 'Vulnerabilities', key: 'findings' },
  { title: 'Components', key: 'components' },
  { title: 'Created', key: 'created_at' },
  { title: 'Actions', key: 'actions', sortable: false }
]

const tags = ref<any[]>([])
const tagsLoading = ref(false)
const tagSearch = ref('')
const tagsPage = ref(1)
const tagsPerPage = ref(10)
const tagsTotal = ref(0)
interface SortItem { key: string; order: 'asc' | 'desc' }
const tagsSortBy = ref<SortItem[]>([{ key: 'created_at', order: 'desc' }])
const tagsPageCount = computed(() => Math.ceil(tagsTotal.value / tagsPerPage.value) || 1)

const tagsForCharts = ref<any[]>([])

const fetchTagsForCharts = async () => {
  try {
    const resp = await api.get(`repositories/${route.params.uuid}/tags-graph/`)
    tagsForCharts.value = resp.data
  } catch (e) {
    tagsForCharts.value = []
  }
}

const tagLabels = computed(() => tagsForCharts.value.map((tag: any) => tag.tag))
const findingsData = computed(() => tagsForCharts.value.map((tag: any) => tag.findings))
const uniqueComponentsData = computed(() => tagsForCharts.value.map((tag: any) => tag.components))

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
  plugins: {
    legend: { display: true },
    title: { display: false },
    tooltip: { enabled: true },
  },
  scales: {
    x: { stacked: false, grid: { display: false } },
    y: { stacked: false, beginAtZero: true, grid: { color: '#eee' } }
  }
}

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
  ]
}))
const comboChartOptions = {
  responsive: true,
  plugins: {
    legend: { display: true },
    title: { display: false },
    tooltip: { enabled: true },
  },
  scales: {
    x: { grid: { display: false } },
    y: { beginAtZero: true, grid: { color: '#eee' } }
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
    const resp = await api.get(`repositories/${route.params.uuid}/tags-list/`, { params })
    tags.value = resp.data.results
    tagsTotal.value = resp.data.count
  } catch (e) {
    tags.value = []
    tagsTotal.value = 0
  } finally {
    tagsLoading.value = false
  }
}

watch([tagSearch, tagsSortBy], () => {
  tagsPage.value = 1
  fetchTags()
})
watch([tagsPage, tagsPerPage], fetchTags)

const fetchRepository = async () => {
  loading.value = true
  try {
    const resp = await api.get(`repositories/${route.params.uuid}/`)
    repository.value = resp.data
  } finally {
    loading.value = false
  }
}

const goBack = () => router.back()
const navigateToTagImages = (item: any) => {
  router.push({ name: 'tag-images', params: { uuid: item.uuid } })
}

const onProcessTag = async (tag: any) => {
  if (!tag.uuid) {
    notificationService.error('Cannot process tag: missing UUID')
    return
  }
  if (['in_process', 'pending'].includes(tag.processing_status)) {
    notificationService.warning('Tag is already queued for processing')
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
  try {
    const resp = await api.post(`repository-tags/${tag.uuid}/rescan-images/`)
    notificationService.success(resp.data.message || 'Rescan started')
    fetchTags()
  } catch (e) {
    notificationService.error('Failed to start rescan for tag images')
  }
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

onMounted(() => {
  fetchRepository()
  fetchTags()
  fetchTagsForCharts()
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
</style> 