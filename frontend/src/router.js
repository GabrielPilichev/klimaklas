import { createRouter, createWebHistory } from 'vue-router'
import { api, setUnauthorizedHandler } from './api.js'
import { store } from './store.js'
import { stopLive } from './live.js'

import LoginView from './views/LoginView.vue'
import DashboardView from './views/DashboardView.vue'
import RoomView from './views/RoomView.vue'
import AlertsView from './views/AlertsView.vue'
import ReportsView from './views/ReportsView.vue'
import AdminView from './views/AdminView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginView, meta: { public: true } },
    { path: '/', component: DashboardView },
    { path: '/rooms/:id', component: RoomView, props: (r) => ({ id: Number(r.params.id) }) },
    { path: '/alerts', component: AlertsView },
    { path: '/reports', component: ReportsView, meta: { roles: ['admin', 'director'] } },
    { path: '/admin', component: AdminView, meta: { roles: ['admin'] } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

let checked = false
router.beforeEach(async (to) => {
  if (!checked) {
    checked = true
    try {
      store.user = await api('/auth/me')
    } catch {
      store.user = null
    }
  }
  if (to.meta.public) return store.user && to.path === '/login' ? '/' : true
  if (!store.user) return { path: '/login', query: to.fullPath !== '/' ? { next: to.fullPath } : {} }
  if (to.meta.roles && !to.meta.roles.includes(store.user.role)) return '/'
  return true
})

setUnauthorizedHandler(() => {
  store.user = null
  stopLive()
  if (router.currentRoute.value.path !== '/login') router.push('/login')
})
