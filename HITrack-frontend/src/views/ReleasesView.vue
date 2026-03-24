<template>
  <v-container fluid class="releases-page page-shell page-shell--wide">
    <v-row>
      <v-col cols="12">
        <div class="d-flex justify-space-between align-center mb-6">
          <div>
            <h1 class="text-h4 font-weight-bold mb-2">Release Management</h1>
            <p class="text-body-1 text-medium-emphasis">Manage product releases and repository tag assignments</p>
          </div>
          <div class="d-flex gap-2">
            <v-btn
              color="secondary"
              prepend-icon="mdi-json"
              @click="openJsonWizard"
            >
              JSON Wizard
            </v-btn>
            <v-btn
              color="primary"
              prepend-icon="mdi-plus"
              @click="openCreateDialog"
            >
              Create Release
            </v-btn>
          </div>
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
              :rules="[
                v => !!v || 'Name is required',
                v => !checkReleaseNameExists(v, editingRelease?.uuid) || 'Release with this name already exists'
              ]"
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
    <v-dialog v-model="detailsDialog" max-width="1280px">
      <v-card>
        <v-card-title class="text-h6 pa-4 d-flex align-center">
          <span>Release Details: {{ selectedRelease?.name }}</span>
          <v-spacer />
          <v-btn
            variant="text"
            color="primary"
            prepend-icon="mdi-refresh"
            :disabled="!selectedRelease"
            @click="refreshSelectedReleaseContents"
          >
            Refresh
          </v-btn>
          <v-btn
            color="primary"
            prepend-icon="mdi-play-circle-outline"
            :loading="releaseScanStarting"
            :disabled="!selectedRelease || releasableScanCount === 0"
            @click="scanUnscannedReleaseTags"
          >
            Scan Unscanned
          </v-btn>
        </v-card-title>
        
        <v-card-text class="pa-4">
          <div v-if="releaseContentsLoading" class="release-details-loading">
            <v-progress-circular indeterminate color="primary" />
          </div>

          <div v-else-if="releaseContents">
            <v-row class="mb-4">
              <v-col cols="12" md="5">
                <h3 class="text-h6 mb-3">Release Information</h3>
                <div class="mb-3">
                  <strong>Name:</strong> {{ releaseContents.release.name }}
                </div>
                <div class="mb-3">
                  <strong>Description:</strong> {{ releaseContents.release.description || 'No description' }}
                </div>
                <div class="mb-3">
                  <strong>Created:</strong> {{ formatDate(releaseContents.release.created_at) }}
                </div>
                <div class="mb-3">
                  <strong>Repository Tags:</strong> {{ releaseSummary.total_tags }}
                </div>
              </v-col>

              <v-col cols="12" md="7">
                <h3 class="text-h6 mb-3">Scan Summary</h3>
                <div class="release-summary-grid">
                  <v-chip color="success" variant="tonal">Scanned: {{ releaseSummary.success_tags }}</v-chip>
                  <v-chip color="info" variant="tonal">Queued: {{ releaseSummary.pending_tags }}</v-chip>
                  <v-chip color="warning" variant="tonal">Processing: {{ releaseSummary.in_process_tags }}</v-chip>
                  <v-chip color="error" variant="tonal">Error: {{ releaseSummary.error_tags }}</v-chip>
                  <v-chip color="grey" variant="tonal">Not Scanned: {{ releaseSummary.unscanned_tags }}</v-chip>
                  <v-chip color="primary" variant="tonal">Images: {{ releaseSummary.total_images }}</v-chip>
                </div>

                <v-alert
                  :type="releaseSummary.all_tags_scanned ? 'success' : 'warning'"
                  variant="tonal"
                  class="mt-4"
                >
                  <template v-if="releaseSummary.all_tags_scanned">
                    All tags included in this release are fully scanned.
                  </template>
                  <template v-else>
                    This release still has {{ incompleteReleaseTagCount }} tag(s) that are not fully scanned yet.
                  </template>
                </v-alert>
              </v-col>
            </v-row>

            <v-data-table
              :headers="releaseTagHeaders"
              :items="releaseTags"
              item-value="uuid"
              density="comfortable"
              class="elevation-1"
            >
              <template #item.repository="{ item }">
                <div class="release-tag-repository">
                  <div class="font-weight-medium">{{ item.repository.name }}</div>
                  <div class="text-caption text-medium-emphasis">{{ item.repository.repository_type }}</div>
                </div>
              </template>

              <template #item.tag="{ item }">
                <div class="release-tag-name">
                  <v-chip size="small" color="primary" variant="tonal">{{ item.tag }}</v-chip>
                  <span v-if="item.image_path" class="text-caption text-medium-emphasis">{{ item.image_path }}</span>
                </div>
              </template>

              <template #item.image_names="{ item }">
                <div class="release-image-cell">
                  <div v-if="item.image_names.length" class="release-image-chips">
                    <v-chip
                      v-for="imageName in getReleaseImagePreview(item)"
                      :key="imageName"
                      size="x-small"
                      variant="outlined"
                    >
                      {{ imageName }}
                    </v-chip>
                    <v-chip
                      v-if="getHiddenReleaseImageCount(item) > 0"
                      size="x-small"
                      color="primary"
                      variant="tonal"
                    >
                      +{{ getHiddenReleaseImageCount(item) }} more
                    </v-chip>
                  </div>
                  <span v-else class="text-caption text-medium-emphasis">No linked images</span>
                </div>
              </template>

              <template #item.processing_status="{ item }">
                <v-chip
                  :color="getReleaseScanStatusColor(item.processing_status)"
                  size="small"
                  variant="tonal"
                >
                  {{ formatReleaseScanStatus(item.processing_status) }}
                </v-chip>
              </template>

              <template #item.scan_progress="{ item }">
                <span class="text-body-2">{{ formatReleaseTagScanProgress(item) }}</span>
              </template>

              <template #item.findings="{ item }">
                <v-chip size="small" color="error" variant="tonal">
                  {{ item.findings }}
                </v-chip>
              </template>

              <template #item.components="{ item }">
                <v-chip size="small" color="info" variant="tonal">
                  {{ item.components }}
                </v-chip>
              </template>

              <template #item.updated_at="{ item }">
                <span class="text-body-2">{{ formatDate(item.updated_at) }}</span>
              </template>

              <template #item.actions="{ item }">
                <v-btn
                  size="small"
                  variant="text"
                  color="primary"
                  prepend-icon="mdi-open-in-new"
                  @click="openReleaseTagImages(item)"
                >
                  Open Tag
                </v-btn>
              </template>
            </v-data-table>
          </div>
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

    <!-- JSON Wizard Dialog -->
    <v-dialog v-model="jsonWizardDialog" max-width="1400px" persistent>
      <v-card>
        <v-card-title class="text-h6 pa-4 d-flex align-center">
          <v-icon class="mr-2" color="secondary">mdi-json</v-icon>
          JSON Helm Releases Wizard
        </v-card-title>
        
        <v-card-text class="pa-4">
          <v-row>
            <v-col cols="12" md="6">
              <v-textarea
                v-model="jsonInput"
                label="Paste JSON Data"
                placeholder="Paste your Helm releases JSON here..."
                rows="15"
                variant="outlined"
                :error="jsonError"
                :error-messages="jsonErrorMessage"
                @input="parseJsonOnInput"
                style="overflow-y: auto;"
              />
              <div class="d-flex gap-2 mt-4">
                <v-tooltip location="top">
                  <template v-slot:activator="{ props }">
                    <v-btn
                      icon="mdi-help-circle"
                      size="small"
                      variant="text"
                      color="info"
                      v-bind="props"
                    />
                  </template>
                  <div class="pa-2">
                    <div class="text-body-2 font-weight-bold mb-2">JSON Structure Example:</div>
                    <pre class="text-caption" style="white-space: pre-wrap; max-width: 300px;">[
  {
    "name": "repository-name",
    "namespace": "namespace",
    "revision": "123",
    "updated": "2025-01-01 10:00:00",
    "status": "deployed",
    "chart": "chart-name",
    "app_version": "1.0.0"
  }
]</pre>
                  </div>
                </v-tooltip>
                <v-btn
                  color="primary"
                  @click="checkRepositories"
                  :loading="checking"
                  :disabled="parsedData.length === 0"
                >
                  Check Repositories
                </v-btn>
                <v-btn
                  v-if="hasFoundTags"
                  color="success"
                  @click="showReleaseCreationStep"
                  :disabled="!hasFoundTags"
                >
                  Create Release
                </v-btn>
                <v-btn
                  color="grey"
                  variant="text"
                  @click="clearJson"
                >
                  Clear
                </v-btn>
              </div>
            </v-col>
            
            <v-col cols="12" md="6">
              <div v-if="parsedData.length > 0">
                <h3 class="text-h6 mb-3">Parsed Data Preview</h3>
                <v-data-table
                  :headers="jsonTableHeaders"
                  :items="parsedData"
                  :items-per-page="-1"
                  class="elevation-1"
                  density="compact"
                  hide-default-footer
                >
                  <template #item.helm_tag="{ item }">
                    <v-chip
                      color="primary"
                      size="small"
                      variant="tonal"
                    >
                      {{ item.helm_tag }}
                    </v-chip>
                  </template>
                  <template #item.app_version="{ item }">
                    <v-chip
                      color="secondary"
                      size="small"
                      variant="tonal"
                    >
                      {{ item.app_version }}
                    </v-chip>
                  </template>
                  <template #item.repository_status="{ item }">
                    <v-chip
                      :color="getStatusColor(item.repository_status)"
                      size="small"
                      variant="tonal"
                    >
                      {{ item.repository_status || 'Not checked' }}
                    </v-chip>
                  </template>
                  <template #item.tag_status="{ item }">
                    <div class="d-flex align-center">
                      <v-chip
                        :color="getStatusColor(item.tag_status)"
                        size="small"
                        variant="tonal"
                      >
                        {{ item.tag_status || 'Not checked' }}
                      </v-chip>
                      <v-btn
                        v-if="item.repository_status === 'Found' && item.tag_status === 'Not Found'"
                        icon="mdi-plus"
                        size="x-small"
                        color="primary"
                        variant="text"
                        class="ml-2"
                        @click="addTagToRepository(item)"
                        :loading="addingTag === item.helm_tag"
                        title="Add tag to repository"
                      />
                    </div>
                  </template>
                </v-data-table>
                <div class="mt-3">
                  <v-chip color="info" size="small">
                    Total items: {{ parsedData.length }}
                  </v-chip>
                </div>
              </div>
              <div v-else class="text-center pa-8">
                <v-icon size="48" color="grey">mdi-table</v-icon>
                <p class="text-body-2 text-medium-emphasis mt-2">Parsed data will appear here</p>
              </div>
            </v-col>
          </v-row>
        </v-card-text>
        
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn
            color="grey"
            variant="text"
            @click="closeJsonWizard"
          >
            Close
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Release Creation Step Dialog -->
    <v-dialog
      v-model="showReleaseStep"
      max-width="800px"
      persistent
    >
      <v-card>
        <v-card-title class="d-flex justify-space-between align-center pa-4">
          <span class="text-h6">Create Release from Found Tags</span>
          <v-btn
            icon="mdi-close"
            variant="text"
            @click="showReleaseStep = false"
          />
        </v-card-title>
        
        <v-card-text class="pa-4">
          <v-row>
            <v-col cols="12">
              <v-text-field
                v-model="releaseName"
                label="Release Name"
                required
                :rules="[
                  v => !!v || 'Release name is required',
                  v => !checkReleaseNameExists(v) || 'Release with this name already exists'
                ]"
                variant="outlined"
                density="compact"
              />
            </v-col>
            
            <v-col cols="12">
              <v-textarea
                v-model="releaseDescription"
                label="Release Description (optional)"
                variant="outlined"
                density="compact"
                rows="3"
                auto-grow
              />
            </v-col>
            
            <v-col cols="12">
              <div class="d-flex align-center mb-3">
                <h4 class="text-h6 mr-2">Selected Tags ({{ selectedTagsForRelease.length }})</h4>
                <v-chip color="success" size="small">
                  All Found
                </v-chip>
              </div>
              
              <v-data-table
                :headers="[
                  { title: 'Repository', key: 'name' },
                  { title: 'Tag', key: 'app_version' },
                  { title: 'Helm Tag', key: 'helm_tag' }
                ]"
                :items="selectedTagsForRelease"
                :items-per-page="-1"
                class="elevation-1"
                density="compact"
                hide-default-footer
              >
                <template #item.name="{ item }">
                  <v-chip
                    color="primary"
                    size="small"
                    variant="tonal"
                  >
                    {{ item.name }}
                  </v-chip>
                </template>
                <template #item.app_version="{ item }">
                  <v-chip
                    color="secondary"
                    size="small"
                    variant="tonal"
                  >
                    {{ item.app_version }}
                  </v-chip>
                </template>
                <template #item.helm_tag="{ item }">
                  <v-chip
                    color="info"
                    size="small"
                    variant="tonal"
                  >
                    {{ item.helm_tag }}
                  </v-chip>
                </template>
              </v-data-table>
            </v-col>
          </v-row>
        </v-card-text>
        
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn
            color="grey"
            variant="text"
            @click="showReleaseStep = false"
          >
            Cancel
          </v-btn>
          <v-btn
            color="success"
            @click="createReleaseWithTags"
            :loading="creatingRelease"
            :disabled="!releaseName.trim() || checkReleaseNameExists(releaseName)"
          >
            Create Release
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
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

