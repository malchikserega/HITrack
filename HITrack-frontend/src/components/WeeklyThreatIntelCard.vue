<template>
  <v-card class="weekly-threat-card" elevation="2">
    <v-card-title class="text-h6 font-weight-bold pa-4 pb-2 d-flex align-center justify-space-between">
      <span>Weekly Threat Intel</span>
      <div class="weekly-threat-card__actions">
        <v-chip size="small" color="primary" variant="tonal">
          {{ formattedPeriod }}
        </v-chip>
        <v-btn
          v-if="showViewAll"
          variant="text"
          color="primary"
          size="small"
          @click="emit('view-all')"
        >
          View All
        </v-btn>
      </div>
    </v-card-title>
    <v-card-text class="pa-4 pt-0">
      <v-row>
        <v-col cols="12" md="4">
          <div class="intel-section">
            <div class="intel-section__header">
              <div class="intel-section__title-row">
                <div class="intel-section__title">Observed In HITrack</div>
                <v-tooltip location="top">
                  <template #activator="{ props }">
                    <v-icon
                      v-bind="props"
                      size="16"
                      color="medium-emphasis"
                    >
                      mdi-information-outline
                    </v-icon>
                  </template>
                  <span>{{ observedTooltip }}</span>
                </v-tooltip>
              </div>
              <v-tooltip location="top">
                <template #activator="{ props }">
                  <v-chip v-bind="props" size="small" color="info" variant="tonal">
                    {{ intel?.observed_this_week?.count || 0 }}
                  </v-chip>
                </template>
                <span>{{ observedTooltip }}</span>
              </v-tooltip>
            </div>
            <div v-if="!intel?.observed_this_week?.entries?.length" class="intel-empty">
              No new observed vulnerabilities this week.
            </div>
            <v-list v-else density="compact" class="intel-list">
              <v-list-item
                v-for="entry in intel.observed_this_week.entries"
                :key="entry.uuid"
                class="intel-item intel-item--clickable"
                @click="openLocalVulnerability(entry.uuid)"
              >
                <template #prepend>
                  <v-chip
                    size="x-small"
                    :color="getSeverityColor(entry.severity)"
                    variant="tonal"
                  >
                    {{ entry.severity }}
                  </v-chip>
                </template>
                <v-list-item-title class="intel-item__title">
                  {{ entry.vulnerability_id }}
                </v-list-item-title>
                <v-list-item-subtitle class="intel-item__subtitle">
                  <div>{{ entry.type }} · {{ formatDate(entry.created_at) }}</div>
                  <div
                    v-if="getThreatIntelMatchSummary(entry)"
                    class="intel-item__match"
                  >
                    {{ getThreatIntelMatchSummary(entry) }}
                  </div>
                </v-list-item-subtitle>
                <template #append>
                  <div class="intel-item__meta">
                    <v-chip
                      v-if="entry.cisa_kev"
                      size="x-small"
                      color="error"
                      variant="tonal"
                    >
                      KEV
                    </v-chip>
                    <v-chip
                      v-else-if="entry.exploit_available"
                      size="x-small"
                      color="warning"
                      variant="tonal"
                    >
                      Exploit
                    </v-chip>
                    <v-chip
                      v-if="entry.epss && entry.epss > 0"
                      size="x-small"
                      color="secondary"
                      variant="tonal"
                    >
                      EPSS {{ entry.epss }}
                    </v-chip>
                  </div>
                </template>
              </v-list-item>
            </v-list>
          </div>
        </v-col>

        <v-col cols="12" md="4">
          <div class="intel-section">
            <div class="intel-section__header">
              <div>
                <div class="intel-section__title-row">
                  <div class="intel-section__title">New KEV This Week</div>
                  <v-tooltip location="top">
                    <template #activator="{ props }">
                      <v-icon
                        v-bind="props"
                        size="16"
                        color="medium-emphasis"
                      >
                        mdi-information-outline
                      </v-icon>
                    </template>
                    <span>{{ kevTooltip }}</span>
                  </v-tooltip>
                </div>
                <div class="intel-section__summary">
                  <v-tooltip location="top">
                    <template #activator="{ props }">
                      <v-chip v-bind="props" size="x-small" color="success" variant="tonal">
                        Matched {{ intel?.kev_added_this_week?.relevant_in_hitrack_count || 0 }}
                      </v-chip>
                    </template>
                    <span>{{ relevantTooltip }}</span>
                  </v-tooltip>
                  <v-tooltip location="top">
                    <template #activator="{ props }">
                      <v-chip v-bind="props" size="x-small" color="primary" variant="tonal">
                        Confirmed {{ intel?.kev_added_this_week?.currently_present_count || 0 }}
                      </v-chip>
                    </template>
                    <span>{{ presentTooltip }}</span>
                  </v-tooltip>
                </div>
              </div>
              <v-tooltip location="top">
                <template #activator="{ props }">
                  <v-chip v-bind="props" size="small" color="error" variant="tonal">
                    {{ intel?.kev_added_this_week?.count || 0 }}
                  </v-chip>
                </template>
                <span>{{ kevTooltip }}</span>
              </v-tooltip>
            </div>
            <div v-if="!intel?.kev_added_this_week?.entries?.length" class="intel-empty">
              No new CISA KEV additions this week.
            </div>
            <v-list v-else density="compact" class="intel-list">
              <v-list-item
                v-for="entry in intel.kev_added_this_week.entries"
                :key="entry.vulnerability_id"
                class="intel-item intel-item--clickable"
                @click="openKevEntry(entry)"
              >
                <template #prepend>
                  <v-icon color="error">mdi-shield-alert</v-icon>
                </template>
                <v-list-item-title class="intel-item__title">
                  {{ entry.vulnerability_id }}
                </v-list-item-title>
                <v-list-item-subtitle class="intel-item__subtitle">
                  <div>{{ entry.vendor || 'Unknown vendor' }} · {{ entry.product || 'Unknown product' }}</div>
                  <div
                    v-if="getThreatIntelMatchSummary(entry)"
                    class="intel-item__match"
                  >
                    {{ getThreatIntelMatchSummary(entry) }}
                  </div>
                </v-list-item-subtitle>
                <template #append>
                  <div class="intel-item__meta">
                    <v-tooltip v-if="entry.currently_present" location="top">
                      <template #activator="{ props }">
                        <v-chip
                          v-bind="props"
                          size="x-small"
                          color="primary"
                          variant="tonal"
                        >
                          Confirmed
                        </v-chip>
                      </template>
                      <span>{{ presentTooltip }}</span>
                    </v-tooltip>
                    <v-tooltip v-else-if="entry.relevant_in_hitrack" location="top">
                      <template #activator="{ props }">
                        <v-chip
                          v-bind="props"
                          size="x-small"
                          color="success"
                          variant="tonal"
                        >
                          Historical
                        </v-chip>
                      </template>
                      <span>{{ relevantTooltip }}</span>
                    </v-tooltip>
                    <v-chip
                      size="x-small"
                      color="error"
                      variant="tonal"
                    >
                      {{ formatDate(entry.date_added) }}
                    </v-chip>
                    <v-chip
                      v-if="entry.ransomware_use === 'Known'"
                      size="x-small"
                      color="warning"
                      variant="tonal"
                    >
                      Ransomware
                    </v-chip>
                  </div>
                </template>
              </v-list-item>
            </v-list>
          </div>
        </v-col>

        <v-col cols="12" md="4">
          <div class="intel-section">
            <div class="intel-section__header">
              <div>
                <div class="intel-section__title-row">
                  <div class="intel-section__title">Supply-Chain Advisories</div>
                  <v-tooltip location="top">
                    <template #activator="{ props }">
                      <v-icon
                        v-bind="props"
                        size="16"
                        color="medium-emphasis"
                      >
                        mdi-information-outline
                      </v-icon>
                    </template>
                    <span>{{ supplyChainTooltip }}</span>
                  </v-tooltip>
                </div>
                <div class="intel-section__summary">
                  <v-tooltip location="top">
                    <template #activator="{ props }">
                      <v-chip v-bind="props" size="x-small" color="success" variant="tonal">
                        Matched {{ intel?.supply_chain_this_week?.relevant_in_hitrack_count || 0 }}
                      </v-chip>
                    </template>
                    <span>{{ relevantTooltip }}</span>
                  </v-tooltip>
                  <v-tooltip location="top">
                    <template #activator="{ props }">
                      <v-chip v-bind="props" size="x-small" color="primary" variant="tonal">
                        Confirmed {{ intel?.supply_chain_this_week?.currently_present_count || 0 }}
                      </v-chip>
                    </template>
                    <span>{{ presentTooltip }}</span>
                  </v-tooltip>
                </div>
              </div>
              <v-tooltip location="top">
                <template #activator="{ props }">
                  <v-chip v-bind="props" size="small" color="warning" variant="tonal">
                    {{ intel?.supply_chain_this_week?.count || 0 }}
                  </v-chip>
                </template>
                <span>{{ supplyChainTooltip }}</span>
              </v-tooltip>
            </div>
            <div v-if="!intel?.supply_chain_this_week?.entries?.length" class="intel-empty">
              No new supply-chain advisories this week.
            </div>
            <v-list v-else density="compact" class="intel-list">
              <v-list-item
                v-for="entry in intel.supply_chain_this_week.entries"
                :key="entry.advisory_id || entry.url"
                class="intel-item intel-item--clickable"
                @click="openSupplyChainEntry(entry)"
              >
                <template #prepend>
                  <v-chip
                    size="x-small"
                    :color="entry.type === 'malware' ? 'error' : 'warning'"
                    variant="tonal"
                  >
                    {{ entry.ecosystem }}
                  </v-chip>
                </template>
                <v-list-item-title class="intel-item__title">
                  {{ entry.advisory_id || 'Advisory' }}
                </v-list-item-title>
                <v-list-item-subtitle class="intel-item__subtitle">
                  <div>{{ entry.packages?.length ? entry.packages.slice(0, 2).join(', ') : entry.title }}</div>
                  <div
                    v-if="getThreatIntelMatchSummary(entry)"
                    class="intel-item__match"
                  >
                    {{ getThreatIntelMatchSummary(entry) }}
                  </div>
                  <div
                    v-if="getSupplyChainChips(entry).length"
                    class="intel-item__tags"
                  >
                    <v-chip
                      v-for="tag in getSupplyChainChips(entry)"
                      :key="`${entry.advisory_id || entry.url}-${tag}`"
                      size="x-small"
                      variant="outlined"
                      :color="getSupplyChainTagColor(tag)"
                    >
                      {{ tag }}
                    </v-chip>
                  </div>
                </v-list-item-subtitle>
                <template #append>
                  <div class="intel-item__meta">
                    <v-tooltip v-if="entry.currently_present" location="top">
                      <template #activator="{ props }">
                        <v-chip
                          v-bind="props"
                          size="x-small"
                          color="primary"
                          variant="tonal"
                        >
                          Confirmed
                        </v-chip>
                      </template>
                      <span>{{ presentTooltip }}</span>
                    </v-tooltip>
                    <v-tooltip v-else-if="entry.relevant_in_hitrack" location="top">
                      <template #activator="{ props }">
                        <v-chip
                          v-bind="props"
                          size="x-small"
                          color="success"
                          variant="tonal"
                        >
                          Historical
                        </v-chip>
                      </template>
                      <span>{{ relevantTooltip }}</span>
                    </v-tooltip>
                    <v-chip
                      v-if="entry.severity"
                      size="x-small"
                      :color="getSeverityColor(entry.severity)"
                      variant="tonal"
                    >
                      {{ entry.severity }}
                    </v-chip>
                    <v-chip
                      v-if="entry.type === 'malware'"
                      size="x-small"
                      color="error"
                      variant="tonal"
                    >
                      Malware
                    </v-chip>
                  </div>
                </template>
              </v-list-item>
            </v-list>
          </div>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { getSeverityColor } from '../utils/colors'
