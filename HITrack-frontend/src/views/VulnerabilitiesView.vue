<template>
  <div class="vulnerabilities">
    <v-container>
      <v-row>
        <v-col cols="12">
          <div class="d-flex align-center justify-space-between mb-4">
            <h1 class="text-h4 font-weight-black">Vulnerabilities</h1>
            <div v-if="activeFilter" class="d-flex align-center">
              <v-chip 
                :color="getFilterColor()" 
                size="small" 
                class="mr-2"
                closable
                @click:close="clearActiveFilter"
              >
                <v-icon size="16" class="mr-1">{{ getFilterIcon() }}</v-icon>
                {{ activeFilter }}
              </v-chip>
            </div>
          </div>
        </v-col>
      </v-row>

      <v-row>
        <v-col cols="12">
          <!-- Search and Filters -->
          <v-card class="mb-4">
            <v-card-text>
              <v-row>
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model="searchQuery"
                    label="Search vulnerabilities"
                    placeholder="Search by vulnerability ID (e.g., CVE-2023-1234)"
                    prepend-inner-icon="mdi-magnify"
                    :append-inner-icon="loading ? 'mdi-loading mdi-spin' : undefined"
                    variant="outlined"
                    clearable
                    @click:clear="searchQuery = ''"
                  ></v-text-field>
                </v-col>
                <v-col cols="12" md="3">
                  <v-select
                    v-model="severityFilter"
                    :items="severityOptions"
                    label="Severity"
                    variant="outlined"
                    clearable
                    @update:model-value="onFilterChange"
                  ></v-select>
                </v-col>
                <v-col cols="12" md="2">
                  <v-select
                    v-model="typeFilter"
                    :items="typeOptions"
                    label="Type"
                    variant="outlined"
                    clearable
                    @update:model-value="onFilterChange"
                  ></v-select>
                </v-col>
                <v-col cols="12" md="1">
                  <v-checkbox
                    v-model="fixableFilter"
                    label="Fixable"
                    @update:model-value="onFilterChange"
                  ></v-checkbox>
                </v-col>
              </v-row>
              <div class="d-flex align-center justify-space-between mt-3">
                <div v-if="searchQuery" class="text-caption text-grey">
                  Found {{ total }} result{{ total !== 1 ? 's' : '' }}
                </div>
                <div class="d-flex gap-2">
                  <v-btn
                    size="small"
                    variant="outlined"
                    :color="route.query.cisa_kev === 'true' ? 'error' : 'default'"
                    @click="toggleFilter('cisa_kev')"
                    class="text-caption"
                  >
                    <v-icon size="16" class="mr-1">mdi-shield-alert</v-icon>
                    CISA KEV
                  </v-btn>
                  <v-btn
                    size="small"
                    variant="outlined"
                    :color="route.query.exploit_available === 'true' ? 'warning' : 'default'"
                    @click="toggleFilter('exploit_available')"
                    class="text-caption"
                  >
                    <v-icon size="16" class="mr-1">mdi-bug</v-icon>
                    Exploit Available
                  </v-btn>
                  <v-btn
                    size="small"
                    variant="outlined"
                    :color="route.query.ransomware === 'true' ? 'error' : 'default'"
                    @click="toggleFilter('ransomware')"
                    class="text-caption"
                  >
                    <v-icon size="16" class="mr-1">mdi-lock-alert</v-icon>
                    Ransomware
                  </v-btn>
                </div>
              </div>
            </v-card-text>
          </v-card>

          <!-- Vulnerabilities Table -->
          <v-card>
            <v-data-table
              :headers="headers"
              :items="vulnerabilities"
              :loading="loading"
              :items-per-page="itemsPerPage"
              :page="currentPage"
              :sort-by="sortBy"
              :sort-desc="sortDesc"
              hide-default-footer
              class="elevation-1"
              hover
              density="comfortable"
              @click:row="onVulnerabilityRowClick"
              :no-data-text="searchQuery ? 'No vulnerabilities found matching your search' : 'No vulnerabilities found'"
            >
              <template v-slot:item.vulnerability_id="{ item }">
                <v-chip
                  size="small"
                  color="primary"
                  variant="tonal"
                  class="font-weight-medium cursor-pointer"
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
              <template v-slot:item.cisa_kev="{ item }">
                <v-chip
                  size="small"
                  :color="item.cisa_kev ? 'error' : 'success'"
                  variant="tonal"
                >
                  <v-icon size="16" class="mr-1">
                    {{ item.cisa_kev ? 'mdi-shield-alert' : 'mdi-shield-check' }}
                  </v-icon>
                  {{ item.cisa_kev ? 'Yes' : 'No' }}
                </v-chip>
              </template>
              <template v-slot:item.exploit_available="{ item }">
                <v-chip
                  size="small"
                  :color="item.exploit_available ? 'warning' : 'success'"
                  variant="tonal"
                >
                  <v-icon size="16" class="mr-1">
                    {{ item.exploit_available ? 'mdi-bug' : 'mdi-shield-check' }}
                  </v-icon>
                  {{ item.exploit_available ? 'Yes' : 'No' }}
                </v-chip>
              </template>
              <template v-slot:item.has_details="{ item }">
                <v-chip
                  size="small"
                  :color="item.has_details ? 'info' : 'grey'"
                  variant="tonal"
                >
                  <v-icon size="16" class="mr-1">
                    {{ item.has_details ? 'mdi-information' : 'mdi-information-outline' }}
                  </v-icon>
                  {{ item.has_details ? 'Yes' : 'No' }}
                </v-chip>
              </template>
              <template v-slot:item.description="{ item }">
                <div class="text-truncate" style="max-width: 300px;" :title="item.description">
                  {{ item.description }}
                </div>
              </template>
            </v-data-table>

            <!-- Pagination -->
            <div class="d-flex align-center justify-end mt-4 gap-4 pa-4">
              <v-select
                :items="[10, 20, 50, 100]"
                v-model="itemsPerPage"
                label="Items per page"
                style="max-width: 150px"
                hide-details
                density="compact"
                variant="outlined"
                @update:model-value="onItemsPerPageChange"
              />
              <v-pagination
                v-model="currentPage"
                :length="pageCount"
                @update:model-value="fetchVulnerabilities"
                :total-visible="7"
                density="comfortable"
              />
            </div>
          </v-card>
        </v-col>
      </v-row>
    </v-container>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import api from '../plugins/axios'
