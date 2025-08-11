/**
 * Color mapping utilities for UI components
 */

// Vulnerability type color mapping
export const VULNERABILITY_TYPE_COLORS = {
  'CVE': 'error',
  'GHSA': 'warning',
  'RUSTSEC': 'orange',
  'PYSEC': 'blue',
  'NPM': 'red'
} as const

// Severity color mapping
export const SEVERITY_COLORS = {
  'CRITICAL': 'error',
  'HIGH': 'warning',
  'MEDIUM': 'orange',
  'LOW': 'info',
  'UNKNOWN': 'grey'
} as const

// Component type color mapping
export const COMPONENT_TYPE_COLORS = {
  'unknown': 'grey',
  'npm': 'red',
  'pypi': 'blue',
  'maven': 'green',
  'gem': 'purple',
  'go': 'cyan',
  'nuget': 'orange',
  'deb': 'grey'
} as const

/**
 * Get color for vulnerability type
 */
export const getVulnerabilityTypeColor = (type: string): string => 
  VULNERABILITY_TYPE_COLORS[type as keyof typeof VULNERABILITY_TYPE_COLORS] || 'grey'

/**
 * Get color for severity level
 */
export const getSeverityColor = (severity: string): string => 
  SEVERITY_COLORS[severity.toUpperCase() as keyof typeof SEVERITY_COLORS] || 'grey'

/**
 * Get color for component type
 */
export const getComponentTypeColor = (type: string): string => 
  COMPONENT_TYPE_COLORS[type?.toLowerCase() as keyof typeof COMPONENT_TYPE_COLORS] || 'grey'

/**
 * Get color for EPSS score
 */
export const getEpssColor = (epss: number): string => 
  epss >= 0.7 ? 'error' : epss >= 0.4 ? 'warning' : epss >= 0.2 ? 'orange' : 'success'

/**
 * Get color for processing status
 */
export const getProcessingStatusColor = (status: string): string => {
  switch (status) {
    case 'success': return 'success'
    case 'pending': return 'warning'
    case 'in_process': return 'info'
    case 'error': return 'error'
    default: return 'grey'
  }
}

/**
 * Get icon for processing status
 */
export const getProcessingStatusIcon = (status: string): string => {
  switch (status) {
    case 'success': return 'mdi-check-circle'
    case 'pending': return 'mdi-timer-sand'
    case 'in_process': return 'mdi-progress-clock'
    case 'error': return 'mdi-alert-circle'
    default: return 'mdi-help-circle'
  }
}

/**
 * Get color for EPSS data source
 */
export const getEpssSourceColor = (source: string): string => {
  switch (source) {
    case 'FIRST-EPSS':
      return 'primary'
    case 'Grype':
      return 'success'
    case 'manual':
      return 'warning'
    default:
      return 'grey'
  }
}

/**
 * Get icon for EPSS data source
 */
export const getEpssSourceIcon = (source: string): string => {
  switch (source) {
    case 'FIRST-EPSS':
      return 'mdi-database'
    case 'Grype':
      return 'mdi-magnify-scan'
    case 'manual':
      return 'mdi-pencil'
    default:
      return 'mdi-information'
  }
}

/**
 * Get display name for EPSS data source
 */
export const getEpssSourceDisplay = (source: string): string => {
  switch (source) {
    case 'FIRST-EPSS':
      return 'FIRST API'
    case 'Grype':
      return 'Grype Scan'
    case 'manual':
      return 'Manual Entry'
    default:
      return source
  }
} 