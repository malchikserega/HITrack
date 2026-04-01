<template>
  <div class="image-comparisons-page">
    <v-container fluid class="page-shell wide-page-shell">
      <div class="page-header">
        <div>
          <h1 class="text-h4 font-weight-bold mb-2">Image Comparisons</h1>
          <p class="text-body-1 text-medium-emphasis">
            Compare images that share the same logical name, such as <code>worker:5.0.426-gec5ee144</code>,
            across different registries and repositories.
          </p>
        </div>
        <v-btn
          variant="text"
          color="primary"
          prepend-icon="mdi-arrow-left"
          @click="goBackToImages"
        >
          Back to Images
        </v-btn>
      </div>

      <v-card elevation="2" class="comparison-card">
        <v-card-text class="pb-0">
          <div class="filters-bar">
            <v-text-field
              v-model="search"
              label="Search logical image"
              placeholder="worker:5.0.426-gec5ee144"
              prepend-inner-icon="mdi-magnify"
              density="comfortable"
              variant="outlined"
              hide-details
              class="comparison-search"
              @keyup.enter="applySearch"
              @click:prepend-inner="applySearch"
            />
            <v-switch
              v-model="duplicatesOnly"
              color="primary"
              inset
              hide-details
              class="duplicates-switch"
              label="Only show duplicate logical names"
            />
          </div>
        </v-card-text>

        <v-card-text class="pa-0">
          <v-data-table-server
            :headers="headers"
            :items="groups"
            :items-length="totalItems"
            :page="page"
            :items-per-page="itemsPerPage"
            :loading="loading"
            item-value="logical_name"
            class="comparison-table"
            @update:options="onTableOptionsUpdate"
          >
            <template #item="{ item }">
              <template v-if="item">
                <tr class="comparison-row">
                  <td class="comparison-row__expand">
                    <v-btn
                      size="small"
                      variant="text"
                      color="primary"
                      :icon="isExpanded(item.logical_name) ? 'mdi-chevron-up' : 'mdi-chevron-down'"
                      @click.stop="toggleExpanded(item.logical_name)"
                    />
                  </td>
                  <td>
                    <div class="logical-name-cell">
                      <div class="logical-name-cell__title">{{ item.logical_name }}</div>
                      <div class="logical-name-cell__subtitle">
                        {{ item.variant_count }} variants across {{ item.registry_count }} registries
                      </div>
                    </div>
                  </td>
                  <td>{{ item.variant_count }}</td>
                  <td>{{ item.registry_count }}</td>
                  <td>
                    <v-chip
                      :color="item.different_digests ? 'warning' : 'success'"
                      size="small"
                      variant="tonal"
                    >
                      {{ item.distinct_digests }} digest<span v-if="item.distinct_digests !== 1">s</span>
                    </v-chip>
                  </td>
                  <td>{{ item.max_findings }}</td>
                  <td>{{ item.max_unique_findings }}</td>
                  <td>{{ item.max_components_count }}</td>
                  <td>
                    <div class="status-breakdown">
                      <v-chip
                        v-if="item.status_breakdown.success"
                        color="success"
                        size="x-small"
                        variant="tonal"
                      >
                        {{ item.status_breakdown.success }} success
                      </v-chip>
                      <v-chip
                        v-if="item.status_breakdown.error"
                        color="error"
                        size="x-small"
                        variant="tonal"
                      >
                        {{ item.status_breakdown.error }} error
                      </v-chip>
                      <v-chip
                        v-if="item.status_breakdown.in_process"
                        color="warning"
                        size="x-small"
                        variant="tonal"
                      >
                        {{ item.status_breakdown.in_process }} processing
                      </v-chip>
                      <v-chip
                        v-if="item.status_breakdown.pending"
                        color="info"
                        size="x-small"
                        variant="tonal"
                      >
                        {{ item.status_breakdown.pending }} pending
                      </v-chip>
                    </div>
                  </td>
                  <td>
                    <div class="date-meta-cell">
                      <div class="date-meta-cell__primary nowrap">{{ $formatDate(item.latest_updated_at) }}</div>
                    </div>
                  </td>
                </tr>
                <tr v-if="isExpanded(item.logical_name)" class="comparison-row comparison-row--expanded">
                  <td :colspan="headers.length">
                    <div class="expanded-panel">
                      <div class="expanded-panel__header">
                        <div class="text-subtitle-1 font-weight-medium">Variants for {{ item.logical_name }}</div>
                        <div class="text-body-2 text-medium-emphasis">
                          Compare registry source, digest, scan status and findings side by side.
                        </div>
                      </div>

                      <div class="expanded-panel__table">
                        <v-table density="compact">
                          <thead>
                            <tr>
                              <th>Image</th>
                              <th>Registry</th>
                              <th>Digest</th>
                              <th>Status</th>
                              <th>Findings</th>
                              <th>Unique</th>
                              <th>Components</th>
                              <th>Repository Tags</th>
                              <th>Updated</th>
                              <th>Open</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr
                              v-for="variant in item.variants"
                              :key="variant.uuid"
                            >
                              <td>
                                <div class="variant-name-cell">
                                  <button
                                    type="button"
                                    class="comparison-link"
                                    @click="openImageDetail(variant.uuid)"
                                  >
                                    {{ variant.name }}
                                  </button>
                                  <div class="variant-name-cell__secondary">
                                    {{ variant.repository_path }}
                                  </div>
                                </div>
                              </td>
                              <td>{{ variant.registry_host || '-' }}</td>
                              <td>
                                <v-tooltip location="top">
                                  <template #activator="{ props }">
                                    <span v-bind="props" class="digest-shortcut">
                                      {{ formatDigest(variant.digest) }}
                                    </span>
                                  </template>
                                  <span>{{ variant.digest || 'No digest' }}</span>
                                </v-tooltip>
                              </td>
                              <td>
                                <v-chip
                                  :color="statusColor(variant.scan_status)"
                                  size="small"
                                  variant="tonal"
                                >
                                  {{ statusLabel(variant.scan_status) }}
                                </v-chip>
                              </td>
                              <td>{{ variant.findings }}</td>
                              <td>{{ variant.unique_findings }}</td>
                              <td>{{ variant.components_count }}</td>
                              <td>
                                <div class="variant-tags">
                                  <v-chip
                                    v-for="tag in variant.repository_tags"
                                    :key="tag.tag_uuid"
                                    size="x-small"
                                    color="primary"
                                    variant="outlined"
                                    class="variant-tag-chip"
                                    @click="openTag(tag.tag_uuid)"
                                  >
                                    {{ tag.repository_name }}:{{ tag.tag }}
                                  </v-chip>
                                </div>
                              </td>
                              <td>{{ $formatDate(variant.updated_at) }}</td>
                              <td>
                                <v-btn
                                  icon="mdi-open-in-new"
                                  size="small"
                                  variant="text"
                                  color="primary"
                                  @click="openImageDetail(variant.uuid)"
                                />
                              </td>
                            </tr>
                          </tbody>
                        </v-table>
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
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { DataTableHeader, DataTableSortItem } from 'vuetify'

