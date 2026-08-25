<template>
  <v-container fluid class="page-shell page-shell--wide">
    <div class="d-flex flex-wrap align-start justify-space-between ga-4 mb-5">
      <div>
        <h1 class="text-h4 font-weight-black">Prioritization</h1>
        <p class="text-body-1 text-medium-emphasis mt-2">
          Actionable upgrade opportunities, package blast radius, and scan coverage.
        </p>
      </div>
      <v-chip v-if="data" color="secondary" variant="tonal">
        {{ data.active_suppressions_count }} active risk acceptance{{ data.active_suppressions_count === 1 ? '' : 's' }}
      </v-chip>
    </div>

    <v-card class="mb-5" variant="outlined">
      <v-card-text>
        <div class="filter-grid">
          <v-text-field v-model="search" label="Package or PURL" prepend-inner-icon="mdi-magnify"
            clearable hide-details density="comfortable" variant="outlined" />
          <v-select v-model="ecosystem" :items="ecosystems" label="Package type"
            hide-details density="comfortable" variant="outlined" />
          <v-select v-model="staleDays" :items="staleDayOptions" label="Stale after"
            hide-details density="comfortable" variant="outlined" />
          <v-switch v-model="includeSuppressed" label="Include accepted risk"
            color="primary" hide-details />
          <v-btn color="primary" prepend-icon="mdi-refresh" :loading="loading" @click="fetchData">Refresh</v-btn>
        </div>
      </v-card-text>
    </v-card>

    <v-alert v-if="error" type="error" variant="tonal" class="mb-5">{{ error }}</v-alert>
    <v-skeleton-loader v-if="loading && !data" type="table-heading, table-thead, table-row@6" />

    <template v-else-if="data">
      <v-row class="mb-2">
        <v-col cols="12" sm="6" lg="3">
          <v-card variant="tonal" color="primary"><v-card-text>
            <div class="text-caption">Fully analyzed</div>
            <div class="text-h4 font-weight-bold">{{ data.scan_freshness.fully_analyzed_percentage }}%</div>
            <div class="text-caption">{{ data.scan_freshness.fully_analyzed_count }} / {{ data.scan_freshness.total_images }} images</div>
          </v-card-text></v-card>
        </v-col>
        <v-col cols="12" sm="6" lg="3">
          <v-card variant="tonal" color="error"><v-card-text>
            <div class="text-caption">Need scan attention</div>
            <div class="text-h4 font-weight-bold">{{ attentionCount }}</div>
            <div class="text-caption">stale or never scanned</div>
          </v-card-text></v-card>
        </v-col>
        <v-col cols="12" sm="6" lg="3">
          <v-card variant="tonal" color="success"><v-card-text>
            <div class="text-caption">Upgrade opportunities</div>
            <div class="text-h4 font-weight-bold">{{ data.remediation_opportunities.length }}</div>
            <div class="text-caption">package versions with known fixes</div>
          </v-card-text></v-card>
        </v-col>
        <v-col cols="12" sm="6" lg="3">
          <v-card variant="tonal" color="warning"><v-card-text>
            <div class="text-caption">High-impact packages</div>
            <div class="text-h4 font-weight-bold">{{ data.high_impact_packages.length }}</div>
            <div class="text-caption">ranked by risk and blast radius</div>
          </v-card-text></v-card>
        </v-col>
      </v-row>

      <v-tabs v-model="tab" color="primary" class="mb-3">
        <v-tab value="remediation">Remediation opportunities</v-tab>
        <v-tab value="impact">High-impact packages</v-tab>
        <v-tab value="freshness">Scan freshness</v-tab>
      </v-tabs>

      <v-window v-model="tab">
        <v-window-item value="remediation">
          <v-card variant="outlined">
            <v-card-title>Upgrades with the greatest risk reduction</v-card-title>
            <v-card-subtitle>Recommended versions are scanner-reported candidates; validate compatibility before deployment.</v-card-subtitle>
            <v-data-table :headers="remediationHeaders" :items="data.remediation_opportunities"
              :items-per-page="25" hover @click:row="openComponent">
              <template #item.component_name="{ item }">
                <div class="font-weight-bold">{{ item.component_name }}</div>
                <div class="text-caption text-medium-emphasis">{{ item.component_type }} · {{ item.current_version }}</div>
              </template>
              <template #item.recommended_version="{ item }">
                <v-chip :color="item.recommended_version ? 'success' : 'grey'" size="small" variant="tonal">
                  {{ item.recommended_version || 'Review upstream' }}
                </v-chip>
              </template>
              <template #item.risk="{ item }"><risk-cell :item="item" /></template>
              <template #item.exposure="{ item }">
                {{ item.affected_images_count }} images · {{ item.affected_repositories_count }} repos
              </template>
            </v-data-table>
          </v-card>
        </v-window-item>

        <v-window-item value="impact">
          <v-card variant="outlined">
            <v-card-title>Packages with broad, high-risk exposure</v-card-title>
            <v-data-table :headers="impactHeaders" :items="data.high_impact_packages"
              :items-per-page="25" hover @click:row="openComponent">
              <template #item.component_name="{ item }">
                <div class="font-weight-bold">{{ item.component_name }}</div>
                <div class="text-caption text-medium-emphasis">{{ item.component_type }} · {{ item.current_version }}</div>
              </template>
              <template #item.risk="{ item }"><risk-cell :item="item" /></template>
              <template #item.fixability="{ item }">
                <v-chip size="small" color="success" variant="tonal">{{ item.fixable_count }} fixable</v-chip>
                <v-chip v-if="item.no_fix_count" size="small" color="error" variant="tonal" class="ml-1">{{ item.no_fix_count }} no fix</v-chip>
              </template>
              <template #item.exposure="{ item }">
                {{ item.affected_images_count }} images · {{ item.affected_tags_count }} tags
              </template>
            </v-data-table>
          </v-card>
        </v-window-item>

        <v-window-item value="freshness">
          <v-row>
            <v-col cols="12" md="4">
              <v-card variant="outlined" class="h-100"><v-card-title>Coverage</v-card-title><v-card-text>
                <coverage-row label="SBOM" :value="data.scan_freshness.sbom_coverage_count" :total="data.scan_freshness.total_images" />
                <coverage-row label="Vulnerability analysis" :value="data.scan_freshness.grype_coverage_count" :total="data.scan_freshness.total_images" />
                <coverage-row label="Complete" :value="data.scan_freshness.fully_analyzed_count" :total="data.scan_freshness.total_images" />
              </v-card-text></v-card>
            </v-col>
            <v-col cols="12" md="8">
              <v-card variant="outlined"><v-card-title>Images requiring attention</v-card-title>
                <v-data-table :headers="freshnessHeaders" :items="data.scan_freshness.attention_images" :items-per-page="20" hover @click:row="openImage">
                  <template #item.freshness="{ item }"><v-chip size="small" :color="item.freshness === 'never_scanned' ? 'error' : 'warning'" variant="tonal">{{ item.freshness === 'never_scanned' ? 'Never scanned' : 'Stale' }}</v-chip></template>
                  <template #item.last_successful_scan="{ item }">{{ item.last_successful_scan ? formatDate(item.last_successful_scan) : 'Never' }}</template>
                </v-data-table>
              </v-card>
            </v-col>
          </v-row>
        </v-window-item>
      </v-window>
    </template>
  </v-container>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '../plugins/axios'

