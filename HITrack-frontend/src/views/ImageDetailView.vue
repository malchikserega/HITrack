<template>
  <div class="image-detail">
    <v-container>
      <v-row>
        <v-col cols="12">
          <v-btn variant="text" @click="router.back()" class="mb-2">
            ← Back
          </v-btn>
          
          <!-- Breadcrumb Navigation -->
          <div v-if="image?.repository_info" class="mb-4">
            <v-breadcrumbs :items="breadcrumbItems" class="pa-0">
              <template v-slot:divider>
                <v-icon size="small">mdi-chevron-right</v-icon>
              </template>
              <template v-slot:title="{ item }">
                <v-btn
                  v-if="item.to && !item.disabled"
                  variant="text"
                  :to="item.to"
                  class="text-decoration-none"
                  density="compact"
                  size="small"
                >
                  {{ item.title }}
                </v-btn>
                <span v-else class="text-body-2 text-grey">{{ item.title }}</span>
              </template>
            </v-breadcrumbs>
          </div>
          
          <h1 class="text-h4 mb-4 font-weight-black">Image Details</h1>
        </v-col>
      </v-row>
      <v-row>
        <v-col cols="12">
          <v-alert v-if="error" type="error" class="mb-4">{{ error }}</v-alert>
          <v-progress-circular v-if="loading" indeterminate color="primary" class="my-8" size="48" />
          <div v-if="image && !loading">
            <!-- Top Card with main info -->
            <v-card class="mb-6 pa-4 main-info-card">
              <div class="d-flex align-center justify-space-between mb-2 flex-wrap">
                <span class="text-h5 font-weight-bold">{{ image.name }}</span>
                <v-chip :color="statusColor(image.scan_status)" class="status-chip" variant="tonal">
                  {{ statusLabel(image.scan_status) }}
                </v-chip>
              </div>
              <div class="mb-1"><b>Digest:</b> <span class="digest-text">{{ image.digest }}</span></div>
              <div class="mb-1"><b>Updated:</b> {{ $formatDate(image.updated_at) }}</div>
            </v-card>

            <!-- Two circles below card -->
            <v-row class="mb-6" justify="center">
              <v-col cols="12" md="4" class="d-flex flex-column align-center justify-center">
                <div class="circle-info mx-4">
                  <v-progress-circular :size="220" :width="16" color="error" :value="100" class="mb-2">
                    <span class="circle-number">{{ animatedFindings }}</span>
                  </v-progress-circular>
                </div>
                <div class="circle-label mt-2">Vulnerabilities</div>
              </v-col>
              <v-col cols="12" md="4" class="d-flex flex-column align-center justify-center">
                <div class="circle-info mx-4 d-flex flex-column align-center" style="min-width: 220px;">
                  <div style="width: 220px; height: 220px;">
                    <PieChart :chartData="pieChartData" :chartOptions="pieChartOptions" style="width: 220px; height: 220px;" />
                  </div>
                </div>
                <div class="circle-label mt-2">Severity</div>
              </v-col>
              <v-col cols="12" md="4" class="d-flex flex-column align-center justify-center">
                <div class="circle-info mx-4">
                  <v-progress-circular :size="220" :width="16" color="primary" :value="100" class="mb-2">
                    <span class="circle-number">{{ animatedComponents }}</span>
                  </v-progress-circular>
                </div>
                <div class="circle-label mt-2">Components</div>
              </v-col>
            </v-row>
            <v-row class="align-center mb-2">
              <v-col cols="12" class="d-flex justify-center">
                <div class="d-flex flex-row align-center justify-center gap-4">
                  <v-switch
                    v-model="showUniqueFindings"
                    color="primary"
                    hide-details
                    class="switch-unique-findings"
                    :label="'Unique vulnerabilities'"
                    density="compact"
                    style="min-width: 220px;"
                  />
                  <v-switch
                    v-model="showFixableOnly"
                    color="success"
                    hide-details
                    class="switch-fixable-findings"
                    :label="'🔧 Only fully fixable components'"
                    density="compact"
                    style="min-width: 260px;"
                  />
                </div>
              </v-col>
            </v-row>
            <v-row class="align-center mb-2">
              <v-col cols="12" class="d-flex justify-center">
                <div class="pie-legend">
                  <div v-for="(label, i) in pieChartData.labels" :key="label" class="legend-row"
                    @click="onLegendClick(i)">
                    <span class="legend-color" :style="{ background: pieChartData.datasets[0].backgroundColor[i] }"></span>
                    <span class="legend-label" :class="{ 'legend-label--strikethrough': !legendVisible[i] }">{{ label }}</span>
                  </div>
                </div>
              </v-col>
            </v-row>

            <!-- SBOM section -->
            <v-card class="mb-4">
              <v-card-title class="font-weight-bold">SBOM</v-card-title>
              <v-card-text>
                <v-btn size="x-small" variant="text" @click="toggleSbom">{{ showSbom ? 'Hide SBOM' : 'Show SBOM' }}</v-btn>
                <v-expand-transition>
                  <div v-if="showSbom">
                    <v-progress-linear v-if="sbomLoading" indeterminate color="primary" class="my-4" height="6" rounded />
                    <pre v-else-if="sbomData && !sbomData.error" class="sbom-json">{{ JSON.stringify(sbomData, null, 2) }}</pre>
                    <div v-else-if="sbomData && sbomData.error" class="text-error">{{ sbomData.error }}</div>
                  </div>
                </v-expand-transition>
              </v-card-text>
            </v-card>

            <!-- Tabs for Components and Vulnerabilities -->
            <v-card class="mb-4">
              <v-tabs v-model="activeTab" color="primary" grow>
                <v-tab value="components">
                  <v-icon start>mdi-package-variant</v-icon>
                  Components
                </v-tab>
                <v-tab value="vulnerabilities">
                  <v-icon start>mdi-shield-alert</v-icon>
                  Vulnerabilities
                </v-tab>
              </v-tabs>

              <v-window v-model="activeTab">
                <!-- Components Tab -->
                <v-window-item value="components">
                  <v-card-text>
                    <v-text-field
                      v-model="componentsSearch"
                      label="Search components"
                      prepend-inner-icon="mdi-magnify"
                      :append-inner-icon="componentsLoading ? 'mdi-loading mdi-spin' : undefined"
                      variant="outlined"
                      clearable
                      class="mb-4"
                      @click:clear="componentsSearch = ''"
                    ></v-text-field>
                    <div v-if="componentsSearch" class="text-caption text-grey mb-4 text-right">
                      Found {{ componentsTotal }} result{{ componentsTotal !== 1 ? 's' : '' }}
                    </div>
                    <v-data-table
                      :headers="componentHeaders"
                      :items="components"
                      :loading="componentsLoading"
                      :items-per-page="componentsPerPage"
                      :page="componentsPage"
                      :sort-by="componentsSortBy"
                      :sort-desc="componentsSortDesc"
                      hide-default-footer
                      class="elevation-1"
                      hover
                      density="comfortable"
                      :no-data-text="componentsSearch ? 'No components found matching your search' : 'No components found'"
                    >
                      <template v-slot:item.name="{ item }">
                        {{ item.component.name }}
                      </template>
                      <template v-slot:item.version="{ item }">
                        {{ item.version }}
                      </template>
                      <template v-slot:item.type="{ item }">
                        <v-chip size="small" :color="getComponentTypeColor(item.component.type)" variant="tonal">
                          {{ item.component.type }}
                        </v-chip>
                      </template>
                      <template v-slot:item.vulnerabilities_count="{ item }: { item: ComponentVersion }">
                        <v-chip
                          size="small"
                          :color="item.vulnerabilities_count > 0 ? 'error' : 'success'"
                          variant="tonal"
                          class="font-weight-medium"
                        >
                          {{ item.vulnerabilities_count }}
                        </v-chip>
                      </template>
                      <template v-slot:item.used_count="{ item }">
                        <v-chip
                          color="primary"
                          size="small"
                          class="font-weight-medium"
                        >
                          {{ item.used_count }}
                        </v-chip>
                      </template>
                      <template v-slot:item.created_at="{ item }">
                        {{ $formatDate(item.created_at) }}
                      </template>
                    </v-data-table>
                    <div class="d-flex align-center justify-end mt-2 gap-4">
                      <v-select
                        :items="[10, 20, 50, 100]"
                        v-model="componentsPerPage"
                        label="Items per page"
                        style="max-width: 150px"
                        hide-details
                        density="compact"
                        variant="outlined"
                        @update:model-value="onComponentsItemsPerPageChange"
                      />
                      <v-pagination
                        v-model="componentsPage"
                        :length="componentsPageCount"
                        @update:model-value="fetchComponents"
                        :total-visible="7"
                        density="comfortable"
                      />
                    </div>
                  </v-card-text>
                </v-window-item>

                <!-- Vulnerabilities Tab -->
                <v-window-item value="vulnerabilities">
                  <v-card-text>
                    <v-text-field
                      v-model="vulnerabilitiesSearch"
                      label="Search vulnerabilities"
                      placeholder="Search by vulnerability ID (e.g., CVE-2023-1234)"
                      prepend-inner-icon="mdi-magnify"
                      :append-inner-icon="vulnerabilitiesLoading ? 'mdi-loading mdi-spin' : undefined"
                      variant="outlined"
                      clearable
                      class="mb-4"
                      @click:clear="vulnerabilitiesSearch = ''"
                    ></v-text-field>
                    <div class="d-flex align-center justify-space-between mb-4">
                      <div class="text-caption text-grey">
                        💡 Search by vulnerability ID (e.g., CVE-2023-1234, GHSA-abc123, etc.)
                      </div>
                      <div v-if="vulnerabilitiesSearch" class="text-caption text-grey">
                        Found {{ vulnerabilitiesTotal }} result{{ vulnerabilitiesTotal !== 1 ? 's' : '' }}
                      </div>
                    </div>
                    <v-data-table
                      :headers="vulnerabilityHeaders"
                      :items="vulnerabilities"
                      :loading="vulnerabilitiesLoading"
                      :items-per-page="vulnerabilitiesPerPage"
                      :page="vulnerabilitiesPage"
                      :sort-by="vulnerabilitiesSortBy"
                      :sort-desc="vulnerabilitiesSortDesc"
                      hide-default-footer
                      class="elevation-1"
                      hover
                      density="comfortable"
                      @click:row="onVulnerabilityRowClick"
                      :no-data-text="vulnerabilitiesSearch ? 'No vulnerabilities found matching your search' : 'No vulnerabilities found'"
                    >
                      <template v-slot:item.vulnerability_id="{ item }">
                        <v-chip
                          size="small"
                          color="primary"
                          variant="tonal"
                          class="font-weight-medium"
                        >
                          {{ item.vulnerability_id }}
                        </v-chip>
                      </template>
                      <template v-slot:item.vulnerability_type="{ item }">
                        <v-chip
                          size="small"
                          :color="getVulnerabilityTypeColor(item.vulnerability_type)"
                          variant="tonal"
                        >
                          {{ item.vulnerability_type }}
                        </v-chip>
                      </template>
                      <template v-slot:item.severity="{ item }">
                        <v-chip
                          size="small"
                          :color="getSeverityColor(item.severity)"
                          variant="tonal"
                          class="font-weight-medium"
                        >
                          {{ item.severity }}
                        </v-chip>
                      </template>
                      <template v-slot:item.epss="{ item }">
                        <v-chip
                          size="small"
                          :color="getEpssColor(item.epss)"
                          variant="tonal"
                        >
                          {{ (item.epss * 100).toFixed(1) }}%
                        </v-chip>
                      </template>
                      <template v-slot:item.fixable="{ item }">
                        <v-chip
                          size="small"
                          :color="item.fixable ? 'success' : 'error'"
                          variant="tonal"
                        >
                          <v-icon size="x-small" class="mr-1">
                            {{ item.fixable ? 'mdi-check' : 'mdi-close' }}
                          </v-icon>
                          {{ item.fixable ? 'Fixable' : 'Not Fixable' }}
                        </v-chip>
                      </template>
                      <template v-slot:item.fix="{ item }">
                        <span v-if="item.fix" class="text-caption">{{ item.fix }}</span>
                        <span v-else class="text-caption text-grey">No fix available</span>
                      </template>
                    </v-data-table>
                    <div class="d-flex align-center justify-end mt-2 gap-4">
                      <v-select
                        :items="[10, 20, 50, 100]"
                        v-model="vulnerabilitiesPerPage"
                        label="Items per page"
                        style="max-width: 150px"
                        hide-details
                        density="compact"
                        variant="outlined"
                        @update:model-value="onVulnerabilitiesItemsPerPageChange"
                      />
                      <v-pagination
                        v-model="vulnerabilitiesPage"
                        :length="vulnerabilitiesPageCount"
                        @update:model-value="fetchVulnerabilities"
                        :total-visible="7"
                        density="comfortable"
                      />
                    </div>
                  </v-card-text>
                </v-window-item>
              </v-window>
            </v-card>
          </div>
        </v-col>
      </v-row>
    </v-container>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../plugins/axios'
