<template>
  <div class="base-lineage-root-causes-page">
    <v-container fluid class="page-shell wide-page-shell">
      <div class="page-header">
        <div>
          <h1 class="text-h4 font-weight-bold mb-2">Base Images & Distros</h1>
          <p class="text-body-1 text-medium-emphasis">
            Group risk by inferred operating system lineage, such as <code>debian-12</code> or <code>ubuntu-22.04</code>,
            to see which base images are spreading the most issues across repositories.
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
              aria-label="How to read base lineage root causes"
            />
          </template>
          <div class="tooltip-copy">
            <div><strong>Lineage</strong> groups images by detected distro or base-image family.</div>
            <div><strong>Source</strong> tells whether lineage came from SBOM distro metadata or package qualifiers.</div>
            <div><strong>Risk</strong> and <strong>Fixability</strong> summarize the issues spreading through that lineage.</div>
          </div>
        </v-tooltip>
      </div>

      <v-card elevation="2" class="root-causes-card">
        <v-card-text class="pb-0">
          <div class="filters-bar">
            <v-text-field
              v-model="search"
              label="Search distro"
              placeholder="debian, ubuntu, alpine"
              prepend-inner-icon="mdi-magnify"
              density="comfortable"
              variant="outlined"
              hide-details
              class="root-causes-search"
              @keyup.enter="applySearch"
              @click:prepend-inner="applySearch"
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

            <v-switch
              v-model="includeUnknown"
              color="primary"
              inset
              hide-details
              class="root-causes-switch"
              label="Include unknown lineage"
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
            item-value="key"
            class="root-causes-table"
            v-model:sort-by="sortBy"
            @update:options="onTableOptionsUpdate"
          >
            <template #header.lineage_label>
              <div class="header-with-help">
                <span>Base Image / Distro</span>
                <v-tooltip location="top" max-width="320">
                  <template #activator="{ props }">
                    <v-icon v-bind="props" size="16" class="help-icon">mdi-help-circle-outline</v-icon>
                  </template>
                  <span>Detected operating system lineage for the image, usually from SBOM distro metadata or OS package qualifiers.</span>
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
                  <span>Repositories whose currently scanned images fall into this lineage.</span>
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
                  <span>Scanned images currently mapped to this distro or base-image lineage.</span>
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
                  <span>Total unique vulnerabilities observed across images in this lineage. Chips highlight the severest subset.</span>
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
                  <span>Threat signals attached to vulnerabilities in this lineage, such as KEV and public exploits.</span>
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
                  <span>Best current remediation state across vulnerabilities in this lineage.</span>
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
                  <span>Weighted score that helps rank which base-image lineage is driving the most operational risk.</span>
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
                  <span>Most recent successful scan in which this lineage was observed.</span>
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
                      :icon="isExpanded(item.key) ? 'mdi-chevron-up' : 'mdi-chevron-down'"
                      @click.stop="toggleExpanded(item.key)"
                    />
                  </td>
                  <td>
                    <div class="component-cell">
                      <div class="component-cell__title">{{ item.lineage_label }}</div>
                      <div class="component-cell__meta">
                        <span>{{ lineageSourceLabel(item.lineage_source) }}</span>
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

                <tr v-if="isExpanded(item.key)" class="root-cause-row root-cause-row--expanded">
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
                              <span>Repositories currently carrying this distro or base-image lineage, with a small blast-radius preview.</span>
                            </v-tooltip>
                          </div>
                          <div v-if="isPreviewLoading(item.key)" class="text-body-2 text-medium-emphasis">
                            Loading repository preview...
                          </div>
                          <div
                            v-else-if="item.preview_status === 'error'"
                            class="text-body-2 text-medium-emphasis preview-status-block"
                          >
                            <span>Preview could not be loaded yet.</span>
                            <v-btn
                              size="small"
                              variant="text"
                              color="primary"
                              class="px-0"
                              @click="retryPreview(item.key, item.lineage_source)"
                            >
                              Retry
                            </v-btn>
                          </div>
                          <div
                            v-else-if="item.preview_status !== 'ready'"
                            class="text-body-2 text-medium-emphasis"
                          >
                            Preview will load when expanded.
                          </div>
                          <div
                            v-else
                            class="preview-scroll"
                            @scroll.passive="onSectionScroll(item, 'repositories', $event)"
                          >
                            <div v-if="!repositorySectionItems(item).length" class="text-body-2 text-medium-emphasis">
                              No repository preview available.
                            </div>
                            <div v-else class="preview-list">
                              <button
                                v-for="repository in repositorySectionItems(item)"
                                :key="`${item.key}-${repository.repository_uuid}`"
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
                            <div v-if="isSectionLoading(item, 'repositories')" class="section-loading">
                              Loading more repositories...
                            </div>
                            <div v-else-if="hasSectionError(item, 'repositories')" class="section-loading section-loading--error">
                              <span>Could not load more repositories.</span>
                              <v-btn
                                size="small"
                                variant="text"
                                color="primary"
                                class="px-0"
                                @click="retrySectionLoad(item, 'repositories')"
                              >
                                Retry
                              </v-btn>
                            </div>
                            <div
                              v-else-if="!sectionHasMore(item, 'repositories') && repositorySectionItems(item).length"
                              class="section-loading section-loading--done"
                            >
                              All affected repositories loaded.
                            </div>
                          </div>
                        </div>

                        <div class="expanded-card">
                          <div class="expanded-card__title-row">
                            <div class="expanded-card__title">Top components in this lineage</div>
                            <v-tooltip location="top" max-width="320">
                              <template #activator="{ props }">
                                <v-icon v-bind="props" size="16" class="help-icon">mdi-help-circle-outline</v-icon>
                              </template>
                              <span>Packages most associated with this lineage and its vulnerability spread.</span>
                            </v-tooltip>
                          </div>
                          <div v-if="isPreviewLoading(item.key)" class="text-body-2 text-medium-emphasis">
                            Loading component preview...
                          </div>
                          <div
                            v-else-if="item.preview_status === 'error'"
                            class="text-body-2 text-medium-emphasis preview-status-block"
                          >
                            <span>Preview could not be loaded yet.</span>
                            <v-btn
                              size="small"
                              variant="text"
                              color="primary"
                              class="px-0"
                              @click="retryPreview(item.key, item.lineage_source)"
                            >
                              Retry
                            </v-btn>
                          </div>
                          <div
                            v-else-if="item.preview_status !== 'ready'"
                            class="text-body-2 text-medium-emphasis"
                          >
                            Preview will load when expanded.
                          </div>
                          <div
                            v-else
                            class="preview-scroll"
                            @scroll.passive="onSectionScroll(item, 'components', $event)"
                          >
                            <div v-if="!componentSectionItems(item).length" class="text-body-2 text-medium-emphasis">
                              No component preview available.
                            </div>
                            <div v-else class="preview-list">
                              <button
                                v-for="component in componentSectionItems(item)"
                                :key="`${item.key}-${component.component_uuid}-${component.version}`"
                                type="button"
                                class="preview-pill"
                                @click="openComponent(component.component_uuid)"
                              >
                                <span class="preview-pill__title">{{ component.component_name }}@{{ component.version }}</span>
                                <span class="preview-pill__meta">
                                  {{ component.component_type }} · {{ component.affected_images_count }} images · {{ component.vulnerabilities_count }} vulns
                                </span>
                              </button>
                            </div>
                            <div v-if="isSectionLoading(item, 'components')" class="section-loading">
                              Loading more components...
                            </div>
                            <div v-else-if="hasSectionError(item, 'components')" class="section-loading section-loading--error">
                              <span>Could not load more components.</span>
                              <v-btn
                                size="small"
                                variant="text"
                                color="primary"
                                class="px-0"
                                @click="retrySectionLoad(item, 'components')"
                              >
                                Retry
                              </v-btn>
                            </div>
                            <div
                              v-else-if="!sectionHasMore(item, 'components') && componentSectionItems(item).length"
                              class="section-loading section-loading--done"
                            >
                              All visible components loaded.
                            </div>
                          </div>
                        </div>

                        <div class="expanded-card expanded-card--wide">
                          <div class="expanded-card__title-row">
                            <div class="expanded-card__title">Top vulnerabilities seen in this lineage</div>
                            <v-tooltip location="top" max-width="320">
                              <template #activator="{ props }">
                                <v-icon v-bind="props" size="16" class="help-icon">mdi-help-circle-outline</v-icon>
                              </template>
                              <span>Highest-priority vulnerabilities currently showing up across images mapped to this lineage.</span>
                            </v-tooltip>
                          </div>
                          <div v-if="isPreviewLoading(item.key)" class="text-body-2 text-medium-emphasis">
                            Loading vulnerability preview...
                          </div>
                          <div
                            v-else-if="item.preview_status === 'error'"
                            class="text-body-2 text-medium-emphasis preview-status-block"
                          >
                            <span>Preview could not be loaded yet.</span>
                            <v-btn
                              size="small"
                              variant="text"
                              color="primary"
                              class="px-0"
                              @click="retryPreview(item.key, item.lineage_source)"
                            >
                              Retry
                            </v-btn>
                          </div>
                          <div
                            v-else-if="item.preview_status !== 'ready'"
                            class="text-body-2 text-medium-emphasis"
                          >
                            Preview will load when expanded.
                          </div>
                          <div
                            v-else
                            class="preview-scroll preview-scroll--wide"
                            @scroll.passive="onSectionScroll(item, 'vulnerabilities', $event)"
                          >
                            <div v-if="!vulnerabilitySectionItems(item).length" class="text-body-2 text-medium-emphasis">
                              No vulnerability preview available.
                            </div>
                            <div v-else class="preview-list">
                              <button
                                v-for="vulnerability in vulnerabilitySectionItems(item)"
                                :key="`${item.key}-${vulnerability.uuid}`"
                                type="button"
                                class="preview-pill preview-pill--vulnerability"
                                @click="openVulnerability(vulnerability.uuid)"
                              >
                                <span class="preview-pill__title">{{ vulnerability.vulnerability_id }}</span>
                                <span class="preview-pill__meta">
                                  {{ vulnerability.severity }} · EPSS {{ vulnerability.epss.toFixed(3) }}
                                  <span v-if="vulnerability.cisa_kev"> · KEV</span>
                                  <span v-if="vulnerability.exploit_available"> · Exploit</span>
                                </span>
                              </button>
                            </div>
                            <div v-if="isSectionLoading(item, 'vulnerabilities')" class="section-loading">
                              Loading more vulnerabilities...
                            </div>
                            <div v-else-if="hasSectionError(item, 'vulnerabilities')" class="section-loading section-loading--error">
                              <span>Could not load more vulnerabilities.</span>
                              <v-btn
                                size="small"
                                variant="text"
                                color="primary"
                                class="px-0"
                                @click="retrySectionLoad(item, 'vulnerabilities')"
                              >
                                Retry
                              </v-btn>
                            </div>
                            <div
                              v-else-if="!sectionHasMore(item, 'vulnerabilities') && vulnerabilitySectionItems(item).length"
                              class="section-loading section-loading--done"
                            >
                              All visible vulnerabilities loaded.
                            </div>
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
import type {
  BaseLineageRootCauseBatchPreviewResponse,
  BaseLineageRootCauseSectionName,
  BaseLineageRootCauseSectionResponse,
  BaseLineageRootCause,
  BaseLineageComponentPreview,
  BaseLineageRootCausePreviewResponse,
  BaseLineageRootCauseResponse,
  RootCauseRepositoryPreview,
  RootCauseVulnerabilityPreview,
} from '../types/interfaces'

