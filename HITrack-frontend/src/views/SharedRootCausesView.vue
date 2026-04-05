<template>
  <div class="shared-root-causes-page">
    <v-container fluid class="page-shell wide-page-shell">
      <div class="page-header">
        <div>
          <h1 class="text-h4 font-weight-bold mb-2">Shared Root Causes</h1>
          <p class="text-body-1 text-medium-emphasis">
            Group vulnerabilities by the shared component version that introduces them across repositories and images.
          </p>
        </div>
        <v-tooltip location="left" max-width="360">
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              icon="mdi-help-circle-outline"
              variant="text"
              color="primary"
              size="small"
              aria-label="How to read shared root causes"
            />
          </template>
          <div class="tooltip-copy">
            <div><strong>Shared root cause</strong> means one component version spreading risk across multiple images or repositories.</div>
            <div><strong>Risk</strong> combines severity, EPSS, KEV, exploit signals and fixability.</div>
            <div><strong>Fixability</strong> tells whether a practical fix is available now, not yet in repo, missing, or unknown.</div>
          </div>
        </v-tooltip>
      </div>

      <v-card elevation="2" class="root-causes-card">
        <v-card-text class="pb-0">
          <div class="filters-bar">
            <v-text-field
              v-model="search"
              label="Search component or version"
              placeholder="openssl, axios, 9.0.0"
              prepend-inner-icon="mdi-magnify"
              density="comfortable"
              variant="outlined"
              hide-details
              class="root-causes-search"
              @keyup.enter="applySearch"
              @click:prepend-inner="applySearch"
            />

            <v-select
              v-model="componentType"
              :items="componentTypeOptions"
              label="Package type"
              density="comfortable"
              variant="outlined"
              hide-details
              class="root-causes-filter"
            />

            <v-select
              v-model="scope"
              :items="scopeOptions"
              label="Scope"
              density="comfortable"
              variant="outlined"
              hide-details
              class="root-causes-filter"
            />

            <v-select
              v-model="fixability"
              :items="fixabilityOptions"
              label="Fixability"
              density="comfortable"
              variant="outlined"
              hide-details
              class="root-causes-filter"
            />
          </div>
        </v-card-text>

        <v-card-text class="pa-0">
          <v-data-table-server
            :headers="headers"
            :items="items"
            :items-length="totalItems"
            :page="page"
            :items-per-page="itemsPerPage"
            :loading="loading"
            item-value="uuid"
            class="root-causes-table"
            @update:options="onTableOptionsUpdate"
          >
            <template #header.component_name>
              <div class="header-with-help">
                <span>Component Version</span>
                <v-tooltip location="top" max-width="300">
                  <template #activator="{ props }">
                    <v-icon v-bind="props" size="16" class="help-icon">mdi-help-circle-outline</v-icon>
                  </template>
                  <span>The exact package version acting as the shared source of vulnerabilities across assets.</span>
                </v-tooltip>
              </div>
            </template>
            <template #header.affected_repositories_count>
              <div class="header-with-help">
                <span>Repos</span>
                <v-tooltip location="top" max-width="300">
                  <template #activator="{ props }">
                    <v-icon v-bind="props" size="16" class="help-icon">mdi-help-circle-outline</v-icon>
                  </template>
                  <span>How many distinct repositories currently include this component version in successful scans.</span>
                </v-tooltip>
              </div>
            </template>
            <template #header.affected_images_count>
              <div class="header-with-help">
                <span>Images</span>
                <v-tooltip location="top" max-width="300">
                  <template #activator="{ props }">
                    <v-icon v-bind="props" size="16" class="help-icon">mdi-help-circle-outline</v-icon>
                  </template>
                  <span>How many scanned images currently carry this component version.</span>
                </v-tooltip>
              </div>
            </template>
            <template #header.vulnerabilities_count>
              <div class="header-with-help">
                <span>Vulns</span>
                <v-tooltip location="top" max-width="320">
                  <template #activator="{ props }">
                    <v-icon v-bind="props" size="16" class="help-icon">mdi-help-circle-outline</v-icon>
                  </template>
                  <span>Total unique vulnerabilities linked to this component version. Chips highlight the most severe subset.</span>
                </v-tooltip>
              </div>
            </template>
            <template #header.kev_vulnerabilities_count>
              <div class="header-with-help">
                <span>Signals</span>
                <v-tooltip location="top" max-width="320">
                  <template #activator="{ props }">
                    <v-icon v-bind="props" size="16" class="help-icon">mdi-help-circle-outline</v-icon>
                  </template>
                  <span>Threat signals such as CISA KEV presence or public exploit availability for vulnerabilities in this root cause.</span>
                </v-tooltip>
              </div>
            </template>
            <template #header.fixability>
              <div class="header-with-help">
                <span>Fixability</span>
                <v-tooltip location="top" max-width="340">
                  <template #activator="{ props }">
                    <v-icon v-bind="props" size="16" class="help-icon">mdi-help-circle-outline</v-icon>
                  </template>
                  <span>Best current fix state across the linked vulnerabilities: ready now, known but unavailable in repo, no fix, or unknown.</span>
                </v-tooltip>
              </div>
            </template>
            <template #header.weighted_risk_score>
              <div class="header-with-help">
                <span>Risk</span>
                <v-tooltip location="top" max-width="340">
                  <template #activator="{ props }">
                    <v-icon v-bind="props" size="16" class="help-icon">mdi-help-circle-outline</v-icon>
                  </template>
                  <span>Weighted score based on severity, EPSS, KEV, exploit availability, ransomware signal, current presence and fixability.</span>
                </v-tooltip>
              </div>
            </template>
            <template #header.latest_seen_at>
              <div class="header-with-help">
                <span>Updated</span>
                <v-tooltip location="top" max-width="300">
                  <template #activator="{ props }">
                    <v-icon v-bind="props" size="16" class="help-icon">mdi-help-circle-outline</v-icon>
                  </template>
                  <span>Most recent time this root cause was observed in successful image scans.</span>
                </v-tooltip>
              </div>
            </template>
            <template #item="{ item }">
              <template v-if="item">
                <tr class="root-cause-row">
                  <td class="root-cause-row__expand">
                    <v-btn
                      size="small"
                      variant="text"
                      color="primary"
                      :icon="isExpanded(item.uuid) ? 'mdi-chevron-up' : 'mdi-chevron-down'"
                      @click.stop="toggleExpanded(item.uuid)"
                    />
                  </td>
                  <td>
                    <div class="component-cell">
                      <button
                        type="button"
                        class="component-link"
                        @click="openComponentVersion(item.uuid)"
                      >
                        {{ item.component_name }}@{{ item.version }}
                      </button>
                      <div class="component-cell__meta">
                        <span>{{ item.component_type || 'unknown' }}</span>
                        <span v-if="item.latest_version">Latest {{ item.latest_version }}</span>
                      </div>
                    </div>
                  </td>
                  <td>{{ item.affected_repositories_count }}</td>
                  <td>{{ item.affected_images_count }}</td>
                  <td>
                    <div class="vuln-count-cell">
                      <span>{{ item.vulnerabilities_count }}</span>
                      <div class="vuln-count-cell__chips">
                        <v-chip
                          v-if="item.critical_vulnerabilities_count"
                          size="x-small"
                          color="error"
                          variant="tonal"
                        >
                          {{ item.critical_vulnerabilities_count }} critical
                        </v-chip>
                        <v-chip
                          v-if="item.high_vulnerabilities_count"
                          size="x-small"
                          color="warning"
                          variant="tonal"
                        >
                          {{ item.high_vulnerabilities_count }} high
                        </v-chip>
                      </div>
                    </div>
                  </td>
                  <td>
                    <div class="flag-chip-stack">
                      <v-chip
                        v-if="item.kev_vulnerabilities_count"
                        size="x-small"
                        color="warning"
                        variant="tonal"
                      >
                        {{ item.kev_vulnerabilities_count }} KEV
                      </v-chip>
                      <v-chip
                        v-if="item.exploit_vulnerabilities_count"
                        size="x-small"
                        color="error"
                        variant="tonal"
                      >
                        {{ item.exploit_vulnerabilities_count }} exploit
                      </v-chip>
                    </div>
                  </td>
                  <td>
                    <div class="flag-chip-stack">
                      <v-chip size="small" :color="fixabilityColor(item.fixability_category)" variant="tonal">
                        {{ fixabilityLabel(item.fixability_category) }}
                      </v-chip>
                      <div class="text-caption text-medium-emphasis">
                        {{ item.fixability_breakdown.fixable_now }} / {{ item.vulnerabilities_count }} ready
                      </div>
                    </div>
                  </td>
                  <td>
                    <v-chip size="small" color="primary" variant="tonal">
                      Risk {{ formatRiskScore(item.weighted_risk_score) }}
                    </v-chip>
                  </td>
                  <td>
                    <div class="date-meta-cell">
                      <div class="date-meta-cell__primary nowrap">{{ $formatDate(item.latest_seen_at) }}</div>
                    </div>
                  </td>
                </tr>

                <tr v-if="isExpanded(item.uuid)" class="root-cause-row root-cause-row--expanded">
                  <td :colspan="headers.length">
                    <div class="expanded-panel">
                      <div class="expanded-grid">
                        <div class="expanded-card">
                          <div class="expanded-card__title-row">
                            <div class="expanded-card__title">Affected repositories</div>
                            <v-tooltip location="top" max-width="300">
                              <template #activator="{ props }">
                                <v-icon v-bind="props" size="16" class="help-icon">mdi-help-circle-outline</v-icon>
                              </template>
                              <span>Repositories where this exact component version is currently present, with a preview of impacted images and tags.</span>
                            </v-tooltip>
                          </div>
                          <div v-if="isPreviewLoading(item.uuid)" class="text-body-2 text-medium-emphasis">
                            Loading repository preview...
                          </div>
                          <div v-else-if="!item.repositories_preview.length" class="text-body-2 text-medium-emphasis">
                            No repository preview available.
                          </div>
                          <div v-else class="preview-list">
                            <button
                              v-for="repository in item.repositories_preview"
                              :key="`${item.uuid}-${repository.repository_uuid}`"
                              type="button"
                              class="preview-pill"
                              @click="openRepository(repository.repository_uuid)"
                            >
                              <span class="preview-pill__title">{{ repository.repository_name }}</span>
                              <span class="preview-pill__meta">
                                {{ repository.affected_images_count }} images · {{ repository.affected_tags_count }} tags
                              </span>
                            </button>
                          </div>
                        </div>

                        <div class="expanded-card">
                          <div class="expanded-card__title-row">
                            <div class="expanded-card__title">Top vulnerabilities carried by this component</div>
                            <v-tooltip location="top" max-width="320">
                              <template #activator="{ props }">
                                <v-icon v-bind="props" size="16" class="help-icon">mdi-help-circle-outline</v-icon>
                              </template>
                              <span>Highest-priority vulnerabilities linked to this component version, ordered by severity and EPSS.</span>
                            </v-tooltip>
                          </div>
                          <div v-if="isPreviewLoading(item.uuid)" class="text-body-2 text-medium-emphasis">
                            Loading vulnerability preview...
                          </div>
                          <div v-else-if="!item.vulnerabilities_preview.length" class="text-body-2 text-medium-emphasis">
                            No vulnerability preview available.
                          </div>
                          <div v-else class="preview-list">
                            <button
                              v-for="vulnerability in item.vulnerabilities_preview"
                              :key="`${item.uuid}-${vulnerability.uuid}`"
                              type="button"
                              class="preview-pill preview-pill--vulnerability"
                              @click="openVulnerability(vulnerability.uuid)"
                            >
                              <span class="preview-pill__title">
                                {{ vulnerability.vulnerability_id }}
                              </span>
                              <span class="preview-pill__meta">
                                {{ vulnerability.severity }} · EPSS {{ vulnerability.epss.toFixed(3) }}
                                <span v-if="vulnerability.cisa_kev"> · KEV</span>
                                <span v-if="vulnerability.exploit_available"> · Exploit</span>
                              </span>
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  </td>
                </tr>
              </template>
            </template>
          </v-data-table-server>
        </v-card-text>
      </v-card>
    </v-container>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '../plugins/axios'
