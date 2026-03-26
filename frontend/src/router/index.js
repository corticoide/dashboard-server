import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import ServicesView from '../views/ServicesView.vue'
import FilesView from '../views/FilesView.vue'
import ScriptsView from '../views/ScriptsView.vue'
import CrontabView from '../views/CrontabView.vue'

const routes = [
  { path: '/login', component: () => import('../views/LoginView.vue'), meta: { public: true, title: 'Login' } },
  { path: '/', component: () => import('../views/DashboardView.vue'), meta: { requiresAuth: true, title: 'Dashboard' } },
  { path: '/services', component: ServicesView, meta: { requiresAuth: true, title: 'Services' } },
  { path: '/files', component: FilesView, meta: { title: 'Files', requiresAuth: true } },
  { path: '/scripts', component: ScriptsView, meta: { title: 'Scripts', requiresAuth: true } },
  { path: '/crontab', component: CrontabView, meta: { title: 'Crontab', requiresAuth: true } },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.isAuthenticated) return '/login'
  if (to.path === '/login' && auth.isAuthenticated) return '/'
})

export default router