const router = useRouter()

type PreviewStatus = 'idle' | 'ready' | 'error'
type InfiniteSectionState<T> = {
  items: T[]
  nextOffset: number
  hasMore: boolean
  loading: boolean
  initialized: boolean
  error: boolean
}

type BaseLineageSectionState = {
  repositories: InfiniteSectionState<RootCauseRepositoryPreview>
  components: InfiniteSectionState<BaseLineageComponentPreview>
  vulnerabilities: InfiniteSectionState<RootCauseVulnerabilityPreview>
}

type BaseLineageRootCauseViewItem = BaseLineageRootCause & {
  preview_status: PreviewStatus
}

const items = ref<BaseLineageRootCauseViewItem[]>([])
const totalItems = ref(0)
const loading = ref(false)
const page = ref(1)
const itemsPerPage = ref(25)
const sortBy = ref<{ key: string; order: 'asc' | 'desc' }[]>([
  { key: 'weighted_risk_score', order: 'desc' },
])
const expandedIds = ref<string[]>([])
const previewLoadingKeys = ref<string[]>([])
const sectionStates = ref<Record<string, BaseLineageSectionState>>({})
const search = ref('')
const appliedSearch = ref('')
const scope = ref('cross_repository')
const fixability = ref('all')
const includeUnknown = ref(false)
const lastOptionsKey = ref('')
const PREFETCH_PREVIEW_LIMIT = 4
const SECTION_PAGE_SIZE = 20