interface ReleaseTagItem {
  uuid: string
  tag: string
  image_path: string
  processing_status: string
  findings: number
  components: number
  vulnerabilities_count: number
  total_images: number
  success_images: number
  pending_images: number
  in_process_images: number
  error_images: number
  image_names: string[]
  created_at: string
  updated_at: string
  repository: {
    uuid: string
    name: string
    url: string
    repository_type: string
  }
}

interface ReleaseContentsSummary {
  total_tags: number
  success_tags: number
  pending_tags: number
  in_process_tags: number
  error_tags: number
  unscanned_tags: number
  total_images: number
  success_images: number
  pending_images: number
  in_process_images: number
  error_images: number
  all_tags_scanned: boolean
}

interface ReleaseContentsResponse {
  release: {
    uuid: string
    name: string
    description: string
    created_at: string
  }
  summary: ReleaseContentsSummary
  tags: ReleaseTagItem[]
}

const router = useRouter()

// Reactive data
const releases = ref<Release[]>([])
const releaseNames = ref<{uuid: string, name: string}[]>([])
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
const releaseContents = ref<ReleaseContentsResponse | null>(null)
const releaseContentsLoading = ref(false)
const releaseScanStarting = ref(false)
const releasePollingTimer = ref<number | undefined>(undefined)