import { notificationService } from '../plugins/notifications'
import { debounce } from '../utils/debounce'
import { getComponentTypeColor, getVulnerabilityTypeColor, getSeverityColor, getEpssColor } from '../utils/colors'
import type { Image, ComponentVersion, PaginatedResponse, Vulnerability } from '../types/interfaces'
import PieChart from '../components/PieChart.vue'
import type { DataTableSortItem } from 'vuetify'

// Define breadcrumb item type
interface BreadcrumbItem {
  title: string
  to?: { name: string; params?: Record<string, string>; query?: Record<string, string> }
  disabled?: boolean
}

const router = useRouter()
const route = useRoute()
const image = ref<Image | null>(null)
const loading = ref(true)
const error = ref('')

const animatedFindings = ref(0)
const animatedComponents = ref(0)

const showUniqueFindings = ref(false)
const showFixableOnly = ref(false)

// SBOM lazy loading
const showSbom = ref(false)
const sbomLoading = ref(false)
const sbomData = ref<any>(null)

// Active tab
const activeTab = ref('components')

// PieChart legend filtering logic
const severityOrder = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN']
const severityLabels = ['Critical', 'High', 'Medium', 'Low', 'Info|Unknown']
const severityColors = [
  '#FF6384', // CRITICAL
  '#FF9F40', // HIGH
  '#FFCD56', // MEDIUM
  '#4BC0C0', // LOW
  '#36A2EB'  // UNKNOWN
]
const legendVisible = ref([true, true, true, true, true])

