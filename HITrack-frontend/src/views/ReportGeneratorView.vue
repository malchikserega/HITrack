<template>
  <div class="report-generator">
    <v-container fluid class="pa-0">
      <v-row justify="center">
        <v-col cols="12" md="11" lg="10" xl="9">
          <h1 class="text-h4 mb-4 font-weight-black">Report Generator</h1>
          <v-card class="mb-4 d-flex flex-column wide-card">
            <v-card-text>
              <v-text-field
                v-model="search"
                label="Search images"
                prepend-inner-icon="mdi-magnify"
                variant="outlined"
                clearable
                class="mb-4"
                @click:clear="search = ''"
              ></v-text-field>

              <div class="table-scroll">
                <v-data-table
                  v-model="selectedImages"
                  :headers="headers"
                  :items="images"
                  :loading="loading"
                  :items-per-page="itemsPerPage"
                  :page="page"
                  show-select
                  item-value="uuid"
                  hide-default-footer
                  class="elevation-1"
                  hover
                  density="comfortable"
                  @click:row="onRowClick"
                >
                  <template v-slot:item.findings="{ item }">
                    <v-chip
                      size="small"
                      :color="item.findings > 0 ? 'error' : 'success'"
                      variant="tonal"
                    >
                      {{ item.findings }}
                    </v-chip>
                  </template>
                  <template v-slot:item.components_count="{ item }">
                    <v-chip
                      size="small"
                      color="primary"
                      variant="tonal"
                    >
                      {{ item.components_count }}
                    </v-chip>
                  </template>
                  <template v-slot:item.updated_at="{ item }">
                    {{ $formatDate(item.updated_at) }}
                  </template>
                  <template v-slot:item.digest="{ item }">
                    <v-tooltip location="top">
                      <template #activator="{ props }">
                        <span v-bind="props" class="digest-shortcut">
                          {{ formatDigest(item.digest) }}
                        </span>
                        <v-icon
                          size="small"
                          class="ml-1 copy-icon"
                          @click.stop="copyDigest(item.digest)"
                          title="Copy digest"
                        >mdi-content-copy</v-icon>
                      </template>
                      <span>{{ item.digest }}</span>
                    </v-tooltip>
                  </template>
                </v-data-table>
              </div>

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
                  @update:model-value="fetchImages"
                  :total-visible="7"
                  density="comfortable"
                />
              </div>
            </v-card-text>
          </v-card>

          <v-card class="wide-card">
            <v-card-text>
              <div class="d-flex align-center justify-space-between mb-4">
                <div class="text-h6">Selected Images: {{ selectedImages.length }}</div>
                <v-btn
                  color="primary"
                  :disabled="selectedImages.length === 0"
                  :loading="generating"
                  @click="generateReport"
                >
                  Generate Report
                </v-btn>
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </v-container>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import api from '../plugins/axios'
import { notificationService } from '../plugins/notifications'
import type { Image, PaginatedResponse } from '../types/interfaces'
import type { DataTableSortItem } from 'vuetify'

const images = ref<Image[]>([])
const selectedImages = ref<Image[]>([])
const loading = ref(false)
const generating = ref(false)
const search = ref('')
const page = ref(1)
const itemsPerPage = ref(10)
const totalItems = ref(0)
const sortBy = ref<DataTableSortItem[]>([{ key: 'updated_at', order: 'desc' }])

const headers: any[] = [
  { title: 'Name', key: 'name', sortable: true },
  { title: 'Digest', key: 'digest', sortable: true },
  { title: 'Findings', key: 'findings', sortable: true },
  { title: 'Components', key: 'components_count', sortable: true },
  { title: 'Updated', key: 'updated_at', sortable: true }
]

const pageCount = computed(() => Math.ceil(totalItems.value / itemsPerPage.value) || 1)

const fetchImages = async () => {
  loading.value = true
  try {
    const params: any = {
      page: Number(page.value),
      page_size: Number(itemsPerPage.value),
    }
    if (search.value) params.search = search.value
    if (sortBy.value && sortBy.value.length > 0) {
      params.ordering = sortBy.value.map(s => s.order === 'desc' ? `-${s.key}` : s.key).join(',')
    }
    const response = await api.get<PaginatedResponse<Image>>('images/', { params })
    images.value = response.data.results
    totalItems.value = Number(response.data.count)
  } catch (error) {
    notificationService.error('Failed to fetch images')
  } finally {
    loading.value = false
  }
}

const onItemsPerPageChange = (val: number) => {
  itemsPerPage.value = val
  page.value = 1
  fetchImages()
}

const generateReport = async () => {
  if (selectedImages.value.length === 0) return

  generating.value = true
  try {
    const response = await api.post('reports/generate/', {
      image_uuids: selectedImages.value
    }, {
      responseType: 'blob'
    })

    // Get filename from Content-Disposition header
    const contentDisposition = response.headers['content-disposition']
    let filename = 'vulnerability_report.xlsx'
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename="(.+)"/)
      if (filenameMatch) {
        filename = filenameMatch[1]
      }
    }

    // Create a download link for the file
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', filename)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)

    notificationService.success('Report generated successfully')
  } catch (error) {
    notificationService.error('Failed to generate report')
  } finally {
    generating.value = false
  }
}

const formatDigest = (digest: string) => {
  if (!digest) return ''
  if (digest.length <= 20) return digest
  return digest.slice(0, 10) + '...' + digest.slice(-6)
}

const copyDigest = (digest: string) => {
  if (!digest) return
  navigator.clipboard.writeText(digest)
    .then(() => notificationService.success('Digest copied!'))
    .catch(() => notificationService.error('Failed to copy digest'))
}

// Debounce helper
function debounce(fn: Function, delay: number) {
  let timeout: ReturnType<typeof setTimeout> | null = null
  return (...args: any[]) => {
    if (timeout) clearTimeout(timeout)
    timeout = setTimeout(() => fn(...args), delay)
  }
}

const debouncedFetchImages = debounce(fetchImages, 300)

watch([search, sortBy], () => {
  page.value = 1
  debouncedFetchImages()
})

const onRowClick = (event: MouseEvent, { item }: { item: any }) => {
  const idx = selectedImages.value.indexOf(item.uuid)
  if (idx === -1) {
    selectedImages.value.push(item.uuid)
  } else {
    selectedImages.value.splice(idx, 1)
  }
}

onMounted(() => {
  fetchImages()
})
</script>

<style scoped>
.report-generator {
  padding: 20px;
}

.wide-card {
  width: 100%;
  max-width: 100%;
  min-width: 900px;
  box-sizing: border-box;
}

.table-scroll {
  width: 100%;
  overflow-x: auto;
}

:deep(.v-table) {
  background: transparent;
}

:deep(.v-table .v-table__wrapper > table) {
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 8px;
  min-width: 900px;
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
  background-color: #f5f5f5;
}

@media (max-width: 1200px) {
  .wide-card {
    min-width: 0;
  }
  :deep(.v-table .v-table__wrapper > table) {
    min-width: 700px;
  }
}

@media (max-width: 900px) {
  .wide-card {
    min-width: 0;
  }
  :deep(.v-table .v-table__wrapper > table) {
    min-width: 500px;
  }
}

.digest-shortcut {
  font-family: monospace;
  cursor: pointer;
  user-select: all;
  color: rgba(60, 60, 60, 0.55);
}
.copy-icon {
  cursor: pointer;
  vertical-align: middle;
}
</style> 