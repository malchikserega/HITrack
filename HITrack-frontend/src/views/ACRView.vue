<template>
  <div class="jobs">
    <v-container>
      <v-row>
        <v-col cols="12">
          <h1 class="text-h4 mb-4 font-weight-black">Container Registries</h1>
          <v-select
            v-model="provider"
            :items="providerOptions"
            item-title="title"
            item-value="value"
            label="Registry type"
            class="mb-4"
            density="comfortable"
            @update:model-value="onProviderChange"
          />
          <v-select
            v-if="registries.length > 1"
            v-model="selectedRegistry"
            :items="registries"
            item-title="name"
            item-value="uuid"
            :label="registrySelectLabel"
            class="mb-4"
            :disabled="isLoading"
          />
          <v-chip
            v-else-if="registries.length === 1 && selectedRegistry"
            class="mb-4"
            color="primary"
            variant="tonal"
            size="large"
          >
            {{ registries.find(r => r.uuid === selectedRegistry)?.name ?? 'Registry selected' }}
          </v-chip>
          <v-btn 
            v-if="registries.length"
            :disabled="!selectedRegistry || isLoading"
            color="primary" 
            @click="openDialog()" 
            class="mb-4"
            :loading="isLoading"
          >
            <template v-slot:loader>
              <v-progress-circular
                indeterminate
                color="white"
              ></v-progress-circular>
            </template>
            {{ addFromButtonLabel }}
          </v-btn>
          <v-alert v-else type="warning" class="mb-4">
            {{ noRegistryMessage }}
          </v-alert>
        </v-col>
      </v-row>

      <v-dialog 
        v-model="dialog" 
        width="1000"
        class="acr-dialog"
      >
        <v-card class="dialog-card">
          <div class="dialog-header">
            <span class="text-h5">{{ dialogTitle }}</span>
            <v-btn
              icon="mdi-close"
              variant="text"
              @click="dialog = false"
            ></v-btn>
          </div>
          <v-stepper v-model="currentStep" :items="activeSteps" class="wizard-stepper">

            <!-- JFrog Step 1: Select Repo Key -->
            <template v-slot:item.1>
              <v-card flat class="step-card">
                <v-card-text class="step-content">
                  <!-- ACR: multi-select repos; JFrog: single-select repo key -->
                  <v-text-field
                    v-model="search"
                    :label="isJfrog ? 'Search repo keys' : 'Search repositories'"
                    prepend-inner-icon="mdi-magnify"
                    variant="outlined"
                    clearable
                    @click:clear="search = ''"
                    class="mb-4"
                  ></v-text-field>
                  <div class="scrollable-content">
                    <v-list class="repository-list">
                      <template v-if="repositories.length > 0">
                        <v-list-item
                          v-for="repo in filteredRepositories"
                          :key="repo.url"
                          :value="repo"
                          class="repository-item"
                          @click="isJfrog ? selectRepoKey(repo) : toggleRepository(repo)"
                          :active="isJfrog && selectedRepoKey?.url === repo.url"
                        >
                          <template v-slot:prepend>
                            <!-- ACR: checkboxes for multi-select -->
                            <v-checkbox
                              v-if="!isJfrog"
                              v-model="selectedRepositories"
                              :value="repo"
                              hide-details
                              class="mr-2"
                              @click.stop
                            ></v-checkbox>
                            <!-- JFrog: radio-style single-select -->
                            <v-radio-group
                              v-else
                              :model-value="selectedRepoKey?.url"
                              hide-details
                              class="mr-2"
                            >
                              <v-radio :value="repo.url" @click.stop="selectRepoKey(repo)" />
                            </v-radio-group>
                          </template>
                          <v-list-item-title class="text-subtitle-1 font-weight-medium">
                            {{ repo.name }}
                            <v-chip
                              v-if="repo.package_type"
                              size="x-small"
                              :color="repo.package_type === 'helm' ? 'purple-lighten-1' : 'light-blue-lighten-1'"
                              variant="tonal"
                              class="ml-2"
                              density="compact"
                            >
                              {{ repo.package_type === 'helm' ? 'Helm' : 'Docker' }}
                            </v-chip>
                            <v-chip
                              size="x-small"
                              color="light-blue-lighten-1"
                              variant="outlined"
                              class="ml-2"
                              density="compact"
                            >
                              {{ repo.url }}
                            </v-chip>
                          </v-list-item-title>
                        </v-list-item>
                        <div v-if="isLoadingMore" class="text-center py-4">
                          <v-progress-circular indeterminate color="primary" size="24"></v-progress-circular>
                        </div>
                        <div ref="observerTarget" class="observer-target"></div>
                      </template>
                      <template v-else>
                        <v-list-item>
                          <v-list-item-title class="text-center py-4">
                            <v-progress-circular indeterminate color="primary" class="mb-2"></v-progress-circular>
                            <div>Loading...</div>
                          </v-list-item-title>
                        </v-list-item>
                      </template>
                    </v-list>
                  </div>
                </v-card-text>
              </v-card>
            </template>

            <!-- JFrog Step 2: Select Components within repo key -->
            <template v-if="isJfrog" v-slot:item.2>
              <v-card flat class="step-card">
                <v-card-text class="step-content">
                  <div class="d-flex align-center mb-4">
                    <v-text-field
                      v-model="componentSearch"
                      label="Search components"
                      prepend-inner-icon="mdi-magnify"
                      variant="outlined"
                      clearable
                      @click:clear="componentSearch = ''"
                      class="flex-grow-1 mr-4"
                    ></v-text-field>
                    <v-btn
                      size="small"
                      variant="tonal"
                      @click="toggleSelectAllComponents"
                    >
                      {{ allComponentsSelected ? 'Deselect all' : 'Select all' }}
                    </v-btn>
                  </div>
                  <div class="scrollable-content">
                    <v-list class="repository-list" v-if="!componentsLoading">
                      <v-list-item
                        v-for="comp in filteredComponents"
                        :key="comp.url"
                        class="repository-item"
                        @click="toggleComponent(comp)"
                      >
                        <template v-slot:prepend>
                          <v-checkbox
                            v-model="selectedComponents"
                            :value="comp"
                            hide-details
                            class="mr-2"
                            @click.stop
                          ></v-checkbox>
                        </template>
                        <v-list-item-title class="text-subtitle-1 font-weight-medium">
                          {{ comp.name }}
                          <v-chip
                            size="x-small"
                            :color="comp.package_type === 'helm' ? 'purple-lighten-1' : 'light-blue-lighten-1'"
                            variant="tonal"
                            class="ml-2"
                            density="compact"
                          >
                            {{ comp.package_type === 'helm' ? 'Helm' : 'Docker' }}
                          </v-chip>
                        </v-list-item-title>
                      </v-list-item>
                    </v-list>
                    <div v-else class="text-center py-8">
                      <v-progress-circular indeterminate color="primary" size="36" class="mb-3"></v-progress-circular>
                      <div>Loading components from {{ selectedRepoKey?.name }}...</div>
                    </div>
                  </div>
                </v-card-text>
              </v-card>
            </template>

            <!-- Summary step (step 2 for ACR, step 3 for JFrog) -->
            <template v-slot:[summarySlot]>
              <v-card flat class="summary-auto-card">
                <v-card-text class="summary-auto-content">
                  <v-list class="summary-list">
                    <v-list-item
                      v-for="repo in itemsToSubmit"
                      :key="repo.url"
                      class="summary-item"
                    >
                      <template v-slot:prepend>
                        <v-icon icon="mdi-source-repository" color="primary"></v-icon>
                      </template>
                      <v-list-item-title class="text-subtitle-1 font-weight-medium">
                        {{ repo.name }}
                      </v-list-item-title>
                    </v-list-item>
                  </v-list>
                </v-card-text>
              </v-card>
            </template>

            <!-- Stepper Actions -->
            <template v-slot:actions>
              <div class="stepper-actions">
                <v-btn
                  :disabled="currentStep === 1"
                  variant="text"
                  @click="currentStep--"
                >
                  Previous
                </v-btn>
                <v-spacer></v-spacer>
                <v-btn
                  v-if="currentStep < totalSteps"
                  variant="text"
                  color="primary"
                  :disabled="!canAdvance"
                  @click="nextStep"
                >
                  Next
                </v-btn>
                <v-btn
                  v-else
                  variant="text"
                  color="primary"
                  :disabled="itemsToSubmit.length === 0"
                  :loading="submitting"
                  @click="submitJob"
                >
                  Submit
                </v-btn>
              </div>
            </template>
          </v-stepper>
        </v-card>
      </v-dialog>
    </v-container>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import api from '../plugins/axios'