// JSON Wizard variables
const jsonWizardDialog = ref(false)
const jsonInput = ref('')
const jsonError = ref(false)
const jsonErrorMessage = ref('')
const parsing = ref(false)
const parsedData = ref<any[]>([])
const parseTimeout = ref<number | undefined>(undefined)
const checking = ref(false)
const addingTag = ref<string | null>(null)

// Release creation step variables
const showReleaseStep = ref(false)
const creatingRelease = ref(false)
const releaseName = ref('')
const releaseDescription = ref('')
const selectedTagsForRelease = ref<any[]>([])
const releaseFormValid = ref(false)

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

const releaseTagHeaders = [
  { title: 'Repository', key: 'repository', sortable: false },
  { title: 'Tag', key: 'tag', sortable: true },
  { title: 'Images', key: 'image_names', sortable: false },
  { title: 'Scan Status', key: 'processing_status', sortable: true },
  { title: 'Scan Progress', key: 'scan_progress', sortable: false },
  { title: 'Findings', key: 'findings', sortable: true },
  { title: 'Components', key: 'components', sortable: true },
  { title: 'Updated', key: 'updated_at', sortable: true },
  { title: 'Actions', key: 'actions', sortable: false }
]

// JSON Wizard table headers
const jsonTableHeaders = [
  { title: 'Helm Tag', key: 'helm_tag', sortable: true },
  { title: 'Version', key: 'app_version', sortable: true },
  { title: 'Repository Status', key: 'repository_status', sortable: true },
  { title: 'Tag Status', key: 'tag_status', sortable: true }
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

const hasFoundTags = computed(() => {
  return parsedData.value.some(item => 
    item.repository_status === 'Found' && 
    (item.tag_status === 'Found' || item.tag_uuid)
  )
})

const releaseTags = computed(() => releaseContents.value?.tags || [])

const releaseSummary = computed<ReleaseContentsSummary>(() => releaseContents.value?.summary || {
  total_tags: 0,
  success_tags: 0,
  pending_tags: 0,
  in_process_tags: 0,
  error_tags: 0,
  unscanned_tags: 0,
  total_images: 0,
  success_images: 0,
  pending_images: 0,
  in_process_images: 0,
  error_images: 0,
  all_tags_scanned: false
})

const releaseHasActiveScanning = computed(() => (
  releaseSummary.value.pending_tags > 0 ||
  releaseSummary.value.in_process_tags > 0 ||
  releaseSummary.value.pending_images > 0 ||
  releaseSummary.value.in_process_images > 0
))

const incompleteReleaseTagCount = computed(() => (
  releaseSummary.value.total_tags - releaseSummary.value.success_tags
))

const releasableScanCount = computed(() => (
  releaseTags.value.filter(tag => !['success', 'pending', 'in_process'].includes(tag.processing_status)).length
))

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

const fetchReleaseNames = async () => {
  try {
    const response = await api.get('/releases/names/')
    releaseNames.value = response.data
  } catch (error) {
    console.error('Error fetching release names:', error)
  }
}

const checkReleaseNameExists = (name: string, excludeUuid?: string) => {
  return releaseNames.value.some(release => 
    release.name.toLowerCase() === name.toLowerCase() && 
    release.uuid !== excludeUuid
  )
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
    await fetchReleaseNames()
  } catch (error: any) {
    console.error('Error saving release:', error)
    
    // Handle specific validation errors
    if (error.response?.data?.name) {
      notificationService.error(error.response.data.name[0])
    } else if (error.response?.data?.non_field_errors) {
      notificationService.error(error.response.data.non_field_errors[0])
    } else {
      notificationService.error('Failed to save release')
    }
  } finally {
    saving.value = false
  }
}

