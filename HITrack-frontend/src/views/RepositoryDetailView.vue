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
        <v-table
          :headers="tagHeaders"
          :items="tagsWithActions"
          :loading="loading"
          class="elevation-1"
        >
          <thead>
            <tr>
              <th v-for="header in tagHeaders" :key="header.key">
                {{ header.title }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr 
              v-for="item in tagsWithActions" 
              :key="item.uuid"
              class="clickable-row" 
              @click="navigateToTagImages(item)"
            >
              <td>
                <span>{{ item.tag }}</span>
                <v-chip
                  size="x-small"
                  :color="getTagStatusColor(item.processing_status || 'none')"
                  class="ml-2"
                  variant="tonal"
                  style="font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;"
                >
                  {{ getProcessingStatusTooltip(item.processing_status || 'none') }}
                </v-chip>
              </td>
              <td>{{ getTagFindings(item) }}</td>
              <td>{{ getTagUniqueComponents(item) }}</td>
              <td>{{ item.created_at }}</td>
              <td>
                <v-icon
                  size="small"
                  color="primary"
                  :class="{ 'opacity-50': item.processing_status === 'in_process' }"
                  @click.stop="onProcessTag(item)"
                >
                  mdi-cog
                </v-icon>
              </td>
            </tr>
          </tbody>
        </v-table>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
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
  { title: 'Vulnerabilities', key: 'findings' },
  { title: 'Components', key: 'components' },
  { title: 'Created', key: 'created_at' },
  { title: 'Actions', key: 'actions', sortable: false }
]

const getTagFindings = (tag: any) => {
  if (!tag.images) return 0;
  return tag.images.reduce((sum: number, img: any) => sum + (img.findings || 0), 0);
}
const getTagUniqueComponents = (tag: any) => {
  if (!tag.images) return 0;
  return tag.images.reduce((sum: number, img: any) => sum + (img.components_count || 0), 0);
}

const tagLabels = computed(() => (repository.value?.tags || []).map((tag: any) => tag.tag))
const findingsData = computed(() => (repository.value?.tags || []).map(getTagFindings))
const uniqueComponentsData = computed(() => (repository.value?.tags || []).map(getTagUniqueComponents))

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

const tagsWithActions = computed(() =>
  (repository.value?.tags || []).map((tag: any) => ({
    ...tag,
    actions: true
  }))
)

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
  try {
    await api.post(`repository-tags/${tag.uuid}/process/`)
    notificationService.success('Tag processing started successfully')
    await fetchRepository()
  } catch (error: any) {
    console.error('Error processing tag:', error)
    notificationService.error('Failed to process tag')
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

onMounted(fetchRepository)
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