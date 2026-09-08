<template>
  <v-container fluid class="clusters-page page-shell page-shell--wide">
    <v-row class="mb-4" align="center">
      <v-col>
        <h1 class="text-h4 font-weight-bold mb-2">Clusters</h1>
        <p class="text-body-1 text-medium-emphasis">Track deployed images and scan them with matching registry credentials.</p>
      </v-col>
      <v-col cols="auto" class="d-flex ga-2">
        <v-btn color="primary" prepend-icon="mdi-plus" @click="openClusterDialog()">Create Cluster</v-btn>
        <v-btn color="secondary" prepend-icon="mdi-auto-fix" :disabled="clusters.length === 0" @click="openWizard">Image Wizard</v-btn>
      </v-col>
    </v-row>

    <v-card>
      <v-card-title class="d-flex align-center ga-4">
        <span>Created clusters</span>
        <v-spacer />
        <v-text-field
          v-model="search"
          label="Search clusters"
          prepend-inner-icon="mdi-magnify"
          density="compact"
          variant="outlined"
          hide-details
          max-width="360"
          @update:model-value="debouncedFetch"
        />
      </v-card-title>
      <v-data-table-server
        :headers="clusterHeaders"
        :items="clusters"
        :items-length="total"
        :loading="loading"
        v-model:page="page"
        v-model:items-per-page="itemsPerPage"
        item-value="uuid"
        @update:options="fetchClusters"
      >
        <template #item.name="{ item }">
          <button class="text-primary font-weight-medium" @click="viewCluster(item)">{{ item.name }}</button>
        </template>
        <template #item.images_count="{ item }">
          <v-chip size="small" color="primary" variant="tonal">{{ item.images_count }}</v-chip>
        </template>
        <template #item.scan_progress="{ item }">
          <div class="cluster-progress-cell py-2">
            <div class="d-flex align-center justify-space-between text-caption mb-1">
              <span>{{ item.scan_progress.completed }}/{{ item.scan_progress.total }}</span>
              <span v-if="item.scan_progress.remaining">{{ item.scan_progress.remaining }} remaining</span>
              <span v-else-if="item.scan_progress.total">Complete</span>
              <span v-else>No images</span>
            </div>
            <v-progress-linear
              :model-value="item.scan_progress.percent"
              :color="progressColor(item.scan_progress)"
              height="7"
              rounded
            />
          </div>
        </template>
        <template #item.created_at="{ item }">{{ formatDate(item.created_at) }}</template>
        <template #item.actions="{ item }">
          <v-btn icon="mdi-eye-outline" size="small" variant="text" @click="viewCluster(item)" />
          <v-btn icon="mdi-pencil-outline" size="small" variant="text" @click="openClusterDialog(item)" />
          <v-btn icon="mdi-delete-outline" size="small" color="error" variant="text" @click="confirmDelete(item)" />
        </template>
      </v-data-table-server>
    </v-card>

    <v-dialog v-model="clusterDialog" max-width="560">
      <v-card>
        <v-card-title>{{ editingCluster ? 'Edit Cluster' : 'Create Cluster' }}</v-card-title>
        <v-card-text>
          <v-text-field v-model="clusterForm.name" label="Cluster name" variant="outlined" autofocus />
          <v-textarea v-model="clusterForm.description" label="Description (optional)" variant="outlined" rows="3" />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="clusterDialog = false">Cancel</v-btn>
          <v-btn color="primary" :loading="savingCluster" :disabled="!clusterForm.name.trim()" @click="saveCluster">Save</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="detailsDialog" max-width="1100">
      <v-card>
        <v-card-title class="d-flex align-center">
          <span>{{ selectedCluster?.name }} images</span>
          <v-spacer />
          <v-btn
            color="success"
            variant="tonal"
            prepend-icon="mdi-radar"
            class="mr-2"
            :loading="bulkScanning"
            :disabled="clusterProgress.total === 0 || clusterProgress.active"
            @click="scanAllImages"
          >
            Scan all images
          </v-btn>
          <v-btn color="primary" variant="tonal" prepend-icon="mdi-plus" class="mr-2" @click="openWizard(selectedCluster || undefined)">Add images</v-btn>
          <v-btn icon="mdi-close" variant="text" @click="detailsDialog = false" />
        </v-card-title>
        <v-card-text>
          <v-progress-linear v-if="loadingContents" indeterminate class="mb-3" />
          <v-sheet v-if="clusterProgress.total" rounded="lg" border class="pa-4 mb-4">
            <div class="d-flex flex-wrap align-center ga-3 mb-3">
              <div>
                <div class="text-subtitle-1 font-weight-bold">Cluster scan progress</div>
                <div class="text-body-2 text-medium-emphasis">
                  {{ clusterProgress.completed }} of {{ clusterProgress.total }} completed ·
                  {{ clusterProgress.remaining }} remaining
                </div>
              </div>
              <v-spacer />
              <v-chip v-if="clusterProgress.pending" color="warning" variant="tonal" size="small">
                {{ clusterProgress.pending }} queued
              </v-chip>
              <v-chip v-if="clusterProgress.in_process" color="info" variant="tonal" size="small">
                {{ clusterProgress.in_process }} scanning
              </v-chip>
              <v-chip color="success" variant="tonal" size="small">
                {{ clusterProgress.success }} successful
              </v-chip>
              <v-chip v-if="clusterProgress.error" color="error" variant="tonal" size="small">
                {{ clusterProgress.error }} failed
              </v-chip>
              <v-chip v-if="clusterProgress.not_started" variant="tonal" size="small">
                {{ clusterProgress.not_started }} not started
              </v-chip>
            </div>
            <v-progress-linear
              :model-value="clusterProgress.percent"
              :color="progressColor(clusterProgress)"
              height="12"
              rounded
              striped
            >
              <strong class="text-caption">{{ clusterProgress.percent }}%</strong>
            </v-progress-linear>
          </v-sheet>
          <v-alert v-if="!loadingContents && clusterImages.length === 0" type="info" variant="tonal">No images have been added yet.</v-alert>
          <v-table v-else density="comfortable">
            <thead><tr><th>Image</th><th>Registry</th><th>Status</th><th>Digest</th><th></th></tr></thead>
            <tbody>
              <tr v-for="image in clusterImages" :key="image.uuid">
                <td><router-link :to="`/images/${image.uuid}`">{{ image.source_reference }}</router-link></td>
                <td>{{ image.registry?.name || 'Public / no configured credentials' }}</td>
                <td><v-chip size="small" :color="statusColor(image.scan_status)" variant="tonal">{{ image.scan_status }}</v-chip></td>
                <td class="text-truncate digest-cell">{{ image.digest || '—' }}</td>
                <td class="text-right text-no-wrap">
                  <v-btn
                    icon="mdi-radar"
                    size="small"
                    color="primary"
                    variant="text"
                    :disabled="['pending', 'in_process'].includes(image.scan_status)"
                    @click="scanImage(image)"
                  />
                  <v-btn icon="mdi-link-off" size="small" variant="text" @click="removeImage(image)" />
                </td>
              </tr>
            </tbody>
          </v-table>
        </v-card-text>
      </v-card>
    </v-dialog>

    <v-dialog v-model="wizardDialog" max-width="1200" persistent>
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon icon="mdi-auto-fix" class="mr-2" /> Cluster Image Wizard
          <v-spacer />
          <v-btn icon="mdi-close" variant="text" @click="closeWizard" />
        </v-card-title>
        <v-card-text>
          <v-select
            v-model="wizardClusterId"
            :items="clusters"
            item-title="name"
            item-value="uuid"
            label="Target cluster"
            variant="outlined"
            :disabled="wizardChecked"
            class="mb-3"
          />
          <v-textarea
            v-if="!wizardChecked"
            v-model="imageInput"
            label="Image references, one per line"
            placeholder="nlpapp0336cre.azurecr.io/litellm/backend:v1.94.0"
            variant="outlined"
            rows="12"
            spellcheck="false"
          />

          <template v-else>
            <v-row dense class="mb-3">
              <v-col><v-alert type="success" variant="tonal">{{ summary.existing }} already in the system</v-alert></v-col>
              <v-col><v-alert type="warning" variant="tonal">{{ summary.missing }} can be created</v-alert></v-col>
              <v-col><v-alert type="info" variant="tonal">{{ summary.authenticated }} matched registries</v-alert></v-col>
              <v-col v-if="summary.invalid"><v-alert type="error" variant="tonal">{{ summary.invalid }} invalid</v-alert></v-col>
            </v-row>
            <v-table fixed-header height="520" density="compact">
              <thead><tr><th>Image</th><th>System</th><th>Registry / scan access</th><th>Create</th><th>Scan now</th></tr></thead>
              <tbody>
                <tr v-for="row in checkedImages" :key="row.reference">
                  <td class="reference-cell">
                    {{ row.reference }}
                    <div v-if="!row.valid" class="text-error text-caption">{{ row.error }}</div>
                  </td>
                  <td>
                    <v-chip v-if="row.exists" color="success" size="small" variant="tonal">Exists</v-chip>
                    <v-chip v-else-if="row.valid" color="warning" size="small" variant="tonal">Missing</v-chip>
                    <v-chip v-else color="error" size="small" variant="tonal">Invalid</v-chip>
                  </td>
                  <td>
                    <template v-if="row.registry">
                      <div>{{ row.registry.name }}</div><div class="text-caption text-success">Authenticated scan available</div>
                    </template>
                    <span v-else-if="row.valid" class="text-medium-emphasis">Public pull / no matching registry</span>
                    <span v-else>—</span>
                  </td>
                  <td><v-checkbox-btn v-if="row.valid && !row.exists" v-model="row.create" /></td>
                  <td><v-checkbox-btn v-if="row.valid" v-model="row.scan" :disabled="!row.exists && !row.create" /></td>
                </tr>
              </tbody>
            </v-table>
          </template>
        </v-card-text>
        <v-card-actions>
          <v-btn v-if="wizardChecked" @click="wizardChecked = false">Back</v-btn>
          <v-spacer />
          <v-btn @click="closeWizard">Cancel</v-btn>
          <v-btn v-if="!wizardChecked" color="primary" :loading="checking" :disabled="!wizardClusterId || !imageInput.trim()" @click="checkImages">Check images</v-btn>
          <v-btn v-else color="primary" :loading="importing" @click="attachImages">Add to cluster</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="deleteDialog" max-width="480">
      <v-card>
        <v-card-title>Delete cluster?</v-card-title>
        <v-card-text>This removes {{ deletingCluster?.name }} and its image links. Images and scan results remain in the system.</v-card-text>
        <v-card-actions><v-spacer /><v-btn @click="deleteDialog = false">Cancel</v-btn><v-btn color="error" @click="deleteCluster">Delete</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import api from '../plugins/axios'