const viewRelease = async (release: Release) => {
  selectedRelease.value = release
  detailsDialog.value = true
  await fetchReleaseContents(release.uuid)
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
    await fetchReleaseNames()
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

const getReleaseScanStatusColor = (status: string) => {
  switch (status) {
    case 'success':
      return 'success'
    case 'pending':
      return 'info'
    case 'in_process':
      return 'warning'
    case 'error':
      return 'error'
    default:
      return 'grey'
  }
}

const formatReleaseScanStatus = (status: string) => {
  switch (status) {
    case 'success':
      return 'Scanned'
    case 'pending':
      return 'Queued'
    case 'in_process':
      return 'Processing'
    case 'error':
      return 'Error'
    default:
      return 'Not scanned'
  }
}

const formatReleaseTagScanProgress = (tag: ReleaseTagItem) => {
  if (!tag.total_images) {
    return 'No linked images yet'
  }

  const parts = [`${tag.success_images}/${tag.total_images} scanned`]
  if (tag.pending_images) {
    parts.push(`${tag.pending_images} pending`)
  }
  if (tag.in_process_images) {
    parts.push(`${tag.in_process_images} processing`)
  }
  if (tag.error_images) {
    parts.push(`${tag.error_images} error`)
  }

  return parts.join(' • ')
}

const getReleaseImagePreview = (tag: ReleaseTagItem) => {
  return (tag.image_names || []).slice(0, 2)
}

const getHiddenReleaseImageCount = (tag: ReleaseTagItem) => {
  return Math.max((tag.image_names || []).length - getReleaseImagePreview(tag).length, 0)
}

const fetchReleaseContents = async (releaseUuid: string, showLoader = true) => {
  if (showLoader) {
    releaseContentsLoading.value = true
  }

  try {
    const response = await api.get(`/releases/${releaseUuid}/contents/`)
    releaseContents.value = response.data
  } catch (error) {
    console.error('Error fetching release contents:', error)
    notificationService.error('Failed to load release contents')
  } finally {
    if (showLoader) {
      releaseContentsLoading.value = false
    }
  }
}

const refreshSelectedReleaseContents = async () => {
  if (!selectedRelease.value) return
  await fetchReleaseContents(selectedRelease.value.uuid)
}

const openReleaseTagImages = (tag: ReleaseTagItem) => {
  detailsDialog.value = false
  router.push({ name: 'tag-images', params: { uuid: tag.uuid } })
}

const scanUnscannedReleaseTags = async () => {
  if (!selectedRelease.value) return

  releaseScanStarting.value = true
  try {
    const response = await api.post(`/releases/${selectedRelease.value.uuid}/scan-unscanned/`)
    const summary = response.data.summary || {}

    if (summary.queued_tags > 0) {
      notificationService.queued(
        `${summary.queued_tags} release tag(s) queued for scanning`,
        3400,
        { dedupeKey: `release-scan:${selectedRelease.value.uuid}` },
      )
    } else if (summary.already_running_tags > 0) {
      notificationService.conflict('Release already has tags being processed')
    } else {
      notificationService.completed('All release tags are already fully scanned')
    }

    await fetchReleaseContents(selectedRelease.value.uuid, false)
  } catch (error) {
    console.error('Error queueing release scan:', error)
    notificationService.error('Failed to queue release tag scanning')
  } finally {
    releaseScanStarting.value = false
  }
}

const stopReleasePolling = () => {
  if (releasePollingTimer.value) {
    clearInterval(releasePollingTimer.value)
    releasePollingTimer.value = undefined
  }
}

const syncReleasePolling = () => {
  stopReleasePolling()
  if (!detailsDialog.value || !selectedRelease.value || !releaseHasActiveScanning.value) {
    return
  }

  releasePollingTimer.value = window.setInterval(() => {
    if (selectedRelease.value) {
      fetchReleaseContents(selectedRelease.value.uuid, false)
    }
  }, 5000)
}

// JSON Wizard functions
const openJsonWizard = () => {
  jsonWizardDialog.value = true
  clearJson()
}

const closeJsonWizard = () => {
  jsonWizardDialog.value = false
  clearJson()
}

const clearJson = () => {
  if (parseTimeout.value) {
    clearTimeout(parseTimeout.value)
    parseTimeout.value = undefined
  }
  jsonInput.value = ''
  parsedData.value = []
  jsonError.value = false
  jsonErrorMessage.value = ''
}

const parseJson = () => {
  if (!jsonInput.value.trim()) {
    jsonError.value = true
    jsonErrorMessage.value = 'Please enter JSON data'
    return
  }

  parsing.value = true
  jsonError.value = false
  jsonErrorMessage.value = ''

  try {
    const data = JSON.parse(jsonInput.value)
    
    if (!Array.isArray(data)) {
      throw new Error('JSON must be an array')
    }

    parsedData.value = data.map(item => ({
      ...item,
      helm_tag: `helm/${item.name}`
    }))
  } catch (error: any) {
    jsonError.value = true
    jsonErrorMessage.value = `Invalid JSON: ${error.message}`
    parsedData.value = []
    notificationService.error('Failed to parse JSON')
  } finally {
    parsing.value = false
  }
}

const parseJsonOnInput = () => {
  // Debounce the parsing to avoid too frequent calls
  clearTimeout(parseTimeout.value)
  parseTimeout.value = setTimeout(() => {
    if (jsonInput.value.trim()) {
      parseJson()
    } else {
      parsedData.value = []
      jsonError.value = false
      jsonErrorMessage.value = ''
    }
  }, 500) // 500ms delay
}



const getStatusColor = (status: string) => {
  switch (status) {
    case 'Found':
      return 'success'
    case 'Not Found':
      return 'error'
    case 'Checking':
      return 'warning'
    default:
      return 'grey'
  }
}

const checkRepositories = async () => {
  if (parsedData.value.length === 0) {
    notificationService.warning('No data to check')
    return
  }

  checking.value = true
  
  try {
    // Update all items to show "Checking" status
    parsedData.value = parsedData.value.map(item => ({
      ...item,
      repository_status: 'Checking',
      tag_status: 'Checking'
    }))

    // Send all data to backend in one request
    const response = await api.post('/repositories/check_helm_releases/', {
      releases: parsedData.value.map(item => ({
        name: `helm/${item.name}`,
        app_version: item.app_version
      }))
    })

    // Backend response received

    // Update the data with results from backend
    parsedData.value = parsedData.value.map((item, index) => {
      const result = response.data.results[index]
      return {
        ...item,
        repository_status: result.repository_status,
        tag_status: result.tag_status,
        repository_uuid: result.repository_uuid,
        tag_uuid: result.tag_uuid
      }
    })

    const { repositories_found, tags_found } = response.data
    notificationService.success(`Check completed: ${repositories_found} repositories found, ${tags_found} tags found`)
  } catch (error) {
    console.error('Error checking repositories:', error)
    notificationService.error('Failed to check repositories')
  } finally {
    checking.value = false
  }
}

const addTagToRepository = async (item: any) => {
  
  if (!item.name || !item.app_version) {
    notificationService.error('Missing repository name or version')
    return
  }

  if (!item.repository_uuid) {
    console.error('Repository UUID missing for item:', item)
    notificationService.error('Repository UUID not available')
    return
  }

  addingTag.value = item.helm_tag
  
  try {
    // Create the tag using the repository UUID from check results
    const postData = {
      tag: item.app_version,
      description: `Auto-created from Helm release: ${item.name}`
    }
    
    // Sending POST request to create tag
    
    const response = await api.post(`/repositories/${item.repository_uuid}/create_tag/`, postData)

    notificationService.success(`Tag ${item.app_version} added to repository ${item.name}`)
    
    // Update the item status and add tag_uuid
    const itemIndex = parsedData.value.findIndex(i => i.helm_tag === item.helm_tag)
    if (itemIndex !== -1) {
      parsedData.value[itemIndex].tag_status = 'Found'
      parsedData.value[itemIndex].tag_uuid = response.data.uuid
    }
  } catch (error: any) {
    console.error('Error adding tag:', error)
    if (error.response?.status === 409) {
      notificationService.error('Tag already exists')
    } else {
      notificationService.error('Failed to add tag')
    }
  } finally {
    addingTag.value = null
  }
}

const showReleaseCreationStep = () => {
  // Get all found tags for release creation (including newly added ones)
  selectedTagsForRelease.value = parsedData.value.filter(item => 
    item.repository_status === 'Found' && 
    (item.tag_status === 'Found' || item.tag_uuid)
  )
  
  // Set default release name based on current date
  const now = new Date()
  releaseName.value = `Release ${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
  releaseDescription.value = ''
  
  showReleaseStep.value = true
}

const createReleaseWithTags = async () => {
  if (!releaseName.value.trim()) {
    notificationService.error('Release name is required')
    return
  }

  if (selectedTagsForRelease.value.length === 0) {
    notificationService.error('No tags selected for release')
    return
  }

  // Check if release name already exists
  if (checkReleaseNameExists(releaseName.value)) {
    notificationService.error('Release with this name already exists')
    return
  }

  creatingRelease.value = true

  try {
    // Get UUIDs directly from the parsed data (already available from check_helm_releases)
    const tagUuids = selectedTagsForRelease.value
      .filter(item => item.tag_uuid)
      .map(item => item.tag_uuid)

    if (tagUuids.length === 0) {
      notificationService.error('No valid tags found for release')
      return
    }

    // Create release with tags
    const releaseResponse = await api.post('/repositories/create_release_with_tags/', {
      release_name: releaseName.value,
      release_description: releaseDescription.value,
      tag_uuids: tagUuids
    })

    // Release created successfully

    notificationService.success(
      `Release "${releaseName.value}" created with ${releaseResponse.data.tags_linked} tags`
    )

    // Close wizard and refresh releases
    showReleaseStep.value = false
    jsonWizardDialog.value = false
    await fetchReleases()
    await fetchReleaseNames()

  } catch (error: any) {
    console.error('Error creating release:', error)
    
    // Handle specific validation errors
    if (error.response?.data?.release_name) {
      notificationService.error(error.response.data.release_name[0])
    } else if (error.response?.data?.non_field_errors) {
      notificationService.error(error.response.data.non_field_errors[0])
    } else {
      notificationService.error('Failed to create release')
    }
  } finally {
    creatingRelease.value = false
  }
}

// Lifecycle
onMounted(() => {
  fetchReleases()
  fetchReleaseNames()
})

watch(
  () => [detailsDialog.value, selectedRelease.value?.uuid, releaseHasActiveScanning.value],
  () => {
    syncReleasePolling()
  },
)

watch(detailsDialog, (isOpen) => {
  if (!isOpen) {
    stopReleasePolling()
  }
})

onUnmounted(() => {
  stopReleasePolling()
})
</script>

<style scoped>
.releases-page {
  padding: 24px;
  background: #ffffff;
  min-height: 100vh;
}


.v-data-table {
  border-radius: 8px;
}

.release-details-loading {
  display: flex;
  justify-content: center;
  padding: 32px 0;
}

.release-summary-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.release-tag-repository {
  display: flex;
  flex-direction: column;
}

.release-tag-name {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.release-image-cell {
  min-width: 240px;
}

.release-image-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
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