// Color utilities imported from utils/colors.ts

const pieChartData = computed(() => {
  if (!image.value) {
    return {
      labels: severityLabels,
      datasets: [{ label: 'Vulnerabilities by Severity', data: [0,0,0,0,0], backgroundColor: severityColors }]
    }
  }
  // Select data for PieChart
  let counts: number[]
  if (showUniqueFindings.value && showFixableOnly.value) {
    counts = severityOrder.map(sev => image.value?.fixable_unique_severity_counts?.[sev] || 0)
  } else if (showUniqueFindings.value) {
    counts = severityOrder.map(sev => image.value?.unique_severity_counts?.[sev] || 0)
  } else if (showFixableOnly.value) {
    counts = severityOrder.map(sev => image.value?.fixable_severity_counts?.[sev] || 0)
  } else {
    counts = severityOrder.map(sev => image.value?.severity_counts?.[sev] || 0)
  }
  return {
    labels: severityLabels,
    datasets: [
      {
        label: showFixableOnly.value
          ? (showUniqueFindings.value ? 'Fixable Unique Vulnerabilities by Severity' : 'Fixable Vulnerabilities by Severity')
          : (showUniqueFindings.value ? 'Unique Vulnerabilities by Severity' : 'Vulnerabilities by Severity'),
        data: counts.map((v, i) => legendVisible.value[i] ? v : 0),
        backgroundColor: severityColors
      }
    ]
  }
})

