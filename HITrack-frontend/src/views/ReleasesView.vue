<template>
  <v-container fluid class="releases-page">
    <v-row>
      <v-col cols="12">
        <div class="d-flex justify-space-between align-center mb-6">
          <div>
            <h1 class="text-h4 font-weight-bold mb-2">Release Management</h1>
            <p class="text-body-1 text-medium-emphasis">Manage product releases and repository tag assignments</p>
          </div>
          <v-btn
            color="primary"
            prepend-icon="mdi-plus"
            @click="openCreateDialog"
          >
            Create Release
          </v-btn>
        </div>
      </v-col>
    </v-row>

    <!-- Releases Grid -->
    <v-row>
      <v-col cols="12">
        <v-card elevation="2">
          <v-card-title class="d-flex justify-space-between align-center pa-4">
            <span class="text-h6">Releases</span>
            <v-text-field
              v-model="search"
              prepend-inner-icon="mdi-magnify"
              label="Search releases"
              single-line
              hide-details
              density="compact"
              style="max-width: 300px"
            />
          </v-card-title>
          
          <v-card-text class="pa-0">
            <v-data-table
              :headers="headers"
              :items="filteredReleases"
              :loading="loading"
              :search="search"
              class="elevation-0"
              item-value="uuid"
            >
              <template #item.name="{ item }">
                <div class="d-flex align-center">
                  <v-icon color="primary" class="mr-2">mdi-tag</v-icon>
                  <span class="font-weight-medium">{{ item.name }}</span>
                </div>
              </template>

              <template #item.description="{ item }">
                <span class="text-body-2">{{ item.description || 'No description' }}</span>
              </template>

              <template #item.tag_count="{ item }">
                <v-chip
                  :color="item.tag_count > 0 ? 'success' : 'grey'"
                  size="small"
                  variant="tonal"
                >
                  {{ item.tag_count }} tags
                </v-chip>
              </template>

              <template #item.critical_vulnerabilities="{ item }">
                <v-chip
                  :color="item.critical_vulnerabilities > 0 ? 'error' : 'success'"
                  size="small"
                  variant="tonal"
                >
                  {{ item.critical_vulnerabilities }} critical
                </v-chip>
              </template>

              <template #item.high_vulnerabilities="{ item }">
                <v-chip
                  :color="item.high_vulnerabilities > 0 ? 'warning' : 'success'"
                  size="small"
                  variant="tonal"
                >
                  {{ item.high_vulnerabilities }} high
                </v-chip>
              </template>

              <template #item.created_at="{ item }">
                <span class="text-body-2">{{ formatDate(item.created_at) }}</span>
              </template>

              <template #item.actions="{ item }">
                <div class="d-flex gap-2">
                  <v-btn
                    icon="mdi-eye"
                    size="small"
                    variant="text"
                    color="primary"
                    @click="viewRelease(item)"
                    title="View details"
                  />
                  <v-btn
                    icon="mdi-pencil"
                    size="small"
                    variant="text"
                    color="info"
                    @click="editRelease(item)"
                    title="Edit release"
                  />
                  <v-btn
                    icon="mdi-delete"
                    size="small"
                    variant="text"
                    color="error"
                    @click="deleteRelease(item)"
                    title="Delete release"
                  />
                </div>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Create/Edit Dialog -->
    <v-dialog v-model="dialog" max-width="600px">
      <v-card>
        <v-card-title class="text-h6 pa-4">
          {{ editingRelease ? 'Edit Release' : 'Create New Release' }}
        </v-card-title>
        
        <v-card-text class="pa-4">
          <v-form ref="form" v-model="formValid">
            <v-text-field
              v-model="releaseForm.name"
              label="Release Name"
              placeholder="e.g., Product A v1.0"
              :rules="[v => !!v || 'Name is required']"
              required
            />
            
            <v-textarea
              v-model="releaseForm.description"
              label="Description"
              placeholder="Describe this release..."
              rows="3"
            />
          </v-form>
        </v-card-text>
        
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn
            color="grey"
            variant="text"
            @click="closeDialog"
          >
            Cancel
          </v-btn>
          <v-btn
            color="primary"
            :loading="saving"
            :disabled="!formValid"
            @click="saveRelease"
          >
            {{ editingRelease ? 'Update' : 'Create' }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Release Details Dialog -->
    <v-dialog v-model="detailsDialog" max-width="800px">
      <v-card>
        <v-card-title class="text-h6 pa-4">
          Release Details: {{ selectedRelease?.name }}
        </v-card-title>
        
        <v-card-text class="pa-4">
          <v-row>
            <v-col cols="12" md="6">
              <h3 class="text-h6 mb-3">Release Information</h3>
              <div class="mb-3">
                <strong>Name:</strong> {{ selectedRelease?.name }}
              </div>
              <div class="mb-3">
                <strong>Description:</strong> {{ selectedRelease?.description || 'No description' }}
              </div>
              <div class="mb-3">
                <strong>Created:</strong> {{ formatDate(selectedRelease?.created_at) }}
              </div>
            </v-col>
            
            <v-col cols="12" md="6">
              <h3 class="text-h6 mb-3">Statistics</h3>
              <div class="mb-3">
                <strong>Repository Tags:</strong> {{ selectedRelease?.tag_count || 0 }}
              </div>
              <div class="mb-3">
                <strong>Critical Vulnerabilities:</strong> {{ selectedRelease?.critical_vulnerabilities || 0 }}
              </div>
              <div class="mb-3">
                <strong>High Vulnerabilities:</strong> {{ selectedRelease?.high_vulnerabilities || 0 }}
              </div>
            </v-col>
          </v-row>
        </v-card-text>
        
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn
            color="primary"
            variant="text"
            @click="detailsDialog = false"
          >
            Close
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete Confirmation Dialog -->
    <v-dialog v-model="deleteDialog" max-width="400px">
      <v-card>
        <v-card-title class="text-h6 pa-4">
          Confirm Delete
        </v-card-title>
        
        <v-card-text class="pa-4">
          Are you sure you want to delete the release "{{ releaseToDelete?.name }}"? 
          This action cannot be undone.
        </v-card-text>
        
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn
            color="grey"
            variant="text"
            @click="deleteDialog = false"
          >
            Cancel
          </v-btn>
          <v-btn
            color="error"
            :loading="deleting"
            @click="confirmDelete"
          >
            Delete
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { notificationService } from '@/plugins/notifications'
import api from '@/plugins/axios'

interface Release {
  uuid: string
  name: string
  description: string
  tag_count: number
  critical_vulnerabilities: number
  high_vulnerabilities: number
  created_at: string
}

const router = useRouter()

// Reactive data
const releases = ref<Release[]>([])
const loading = ref(false)
const saving = ref(false)
const deleting = ref(false)
const search = ref('')
const dialog = ref(false)
const detailsDialog = ref(false)
const deleteDialog = ref(false)
const formValid = ref(false)
const selectedRelease = ref<Release | null>(null)
const releaseToDelete = ref<Release | null>(null)
const editingRelease = ref<Release | null>(null)

const releaseForm = ref({
  name: '',
  description: ''
})

// Table headers
const headers = [
  { title: 'Name', key: 'name', sortable: true },
  { title: 'Description', key: 'description', sortable: false },
  { title: 'Tags', key: 'tag_count', sortable: true },
  { title: 'Critical', key: 'critical_vulnerabilities', sortable: true },
  { title: 'High', key: 'high_vulnerabilities', sortable: true },
  { title: 'Created', key: 'created_at', sortable: true },
  { title: 'Actions', key: 'actions', sortable: false }
]

// Computed
const filteredReleases = computed(() => {
  if (!search.value) return releases.value
  
  const searchLower = search.value.toLowerCase()
  return releases.value.filter(release => 
    release.name.toLowerCase().includes(searchLower) ||
    release.description.toLowerCase().includes(searchLower)
  )
})

// Methods
const fetchReleases = async () => {
  loading.value = true
  try {
    const response = await api.get('/releases/with_stats/')
    releases.value = response.data
  } catch (error) {
    console.error('Error fetching releases:', error)
    notificationService.error('Failed to load releases')
  } finally {
    loading.value = false
  }
}

const openCreateDialog = () => {
  editingRelease.value = null
  releaseForm.value = {
    name: '',
    description: ''
  }
  dialog.value = true
}

const editRelease = (release: Release) => {
  editingRelease.value = release
  releaseForm.value = {
    name: release.name,
    description: release.description
  }
  dialog.value = true
}

const closeDialog = () => {
  dialog.value = false
  editingRelease.value = null
  releaseForm.value = {
    name: '',
    description: ''
  }
}

const saveRelease = async () => {
  if (!formValid.value) return
  
  saving.value = true
  try {
    if (editingRelease.value) {
      await api.put(`/releases/${editingRelease.value.uuid}/`, releaseForm.value)
      notificationService.success('Release updated successfully')
    } else {
      await api.post('/releases/', releaseForm.value)
      notificationService.success('Release created successfully')
    }
    
    closeDialog()
    await fetchReleases()
  } catch (error) {
    console.error('Error saving release:', error)
    notificationService.error('Failed to save release')
  } finally {
    saving.value = false
  }
}

const viewRelease = (release: Release) => {
  selectedRelease.value = release
  detailsDialog.value = true
}

const deleteRelease = (release: Release) => {
  releaseToDelete.value = release
  deleteDialog.value = true
}

const confirmDelete = async () => {
  if (!releaseToDelete.value) return
  
  deleting.value = true
  try {
    await api.delete(`/releases/${releaseToDelete.value.uuid}/`)
    notificationService.success('Release deleted successfully')
    deleteDialog.value = false
    releaseToDelete.value = null
    await fetchReleases()
  } catch (error) {
    console.error('Error deleting release:', error)
    notificationService.error('Failed to delete release')
  } finally {
    deleting.value = false
  }
}

const formatDate = (dateString: string | undefined) => {
  if (!dateString) return ''
  return new Date(dateString).toLocaleDateString()
}

// Lifecycle
onMounted(() => {
  fetchReleases()
})
</script>

<style scoped>
.releases-page {
  padding: 24px;
}

.v-data-table {
  border-radius: 8px;
}

/* Matrix theme override */
.v-theme--matrix .releases-page {
  background: #000 !important;
}

.v-theme--matrix .v-card {
  background: #000 !important;
  border: 1px solid #39FF14 !important;
}

.v-theme--matrix .v-card-title {
  color: #39FF14 !important;
}

.v-theme--matrix .v-card-text {
  color: #39FF14 !important;
}

.v-theme--matrix .text-h4,
.v-theme--matrix .text-h6 {
  color: #39FF14 !important;
}

.v-theme--matrix .text-body-1,
.v-theme--matrix .text-body-2 {
  color: #39FF14 !important;
}
</style> 