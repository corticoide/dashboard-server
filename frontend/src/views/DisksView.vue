<template>
  <div class="disks-view">

    <!-- Header -->
    <div class="page-header">
      <div class="page-title">
        <i class="pi pi-database page-icon" />
        <span>DISKS</span>
        <span class="page-sub">/ Management</span>
      </div>
      <div class="header-actions">
        <Button
          :icon="scanning ? 'pi pi-spinner pi-spin' : 'pi pi-refresh'"
          label="Scan"
          size="small"
          severity="secondary"
          :disabled="scanning"
          @click="runScan"
        />
        <Button icon="pi pi-plus" label="Mount Disk" size="small" @click="showMountHint" />
      </div>
    </div>

    <!-- Stat cards row -->
    <div class="disk-stats-row">
      <div class="disk-stat-card">
        <i class="pi pi-database disk-stat-icon" />
        <div class="disk-stat-body">
          <span class="disk-stat-label">TOTAL DISKS</span>
          <span class="disk-stat-value">{{ disks.length }}</span>
        </div>
      </div>
      <div class="disk-stat-card disk-stat-card--green">
        <i class="pi pi-check-circle disk-stat-icon disk-stat-icon--green" />
        <div class="disk-stat-body">
          <span class="disk-stat-label">MOUNTED</span>
          <span class="disk-stat-value disk-stat-val--green">{{ disks.filter(d => d.status === 'mounted').length }}</span>
        </div>
      </div>
      <div class="disk-stat-card disk-stat-card--orange">
        <i class="pi pi-server disk-stat-icon disk-stat-icon--orange" />
        <div class="disk-stat-body">
          <span class="disk-stat-label">TOTAL CAPACITY</span>
          <span class="disk-stat-value disk-stat-val--orange">{{ fmtBytes(disks.reduce((s, d) => s + d.size, 0)) }}</span>
        </div>
      </div>
      <div class="disk-stat-card disk-stat-card--blue">
        <i class="pi pi-heart disk-stat-icon disk-stat-icon--blue" />
        <div class="disk-stat-body">
          <span class="disk-stat-label">HEALTHY</span>
          <span class="disk-stat-value disk-stat-val--blue">{{ disks.filter(d => d.smart === 'PASSED' || d.smart === 'N/A').length }} / {{ disks.length }}</span>
        </div>
      </div>
    </div>

    <!-- Main split -->
    <Splitter class="main-splitter" :gutter-size="5">

      <!-- Left: disk list -->
      <SplitterPanel :size="36" :min-size="24" class="list-panel">
        <div class="list-header">
          <div class="search-box">
            <i class="pi pi-search search-icon" />
            <input
              v-model="searchQuery"
              class="search-input"
              placeholder="Filter disks…"
            />
          </div>
          <span class="count-badge">{{ filteredDisks.length }}</span>
        </div>

        <div v-if="loading" class="disk-table-body">
          <div v-for="i in 3" :key="i" class="disk-row-skeleton" />
        </div>

        <div v-else-if="filteredDisks.length === 0" class="empty-list">
          <i class="pi pi-database" style="font-size:28px;opacity:0.2;" />
          <span>No disks found</span>
        </div>

        <div v-else class="disk-table">
          <!-- Table header -->
          <div class="disk-table-head">
            <div class="col-icon" />
            <div class="col-name">Disk</div>
            <div class="col-size">Size</div>
            <div class="col-usage">Usage</div>
            <div class="col-badges" />
          </div>

          <!-- Table rows -->
          <div class="disk-table-body">
            <div
              v-for="disk in filteredDisks"
              :key="disk.id"
              class="disk-row"
              :class="{ active: selectedId === disk.id }"
              @click="selectDisk(disk.id)"
            >
              <!-- Icon -->
              <div class="col-icon">
                <div class="disk-icon">
                  <i :class="['pi', diskIcon(disk.type)]" />
                </div>
              </div>

              <!-- Name + dev -->
              <div class="col-name">
                <div class="dc-name-wrap">
                  <template v-if="editingId === disk.id">
                    <input
                      :ref="el => { if (el) editInputs[disk.id] = el }"
                      v-model="editName"
                      class="dc-name-input"
                      @keydown.enter="saveName(disk)"
                      @keydown.escape="cancelEdit"
                      @blur="saveName(disk)"
                      @click.stop
                    />
                  </template>
                  <template v-else>
                    <span class="dc-name">{{ disk.name }}</span>
                    <button class="btn-edit" @click.stop="startEdit($event, disk)">
                      <i class="pi pi-pencil" />
                    </button>
                  </template>
                </div>
                <div class="dc-dev">{{ disk.dev }}</div>
              </div>

              <!-- Size -->
              <div class="col-size">
                <span class="dc-size">{{ fmtBytes(disk.size) }}</span>
              </div>

              <!-- Usage bar -->
              <div class="col-usage">
                <div class="dc-usage-row">
                  <strong :style="{ color: usageColor(usedPct(disk)) }">{{ usedPct(disk) }}%</strong>
                  <span class="dc-usage-sub">{{ fmtBytes(disk.used) }}</span>
                </div>
                <div class="usage-bar">
                  <div
                    class="usage-bar-fill"
                    :style="{ width: usedPct(disk) + '%', background: usageColor(usedPct(disk)) }"
                  />
                </div>
              </div>

              <!-- Badges + star -->
              <div class="col-badges">
                <span :class="['type-badge', typeBadgeClass(disk.type)]">{{ disk.type }}</span>
                <button
                  :class="['btn-star', { starred: disk.favorite }]"
                  :title="disk.favorite ? 'Remove from favorites' : 'Mark as favorite'"
                  @click.stop="toggleFavorite(disk)"
                >{{ disk.favorite ? '★' : '☆' }}</button>
              </div>
            </div>
          </div>
        </div>
      </SplitterPanel>

      <!-- Right: detail -->
      <SplitterPanel :size="64" :min-size="40" class="detail-panel">

        <!-- Empty state -->
        <div v-if="!selectedDisk" class="detail-empty">
          <i class="pi pi-database" style="font-size:36px;opacity:0.18;" />
          <p>Select a disk to view details</p>
        </div>

        <!-- Detail content -->
        <div v-else class="detail-inner">

          <!-- Detail top -->
          <div class="detail-top">
            <div class="detail-disk-icon">
              <i :class="['pi', diskIcon(selectedDisk.type)]" style="font-size:24px;" />
            </div>
            <div class="detail-head">
              <div class="detail-name">
                <span>{{ selectedDisk.name }}</span>
                <span :class="['status-badge', selectedDisk.smart === 'FAILED' ? 'badge-red' : selectedDisk.status === 'mounted' ? 'badge-green' : 'badge-neutral']">
                  <span class="status-dot" />
                  {{ selectedDisk.smart === 'FAILED' ? 'S.M.A.R.T. FAILED' : selectedDisk.status === 'mounted' ? 'Mounted' : 'Unmounted' }}
                </span>
                <span v-if="selectedDisk.favorite" class="fav-badge">
                  <i class="pi pi-star-fill" style="font-size:9px;" /> Favorite — protected
                </span>
              </div>
              <div class="detail-dev">{{ selectedDisk.dev }} · {{ selectedDisk.model }} · {{ selectedDisk.interface }}</div>
              <div class="detail-actions">

                <!-- State group: mount / unmount -->
                <div class="action-group">
                  <span class="action-group-label">STATE</span>
                  <div class="action-group-buttons">
                    <Button
                      v-if="selectedDisk.status === 'mounted'"
                      :icon="isLocked(selectedDisk) ? 'pi pi-lock' : 'pi pi-eject'"
                      label="Unmount"
                      size="small"
                      severity="secondary"
                      :loading="actioning"
                      @click="toggleMount(selectedDisk)"
                    />
                    <Button
                      v-else
                      icon="pi pi-arrow-up"
                      label="Mount"
                      size="small"
                      :loading="actioning"
                      @click="toggleMount(selectedDisk)"
                    />
                  </div>
                </div>

                <!-- Tools group: open / rename -->
                <div class="action-group">
                  <span class="action-group-label">TOOLS</span>
                  <div class="action-group-buttons">
                    <Button
                      v-if="selectedDisk.mount"
                      icon="pi pi-folder-open"
                      label="Open in Files"
                      size="small"
                      severity="secondary"
                      @click="goToFiles(selectedDisk.mount)"
                    />
                    <Button
                      icon="pi pi-pencil"
                      label="Rename"
                      size="small"
                      severity="secondary"
                      @click="startEdit(null, selectedDisk)"
                    />
                  </div>
                </div>

                <!-- Danger group: format -->
                <div class="action-group action-group--danger">
                  <span class="action-group-label">DANGER</span>
                  <div class="action-group-buttons">
                    <Button
                      :icon="isLocked(selectedDisk) ? 'pi pi-lock' : 'pi pi-trash'"
                      label="Format"
                      size="small"
                      severity="danger"
                      :style="isLocked(selectedDisk) ? 'opacity:0.4;cursor:not-allowed;' : ''"
                      outlined
                      @click="confirmFormat(selectedDisk)"
                    />
                  </div>
                </div>

              </div>
            </div>

            <!-- Health ring -->
            <div v-if="selectedDisk.health !== null" class="health-ring">
              <svg viewBox="0 0 50 50">
                <circle cx="25" cy="25" r="22" fill="none" stroke="var(--p-surface-border)" stroke-width="4" />
                <circle
                  cx="25" cy="25" r="22" fill="none"
                  :stroke="healthColor(selectedDisk.health)"
                  stroke-width="4"
                  :stroke-dasharray="`${healthDash(selectedDisk.health)} ${healthGap(selectedDisk.health)}`"
                  stroke-linecap="round"
                  style="transform:rotate(-90deg);transform-origin:50% 50%;"
                />
              </svg>
              <div class="health-label">
                {{ selectedDisk.health }}<span>%</span>
              </div>
            </div>
          </div>

          <!-- Stat strip -->
          <div class="stat-strip">
            <div class="stat-cell">
              <div class="sc-label">CAPACITY</div>
              <div class="sc-value">{{ selectedDisk.size >= 1e12 ? (selectedDisk.size / 1e12).toFixed(1) : (selectedDisk.size / 1e9).toFixed(0) }}</div>
              <div class="sc-unit">{{ selectedDisk.size >= 1e12 ? 'TB' : 'GB' }} total</div>
            </div>
            <div class="stat-cell">
              <div class="sc-label">USAGE</div>
              <div class="sc-value" :style="{ color: usageColor(usedPct(selectedDisk)) }">{{ usedPct(selectedDisk) }}</div>
              <div class="sc-unit">% · {{ fmtBytes(selectedDisk.used) }} used</div>
              <div class="sc-bar">
                <div class="sc-bar-fill" :style="{ width: usedPct(selectedDisk) + '%', background: usageColor(usedPct(selectedDisk)) }" />
              </div>
            </div>
            <div class="stat-cell">
              <div class="sc-label">TEMPERATURE</div>
              <div class="sc-value" :style="{ color: tempColor(selectedDisk.temp) }">{{ selectedDisk.temp ?? '—' }}</div>
              <div class="sc-unit">{{ selectedDisk.temp !== null ? '°C · S.M.A.R.T.' : 'Not available' }}</div>
            </div>
            <div class="stat-cell">
              <div class="sc-label">HEALTH</div>
              <div class="sc-value" :style="{ color: healthColor(selectedDisk.health) }">{{ selectedDisk.health ?? '—' }}</div>
              <div class="sc-unit">{{ selectedDisk.health !== null ? `% · ${selectedDisk.smart}` : selectedDisk.smart }}</div>
            </div>
          </div>

          <!-- Scrollable body -->
          <div class="detail-body">

            <!-- Specs -->
            <div class="section">
              <div class="section-title">SPECIFICATIONS</div>
              <div class="specs-grid">
                <div class="spec-cell"><span class="spec-key">TYPE</span><span class="spec-val">{{ selectedDisk.type }}</span></div>
                <div class="spec-cell"><span class="spec-key">INTERFACE</span><span class="spec-val">{{ selectedDisk.interface }}</span></div>
                <div class="spec-cell"><span class="spec-key">FILESYSTEM</span><span class="spec-val">{{ selectedDisk.fs }}</span></div>
                <div class="spec-cell">
                  <span class="spec-key">MOUNT POINT</span>
                  <span
                    :class="['spec-val', { 'spec-link': selectedDisk.mount }]"
                    @click="goToFiles(selectedDisk.mount)"
                  >{{ selectedDisk.mount || '—' }}</span>
                </div>
                <div class="spec-cell"><span class="spec-key">MODEL</span><span class="spec-val">{{ selectedDisk.model }}</span></div>
                <div class="spec-cell"><span class="spec-key">SERIAL</span><span class="spec-val">{{ selectedDisk.serial }}</span></div>
                <div class="spec-cell"><span class="spec-key">UUID</span><span class="spec-val spec-uuid">{{ selectedDisk.uuid }}</span></div>
                <div class="spec-cell"><span class="spec-key">RPM</span><span class="spec-val">{{ selectedDisk.rpm ?? 'SSD / Flash' }}</span></div>
              </div>
            </div>

            <!-- I/O -->
            <div class="section">
              <div class="section-title">I/O SPEED</div>
              <div class="io-bars">
                <div class="io-row">
                  <span class="io-label">READ</span>
                  <div class="io-bar-wrap">
                    <div class="io-bar">
                      <div class="io-bar-fill" :style="{ width: (selectedDisk.read_pct * 100) + '%', background: 'var(--p-blue-400)' }" />
                    </div>
                  </div>
                  <span class="io-speed">{{ fmtMBs(selectedDisk.read) }}</span>
                </div>
                <div class="io-row">
                  <span class="io-label">WRITE</span>
                  <div class="io-bar-wrap">
                    <div class="io-bar">
                      <div class="io-bar-fill" :style="{ width: (selectedDisk.write_pct * 100) + '%', background: 'var(--brand-orange)' }" />
                    </div>
                  </div>
                  <span class="io-speed">{{ fmtMBs(selectedDisk.write) }}</span>
                </div>
              </div>
            </div>

            <!-- Partitions -->
            <div v-if="selectedDisk.partitions.length > 0" class="section">
              <div class="section-title">PARTITIONS · {{ selectedDisk.partitions.length }}</div>
              <div class="table-wrap">
                <table class="part-table">
                  <thead>
                    <tr>
                      <th>Partition</th>
                      <th>Size</th>
                      <th>FS</th>
                      <th>Mount</th>
                      <th>Type</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="p in selectedDisk.partitions" :key="p.name">
                      <td class="muted">{{ p.name }}</td>
                      <td>{{ p.size }}</td>
                      <td>{{ p.fs }}</td>
                      <td
                        :class="['mount-cell', { 'link-cell': p.mount && p.mount !== '—' }]"
                        @click="goToFiles(p.mount)"
                      >{{ p.mount }}</td>
                      <td class="muted">{{ p.type }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

          </div>
        </div>
      </SplitterPanel>
    </Splitter>

    <!-- Custom warning toast -->
    <Transition name="toast-slide">
      <div v-if="toast.show" class="warn-toast">
        {{ toast.msg }}
      </div>
    </Transition>

    <!-- Format confirm dialog -->
    <Dialog v-model:visible="formatDialog.show" modal :header="`Format ${formatDialog.disk?.name}`" :style="{ width: '420px' }">
      <p class="dialog-msg">
        This will permanently erase all data on <strong>{{ formatDialog.disk?.dev }}</strong>.
        This action cannot be undone.
      </p>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="formatDialog.show = false" />
        <Button label="Format" severity="danger" icon="pi pi-trash" @click="doFormat" />
      </template>
    </Dialog>

  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import Splitter from 'primevue/splitter'
import SplitterPanel from 'primevue/splitterpanel'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import api from '../api/client.js'

const router = useRouter()

// ── State ───────────────────────────────────────────────────────────────────
const disks        = ref([])
const selectedId   = ref(null)
const searchQuery  = ref('')
const loading      = ref(true)
const scanning     = ref(false)
const actioning    = ref(false)
const editingId    = ref(null)
const editName     = ref('')
const editInputs   = ref({})
const toast        = ref({ show: false, msg: '', timer: null })
const formatDialog = ref({ show: false, disk: null })

// ── Computed ─────────────────────────────────────────────────────────────────
const filteredDisks = computed(() => {
  const q = searchQuery.value.toLowerCase().trim()
  if (!q) return disks.value
  return disks.value.filter(d =>
    d.name.toLowerCase().includes(q) ||
    d.dev.toLowerCase().includes(q) ||
    d.model.toLowerCase().includes(q)
  )
})

const selectedDisk = computed(() =>
  selectedId.value ? disks.value.find(d => d.id === selectedId.value) ?? null : null
)

// ── Helpers ──────────────────────────────────────────────────────────────────
function usedPct(disk) {
  if (!disk.size) return 0
  return Math.round((disk.used / disk.size) * 100)
}

function usageColor(pct) {
  if (pct >= 90) return 'var(--p-red-500)'
  if (pct >= 70) return 'var(--p-yellow-500)'
  return 'var(--p-green-500)'
}

function healthColor(h) {
  if (h === null || h === undefined) return 'var(--p-text-muted-color)'
  if (h >= 80) return 'var(--p-green-500)'
  if (h >= 50) return 'var(--p-yellow-500)'
  return 'var(--p-red-500)'
}

function tempColor(t) {
  if (t === null || t === undefined) return 'var(--p-text-color)'
  if (t > 55) return 'var(--p-red-500)'
  if (t > 45) return 'var(--p-yellow-500)'
  return 'var(--p-text-color)'
}

function diskIcon(type) {
  if (type === 'NVMe') return 'pi-microchip'
  if (type === 'USB')  return 'pi-usb'
  return 'pi-database'
}

function typeBadgeClass(type) {
  return { NVMe: 'badge-blue', SSD: 'badge-orange' }[type] ?? 'badge-neutral'
}

function fmtBytes(b) {
  if (!b) return '0 GB'
  if (b >= 1e12) return `${(b / 1e12).toFixed(1)} TB`
  if (b >= 1e9)  return `${(b / 1e9).toFixed(0)} GB`
  if (b >= 1e6)  return `${(b / 1e6).toFixed(0)} MB`
  return `${b} B`
}

function fmtMBs(mb) {
  if (!mb) return '0 MB/s'
  if (mb >= 1000) return `${(mb / 1000).toFixed(1)} GB/s`
  return `${mb.toFixed(0)} MB/s`
}

const CIRC = 2 * Math.PI * 22
function healthDash(h) { return CIRC * ((h ?? 0) / 100) }
function healthGap(h)  { return CIRC * (1 - (h ?? 0) / 100) }

function isLocked(disk) {
  return disk.favorite && disk.status === 'mounted'
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function showWarnToast(msg) {
  clearTimeout(toast.value.timer)
  toast.value.show = true
  toast.value.msg  = msg
  toast.value.timer = setTimeout(() => { toast.value.show = false }, 2800)
}

// ── Data loading ──────────────────────────────────────────────────────────────
async function loadDisks() {
  try {
    const { data } = await api.get('/disks')
    disks.value = data
    // keep selection valid
    if (selectedId.value && !data.find(d => d.id === selectedId.value)) {
      selectedId.value = null
    }
  } catch { /* silent */ }
}

async function runScan() {
  scanning.value = true
  try {
    const { data } = await api.post('/disks/scan')
    disks.value = data
  } catch { /* silent */ } finally {
    setTimeout(() => { scanning.value = false }, 1800)
  }
}

// ── Selection ─────────────────────────────────────────────────────────────────
function selectDisk(id) {
  if (editingId.value) return
  selectedId.value = id
}

// ── Inline name editing ───────────────────────────────────────────────────────
async function startEdit(e, disk) {
  if (e) e.stopPropagation()
  editingId.value = disk.id
  editName.value  = disk.name
  selectedId.value = disk.id
  await nextTick()
  editInputs.value[disk.id]?.focus()
  editInputs.value[disk.id]?.select()
}

async function saveName(disk) {
  const name = editName.value.trim()
  if (name && name !== disk.name) {
    disk.name = name
    try { await api.patch(`/disks/${disk.id}/name`, { name }) } catch { /* silent */ }
  }
  editingId.value = null
}

function cancelEdit() {
  editingId.value = null
}

// ── Favorite ──────────────────────────────────────────────────────────────────
async function toggleFavorite(disk) {
  disk.favorite = !disk.favorite
  try { await api.patch(`/disks/${disk.id}/favorite`, { favorite: disk.favorite }) } catch {
    disk.favorite = !disk.favorite
  }
}

// ── Mount / Unmount ───────────────────────────────────────────────────────────
async function toggleMount(disk) {
  if (isLocked(disk)) {
    showWarnToast('⭐ Favorite disk is protected — remove the star to unmount')
    return
  }
  actioning.value = true
  try {
    const endpoint = disk.status === 'mounted' ? 'unmount' : 'mount'
    await api.post(`/disks/${disk.id}/${endpoint}`)
    await loadDisks()
  } catch (err) {
    showWarnToast(err.response?.data?.detail ?? 'Action failed')
  } finally {
    actioning.value = false
  }
}

// ── Format ────────────────────────────────────────────────────────────────────
function confirmFormat(disk) {
  if (isLocked(disk)) {
    showWarnToast('⭐ Favorite disk is protected — remove the star to format')
    return
  }
  formatDialog.value = { show: true, disk }
}

async function doFormat() {
  formatDialog.value.show = false
  showWarnToast('Format is not yet implemented on the server side.')
}

// ── Navigate to Files ─────────────────────────────────────────────────────────
function goToFiles(path) {
  if (!path || path === '—') return
  router.push({ path: '/files', query: { dir: path } })
}

function showMountHint() {
  showWarnToast('Use udisksctl to mount an external device, then click Scan.')
}

// ── Init ──────────────────────────────────────────────────────────────────────
onMounted(async () => {
  await loadDisks()
  loading.value = false
})
</script>

<style scoped>
/* ── Root ───────────────────────────────────────────────────────────────────── */
.disks-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 10px;
  animation: sd-enter 0.25s ease-out;
}

.page-sub {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--p-text-muted-color);
  font-weight: 400;
  margin-left: 4px;
}

