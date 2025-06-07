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

      <v-dialog v-model="dialog" max-width="800px">
        <v-card>
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
                          <v-chip
                            size="x-small"
                            color="purple-lighten-1"
                            variant="outlined"
                            class="ml-2"
                            density="compact"
                          >
                            {{ repo.tag_count }} tags
                          </v-chip>
                        </v-list-item-title>
                      </v-list-item>
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
                </v-card-text>
              </v-card>
            </template>

            <!-- Step 2: Scanning Options -->
            <template v-slot:item.2>
              <v-card flat class="step-card" title="Choose versions to scan for each repository">
                <v-card-text class="step-content">
                  <v-table>
                    <thead>
                      <tr>
                        <th class="text-subtitle-1 font-weight-medium">Repository</th>
                        <th class="text-subtitle-1 font-weight-medium text-center">Last version</th>
                        <th class="text-subtitle-1 font-weight-medium text-center">Last 10</th>
                        <th class="text-subtitle-1 font-weight-medium text-center">All</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="repo in selectedRepositories" :key="repo.uuid || repo.url">
                        <td class="text-subtitle-1">{{ repo.name }}</td>
                        <td class="text-center">
                          <v-radio-group
                            v-model="scanOptions[repo.url]"
                            hide-details
                            class="radio-group"
                          >
                            <v-radio
                              value="last"
                              color="primary"
                              hide-details
                            ></v-radio>
                          </v-radio-group>
                        </td>
                        <td class="text-center">
                          <v-radio-group
                            v-model="scanOptions[repo.url]"
                            hide-details
                            class="radio-group"
                          >
                            <v-radio
                              value="last10"
                              color="primary"
                              hide-details
                            ></v-radio>
                          </v-radio-group>
                        </td>
                        <td class="text-center">
                          <v-radio-group
                            v-model="scanOptions[repo.url]"
                            hide-details
                            class="radio-group"
                          >
                            <v-radio
                              value="all"
                              color="primary"
                              hide-details
                            ></v-radio>
                          </v-radio-group>
                        </td>
                      </tr>
                    </tbody>
                  </v-table>
                </v-card-text>
              </v-card>
            </template>

            <!-- Step 3: Summary and Confirmation -->
            <template v-slot:item.3>
              <v-card flat class="step-card" title="Summary for chosen repositories">
                <v-card-text class="step-content">
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
                      <template v-slot:append>
                        <v-chip
                          size="small"
                          :color="getScanOptionColor(scanOptions[repo.url])"
                          class="text-caption ml-2"
                        >
                          {{ getScanOptionLabel(scanOptions[repo.url]) }}
                        </v-chip>
                      </template>
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
                  v-if="currentStep < 3"
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
import { ref, computed, onMounted } from 'vue'
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
const scanOptions = ref<Record<string, string>>({})
const submitting = ref(false)
const isLoading = ref(false)

