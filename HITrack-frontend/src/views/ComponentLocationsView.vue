<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <v-card>
          <v-card-title class="d-flex align-center">
            <v-icon class="mr-2">mdi-map-marker</v-icon>
            Component Locations
            <v-spacer></v-spacer>
            <v-btn
              color="primary"
              @click="loadComponentLocations"
              :loading="loading"
              :disabled="!imageUuid"
            >
              <v-icon class="mr-2">mdi-refresh</v-icon>
              Refresh
            </v-btn>
          </v-card-title>

          <v-card-text>
            <div v-if="!imageUuid" class="text-center pa-8">
              <v-icon size="64" color="grey">mdi-image-off</v-icon>
              <h3 class="mt-4">No Image Selected</h3>
              <p class="text-grey">Please select an image to view component locations.</p>
            </div>

            <div v-else-if="loading" class="text-center pa-8">
              <v-progress-circular
                indeterminate
                color="primary"
                size="64"
              ></v-progress-circular>
              <p class="mt-4">Loading component locations...</p>
            </div>

            <div v-else-if="error" class="text-center pa-8">
              <v-icon size="64" color="error">mdi-alert-circle</v-icon>
              <h3 class="mt-4 text-error">Error Loading Data</h3>
              <p class="text-grey">{{ error }}</p>
              <v-btn
                color="primary"
                @click="loadComponentLocations"
                class="mt-4"
              >
                Try Again
              </v-btn>
            </div>

            <div v-else-if="componentLocations.length === 0" class="text-center pa-8">
              <v-icon size="64" color="grey">mdi-package-variant-closed</v-icon>
              <h3 class="mt-4">No Component Locations Found</h3>
              <p class="text-grey">
                No component location information is available for this image.
                This might be because:
              </p>
              <ul class="text-left mt-4">
                <li>The image hasn't been scanned with Grype yet</li>
                <li>The scan didn't find any components with location information</li>
                <li>The scan results don't include location data</li>
              </ul>
              <v-btn
                color="primary"
                @click="rescanImage"
                class="mt-4"
                :loading="rescanning"
              >
                <v-icon class="mr-2">mdi-refresh</v-icon>
                Rescan Image
              </v-btn>
            </div>

            <div v-else>
              <div class="mb-4">
                <v-alert
                  type="info"
                  variant="tonal"
                  class="mb-4"
                >
                  <template v-slot:prepend>
                    <v-icon>mdi-information</v-icon>
                  </template>
                  <div>
                    <strong>Image:</strong> {{ imageName }}
                  </div>
                  <div>
                    <strong>Components Found:</strong> {{ componentLocations.length }}
                  </div>
                  <div>
                    <strong>Total Locations:</strong> {{ totalLocations }}
                  </div>
                </v-alert>
              </div>

              <div class="component-locations">
                <ComponentLocationCard
                  v-for="component in componentLocations"
                  :key="`${component.component_name}-${component.component_version}`"
                  :component="component"
                />
              </div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Rescan Dialog -->
    <v-dialog v-model="showRescanDialog" max-width="500">
      <v-card>
        <v-card-title>Rescan Image</v-card-title>
        <v-card-text>
          <p>This will trigger a new Grype scan of the image to update component location information.</p>
          <p class="text-grey">The scan may take several minutes to complete.</p>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn @click="showRescanDialog = false">Cancel</v-btn>
          <v-btn
            color="primary"
            @click="confirmRescan"
            :loading="rescanning"
          >
            Start Scan
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/plugins/axios'
import ComponentLocationCard from '@/components/ComponentLocationCard.vue'

export default {
  name: 'ComponentLocationsView',
  components: {
    ComponentLocationCard
  },
  setup() {
    const route = useRoute()
    const loading = ref(false)
    const rescanning = ref(false)
    const error = ref(null)
    const componentLocations = ref([])
    const imageName = ref('')
    const showRescanDialog = ref(false)

    const imageUuid = computed(() => route.params.uuid)

    const totalLocations = computed(() => {
      return componentLocations.value.reduce((total, component) => {
        return total + component.locations.length
      }, 0)
    })

    const loadComponentLocations = async () => {
      if (!imageUuid.value) return

      loading.value = true
      error.value = null

      try {
        const response = await api.get(`/images/${imageUuid.value}/component-locations/`)
        componentLocations.value = response.data.component_locations
        imageName.value = response.data.image_name
      } catch (err) {
        console.error('Error loading component locations:', err)
        error.value = err.response?.data?.error || 'Failed to load component locations'
      } finally {
        loading.value = false
      }
    }

    const rescanImage = () => {
      showRescanDialog.value = true
    }

    const confirmRescan = async () => {
      rescanning.value = true
      showRescanDialog.value = false

      try {
        await api.post(`/images/${imageUuid.value}/rescan-grype/`)
        
        // Show success message
        this.$notify({
          type: 'success',
          title: 'Scan Started',
          text: 'Grype scan has been started. Component locations will be updated when the scan completes.'
        })

        // Wait a bit and then reload
        setTimeout(() => {
          loadComponentLocations()
        }, 2000)

      } catch (err) {
        console.error('Error starting rescan:', err)
        this.$notify({
          type: 'error',
          title: 'Scan Failed',
          text: err.response?.data?.error || 'Failed to start Grype scan'
        })
      } finally {
        rescanning.value = false
      }
    }

    onMounted(() => {
      if (imageUuid.value) {
        loadComponentLocations()
      }
    })

    return {
      loading,
      rescanning,
      error,
      componentLocations,
      imageName,
      showRescanDialog,
      imageUuid,
      totalLocations,
      loadComponentLocations,
      rescanImage,
      confirmRescan
    }
  }
}
</script>

<style scoped>
.component-locations {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
  background: #ffffff;
  min-height: 100vh;
}

</style>
