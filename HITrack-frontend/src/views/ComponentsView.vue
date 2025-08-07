<template>
  <div class="components">
    <v-container>
      <v-row>
        <v-col cols="12">
          <h1 class="text-h4 mb-4 font-weight-black">Components</h1>
        </v-col>
      </v-row>
      <v-row>
        <v-col cols="12">
          <v-text-field
            v-model="componentsSearch"
            label="Search components"
            prepend-inner-icon="mdi-magnify"
            variant="outlined"
            clearable
            class="mb-4"
            @click:clear="componentsSearch = ''"
          ></v-text-field>
          <v-data-table
            :headers="headers"
            :items="components"
            :loading="loading"
            :items-per-page="itemsPerPage"
            :page="page"
            hide-default-footer
            class="elevation-1"
            hover
            density="comfortable"
            item-value="uuid"
          >
            <template v-slot:item.name="{ item }">
              <div @click="onRowClick(item)" style="cursor: pointer; width: 100%; height: 100%;">
                {{ item.name }}
              </div>
            </template>
            <template v-slot:item.created_at="{ item }">
              <div @click="onRowClick(item)" style="cursor: pointer; width: 100%; height: 100%;">
                {{ $formatDate(item.created_at) }}
              </div>
            </template>
            <template v-slot:item.updated_at="{ item }">
              <div @click="onRowClick(item)" style="cursor: pointer; width: 100%; height: 100%;">
                {{ $formatDate(item.updated_at) }}
              </div>
            </template>
            <template v-slot:item.type="{ item }">
              <v-chip
                size="small"
                :color="getTypeColor(item.type)"
                variant="tonal"
                @click.stop="onRowClick(item)"
                style="cursor: pointer"
              >
                {{ item.type }}
              </v-chip>
            </template>
          </v-data-table>
          <div class="d-flex align-center justify-end mt-2 gap-4">
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
              v-model="page"
              :length="pageCount"
              @update:model-value="fetchComponents"
              :total-visible="7"
              density="comfortable"
            />
          </div>
        </v-col>
      </v-row>
    </v-container>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '../plugins/axios'
import { notificationService } from '../plugins/notifications'
import type { Component, PaginatedResponse } from '../types/interfaces'

const components = ref<Component[]>([])
const loading = ref(false)
const page = ref(1)
const itemsPerPage = ref(10)
const totalItems = ref(0)
const sortBy = ref<string[]>([])
const sortDesc = ref<boolean[]>([])
const componentsSearch = ref('')

const pageCount = computed(() => Math.ceil(totalItems.value / itemsPerPage.value))

const headers: any[] = [
  { title: 'Name', key: 'name', sortable: true },
  { title: 'Type', key: 'type', sortable: true },
  { title: 'Created', key: 'created_at', sortable: true },
  { title: 'Updated', key: 'updated_at', sortable: true }
]

const getTypeColor = (type: string | undefined) => {
  if (!type) return 'grey'
  const colors: { [key: string]: string } = {
    'unknown': 'grey',
    'npm': 'red',
    'pypi': 'blue',
    'maven': 'green',
    'gem': 'purple',
    'go': 'cyan',
    'nuget': 'orange',
    'deb': 'grey'
  }
  return colors[type.toLowerCase()] || 'grey'
}

const fetchComponents = async () => {
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: itemsPerPage.value,
      ordering: sortBy.value.length ? `${sortDesc.value[0] ? '-' : ''}${sortBy.value[0]}` : undefined,
      search: componentsSearch.value || undefined
    }
    const response = await api.get<PaginatedResponse<Component>>('components/', { params })
    components.value = response.data.results
    totalItems.value = response.data.count
    console.log('Fetched components:', components.value)
  } catch (error) {
    console.error('Error fetching components:', error)
    notificationService.error('Failed to fetch components')
  } finally {
    loading.value = false
  }
}

const onItemsPerPageChange = (val: number) => {
  itemsPerPage.value = val
  page.value = 1
  fetchComponents()
}

const onSortByChange = (newSortBy: string[]) => {
  sortBy.value = newSortBy
  fetchComponents()
}
const onSortDescChange = (newSortDesc: boolean[]) => {
  sortDesc.value = newSortDesc
  fetchComponents()
}

// Debounce helper
function debounce(fn: Function, delay: number) {
  let timeout: ReturnType<typeof setTimeout> | null = null
  return (...args: any[]) => {
    if (timeout) clearTimeout(timeout)
    timeout = setTimeout(() => fn(...args), delay)
  }
}

const debouncedFetchComponents = debounce(fetchComponents, 300)

const router = useRouter()

const onRowClick = (event: any) => {
  console.log('Row clicked event:', event)
  // In Vuetify DataTable, the clicked item is passed directly as the first parameter
  const component = event
  console.log('Component from event:', component)
  if (component && component.uuid) {
    console.log('Navigating to component detail with UUID:', component.uuid)
    router.push({ name: 'component-detail', params: { uuid: component.uuid } })
  } else {
    console.log('Component has no UUID or event is missing')
  }
}

watch([
  page,
  itemsPerPage,
  sortBy,
  sortDesc
], fetchComponents)

watch(componentsSearch, () => {
  page.value = 1
  debouncedFetchComponents()
})

onMounted(() => {
  fetchComponents()
})
</script>

<style scoped>
.components {
  padding: 20px;
}

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
  transition: all 0.3s ease;
}

:deep(.v-table .v-table__wrapper > table > thead > tr > th:hover) {
  background-color: #e3f2fd;
  color: rgba(0, 0, 0, 0.87);
}

:deep(.v-table .v-table__wrapper > table > tbody > tr > td) {
  padding: 12px 16px;
  border-bottom: 1px solid #e0e0e0;
}

:deep(.v-table .v-table__wrapper > table > tbody > tr:hover) {
  background-color: #e3f2fd;
  cursor: pointer;
}

.v-theme--matrix :deep(.v-table .v-table__wrapper > table > thead > tr > th) {
  background: #011 !important;
  color: #39FF14 !important;
  border: 1px solid #39FF14 !important;
}
</style> 