/* ── Splitter ───────────────────────────────────────────────────────────────── */
.main-splitter {
  flex: 1;
  overflow: hidden;
  border: 1px solid var(--p-surface-border);
  border-radius: var(--radius-2xl);
}

:deep(.p-splitter-gutter) {
  background: var(--p-surface-border) !important;
}

/* ── List panel ─────────────────────────────────────────────────────────────── */
.list-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--p-surface-card);
}

.list-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--p-surface-border);
  flex-shrink: 0;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--p-surface-hover);
  border: 1px solid var(--p-surface-border);
  border-radius: 7px;
  padding: 5px 10px;
  flex: 1;
}
.search-icon { color: var(--p-text-muted-color); font-size: 11px; }
.search-input {
  background: transparent;
  border: none;
  outline: none;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--p-text-color);
  width: 100%;
}
.search-input::placeholder { color: var(--p-text-muted-color); }

.count-badge {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  font-weight: 600;
  padding: 2px 8px;
  border-radius: var(--radius-xs);
  background: var(--p-surface-ground);
  border: 1px solid var(--p-surface-border);
  color: var(--p-text-muted-color);
  flex-shrink: 0;
}

.disk-items {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.empty-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--p-text-muted-color);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
}

/* Skeleton */
.disk-row-skeleton {
  height: 56px;
  background: var(--p-surface-hover);
  border-bottom: 1px solid var(--p-surface-border);
  animation: shimmer 1.4s ease-in-out infinite;
}
.disk-row-skeleton:last-child { border-bottom: none; }
@keyframes shimmer {
  0%, 100% { opacity: 0.5; }
  50%       { opacity: 1; }
}

