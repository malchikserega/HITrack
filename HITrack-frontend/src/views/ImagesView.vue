<template>
  <div class="images">
    <v-container fluid class="page-shell page-shell--wide">
      <v-row>
        <v-col cols="12">
          <h1 class="text-h4 mb-4 font-weight-black">Images</h1>
          <div class="d-flex align-center ga-3 mb-4">
            <v-btn color="primary" @click="openDialog('New Image')">
              Add Image
            </v-btn>
            <v-btn
              variant="outlined"
              color="primary"
              prepend-icon="mdi-compare"
              @click="openImageComparisons"
            >
              Compare By Logical Name
            </v-btn>
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
            <v-data-table-server
              :headers="headers"
              :items="images"
              :items-length="totalItems"
              :loading="loading"
              class="elevation-1"
              item-class="clickable-row"
              :items-per-page="itemsPerPage"
              :page="page"
              v-model:sort-by="sortBy"
              hide-default-footer
              @update:options="onTableOptionsUpdate"
            >
              <template #item="{ item }">
                <tr class="clickable-row">
                  <td @click="onRowClick(item)">
                    <div class="image-name-cell">
                      <div class="image-name-cell__title">
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
                      </div>
                    </div>
                  </td>
                  <td @click="onRowClick(item)">
                    <div v-if="hasLineage(item)" class="lineage-cell">
                      <v-chip
                        size="small"
                        color="teal"
                        variant="tonal"
                        class="lineage-cell__label"
                      >
                        {{ item.lineage_label }}
                      </v-chip>
                      <v-tooltip location="top">
                        <template #activator="{ props }">
                          <v-chip
                            v-bind="props"
                            size="x-small"
                            color="grey-darken-1"
                            variant="outlined"
                            class="mt-1"
                          >
                            {{ lineageSourceLabel(item.lineage_source) }}
                          </v-chip>
                        </template>
                        <span>{{ lineageSourceTooltip(item.lineage_source) }}</span>
                      </v-tooltip>
                      <v-tooltip v-if="item.os_eol_status && item.os_eol_status !== 'unknown'" location="top">
                        <template #activator="{ props }">
                          <v-chip
                            v-bind="props"
                            size="x-small"
                            :color="osEolStatusColor(item.os_eol_status)"
                            variant="tonal"
                            class="mt-1"
                          >
                            {{ osEolStatusLabel(item.os_eol_status) }}
                          </v-chip>
                        </template>
                        <span>{{ osEolStatusTooltip(item) }}</span>
                      </v-tooltip>
                    </div>
                    <span v-else class="text-medium-emphasis text-caption">Unknown</span>
                  </td>
                  <td @click="onRowClick(item)">
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
                  <td @click="onRowClick(item)">
                    <v-icon :color="item.has_sbom ? 'success' : 'error'">
                      {{ item.has_sbom ? 'mdi-check-circle' : 'mdi-close-circle' }}
                    </v-icon>
                  </td>
                  <td @click="onRowClick(item)">
                    <v-chip
                      :color="getFindingsColor(showUniqueFindings ? item.unique_findings : item.findings)"
                      size="small"
                      class="font-weight-medium"
                    >
                      {{ showUniqueFindings ? item.unique_findings : item.findings }}
                    </v-chip>
                  </td>
                  <td @click="onRowClick(item)">
                    {{ item.components_count }}
                  </td>
                  <td @click="onRowClick(item)">
                    <div class="date-meta-cell">
                      <div class="date-meta-cell__primary nowrap">{{ $formatDate(item.updated_at) }}</div>
                      <div class="date-meta-cell__secondary nowrap">
                        Created: {{ $formatDate(item.created_at) }}
                      </div>
                    </div>
                  </td>
                  <td>
                    <v-tooltip location="top">
                      <template #activator="{ props }">
                        <v-icon
                          small
                          class="mr-2"
                          color="primary"
                          v-bind="props"
                          :disabled="isImageScanActive(item)"
                          @click.stop="!isImageScanActive(item) && onRescan(item)"
                          :style="{ cursor: isImageScanActive(item) ? 'not-allowed' : 'pointer', opacity: isImageScanActive(item) ? 0.5 : 1 }"
                        >mdi-refresh</v-icon>
                      </template>
                      <span v-if="item.scan_status === 'in_process'">Scan in process</span>
                      <span v-else-if="item.scan_status === 'pending'">Scan pending</span>
                      <span v-else>Rescan image</span>
                    </v-tooltip>
                    <v-tooltip location="top">
                      <template #activator="{ props }">
                        <v-icon
                          small
                          class="mr-2"
                          color="info"
                          v-bind="props"
                          @click.stop="onUpdateLatestVersions(item)"
                        >mdi-update</v-icon>
                      </template>
                      <span>Update latest versions</span>
                    </v-tooltip>
                    <v-tooltip location="top">
                      <template #activator="{ props }">
                        <v-icon
                          small
                          class="mr-2"
                          color="warning"
                          v-bind="props"
                          :disabled="isImageScanActive(item)"
                          @click.stop="!isImageScanActive(item) && onRescanGrype(item)"
                          :style="{ cursor: isImageScanActive(item) ? 'not-allowed' : 'pointer', opacity: isImageScanActive(item) ? 0.5 : 1 }"
                        >mdi-bug</v-icon>
                      </template>
                      <span v-if="item.scan_status === 'in_process'">Scan in process</span>
                      <span v-else-if="item.scan_status === 'pending'">Scan pending</span>
                      <span v-else>Reanalyze SBOM</span>
                    </v-tooltip>
                    <v-tooltip location="top">
                      <template #activator="{ props }">
                        <v-icon
                          small
                          class="mr-2"
                          color="success"
                          v-bind="props"
                          @click.stop="onViewComponentLocations(item)"
                        >mdi-map-marker</v-icon>
                      </template>
                      <span>View Component Locations</span>
                    </v-tooltip>
                    <v-tooltip location="top">
                      <template #activator="{ props }">
                        <v-icon small color="red" v-bind="props" @click.stop="onDelete(item)">mdi-delete</v-icon>
                      </template>
                      <span>Delete image</span>
                    </v-tooltip>
                  </td>
                </tr>
              </template>
            </v-data-table-server>
          </div>
        </v-col>
      </v-row>

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
          :total-visible="7"
          density="comfortable"
        />
      </div>

      <v-dialog v-model="dialog" max-width="500px">
        <v-card :title="formTitle">

          <v-card-text>
            <v-row>
              <v-col cols="12">
                <v-text-field
                  v-model="editedItem.name"
                  label="Name"
                  variant="outlined"
                  :rules="[rules.required]"
                ></v-text-field>
              </v-col>
              <v-col cols="12">
                <v-text-field
                  v-model="editedItem.digest"
                  label="Digest (optional)"
                  variant="outlined"
                ></v-text-field>
              </v-col>
              <v-col v-if="!editedItem.uuid" cols="12">
                <v-checkbox
                  v-model="scanAfterCreate"
                  color="primary"
                  label="Scan now (local Docker first, registry fallback)"
                  hide-details
                />
                <div class="text-caption text-medium-emphasis mt-1">
                  HITrack will use an image in this machine's Docker daemon before trying to pull it.
                </div>
              </v-col>
            </v-row>
          </v-card-text>

          <v-card-actions>
            <v-spacer></v-spacer>
            <v-btn color="red-darken-1" variant="text" @click="closeDialog">
              Cancel
            </v-btn>
            <v-btn variant="text" @click="save" :loading="saving">
              Save
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>

      <v-dialog v-model="dialogDelete" max-width="500px">
        <v-card title="Delete Image">
          <v-card-text>Are you sure you want to delete <b>{{ itemToDelete?.name }}</b> image? </v-card-text>
          <v-card-actions>
            <v-btn color="red-darken-1" variant="text" @click="closeDelete">Cancel</v-btn>
            <v-btn variant="text" @click="deleteItem" :loading="deleting">Delete</v-btn>
            <v-spacer></v-spacer>
          </v-card-actions>
        </v-card>
      </v-dialog>
    </v-container>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '../plugins/axios'
