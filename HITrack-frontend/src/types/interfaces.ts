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
 */
export interface Repository extends BaseEntity {
  name: string
  url: string
  tag_count: number
  repository_type: 'docker' | 'helm' | 'none'
  scan_status: 'pending' | 'in_process' | 'success' | 'error' | 'none'
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
  details?: VulnerabilityDetails
  has_details: boolean
  exploit_available: boolean
  cisa_kev: boolean
  created_at: string
  updated_at: string
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
  has_sbom: boolean
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

export interface Stats {
  repositories: number
  images: number
  vulnerabilities: number
  components: number
}