/* ── Disk table ─────────────────────────────────────────────────────────────── */
.disk-table {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.disk-table-head {
  display: grid;
  grid-template-columns: 50px 1fr 72px 120px 84px;
  align-items: center;
  padding: 0 8px;
  height: 32px;
  border-bottom: 1px solid var(--p-surface-border);
  background: var(--p-surface-900);
  flex-shrink: 0;
}
.disk-table-head > div {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  font-weight: 600;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--p-text-muted-color);
  padding: 0 6px;
}

.disk-table-body {
  flex: 1;
  overflow-y: auto;
}

.disk-row {
  display: grid;
  grid-template-columns: 50px 1fr 72px 120px 84px;
  align-items: center;
  padding: 0 8px;
  min-height: 58px;
  border-bottom: 1px solid var(--p-surface-border);
  cursor: pointer;
  transition: background 0.12s;
  border-left: 2px solid transparent;
}
.disk-row:last-child { border-bottom: none; }
.disk-row:hover { background: var(--p-surface-hover); }
.disk-row.active {
  background: var(--orange-tint-08);
  border-left-color: var(--brand-orange);
}

.col-icon { display: flex; align-items: center; justify-content: center; padding: 0 4px; }
.col-name { display: flex; flex-direction: column; gap: 2px; padding: 0 6px; min-width: 0; }
.col-size { padding: 0 6px; }
.col-usage { padding: 0 6px; display: flex; flex-direction: column; gap: 4px; }
.col-badges { display: flex; align-items: center; justify-content: flex-end; gap: 5px; padding: 0 4px; }

