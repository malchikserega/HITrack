<template>
  <div class="images">
    <v-container>
      <v-row>
        <v-col cols="12">
          <v-btn variant="text" @click="goBack" class="mb-2">
            <v-icon left>mdi-arrow-left</v-icon>Back
          </v-btn>
          <div class="d-flex align-center">
            <h1 class="text-h4 mb-4 font-weight-black">Images for Tag:</h1>
            <v-chip
              class="ml-4 mb-4"
              color="primary"
              size="large"
              variant="elevated"
            >
              {{ tagName }}
            </v-chip>
          </div>
        </v-col>
      </v-row>
      <v-row class="pa-0 ma-0 mt-0">
        <v-col cols="12" class="pa-0 ma-0">
          <div class="d-flex align-center">
            <span class="mr-2">Show unique findings</span>
            <v-switch
              v-model="showUniqueFindings"
              color="indigo"
              class="switch-compact"
              hide-details
              density="compact"
            ></v-switch>
            <v-spacer></v-spacer>
            <v-text-field
              v-model="search"
              append-inner-icon="mdi-magnify"
              label="Search images"
              hide-details
              density="compact"
              class="ml-4"
              style="max-width: 300px;"
              @keyup.enter="fetchImages"
              @click:append-inner="fetchImages"
            />
          </div>
        </v-col>
      </v-row>
      <v-row>
        <v-col cols="12">
          <div class="images-table-responsive" style="margin-top:-8px !important;padding-top:0 !important;">
            <v-data-table
              :headers="headers"
              :items="images"
              :loading="loading"
              class="elevation-1"
              item-class="clickable-row"
              :items-per-page="itemsPerPage"
              :page="page"
              :sort-by.sync="sortBy"
              hide-default-footer
            >
              <template #item="{ item }">
                <tr class="clickable-row" @click="navigateToImageDetail(item)">
                  <td>
                    <span>{{ item.name }}</span>
                    <v-chip
                      size="x-small"
                      :color="statusColor(item.scan_status)"
                      class="ml-2"
                      variant="tonal"
                      style="font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;"
                    >
                      {{ statusLabel(item.scan_status) }}
                    </v-chip>
                  </td>
                  <td>
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
                  </td>
                  <td>
                    <v-icon :color="item.has_sbom ? 'success' : 'error'">
                      {{ item.has_sbom ? 'mdi-check-circle' : 'mdi-close-circle' }}
                    </v-icon>
                  </td>
                  <td>
                    <v-chip
                      :color="getFindingsColor(showUniqueFindings ? item.unique_findings : item.findings)"
                      size="small"
                      class="font-weight-medium"
                    >
                      {{ showUniqueFindings ? item.unique_findings : item.findings }}
                    </v-chip>
                  </td>
                  <td>
                    {{ item.components_count }}
                  </td>
                  <td>
                    <span class="nowrap">{{ $formatDate(item.updated_at) }}</span>
                  </td>
                  <td>
                    <v-tooltip text="Rescan image">
                      <template v-slot:activator="{ props }">
                        <v-btn
                          v-bind="props"
                          icon="mdi-refresh"
                          variant="tonal"
                          size="x-small"
                          color="primary"
                          :class="{ 'opacity-50': item.scan_status === 'in_process' }"
                          @click.stop="onRescan(item)"
                        />
                      </template>
                    </v-tooltip>
                  </td>
                </tr>
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
import type { Image, PaginatedResponse } from '../types/interfaces'

interface SortItem {
  key: string
  order: 'asc' | 'desc'
}

const route = useRoute()
const router = useRouter()
const tagUuid = computed(() => route.params.uuid as string)
const tagName = ref('')
const images = ref<Image[]>([])
const loading = ref(false)
const search = ref('')
const page = ref(1)
const itemsPerPage = ref(10)
const totalItems = ref(0)
const sortBy = ref<SortItem[]>([{ key: 'updated_at', order: 'desc' }])
const showUniqueFindings = ref(false)

const headers: any[] = [
  { title: 'Name', key: 'name', sortable: true },
  { title: 'Digest', key: 'digest', sortable: true },
  { title: 'SBOM', key: 'has_sbom', sortable: false },
  { title: 'Findings', key: 'findings', sortable: true },
  { title: 'Components', key: 'components_count', sortable: true },
  { title: 'Updated', key: 'updated_at', sortable: true },
  { title: 'Actions', key: 'actions', sortable: false }
]

const pageCount = computed(() => Math.ceil(totalItems.value / itemsPerPage.value) || 1)

const fetchImages = async () => {
  loading.value = true
  try {
    const params: any = {
      page: page.value,
      page_size: itemsPerPage.value,
    }
    if (search.value) params.search = search.value
    if (sortBy.value && sortBy.value.length > 0) {
      params.ordering = sortBy.value.map(s => s.order === 'desc' ? `-${s.key}` : s.key).join(',')
    }
    const response = await api.get<PaginatedResponse<Image>>(`repository-tags/${tagUuid.value}/images/`, { params })
    images.value = response.data.results
    totalItems.value = response.data.count
  } catch (error) {
    notificationService.error('Failed to fetch images for tag')
  } finally {
    loading.value = false
  }
}

const onItemsPerPageChange = (val: number) => {
  itemsPerPage.value = val
  page.value = 1
  fetchImages()
}

watch([search, sortBy], () => {
  page.value = 1
  fetchImages()
})
watch([page, itemsPerPage], fetchImages)

const statusLabel = (status: string) => {
  switch (status) {
    case 'pending': return 'Pending';
    case 'in_process': return 'In Process';
    case 'success': return 'Success';
    case 'error': return 'Error';
    default: return 'None';
  }
}
const statusColor = (status: string) => {
  switch (status) {
    case 'pending': return 'grey';
    case 'in_process': return 'info';
    case 'success': return 'success';
    case 'error': return 'error';
    default: return 'default';
  }
}
const getFindingsColor = (findings: number) => {
  if (findings === 0) return 'success'
  if (findings <= 5) return 'warning'
  return 'error'
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

const onRescan = async (image: Image) => {
  try {
    await api.post(`images/${image.uuid}/rescan/`)
    notificationService.success('Image rescan started successfully')
    await fetchImages()
  } catch (error: any) {
    if (error.response?.status === 409) {
      notificationService.warning(error.response.data.error || 'Image is already being scanned')
    } else {
      notificationService.error('Failed to start image rescan')
    }
  }
}

const goBack = () => router.back()

const navigateToImageDetail = (image: Image) => {
  router.push({ name: 'image-detail', params: { uuid: image.uuid } })
}

const fetchTagName = async () => {
  try {
    const resp = await api.get(`repository-tags/${tagUuid.value}/`)
    tagName.value = resp.data.tag
  } catch (error) {
    tagName.value = ''
  }
}

onMounted(() => {
  fetchTagName()
  fetchImages()
})
</script>

<style scoped>
.images {
  padding: 20px;
}
.images-table-responsive {
  width: 100%;
  overflow-x: auto;
  margin-top: -8px !important;
  padding-top: 0 !important;
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
.switch-compact {
  margin-top: -2px;
}
.switch-compact :deep(.v-switch__track) {
  height: 16px !important;
  width: 32px !important;
}
.switch-compact :deep(.v-switch__thumb) {
  height: 12px !important;
  width: 12px !important;
}
.switch-compact :deep(.v-label) {
  font-size: 0.75rem;
  opacity: 0.7;
}
.clickable-row {
  cursor: pointer;
  transition: background 0.2s;
}
.clickable-row:hover {
  background: #f0f4ff !important;
}
</style> 