const normalizeBaseLineageSort = (items?: { key: string; order?: 'asc' | 'desc' }[]) =>
  (items && items.length ? items : [{ key: 'weighted_risk_score', order: 'desc' }]).map((item) => ({
    key: String(item.key || 'weighted_risk_score'),
    order: item.order === 'asc' ? 'asc' as const : 'desc' as const,
  }))

const areBaseLineageSortEqual = (
  left: { key: string; order?: 'asc' | 'desc' }[],
  right: { key: string; order?: 'asc' | 'desc' }[],
) => JSON.stringify(normalizeBaseLineageSort(left)) === JSON.stringify(normalizeBaseLineageSort(right))

const hasPreviewContent = (item: {
  repositories_preview?: unknown[]
  components_preview?: unknown[]
  vulnerabilities_preview?: unknown[]
}) => Boolean(
  (item.repositories_preview && item.repositories_preview.length)
  || (item.components_preview && item.components_preview.length)
  || (item.vulnerabilities_preview && item.vulnerabilities_preview.length)
)

const canExpectPreview = (item: {
  affected_repositories_count?: number
  affected_images_count?: number
  vulnerabilities_count?: number
}) => Boolean(
  (item.affected_repositories_count || 0) > 0
  || (item.affected_images_count || 0) > 0
  || (item.vulnerabilities_count || 0) > 0
)

