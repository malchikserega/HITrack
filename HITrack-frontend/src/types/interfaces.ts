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