interface PackageRiskRow {
  component_version_uuid: string; component_name: string; component_type: string
  current_version: string; latest_version?: string | null; recommended_version?: string | null
  vulnerabilities_count: number; critical_count: number; high_count: number; medium_count: number
  fixable_count: number; no_fix_count: number; kev_count: number; exploit_count: number
  affected_images_count: number; affected_tags_count: number; affected_repositories_count: number
  risk_score: number
}
interface AttentionImage { uuid: string; name: string; scan_status: string; freshness: string; last_successful_scan?: string | null }
interface PrioritizationData {
  active_suppressions_count: number
  remediation_opportunities: PackageRiskRow[]
  high_impact_packages: PackageRiskRow[]
  scan_freshness: {
    total_images: number; sbom_coverage_count: number; grype_coverage_count: number
    fully_analyzed_count: number; fully_analyzed_percentage: number
    freshness_buckets: Record<string, number>; attention_images: AttentionImage[]
  }
}

const router = useRouter()
const data = ref<PrioritizationData | null>(null)
const loading = ref(false)
const error = ref('')
const tab = ref('remediation')
const search = ref('')
const ecosystem = ref('all')
const staleDays = ref(30)
const includeSuppressed = ref(false)
const ecosystems = [
  { title: 'All package types', value: 'all' }, { title: '.NET / NuGet', value: 'dotnet' },
  { title: 'npm', value: 'npm' }, { title: 'Python', value: 'python' },
  { title: 'Java', value: 'java' }, { title: 'Go', value: 'go' },
  { title: 'Ruby', value: 'ruby' }, { title: 'Rust', value: 'rust' },
  { title: 'PHP / Composer', value: 'php' }, { title: 'OS packages', value: 'os' },
]
const staleDayOptions = [
  { title: '7 days', value: 7 }, { title: '14 days', value: 14 },
  { title: '30 days', value: 30 }, { title: '60 days', value: 60 }, { title: '90 days', value: 90 },
]
const remediationHeaders = [
  { title: 'Package', key: 'component_name' }, { title: 'Upgrade target', key: 'recommended_version' },
  { title: 'Risk signals', key: 'risk', sortable: false }, { title: 'Exposure', key: 'exposure', sortable: false },
  { title: 'Risk score', key: 'risk_score' },
]
const impactHeaders = [
  { title: 'Package', key: 'component_name' }, { title: 'Risk signals', key: 'risk', sortable: false },
  { title: 'Fixability', key: 'fixability', sortable: false }, { title: 'Exposure', key: 'exposure', sortable: false },
  { title: 'Risk score', key: 'risk_score' },
]
const freshnessHeaders = [
  { title: 'Image', key: 'name' }, { title: 'State', key: 'freshness' },
  { title: 'Last successful analysis', key: 'last_successful_scan' }, { title: 'Scan status', key: 'scan_status' },
]
const attentionCount = computed(() => (data.value?.scan_freshness.freshness_buckets.stale || 0) + (data.value?.scan_freshness.freshness_buckets.never_scanned || 0))

