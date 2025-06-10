<template>
  <div class="jobs">
    <v-container>
      <v-row>
        <v-col cols="12">
          <h1 class="text-h4 mb-4 font-weight-black">Azure Container Registry</h1>
          <v-select
            v-if="acrRegistries.length > 1"
            v-model="selectedRegistry"
            :items="acrRegistries"
            item-title="name"
            item-value="uuid"
            label="Select ACR Registry"
            class="mb-4"
            :disabled="isLoading"
          />
          <v-btn 
            v-if="acrRegistries.length"
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
            Add from ACR
          </v-btn>
          <v-alert v-else type="warning" class="mb-4">
            No Azure Container Registry found in database
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
            <span class="text-h5">Select Repositories</span>
            <v-btn
              icon="mdi-close"
              variant="text"
              @click="dialog = false"
            ></v-btn>
          </div>
          <v-stepper v-model="currentStep" :items="steps" class="wizard-stepper">
            <!-- Step 1: Repository Selection -->
            <template v-slot:item.1>
              <v-card flat class="step-card">
                <v-card-text class="step-content">
                  <v-text-field
                    v-model="search"
                    label="Search repositories"
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
                          :key="repo.uuid || repo.url"
                          :value="repo"
                          class="repository-item"
                          @click="toggleRepository(repo)"
                        >
                          <template v-slot:prepend>
                            <v-checkbox
                              v-model="selectedRepositories"
                              :value="repo"
                              hide-details
                              class="mr-2"
                              @click.stop
                            ></v-checkbox>
                          </template>
                          <v-list-item-title class="text-subtitle-1 font-weight-medium">
                            {{ repo.name }}
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
                        <!-- Loading indicator for infinite scroll -->
                        <div v-if="isLoadingMore" class="text-center py-4">
                          <v-progress-circular
                            indeterminate
                            color="primary"
                            size="24"
                          ></v-progress-circular>
                        </div>
                        <!-- Observer target for infinite scroll -->
                        <div ref="observerTarget" class="observer-target"></div>
                      </template>
                      <template v-else>
                        <v-list-item>
                          <v-list-item-title class="text-center py-4">
                            <v-progress-circular
                              indeterminate
                              color="primary"
                              class="mb-2"
                            ></v-progress-circular>
                            <div>Loading repositories...</div>
                          </v-list-item-title>
                        </v-list-item>
                      </template>
                    </v-list>
                  </div>
                </v-card-text>
              </v-card>
            </template>

            <!-- Step 2: Summary and Confirmation -->
            <template v-slot:item.2>
              <v-card flat class="summary-auto-card">
                <v-card-text class="summary-auto-content">
                  <v-list class="summary-list">
                    <v-list-item
                      v-for="repo in selectedRepositories"
                      :key="repo.uuid || repo.url"
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
                  :disabled="currentStep == 1"
                  variant="text"
                  @click="currentStep--"
                >
                  Previous
                </v-btn>
                <v-spacer></v-spacer>
                <v-btn
                  v-if="currentStep < 2"
                  variant="text"
                  color="primary"
                  @click="nextStep"
                >
                  Next
                </v-btn>
                <v-btn
                  v-else
                  variant="text"
                  color="primary"
                  @click="submitJob"
                  :loading="submitting"
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
import type { Repository, PaginatedResponse } from '../types/interfaces'

const acrRegistries = ref<{uuid: string, name: string, api_url: string}[]>([])
const selectedRegistry = ref<string | null>(null)

const dialog = ref(false)
const currentStep = ref(1)
const search = ref('')
const repositories = ref<Repository[]>([])
const selectedRepositories = ref<Repository[]>([])
const submitting = ref(false)
const isLoading = ref(false)
const hasMore = ref(true)
const isLoadingMore = ref(false)
const pageSize = 50
const lastRepo = ref<string | null>(null)

const steps = [
  { title: 'Select Repositories', description: 'Select the repositories' },
  { title: 'Summary', description: 'Submit repositories' }
]

const repositoryHeaders = [
  { title: 'Name', key: 'name' },
  { title: 'URL', key: 'url' },
]

