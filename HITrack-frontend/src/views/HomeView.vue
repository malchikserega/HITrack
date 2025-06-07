<template>
  <div class="home">
    <v-container>
      <v-row>
        <v-col cols="12">
          <h1 class="text-h4 mb-4 font-weight-black">Dashboard</h1>
        </v-col>
      </v-row>

      <v-row>
        <v-col cols="12" sm="6" md="3">
          <router-link to="/repositories" style="text-decoration: none;">
            <v-card class="dashboard-card" elevation="2" :color="'#f8f9fa'">
              <div class="d-flex flex-column align-center justify-center text-center" style="min-height:170px;">
                <div class="icon-number-row">
                  <v-icon class="dashboard-icon mr-2" color="#1976d2">mdi-source-repository</v-icon>
                  <div class="dashboard-number">{{ stats.repositories }}</div>
                </div>
                <div class="dashboard-label">Repositories</div>
              </div>
            </v-card>
          </router-link>
        </v-col>

        <v-col cols="12" sm="6" md="3">
          <router-link to="/images" style="text-decoration: none;">
            <v-card class="dashboard-card" elevation="2" :color="'#f8f9fa'">
              <div class="d-flex flex-column align-center justify-center text-center" style="min-height:170px;">
                <div class="icon-number-row">
                  <v-icon class="dashboard-icon mr-2" color="#0097a7">mdi-docker</v-icon>
                  <div class="dashboard-number">{{ stats.images }}</div>
                </div>
                <div class="dashboard-label">Images</div>
              </div>
            </v-card>
          </router-link>
        </v-col>

        <v-col cols="12" sm="6" md="3">
          <router-link to="/components" style="text-decoration: none;">
            <v-card class="dashboard-card" elevation="2" :color="'#f8f9fa'">
            <div class="d-flex flex-column align-center justify-center text-center" style="min-height:170px;">
              <div class="icon-number-row">
                <v-icon class="dashboard-icon mr-2" color="#8e24aa">mdi-cube</v-icon>
                <div class="dashboard-number">{{ stats.components }}</div>
              </div>
              <div class="dashboard-label">Components</div>
            </div>
          </v-card>
          </router-link>
        </v-col>

        <v-col cols="12" sm="6" md="3">
          <v-card class="dashboard-card" elevation="2" :color="'#f8f9fa'">
            <div class="d-flex flex-column align-center justify-center text-center" style="min-height:170px;">
              <div class="icon-number-row">
                <v-icon class="dashboard-icon mr-2" color="#d32f2f">mdi-bug</v-icon>
                <div class="dashboard-number">{{ stats.vulnerabilities }}</div>
              </div>
              <div class="dashboard-label">Vulnerabilities</div>
            </div>
          </v-card>
        </v-col>
      </v-row>
    </v-container>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '../plugins/axios'
import type { Stats } from '../types/interfaces'

const stats = ref<Stats>({
  repositories: 0,
  images: 0,
  vulnerabilities: 0,
  components: 0
})

const fetchStats = async () => {
  try {
    const response = await api.get('stats/')
    const data = response.data

    stats.value = {
      repositories: data.repositories,
      images: data.images,
      components: data.components,
      vulnerabilities: data.vulnerabilities
    }
  } catch (error) {
    console.error('Error fetching stats:', error)
  }
}

onMounted(() => {
  fetchStats()
})
</script>

<style scoped>
.home {
  padding: 20px;
}

.dashboard-card {
  transition: all 0.3s ease-in-out;
  border-radius: 16px;
  min-height: 170px !important;
  height: auto !important;
  background: linear-gradient(145deg, #ffffff, #f8f9fa);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
}

.dashboard-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
}

.d-flex.flex-column.align-center.justify-center.text-center {
  min-height: 140px !important;
  height: auto !important;
  padding: 18px 0 10px 0;
}

.icon-number-row {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 6px;
}

.v-icon {
  opacity: 0.95;
  font-size: 38px !important;
}

.dashboard-number {
  font-size: 3rem;
  font-weight: 700;
  color: #222;
  letter-spacing: 0.5px;
}

.dashboard-label {
  font-size: 1.8rem;
  font-weight: 700;
  color: #000000;
  margin-top: 10px;
  margin-bottom: 6px;
  letter-spacing: 0.5px;
  background: none;
  border: none;
  text-align: center;
  text-shadow: none;
  padding: 0;
  display: block;
}

.dashboard-icon {
  font-size: 54px !important;
  width: 54px !important;
  height: 54px !important;
  min-width: 54px !important;
  min-height: 54px !important;
  line-height: 54px !important;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
</style> 