import type { SharedRootCause, SharedRootCausePreviewResponse, SharedRootCauseResponse } from '../types/interfaces'

const router = useRouter()

const items = ref<SharedRootCause[]>([])
const totalItems = ref(0)
const loading = ref(false)
const page = ref(1)
const itemsPerPage = ref(25)
const sortBy = ref<{ key: string; order: 'asc' | 'desc' }[]>([
  { key: 'weighted_risk_score', order: 'desc' },
])
const expandedIds = ref<string[]>([])
const previewLoadingIds = ref<string[]>([])
const search = ref('')
const appliedSearch = ref('')
const componentType = ref('all')
const scope = ref('cross_repository')
const fixability = ref('all')
const lastOptionsKey = ref('')
const PREFETCH_PREVIEW_LIMIT = 4

const headers = [
  { title: '', key: 'expand', sortable: false, width: 56 },
  { title: 'Component Version', key: 'component_name', sortable: true, minWidth: 280 },
  { title: 'Repos', key: 'affected_repositories_count', sortable: true, width: 90 },
  { title: 'Images', key: 'affected_images_count', sortable: true, width: 90 },
  { title: 'Vulns', key: 'vulnerabilities_count', sortable: true, minWidth: 160 },
  { title: 'Signals', key: 'kev_vulnerabilities_count', sortable: true, minWidth: 130 },
  { title: 'Fixability', key: 'fixability', sortable: false, minWidth: 160 },
  { title: 'Risk', key: 'weighted_risk_score', sortable: true, width: 120 },
  { title: 'Updated', key: 'latest_seen_at', sortable: true, minWidth: 150 },
]

