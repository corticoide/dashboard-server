<template>
  <template v-if="isAuthRoute">
    <RouterView />
  </template>
  <template v-else>
    <AppSidebar :collapsed="sidebarCollapsed" @toggle="sidebarCollapsed = !sidebarCollapsed" />
    <div :class="['main-content', { 'sidebar-collapsed': sidebarCollapsed }]">
      <AppHeader :page-title="pageTitle" />
      <div class="page-body">
        <RouterView />
      </div>
    </div>
  </template>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import AppSidebar from './components/layout/AppSidebar.vue'
import AppHeader from './components/layout/AppHeader.vue'

const route = useRoute()
const sidebarCollapsed = ref(false)
const isAuthRoute = computed(() => route.meta.public)
const pageTitle = computed(() => route.meta.title || 'Dashboard')
</script>

<style>
.main-content {
  margin-left: var(--sidebar-width);
  padding-top: var(--header-height);
  min-height: 100vh;
  transition: margin-left 0.2s ease;
}
.main-content.sidebar-collapsed {
  margin-left: var(--sidebar-collapsed-width);
}
.page-body { padding: 24px; }
</style>
