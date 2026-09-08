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
import ChartDataLabels, { type Context as DataLabelContext } from 'chartjs-plugin-datalabels'

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
      clamp: true,
      font: { weight: 'bold', size: 12 },
      formatter: (value: number, context: DataLabelContext) => {
        const values = context.chart.data.datasets[context.datasetIndex]?.data || []
        const total = values.reduce<number>(
          (sum, item) => sum + (typeof item === 'number' ? item : 0),
          0,
        )

        // Tiny slices remain discoverable via the legend and tooltip, while
        // suppressing their labels prevents unreadable text collisions.
        return value > 0 && (total === 0 || value / total >= 0.05)
          ? value.toLocaleString()
          : ''
      }
    }
  }
}) as Partial<ChartOptions<'pie'>>)
</script>