const breadcrumbItems = computed((): BreadcrumbItem[] => {
  if (!image.value?.repository_info) {
    return []
  }
  
  const { repository_name, repository_uuid, tag, tag_uuid } = image.value.repository_info
  
  const items: BreadcrumbItem[] = [
    {
      title: 'Repositories',
      to: { name: 'repositories' }
    }
  ]
  
  // Add repository link only if we have a valid UUID
  if (repository_name && repository_uuid) {
    items.push({
      title: repository_name,
      to: { name: 'RepositoryDetail', params: { uuid: repository_uuid } }
    })
  } else if (repository_name) {
    items.push({
      title: repository_name,
      disabled: true
    })
  }
  
  // Add tag link only if we have valid UUIDs
  if (tag && tag_uuid) {
    items.push({
      title: `Tag: ${tag}`,
      to: { name: 'tag-images', params: { uuid: tag_uuid } }
    })
  } else if (tag) {
    items.push({
      title: `Tag: ${tag}`,
      disabled: true
    })
  }
  
  // Always add current image name
  items.push({
    title: image.value.name,
    disabled: true // Current page, no link
  })
  
  return items
})

function onLegendClick(i: number) {
  legendVisible.value[i] = !legendVisible.value[i]
}

function animateNumber(targetRef: any, targetValue: number, duration = 900) {
  const start = 0
  const startTime = performance.now()
  function animate(currentTime: number) {
    const elapsed = currentTime - startTime
    const progress = Math.min(elapsed / duration, 1)
    targetRef.value = Math.floor(progress * (targetValue - start) + start)
    if (progress < 1) {
      requestAnimationFrame(animate)
    } else {
      targetRef.value = targetValue
    }
  }
  requestAnimationFrame(animate)
}

