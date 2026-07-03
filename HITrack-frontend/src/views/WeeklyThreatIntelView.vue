<template>
  <div class="weekly-threat-intel-page">
    <v-container fluid class="page-shell wide-page-shell">
      <div class="page-header">
        <div>
          <h1 class="text-h4 font-weight-bold mb-2">Weekly Threat Intel</h1>
          <p class="text-body-1 text-medium-emphasis">
            Full weekly view of observed vulnerabilities, new KEV entries, and supply-chain advisories enriched from GitHub and OSV.
          </p>
        </div>
        <v-btn
          variant="text"
          color="primary"
          prepend-icon="mdi-arrow-left"
          @click="goBackToDashboard"
        >
          Back to Dashboard
        </v-btn>
      </div>

      <v-card elevation="2" class="threat-intel-card">
        <v-card-text class="pb-0">
          <div class="filters-bar">
            <div class="filters-bar__left">
              <v-select
                v-model="selectedIntelType"
                :items="intelTypeOptions"
                label="Intel Type"
                variant="outlined"
                density="comfortable"
                hide-details
                class="intel-type-filter"
              />
              <v-tooltip location="top">
                <template #activator="{ props }">
                  <v-btn
                    v-bind="props"
                    icon="mdi-information-outline"
                    size="small"
                    variant="text"
                    color="medium-emphasis"
                  />
                </template>
                <div class="intel-tooltip">
                  <div><strong>Observed</strong>: first seen in HITrack this week.</div>
                  <div><strong>Relevant</strong>: matched in HITrack historical data.</div>
                  <div><strong>Present</strong>: currently linked to scanned images.</div>
                </div>
              </v-tooltip>
            </div>
            <v-chip color="primary" variant="tonal" size="small">
              {{ formattedPeriod }}
            </v-chip>
          </div>
        </v-card-text>
        <v-card-text class="pa-0">
          <v-data-table-server
            :headers="headers"
            :items="items"
            :items-length="totalItems"
            :items-per-page="itemsPerPage"
            :page="page"
            :loading="loading"
            item-value="id"
            class="threat-intel-table"
            @update:options="onTableOptionsUpdate"
          >
            <template #item.identifier="{ item }">
              <button
                type="button"
                class="intel-link"
                :class="{ 'intel-link--disabled': !hasItemAction(item) }"
                :disabled="!hasItemAction(item)"
                @click="openItem(item)"
              >
                {{ item.identifier }}
              </button>
              <div class="intel-link__title">{{ item.title }}</div>
            </template>

            <template #item.type="{ item }">
              <v-chip
                :color="getTypeColor(item.type)"
                size="small"
                variant="tonal"
              >
                {{ getTypeLabel(item.type) }}
              </v-chip>
            </template>

            <template #item.context="{ item }">
              <div class="context-cell">{{ item.context || '-' }}</div>
            </template>

            <template #item.attributes="{ item }">
              <div v-if="getAttributeChips(item).length" class="attribute-cell">
                <v-chip
                  v-for="tag in getAttributeChips(item)"
                  :key="`${item.id}-${tag}`"
                  size="x-small"
                  variant="outlined"
                  :color="getAttributeColor(tag)"
                >
                  {{ tag }}
                </v-chip>
              </div>
              <span v-else class="text-medium-emphasis">-</span>
            </template>

            <template #item.timestamp="{ item }">
              <div class="timestamp-cell">
                <div>{{ formatTimestamp(item.timestamp) }}</div>
                <div class="timestamp-cell__relative">{{ formatRelativeTime(item.timestamp) }}</div>
              </div>
            </template>

            <template #item.hitrack="{ item }">
              <div class="presence-cell">
                <template v-if="item.currently_present || item.relevant_in_hitrack">
                  <v-tooltip v-if="item.currently_present" location="top">
                    <template #activator="{ props }">
                      <v-chip
                        v-bind="props"
                        size="small"
                        color="primary"
                        variant="tonal"
                      >
                        Present
                      </v-chip>
                    </template>
                    <span>{{ presentTooltip }}</span>
                  </v-tooltip>
                  <v-tooltip v-else location="top">
                    <template #activator="{ props }">
                      <v-chip
                        v-bind="props"
                        size="small"
                        color="success"
                        variant="tonal"
                      >
                        Relevant
                      </v-chip>
                    </template>
                    <span>{{ relevantTooltip }}</span>
                  </v-tooltip>
                  <div
                    v-if="getThreatIntelMatchSummary(item)"
                    class="presence-cell__summary"
                  >
                    {{ getThreatIntelMatchSummary(item) }}
                  </div>
                </template>
                <span v-else class="text-medium-emphasis">-</span>
              </div>
            </template>

            <template #item.severity="{ item }">
              <v-chip
                v-if="item.severity"
                :color="getSignalColor(item)"
                size="small"
                variant="tonal"
              >
                {{ item.severity }}
              </v-chip>
              <span v-else class="text-medium-emphasis">-</span>
            </template>

            <template #item.actions="{ item }">
              <v-btn
                v-if="hasItemAction(item)"
                icon="mdi-open-in-new"
                size="small"
                variant="text"
                color="primary"
                @click="openItem(item)"
              />
              <span v-else class="text-medium-emphasis">-</span>
            </template>
          </v-data-table-server>
        </v-card-text>
      </v-card>
    </v-container>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { DataTableHeader, DataTableSortItem } from 'vuetify'

