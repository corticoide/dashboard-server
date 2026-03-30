import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

const routes = [
  { path: '/login',    component: () => import('../views/LoginView.vue'),    meta: { public: true,        title: 'Login'     } },
  { path: '/',         component: () => import('../views/DashboardView.vue'), meta: { requiresAuth: true,  title: 'Dashboard' } },
  { path: '/services', component: () => import('../views/ServicesView.vue'),  meta: { requiresAuth: true,  title: 'Services'  } },
  { path: '/files',    component: () => import('../views/FilesView.vue'),     meta: { requiresAuth: true,  title: 'Files'     } },
  { path: '/scripts',  component: () => import('../views/ScriptsView.vue'),   meta: { requiresAuth: true,  title: 'Scripts'   } },
  { path: '/crontab',  component: () => import('../views/CrontabView.vue'),   meta: { requiresAuth: true,  title: 'Crontab'   } },
  { path: '/logs',     component: () => import('../views/LogsView.vue'),      meta: { requiresAuth: true,  title: 'Logs'      } },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.isAuthenticated) return '/login'
  if (to.path === '/login' && auth.isAuthenticated) return '/'
})

export default router