import { openSafeExternalUrl } from '../utils/urls'

interface ThreatIntelHitrackMatch {
  repository_count: number
  repositories: string[]
  tag_count: number
  tags: string[]
  image_count: number
  images: string[]
  component_count: number
  components: Array<{
    component_version_uuid: string
    name: string
    version: string
    ecosystem: string
    image_count: number
    images: string[]
  }>
}

interface ObservedThreatEntry {
  uuid: string
  vulnerability_id: string
  severity: string
  type: string
  created_at: string
  epss: number
  cisa_kev: boolean
  exploit_available: boolean
  matched_identifier?: string | null
  matched_by?: string | null
  matched_vulnerability_id?: string | null
  hitrack_match?: ThreatIntelHitrackMatch | null
}

interface KevThreatEntry {
  vulnerability_id: string
  vendor?: string | null
  product?: string | null
  date_added: string
  ransomware_use?: string | null
  url?: string | null
  relevant_in_hitrack?: boolean
  currently_present?: boolean
  target_uuid?: string | null
  matched_identifier?: string | null
  matched_by?: string | null
  matched_vulnerability_id?: string | null
  hitrack_match?: ThreatIntelHitrackMatch | null
}

interface SupplyChainEntry {
  advisory_id?: string | null
  osv_id?: string | null
  ghsa_id?: string | null
  cve_id?: string | null
  aliases?: string[]
  title: string
  severity?: string | null
  ecosystem: string
  type: string
  packages?: string[]
  published_at?: string | null
  modified_at?: string | null
  url?: string | null
  source_labels?: string[]
  tags?: string[]
  relevant_in_hitrack?: boolean
  currently_present?: boolean
  target_uuid?: string | null
  matched_identifier?: string | null
  matched_by?: string | null
  matched_vulnerability_id?: string | null
  hitrack_match?: ThreatIntelHitrackMatch | null
}

