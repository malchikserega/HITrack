<template>
  <v-card class="weekly-threat-card" elevation="2">
    <v-card-title class="text-h6 font-weight-bold pa-4 pb-2 d-flex align-center justify-space-between">
      <span>Weekly Threat Intel</span>
      <v-chip size="small" color="primary" variant="tonal">
        {{ formattedPeriod }}
      </v-chip>
    </v-card-title>
    <v-card-text class="pa-4 pt-0">
      <v-row>
        <v-col cols="12" md="4">
          <div class="intel-section">
            <div class="intel-section__header">
              <div class="intel-section__title">Observed In HITrack</div>
              <v-chip size="small" color="info" variant="tonal">
                {{ intel?.observed_this_week?.count || 0 }}
              </v-chip>
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
                  {{ entry.type }} · {{ formatDate(entry.created_at) }}
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
              <div class="intel-section__title">New KEV This Week</div>
              <v-chip size="small" color="error" variant="tonal">
                {{ intel?.kev_added_this_week?.count || 0 }}
              </v-chip>
            </div>
            <div v-if="!intel?.kev_added_this_week?.entries?.length" class="intel-empty">
              No new CISA KEV additions this week.
            </div>
            <v-list v-else density="compact" class="intel-list">
              <v-list-item
                v-for="entry in intel.kev_added_this_week.entries"
                :key="entry.vulnerability_id"
                class="intel-item intel-item--clickable"
                @click="openExternal(entry.url)"
              >
                <template #prepend>
                  <v-icon color="error">mdi-shield-alert</v-icon>
                </template>
                <v-list-item-title class="intel-item__title">
                  {{ entry.vulnerability_id }}
                </v-list-item-title>
                <v-list-item-subtitle class="intel-item__subtitle">
                  {{ entry.vendor || 'Unknown vendor' }} · {{ entry.product || 'Unknown product' }}
                </v-list-item-subtitle>
                <template #append>
                  <div class="intel-item__meta">
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
              <div class="intel-section__title">Supply-Chain Advisories</div>
              <v-chip size="small" color="warning" variant="tonal">
                {{ intel?.supply_chain_this_week?.count || 0 }}
              </v-chip>
            </div>
            <div v-if="!intel?.supply_chain_this_week?.entries?.length" class="intel-empty">
              No new supply-chain advisories this week.
            </div>
            <v-list v-else density="compact" class="intel-list">
              <v-list-item
                v-for="entry in intel.supply_chain_this_week.entries"
                :key="entry.advisory_id || entry.url"
                class="intel-item intel-item--clickable"
                @click="openExternal(entry.url)"
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
                  {{ entry.packages?.length ? entry.packages.slice(0, 2).join(', ') : entry.title }}
                </v-list-item-subtitle>
                <template #append>
                  <div class="intel-item__meta">
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

interface ObservedThreatEntry {
  uuid: string
  vulnerability_id: string
  severity: string
  type: string
  created_at: string
  epss: number
  cisa_kev: boolean
  exploit_available: boolean
}

interface KevThreatEntry {
  vulnerability_id: string
  vendor?: string | null
  product?: string | null
  date_added: string
  ransomware_use?: string | null
  url?: string | null
}

interface SupplyChainEntry {
  advisory_id?: string | null
  title: string
  severity?: string | null
  ecosystem: string
  type: string
  packages?: string[]
  published_at?: string | null
  url?: string | null
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
    entries: KevThreatEntry[]
  }
  supply_chain_this_week?: {
    count: number
    entries: SupplyChainEntry[]
  }
}

const props = defineProps<{
  intel?: WeeklyThreatIntel | null
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

const openLocalVulnerability = (uuid?: string) => {
  if (!uuid) return
  router.push({ name: 'vulnerability-detail', params: { uuid } })
}

const openExternal = (url?: string | null) => {
  if (!url) return
  window.open(url, '_blank', 'noopener,noreferrer')
}
</script>

<style scoped>
.weekly-threat-card {
  border-radius: 12px;
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