import api from '../plugins/axios'
import { notificationService } from '../plugins/notifications'
import type { ImageComparisonGroup, PaginatedResponse } from '../types/interfaces'

const router = useRouter()

const groups = ref<ImageComparisonGroup[]>([])
const loading = ref(false)
const search = ref('')
const duplicatesOnly = ref(true)
const page = ref(1)
const itemsPerPage = ref(25)
const totalItems = ref(0)
const sortBy = ref<DataTableSortItem[]>([
  { key: 'variant_count', order: 'desc' },
])
const expandedLogicalNames = ref<string[]>([])

const headers: DataTableHeader[] = [
  { title: '', key: 'expand', sortable: false, width: 72 },
  { title: 'Logical Image', key: 'logical_name', sortable: true, minWidth: 260 },
  { title: 'Variants', key: 'variant_count', sortable: true, width: 110 },
  { title: 'Registries', key: 'registry_count', sortable: true, width: 120 },
  { title: 'Digests', key: 'distinct_digests', sortable: true, width: 120 },
  { title: 'Worst Findings', key: 'max_findings', sortable: true, width: 130 },
  { title: 'Worst Unique', key: 'max_unique_findings', sortable: true, width: 130 },
  { title: 'Max Components', key: 'max_components_count', sortable: true, width: 140 },
  { title: 'Statuses', key: 'statuses', sortable: false, width: 220 },
  { title: 'Latest Updated', key: 'latest_updated_at', sortable: true, width: 180 },
]

const buildOrdering = () => {
  const [activeSort] = sortBy.value
  if (!activeSort?.key || !activeSort.order) {
    return '-variant_count'
  }
  return `${activeSort.order === 'desc' ? '-' : ''}${activeSort.key}`
}

const fetchComparisonGroups = async () => {
  loading.value = true
  try {
    const response = await api.get<PaginatedResponse<ImageComparisonGroup>>('images/comparisons/', {
      params: {
        page: page.value,
        page_size: itemsPerPage.value,
        search: search.value || undefined,
        duplicates_only: duplicatesOnly.value,
        ordering: buildOrdering(),
      },
    })
    groups.value = response.data.results || []
    totalItems.value = response.data.count || 0
    expandedLogicalNames.value = expandedLogicalNames.value.filter((value) =>
      groups.value.some((group) => group.logical_name === value)
    )
  } catch (error) {
    console.error('Error fetching image comparison groups:', error)
    notificationService.error('Failed to load image comparisons')
  } finally {
    loading.value = false
  }
}