const uniqueSectionItems = <T>(items: T[], getKey: (item: T) => string) => {
  const seen = new Set<string>()
  return items.filter((item) => {
    const key = getKey(item)
    if (seen.has(key)) {
      return false
    }
    seen.add(key)
    return true
  })
}

const repositoryPreviewKey = (item: RootCauseRepositoryPreview) => item.repository_uuid
const componentPreviewKey = (item: BaseLineageComponentPreview) => `${item.component_uuid}:${item.version}`
const vulnerabilityPreviewKey = (item: RootCauseVulnerabilityPreview) => item.uuid

const createInfiniteSectionState = <T>(seedItems: T[], hasMore: boolean): InfiniteSectionState<T> => ({
  items: seedItems,
  nextOffset: seedItems.length,
  hasMore,
  loading: false,
  initialized: true,
  error: false,
})

const getSectionSeed = (item: BaseLineageRootCauseViewItem, section: BaseLineageRootCauseSectionName) => {
  switch (section) {
    case 'repositories':
      return item.repositories_preview || []
    case 'components':
      return item.components_preview || []
    case 'vulnerabilities':
      return item.vulnerabilities_preview || []
  }
}

const getInitialHasMore = (item: BaseLineageRootCauseViewItem, section: BaseLineageRootCauseSectionName, seedLength: number) => {
  switch (section) {
    case 'repositories':
      return (item.affected_repositories_count || 0) > seedLength
    case 'components':
      return seedLength > 0 || (item.affected_images_count || 0) > 0
    case 'vulnerabilities':
      return (item.vulnerabilities_count || 0) > seedLength
  }
}

