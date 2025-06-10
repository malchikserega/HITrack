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
        <v-data-table
          :headers="tagHeaders"
          :items="repository?.tags || []"
          :loading="loading"
          class="elevation-1"
          @click:row="onTagRowClick"
        >
          <template #item.findings="{ item }">
            {{ getTagFindings(item) }}
          </template>
          <template #item.components="{ item }">
            {{ getTagUniqueComponents(item) }}
          </template>
        </v-data-table>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../plugins/axios'
import { Bar, Line } from 'vue-chartjs'
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
const onTagRowClick = (tag: any) => {
  
}

onMounted(fetchRepository)
</script>

<style scoped>
</style> 