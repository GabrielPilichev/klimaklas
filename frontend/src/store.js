import { reactive } from 'vue'
import { api } from './api.js'

export const store = reactive({
  user: null,
  rooms: [],
  activeAlerts: [],
  toasts: [],
  liveConnected: false,
  theme: document.documentElement.dataset.theme || null,
})

export const ROLE_LABELS = { admin: 'Администратор', director: 'Директор', teacher: 'Учител' }
export const STATUS_LABELS = {
  green: 'Чист въздух',
  yellow: 'Проветрете скоро',
  red: 'Проветрете сега',
  offline: 'Няма данни',
}

export async function loadRooms() {
  store.rooms = await api('/rooms')
}

export async function loadActiveAlerts() {
  store.activeAlerts = await api('/alerts?active=true')
}

export function toast(text, kind = 'info', ms = 6000) {
  const id = Math.random().toString(36).slice(2)
  store.toasts.push({ id, text, kind })
  setTimeout(() => {
    store.toasts = store.toasts.filter((t) => t.id !== id)
  }, ms)
}

export function setTheme(theme) {
  store.theme = theme
  if (theme) document.documentElement.dataset.theme = theme
  else delete document.documentElement.dataset.theme
  try {
    if (theme) localStorage.setItem('kk-theme', theme)
    else localStorage.removeItem('kk-theme')
  } catch {
    /* частен режим – темата просто не се помни */
  }
}

export function timeAgo(iso) {
  if (!iso) return '—'
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return 'току-що'
  if (s < 3600) return `преди ${Math.round(s / 60)} мин`
  if (s < 86400) return `преди ${Math.round(s / 3600)} ч`
  return new Date(iso).toLocaleString('bg-BG')
}

export function fmtTime(iso) {
  return new Date(iso).toLocaleString('bg-BG', { dateStyle: 'short', timeStyle: 'short' })
}
