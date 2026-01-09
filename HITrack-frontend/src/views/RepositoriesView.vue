<template>
  <div class="repositories">
    <v-container>
      <v-row>
        <v-col cols="12">
          <h1 class="text-h4 mb-4 font-weight-black">Repositories</h1>
          <v-btn color="primary" @click="openDialog('New Repository')" class="mb-4">
            Add Repository
          </v-btn>
        </v-col>
      </v-row>
      <v-row>
        <v-col cols="12" class="d-flex align-center mb-2">
          <v-text-field
            v-model="repositoriesSearch"
            append-inner-icon="mdi-magnify"
            label="Search repositories"
            hide-details
            density="compact"
            class="mr-4"
            style="max-width: 300px;"
            @keyup.enter="fetchRepositories"
            @click:append-inner="fetchRepositories"
          />
          <v-spacer></v-spacer>
          <v-select
            :items="[10, 20, 50, 100]"
            v-model="itemsPerPage"
            label="Items per page"
            style="max-width: 150px"
            hide-details
            density="compact"
            variant="outlined"
          />
        </v-col>
      </v-row>
      <v-row>
        <v-col cols="12">
          <v-data-table
            :headers="headers"
            :items="repositories"
            :loading="loading"
            class="elevation-1"
            hover
            density="comfortable"
            :items-per-page="itemsPerPage"
            :page="page"
            v-model:sort-by="sortBy"
            :server-items-length="totalItems"
            hide-default-footer
            @update:sort-by="sortBy = $event"
          >
            <template #item="{ item }">
              <tr class="clickable-row" @click="onRowClick(item)">
                <td>{{ item.name }}
                  <v-chip
                    size="x-small"
                    :color="getRepositoryTypeColor(item.repository_type)"
                    class="ml-2"
                    variant="tonal"
                    style="font-size: 0.55rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; height: 20px;"
                  >
                    {{ item.repository_type?.toUpperCase() }}
                  </v-chip>
                </td>
                <td>{{ item.url }}</td>
                <td>
                  <v-chip
                    size="small"
                    color="black"
                    variant="tonal"
                    class="tag-count-chip"
                  >
                    {{ item.tag_count }}
                  </v-chip>
                </td>
                <td>{{ $formatDate(item.created_at) }}</td>
                <td>{{ $formatDate(item.updated_at) }}</td>
                <td>
                  <div style="display: flex; flex-direction: row; gap: 8px; justify-content: center; align-items: center;">
                    <v-tooltip :text="getScanTooltip(item)" location="top">
                      <template v-slot:activator="{ props }">
                        <div v-bind="props">
                          <v-btn
                            icon="mdi-refresh"
                            variant="tonal"
                            size="x-small"
                            color="primary"
                            :disabled="isScanDisabled(item)"
                            @click.stop="onScan(item)"
                          />
                        </div>
                      </template>
                    </v-tooltip>
                    <v-tooltip text="Edit repository" location="top">
                      <template v-slot:activator="{ props }">
                        <div v-bind="props">
                          <v-btn
                            icon="mdi-pencil"
                            variant="tonal"
                            size="x-small"
                            color="secondary"
                            @click.stop="onEdit(item)"
                          />
                        </div>
                      </template>
                    </v-tooltip>
                    <v-tooltip text="Delete repository" location="top">
                      <template v-slot:activator="{ props }">
                        <div v-bind="props">
                          <v-btn
                            icon="mdi-delete"
                            variant="tonal"
                            size="x-small"
                            color="red"
                            @click.stop="onDelete(item)"
                          />
                        </div>
                      </template>
                    </v-tooltip>
                  </div>
                </td>
              </tr>
            </template>
          </v-data-table>
        </v-col>
      </v-row>

      <v-row>
        <v-col cols="12" class="d-flex align-center justify-end mt-2 gap-4">
          <div class="d-flex align-center gap-4">
            <span class="text-body-2">Items per page:</span>
            <v-select
              :items="[10, 20, 50, 100]"
              v-model="itemsPerPage"
              density="compact"
              variant="outlined"
              hide-details
              style="width: 80px"
              @update:model-value="onItemsPerPageChange"
            />
            <span class="text-body-2">
              {{ ((page - 1) * itemsPerPage) + 1 }}-{{ Math.min(page * itemsPerPage, totalItems) }} of {{ totalItems }}
            </span>
          </div>
          <v-pagination
            v-model="page"
            :length="Math.ceil(totalItems / itemsPerPage) || 1"
            :total-visible="7"
            density="comfortable"
            @update:model-value="onPageChange"
          />
        </v-col>
      </v-row>

      <v-dialog v-model="dialog" max-width="500px">
        <v-card :title="formTitle">
          <v-card-text>
              <v-row dense>
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
                    v-model="editedItem.url"
                    label="URL"
                    variant="outlined"
                    :rules="[rules.required, rules.url]"
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
        <v-card title="Delete Repository">
          <v-card-text>Are you sure you want to delete <b>{{ itemToDelete?.name }}</b> repository?</v-card-text>
          <v-card-actions>
            <v-spacer></v-spacer>
            <v-btn color="red-darken-1" variant="text" @click="closeDelete">Cancel</v-btn>
            <v-btn variant="text" @click="deleteItem" :loading="deleting">Delete</v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>
    </v-container>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch, onUnmounted } from 'vue'