// Animate findings when image, showUniqueFindings, or showFixableOnly changes
watch([image, showUniqueFindings, showFixableOnly], ([img, unique, fixable], [oldImg, oldUnique, oldFixable]) => {
  if (img) {
    // Number of vulnerabilities
    let findingsValue = 0
    if (fixable) {
      findingsValue = unique ? (img.fixable_unique_findings || 0) : (img.fixable_findings || 0)
    } else {
      findingsValue = unique ? (img.unique_findings || 0) : (img.findings || 0)
    }
    animateNumber(animatedFindings, findingsValue)
    // Number of components
    let componentsValue = fixable ? (img.fully_fixable_components_count || 0) : (img.components_count || 0)
    animateNumber(animatedComponents, componentsValue)
  }
})

const pieChartOptions = {
  responsive: true,
  plugins: {
    legend: { display: false }
  }
}

function statusLabel(status: string) {
  switch (status) {
    case 'pending': return 'Pending';
    case 'in_process': return 'In Process';
    case 'success': return 'Success';
    case 'error': return 'Error';
    default: return 'None';
  }
}
function statusColor(status: string) {
  switch (status) {
    case 'pending': return 'grey';
    case 'in_process': return 'info';
    case 'success': return 'success';
    case 'error': return 'error';
    default: return 'default';
  }
}

async function toggleSbom() {
  if (!showSbom.value) {
    // Open - if not loaded yet, load
    showSbom.value = true;
    if (!sbomData.value) {
      sbomLoading.value = true;
      try {
        const uuid = route.params.uuid;
        const response = await api.get(`/images/${uuid}/sbom/`);
        sbomData.value = response.data;
      } catch (e: any) {
        sbomData.value = { error: e?.response?.data?.detail || 'Failed to load SBOM.' };
      } finally {
        sbomLoading.value = false;
      }
    }
  } else {
    // Hide
    showSbom.value = false;
  }
}

const fetchImage = async () => {
  loading.value = true
  error.value = ''
  try {
    const uuid = route.params.uuid
    const response = await api.get(`/images/${uuid}/`)
    image.value = response.data
    await fetchComponents() // fetch components only after image is loaded
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Failed to load image details.'
  } finally {
    loading.value = false
  }
}

// --- Components for table ---
const components = ref<ComponentVersion[]>([])
const componentsLoading = ref(false)
const componentsTotal = ref(0)
const componentsPage = ref(1)
const componentsPerPage = ref(10)
const componentsSortBy = ref<readonly DataTableSortItem[]>([])
const componentsSortDesc = ref<boolean[]>([])
const componentsSearch = ref('')
const componentsPageCount = computed(() => Math.ceil(componentsTotal.value / componentsPerPage.value))

