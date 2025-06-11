<template>
  <div class="vulnerabilities">
    <v-container>
      <v-row>
        <v-col cols="12">
          <h1 class="text-h4 mb-4 font-weight-black">Vulnerabilities</h1>
          <v-btn color="primary" @click="openDialog('New Vulnerability')" class="mb-4">
            Add Vulnerability
          </v-btn>
        </v-col>
      </v-row>

      <v-row>
        <v-col cols="12">
          <v-data-table
            :headers="headers"
            :items="vulnerabilities"
            :loading="loading"
            class="elevation-1"
          >
            <template v-slot:item.created_at="{ item }">
              {{ $formatDate(item.created_at) }}
            </template>
            <template v-slot:item.updated_at="{ item }">
              {{ $formatDate(item.updated_at) }}
            </template>
            <template v-slot:item.actions="{ item }">
              <v-tooltip text="Edit vulnerability">
                <template v-slot:activator="{ props }">
                  <v-btn
                    v-bind="props"
                    icon="mdi-pencil"
                    variant="tonal"
                    size="x-small"
                    color="secondary"
                    @click="onEdit(item)"
                  />
                </template>
              </v-tooltip>
              <v-tooltip text="Delete vulnerability">
                <template v-slot:activator="{ props }">
                  <v-btn
                    v-bind="props"
                    icon="mdi-delete"
                    variant="tonal"
                    size="x-small"
                    color="red"
                    @click="onDelete(item)"
                  />
                </template>
              </v-tooltip>
            </template>
          </v-data-table>
        </v-col>
      </v-row>

      <v-dialog v-model="dialog" max-width="500px">
        <v-card :title="formTitle">
          <v-card-text>
            <v-row>
              <v-col cols="12">
                <v-text-field
                  v-model="editedItem.vulnerability_id"
                  label="CVE"
                  variant="outlined"
                  :rules="[rules.required]"
                ></v-text-field>
              </v-col>
              <v-col cols="12">
                <v-text-field
                  v-model="editedItem.description"
                  label="Description"
                  variant="outlined"
                  :rules="[rules.required]"
                ></v-text-field>
              </v-col>
              <v-col cols="12">
                <v-select
                  v-model="editedItem.severity"
                  :items="severityLevels"
                  label="Severity"
                  variant="outlined"
                  :rules="[rules.required]"
                ></v-select>
              </v-col>
            </v-row>
          </v-card-text>

          <v-card-actions>
            <v-spacer></v-spacer>
            <v-btn color="red-darken-1" variant="text" @click="closeDialog">
              Cancel
            </v-btn>
            <v-btn variant="text" @click="save" :loading="saving">
              Save
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>

      <v-dialog v-model="dialogDelete" max-width="500px">
        <v-card title="Delete Vulnerability">
          <v-card-text>Are you sure you want to delete <b>{{ itemToDelete?.vulnerability_id }}</b> vulnerability?</v-card-text>
          <v-card-actions>
            <v-spacer></v-spacer>
            <v-btn color="red-darken-1" variant="text" @click="closeDelete">Cancel</v-btn>
            <v-btn variant="text" @click="deleteItem" :loading="deleting">Delete</v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>
    </v-container>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import api from '../plugins/axios'
import { notificationService } from '../plugins/notifications'
import type { Vulnerability, PaginatedResponse } from '../types/interfaces'

const defaultItem = {
  id: undefined,
  uuid: '',
  vulnerability_id: '',
  vulnerability_type: '',
  severity: '',
  description: '',
  epss: 0,
  fixable: false,
  fix: '',
  created_at: '',
  updated_at: ''
}
const editedItem = ref<Vulnerability>({...defaultItem})
const vulnerabilities = ref<Vulnerability[]>([])
const loading = ref(false)
const saving = ref(false)
const deleting = ref(false)
const dialog = ref(false)
const dialogDelete = ref(false)
const itemToDelete = ref<Vulnerability | null>(null)
const formTitle = ref('New Vulnerability')
const severityLevels = [
  'LOW',
  'MEDIUM',
  'HIGH',
  'CRITICAL'
]

const headers: any[] = [
  { title: 'CVE', key: 'vulnerability_id', width: '150px' },
  { title: 'Description', key: 'description' },
  { title: 'Severity', key: 'severity' },
  { title: 'Created', key: 'created_at' },
  { title: 'Updated', key: 'updated_at' },
  { title: 'Actions', key: 'actions', sortable: false }
]

