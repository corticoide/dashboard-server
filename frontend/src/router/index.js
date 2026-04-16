import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

const routes = [
  { path: '/login',    component: () => import('../views/LoginView.vue'),    meta: { public: true,        title: 'Login'     } },
  { path: '/',         component: () => import('../views/DashboardView.vue'), meta: { requiresAuth: true,  title: 'Dashboard', resource: 'system' } },
  { path: '/services', component: () => import('../views/ServicesView.vue'),  meta: { requiresAuth: true,  title: 'Services',  resource: 'services' } },
  { path: '/files',    component: () => import('../views/FilesView.vue'),     meta: { requiresAuth: true,  title: 'Files',     resource: 'files' } },
  { path: '/scripts',  component: () => import('../views/ScriptsView.vue'),   meta: { requiresAuth: true,  title: 'Scripts',   resource: 'scripts' } },
  { path: '/crontab',  component: () => import('../views/CrontabView.vue'),   meta: { requiresAuth: true,  title: 'Crontab',   resource: 'crontab' } },
  { path: '/logs',     component: () => import('../views/LogsView.vue'),      meta: { requiresAuth: true,  title: 'Logs',      resource: 'logs' } },
  { path: '/network',  component: () => import('../views/NetworkView.vue'),  meta: { requiresAuth: true, title: 'Network', resource: 'network' } },
  { path: '/history', component: () => import('../views/HistoryView.vue'),  meta: { requiresAuth: true, title: 'History', resource: 'system'  } },
  { path: '/admin/users', component: () => import('../views/AdminUsersView.vue'), meta: { requiresAuth: true, title: 'Users', adminOnly: true } },
  { path: '/pipelines', component: () => import('../views/PipelinesView.vue'), meta: { requiresAuth: true, title: 'Pipelines', resource: 'pipelines' } },
  { path: '/admin/permissions', component: () => import('../views/AdminPermissionsView.vue'), meta: { requiresAuth: true, title: 'Permissions', adminOnly: true } },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.isAuthenticated) return '/login'
  if (to.path === '/login' && auth.isAuthenticated) return '/'
  if (to.meta.adminOnly && !auth.isAdmin) return '/'
  if (to.meta.resource && !auth.hasPermission(to.meta.resource, 'read')) return '/'
})

export default router