import { notificationService } from '../plugins/notifications'
import type { Image, PaginatedResponse } from '../types/interfaces'
import type { DataTableSortItem } from 'vuetify'

const images = ref<Image[]>([])
const loading = ref(false)
const saving = ref(false)
const deleting = ref(false)
const dialog = ref(false)
const dialogDelete = ref(false)
const scanAfterCreate = ref(true)
const search = ref('')
const page = ref(1)
const itemsPerPage = ref(10)
const totalItems = ref(0)
const sortBy = ref<DataTableSortItem[]>([{ key: 'updated_at', order: 'desc' }])
const hasActiveImageScans = computed(() =>
  images.value.some(image => ['pending', 'in_process'].includes(image.scan_status || 'none'))
)
const editedItem = ref<Image>({
  id: undefined,
  uuid: '',
  name: '',
  digest: '',
  scan_status: '',
  lineage_label: '',
  lineage_source: '',
  os_distro_name: '',
  os_distro_version: '',
  os_eol_status: 'unknown',
  os_eol_source: 'unknown',
  os_eol_message: '',
  os_eol_checked_at: null,
  has_sbom: false,
  has_grype: false,
  findings: 0,
  unique_findings: 0,
  severity_counts: {},
  components_count: 0,
  fully_fixable_components_count: 0,
  fixable_findings: 0,
  fixable_unique_findings: 0,
  fixable_severity_counts: {},
  unique_severity_counts: {},
  fixable_unique_severity_counts: {},
  fully_fixable_findings: 0,
  fully_fixable_unique_findings: 0,
  fully_fixable_severity_counts: {},
  fully_fixable_unique_severity_counts: {},
  created_at: '',
  updated_at: ''
})
const itemToDelete = ref<Image | null>(null)
const formTitle = ref('New Image')
const showUniqueFindings = ref(false)
const router = useRouter()
let refreshTimer: number | null = null