import { notificationService } from '../plugins/notifications'
import type { ContainerRegistry, RegistryProvider } from '../types/interfaces'

interface RepoItem {
  name: string
  url: string
  package_type?: string
  repo_key?: string
}

const providerOptions: { title: string; value: RegistryProvider }[] = [
  { title: 'Azure Container Registry', value: 'acr' },
  { title: 'JFrog Artifactory', value: 'jfrog' }
]

const provider = ref<RegistryProvider>('acr')
const registries = ref<ContainerRegistry[]>([])
const selectedRegistry = ref<string | null>(null)
const isJfrog = computed(() => provider.value === 'jfrog')

const dialog = ref(false)
const currentStep = ref(1)

// Step 1: repo keys (JFrog) or repos (ACR)
const search = ref('')
const repositories = ref<RepoItem[]>([])
const selectedRepositories = ref<RepoItem[]>([])
const selectedRepoKey = ref<RepoItem | null>(null)

// Step 2 (JFrog only): components within a repo key
const componentSearch = ref('')
const components = ref<RepoItem[]>([])
const selectedComponents = ref<RepoItem[]>([])
const componentsLoading = ref(false)

const submitting = ref(false)
const isLoading = ref(false)
const hasMore = ref(true)
const isLoadingMore = ref(false)
const pageSize = 100
const lastRepo = ref<string | null>(null)

