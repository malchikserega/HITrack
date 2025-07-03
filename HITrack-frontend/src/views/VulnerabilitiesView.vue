<template>
  <div class="vulnerabilities">
    <v-container>
      <v-row>
        <v-col cols="12">
          <h1 class="text-h4 mb-4 font-weight-black">Vulnerabilities</h1>
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
                <v-col cols="12" md="3">
                  <v-select
                    v-model="typeFilter"
                    :items="typeOptions"
                    label="Type"
                    variant="outlined"
                    clearable
                    @update:model-value="onFilterChange"
                  ></v-select>
                </v-col>
              </v-row>
              <div v-if="searchQuery" class="text-caption text-grey mt-2">
                Found {{ total }} result{{ total !== 1 ? 's' : '' }}
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
              <template v-slot:item.description="{ item }">
                <div class="text-truncate" style="max-width: 300px;" :title="item.description">
                  {{ item.description }}
                </div>
              </template>
              <template v-slot:item.created_at="{ item }">
                {{ $formatDate(item.created_at) }}
              </template>
              <template v-slot:item.updated_at="{ item }">
                {{ $formatDate(item.updated_at) }}
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
import { useRouter } from 'vue-router'
import api from '../plugins/axios'
import { notificationService } from '../plugins/notifications'
import { debounce } from '../utils/debounce'
import { getVulnerabilityTypeColor, getSeverityColor, getEpssColor } from '../utils/colors'
import type { Vulnerability, PaginatedResponse } from '../types/interfaces'
import type { DataTableSortItem } from 'vuetify'

const router = useRouter()

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
  { title: 'Description', key: 'description', sortable: false },
  { title: 'Created', key: 'created_at', sortable: true },
  { title: 'Updated', key: 'updated_at', sortable: true }
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

// Initialize
onMounted(() => {
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
  border-radius: 8px;
}

:deep(.v-table .v-table__wrapper > table > thead > tr > th) {
  font-weight: 700 !important;
  font-size: 0.875rem;
  color: rgba(0, 0, 0, 0.87);
  background-color: #f8f9fa;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 12px 16px;
  border-bottom: 2px solid #e0e0e0;
  transition: background-color 0.3s ease;
}

:deep(.v-table .v-table__wrapper > table > thead > tr > th:hover) {
  background-color: #e3f2fd;
}

:deep(.v-table .v-table__wrapper > table > tbody > tr > td) {
  padding: 12px 16px;
  border-bottom: 1px solid #e0e0e0;
}

:deep(.v-table .v-table__wrapper > table > tbody > tr:hover) {
  background-color: #f5f5f5;
}

/* Matrix theme override */
.v-theme--matrix :deep(.v-table .v-table__wrapper > table > thead > tr > th) {
  background: #011 !important;
  color: #39FF14 !important;
  border: 1px solid #39FF14 !important;
}
</style> 