import api from '../plugins/axios'
import { notificationService } from '../plugins/notifications'
import { getSeverityColor } from '../utils/colors'
import type {
  WeeklyThreatIntelListItem,
  WeeklyThreatIntelResponse,
  WeeklyThreatIntelType,
} from '../types/interfaces'

const router = useRouter()

const items = ref<WeeklyThreatIntelListItem[]>([])
const loading = ref(false)
const page = ref(1)
const itemsPerPage = ref(50)
const totalItems = ref(0)
const selectedIntelType = ref<WeeklyThreatIntelType>('all')
const periodStart = ref<string | null>(null)
const periodEnd = ref<string | null>(null)

const intelTypeOptions = [
  { title: 'All Weekly Intel', value: 'all' },
  { title: 'Observed In HITrack', value: 'observed' },
  { title: 'New CISA KEV', value: 'kev' },
  { title: 'Supply-Chain Advisories', value: 'supply_chain' },
]

const headers: DataTableHeader[] = [
  { title: 'Item', key: 'identifier', sortable: false, minWidth: 260 },
  { title: 'Type', key: 'type', sortable: false, width: 170 },
  { title: 'Context', key: 'context', sortable: false, minWidth: 280 },
  { title: 'Attributes', key: 'attributes', sortable: false, minWidth: 250 },
  { title: 'When', key: 'timestamp', sortable: false, width: 220 },
  { title: 'HITrack', key: 'hitrack', sortable: false, width: 160 },
  { title: 'Signal', key: 'severity', sortable: false, width: 150 },
  { title: 'Actions', key: 'actions', sortable: false, width: 90, align: 'end' },
]

const formatDateOnly = (value?: string | null) => {
  if (!value) return 'Current Week'
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month, day] = value.split('-').map(Number)
    return new Date(year, month - 1, day).toLocaleDateString()
  }
  return new Date(value).toLocaleDateString()
}

const formattedPeriod = computed(() => {
  if (!periodStart.value || !periodEnd.value) {
    return 'Current Week'
  }
  return `${formatDateOnly(periodStart.value)} - ${formatDateOnly(periodEnd.value)}`
})

const relevantTooltip = 'Matched in HITrack historical data at least once.'
const presentTooltip = 'Currently linked to scanned images in HITrack.'

const getAttributeChips = (item: WeeklyThreatIntelListItem) => {
  const sourceLabels = item.source_labels || []
  const tags = item.tags || []
  return [...new Set([...sourceLabels, ...tags])].slice(0, 6)
}

const getThreatIntelMatchSummary = (item: WeeklyThreatIntelListItem) => {
  const match = item.hitrack_match
  if (!match) return ''

  const summaryParts = []
  if (item.matched_by && item.matched_identifier) {
    summaryParts.push(`By ${item.matched_by}: ${item.matched_identifier}`)
  } else if (item.matched_vulnerability_id) {
    summaryParts.push(`Matched ${item.matched_vulnerability_id}`)
  }

  if (match.tags?.length) {
    const tagPreview = match.tags.slice(0, 2).join(', ')
    const extraTagCount = Math.max(match.tag_count - Math.min(match.tag_count, 2), 0)
    summaryParts.push(`Seen in ${tagPreview}${extraTagCount > 0 ? ` +${extraTagCount}` : ''}`)
  } else if (match.images?.length) {
    const imagePreview = match.images.slice(0, 1).join(', ')
    const extraImageCount = Math.max(match.image_count - Math.min(match.image_count, 1), 0)
    summaryParts.push(`Image ${imagePreview}${extraImageCount > 0 ? ` +${extraImageCount}` : ''}`)
  } else if (match.repositories?.length) {
    const repositoryPreview = match.repositories.slice(0, 2).join(', ')
    const extraRepositoryCount = Math.max(match.repository_count - Math.min(match.repository_count, 2), 0)
    summaryParts.push(`Repo ${repositoryPreview}${extraRepositoryCount > 0 ? ` +${extraRepositoryCount}` : ''}`)
  }

  return summaryParts.join(' · ')
}

const fetchThreatIntel = async () => {
  loading.value = true
  try {
    const response = await api.get<WeeklyThreatIntelResponse>('stats/weekly-threat-intel/', {
      params: {
        page: page.value,
        page_size: itemsPerPage.value,
        type: selectedIntelType.value,
      },
    })
    items.value = response.data.results || []
    totalItems.value = response.data.count || 0
    periodStart.value = response.data.period_start || null
    periodEnd.value = response.data.period_end || null
  } catch (error) {
    console.error('Error fetching weekly threat intel:', error)
    notificationService.error('Failed to load weekly threat intel')
  } finally {
    loading.value = false
  }
}