const steps = [
  { title: 'Select Repositories', description: 'Select the repositories' },
  { title: 'Scanning options', description: 'Select tags to scan for each repository' },
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

const getScanOptionLabel = (option: string) => {
  switch (option) {
    case 'all': return 'Scan all tags'
    case 'last10': return 'Scan last 10 tags'
    case 'last': return 'Scan last tag only'
    default: return 'Not selected'
  }
}

const getScanOptionColor = (option: string) => {
  switch (option) {
    case 'last': return 'info'
    case 'last10': return 'warning'
    case 'all': return 'success'
    default: return 'grey'
  }
}

const openDialog = async () => {
  if (!selectedRegistry.value) return
  isLoading.value = true
  try {
    const registry = acrRegistries.value.find(r => r.uuid === selectedRegistry.value)
    const response = await api.get('repositories/get_acr_repos/', {
      params: {
        provider: 'acr',
        registry_uuid: registry?.uuid
      }
    })
    repositories.value = response.data.repositories
    dialog.value = true
    currentStep.value = 1
    selectedRepositories.value = []
    scanOptions.value = {}
  } catch (error) {
    notificationService.error('Failed to fetch repositories')
  } finally {
    isLoading.value = false
  }
}

const nextStep = () => {
  if (currentStep.value === 1) {
    selectedRepositories.value.forEach(repo => {
      if (!scanOptions.value[repo.url]) {
        scanOptions.value[repo.url] = 'last'
      }
    })
  }
  currentStep.value++
}

const submitJob = async () => {
  submitting.value = true
  try {
    const jobData = selectedRepositories.value
      .map((repo: any) => ({
        repository_url: repo.url,
        repository_name: repo.name,
        scan_option: scanOptions.value[repo.url] || 'last'
      }))

    const response = await api.post('jobs/scan-repositories/', { repositories: jobData })
    console.log('Job created:', response.data)
    
    const newRepos = response.data.results.filter((r: any) => r.created)
    const existingRepos = response.data.results.filter((r: any) => !r.created)
    
    if (newRepos.length > 0) {
      const newRepoNames = newRepos.map((r: any) => r.repository_name || r.repository).join(', ')
      notificationService.success(`Started scanning new repositories: ${newRepoNames}`, 10000)
    }
    
    if (existingRepos.length > 0) {
      const existingRepoNames = existingRepos.map((r: any) => r.repository_name || r.repository).join(', ')
      notificationService.info(`Skipped existing repositories: ${existingRepoNames}`, 10000)
    }
    
    dialog.value = false
  } catch (error) {
    console.error('Error creating job:', error)
    notificationService.error('Failed to create job')
  } finally {
    submitting.value = false
  }
}

const toggleRepository = (repo: Repository) => {
  const index = selectedRepositories.value.findIndex((r: Repository) => r.url === repo.url)
  if (index === -1) {
    selectedRepositories.value.push(repo)
    scanOptions.value[repo.url] = 'last'
  } else {
    selectedRepositories.value.splice(index, 1)
    delete scanOptions.value[repo.url]
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

.wizard-stepper {
  background: transparent !important;
  height: 600px;
  display: flex;
  flex-direction: column;
  position: relative;
}

.step-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding-bottom: 64px;
  height: 500px;
}

.step-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  height: calc(100% - 32px);
}

.repository-list {
  border: 1px solid;
  border-radius: 4px;
  overflow: hidden;
}

.repository-item {
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
}

.repository-item:last-child {
  border-bottom: none;
}

.stepper-actions {
  display: flex;
  align-items: center;
  padding: 16px;
  border-top: 1px solid rgba(0, 0, 0, 0.12);
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: white;
  z-index: 2;
  height: 64px;
}

.scan-options-list {
  background: transparent;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 8px;
  overflow: hidden;
}

.scan-option-item {
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
  padding: 16px;
}

.scan-option-item:last-child {
  border-bottom: none;
}

:deep(.v-table) {
  background: transparent;
}

:deep(.v-table .v-table__wrapper > table) {
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 8px;
}

:deep(.v-table .v-table__wrapper > table > thead > tr > th) {
  font-weight: 600;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
  font-size: 1rem;
  line-height: 1.5;
}

:deep(.v-table .v-table__wrapper > table > tbody > tr > td) {
  padding: 12px 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
  font-size: 1rem;
  line-height: 1.5;
}

:deep(.v-table .v-table__wrapper > table > tbody > tr:last-child > td) {
  border-bottom: none;
}

:deep(.radio-group) {
  margin: 0;
  padding: 0;
  display: flex;
  justify-content: center;
}

:deep(.radio-group .v-radio) {
  margin: 0;
  padding: 0;
}

:deep(.radio-group .v-radio__input) {
  margin-right: 0;
}

:deep(.radio-group .v-radio__label) {
  display: none;
}

.summary-list {
  background: transparent;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 8px;
  overflow: hidden;
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

:deep(.v-list-item__content) {
  padding: 0;
}

:deep(.v-list-item-title) {
  font-size: 1rem;
  line-height: 1.5;
}

:deep(.v-list-item-subtitle) {
  font-size: 0.875rem;
  line-height: 1.25;
}

:deep(.v-chip) {
  font-size: 0.65rem;
  line-height: 1.2;
  height: 20px;
  font-family: monospace;
  padding: 0 6px;
}

:deep(.v-chip .v-chip__content) {
  padding: 0 2px;
}

:deep(.v-text-field .v-field__input) {
  font-size: 1rem;
  line-height: 1.5;
}

:deep(.v-list-item-title) {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.v-progress-circular {
  margin: 0 8px;
}

.repository-list {
  min-height: 200px;
  display: flex;
  flex-direction: column;
}

.repository-list .v-list-item {
  flex: 0 0 auto;
}
</style> 