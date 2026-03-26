<template>
  <Toast />
  <ConfirmDialog />
  <template v-if="isAuthRoute">
    <RouterView />
  </template>
  <template v-else>
    <AppSidebar :collapsed="sidebarCollapsed" @toggle="sidebarCollapsed = !sidebarCollapsed" />
    <div :class="['main-content', { 'sidebar-collapsed': sidebarCollapsed }]">
      <AppHeader :page-title="pageTitle" :sidebar-collapsed="sidebarCollapsed" />
      <div class="page-body">
        <RouterView />
      </div>
    </div>
  </template>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import Toast from 'primevue/toast'
import ConfirmDialog from 'primevue/confirmdialog'
import AppSidebar from './components/layout/AppSidebar.vue'
import AppHeader from './components/layout/AppHeader.vue'

const route = useRoute()
const sidebarCollapsed = ref(false)
const isAuthRoute = computed(() => route.meta.public)
const pageTitle = computed(() => route.meta.title || 'Dashboard')

onMounted(() => {
  const saved = localStorage.getItem('theme') || 'dark'
  document.documentElement.setAttribute('data-theme', saved)
})
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