const activeSteps = computed(() => {
  if (isJfrog.value) {
    return [
      { title: 'Select Repo Key', description: 'Pick an Artifactory repository' },
      { title: 'Select Components', description: 'Choose images / charts' },
      { title: 'Summary', description: 'Confirm and submit' },
    ]
  }
  return [
    { title: 'Select Repositories', description: 'Select the repositories' },
    { title: 'Summary', description: 'Submit repositories' },
  ]
})

const totalSteps = computed(() => activeSteps.value.length)
const summarySlot = computed(() => `item.${totalSteps.value}`)

const itemsToSubmit = computed<RepoItem[]>(() => {
  if (isJfrog.value) return selectedComponents.value
  return selectedRepositories.value
})

const canAdvance = computed(() => {
  if (isJfrog.value) {
    if (currentStep.value === 1) return !!selectedRepoKey.value
    if (currentStep.value === 2) return selectedComponents.value.length > 0
  } else {
    if (currentStep.value === 1) return selectedRepositories.value.length > 0
  }
  return true
})

const registrySelectLabel = computed(() =>
  isJfrog.value ? 'Select Artifactory Registry' : 'Select ACR Registry'
)
const addFromButtonLabel = computed(() =>
  isJfrog.value ? 'Add from Artifactory' : 'Add from ACR'
)
const noRegistryMessage = computed(() =>
  isJfrog.value
    ? 'No JFrog Artifactory registry found in database'
    : 'No Azure Container Registry found in database'
)
const dialogTitle = computed(() =>
  isJfrog.value
    ? 'Add Repositories (Artifactory)'
    : 'Add Repositories (ACR)'
)

const filteredRepositories = computed(() => {
  if (!search.value) return repositories.value
  const s = search.value.toLowerCase()
  return repositories.value.filter(r => r.name.toLowerCase().includes(s) || r.url.toLowerCase().includes(s))
})