import { notificationService } from '../plugins/notifications'
import { debounce } from '../utils/debounce'

interface ClusterScanProgress {
  state: 'empty' | 'idle' | 'running' | 'completed'
  total: number
  completed: number
  remaining: number
  pending: number
  in_process: number
  success: number
  error: number
  not_started: number
  active: boolean
  percent: number
}
interface Cluster { uuid: string; name: string; description: string; images_count: number; scan_progress: ClusterScanProgress; created_at: string; updated_at: string }
interface Registry { uuid: string; name: string; provider: string }
interface ClusterImage { uuid: string; name: string; source_reference: string; digest?: string; scan_status: string; registry?: Registry }
interface CheckedImage { reference: string; valid: boolean; error?: string; exists?: boolean; registry?: Registry; create?: boolean; scan?: boolean }

const clusters = ref<Cluster[]>([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const itemsPerPage = ref(10)
const search = ref('')
const clusterHeaders = [
  { title: 'Name', key: 'name' },
  { title: 'Description', key: 'description' },
  { title: 'Images', key: 'images_count', align: 'center' as const },
  { title: 'Scan progress', key: 'scan_progress', sortable: false },
  { title: 'Created', key: 'created_at' },
  { title: '', key: 'actions', sortable: false, align: 'end' as const },
]

const clusterDialog = ref(false)
const savingCluster = ref(false)
const editingCluster = ref<Cluster | null>(null)
const clusterForm = ref({ name: '', description: '' })
const detailsDialog = ref(false)
const loadingContents = ref(false)
const selectedCluster = ref<Cluster | null>(null)
const clusterImages = ref<ClusterImage[]>([])
const emptyProgress = (): ClusterScanProgress => ({
  state: 'empty', total: 0, completed: 0, remaining: 0, pending: 0,
  in_process: 0, success: 0, error: 0, not_started: 0, active: false, percent: 0,
})
const clusterProgress = ref<ClusterScanProgress>(emptyProgress())
const bulkScanning = ref(false)
let clusterPollTimer: ReturnType<typeof setInterval> | null = null
const deleteDialog = ref(false)
const deletingCluster = ref<Cluster | null>(null)

const wizardDialog = ref(false)
const wizardClusterId = ref<string | null>(null)
const imageInput = ref('')
const wizardChecked = ref(false)
const checking = ref(false)
const importing = ref(false)
const checkedImages = ref<CheckedImage[]>([])
const summary = ref({ total: 0, existing: 0, missing: 0, invalid: 0, authenticated: 0 })

async function fetchClusters() {
  loading.value = true
  try {
    const response = await api.get('/clusters/', { params: { page: page.value, page_size: itemsPerPage.value, search: search.value } })
    clusters.value = response.data.results || response.data
    total.value = response.data.count ?? clusters.value.length
  } catch (error) {
    notificationService.error('Failed to load clusters')
  } finally { loading.value = false }
}
const debouncedFetch = debounce(() => { page.value = 1; fetchClusters() }, 300)

function openClusterDialog(cluster?: Cluster) {
  editingCluster.value = cluster || null
  clusterForm.value = { name: cluster?.name || '', description: cluster?.description || '' }
  clusterDialog.value = true
}
async function saveCluster() {
  savingCluster.value = true
  try {
    if (editingCluster.value) await api.patch(`/clusters/${editingCluster.value.uuid}/`, clusterForm.value)
    else await api.post('/clusters/', clusterForm.value)
    notificationService.success(editingCluster.value ? 'Cluster updated' : 'Cluster created')
    clusterDialog.value = false
    await fetchClusters()
  } catch (error: any) {
    notificationService.error(error.response?.data?.name?.[0] || 'Failed to save cluster')
  } finally { savingCluster.value = false }
}
async function viewCluster(cluster: Cluster) {
  selectedCluster.value = cluster
  clusterProgress.value = cluster.scan_progress || emptyProgress()
  detailsDialog.value = true
  await loadContents()
}
async function loadContents(showLoader = true) {
  if (!selectedCluster.value) return
  if (showLoader) loadingContents.value = true
  try {
    const response = await api.get(`/clusters/${selectedCluster.value.uuid}/contents/`)
    clusterImages.value = response.data.images
    clusterProgress.value = response.data.progress || emptyProgress()
    selectedCluster.value = { ...selectedCluster.value, scan_progress: clusterProgress.value }
    syncClusterPolling()
  } finally {
    if (showLoader) loadingContents.value = false
  }
}
async function removeImage(image: ClusterImage) {
  if (!selectedCluster.value) return
  await api.delete(`/clusters/${selectedCluster.value.uuid}/images/${image.uuid}/`)
  notificationService.success('Image removed from cluster')
  await Promise.all([loadContents(), fetchClusters()])
}
async function scanImage(image: ClusterImage) {
  try {
    await api.post(`/images/${image.uuid}/rescan/`)
    notificationService.success(`Scan queued for ${image.source_reference}`)
    await loadContents()
  } catch (error: any) {
    if (error.response?.status === 409) notificationService.warning('This image is already being scanned')
    else notificationService.error('Failed to queue image scan')
  }
}
async function scanAllImages() {
  if (!selectedCluster.value || clusterProgress.value.total === 0) return
  bulkScanning.value = true
  try {
    const response = await api.post(`/clusters/${selectedCluster.value.uuid}/scan-all/`)
    clusterProgress.value = response.data.progress || clusterProgress.value
    const failed = response.data.failed_to_queue?.length || 0
    notificationService.success(
      `Queued ${response.data.scheduled.length} image(s); ${clusterProgress.value.remaining} remaining${failed ? `; ${failed} failed to queue` : ''}`,
    )
    await Promise.all([loadContents(false), fetchClusters()])
    syncClusterPolling()
  } catch (error: any) {
    notificationService.error(error.response?.data?.error || 'Failed to scan cluster images')
  } finally {
    bulkScanning.value = false
  }
}

function stopClusterPolling() {
  if (clusterPollTimer) {
    clearInterval(clusterPollTimer)
    clusterPollTimer = null
  }
}

function syncClusterPolling() {
  if (!detailsDialog.value || !clusterProgress.value.active) {
    stopClusterPolling()
    return
  }
  if (!clusterPollTimer) {
    clusterPollTimer = setInterval(async () => {
      await loadContents(false)
      await fetchClusters()
    }, 2500)
  }
}
function confirmDelete(cluster: Cluster) { deletingCluster.value = cluster; deleteDialog.value = true }
async function deleteCluster() {
  if (!deletingCluster.value) return
  await api.delete(`/clusters/${deletingCluster.value.uuid}/`)
  deleteDialog.value = false
  notificationService.success('Cluster deleted; images were preserved')
  await fetchClusters()
}

function openWizard(cluster?: Cluster) {
  wizardClusterId.value = cluster?.uuid || selectedCluster.value?.uuid || clusters.value[0]?.uuid || null
  imageInput.value = ''
  checkedImages.value = []
  wizardChecked.value = false
  wizardDialog.value = true
}
function closeWizard() { wizardDialog.value = false }
async function checkImages() {
  checking.value = true
  try {
    const response = await api.post('/clusters/check-images/', { images: imageInput.value })
    checkedImages.value = response.data.results.map((row: CheckedImage) => ({ ...row, create: row.valid && !row.exists, scan: false }))
    summary.value = response.data.summary
    wizardChecked.value = true
  } catch (error) { notificationService.error('Failed to check image list') }
  finally { checking.value = false }
}
async function attachImages() {
  if (!wizardClusterId.value) return
  importing.value = true
  try {
    const valid = checkedImages.value.filter(row => row.valid)
    const response = await api.post(`/clusters/${wizardClusterId.value}/attach-images/`, {
      images: valid.map(row => row.reference),
      create_references: valid.filter(row => !row.exists && row.create).map(row => row.reference),
      scan_references: valid.filter(row => row.scan).map(row => row.reference),
    })
    const created = response.data.results.filter((row: any) => row.status === 'created').length
    const scheduled = response.data.scheduled.length
    notificationService.success(`Images added. Created: ${created}; scans queued: ${scheduled}`)
    wizardDialog.value = false
    await fetchClusters()
    if (selectedCluster.value?.uuid === wizardClusterId.value) await loadContents()
  } catch (error) { notificationService.error('Failed to add images to cluster') }
  finally { importing.value = false }
}

function formatDate(value: string) { return value ? new Date(value).toLocaleString() : '—' }
function statusColor(status: string) { return ({ success: 'success', error: 'error', pending: 'warning', in_process: 'info' } as Record<string, string>)[status] || 'default' }
function progressColor(progress: ClusterScanProgress) {
  if (progress.active) return 'info'
  if (progress.error) return 'error'
  if (progress.total && progress.remaining === 0) return 'success'
  return 'primary'
}

onMounted(fetchClusters)
watch(detailsDialog, (open) => {
  if (open) syncClusterPolling()
  else stopClusterPolling()
})
onUnmounted(stopClusterPolling)
</script>

<style scoped>
.reference-cell { max-width: 440px; overflow-wrap: anywhere; }
.digest-cell { max-width: 220px; }
.cluster-progress-cell { min-width: 190px; }
button { cursor: pointer; }
</style>