interface WeeklyThreatIntel {
  period_start?: string
  period_end?: string
  observed_this_week?: {
    count: number
    entries: ObservedThreatEntry[]
  }
  kev_added_this_week?: {
    count: number
    relevant_in_hitrack_count?: number
    currently_present_count?: number
    entries: KevThreatEntry[]
  }
  supply_chain_this_week?: {
    count: number
    relevant_in_hitrack_count?: number
    currently_present_count?: number
    entries: SupplyChainEntry[]
  }
}

const props = defineProps<{
  intel?: WeeklyThreatIntel | null
  showViewAll?: boolean
}>()
const emit = defineEmits<{
  (e: 'view-all'): void
}>()

const router = useRouter()

const formatDate = (value?: string | null) => {
  if (!value) return 'Unknown date'
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month, day] = value.split('-').map(Number)
    return new Date(year, month - 1, day).toLocaleDateString()
  }
  return new Date(value).toLocaleDateString()
}

const formattedPeriod = computed(() => {
  if (!props.intel?.period_start || !props.intel?.period_end) {
    return 'Current Week'
  }
  return `${formatDate(props.intel.period_start)} - ${formatDate(props.intel.period_end)}`
})

const observedTooltip = 'Vulnerabilities first seen in HITrack during the current week.'
const kevTooltip = 'New entries added to the official CISA Known Exploited Vulnerabilities catalog this week.'
const supplyChainTooltip = 'New weekly package or malware advisories from external supply-chain sources such as GitHub Advisory data and OSV.'
const relevantTooltip = 'This advisory matches a HITrack vulnerability record. A Historical badge means no current image is linked to it.'
const presentTooltip = 'Scanner evidence confirms this vulnerability on an exact component version in at least one current image.'

