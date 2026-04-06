/**
 * Base interface for all entities
 */
export interface BaseEntity {
  id?: number
  uuid: string
  created_at: string
  updated_at: string
}

/**
 * Repository interface
 * When loaded from registry (e.g. get_acr_repos for JFrog), items may include
 * optional package_type ('docker' | 'helm') from the registry API.
 */
/** Minimal repo for fallback list (detail API returns { uuid, name }) */
export interface RepositoryFallbackItem {
  uuid: string
  name: string
}

export interface Repository extends BaseEntity {
  name: string
  url: string
  /** For JFrog: the Artifactory repo key (e.g. a8n-docker-local). Empty for ACR. */
  repo_key?: string
  tag_count: number
  repository_type: 'docker' | 'helm' | 'none'
  scan_status: 'pending' | 'in_process' | 'success' | 'error' | 'none'
  /** Set by get_acr_repos for JFrog; use when adding repos to set repository_type */
  package_type?: 'docker' | 'helm'
  /** For Helm repos: Docker repos to try when chart image refs fail (detail only) */
  image_fallback_repositories?: RepositoryFallbackItem[]
}

/**
 * Vulnerability Details interface
 */
export interface VulnerabilityDetails extends BaseEntity {
  cve_details_score?: number
  cve_details_severity?: string
  cve_details_published_date?: string
  cve_details_updated_date?: string
  cve_details_summary?: string
  cve_details_references?: string[]
  exploit_available: boolean
  exploit_public: boolean
  exploit_verified: boolean
  exploit_links?: string[]
  cisa_kev_known_exploited: boolean
  cisa_kev_date_added?: string
  cisa_kev_vendor_project?: string
  cisa_kev_product?: string
  cisa_kev_vulnerability_name?: string
  cisa_kev_short_description?: string
  cisa_kev_required_action?: string
  cisa_kev_due_date?: string
  cisa_kev_ransomware_use?: string
  cisa_kev_notes?: string
  cisa_kev_cwes?: string[]
  exploit_db_available: boolean
  exploit_db_verified: boolean
  exploit_db_count: number
  exploit_db_verified_count: number
  exploit_db_working_count: number
  exploit_db_links?: string[]
  last_updated: string
  data_source: string
  
  // EPSS information from FIRST API
  epss_score?: number
  epss_percentile?: number
  epss_date?: string
  epss_data_source?: string
  epss_last_updated?: string
}

/**
 * Vulnerability interface
 */
export interface Vulnerability extends BaseEntity {
  vulnerability_id: string
  vulnerability_type: string
  severity: string
  description?: string
  epss: number
  fixable?: boolean
  fix?: string
  fix_status?: string
  fix_state?: string
  fix_versions?: string[]
  details?: VulnerabilityDetails
  has_details: boolean
  exploit_available: boolean
  cisa_kev: boolean
  threat_intel_match?: VulnerabilityThreatIntelMatch
  weighted_risk_score?: number
  currently_present?: boolean
  fixability_category?: string
  affected_repositories_count?: number
  affected_tags_count?: number
  affected_releases_count?: number
  affected_images_count?: number
  active_images_count?: number
  created_at: string
  updated_at: string
}

export interface VulnerabilityRiskPrioritization {
  weighted_risk_score: number
  currently_present: boolean
  fixability_category: string
  affected_repositories_count: number
  affected_tags_count: number
  affected_releases_count: number
  affected_images_count: number
  active_images_count: number
}

export interface VulnerabilityThreatIntelEntry {
  intel_type: 'observed' | 'kev' | 'supply_chain'
  label: string
  identifier: string
  title: string
  timestamp?: string | null
  source_labels?: string[]
  tags?: string[]
  matched_by?: string | null
  matched_identifier?: string | null
  matched_vulnerability_id?: string | null
  currently_present?: boolean
  relevant_in_hitrack?: boolean
  hitrack_match?: WeeklyThreatIntelMatch | null
}

export interface VulnerabilityThreatIntelMatch {
  matched_this_week: boolean
  period_start?: string | null
  period_end?: string | null
  has_external_matches: boolean
  entries: VulnerabilityThreatIntelEntry[]
}

/**
 * Repository Tag interface
 */
export interface RepositoryTag extends BaseEntity {
  tag: string
  repository: Repository
  images?: Image[]
  processing_status?: 'pending' | 'in_process' | 'success' | 'error' | 'none'
}

/**
 * Image interface
 */
