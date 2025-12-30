<template>
  <v-card class="component-location-card">
    <v-card-title class="d-flex align-center">
      <v-icon class="mr-2">mdi-map-marker</v-icon>
      Component Locations
      <v-spacer></v-spacer>
      <v-chip
        :color="getSeverityColor(component.severity)"
        small
        v-if="component.severity"
      >
        {{ component.severity }}
      </v-chip>
    </v-card-title>

    <v-card-text>
      <div class="component-info mb-4">
        <div class="d-flex align-center mb-2">
          <v-icon class="mr-2">mdi-package-variant</v-icon>
          <strong>{{ componentName }}</strong>
          <v-chip
            size="small"
            color="primary"
            class="ml-2"
          >
            {{ componentVersion }}
          </v-chip>
        </div>
        
        <div class="component-details">
          <div class="detail-row">
            <span class="detail-label">Type:</span>
            <span class="detail-value">{{ componentType }}</span>
          </div>
          
          <div class="detail-row" v-if="componentPurl">
            <span class="detail-label">PURL:</span>
            <span class="detail-value font-mono">{{ componentPurl }}</span>
          </div>
          
          <div class="detail-row" v-if="componentCpes && componentCpes.length">
            <span class="detail-label">CPEs:</span>
            <div class="detail-value">
              <v-chip
                v-for="cpe in componentCpes"
                :key="cpe"
                size="small"
                class="mr-1 mb-1"
                color="secondary"
              >
                {{ cpe }}
              </v-chip>
            </div>
          </div>
        </div>
      </div>

      <v-divider class="mb-4"></v-divider>

      <div class="locations-section">
        <h4 class="mb-3">
          <v-icon class="mr-2">mdi-file-tree</v-icon>
          File Locations ({{ locations.length }})
        </h4>
        
        <v-expansion-panels>
          <v-expansion-panel
            v-for="(location, index) in locations"
            :key="index"
          >
            <v-expansion-panel-header>
              <div class="d-flex align-center">
                <v-icon
                  :color="getEvidenceColor(location.evidence_type)"
                  class="mr-2"
                >
                  {{ getEvidenceIcon(location.evidence_type) }}
                </v-icon>
                <span class="font-mono">{{ location.path }}</span>
                <v-spacer></v-spacer>
                <v-chip
                  size="small"
                  :color="getEvidenceColor(location.evidence_type)"
                >
                  {{ location.evidence_type }}
                </v-chip>
              </div>
            </v-expansion-panel-header>
            
            <v-expansion-panel-content>
              <div class="location-details">
                <div class="detail-row" v-if="location.layer_id">
                  <span class="detail-label">Layer ID:</span>
                  <span class="detail-value font-mono">{{ location.layer_id }}</span>
                </div>
                
                <div class="detail-row" v-if="location.access_path">
                  <span class="detail-label">Access Path:</span>
                  <span class="detail-value font-mono">{{ location.access_path }}</span>
                </div>
                
                <div class="detail-row" v-if="location.annotations && Object.keys(location.annotations).length">
                  <span class="detail-label">Annotations:</span>
                  <div class="detail-value">
                    <v-chip
                      v-for="(value, key) in location.annotations"
                      :key="key"
                      size="small"
                      class="mr-1 mb-1"
                      color="info"
                    >
                      {{ key }}: {{ value }}
                    </v-chip>
                  </div>
                </div>
              </div>
            </v-expansion-panel-content>
          </v-expansion-panel>
        </v-expansion-panels>
      </div>
    </v-card-text>
  </v-card>
</template>

<script>
export default {
  name: 'ComponentLocationCard',
  props: {
    component: {
      type: Object,
      required: true
    }
  },
  computed: {
    // Handle both old format (from image locations) and new format (from component locations)
    componentName() {
      return this.component.component_name || this.component.component_version?.version || 'Unknown'
    },
    componentVersion() {
      return this.component.component_version || this.component.component_version?.version || 'Unknown'
    },
    componentType() {
      return this.component.component_type || this.component.component?.type || 'unknown'
    },
    componentPurl() {
      return this.component.purl || this.component.component_version?.purl || null
    },
    componentCpes() {
      return this.component.cpes || this.component.component_version?.cpes || []
    },
    locations() {
      // If this is a single location object, wrap it in an array
      if (this.component.path) {
        return [this.component]
      }
      // If this is already an array of locations
      return this.component.locations || []
    }
  },
  methods: {
    getEvidenceColor(evidenceType) {
      switch (evidenceType) {
        case 'primary':
          return 'success'
        case 'supporting':
          return 'warning'
        default:
          return 'grey'
      }
    },
    getEvidenceIcon(evidenceType) {
      switch (evidenceType) {
        case 'primary':
          return 'mdi-check-circle'
        case 'supporting':
          return 'mdi-help-circle'
        default:
          return 'mdi-question-circle'
      }
    },
    getSeverityColor(severity) {
      switch (severity?.toUpperCase()) {
        case 'CRITICAL':
          return 'error'
        case 'HIGH':
          return 'warning'
        case 'MEDIUM':
          return 'orange'
        case 'LOW':
          return 'info'
        default:
          return 'grey'
      }
    }
  }
}
</script>

<style scoped>
.component-location-card {
  margin-bottom: 16px;
}

.component-info {
  background-color: #f5f5f5;
  padding: 16px;
  border-radius: 8px;
}

.component-details {
  margin-top: 12px;
}

.detail-row {
  display: flex;
  margin-bottom: 8px;
  align-items: flex-start;
}

.detail-label {
  font-weight: 600;
  min-width: 80px;
  margin-right: 12px;
  color: #666;
}

.detail-value {
  flex: 1;
  word-break: break-all;
}

.font-mono {
  font-family: 'Courier New', monospace;
  font-size: 0.9em;
  background-color: #f0f0f0;
  padding: 2px 6px;
  border-radius: 4px;
}

.locations-section h4 {
  color: #333;
  font-weight: 600;
}

.location-details {
  padding: 8px 0;
}
</style>