const componentTypeOptions = [
  { title: 'All types', value: 'all' },
  { title: 'deb', value: 'deb' },
  { title: 'rpm', value: 'rpm' },
  { title: 'apk', value: 'apk' },
  { title: 'npm', value: 'npm' },
  { title: 'pip', value: 'pip' },
  { title: 'nuget', value: 'nuget' },
  { title: 'maven', value: 'maven' },
  { title: 'go', value: 'go' },
  { title: 'generic', value: 'generic' },
]

const scopeOptions = [
  { title: 'Cross-repository', value: 'cross_repository' },
  { title: 'All', value: 'all' },
  { title: 'Single repository only', value: 'single_repository' },
]

const fixabilityOptions = [
  { title: 'All', value: 'all' },
  { title: 'Fixable now', value: 'fixable_now' },
  { title: 'Fix exists, not in repo', value: 'fix_exists_but_not_in_repo' },
  { title: 'No fix', value: 'no_fix' },
  { title: 'Unknown', value: 'fix_unknown' },
]

const currentOrdering = computed(() => {
  const current = sortBy.value[0]
  if (!current?.key) {
    return '-weighted_risk_score'
  }
  return `${current.order === 'desc' ? '-' : ''}${current.key}`
})

const buildOptionsKey = () => JSON.stringify({
  page: page.value,
  itemsPerPage: itemsPerPage.value,
  ordering: currentOrdering.value,
  search: appliedSearch.value,
  componentType: componentType.value,
  scope: scope.value,
  fixability: fixability.value,
})

