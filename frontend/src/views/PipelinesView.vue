<template>
  <div class="pipelines-view">
    <div class="empty-state">
      <i class="pi pi-gears empty-icon" />
      <span class="empty-text">Pipelines feature coming soon.</span>
    </div>
  </div>
</template>

<script setup>
// Placeholder for Pipeline system feature
</script>

<style scoped>
.pipelines-view {
  height: calc(100vh - var(--header-height) - 48px);
  display: flex;
  align-items: center;
  justify-content: center;
}
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 24px;
}
.empty-icon {
  font-size: 28px;
  opacity: 0.4;
  color: var(--p-text-muted-color);
}
.empty-text {
  font-size: var(--text-sm);
  font-family: var(--font-mono);
  color: var(--p-text-muted-color);
  text-align: center;
}
</style>