import { notificationService } from '../plugins/notifications'
import { debounce } from '../utils/debounce'
import { getVulnerabilityTypeColor, getSeverityColor, getEpssColor } from '../utils/colors'
import type { Vulnerability, PaginatedResponse } from '../types/interfaces'
import type { DataTableSortItem } from 'vuetify'

const router = useRouter()
const route = useRoute()

// Reactive data
const vulnerabilities = ref<Vulnerability[]>([])
const loading = ref(false)
const total = ref(0)

// Pagination state
const currentPage = ref(1)
const itemsPerPage = ref(20)
const pageCount = computed(() => Math.ceil(total.value / itemsPerPage.value))

// Sorting state
const sortBy = ref<readonly DataTableSortItem[]>([])
const sortDesc = ref<boolean[]>([])

// Search and filter state
const searchQuery = ref('')
const severityFilter = ref('')
const typeFilter = ref('')
const fixableFilter = ref(false)
const activeFilter = ref('')

// Filter options
const severityOptions = [
  { title: 'Critical', value: 'CRITICAL' },
  { title: 'High', value: 'HIGH' },
  { title: 'Medium', value: 'MEDIUM' },
  { title: 'Low', value: 'LOW' },
  { title: 'Unknown', value: 'UNKNOWN' }
] as const

const typeOptions = [
  { title: 'CVE', value: 'CVE' },
  { title: 'GHSA', value: 'GHSA' },
  { title: 'RUSTSEC', value: 'RUSTSEC' },
  { title: 'PYSEC', value: 'PYSEC' },
  { title: 'NPM', value: 'NPM' }
] as const