.disk-icon {
  width: 34px; height: 34px;
  border-radius: 8px;
  background: var(--p-surface-hover);
  border: 1px solid var(--p-surface-border);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.disk-icon .pi { font-size: 15px; color: var(--p-text-muted-color); }
.disk-row.active .disk-icon {
  background: var(--orange-tint-12);
  border-color: var(--orange-tint-30);
}
.disk-row.active .disk-icon .pi { color: var(--brand-orange); }

.dc-name-wrap {
  display: flex;
  align-items: center;
  gap: 5px;
}

.dc-name {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--p-text-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dc-name-input {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--p-text-color);
  background: var(--p-surface-ground);
  border: 1px solid var(--brand-orange);
  border-radius: var(--radius-xs);
  padding: 2px 6px;
  outline: none;
  width: 130px;
}

.btn-edit {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--p-text-muted-color);
  font-size: 10px;
  padding: 0;
  opacity: 0;
  transition: opacity 0.15s, color 0.15s;
  flex-shrink: 0;
}
.disk-row:hover .btn-edit,
.disk-row.active .btn-edit { opacity: 1; }
.btn-edit:hover { color: var(--brand-orange); }

.dc-dev {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  color: var(--p-text-muted-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dc-size {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--p-text-muted-color);
  white-space: nowrap;
}

/* Star button */
.btn-star {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 14px;
  padding: 0 1px;
  color: var(--p-text-muted-color);
  opacity: 0;
  transition: opacity 0.15s, color 0.15s;
  line-height: 1;
}
.disk-row:hover .btn-star { opacity: 1; }
.btn-star.starred { opacity: 1; color: #eab308; }
.btn-star.starred:hover { color: #ca8a04; }
.btn-star:not(.starred):hover { color: var(--p-text-color); opacity: 1; }

/* Usage bar */
.dc-usage-row {
  display: flex;
  align-items: baseline;
  gap: 5px;
}
.dc-usage-row strong {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 600;
}
.dc-usage-sub {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  color: var(--p-text-muted-color);
}

.usage-bar {
  height: 4px;
  border-radius: 2px;
  background: var(--p-surface-border);
  overflow: hidden;
}
.usage-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.4s ease;
}

/* ── Detail panel ───────────────────────────────────────────────────────────── */
.detail-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--p-surface-ground);
}