const hasItemAction = (item: WeeklyThreatIntelListItem) => Boolean(item.target_uuid || item.external_url)

const openItem = (item: WeeklyThreatIntelListItem) => {
  if (item.target_type === 'vulnerability' && item.target_uuid) {
    router.push({ name: 'vulnerability-detail', params: { uuid: item.target_uuid } })
    return
  }
  if (item.external_url) {
    window.open(item.external_url, '_blank', 'noopener,noreferrer')
  }
}

const onTableOptionsUpdate = (options: { page: number; itemsPerPage: number; sortBy: DataTableSortItem[] }) => {
  const pageChanged = page.value !== options.page
  const itemsPerPageChanged = itemsPerPage.value !== options.itemsPerPage
  if (!pageChanged && !itemsPerPageChanged) {
    return
  }

  page.value = options.page
  itemsPerPage.value = options.itemsPerPage
}

const goBackToDashboard = () => {
  router.push('/')
}

const formatTimestamp = (timestamp?: string | null) => {
  if (!timestamp) return 'Unknown time'
  if (/^\d{4}-\d{2}-\d{2}$/.test(timestamp)) {
    return formatDateOnly(timestamp)
  }
  return new Date(timestamp).toLocaleString()
}

const formatRelativeTime = (timestamp?: string | null) => {
  if (!timestamp) return ''
  try {
    const baseDate = /^\d{4}-\d{2}-\d{2}$/.test(timestamp)
      ? new Date(`${timestamp}T00:00:00`)
      : new Date(timestamp)
    const now = new Date()
    const diffInSeconds = Math.floor((now.getTime() - baseDate.getTime()) / 1000)
    if (diffInSeconds < 60) return 'just now'
    if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)} minutes ago`
    if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)} hours ago`
    return `${Math.floor(diffInSeconds / 86400)} days ago`
  } catch {
    return ''
  }
}

const getTypeLabel = (type: WeeklyThreatIntelListItem['type']) => {
  switch (type) {
    case 'observed':
      return 'Observed'
    case 'kev':
      return 'CISA KEV'
    case 'supply_chain':
      return 'Supply Chain'
    default:
      return type
  }
}

const getTypeColor = (type: WeeklyThreatIntelListItem['type']) => {
  switch (type) {
    case 'observed':
      return 'info'
    case 'kev':
      return 'error'
    case 'supply_chain':
      return 'warning'
    default:
      return 'grey'
  }
}

const getSignalColor = (item: WeeklyThreatIntelListItem) => {
  if (item.type === 'kev') return 'error'
  if (item.severity === 'MALWARE') return 'error'
  return getSeverityColor(item.severity || 'UNKNOWN')
}

const getAttributeColor = (tag: string) => {
  const normalized = tag.toLowerCase()
  if (normalized === 'osv') return 'info'
  if (normalized === 'github') return 'secondary'
  if (normalized === 'cisa kev') return 'error'
  if (normalized === 'malware') return 'error'
  if (normalized.includes('fix available')) return 'success'
  if (normalized.includes('no fix')) return 'error'
  if (normalized.includes('severity:')) return 'warning'
  return 'default'
}

watch(selectedIntelType, () => {
  if (page.value !== 1) {
    page.value = 1
    return
  }
  fetchThreatIntel()
})

watch([page, itemsPerPage], fetchThreatIntel)

onMounted(fetchThreatIntel)
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 24px;
}

.threat-intel-card {
  border-radius: 16px;
  overflow: hidden;
}

.filters-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.filters-bar__left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.intel-type-filter {
  max-width: 280px;
}

.intel-link {
  border: 0;
  background: transparent;
  padding: 0;
  color: rgb(var(--v-theme-primary));
  font-weight: 700;
  cursor: pointer;
  text-align: left;
}

.intel-link--disabled {
  color: inherit;
  cursor: default;
}

.intel-link__title {
  margin-top: 4px;
  color: rgba(0, 0, 0, 0.68);
  font-size: 0.88rem;
  line-height: 1.35;
}

.context-cell {
  white-space: normal;
  line-height: 1.35;
}

.attribute-cell {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  min-height: 32px;
}

.presence-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  min-height: 32px;
}

.presence-cell__summary {
  color: rgba(0, 0, 0, 0.62);
  font-size: 0.78rem;
  line-height: 1.3;
  white-space: normal;
}

.intel-tooltip {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-width: 280px;
}

.timestamp-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.timestamp-cell__relative {
  color: rgba(0, 0, 0, 0.58);
  font-size: 0.8rem;
}

@media (max-width: 960px) {
  .page-header {
    flex-direction: column;
  }

  .intel-type-filter {
    max-width: 100%;
    width: 100%;
  }
}
</style>
