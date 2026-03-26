<template>
  <Tag :value="state" :severity="severityMap[state] || 'secondary'" />
</template>

<script setup>
import Tag from 'primevue/tag'
defineProps({ state: String })
const severityMap = {
  active:       'success',
  failed:       'danger',
  activating:   'warn',
  inactive:     'secondary',
  deactivating: 'contrast',
}
</script>