const componentHeaders = [
  { title: 'Component', key: 'component.name', sortable: true },
  { title: 'Version', key: 'version', sortable: true },
  { title: 'Type', key: 'component.type', sortable: true },
  { title: 'Vulnerabilities', key: 'vulnerabilities_count', sortable: true },
  { title: 'Used in:', key: 'used_count', sortable: true }
] as const

const fetchComponents = async () => {
  if (!image.value) {
    console.log('fetchComponents: image.value is not set');
    return;
  }
  if (!image.value.uuid) {
    console.log('fetchComponents: image.value.uuid is not set');
    return;
  }
  componentsLoading.value = true
  try {
    // Get the first sort field and direction
    const sortField = componentsSortBy.value[0]
    const sortDesc = componentsSortDesc.value[0]
    
    // Build ordering parameter
    let ordering = undefined
    if (sortField) {
      const prefix = sortDesc ? '-' : ''
      ordering = `${prefix}${sortField}`
    }

    const params = {
      images: image.value.uuid,
      page: componentsPage.value,
      page_size: componentsPerPage.value,
      ordering,
      search: componentsSearch.value || undefined
    }
    const resp = await api.get<PaginatedResponse<ComponentVersion>>(`/component-versions/`, { params })
    components.value = resp.data.results
    componentsTotal.value = resp.data.count
  } catch (e: any) {
    components.value = []
    componentsTotal.value = 0
    // Show error notification if it's not a 404 (which is expected for empty results)
    if (e?.response?.status !== 404) {
      notificationService.error('Failed to fetch components')
    }
  } finally {
    componentsLoading.value = false
  }
}

// --- Vulnerabilities for table ---
const vulnerabilities = ref<Vulnerability[]>([])
const vulnerabilitiesLoading = ref(false)
const vulnerabilitiesTotal = ref(0)
const vulnerabilitiesPage = ref(1)
const vulnerabilitiesPerPage = ref(10)
const vulnerabilitiesSortBy = ref<readonly DataTableSortItem[]>([])
const vulnerabilitiesSortDesc = ref<boolean[]>([])
const vulnerabilitiesSearch = ref('')
const vulnerabilitiesPageCount = computed(() => Math.ceil(vulnerabilitiesTotal.value / vulnerabilitiesPerPage.value))

const vulnerabilityHeaders = [
  { title: 'Vulnerability ID', key: 'vulnerability_id', sortable: true },
  { title: 'Type', key: 'vulnerability_type', sortable: true },
  { title: 'Severity', key: 'severity', sortable: true },
  { title: 'EPSS', key: 'epss', sortable: true },
  { title: 'Fixable', key: 'fixable', sortable: true },
  { title: 'Fix', key: 'fix', sortable: false }
] as const

const fetchVulnerabilities = async () => {
  if (!image.value || !image.value.uuid) {
    console.log('fetchVulnerabilities: image.value or image.value.uuid is not set');
    return;
  }
  vulnerabilitiesLoading.value = true
  try {
    // Get the first sort field and direction
    const sortField = vulnerabilitiesSortBy.value[0]
    const sortDesc = vulnerabilitiesSortDesc.value[0]
    
    // Build ordering parameter
    let ordering = undefined
    if (sortField) {
      const prefix = sortDesc ? '-' : ''
      ordering = `${prefix}${sortField}`
    }

    const params = {
      page: vulnerabilitiesPage.value,
      page_size: vulnerabilitiesPerPage.value,
      ordering,
      search: vulnerabilitiesSearch.value || undefined
    }
    const resp = await api.get<PaginatedResponse<Vulnerability>>(`/images/${image.value.uuid}/vulnerabilities/`, { params })
    vulnerabilities.value = resp.data.results
    vulnerabilitiesTotal.value = resp.data.count
  } catch (e: any) {
    vulnerabilities.value = []
    vulnerabilitiesTotal.value = 0
    // Show error notification if it's not a 404 (which is expected for empty results)
    if (e?.response?.status !== 404) {
      notificationService.error('Failed to fetch vulnerabilities')
    }
  } finally {
    vulnerabilitiesLoading.value = false
  }
}