const filteredRepositories = computed(() => {
  if (!search.value) return repositories.value
  const searchLower = search.value.toLowerCase()
  return repositories.value.filter(repo => 
    repo.name.toLowerCase().includes(searchLower) || repo.url.toLowerCase().includes(searchLower)
  )
})

const loadRepositories = async (reset: boolean = false) => {
  if (!selectedRegistry.value) return
  if (reset) {
    isLoading.value = true
    lastRepo.value = null
  } else {
    isLoadingMore.value = true
  }
  try {
    const registry = acrRegistries.value.find(r => r.uuid === selectedRegistry.value)
    const response = await api.get('repositories/get_acr_repos/', {
      params: {
        provider: 'acr',
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
    console.log('After loadRepositories:', { hasMore: hasMore.value, isLoadingMore: isLoadingMore.value, lastRepo: lastRepo.value })
  } catch (error) {
    notificationService.error('Failed to fetch repositories')
  } finally {
    isLoading.value = false
    isLoadingMore.value = false
  }
}

const openDialog = async () => {
  if (!selectedRegistry.value) return
  await loadRepositories(true)
  dialog.value = true
  currentStep.value = 1
  selectedRepositories.value = []
}

const loadMore = async () => {
  if (!isLoadingMore.value && hasMore.value) {
    await loadRepositories(false)
  }
}

// Add intersection observer for infinite scroll
const observerTarget = ref<HTMLElement | null>(null)

onMounted(() => {
  const observer = new IntersectionObserver(
    (entries) => {
      if (entries[0].isIntersecting && hasMore.value && !isLoadingMore.value) {
        console.log('Observer triggered - loading more repositories')
        loadMore()
      }
    },
    { 
      threshold: 0.1,
      rootMargin: '100px'
    }
  )

  // Watch for changes in the observer target
  watch(observerTarget, (newTarget) => {
    if (newTarget) {
      console.log('Observer target mounted, starting observation')
      observer.observe(newTarget)
    }
  })

  return () => {
    if (observerTarget.value) {
      console.log('Cleaning up observer')
      observer.unobserve(observerTarget.value)
    }
  }
})

const nextStep = () => {
  currentStep.value++
}

const submitJob = async () => {
  submitting.value = true
  try {
    const jobData = selectedRepositories.value
      .map((repo: any) => ({
        repository_url: repo.url,
        repository_name: repo.name
      }))

    const response = await api.post('jobs/add-repositories/', {
      repositories: jobData,
      registry_uuid: selectedRegistry.value
    })
    console.log('Job created:', response.data)
    
    const newRepos = response.data.results.filter((r: any) => r.created)
    const existingRepos = response.data.results.filter((r: any) => !r.created)
    
    if (newRepos.length > 0) {
      const newRepoNames = newRepos.map((r: any) => r.repository_name || r.repository).join(', ')
      notificationService.success(`Added new repositories: ${newRepoNames}`, 10000)
    }
    
    if (existingRepos.length > 0) {
      const existingRepoNames = existingRepos.map((r: any) => r.repository_name || r.repository).join(', ')
      notificationService.info(`Skipped existing repositories: ${existingRepoNames}`, 10000)
    }
    
    dialog.value = false
  } catch (error) {
    console.error('Error adding repositories:', error)
    notificationService.error('Failed to add repositories')
  } finally {
    submitting.value = false
  }
}

const toggleRepository = (repo: Repository) => {
  const index = selectedRepositories.value.findIndex((r: Repository) => r.url === repo.url)
  if (index === -1) {
    selectedRepositories.value.push(repo)
  } else {
    selectedRepositories.value.splice(index, 1)
  }
}

onMounted(async () => {
  try {
    const resp = await api.get('acr_registries/')
    acrRegistries.value = resp.data.registries
    if (acrRegistries.value.length === 1) {
      selectedRegistry.value = acrRegistries.value[0].uuid
    }
  } catch (e) {
    acrRegistries.value = []
  }
})
</script>

<style scoped>
.jobs {
  padding: 20px;
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
/* Make stepper actions static for summary step */
.summary-auto-card + .stepper-actions {
  position: static !important;
  margin-top: 0;
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