export interface Image extends BaseEntity {
  name: string
  digest: string
  scan_status: string
  lineage_label?: string
  lineage_source?: string
  os_distro_name?: string | null
  os_distro_version?: string | null
  os_eol_status?: string
  os_eol_source?: string
  os_eol_message?: string | null
  os_eol_checked_at?: string | null
  has_sbom: boolean
  has_grype: boolean
  findings: number
  unique_findings: number
  severity_counts: { [key: string]: number }
  components_count: number
  fully_fixable_components_count: number
  fixable_findings: number
  fixable_unique_findings: number
  fixable_severity_counts: { [key: string]: number }
  unique_severity_counts: { [key: string]: number }
  fixable_unique_severity_counts: { [key: string]: number }
  repository_info?: {
    repository_name: string
    repository_uuid: string
    tag: string
    tag_uuid: string
    repository_type: string
  }
  updated_at: string
  repository_tags?: RepositoryTag[]
  component_versions?: ComponentVersion[]
}

export interface ImageComparisonVariantTag {
  repository_name: string
  repository_uuid: string
  repository_type: string
  tag: string
  tag_uuid: string
}

export interface ImageComparisonVariant {
  uuid: string
  name: string
  logical_name: string
  registry_host: string
  repository_path: string
  digest: string | null
  scan_status: string
  has_sbom: boolean
  has_grype: boolean
  findings: number
  unique_findings: number
  components_count: number
  repository_tags: ImageComparisonVariantTag[]
  created_at: string
  updated_at: string
}

export interface ImageComparisonGroup {
  logical_name: string
  variant_count: number
  registry_count: number
  distinct_digests: number
  different_digests: boolean
  max_findings: number
  max_unique_findings: number
  max_components_count: number
  latest_updated_at: string
  status_breakdown: Record<string, number>
  variants: ImageComparisonVariant[]
}

export interface RootCauseRepositoryPreview {
  repository_uuid: string
  repository_name: string
  affected_images_count: number
  affected_tags_count: number
}

export interface RootCauseVulnerabilityPreview {
  uuid: string
  vulnerability_id: string
  severity: string
  epss: number
  cisa_kev: boolean
  exploit_available: boolean
  fix_status?: string | null
}

export interface SharedRootCause {
  uuid: string
  component_uuid: string
  component_name: string
  version: string
  component_type: string
  purl?: string | null
  latest_version?: string | null
  affected_repositories_count: number
  affected_tags_count: number
  affected_releases_count: number
  affected_images_count: number
  vulnerabilities_count: number
  critical_vulnerabilities_count: number
  high_vulnerabilities_count: number
  kev_vulnerabilities_count: number
  exploit_vulnerabilities_count: number
  weighted_risk_score: number
  fixability_category: string
  fixability_breakdown: {
    fixable_now: number
    fix_exists_but_not_in_repo: number
    no_fix: number
    fix_unknown: number
  }
  latest_seen_at?: string | null
  repositories_preview: RootCauseRepositoryPreview[]
  vulnerabilities_preview: RootCauseVulnerabilityPreview[]
  previews_loaded?: boolean
}

export interface SharedRootCauseResponse extends PaginatedResponse<SharedRootCause> {
  scope?: string
  component_type?: string
  fixability?: string
}

export interface SharedRootCausePreviewResponse {
  repositories_preview: RootCauseRepositoryPreview[]
  vulnerabilities_preview: RootCauseVulnerabilityPreview[]
}

export interface BaseLineageComponentPreview {
  component_uuid: string
  component_name: string
  version: string
  component_type: string
  affected_images_count: number
  vulnerabilities_count: number
}

export interface BaseLineageRootCause {
  key: string
  lineage_label: string
  lineage_source: string
  affected_repositories_count: number
  affected_tags_count: number
  affected_releases_count: number
  affected_images_count: number
  vulnerabilities_count: number
  critical_vulnerabilities_count: number
  high_vulnerabilities_count: number
  kev_vulnerabilities_count: number
  exploit_vulnerabilities_count: number
  weighted_risk_score: number
  fixability_category: string
  fixability_breakdown: {
    fixable_now: number
    fix_exists_but_not_in_repo: number
    no_fix: number
    fix_unknown: number
  }
  latest_seen_at?: string | null
  repositories_preview: RootCauseRepositoryPreview[]
  components_preview: BaseLineageComponentPreview[]
  vulnerabilities_preview: RootCauseVulnerabilityPreview[]
  previews_loaded?: boolean
}

export interface BaseLineageRootCauseResponse extends PaginatedResponse<BaseLineageRootCause> {
  scope?: string
  fixability?: string
  include_unknown?: boolean
}

export interface BaseLineageRootCausePreviewResponse {
  repositories_preview: RootCauseRepositoryPreview[]
  components_preview: BaseLineageComponentPreview[]
  vulnerabilities_preview: RootCauseVulnerabilityPreview[]
}

export interface BaseLineageRootCauseBatchPreviewEntry extends BaseLineageRootCausePreviewResponse {
  lineage_label: string
  lineage_source: string
}

export interface BaseLineageRootCauseBatchPreviewResponse {
  results: BaseLineageRootCauseBatchPreviewEntry[]
}