const buildSectionState = (item: BaseLineageRootCauseViewItem): BaseLineageSectionState => ({
  repositories: createInfiniteSectionState(
    uniqueSectionItems(item.repositories_preview || [], repositoryPreviewKey),
    getInitialHasMore(item, 'repositories', (item.repositories_preview || []).length),
  ),
  components: createInfiniteSectionState(
    uniqueSectionItems(item.components_preview || [], componentPreviewKey),
    getInitialHasMore(item, 'components', (item.components_preview || []).length),
  ),
  vulnerabilities: createInfiniteSectionState(
    uniqueSectionItems(item.vulnerabilities_preview || [], vulnerabilityPreviewKey),
    getInitialHasMore(item, 'vulnerabilities', (item.vulnerabilities_preview || []).length),
  ),
})

const ensureSectionState = (item: BaseLineageRootCauseViewItem) => {
  if (!sectionStates.value[item.key]) {
    sectionStates.value[item.key] = buildSectionState(item)
  }
  return sectionStates.value[item.key]
}

const syncSectionStateFromItem = (item: BaseLineageRootCauseViewItem, overwrite = false) => {
  const state = sectionStates.value[item.key]
  if (!state) {
    sectionStates.value[item.key] = buildSectionState(item)
    return
  }

  const repositoriesSeed = uniqueSectionItems(item.repositories_preview || [], repositoryPreviewKey)
  const componentsSeed = uniqueSectionItems(item.components_preview || [], componentPreviewKey)
  const vulnerabilitiesSeed = uniqueSectionItems(item.vulnerabilities_preview || [], vulnerabilityPreviewKey)

  if (overwrite || !state.repositories.initialized) {
    state.repositories = createInfiniteSectionState(
      repositoriesSeed,
      getInitialHasMore(item, 'repositories', repositoriesSeed.length),
    )
  }

  if (overwrite || !state.components.initialized) {
    state.components = createInfiniteSectionState(
      componentsSeed,
      getInitialHasMore(item, 'components', componentsSeed.length),
    )
  }

  if (overwrite || !state.vulnerabilities.initialized) {
    state.vulnerabilities = createInfiniteSectionState(
      vulnerabilitiesSeed,
      getInitialHasMore(item, 'vulnerabilities', vulnerabilitiesSeed.length),
    )
  }
}

const getSectionState = (
  item: BaseLineageRootCauseViewItem,
  section: BaseLineageRootCauseSectionName,
) => ensureSectionState(item)[section]

const repositorySectionState = (item: BaseLineageRootCauseViewItem) => ensureSectionState(item).repositories
const componentSectionState = (item: BaseLineageRootCauseViewItem) => ensureSectionState(item).components
const vulnerabilitySectionState = (item: BaseLineageRootCauseViewItem) => ensureSectionState(item).vulnerabilities

const headers = [
  { title: '', key: 'expand', sortable: false, width: 56 },
  { title: 'Base Image / Distro', key: 'lineage_label', sortable: true, minWidth: 240 },
  { title: 'Repos', key: 'affected_repositories_count', sortable: true, width: 90 },
  { title: 'Images', key: 'affected_images_count', sortable: true, width: 90 },
  { title: 'Vulns', key: 'vulnerabilities_count', sortable: true, minWidth: 160 },
  { title: 'Signals', key: 'kev_vulnerabilities_count', sortable: true, minWidth: 130 },
  { title: 'Fixability', key: 'fixability', sortable: false, minWidth: 160 },
  { title: 'Risk', key: 'weighted_risk_score', sortable: true, width: 120 },
  { title: 'Updated', key: 'latest_seen_at', sortable: true, minWidth: 150 },
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
  scope: scope.value,
  fixability: fixability.value,
  includeUnknown: includeUnknown.value,
})

const resetExpandedState = () => {
  expandedIds.value = []
  previewLoadingKeys.value = []
  sectionStates.value = {}
}