import api from '../plugins/axios'
import { notificationService } from '../plugins/notifications'
import type { Repository, PaginatedResponse } from '../types/interfaces'
import { useRouter } from 'vue-router'

interface SortItem { key: string; order: 'asc' | 'desc' }

const router = useRouter()
const repositories = ref<Repository[]>([])
const loading = ref(false)
const page = ref(1)
const itemsPerPage = ref(25)
const totalItems = ref(0)
const sortBy = ref<SortItem[]>([{ key: 'name', order: 'asc' }])
const repositoriesSearch = ref('')
const saving = ref(false)
const deleting = ref(false)
const dialog = ref(false)
const dialogDelete = ref(false)
const defaultItem = {
  id: undefined,
  uuid: '',
  name: '',
  url: '',
  tag_count: 0,
  repository_type: 'docker' as const,
  scan_status: 'none' as const,
  created_at: '',
  updated_at: ''
}
const editedItem = ref<Repository>({...defaultItem})
const itemToDelete = ref<Repository | null>(null)

const headers: any[] = [
  { title: 'Name', key: 'name', sortable: true },
  { title: 'URL', key: 'url', sortable: true },
  { title: 'Tags', key: 'tag_count', align: 'center', sortable: true },
  { title: 'Created', key: 'created_at', sortable: true },
  { title: 'Updated', key: 'updated_at', sortable: true },
  { title: 'Actions', key: 'actions', sortable: false }
]

const rules = {
  required: (v: string) => !!v || 'This field is required',
  url: (v: string) => {
    try {
      new URL(v)
      return true
    } catch {
      return 'Please enter a valid URL'
    }
  }
}

const formTitle = ref('New Repository')

const fetchRepositories = async () => {
  loading.value = true
  try {
    const params: any = {
      page: page.value,
      page_size: itemsPerPage.value
    }
    if (repositoriesSearch.value) params.search = repositoriesSearch.value
    if (sortBy.value.length > 0) {
      params.ordering = sortBy.value.map(s => s.order === 'desc' ? `-${s.key}` : s.key).join(',')
    }
    const response = await api.get<PaginatedResponse<Repository>>('repositories/', { params })
    repositories.value = response.data.results
    totalItems.value = response.data.count
  } catch (error) {
    console.error('Error fetching repositories:', error)
    notificationService.error('Failed to fetch repositories')
  } finally {
    loading.value = false
  }
}

// Debounced fetch function to prevent multiple rapid requests
let fetchTimeout: number | null = null
let isInitialized = false

const debouncedFetchRepositories = () => {
  if (!isInitialized) return // Skip during initialization
  
  if (fetchTimeout) {
    clearTimeout(fetchTimeout)
  }
  fetchTimeout = setTimeout(() => {
    fetchRepositories()
  }, 100)
}

// Watch for changes and use debounced fetch
watch([page, itemsPerPage, repositoriesSearch, sortBy], debouncedFetchRepositories, { flush: 'post' })

const onPageChange = (newPage: number) => {
  page.value = newPage
}

const onItemsPerPageChange = (newItemsPerPage: number) => {
  itemsPerPage.value = newItemsPerPage
  page.value = 1 // Reset to first page when changing items per page
}