export type BaseLineageRootCauseSectionName = 'repositories' | 'components' | 'vulnerabilities'

export interface BaseLineageRootCauseSectionResponse<T> {
  offset: number
  limit: number
  next_offset: number | null
  has_more: boolean
  results: T[]
}

export interface VulnerabilityAffectedImageTag {
  repository_name: string
  repository_uuid: string
  repository_type: string
  tag: string
  tag_uuid: string
}

export interface VulnerabilityAffectedImage {
  uuid: string
  name: string
  digest: string
  scan_status: string
  has_sbom: boolean
  has_grype: boolean
  repository_tags: VulnerabilityAffectedImageTag[]
}

/**
 * Component interface
 */
export interface Component extends BaseEntity {
  name: string
  type: string
  purl?: string
  cpes?: string[]
  versions: ComponentVersion[]
  created_at: string
  updated_at: string
}

/**
 * Component Version interface
 */
export interface ComponentVersion extends BaseEntity {
  version: string
  component: Component
  images: Image[]
  vulnerabilities: Vulnerability[]
  vulnerabilities_count: number
  used_count: number
  dependency_scope?: string | null
  dependency_depth?: number | null
  package_scope?: string | null
  package_arch?: string | null
  package_distro?: string | null
  package_repo?: string | null
  package_channel?: string | null
  source_package?: string | null
  source_package_version?: string | null
  cataloger?: string | null
  metadata_type?: string | null
  created_at: string
  updated_at: string
}

/**
 * Generic paginated response interface
 */
export interface PaginatedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface RecentActivity {
  type: 'scan' | 'vulnerability'
  title: string
  timestamp: string
  severity?: string | null
  status?: string | null
  target_type?: 'repository' | 'vulnerability' | 'image' | 'component' | 'repository_tag' | 'release' | null
  target_uuid?: string | null
}

export type WeeklyThreatIntelType = 'all' | 'observed' | 'kev' | 'supply_chain'

export interface WeeklyThreatIntelMatch {
  repository_count: number
  repositories: string[]
  tag_count: number
  tags: string[]
  image_count: number
  images: string[]
}

export interface WeeklyThreatIntelListItem {
  id: string
  type: 'observed' | 'kev' | 'supply_chain'
  identifier: string
  title: string
  context: string
  timestamp: string
  severity?: string | null
  source_labels?: string[]
  tags?: string[]
  relevant_in_hitrack?: boolean
  currently_present?: boolean
  target_type?: 'vulnerability' | null
  target_uuid?: string | null
  external_url?: string | null
  matched_identifier?: string | null
  matched_by?: string | null
  matched_vulnerability_id?: string | null
  hitrack_match?: WeeklyThreatIntelMatch | null
}

export interface WeeklyThreatIntelResponse extends PaginatedResponse<WeeklyThreatIntelListItem> {
  period_start?: string
  period_end?: string
  selected_type?: WeeklyThreatIntelType
}

export interface Stats {
  repositories: number
  images: number
  vulnerabilities: number
  components: number
}

/** Container registry provider (ACR or Artifactory) */
export type RegistryProvider = 'acr' | 'jfrog'

export interface RegistryFallbackEntry {
  url: string
  name: string
  registry_uuid: string
}

export interface ContainerRegistry {
  uuid: string
  name: string
  api_url: string
  image_fallback_repositories?: RegistryFallbackEntry[]
}

// Celery Task Interfaces
export interface TaskResult {
  task_id: string;
  task_name: string;
  status: 'success' | 'error' | 'pending' | 'in_process' | 'revoked';
  result_summary?: any;
  duration?: number;
  created: string;
  updated?: string;
  traceback?: string;
}

export interface TaskResultList {
  task_id: string;
  task_name: string;
  status: 'success' | 'error' | 'pending' | 'in_process' | 'revoked';
  duration?: number;
  created: string;
}

export interface TaskStatistics {
  total_tasks: number;
  successful_tasks: number;
  failed_tasks: number;
  pending_tasks: number;
  running_tasks: number;
  average_duration: number;
  recent_tasks: TaskResultList[];
}

export interface TaskTypeStats {
  task_name: string;
  total: number;
  success: number;
  failure: number;
  pending: number;
  running: number;
}

export interface TaskDetails {
  task_id: string;
  task_name: string;
  status: string;
  created: string;
  updated?: string;
  duration?: number;
  result?: any;
  traceback?: string;
  meta?: any;
}

export interface PeriodicTask {
  id: number;
  name: string;
  task: string;
  enabled: boolean;
  schedule_info?: {
    type: 'interval' | 'crontab';
    every?: number;
    period?: string;
    minute?: string;
    hour?: string;
    day_of_week?: string;
    day_of_month?: string;
    month_of_year?: string;
  };
  next_run?: string;
  last_run_at?: string;
  total_run_count: number;
}