const fetchRootCauses = async () => {
  loading.value = true
  try {
    const response = await api.get<SharedRootCauseResponse>('stats/shared-root-causes/', {
      params: {
        page: page.value,
        page_size: itemsPerPage.value,
        ordering: currentOrdering.value,
        search: appliedSearch.value || undefined,
        component_type: componentType.value,
        scope: scope.value,
        fixability: fixability.value,
      },
    })
    items.value = response.data.results || []
    items.value = items.value.map((item) => ({
      ...item,
      repositories_preview: item.repositories_preview || [],
      vulnerabilities_preview: item.vulnerabilities_preview || [],
      previews_loaded: false,
    }))
    totalItems.value = response.data.count || 0
    const optionsKey = buildOptionsKey()
    void prefetchVisiblePreviews(optionsKey)
  } finally {
    loading.value = false
  }
}

const refreshIfNeeded = async () => {
  const nextKey = buildOptionsKey()
  if (nextKey === lastOptionsKey.value) {
    return
  }
  lastOptionsKey.value = nextKey
  await fetchRootCauses()
}

const onTableOptionsUpdate = (options: {
  page?: number
  itemsPerPage?: number
  sortBy?: { key: string; order?: 'asc' | 'desc' }[]
}) => {
  const nextPage = options.page || 1
  const nextItemsPerPage = options.itemsPerPage || 25
  const nextSortBy: { key: string; order: 'asc' | 'desc' }[] = (options.sortBy || []).map((item) => ({
    key: item.key,
    order: item.order === 'asc' ? 'asc' : 'desc',
  }))

  const nextKey = JSON.stringify({
    page: nextPage,
    itemsPerPage: nextItemsPerPage,
    sortBy: nextSortBy,
  })
  const currentKey = JSON.stringify({
    page: page.value,
    itemsPerPage: itemsPerPage.value,
    sortBy: sortBy.value,
  })
  if (nextKey === currentKey) {
    return
  }

  page.value = nextPage
  itemsPerPage.value = nextItemsPerPage
  sortBy.value = nextSortBy.length ? nextSortBy : [{ key: 'weighted_risk_score', order: 'desc' }]
}

const applySearch = async () => {
  appliedSearch.value = search.value.trim()
  page.value = 1
  await refreshIfNeeded()
}

watch([componentType, scope, fixability], async () => {
  page.value = 1
  await refreshIfNeeded()
})

watch([page, itemsPerPage, sortBy], async () => {
  await refreshIfNeeded()
}, { deep: true })