const RiskCell = defineComponent({ props: { item: { type: Object, required: true } }, setup(props) { return () => h('div', { class: 'd-flex ga-1 flex-wrap' }, [
  props.item.critical_count ? h('span', { class: 'risk-pill risk-pill--critical' }, `${props.item.critical_count} critical`) : null,
  props.item.high_count ? h('span', { class: 'risk-pill risk-pill--high' }, `${props.item.high_count} high`) : null,
  props.item.kev_count ? h('span', { class: 'risk-pill risk-pill--kev' }, `${props.item.kev_count} KEV`) : null,
  props.item.exploit_count ? h('span', { class: 'risk-pill' }, `${props.item.exploit_count} exploit`) : null,
]) } })
const CoverageRow = defineComponent({ props: { label: String, value: Number, total: Number }, setup(props) { return () => h('div', { class: 'mb-5' }, [
  h('div', { class: 'd-flex justify-space-between mb-1' }, [h('span', props.label), h('strong', `${props.value || 0} / ${props.total || 0}`)]),
  h('div', { class: 'coverage-track' }, [h('div', { class: 'coverage-fill', style: { width: `${props.total ? (Number(props.value) / Number(props.total)) * 100 : 0}%` } })]),
]) } })

const fetchData = async () => {
  loading.value = true; error.value = ''
  try {
    const response = await api.get<PrioritizationData>('stats/prioritization/', { params: {
      search: search.value || undefined, ecosystem: ecosystem.value, stale_days: staleDays.value,
      include_suppressed: includeSuppressed.value, limit: 100,
    } })
    data.value = response.data
  } catch { error.value = 'Failed to load prioritization analytics.' } finally { loading.value = false }
}
let timer: ReturnType<typeof setTimeout> | undefined
watch([search, ecosystem, staleDays, includeSuppressed], () => { if (timer) clearTimeout(timer); timer = setTimeout(fetchData, 300) })
const openComponent = (_event: Event, row: { item: PackageRiskRow }) => router.push(`/component-versions/${row.item.component_version_uuid}`)
const openImage = (_event: Event, row: { item: AttentionImage }) => router.push(`/images/${row.item.uuid}`)
const formatDate = (value: string) => new Date(value).toLocaleString()
onMounted(fetchData)
</script>

<style scoped>
.filter-grid { display: grid; grid-template-columns: minmax(240px, 1fr) 210px 170px 210px auto; gap: 12px; align-items: center; }
.risk-pill { padding: 3px 7px; border-radius: 999px; font-size: .72rem; background: rgba(245, 124, 0, .14); color: #a54b00; }
.risk-pill--critical, .risk-pill--kev { background: rgba(211, 47, 47, .14); color: #b71c1c; }
.risk-pill--high { background: rgba(245, 124, 0, .16); color: #9a4500; }
.coverage-track { height: 9px; border-radius: 999px; overflow: hidden; background: rgba(0,0,0,.09); }
.coverage-fill { height: 100%; background: rgb(var(--v-theme-primary)); border-radius: inherit; }
@media (max-width: 1100px) { .filter-grid { grid-template-columns: 1fr 1fr; } }
@media (max-width: 600px) { .filter-grid { grid-template-columns: 1fr; } }
</style>