const fetchItems = async () => {
  loading.value = true
  try {
    const response = await api.get<BaseLineageRootCauseResponse>('stats/base-lineage-root-causes/', {
      params: {
        page: page.value,
        page_size: itemsPerPage.value,
        ordering: currentOrdering.value,
        search: appliedSearch.value || undefined,
        scope: scope.value,
        fixability: fixability.value,
        include_unknown: includeUnknown.value ? 1 : 0,
      },
    })
    const results = response.data.results || []
    totalItems.value = response.data.count || 0
    if (!results.length && totalItems.value > 0 && page.value > 1) {
      page.value = 1
      return
    }
    items.value = (response.data.results || []).map((item) => ({
      ...item,
      repositories_preview: item.repositories_preview || [],
      components_preview: item.components_preview || [],
      vulnerabilities_preview: item.vulnerabilities_preview || [],
      preview_status: hasPreviewContent(item) ? 'ready' as PreviewStatus : 'idle' as PreviewStatus,
    }))
    items.value.forEach((item) => syncSectionStateFromItem(item, true))
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
  await fetchItems()
}

const onTableOptionsUpdate = (options: {
  page?: number
  itemsPerPage?: number
  sortBy?: { key: string; order?: 'asc' | 'desc' }[]
}) => {
  const nextPage = options.page || 1
  const nextItemsPerPage = options.itemsPerPage || 25
  const nextSortBy = normalizeBaseLineageSort(options.sortBy)

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

  const itemsPerPageChanged = itemsPerPage.value !== nextItemsPerPage
  const sortChanged = !areBaseLineageSortEqual(sortBy.value, nextSortBy)
  const pageChanged = page.value !== nextPage

  if (itemsPerPageChanged || sortChanged || pageChanged) {
    resetExpandedState()
  }

  itemsPerPage.value = nextItemsPerPage
  page.value = itemsPerPageChanged || sortChanged ? 1 : nextPage
  sortBy.value = nextSortBy
}

const applySearch = async () => {
  appliedSearch.value = search.value.trim()
  page.value = 1
  resetExpandedState()
  await refreshIfNeeded()
}

watch([scope, fixability, includeUnknown], async () => {
  page.value = 1
  resetExpandedState()
  await refreshIfNeeded()
})

watch([page, itemsPerPage, sortBy], async () => {
  await refreshIfNeeded()
}, { deep: true })

const isExpanded = (key: string) => expandedIds.value.includes(key)
const isPreviewLoading = (key: string) => previewLoadingKeys.value.includes(key)

const fetchPreview = async (key: string, lineageSource?: string) => {
  if (isPreviewLoading(key)) {
    return
  }

  previewLoadingKeys.value = [...previewLoadingKeys.value, key]
  try {
    const response = await api.get<BaseLineageRootCausePreviewResponse>('stats/base-lineage-root-causes-preview/', {
      params: {
        lineage_label: key,
        lineage_source: lineageSource,
        include_unknown: includeUnknown.value ? 1 : 0,
        fresh: 1,
      },
    })
    items.value = items.value.map((item) => item.key === key ? {
      ...item,
      repositories_preview: response.data.repositories_preview || [],
      components_preview: response.data.components_preview || [],
      vulnerabilities_preview: response.data.vulnerabilities_preview || [],
      preview_status: hasPreviewContent(response.data)
        ? 'ready'
        : (canExpectPreview(item) ? 'error' : 'idle'),
    } : item)
    const updatedItem = items.value.find((item) => item.key === key)
    if (updatedItem) {
      syncSectionStateFromItem(updatedItem, true)
    }
  } catch (error) {
    items.value = items.value.map((item) => item.key === key ? {
      ...item,
      preview_status: 'error',
    } : item)
  } finally {
    previewLoadingKeys.value = previewLoadingKeys.value.filter((value) => value !== key)
  }
}

const prefetchVisiblePreviews = async (optionsKey: string) => {
  const candidates = items.value
    .filter((item) => item.preview_status === 'idle')
    .slice(0, PREFETCH_PREVIEW_LIMIT)

  if (!candidates.length) {
    return
  }

  const loadingKeys = candidates
    .map((item) => item.key)
    .filter((key) => !isPreviewLoading(key))

  if (!loadingKeys.length) {
    return
  }

  previewLoadingKeys.value = [...previewLoadingKeys.value, ...loadingKeys]
  try {
    const response = await api.post<BaseLineageRootCauseBatchPreviewResponse>(
      'stats/base-lineage-root-causes-previews-batch/',
      {
        entries: candidates.map((item) => ({
          lineage_label: item.key,
          lineage_source: item.lineage_source,
          include_unknown: includeUnknown.value ? 1 : 0,
        })),
      },
    )

    if (lastOptionsKey.value !== optionsKey) {
      return
    }

    const previewMap = new Map(
      (response.data.results || []).map((entry) => [entry.lineage_label, entry])
    )

    items.value = items.value.map((item) => {
      const preview = previewMap.get(item.key)
      if (!preview) {
        return item
      }
      return {
        ...item,
        repositories_preview: preview.repositories_preview || [],
        components_preview: preview.components_preview || [],
        vulnerabilities_preview: preview.vulnerabilities_preview || [],
        preview_status: hasPreviewContent(preview) ? 'ready' : 'idle',
      }
    })
    items.value.forEach((item) => {
      if (previewMap.has(item.key)) {
        syncSectionStateFromItem(item)
      }
    })
  } finally {
    previewLoadingKeys.value = previewLoadingKeys.value.filter((value) => !loadingKeys.includes(value))
  }
}

const fetchSectionPage = async (
  item: BaseLineageRootCauseViewItem,
  section: BaseLineageRootCauseSectionName,
) => {
  const state = getSectionState(item, section)
  if (state.loading || !state.hasMore) {
    return
  }

  state.loading = true
  state.error = false
  try {
    if (item.preview_status !== 'ready') {
      await fetchPreview(item.key, item.lineage_source)
    }

    const refreshedItem = items.value.find((entry) => entry.key === item.key)
    const targetItem = refreshedItem || item
    if (section === 'repositories') {
      const targetState = repositorySectionState(targetItem)
      const response = await api.get<BaseLineageRootCauseSectionResponse<RootCauseRepositoryPreview>>(
        'stats/base-lineage-root-causes-section/',
        {
          params: {
            lineage_label: targetItem.key,
            lineage_source: targetItem.lineage_source,
            include_unknown: includeUnknown.value ? 1 : 0,
            section,
            offset: targetState.nextOffset,
            limit: SECTION_PAGE_SIZE,
          },
        },
      )
      targetState.items = uniqueSectionItems(
        [...targetState.items, ...(response.data.results || [])],
        repositoryPreviewKey,
      )
      targetState.nextOffset = response.data.next_offset ?? targetState.items.length
      targetState.hasMore = Boolean(response.data.has_more)
      targetState.initialized = true
      targetState.error = false
    } else if (section === 'components') {
      const targetState = componentSectionState(targetItem)
      const response = await api.get<BaseLineageRootCauseSectionResponse<BaseLineageComponentPreview>>(
        'stats/base-lineage-root-causes-section/',
        {
          params: {
            lineage_label: targetItem.key,
            lineage_source: targetItem.lineage_source,
            include_unknown: includeUnknown.value ? 1 : 0,
            section,
            offset: targetState.nextOffset,
            limit: SECTION_PAGE_SIZE,
          },
        },
      )
      targetState.items = uniqueSectionItems(
        [...targetState.items, ...(response.data.results || [])],
        componentPreviewKey,
      )
      targetState.nextOffset = response.data.next_offset ?? targetState.items.length
      targetState.hasMore = Boolean(response.data.has_more)
      targetState.initialized = true
      targetState.error = false
    } else {
      const targetState = vulnerabilitySectionState(targetItem)
      const response = await api.get<BaseLineageRootCauseSectionResponse<RootCauseVulnerabilityPreview>>(
        'stats/base-lineage-root-causes-section/',
        {
          params: {
            lineage_label: targetItem.key,
            lineage_source: targetItem.lineage_source,
            include_unknown: includeUnknown.value ? 1 : 0,
            section,
            offset: targetState.nextOffset,
            limit: SECTION_PAGE_SIZE,
          },
        },
      )
      targetState.items = uniqueSectionItems(
        [...targetState.items, ...(response.data.results || [])],
        vulnerabilityPreviewKey,
      )
      targetState.nextOffset = response.data.next_offset ?? targetState.items.length
      targetState.hasMore = Boolean(response.data.has_more)
      targetState.initialized = true
      targetState.error = false
    }
  } catch (error) {
    state.error = true
  } finally {
    state.loading = false
  }
}

const onSectionScroll = async (
  item: BaseLineageRootCauseViewItem,
  section: BaseLineageRootCauseSectionName,
  event: Event,
) => {
  const target = event.target as HTMLElement | null
  if (!target) {
    return
  }
  const distanceToBottom = target.scrollHeight - target.scrollTop - target.clientHeight
  if (distanceToBottom <= 96) {
    await fetchSectionPage(item, section)
  }
}

const retrySectionLoad = async (
  item: BaseLineageRootCauseViewItem,
  section: BaseLineageRootCauseSectionName,
) => {
  const state = getSectionState(item, section)
  state.error = false
  await fetchSectionPage(item, section)
}

const repositorySectionItems = (item: BaseLineageRootCauseViewItem) => repositorySectionState(item).items
const componentSectionItems = (item: BaseLineageRootCauseViewItem) => componentSectionState(item).items
const vulnerabilitySectionItems = (item: BaseLineageRootCauseViewItem) => vulnerabilitySectionState(item).items

const isSectionLoading = (
  item: BaseLineageRootCauseViewItem,
  section: BaseLineageRootCauseSectionName,
) => getSectionState(item, section).loading

const hasSectionError = (
  item: BaseLineageRootCauseViewItem,
  section: BaseLineageRootCauseSectionName,
) => getSectionState(item, section).error

const sectionHasMore = (
  item: BaseLineageRootCauseViewItem,
  section: BaseLineageRootCauseSectionName,
) => getSectionState(item, section).hasMore

const toggleExpanded = async (key: string) => {
  if (isExpanded(key)) {
    expandedIds.value = expandedIds.value.filter((value) => value !== key)
    return
  }

  expandedIds.value = [...expandedIds.value, key]
  const item = items.value.find((entry) => entry.key === key)
  if (!item) {
    return
  }
  ensureSectionState(item)
  if (item.preview_status !== 'ready') {
    await fetchPreview(key, item.lineage_source)
  }
}

const retryPreview = async (key: string, lineageSource?: string) => {
  items.value = items.value.map((item) => item.key === key ? {
    ...item,
    preview_status: 'idle',
  } : item)
  await fetchPreview(key, lineageSource)
}

const lineageSourceLabel = (value: string) => {
  switch (value) {
    case 'sbom_distro':
      return 'Detected from SBOM distro metadata'
    case 'package_distro':
      return 'Inferred from OS package distro qualifiers'
    default:
      return 'Lineage not confidently detected'
  }
}

const openRepository = (uuid: string) => router.push(`/repositories/${uuid}`)
const openComponent = (uuid: string) => router.push(`/components/${uuid}`)
const openVulnerability = (uuid: string) => router.push(`/vulnerabilities/${uuid}`)

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

.component-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.component-cell__title {
  font-weight: 600;
}

.component-cell__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  color: rgba(0, 0, 0, 0.6);
  font-size: 0.8rem;
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

.expanded-card--wide {
  grid-column: 1 / -1;
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

.preview-scroll {
  max-height: 360px;
  overflow-y: auto;
  padding-right: 6px;
}

.preview-scroll--wide {
  max-height: 320px;
}

.preview-status-block {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.section-loading {
  padding-top: 12px;
  color: rgba(0, 0, 0, 0.6);
  font-size: 0.9rem;
}

.section-loading--error {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.section-loading--done {
  color: rgba(0, 0, 0, 0.45);
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

  .expanded-card--wide {
    grid-column: auto;
  }
}
</style>