const normalizeSortBy = (items?: readonly DataTableSortItem[]): DataTableSortItem[] =>
  (items || []).map((item) => {
    const order: 'asc' | 'desc' = item.order === 'desc' ? 'desc' : 'asc'
    return {
      key: String(item.key),
      order,
    }
  })

const areSortByEqual = (left: readonly DataTableSortItem[], right: readonly DataTableSortItem[]) =>
  JSON.stringify(normalizeSortBy(left)) === JSON.stringify(normalizeSortBy(right))

const defaultItem = {
  id: undefined,
  uuid: '',
  name: '',
  digest: '',
  scan_status: '',
  lineage_label: '',
  lineage_source: '',
  os_distro_name: '',
  os_distro_version: '',
  os_eol_status: 'unknown',
  os_eol_source: 'unknown',
  os_eol_message: '',
  os_eol_checked_at: null,
  has_sbom: false,
  has_grype: false,
  findings: 0,
  unique_findings: 0,
  severity_counts: {},
  components_count: 0,
  fully_fixable_components_count: 0,
  fixable_findings: 0,
  fixable_unique_findings: 0,
  fixable_severity_counts: {},
  unique_severity_counts: {},
  fixable_unique_severity_counts: {},
  fully_fixable_findings: 0,
  fully_fixable_unique_findings: 0,
  fully_fixable_severity_counts: {},
  fully_fixable_unique_severity_counts: {},
  created_at: '',
  updated_at: ''
}

const headers: any[] = [
  { title: 'Name', key: 'name', sortable: true },
  { title: 'OS / Distro', key: 'lineage_label', sortable: true, width: '220px' },
  { title: 'Digest', key: 'digest', sortable: true },
  { title: 'SBOM', key: 'has_sbom', sortable: false },
  { title: 'Findings', key: 'findings', sortable: true },
  { title: 'Components', key: 'components_count', sortable: true },
  { title: 'Updated', key: 'updated_at', sortable: true, width: '210px' },
  { title: 'Actions', key: 'actions', sortable: false }
]