const filteredComponents = computed(() => {
  if (!componentSearch.value) return components.value
  const s = componentSearch.value.toLowerCase()
  return components.value.filter(c => c.name.toLowerCase().includes(s))
})

const allComponentsSelected = computed(() =>
  components.value.length > 0 && selectedComponents.value.length === components.value.length
)

// ---- Data loading ----

const loadRepositories = async (reset: boolean = false) => {
  if (!selectedRegistry.value) return
  if (reset) {
    isLoading.value = true
    lastRepo.value = null
  } else {
    isLoadingMore.value = true
  }
  try {
    const registry = registries.value.find(r => r.uuid === selectedRegistry.value)
    const response = await api.get('repositories/get_acr_repos/', {
      params: {
        provider: provider.value,
        registry_uuid: registry?.uuid,
        page_size: pageSize,
        last: lastRepo.value
      }
    })
    if (reset) {
      repositories.value = response.data.repositories
    } else {
      repositories.value = [...repositories.value, ...response.data.repositories]
    }
    lastRepo.value = response.data.pagination.next_page
    hasMore.value = !!lastRepo.value
  } catch (error: any) {
    const msg = error?.response?.data?.error ?? 'Failed to fetch repositories'
    notificationService.error(msg)
  } finally {
    isLoading.value = false
    isLoadingMore.value = false
  }
}

const loadComponents = async () => {
  if (!selectedRepoKey.value || !selectedRegistry.value) return
  componentsLoading.value = true
  components.value = []
  selectedComponents.value = []
  try {
    const registry = registries.value.find(r => r.uuid === selectedRegistry.value)
    const response = await api.get('repositories/get_acr_repos/', {
      params: {
        provider: 'jfrog',
        registry_uuid: registry?.uuid,
        repo_key: selectedRepoKey.value.name,
        package_type: selectedRepoKey.value.package_type || 'docker',
      }
    })
    components.value = response.data.repositories
    selectedComponents.value = [...components.value]
  } catch (error: any) {
    const msg = error?.response?.data?.error ?? 'Failed to load components'
    notificationService.error(msg)
  } finally {
    componentsLoading.value = false
  }
}

const openDialog = async () => {
  if (!selectedRegistry.value) return
  await loadRepositories(true)
  dialog.value = true
  currentStep.value = 1
  selectedRepositories.value = []
  selectedRepoKey.value = null
  components.value = []
  selectedComponents.value = []
  componentSearch.value = ''
  search.value = ''
}

const loadMore = async () => {
  if (!isLoadingMore.value && hasMore.value) {
    await loadRepositories(false)
  }
}

const observerTarget = ref<HTMLElement | null>(null)

onMounted(() => {
  const observer = new IntersectionObserver(
    (entries) => {
      if (entries[0].isIntersecting && hasMore.value && !isLoadingMore.value) {
        loadMore()
      }
    },
    { threshold: 0.1, rootMargin: '100px' }
  )
  watch(observerTarget, (newTarget) => {
    if (newTarget) observer.observe(newTarget)
  })
  return () => {
    if (observerTarget.value) observer.unobserve(observerTarget.value)
  }
})

// ---- Actions ----

const selectRepoKey = (repo: RepoItem) => {
  selectedRepoKey.value = repo
}

const toggleRepository = (repo: RepoItem) => {
  const idx = selectedRepositories.value.findIndex(r => r.url === repo.url)
  if (idx === -1) selectedRepositories.value.push(repo)
  else selectedRepositories.value.splice(idx, 1)
}

const toggleComponent = (comp: RepoItem) => {
  const idx = selectedComponents.value.findIndex(c => c.url === comp.url)
  if (idx === -1) selectedComponents.value.push(comp)
  else selectedComponents.value.splice(idx, 1)
}

const toggleSelectAllComponents = () => {
  if (allComponentsSelected.value) {
    selectedComponents.value = []
  } else {
    selectedComponents.value = [...components.value]
  }
}