// Table configuration
const headers = [
  { title: 'Vulnerability ID', key: 'vulnerability_id', sortable: true },
  { title: 'Type', key: 'vulnerability_type', sortable: true },
  { title: 'Severity', key: 'severity', sortable: true },
  { title: 'EPSS', key: 'epss', sortable: true },
  { title: 'CISA KEV', key: 'cisa_kev', sortable: false },
  { title: 'Exploit', key: 'exploit_available', sortable: false },
  { title: 'Details', key: 'has_details', sortable: false },
  { title: 'Description', key: 'description', sortable: false }
] as const

// Fetch vulnerabilities with optimized parameters
const fetchVulnerabilities = async () => {
  loading.value = true
  try {
    // Build query parameters
    const params: Record<string, any> = {
      page: currentPage.value,
      page_size: itemsPerPage.value
    }

    // Add sorting
    const sortField = sortBy.value[0]
    const sortDescValue = sortDesc.value[0]
    if (sortField) {
      params.ordering = `${sortDescValue ? '-' : ''}${sortField}`
    }

    // Add search and filters
    if (searchQuery.value) params.search = searchQuery.value
    if (severityFilter.value) params.severity = severityFilter.value
    if (typeFilter.value) params.vulnerability_type = typeFilter.value
    if (fixableFilter.value) params.fixable = 'true'
    
    // Add special filters from URL parameters
    if (route.query.cisa_kev === 'true') params.cisa_kev = 'true'
    if (route.query.exploit_available === 'true') params.exploit_available = 'true'
    if (route.query.ransomware === 'true') params.ransomware = 'true'

    const resp = await api.get<PaginatedResponse<Vulnerability>>('vulnerabilities/', { params })
    vulnerabilities.value = resp.data.results
    total.value = resp.data.count
  } catch (e: any) {
    vulnerabilities.value = []
    total.value = 0
    if (e?.response?.status !== 404) {
      notificationService.error('Failed to fetch vulnerabilities')
    }
  } finally {
    loading.value = false
  }
}

// Debounced search function
const debouncedFetchVulnerabilities = debounce(fetchVulnerabilities, 300)

// Handle URL parameters for filters
const handleUrlParams = () => {
  const severity = route.query.severity as string
  const fixable = route.query.fixable as string
  const cisaKev = route.query.cisa_kev as string
  const exploitAvailable = route.query.exploit_available as string
  const ransomware = route.query.ransomware as string
  
  if (severity) {
    severityFilter.value = severity
  }
  
  if (fixable === 'true') {
    fixableFilter.value = true
  }
  
  if (cisaKev === 'true') {
    // Set CISA KEV filter
    activeFilter.value = 'CISA KEV Vulnerabilities'
  }
  
  if (exploitAvailable === 'true') {
    // Set exploit available filter
    activeFilter.value = 'Exploit Available'
  }
  
  if (ransomware === 'true') {
    // Set ransomware filter
    activeFilter.value = 'Ransomware Vulnerabilities'
  }
}

// Event handlers
const onVulnerabilityRowClick = (_: MouseEvent, { item }: { item: Vulnerability }) => {
  item?.uuid && router.push({ name: 'vulnerability-detail', params: { uuid: item.uuid } })
}

const onItemsPerPageChange = (val: number) => {
  itemsPerPage.value = val
  currentPage.value = 1
  fetchVulnerabilities()
}

const onFilterChange = () => {
  currentPage.value = 1
  fetchVulnerabilities()
}

// Color utilities imported from utils/colors.ts

// Watchers
watch([
  currentPage,
  itemsPerPage,
  sortBy,
  sortDesc
], fetchVulnerabilities)

watch(searchQuery, () => {
  currentPage.value = 1
  debouncedFetchVulnerabilities()
})

// Filter utility methods
const getFilterColor = (): string => {
  if (route.query.cisa_kev === 'true') return 'error'
  if (route.query.exploit_available === 'true') return 'warning'
  if (route.query.ransomware === 'true') return 'error'
  return 'primary'
}

