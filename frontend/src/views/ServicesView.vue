<template>
  <div class="services-view">
    <!-- Toolbar -->
    <div class="toolbar">
      <div class="search-wrap">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <input v-model="filter" placeholder="Filter services…" class="search-input" />
      </div>
      <div class="state-filters">
        <button
          v-for="s in stateOptions" :key="s.value"
          class="filter-btn" :class="{ active: stateFilter === s.value }"
          @click="stateFilter = s.value"
        >{{ s.label }}</button>
      </div>
      <!-- Sudo credentials -->
      <div class="sudo-wrap" :class="{ unlocked: sudoPassword }">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
          <path v-if="!sudoPassword" d="M7 11V7a5 5 0 0 1 10 0v4"/>
          <path v-else d="M7 11V7a5 5 0 0 1 9.9-1"/>
        </svg>
        <input
          v-model="sudoPassword"
          type="password"
          placeholder="sudo password"
          class="sudo-input"
          autocomplete="off"
        />
        <button v-if="sudoPassword" class="sudo-clear" @click="sudoPassword = ''" title="Clear password">✕</button>
      </div>
      <button class="refresh-btn" @click="loadServices" :disabled="loading" title="Refresh">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
        </svg>
      </button>
    </div>

    <!-- Error -->
    <div v-if="error" class="error-banner">{{ error }}</div>

    <!-- Table -->
    <div class="table-wrap">
      <table class="service-table">
        <thead>
          <tr>
            <th>SERVICE</th>
            <th>STATE</th>
            <th>SUB</th>
            <th>ENABLED</th>
            <th class="desc-col">DESCRIPTION</th>
            <th>ACTIONS</th>
          </tr>
        </thead>
        <tbody>
          <template v-if="loading">
            <tr v-for="i in 8" :key="i" class="skeleton-row">
              <td colspan="6"><div class="skeleton"></div></td>
            </tr>
          </template>
          <template v-else-if="filtered.length === 0">
            <tr><td colspan="6" class="empty-cell">No services found</td></tr>
          </template>
          <template v-else>
            <tr
              v-for="svc in filtered" :key="svc.name"
              class="service-row"
              :class="{ selected: selectedService === svc.name }"
              @click="toggleLogs(svc.name)"
            >
              <td class="name-cell">{{ svc.name }}</td>
              <td><StatusBadge :state="svc.active_state" /></td>
              <td class="sub-cell">{{ svc.sub_state }}</td>
              <td class="sub-cell">{{ svc.enabled }}</td>
              <td class="desc-col text-muted">{{ svc.description }}</td>
              <td class="actions-cell" @click.stop>
                <button
                  v-for="act in actions" :key="act.action"
                  class="action-btn" :class="`btn-${act.color}`"
                  :disabled="actionLoading[svc.name]"
                  @click="runAction(svc.name, act.action)"
                  :title="act.label"
                >{{ act.label }}</button>
              </td>
            </tr>
            <!-- Inline log panel -->
            <tr v-if="selectedService && logsByService[selectedService]" class="log-row">
              <td colspan="6">
                <div class="log-panel">
                  <div class="log-header">
                    <span>{{ selectedService }} — journald logs</span>
                    <button class="close-log" @click.stop="selectedService = null">✕</button>
                  </div>
                  <pre class="log-content">{{ logsByService[selectedService].join('\n') }}</pre>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import StatusBadge from '../components/services/StatusBadge.vue'
import api from '../api/client.js'

const services = ref([])
const loading = ref(false)
const error = ref('')
const filter = ref('')
const stateFilter = ref('all')
const selectedService = ref(null)
const logsByService = ref({})
const actionLoading = ref({})
const sudoPassword = ref('')

const stateOptions = [
  { value: 'all', label: 'All' },
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
  { value: 'failed', label: 'Failed' },
]

const actions = [
  { action: 'start', label: 'Start', color: 'green' },
  { action: 'stop', label: 'Stop', color: 'yellow' },
  { action: 'restart', label: 'Restart', color: 'blue' },
]

async function loadServices() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get('/services/')
    services.value = data
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load services'
  } finally {
    loading.value = false
  }
}

async function toggleLogs(name) {
  if (selectedService.value === name) {
    selectedService.value = null
    return
  }
  selectedService.value = name
  if (!logsByService.value[name]) {
    try {
      const { data } = await api.get(`/services/${name}/logs?lines=80`)
      logsByService.value[name] = data.lines
    } catch {
      logsByService.value[name] = ['Failed to load logs']
    }
  }
}

async function runAction(name, action) {
  actionLoading.value[name] = true
  error.value = ''
  try {
    await api.post(`/services/${name}/${action}`, {
      sudo_password: sudoPassword.value || null,
    })
    const { data } = await api.get('/services/')
    services.value = data
    // Invalidate cached logs so next open fetches fresh
    delete logsByService.value[name]
    if (selectedService.value === name) {
      const logResp = await api.get(`/services/${name}/logs?lines=80`)
      logsByService.value[name] = logResp.data.lines
    }
  } catch (e) {
    error.value = e.response?.data?.detail || `Failed to ${action} ${name}`
    // Clear wrong password on auth failure
    if (e.response?.status === 500 && error.value.toLowerCase().includes('password')) {
      sudoPassword.value = ''
    }
  } finally {
    actionLoading.value[name] = false
  }
}