const openDialog = (title: string, item?: Repository) => {
  formTitle.value = title
  if (item) {
    editedItem.value = {
      id: item.id,
      uuid: item.uuid,
      name: item.name,
      url: item.url,
      tag_count: item.tag_count,
      repository_type: item.repository_type,
      scan_status: item.scan_status,
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
      url: editedItem.value.url
    }
    
    if (editedItem.value.uuid) {
      await api.put(`repositories/${editedItem.value.uuid}/`, data)
      notificationService.success('Repository updated successfully')
    } else {
      await api.post('repositories/', data)
      notificationService.success('Repository created successfully')
    }
    await fetchRepositories()
    closeDialog()
  } catch (error) {
    console.error('Error saving repository:', error)
    notificationService.error('Failed to save repository')
  } finally {
    saving.value = false
  }
}

const confirmDelete = (item: Repository) => {
  if (!item.uuid) {
    notificationService.error('Cannot delete repository: missing UUID')
    return
  }
  itemToDelete.value = item
  dialogDelete.value = true
}

const deleteItem = async () => {  
  if (!itemToDelete.value || !itemToDelete.value.uuid) {
    notificationService.error('Cannot delete repository: missing UUID')
    return
  }
  deleting.value = true
  try {
    await api.delete(`repositories/${itemToDelete.value.uuid}/`)
    await fetchRepositories()
    notificationService.info(`Repository: ${itemToDelete.value.name} deleted successfully`)
  } catch (error) {
    console.error('Error deleting repository:', error)
    notificationService.error('Failed to delete repository')
  } finally {
    deleting.value = false
    closeDelete()
  }
}

const closeDelete = () => {
  dialogDelete.value = false
  itemToDelete.value = null
}

const onEdit = (repo: Repository) => {
  openDialog('Edit Repository', repo);
};
const onDelete = (repo: Repository) => {
  confirmDelete(repo);
};

const getRepositoryTypeColor = (type: string | undefined) => {
  if (!type) return 'grey'
  const colors: { [key: string]: string } = {
    'docker': 'blue',
    'helm': 'red'
  }
  return colors[type.toLowerCase()] || 'grey'
}

const onRowClick = (repo: any) => {
  router.push(`/repositories/${repo.uuid}`)
}

const getScanStatusTooltip = (status: string) => {
  const statusMap: { [key: string]: string } = {
    'pending': 'Scan pending',
    'in_process': 'Scan in progress',
    'success': 'Scan completed',
    'error': 'Scan failed',
    'none': 'Start scan'
  }
  return statusMap[status] || 'Start scan'
}

const isScanDisabled = (repo: Repository) => {
  return repo.scan_status === 'in_process'
}

const getScanTooltip = (repo: Repository) => {
  if (repo.scan_status === 'in_process') {
    return 'Repository is already being scanned'
  }
  return 'Scan repository'
}

const onScan = async (repo: Repository) => {
  if (!repo.uuid) {
    notificationService.error('Cannot scan repository: missing UUID')
    return
  }
  if (isScanDisabled(repo)) {
    notificationService.warning(getScanTooltip(repo))
    return
  }
  try {
    await api.post(`repositories/${repo.uuid}/scan_tags/`)
    notificationService.success('Repository scan started successfully')
    await fetchRepositories()
  } catch (error: any) {
    if (error.response?.status === 409) {
      notificationService.warning(error.response.data.error || 'Repository is already being scanned')
    } else {
      console.error('Error starting repository scan:', error)
      notificationService.error('Failed to start repository scan')
    }
  }
}

onMounted(() => {
  fetchRepositories()
  isInitialized = true
})

onUnmounted(() => {
  if (fetchTimeout) {
    clearTimeout(fetchTimeout)
  }
})
</script>

<style scoped>
.repositories {
  padding: 20px;
  background: #ffffff;
  min-height: 100vh;
}


:deep(.v-table) {
  background: transparent;
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

:deep(.v-table .v-table__wrapper > table) {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  overflow: hidden;
}

.tag-count-chip {
  font-size: 1rem !important;
  font-weight: 700;
  justify-content: center;
  align-items: center;
  text-align: center;
  min-width: 40px;
}

.v-theme--matrix :deep(.v-table .v-table__wrapper > table > thead > tr > th) {
  background: #011 !important;
  color: #39FF14 !important;
  border: 1px solid #39FF14 !important;
}
</style> 