const isExpanded = (uuid: string) => expandedIds.value.includes(uuid)
const isPreviewLoading = (uuid: string) => previewLoadingIds.value.includes(uuid)

const fetchPreview = async (uuid: string) => {
  if (isPreviewLoading(uuid)) {
    return
  }

  previewLoadingIds.value = [...previewLoadingIds.value, uuid]
  try {
    const response = await api.get<SharedRootCausePreviewResponse>('stats/shared-root-causes-preview/', {
      params: {
        component_version_uuid: uuid,
      },
    })
    items.value = items.value.map((item) => item.uuid === uuid ? {
      ...item,
      repositories_preview: response.data.repositories_preview || [],
      vulnerabilities_preview: response.data.vulnerabilities_preview || [],
      previews_loaded: true,
    } : item)
  } finally {
    previewLoadingIds.value = previewLoadingIds.value.filter((value) => value !== uuid)
  }
}

const prefetchVisiblePreviews = async (optionsKey: string) => {
  const candidates = items.value
    .filter((item) => !item.previews_loaded)
    .slice(0, PREFETCH_PREVIEW_LIMIT)

  for (const item of candidates) {
    if (lastOptionsKey.value !== optionsKey) {
      return
    }
    if (isPreviewLoading(item.uuid)) {
      continue
    }
    await fetchPreview(item.uuid)
  }
}

const toggleExpanded = async (uuid: string) => {
  if (isExpanded(uuid)) {
    expandedIds.value = expandedIds.value.filter((value) => value !== uuid)
    return
  }

  expandedIds.value = [...expandedIds.value, uuid]
  const item = items.value.find((entry) => entry.uuid === uuid)
  if (item && !item.previews_loaded) {
    await fetchPreview(uuid)
  }
}

const openComponentVersion = (uuid: string) => {
  router.push(`/component-versions/${uuid}`)
}

const openRepository = (uuid: string) => {
  router.push(`/repositories/${uuid}`)
}

const openVulnerability = (uuid: string) => {
  router.push(`/vulnerabilities/${uuid}`)
}

const fixabilityLabel = (value: string) => {
  switch (value) {
    case 'fixable_now':
      return 'Fixable now'
    case 'fix_exists_but_not_in_repo':
      return 'Not in repo'
    case 'no_fix':
      return 'No fix'
    default:
      return 'Unknown'
  }
}

const fixabilityColor = (value: string) => {
  switch (value) {
    case 'fixable_now':
      return 'success'
    case 'fix_exists_but_not_in_repo':
      return 'warning'
    case 'no_fix':
      return 'error'
    default:
      return 'grey'
  }
}

const formatRiskScore = (value: number) => Number(value || 0).toFixed(1)

refreshIfNeeded()
</script>

<style scoped>
.filters-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: center;
}

.root-causes-search {
  flex: 1 1 320px;
  min-width: 260px;
}

.root-causes-filter {
  flex: 0 1 220px;
  min-width: 180px;
}

.root-cause-row__expand {
  width: 56px;
}

.component-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.component-link {
  border: 0;
  background: transparent;
  color: rgb(var(--v-theme-primary));
  text-align: left;
  font-weight: 600;
  cursor: pointer;
}

.component-link:hover {
  text-decoration: underline;
}

.component-cell__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  color: rgba(0, 0, 0, 0.6);
  font-size: 0.8rem;
}

.vuln-count-cell {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.vuln-count-cell__chips,
.flag-chip-stack {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.header-with-help,
.expanded-card__title-row {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.help-icon {
  color: rgba(0, 0, 0, 0.45);
}

.tooltip-copy {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.expanded-panel {
  padding: 20px;
  background: rgba(var(--v-theme-primary), 0.03);
}

.expanded-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.expanded-card {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 14px;
  padding: 16px;
  background: #fff;
}

.expanded-card__title {
  font-weight: 600;
  margin-bottom: 12px;
}

.preview-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.preview-pill {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 12px;
  padding: 12px;
  background: rgba(var(--v-theme-primary), 0.02);
  cursor: pointer;
  text-align: left;
}

.preview-pill:hover {
  border-color: rgba(var(--v-theme-primary), 0.35);
  background: rgba(var(--v-theme-primary), 0.05);
}

.preview-pill__title {
  display: block;
  font-weight: 600;
}

.preview-pill__meta {
  display: block;
  margin-top: 4px;
  color: rgba(0, 0, 0, 0.65);
  font-size: 0.85rem;
}

@media (max-width: 960px) {
  .expanded-grid {
    grid-template-columns: 1fr;
  }
}
</style>