const filtered = computed(() => services.value.filter(s => {
  const matchesText = filter.value === '' ||
    s.name.toLowerCase().includes(filter.value.toLowerCase()) ||
    s.description.toLowerCase().includes(filter.value.toLowerCase())
  const matchesState = stateFilter.value === 'all' || s.active_state === stateFilter.value
  return matchesText && matchesState
}))

onMounted(loadServices)
</script>

<style scoped>
.services-view { display: flex; flex-direction: column; gap: 14px; }

.toolbar {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
}
.search-wrap {
  display: flex; align-items: center; gap: 8px;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 5px; padding: 6px 10px; flex: 1; min-width: 200px;
  color: var(--text-muted);
}
.search-input {
  background: none; border: none; outline: none;
  color: var(--text); font-family: var(--font-mono); font-size: 12px; width: 100%;
}
.search-input::placeholder { color: var(--text-dim); }
.state-filters { display: flex; gap: 4px; }
.filter-btn {
  background: var(--surface); border: 1px solid var(--border);
  color: var(--text-muted); padding: 5px 10px;
  border-radius: 4px; font-size: 11px; cursor: pointer;
  font-family: var(--font-mono); transition: all 0.15s;
}
.filter-btn:hover, .filter-btn.active {
  background: var(--surface-2); border-color: var(--accent-blue); color: var(--accent-blue);
}
.sudo-wrap {
  display: flex; align-items: center; gap: 6px;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 5px; padding: 5px 10px;
  color: var(--text-muted); transition: border-color 0.15s;
}
.sudo-wrap.unlocked {
  border-color: var(--accent-green);
  color: var(--accent-green);
}
.sudo-input {
  background: none; border: none; outline: none;
  color: var(--text); font-family: var(--font-mono); font-size: 12px;
  width: 120px;
}
.sudo-input::placeholder { color: var(--text-dim); }
.sudo-clear {
  background: none; border: none; color: var(--text-muted);
  cursor: pointer; font-size: 11px; padding: 0; line-height: 1;
}
.sudo-clear:hover { color: var(--accent-red); }

.refresh-btn {
  background: var(--surface); border: 1px solid var(--border);
  color: var(--text-muted); padding: 6px 8px; border-radius: 5px; cursor: pointer;
  display: flex; align-items: center; transition: all 0.15s;
}
.refresh-btn:hover { color: var(--text); border-color: var(--border-bright); }

.error-banner {
  background: rgba(239,68,68,0.1); border: 1px solid var(--accent-red);
  color: var(--accent-red); padding: 10px 14px; border-radius: 6px; font-size: 13px;
}

.table-wrap { overflow-x: auto; }
.service-table {
  width: 100%; border-collapse: collapse;
  background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
  overflow: hidden;
}
.service-table th {
  font-family: var(--font-mono); font-size: 9px; letter-spacing: 1.5px;
  color: var(--text-muted); text-align: left; padding: 10px 14px;
  border-bottom: 1px solid var(--border); background: var(--surface-2);
  font-weight: 600;
}
.service-row { cursor: pointer; transition: background 0.1s; }
.service-row:hover { background: var(--surface-2); }
.service-row.selected { background: var(--surface-2); }
.service-row td {
  padding: 9px 14px; border-bottom: 1px solid var(--border);
  font-size: 12px; vertical-align: middle;
}
.name-cell { font-family: var(--font-mono); font-size: 12px; color: var(--text-bright); }
.sub-cell { font-family: var(--font-mono); font-size: 11px; color: var(--text-muted); }
.desc-col { max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.text-muted { color: var(--text-muted); }
.empty-cell { text-align: center; padding: 40px; color: var(--text-muted); font-size: 13px; }

.actions-cell { white-space: nowrap; }
.action-btn {
  background: none; border: 1px solid var(--border); color: var(--text-muted);
  padding: 3px 8px; border-radius: 4px; font-size: 10px; cursor: pointer;
  font-family: var(--font-mono); margin-right: 4px; transition: all 0.15s;
}
.btn-green:hover { border-color: var(--accent-green); color: var(--accent-green); }
.btn-yellow:hover { border-color: var(--accent-yellow); color: var(--accent-yellow); }
.btn-blue:hover { border-color: var(--accent-blue); color: var(--accent-blue); }
.action-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.log-row td { padding: 0; border-bottom: 1px solid var(--border); }
.log-panel { background: var(--bg); }
.log-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 14px; border-bottom: 1px solid var(--border);
  font-family: var(--font-mono); font-size: 11px; color: var(--text-muted);
}
.close-log {
  background: none; border: none; color: var(--text-muted); cursor: pointer; font-size: 12px;
}
.close-log:hover { color: var(--text); }
.log-content {
  font-family: var(--font-mono); font-size: 11px; line-height: 1.7;
  color: var(--text-muted); padding: 12px 14px;
  max-height: 300px; overflow-y: auto;
  white-space: pre-wrap; word-break: break-all;
}

.skeleton-row td { padding: 10px 14px; border-bottom: 1px solid var(--border); }
.skeleton {
  height: 14px; background: var(--surface-2);
  border-radius: 4px; animation: shimmer 1.4s ease-in-out infinite;
}
@keyframes shimmer {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 0.8; }
}
</style>
