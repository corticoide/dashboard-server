<template>
  <div class="tree-node">
    <div
      class="tree-item"
      :class="{ active: currentPath === node.path, loading: isLoading }"
      :style="{ paddingLeft: `${depth * 14 + 8}px` }"
      @click="handleClick"
    >
      <span class="tree-arrow" :class="{ expanded: isExpanded }">
        <svg v-if="!isLoading" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="9 18 15 12 9 6"/>
        </svg>
        <svg v-else width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin">
          <circle cx="12" cy="12" r="10" stroke-dasharray="20 60"/>
        </svg>
      </span>
      <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" class="folder-icon">
        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
      </svg>
      <span class="tree-name">{{ node.name || node.path }}</span>
    </div>
    <div v-if="isExpanded && children.length > 0" class="tree-children">
      <DirTree
        v-for="child in children"
        :key="child.path"
        :node="child"
        :current-path="currentPath"
        :depth="depth + 1"
        @navigate="$emit('navigate', $event)"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import api from '../../api/client.js'

const props = defineProps({
  node: { type: Object, required: true },
  currentPath: String,
  depth: { type: Number, default: 0 },
})
const emit = defineEmits(['navigate'])

const isExpanded = ref(false)
const isLoading = ref(false)
const children = ref([])

async function loadChildren() {
  if (children.value.length > 0) return
  isLoading.value = true
  try {
    const { data } = await api.get('/files/list', { params: { path: props.node.path } })
    children.value = data.entries
      .filter(e => e.is_dir)
      .map(e => ({ name: e.name, path: e.path }))
  } catch {
    children.value = []
  } finally {
    isLoading.value = false
  }
}

async function handleClick() {
  emit('navigate', props.node.path)
  if (!isExpanded.value) {
    await loadChildren()
    isExpanded.value = true
  } else {
    isExpanded.value = false
  }
}

if (props.depth === 0) {
  loadChildren().then(() => { isExpanded.value = true })
}

watch(() => props.currentPath, (newPath) => {
  if (newPath && newPath.startsWith(props.node.path + '/') && !isExpanded.value) {
    loadChildren().then(() => { isExpanded.value = true })
  }
})
</script>

<style scoped>
.tree-node { user-select: none; }
.tree-item {
  display: flex; align-items: center; gap: 5px;
  padding: 4px 8px; border-radius: 4px; cursor: pointer;
  font-family: var(--font-mono); font-size: 12px; color: var(--text-muted);
  transition: background 0.1s, color 0.1s; white-space: nowrap;
}
.tree-item:hover { background: var(--surface-2); color: var(--text); }
.tree-item.active { background: var(--surface-3); color: var(--accent-blue); }
.tree-arrow { width: 12px; flex-shrink: 0; color: var(--text-dim); transition: transform 0.15s; }
.tree-arrow.expanded { transform: rotate(90deg); }
.folder-icon { flex-shrink: 0; color: var(--accent-yellow); opacity: 0.8; }
.tree-item.active .folder-icon { color: var(--accent-blue); opacity: 1; }
.tree-name { overflow: hidden; text-overflow: ellipsis; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