const onTableOptionsUpdate = (options: { page: number; itemsPerPage: number; sortBy: DataTableSortItem[] }) => {
  const nextSort = options.sortBy && options.sortBy.length ? options.sortBy : [{ key: 'variant_count', order: 'desc' as const }]
  const currentSort = sortBy.value[0]
  const nextPrimarySort = nextSort[0]

  const pageChanged = page.value !== options.page
  const pageSizeChanged = itemsPerPage.value !== options.itemsPerPage
  const sortChanged =
    currentSort?.key !== nextPrimarySort?.key ||
    currentSort?.order !== nextPrimarySort?.order

  if (!pageChanged && !pageSizeChanged && !sortChanged) {
    return
  }

  page.value = options.page
  itemsPerPage.value = options.itemsPerPage
  sortBy.value = nextSort
}

const applySearch = () => {
  page.value = 1
  fetchComparisonGroups()
}

const isExpanded = (logicalName: string) => expandedLogicalNames.value.includes(logicalName)

const toggleExpanded = (logicalName: string) => {
  if (isExpanded(logicalName)) {
    expandedLogicalNames.value = expandedLogicalNames.value.filter((value) => value !== logicalName)
    return
  }
  expandedLogicalNames.value = [...expandedLogicalNames.value, logicalName]
}

const openImageDetail = (uuid: string) => {
  router.push({ name: 'image-detail', params: { uuid } })
}

const openTag = (uuid: string) => {
  router.push({ name: 'tag-images', params: { uuid } })
}

const goBackToImages = () => {
  router.push({ name: 'images' })
}

const formatDigest = (digest?: string | null) => {
  if (!digest) {
    return 'No digest'
  }
  if (digest.length <= 18) {
    return digest
  }
  return `${digest.slice(0, 12)}...${digest.slice(-6)}`
}

const statusColor = (status: string) => {
  switch (status) {
    case 'success':
      return 'success'
    case 'error':
      return 'error'
    case 'in_process':
      return 'warning'
    case 'pending':
      return 'info'
    default:
      return 'grey'
  }
}

const statusLabel = (status: string) => {
  switch (status) {
    case 'success':
      return 'Success'
    case 'error':
      return 'Error'
    case 'in_process':
      return 'Processing'
    case 'pending':
      return 'Pending'
    default:
      return 'Unknown'
  }
}

watch([page, itemsPerPage, sortBy], () => {
  fetchComparisonGroups()
}, { deep: true })

watch(duplicatesOnly, () => {
  page.value = 1
  fetchComparisonGroups()
})

onMounted(() => {
  fetchComparisonGroups()
})
</script>

<style scoped>
.image-comparisons-page {
  padding: 20px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 24px;
}

.comparison-card {
  border-radius: 16px;
}

.filters-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding-bottom: 16px;
  flex-wrap: wrap;
}

.comparison-search {
  min-width: 320px;
  max-width: 460px;
}

.duplicates-switch {
  margin-top: -4px;
}

.comparison-row__expand {
  width: 72px;
}

.logical-name-cell__title {
  font-weight: 600;
}

.logical-name-cell__subtitle {
  font-size: 0.85rem;
  color: rgba(0, 0, 0, 0.6);
}

.status-breakdown {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.expanded-panel {
  padding: 16px 8px 20px;
  background: rgba(0, 0, 0, 0.02);
}

.expanded-panel__header {
  margin-bottom: 12px;
}

.expanded-panel__table {
  overflow-x: auto;
}

.comparison-link {
  background: none;
  border: none;
  padding: 0;
  color: rgb(var(--v-theme-primary));
  cursor: pointer;
  text-align: left;
  font-weight: 600;
}

.comparison-link:hover {
  text-decoration: underline;
}

.variant-name-cell__secondary {
  font-size: 0.8rem;
  color: rgba(0, 0, 0, 0.55);
  margin-top: 2px;
}

.variant-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  max-width: 360px;
}

.variant-tag-chip {
  cursor: pointer;
}

.digest-shortcut {
  font-family: 'Share Tech Mono', monospace;
  font-size: 0.85rem;
}

.date-meta-cell__primary.nowrap {
  white-space: nowrap;
}

.comparison-table :deep(table) {
  min-width: 1260px;
}
</style>