const rules = {
  required: (v: string) => !!v || 'This field is required'
}

const fetchVulnerabilities = async () => {
  loading.value = true
  try {
    const response = await api.get<PaginatedResponse<Vulnerability>>('vulnerabilities/')
    vulnerabilities.value = response.data.results
  } catch (error) {
    console.error('Error fetching vulnerabilities:', error)
    notificationService.error('Failed to fetch vulnerabilities')
  } finally {
    loading.value = false
  }
}

const openDialog = (title: string, item?: Vulnerability) => {
  formTitle.value = title
  if (item) {
    editedItem.value = {
      id: item.id,
      uuid: item.uuid,
      vulnerability_id: item.vulnerability_id,
      vulnerability_type: item.vulnerability_type,
      description: item.description,
      severity: item.severity,
      epss: item.epss,
      fixable: item.fixable ?? false,
      fix: item.fix ?? '',
      created_at: item.created_at,
      updated_at: item.updated_at
    }
  } else {
    editedItem.value = Object.assign({}, defaultItem)
  }
  dialog.value = true
}

const closeDialog = () => {
  dialog.value = false
  editedItem.value = Object.assign({}, defaultItem)
}

const save = async () => {
  saving.value = true
  try {
    const data = {
      vulnerability_id: editedItem.value.vulnerability_id,
      description: editedItem.value.description,
      severity: editedItem.value.severity
    }
    
    if (editedItem.value.uuid) {
      await api.put(`vulnerabilities/${editedItem.value.uuid}/`, data)
      notificationService.success('Vulnerability updated successfully')
    } else {
      await api.post('vulnerabilities/', data)
      notificationService.success('Vulnerability created successfully')
    }
    await fetchVulnerabilities()
    closeDialog()
  } catch (error) {
    console.error('Error saving vulnerability:', error)
    notificationService.error('Failed to save vulnerability')
  } finally {
    saving.value = false
  }
}

const confirmDelete = (item: Vulnerability) => {
  if (!item.uuid) {
    notificationService.error('Cannot delete vulnerability: missing UUID')
    return
  }
  itemToDelete.value = item
  dialogDelete.value = true
}

const deleteItem = async () => {
  if (!itemToDelete.value?.uuid) {
    notificationService.error('Cannot delete vulnerability: missing UUID')
    return
  }
  
  deleting.value = true
  try {
    await api.delete(`vulnerabilities/${itemToDelete.value.uuid}/`)
    await fetchVulnerabilities()
    notificationService.success('Vulnerability deleted successfully')
  } catch (error) {
    console.error('Error deleting vulnerability:', error)
    notificationService.error('Failed to delete vulnerability')
  } finally {
    deleting.value = false
    closeDelete()
  }
}

const closeDelete = () => {
  dialogDelete.value = false
  itemToDelete.value = null
}

const onEdit = (vuln: Vulnerability) => {
  openDialog('Edit Vulnerability', vuln);
};
const onDelete = (vuln: Vulnerability) => {
  console.log('Delete click:', vuln);
  confirmDelete(vuln);
};

onMounted(() => {
  fetchVulnerabilities()
})
</script>

<style scoped>
.vulnerabilities {
  padding: 20px;
}

:deep(.v-table) {
  background: transparent;
}

:deep(.v-table .v-table__wrapper > table) {
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 8px;
}

:deep(.v-table .v-table__wrapper > table > thead > tr > th) {
  font-weight: 700 !important;
  font-size: 0.875rem;
  color: rgba(0, 0, 0, 0.87);
  background-color: #f8f9fa;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 12px 16px;
  border-bottom: 2px solid #e0e0e0;
  transition: all 0.3s ease;
}

:deep(.v-table .v-table__wrapper > table > thead > tr > th:hover) {
  background-color: #e3f2fd;
  color: rgba(0, 0, 0, 0.87);
}

:deep(.v-table .v-table__wrapper > table > tbody > tr > td) {
  padding: 12px 16px;
  border-bottom: 1px solid #e0e0e0;
}

:deep(.v-table .v-table__wrapper > table > tbody > tr:hover) {
  background-color: #f5f5f5;
}
</style> 