const nextStep = async () => {
  if (isJfrog.value && currentStep.value === 1) {
    currentStep.value = 2
    await loadComponents()
    return
  }
  currentStep.value++
}

const submitJob = async () => {
  submitting.value = true
  try {
    const jobData = itemsToSubmit.value.map((repo: RepoItem) => ({
      repository_url: repo.url,
      repository_name: repo.name,
      ...(repo.package_type ? { repository_type: repo.package_type } : {}),
      ...(repo.repo_key ? { repo_key: repo.repo_key } : {}),
    }))

    const response = await api.post('jobs/add-repositories/', {
      repositories: jobData,
      registry_uuid: selectedRegistry.value
    })

    const newRepos = response.data.results.filter((r: any) => r.created)
    const existingRepos = response.data.results.filter((r: any) => !r.created)

    if (newRepos.length > 0) {
      const names = newRepos.map((r: any) => r.repository_name || r.repository).join(', ')
      notificationService.success(`Added new repositories: ${names}`, 10000)
    }
    if (existingRepos.length > 0) {
      const names = existingRepos.map((r: any) => r.repository_name || r.repository).join(', ')
      notificationService.info(`Skipped existing repositories: ${names}`, 10000)
    }

    dialog.value = false
  } catch (error) {
    console.error('Error adding repositories:', error)
    notificationService.error('Failed to add repositories')
  } finally {
    submitting.value = false
  }
}

const loadRegistries = async () => {
  try {
    const resp = await api.get('registries/', { params: { provider: provider.value } })
    registries.value = resp.data.registries ?? []
    if (registries.value.length === 1) {
      selectedRegistry.value = registries.value[0].uuid
    } else {
      selectedRegistry.value = null
    }
  } catch (e) {
    registries.value = []
    selectedRegistry.value = null
  }
}

const onProviderChange = () => {
  selectedRegistry.value = null
  loadRegistries()
}

onMounted(() => {
  loadRegistries()
})
</script>

<style scoped>
.jobs {
  padding: 20px;
  background: #ffffff;
  min-height: 100vh;
}

.dialog-card {
  width: 1000px;
  max-width: 99vw;
  min-width: 340px;
  height: 80vh;
  display: flex;
  flex-direction: column;
  margin: auto;
  overflow: hidden;
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px 32px 16px 32px;
  border-bottom: 1px solid #eee;
  background: #fff;
  position: sticky;
  top: 0;
  z-index: 10;
  font-size: 1.3rem;
}

.acr-dialog :deep(.v-overlay__content) {
  max-height: 80vh;
  margin: auto;
}

.wizard-stepper {
  background: transparent !important;
  height: 100%;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}

:deep(.v-stepper__header) {
  position: sticky;
  top: 64px;
  z-index: 9;
  background: #fff;
  padding: 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
}

.step-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  height: auto;
}

.step-content {
  padding: 0 24px;
}

.scrollable-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  min-height: 0;
  max-height: 45vh;
}

.repository-list {
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 4px;
  overflow: hidden;
  min-height: 200px;
  display: flex;
  flex-direction: column;
}

.repository-item {
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
}

.repository-item:last-child {
  border-bottom: none;
}

.observer-target {
  height: 20px;
  width: 100%;
}

.stepper-actions {
  display: flex;
  align-items: center;
  padding: 16px;
  border-top: 1px solid rgba(0, 0, 0, 0.12);
  position: sticky;
  bottom: 0;
  left: 0;
  right: 0;
  background: white;
  z-index: 10;
  height: 64px;
}

.summary-auto-card {
  height: auto !important;
  min-height: unset !important;
  display: block !important;
  box-shadow: none;
  background: transparent;
}
.summary-auto-content {
  padding: 24px;
}

.summary-list {
  background: transparent;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 8px;
  overflow: hidden;
  margin-top: 12px;
  margin-bottom: 12px;
}

.summary-item {
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
  padding: 12px 16px;
  min-height: 48px;
  display: flex;
  align-items: center;
}

.summary-item:last-child {
  border-bottom: none;
}
</style>
