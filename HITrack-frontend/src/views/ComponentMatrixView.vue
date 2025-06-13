<template>
  <div class="component-matrix-view">
    <v-container fluid class="pa-0">
      <v-row justify="center">
        <v-col cols="12" md="11" lg="10" xl="9">
          <h1 class="text-h4 mb-4 font-weight-black">Component Matrix</h1>
          <v-card class="mb-4 d-flex flex-column wide-card">
            <v-card-text>
              <v-autocomplete
                v-model="selectedRepos"
                :items="repositories"
                item-title="name"
                item-value="uuid"
                label="Select repositories"
                multiple
                chips
                clearable
                class="mb-4"
                :loading="reposLoading"
                :disabled="reposLoading"
              />
              <v-btn color="primary" :disabled="selectedRepos.length === 0 || loading" @click="fetchMatrix" :loading="loading">
                Build Matrix
              </v-btn>
            </v-card-text>
          </v-card>

          <v-card v-if="matrixData" class="wide-card">
            <v-card-text>
              <div class="matrix-scroll">
                <table class="matrix-table">
                  <thead>
                    <tr>
                      <th class="sticky-col">Component</th>
                      <th v-for="col in matrixData.columns" :key="col.label">{{ col.label }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="component in matrixData.components" :key="component">
                      <td class="sticky-col">{{ component }}</td>
                      <td
                        v-for="col in matrixData.columns"
                        :key="col.label"
                        :class="getCellBgClass(matrixData.matrix[component][col.label])"
                      >
                        <div class="d-flex align-center justify-center">
                          <v-chip
                            v-if="matrixData.matrix[component][col.label].version"
                            color="primary"
                            size="small"
                            class="font-weight-medium mr-1"
                          >
                            {{ matrixData.matrix[component][col.label].version }}
                            <v-tooltip v-if="matrixData.matrix[component][col.label].has_vuln" location="top">
                              <template #activator="{ props }">
                                <v-icon
                                  v-bind="props"
                                  color="error"
                                  size="x-small"
                                  class="ml-1"
                                  style="vertical-align: middle;"
                                >
                                  mdi-spider
                                </v-icon>
                              </template>
                              Vulnerable
                            </v-tooltip>
                          </v-chip>
                          <v-tooltip v-if="matrixData.matrix[component][col.label].version && matrixData.matrix[component][col.label].latest_version" location="top">
                            <template #activator="{ props }">
                              <v-icon
                                v-if="matrixData.matrix[component][col.label].latest_version"
                                v-bind="props"
                                :color="getVersionStatusColor(matrixData.matrix[component][col.label])"
                                size="small"
                              >
                                {{ getVersionStatusIcon(matrixData.matrix[component][col.label]) }}
                              </v-icon>
                            </template>
                            <span v-if="matrixData.matrix[component][col.label].version !== matrixData.matrix[component][col.label].latest_version">
                              New version available: {{ matrixData.matrix[component][col.label].latest_version }}
                            </span>
                            <span v-else>
                              Version is up to date
                            </span>
                          </v-tooltip>
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </v-container>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '../plugins/axios'
import { notificationService } from '../plugins/notifications'

const repositories = ref<any[]>([])
const reposLoading = ref(false)
const selectedRepos = ref<string[]>([])
const loading = ref(false)
const matrixData = ref<any | null>(null)

const fetchRepositories = async () => {
  reposLoading.value = true
  try {
    const resp = await api.get('repositories/', { params: { page_size: 1000 } })
    repositories.value = resp.data.results
  } catch (e) {
    notificationService.error('Failed to fetch repositories')
  } finally {
    reposLoading.value = false
  }
}

const getCellBgClass = (versionData: any) => {
  if (!versionData || !versionData.version || !versionData.latest_version) return ''
  if (versionData.version === versionData.latest_version) {
    return 'cell-up-to-date'
  }
  return 'cell-outdated'
}

const getVersionStatusColor = (versionData: any) => {
  if (!versionData.latest_version) return ''
  if (versionData.version === versionData.latest_version) return 'success'
  return 'error'
}

const getVersionStatusIcon = (versionData: any) => {
  if (!versionData.latest_version) return ''
  if (versionData.version === versionData.latest_version) return 'mdi-check'
  return 'mdi-arrow-up-bold'
}

const fetchMatrix = async () => {
  if (selectedRepos.value.length === 0) return
  loading.value = true
  try {
    const resp = await api.post('component-matrix/', {
      repository_uuids: selectedRepos.value
    })
    matrixData.value = resp.data
  } catch (e) {
    notificationService.error('Failed to fetch component matrix')
  } finally {
    loading.value = false
  }
}

onMounted(fetchRepositories)
</script>

<style scoped>
.component-matrix-view {
  padding: 20px;
}
.wide-card {
  width: 100%;
  max-width: 100%;
  min-width: 900px;
  box-sizing: border-box;
}
.matrix-scroll {
  width: 100%;
  overflow-x: auto;
  overflow-y: auto;
  max-height: 70vh;
}
.matrix-table {
  border-collapse: collapse;
  font-size: 0.65rem;
  min-width: 250px;
}
.matrix-table th, .matrix-table td {
  border: 1px solid #e0e0e0;
  padding: 4px 10px;
  text-align: center;
  white-space: nowrap;
}
.matrix-table th {
  background: #f8f9fa;
  font-weight: 700;
  position: sticky;
  top: 0;
  z-index: 2;
}
.sticky-col {
  position: sticky;
  left: 0;
  background: #fff;
  z-index: 3;
  font-weight: 700;
  text-align: left !important;
}
.matrix-table tr:hover td {
  background: #f5f5f5;
}
.cell-up-to-date {
  background-color: #e8f5e9 !important;
}
.cell-outdated {
  background-color: #ffebee !important;
}
</style> 