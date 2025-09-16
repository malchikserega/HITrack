<template>
  <div>
    <Pie :data="chartData" :options="mergedOptions" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Pie } from 'vue-chartjs'
import {
  Chart as ChartJS,
  Title,
  Tooltip,
  Legend,
  ArcElement,
  type ChartOptions,
  type ChartData
} from 'chart.js'
import ChartDataLabels from 'chartjs-plugin-datalabels'

ChartJS.register(Title, Tooltip, Legend, ArcElement, ChartDataLabels)

const props = defineProps<{
  chartData: ChartData<'pie'>
  chartOptions?: Partial<ChartOptions<'pie'>>
}>()

const mergedOptions = computed(() => ({
  responsive: true,
  plugins: {
    ...(props.chartOptions?.plugins || {}),
    legend: { display: false },
    datalabels: {
      color: '#222',
      font: { weight: 'bold', size: 16 },
      formatter: (value: number) => value > 0 ? value : ''
    }
  }
}) as Partial<ChartOptions<'pie'>>)
</script> 