// Debounced fetch functions
const debouncedFetchComponents = debounce(() => {
  if (image.value && image.value.uuid) {
    fetchComponents()
  }
}, 300)

const debouncedFetchVulnerabilities = debounce(() => {
  if (image.value && image.value.uuid) {
    fetchVulnerabilities()
  }
}, 300)

// Watchers for components
watch([
  componentsPage,
  componentsPerPage,
  componentsSortBy,
  componentsSortDesc
], fetchComponents)

watch(componentsSearch, () => {
  componentsPage.value = 1 // reset to first page on new search
  debouncedFetchComponents()
})

// Watchers for vulnerabilities
watch([
  vulnerabilitiesPage,
  vulnerabilitiesPerPage,
  vulnerabilitiesSortBy,
  vulnerabilitiesSortDesc
], fetchVulnerabilities)

watch(vulnerabilitiesSearch, () => {
  vulnerabilitiesPage.value = 1 // reset to first page on new search
  debouncedFetchVulnerabilities()
})

// Watch for tab changes to load vulnerabilities when needed
watch(activeTab, (newTab) => {
  if (newTab === 'vulnerabilities' && image.value && image.value.uuid) {
    fetchVulnerabilities()
  }
})

const onVulnerabilitiesItemsPerPageChange = (val: number) => {
  vulnerabilitiesPerPage.value = val
  vulnerabilitiesPage.value = 1
  fetchVulnerabilities()
}

const onComponentsItemsPerPageChange = (val: number) => {
  componentsPerPage.value = val
  componentsPage.value = 1
  fetchComponents()
}

const onVulnerabilityRowClick = (event: MouseEvent, { item }: { item: Vulnerability }) => {
  if (item && item.uuid) {
    router.push({ name: 'vulnerability-detail', params: { uuid: item.uuid } })
  }
}

onMounted(fetchImage)
</script>

<style scoped>
.image-detail {
  padding: 20px;
}
.main-info-card {
  border-radius: 12px;
  box-shadow: 0 2px 12px 0 rgba(60,60,60,0.07);
}
.digest-text {
  font-family: monospace;
  color: #888;
}
.circle-info {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.circle-number {
  font-size: 2.7rem;
  font-weight: 700;
}
.circle-label {
  font-size: 1.1rem;
  color: #666;
  margin-top: 4px;
  font-weight: 500;
}
.sbom-json {
  background: #f8f8f8;
  border-radius: 6px;
  padding: 12px;
  font-size: 0.95rem;
  max-height: 400px;
  overflow: auto;
}
.status-chip {
  font-size: 1.15rem;
  height: 38px;
  min-width: 90px;
  padding: 0 18px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
}
.pie-legend-wrapper {
  width: 100%;
  margin-top: 12px;
}
.pie-legend {
  display: flex;
  flex-direction: row;
  justify-content: center;
  align-items: center;
  flex-wrap: wrap;
  gap: 18px;
}
.legend-row {
  display: flex;
  align-items: center;
  margin-bottom: 0;
  cursor: pointer;
  transition: background 0.2s;
}
.legend-row.active {
  background: #ffffff;
  border-radius: 6px;
}
.legend-color {
  width: 18px;
  height: 18px;
  border-radius: 4px;
  margin-right: 8px;
  display: inline-block;
}
.legend-label {
  font-size: 1rem;
  color: #444;
  font-weight: 500;
}
.legend-label--strikethrough {
  text-decoration: line-through;
  opacity: 0.5;
}
.switch-unique-findings {
  margin-right: 8px;
}
.switch-fixable-findings {
  margin-right: 8px;
}

/* Breadcrumb styles */
.v-breadcrumbs {
  background: transparent;
  padding: 8px 0;
}

.v-breadcrumbs .v-btn {
  font-weight: 500;
  color: #666;
  transition: color 0.2s;
}

.v-breadcrumbs .v-btn:hover {
  color: #1976d2;
}

.v-breadcrumbs .text-grey {
  color: #999;
  font-weight: 400;
}

/* Component-specific styles */
</style> 