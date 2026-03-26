<template>
  <div class="tree-node">
    <div
      class="tree-item"
      :class="{ active: currentPath === node.path }"
      :style="{ paddingLeft: `${depth * 14 + 8}px` }"
      @click="handleClick"
    >
      <span class="tree-arrow" :class="{ expanded: isExpanded }">
        <i v-if="isLoading" class="pi pi-spin pi-spinner tree-arrow-icon" />
        <i v-else class="pi pi-chevron-right tree-arrow-icon" />
      </span>
      <i class="pi pi-folder folder-icon" />
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
  padding: 5px 8px; border-radius: 4px; cursor: pointer;
  font-family: var(--font-mono); font-size: var(--text-sm);
  color: var(--p-text-muted-color);
  transition: background 0.1s, color 0.1s;
  white-space: nowrap;
}
.tree-item:hover {
  background: var(--p-surface-hover);
  color: var(--p-text-color);
}
.tree-item.active {
  background: color-mix(in srgb, var(--brand-orange) 10%, transparent);
  color: var(--brand-orange);
  border-left: 2px solid var(--brand-orange);
}

.tree-arrow {
  width: 12px; flex-shrink: 0;
  color: var(--p-text-muted-color);
  transition: transform 0.15s;
  display: flex; align-items: center;
}
.tree-arrow.expanded { transform: rotate(90deg); }
.tree-arrow-icon { font-size: 10px; }

.folder-icon {
  flex-shrink: 0;
  color: var(--p-yellow-400);
  font-size: 13px;
}
.tree-item.active .folder-icon {
  color: var(--brand-orange);
}

.tree-name { overflow: hidden; text-overflow: ellipsis; }
</style>