const rules = {
  required: (v: any) => !!v || 'This field is required'
}

const fetchImages = async () => {
  loading.value = true
  try {
    const params: any = {
      page: Number(page.value),
      page_size: Number(itemsPerPage.value),
    }
    if (search.value) params.search = search.value
    if (sortBy.value && sortBy.value.length > 0) {
      const [sort] = sortBy.value
      const resolvedKey = sort.key === 'findings'
        ? (showUniqueFindings.value ? 'unique_findings_count' : 'findings_count')
        : String(sort.key)
      params.ordering = `${sort.order === 'desc' ? '-' : ''}${resolvedKey}`
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

const startAutoRefresh = () => {
  if (refreshTimer !== null) return
  refreshTimer = window.setInterval(() => {
    if (!loading.value) {
      fetchImages()
    }
  }, 5000)
}

const stopAutoRefresh = () => {
  if (refreshTimer === null) return
  window.clearInterval(refreshTimer)
  refreshTimer = null
}

const pageCount = computed(() => Math.ceil(totalItems.value / itemsPerPage.value) || 1)

const onItemsPerPageChange = (val: number) => {
  itemsPerPage.value = val
  page.value = 1
}

watch(search, () => {
  if (page.value !== 1) {
    page.value = 1
    return
  }
  fetchImages()
})

watch(sortBy, () => {
  if (page.value !== 1) {
    page.value = 1
    return
  }
  fetchImages()
})
watch(showUniqueFindings, () => {
  if (sortBy.value[0]?.key === 'findings') {
    fetchImages()
  }
})
watch([page, itemsPerPage], fetchImages)
watch(hasActiveImageScans, (isActive) => {
  if (isActive) {
    startAutoRefresh()
  } else {
    stopAutoRefresh()
  }
}, { immediate: true })

const openDialog = (title: string, item?: Image) => {
  formTitle.value = title
  if (item) {
    editedItem.value = {
      id: item.id,
      uuid: item.uuid,
      name: item.name,
      digest: item.digest,
      scan_status: item.scan_status,
      lineage_label: item.lineage_label,
      lineage_source: item.lineage_source,
      os_distro_name: item.os_distro_name,
      os_distro_version: item.os_distro_version,
      os_eol_status: item.os_eol_status,
      os_eol_source: item.os_eol_source,
      os_eol_message: item.os_eol_message,
      os_eol_checked_at: item.os_eol_checked_at,
      has_sbom: item.has_sbom,
      has_grype: item.has_grype,
      findings: item.findings,
      unique_findings: item.unique_findings,
      severity_counts: item.severity_counts,
      components_count: item.components_count,
      fully_fixable_components_count: item.fully_fixable_components_count,
      fixable_findings: item.fixable_findings,
      fixable_unique_findings: item.fixable_unique_findings,
      fixable_severity_counts: item.fixable_severity_counts,
      unique_severity_counts: item.unique_severity_counts,
      fixable_unique_severity_counts: item.fixable_unique_severity_counts,
      fully_fixable_findings: item.fully_fixable_findings,
      fully_fixable_unique_findings: item.fully_fixable_unique_findings,
      fully_fixable_severity_counts: item.fully_fixable_severity_counts,
      fully_fixable_unique_severity_counts: item.fully_fixable_unique_severity_counts,
      created_at: item.created_at,
      updated_at: item.updated_at
    }
  } else {
    editedItem.value = Object.assign({}, defaultItem)
  }
  dialog.value = true
}

const closeDialog = () => {
  dialog.value = false
  scanAfterCreate.value = true
  editedItem.value = Object.assign({}, defaultItem)
}

const onTableOptionsUpdate = (options: { page: number; itemsPerPage: number; sortBy: DataTableSortItem[] }) => {
  const nextSortBy = normalizeSortBy(options.sortBy)
  const currentSortBy = normalizeSortBy(sortBy.value)

  if (
    page.value === options.page &&
    itemsPerPage.value === options.itemsPerPage &&
    JSON.stringify(currentSortBy) === JSON.stringify(nextSortBy)
  ) {
    return
  }

  page.value = options.page
  itemsPerPage.value = options.itemsPerPage
  if (!areSortByEqual(sortBy.value, nextSortBy)) {
    sortBy.value = nextSortBy
  }
}

const save = async () => {
  saving.value = true
  try {
    const data = {
      name: editedItem.value.name,
      digest: editedItem.value.digest
    }
    
    if (editedItem.value.uuid) {
      await api.put(`images/${editedItem.value.uuid}/`, data)
      notificationService.success('Image updated successfully')
    } else {
      const response = await api.post<Image>('images/', data)
      if (scanAfterCreate.value) {
        const scanResponse = await api.post(`images/${response.data.uuid}/rescan/`)
        notificationService.queued(
          scanResponse.data.message || 'Image was created and its scan was queued.'
        )
      } else {
        notificationService.success('Image created successfully')
      }
    }
    await fetchImages()
    closeDialog()
  } catch (error) {
    notificationService.error('Failed to save image')
  } finally {
    saving.value = false
  }
}

const confirmDelete = (item: Image) => {
  if (!item.uuid) {
    notificationService.error('Cannot delete image: missing UUID')
    return
  }
  itemToDelete.value = item
  dialogDelete.value = true
}

const deleteItem = async () => {
  if (!itemToDelete.value?.uuid) {
    notificationService.error('Cannot delete image: missing UUID')
    return
  }
  
  deleting.value = true
  try {
    await api.delete(`images/${itemToDelete.value.uuid}/`)
    await fetchImages()
    notificationService.success('Image deleted successfully')
  } catch (error) {
    notificationService.error('Failed to delete image')
  } finally {
    deleting.value = false
    closeDelete()
  }
}

const closeDelete = () => {
  dialogDelete.value = false
  itemToDelete.value = null
}

const onDelete = (img: Image) => {
  confirmDelete(img);
};

const isImageScanActive = (img: Image) => {
  return ['pending', 'in_process'].includes(img.scan_status)
}

const onRescan = async (img: Image) => {
  if (!img.uuid) {
    notificationService.error('Cannot rescan image: missing UUID')
    return
  }
  if (isImageScanActive(img)) {
    notificationService.conflict('Image is already being scanned or queued for scanning')
    return
  }
  const previousStatus = img.scan_status
  img.scan_status = 'pending'
  try {
    const response = await api.post(`images/${img.uuid}/rescan/`)
    notificationService.queued(response.data.message || 'Image rescan was queued.')
    await fetchImages()
  } catch (error: any) {
    img.scan_status = previousStatus
    if (error.response?.status === 409) {
      notificationService.conflict(error.response.data.error || 'Image is already being scanned or queued for scanning')
      fetchImages()
    } else {
      notificationService.error('Failed to rescan image')
    }
  }
};

const onUpdateLatestVersions = async (item: Image) => {
  try {
    const response = await api.post(`images/${item.uuid}/update_latest_versions/`)
    notificationService.queued(response.data.message || 'Latest version lookup was queued.')
    await fetchImages()
  } catch (error: any) {
    notificationService.error(error.response?.data?.error || 'Failed to update latest versions')
  }
}

const onRescanGrype = async (image: Image) => {
  if (!image.uuid) return
  if (isImageScanActive(image)) {
    notificationService.conflict('Image is already being scanned or queued for scanning')
    return
  }
  const previousStatus = image.scan_status
  image.scan_status = 'pending'
  try {
    const response = await api.post(`images/${image.uuid}/rescan-grype/`)
    notificationService.queued(response.data.message || 'Grype scan was queued.')
    fetchImages()
  } catch (e: any) {
    image.scan_status = previousStatus
    const msg = e?.response?.data?.error || 'Failed to schedule Grype scan'
    if (e?.response?.status === 409) {
      notificationService.conflict(msg)
      fetchImages()
    } else {
      notificationService.error(msg)
    }
  }
}

const onViewComponentLocations = (image: Image) => {
  if (!image.uuid) return
  router.push({ name: 'component-locations', params: { uuid: image.uuid } })
}

const openImageComparisons = () => {
  router.push({ name: 'image-comparisons' })
}

const formatDigest = (digest: string) => {
  if (!digest) return ''
  if (digest.length <= 20) return digest
  return digest.slice(0, 10) + '...' + digest.slice(-6)
}

const copyDigest = (digest: string) => {
  if (!digest) return
  navigator.clipboard.writeText(digest)
    .then(() => notificationService.copied('Digest copied to clipboard.'))
    .catch(() => notificationService.error('Failed to copy digest'))
}

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

const hasLineage = (image: Image) =>
  Boolean(image.lineage_label && image.lineage_label !== 'unknown')

const lineageSourceLabel = (source?: string) => {
  switch (source) {
    case 'sbom_distro':
      return 'SBOM distro'
    case 'package_distro':
      return 'Pkg distro'
    default:
      return 'Unknown'
  }
}

const lineageSourceTooltip = (source?: string) => {
  switch (source) {
    case 'sbom_distro':
      return 'Detected directly from SBOM distro metadata.'
    case 'package_distro':
      return 'Inferred from OS package metadata when SBOM distro was unavailable.'
    default:
      return 'OS lineage could not be determined.'
  }
}

const osEolStatusLabel = (status?: string) => {
  switch (status) {
    case 'eol':
      return 'EOL distro'
    case 'supported':
      return 'Supported'
    default:
      return 'Unknown'
  }
}

const osEolStatusColor = (status?: string) => {
  switch (status) {
    case 'eol':
      return 'error'
    case 'supported':
      return 'success'
    default:
      return 'grey'
  }
}

const osEolStatusTooltip = (image: Image) => {
  if (image.os_eol_status === 'eol') {
    return image.os_eol_message || 'Grype detected packages from an end-of-life distro. Vulnerability coverage may be incomplete.'
  }
  if (image.os_eol_status === 'supported') {
    return 'No distro EOL warning was present in Grype for this tracked OS lineage.'
  }
  return 'OS lifecycle status is currently unknown.'
}

const onRowClick = (item: Image) => {
  if (item.uuid) {
    router.push({ name: 'image-detail', params: { uuid: item.uuid } })
  }
}

onMounted(() => {
  fetchImages()
})

onUnmounted(() => {
  stopAutoRefresh()
})
</script>

<style scoped>
.images {
  padding: 20px;
  background: #ffffff;
  min-height: 100vh;
}


.images-table-responsive {
  width: 100%;
  overflow-x: auto;
  margin-top: -8px !important;
  padding-top: 0 !important;
}

.digest-cell {
  max-width: 320px;
  word-break: break-all;
  white-space: normal;
  display: inline-block;
}

.nowrap {
  white-space: nowrap;
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
  background-color: #f5f5f5;
}

:deep(.v-table .v-table__wrapper > table > thead > tr > th:last-child),
:deep(.v-table .v-table__wrapper > table > tbody > tr > td:last-child) {
  text-align: center;
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

.date-meta-cell {
  line-height: 1.2;
}

.image-name-cell {
  min-width: 260px;
}

.image-name-cell__title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

.lineage-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.lineage-cell__label {
  max-width: 100%;
}

.date-meta-cell__primary {
  font-weight: 500;
}

.date-meta-cell__secondary {
  color: #6b7280;
  font-size: 0.82rem;
  margin-top: 4px;
}

.clickable-row {
  cursor: pointer;
  transition: background 0.2s;
}
.clickable-row:hover {
  background: #f0f4ff !important;
}

.v-theme--matrix :deep(.v-table .v-table__wrapper > table > thead > tr > th) {
  background: #011 !important;
  color: #39FF14 !important;
  border: 1px solid #39FF14 !important;
}
</style> 