const getThreatIntelMatchSummary = (
  entry: ObservedThreatEntry | KevThreatEntry | SupplyChainEntry,
) => {
  const match = entry.hitrack_match
  if (!match) return ''

  const summaryParts = []
  if (entry.matched_by && entry.matched_identifier) {
    summaryParts.push(`Matched by ${entry.matched_by}: ${entry.matched_identifier}`)
  } else if (entry.matched_vulnerability_id) {
    summaryParts.push(`Matched to ${entry.matched_vulnerability_id}`)
  }

  if (match.components?.length) {
    const componentPreview = match.components.slice(0, 2)
      .map(component => `${component.name} ${component.version}`)
      .join(', ')
    const extraComponentCount = Math.max(match.component_count - 2, 0)
    summaryParts.push(`Components ${componentPreview}${extraComponentCount > 0 ? ` +${extraComponentCount}` : ''}`)
    return summaryParts.join(' · ')
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

const getSupplyChainChips = (entry: SupplyChainEntry) => {
  const sourceLabels = entry.source_labels || []
  const tags = (entry.tags || []).filter(
    (tag) => !sourceLabels.includes(tag) && !tag.startsWith('Severity:')
  )
  return [...sourceLabels, ...tags].slice(0, 4)
}

const getSupplyChainTagColor = (tag: string) => {
  const normalized = tag.toLowerCase()
  if (normalized === 'osv') return 'info'
  if (normalized === 'github') return 'secondary'
  if (normalized === 'malware') return 'error'
  if (normalized.includes('fix available')) return 'success'
  if (normalized.includes('no fix')) return 'error'
  return 'default'
}

const openLocalVulnerability = (uuid?: string) => {
  if (!uuid) return
  router.push({ name: 'vulnerability-detail', params: { uuid } })
}

const openKevEntry = (entry: KevThreatEntry) => {
  if (entry.target_uuid) {
    openLocalVulnerability(entry.target_uuid)
    return
  }
  openExternal(entry.url)
}

const openSupplyChainEntry = (entry: SupplyChainEntry) => {
  if (entry.target_uuid) {
    openLocalVulnerability(entry.target_uuid)
    return
  }
  openExternal(entry.url)
}

const openExternal = (url?: string | null) => {
  openSafeExternalUrl(url)
}
</script>

<style scoped>
.weekly-threat-card {
  border-radius: 12px;
}

.weekly-threat-card__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.intel-section {
  height: 100%;
}

.intel-section__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  gap: 12px;
}

.intel-section__title {
  font-weight: 700;
  font-size: 1rem;
}

.intel-section__title-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.intel-section__summary {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
}

.intel-list {
  background: transparent;
  padding: 0;
}

.intel-item {
  border-radius: 10px;
  margin-bottom: 8px;
}

.intel-item--clickable {
  cursor: pointer;
}

.intel-item--clickable:hover {
  background: rgba(0, 0, 0, 0.04);
}

.intel-item__title {
  font-weight: 600;
  line-height: 1.3;
}

.intel-item__subtitle {
  line-height: 1.25;
}

.intel-item__match {
  margin-top: 4px;
  color: rgba(0, 0, 0, 0.62);
  font-size: 0.78rem;
  line-height: 1.3;
}

.intel-item__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}

.intel-item__meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}

.intel-empty {
  color: #6b7280;
  font-size: 0.92rem;
  padding: 12px 0;
}
</style>
