<template>
  <div class="disks-view">
    <div class="page-header">
      <div class="page-title">
        <i class="pi pi-database page-icon" />
        <span>DISKS</span>
      </div>
    </div>

    <div class="wip-container">
      <div class="wip-card">
        <div class="wip-icon-ring">
          <i class="pi pi-wrench wip-icon" />
        </div>
        <span class="wip-title">IN PROGRESS</span>
        <span class="wip-desc">Disk management is under construction. Coming soon: partition browser, mount/unmount, SMART health, and storage usage.</span>
        <div class="wip-tags">
          <span class="wip-tag">udisks2</span>
          <span class="wip-tag">SMART</span>
          <span class="wip-tag">partitions</span>
          <span class="wip-tag">mount/umount</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
</script>

<style scoped>
.disks-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 14px;
  animation: sd-enter 0.25s ease-out;
}

.wip-container {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.wip-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 48px 40px;
  background: var(--p-surface-card);
  border: 1px solid var(--p-surface-border);
  border-left: 2px solid color-mix(in srgb, var(--brand-orange) 35%, transparent);
  border-radius: var(--radius-2xl);
  max-width: 480px;
  text-align: center;
  transition: border-left-color 0.2s, box-shadow 0.2s;
}
.wip-card:hover {
  border-left-color: var(--brand-orange);
  box-shadow: 0 0 0 1px var(--orange-tint-08), 0 8px 24px -8px rgba(0,0,0,0.35);
}

.wip-icon-ring {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--brand-orange) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand-orange) 25%, transparent);
  display: flex;
  align-items: center;
  justify-content: center;
}
.wip-icon {
  font-size: 26px;
  color: var(--brand-orange);
}

.wip-title {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  font-weight: 700;
  letter-spacing: 3px;
  color: var(--brand-orange);
}

.wip-desc {
  font-family: var(--font-ui);
  font-size: var(--text-sm);
  color: var(--p-text-muted-color);
  line-height: 1.6;
  max-width: 360px;
}

.wip-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: center;
  margin-top: 4px;
}
.wip-tag {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  letter-spacing: 1px;
  padding: 3px 10px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--p-surface-hover) 60%, transparent);
  border: 1px solid var(--p-surface-border);
  color: var(--p-text-muted-color);
}
</style>