const getFilterIcon = (): string => {
  if (route.query.cisa_kev === 'true') return 'mdi-shield-alert'
  if (route.query.exploit_available === 'true') return 'mdi-bug'
  if (route.query.ransomware === 'true') return 'mdi-lock-alert'
  return 'mdi-filter'
}

const clearActiveFilter = () => {
  activeFilter.value = ''
  router.push({ query: {} })
  fetchVulnerabilities()
}

const toggleFilter = (filterType: string) => {
  const currentQuery = { ...route.query }
  
  if (currentQuery[filterType] === 'true') {
    // Remove filter
    delete currentQuery[filterType]
  } else {
    // Add filter
    currentQuery[filterType] = 'true'
  }
  
  router.push({ query: currentQuery })
}

// Update active filter based on route query
watch(() => route.query, (newQuery) => {
  if (newQuery.cisa_kev === 'true') {
    activeFilter.value = 'CISA KEV Vulnerabilities'
  } else if (newQuery.exploit_available === 'true') {
    activeFilter.value = 'Exploit Available'
  } else if (newQuery.ransomware === 'true') {
    activeFilter.value = 'Ransomware Vulnerabilities'
  } else {
    activeFilter.value = ''
  }
  
  // Refetch data when query parameters change
  fetchVulnerabilities()
}, { immediate: true })

// Initialize
onMounted(() => {
  handleUrlParams()
  fetchVulnerabilities()
})
</script>

<style scoped>
.vulnerabilities {
  padding: 20px;
}

/* Component-specific styles */

/* Table styling */
:deep(.v-table) {
  background: transparent;
}

:deep(.v-table .v-table__wrapper > table) {
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

:deep(.v-table .v-table__wrapper > table > thead > tr > th) {
  font-weight: 700 !important;
  font-size: 0.875rem;
  color: rgba(0, 0, 0, 0.87);
  background: linear-gradient(135deg, #f8f9fa 0%, #e3f2fd 100%);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 16px;
  border-bottom: 2px solid #1976d2;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
}

:deep(.v-table .v-table__wrapper > table > thead > tr > th:hover) {
  background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(25, 118, 210, 0.2);
}

:deep(.v-table .v-table__wrapper > table > tbody > tr > td) {
  padding: 16px;
  border-bottom: 1px solid #e0e0e0;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

:deep(.v-table .v-table__wrapper > table > tbody > tr) {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
}

:deep(.v-table .v-table__wrapper > table > tbody > tr:hover) {
  background: linear-gradient(135deg, #f8f9fa 0%, #e3f2fd 100%);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  border-radius: 8px;
  margin: 4px 0;
}

:deep(.v-table .v-table__wrapper > table > tbody > tr:hover > td:first-child) {
  border-top-left-radius: 8px;
  border-bottom-left-radius: 8px;
}

:deep(.v-table .v-table__wrapper > table > tbody > tr:hover > td:last-child) {
  border-top-right-radius: 8px;
  border-bottom-right-radius: 8px;
}

/* Matrix theme override */
.v-theme--matrix :deep(.v-table .v-table__wrapper > table) {
  border: 1px solid #39FF14 !important;
  box-shadow: 0 4px 12px rgba(57, 255, 20, 0.2) !important;
}

.v-theme--matrix :deep(.v-table .v-table__wrapper > table > thead > tr > th) {
  background: linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 100%) !important;
  color: #39FF14 !important;
  border-bottom: 2px solid #39FF14 !important;
}

.v-theme--matrix :deep(.v-table .v-table__wrapper > table > thead > tr > th:hover) {
  background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%) !important;
  box-shadow: 0 2px 8px rgba(57, 255, 20, 0.3) !important;
}

.v-theme--matrix :deep(.v-table .v-table__wrapper > table > tbody > tr:hover) {
  background: linear-gradient(135deg, #0a0a0a 0%, #1a2a1a 100%) !important;
  box-shadow: 0 4px 12px rgba(57, 255, 20, 0.2) !important;
}
</style> 