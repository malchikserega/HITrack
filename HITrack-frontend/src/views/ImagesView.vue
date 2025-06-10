<template>
  <div class="images">
    <v-container>
      <v-row>
        <v-col cols="12">
          <h1 class="text-h4 mb-4 font-weight-black">Images</h1>
          <v-btn color="primary" @click="openDialog('New Image')" class="mb-4">
            Add Image
          </v-btn>
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
              :page="page"
              :items-per-page="itemsPerPage"
              :server-items-length="totalItems"
              :options.sync="tableOptions"
              :sort-by.sync="sortBy"
              @update:options="onOptionsUpdate"
            >
              <template #item="{ item }">
                <tr class="clickable-row">
                  <td @click="onRowClick(item)">
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
                    <span class="nowrap">{{ $formatDate(item.updated_at) }}</span>
                  </td>
                  <td>
                    <v-tooltip location="top">
                      <template #activator="{ props }">
                        <v-icon small class="mr-2" color="secondary" v-bind="props" @click.stop="onEdit(item)">mdi-pencil</v-icon>
                      </template>
                      <span>Edit image</span>
                    </v-tooltip>
                    <v-tooltip location="top">
                      <template #activator="{ props }">
                        <v-icon
                          small
                          class="mr-2"
                          color="primary"
                          v-bind="props"
                          :disabled="item.scan_status === 'in_process'"
                          @click.stop="item.scan_status !== 'in_process' && onRescan(item)"
                          :style="{ cursor: item.scan_status === 'in_process' ? 'not-allowed' : 'pointer', opacity: item.scan_status === 'in_process' ? 0.5 : 1 }"
                        >mdi-refresh</v-icon>
                      </template>
                      <span v-if="item.scan_status === 'in_process'">Scan in process</span>
                      <span v-else>Rescan image</span>
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
            </v-data-table>
          </div>
        </v-col>
      </v-row>

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
                  label="Digest"
                  variant="outlined"
                  :rules="[rules.required]"
                ></v-text-field>
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
import { ref, onMounted, computed, watch } from 'vue'
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
const search = ref('')
const page = ref(1)
const itemsPerPage = ref(10)
const totalItems = ref(0)
const sortBy = ref<DataTableSortItem[]>([{ key: 'updated_at', order: 'desc' }])
const tableOptions = ref({})
const editedItem = ref<Image>({
  id: undefined,
  uuid: '',
  name: '',
  digest: '',
  scan_status: '',
  has_sbom: false,
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
  created_at: '',
  updated_at: ''
})
const itemToDelete = ref<Image | null>(null)
const formTitle = ref('New Image')
const showUniqueFindings = ref(false)
const router = useRouter()

const defaultItem = {
  id: undefined,
  uuid: '',
  name: '',
  digest: '',
  scan_status: '',
  has_sbom: false,
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
  created_at: '',
  updated_at: ''
}

const headers: any[] = [
  { title: 'Name', key: 'name', sortable: true },
  { title: 'Digest', key: 'digest', sortable: true },
  { title: 'SBOM', key: 'has_sbom', sortable: false },
  { title: 'Findings', key: 'findings', sortable: true },
  { title: 'Components', key: 'components_count', sortable: true },
  { title: 'Updated', key: 'updated_at', sortable: true },
  { title: 'Actions', key: 'actions', sortable: false }
]

const rules = {
  required: (v: any) => !!v || 'This field is required'
}

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
    const response = await api.get<PaginatedResponse<Image>>('images/', { params })
    images.value = response.data.results
    totalItems.value = response.data.count
  } catch (error) {
    console.error('Error fetching images:', error)
    notificationService.error('Failed to fetch images')
  } finally {
    loading.value = false
  }
}

const onOptionsUpdate = (options: any) => {
  page.value = options.page
  itemsPerPage.value = options.itemsPerPage
  sortBy.value = options.sortBy
  fetchImages()
}

watch([page, itemsPerPage, search, sortBy], fetchImages)

const openDialog = (title: string, item?: Image) => {
  formTitle.value = title
  if (item) {
    editedItem.value = {
      id: item.id,
      uuid: item.uuid,
      name: item.name,
      digest: item.digest,
      scan_status: item.scan_status,
      has_sbom: item.has_sbom,
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
  editedItem.value = Object.assign({}, defaultItem)
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
      await api.post('images/', data)
      notificationService.success('Image created successfully')
    }
    await fetchImages()
    closeDialog()
  } catch (error) {
    console.error('Error saving image:', error)
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
    console.error('Error deleting image:', error)
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

const onEdit = (img: Image) => {
  openDialog('Edit Image', img);
};
const onDelete = (img: Image) => {
  console.log('Delete click:', img);
  confirmDelete(img);
};

const onRescan = async (img: Image) => {
  if (!img.uuid) {
    notificationService.error('Cannot rescan image: missing UUID')
    return
  }
  
  try {
    await api.post(`images/${img.uuid}/rescan/`)
    notificationService.success('Image rescan scheduled successfully')
  } catch (error) {
    console.error('Error rescanning image:', error)
    notificationService.error('Failed to rescan image')
  }
};

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

const onRowClick = (item: Image) => {
  if (item.uuid) {
    router.push({ name: 'image-detail', params: { uuid: item.uuid } })
  }
}

onMounted(() => {
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

.clickable-row {
  cursor: pointer;
  transition: background 0.2s;
}
.clickable-row:hover {
  background: #f0f4ff !important;
}
</style> 