.detail-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--p-text-muted-color);
}
.detail-empty p {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  opacity: 0.5;
}

.detail-inner {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Detail top */
.detail-top {
  padding: 20px 22px;
  border-bottom: 1px solid var(--p-surface-border);
  display: flex;
  align-items: flex-start;
  gap: 16px;
  flex-shrink: 0;
}

.detail-disk-icon {
  width: 56px; height: 56px;
  border-radius: 12px;
  background: var(--orange-tint-12);
  border: 1px solid var(--orange-tint-30);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  color: var(--brand-orange);
}

.detail-head { flex: 1; min-width: 0; }

.detail-name {
  font-family: var(--font-mono);
  font-size: var(--text-xl);
  font-weight: 700;
  color: var(--p-text-color);
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.detail-dev {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--p-text-muted-color);
  margin-bottom: 10px;
}

.detail-actions {
  display: flex;
  align-items: flex-end;
  gap: 0;
  flex-wrap: wrap;
  margin-top: 10px;
  background: var(--p-surface-ground);
  border: 1px solid var(--p-surface-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.action-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 12px;
  border-right: 1px solid var(--p-surface-border);
}
.action-group:last-child { border-right: none; }
.action-group--danger { margin-left: auto; }

.action-group-label {
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 1.5px;
  color: var(--p-text-muted-color);
  opacity: 0.6;
}
.action-group--danger .action-group-label { color: #f87171; opacity: 0.7; }

.action-group-buttons {
  display: flex;
  gap: 5px;
}

/* Badges */
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  font-weight: 600;
  border-radius: var(--radius-xs);
  padding: 2px 8px;
  line-height: 1.7;
}
.badge-green {
  background: color-mix(in srgb, #22c55e 12%, transparent);
  border: 1px solid color-mix(in srgb, #22c55e 30%, transparent);
  color: #4ade80;
}
.badge-red {
  background: color-mix(in srgb, #ef4444 12%, transparent);
  border: 1px solid color-mix(in srgb, #ef4444 30%, transparent);
  color: #f87171;
}
.badge-neutral {
  background: var(--p-surface-ground);
  border: 1px solid var(--p-surface-border);
  color: var(--p-text-muted-color);
}
.badge-blue {
  background: color-mix(in srgb, #3b82f6 12%, transparent);
  border: 1px solid color-mix(in srgb, #3b82f6 30%, transparent);
  color: #93c5fd;
}
.badge-orange {
  background: var(--orange-tint-12);
  border: 1px solid var(--orange-tint-25);
  color: var(--brand-orange);
}

.status-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: currentColor;
  display: inline-block;
}

.fav-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  font-weight: 600;
  background: color-mix(in srgb, #eab308 12%, transparent);
  border: 1px solid color-mix(in srgb, #eab308 30%, transparent);
  color: #fde047;
  border-radius: var(--radius-xs);
  padding: 2px 8px;
  line-height: 1.7;
}

.type-badge {
  display: inline-flex;
  align-items: center;
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  font-weight: 600;
  border-radius: var(--radius-xs);
  padding: 1px 7px;
  line-height: 1.7;
  flex-shrink: 0;
}

/* Health ring */
.health-ring {
  position: relative;
  width: 64px; height: 64px;
  flex-shrink: 0;
}
.health-ring svg { width: 100%; height: 100%; }
.health-label {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 700;
  color: var(--p-text-color);
}
.health-label span { font-size: 9px; color: var(--p-text-muted-color); }

/* Stat strip */
.stat-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  border-bottom: 1px solid var(--p-surface-border);
  flex-shrink: 0;
}
.stat-cell {
  padding: 14px 16px;
  border-right: 1px solid var(--p-surface-border);
}
.stat-cell:last-child { border-right: none; }

.sc-label {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 2px;
  color: var(--p-text-muted-color);
  margin-bottom: 5px;
}
.sc-value {
  font-family: var(--font-mono);
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--p-text-color);
  line-height: 1;
}
.sc-unit {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  color: var(--p-text-muted-color);
  margin-top: 3px;
}
.sc-bar {
  height: 3px;
  border-radius: 2px;
  background: var(--p-surface-border);
  margin-top: 8px;
  overflow: hidden;
}
.sc-bar-fill { height: 100%; border-radius: 2px; }

/* Detail body */
.detail-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section {
  background: var(--p-surface-card);
  border: 1px solid var(--p-surface-border);
  border-radius: var(--radius-xl);
  overflow: hidden;
}
.section-title {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 2px;
  color: var(--p-text-muted-color);
  padding: 8px 14px;
  background: var(--p-surface-900);
  border-bottom: 1px solid var(--p-surface-border);
}

/* Specs grid */
.specs-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1px;
  background: var(--p-surface-border);
  overflow: hidden;
  margin: 0;
}
.spec-cell {
  background: var(--p-surface-card);
  padding: 11px 14px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.spec-key {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  color: var(--p-text-muted-color);
  letter-spacing: 1px;
}
.spec-val {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--p-text-color);
  word-break: break-all;
}
.spec-uuid { font-size: 10px; }
.spec-link {
  color: var(--brand-orange);
  cursor: pointer;
  text-decoration: underline;
  text-decoration-style: dotted;
  text-underline-offset: 3px;
}
.spec-link:hover { color: var(--brand-orange-hover); }

/* I/O bars */
.io-bars { display: flex; flex-direction: column; gap: 10px; padding: 14px; }
.io-row { display: flex; align-items: center; gap: 12px; }
.io-label {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  color: var(--p-text-muted-color);
  width: 38px;
  flex-shrink: 0;
}
.io-bar-wrap { flex: 1; }
.io-bar {
  height: 6px;
  border-radius: 3px;
  background: var(--p-surface-border);
  overflow: hidden;
}
.io-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.6s ease;
}
.io-speed {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--p-text-color);
  width: 76px;
  text-align: right;
  flex-shrink: 0;
}

/* Partitions table */
.table-wrap {
  overflow: hidden;
  margin: 0;
}
.part-table {
  width: 100%;
  border-collapse: collapse;
}
.part-table th {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  text-transform: uppercase;
  letter-spacing: 1.5px;
  color: var(--p-text-muted-color);
  text-align: left;
  padding: 7px 14px;
  border-bottom: 1px solid var(--p-surface-border);
  font-weight: 600;
}
.part-table td {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--p-text-color);
  padding: 7px 14px;
  border-bottom: 1px solid var(--p-surface-border);
  vertical-align: middle;
}
.part-table tr:last-child td { border-bottom: none; }
.part-table tr:hover td { background: var(--p-surface-hover); }
.part-table td.muted { color: var(--p-text-muted-color); }
.link-cell {
  color: var(--brand-orange) !important;
  cursor: pointer;
}
.link-cell:hover { text-decoration: underline; }

/* ── Custom warning toast ───────────────────────────────────────────────────── */
.warn-toast {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  background: color-mix(in srgb, #eab308 14%, var(--p-surface-card));
  border: 1px solid color-mix(in srgb, #eab308 40%, transparent);
  border-radius: var(--radius-base);
  padding: 10px 20px;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--p-text-color);
  z-index: 500;
  white-space: nowrap;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.4);
  pointer-events: none;
}

.toast-slide-enter-active,
.toast-slide-leave-active { transition: opacity 0.2s, transform 0.2s; }
.toast-slide-enter-from   { opacity: 0; transform: translateX(-50%) translateY(12px); }
.toast-slide-leave-to     { opacity: 0; transform: translateX(-50%) translateY(8px); }

/* ── Dialog ─────────────────────────────────────────────────────────────────── */
.dialog-msg {
  font-family: var(--font-ui);
  font-size: var(--text-sm);
  color: var(--p-text-muted-color);
  line-height: 1.6;
}
.dialog-msg strong { color: var(--p-text-color); }

/* ── Disk stats row ─────────────────────────────────────────────── */
.disk-stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  flex-shrink: 0;
}
.disk-stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  background: var(--p-surface-card);
  border: 1px solid var(--p-surface-border);
  border-left: 3px solid var(--p-surface-border);
  border-radius: 10px;
}
.disk-stat-card--green  { border-left-color: var(--p-green-500); }
.disk-stat-card--orange { border-left-color: var(--brand-orange); }
.disk-stat-card--blue   { border-left-color: var(--p-blue-400); }
.disk-stat-icon { font-size: 18px; opacity: 0.45; color: var(--p-text-muted-color); flex-shrink: 0; }
.disk-stat-icon--green  { color: var(--p-green-500); opacity: 1; }
.disk-stat-icon--orange { color: var(--brand-orange); opacity: 1; }
.disk-stat-icon--blue   { color: var(--p-blue-400); opacity: 1; }
.disk-stat-body { display: flex; flex-direction: column; gap: 2px; }
.disk-stat-label {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 1.5px;
  color: var(--p-text-muted-color);
}
.disk-stat-value {
  font-family: var(--font-mono);
  font-size: var(--text-xl);
  font-weight: 700;
  color: var(--p-text-color);
  line-height: 1;
}
.disk-stat-val--green  { color: var(--p-green-500); }
.disk-stat-val--orange { color: var(--brand-orange); }
.disk-stat-val--blue   { color: var(--p-blue-400); }
</style>
