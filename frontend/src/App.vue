<script setup>
import { computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from './api.js'
import { startLive, stopLive } from './live.js'
import { ROLE_LABELS, loadActiveAlerts, loadRooms, setTheme, store } from './store.js'

const router = useRouter()

const links = computed(() => {
  const role = store.user?.role
  const l = [
    { to: '/', label: 'Сграда' },
    { to: '/alerts', label: 'Известия' },
  ]
  if (role === 'admin' || role === 'director') l.push({ to: '/reports', label: 'Отчети' })
  if (role === 'admin') l.push({ to: '/admin', label: 'Администрация' })
  return l
})

const isDark = computed(() => {
  if (store.theme) return store.theme === 'dark'
  return window.matchMedia('(prefers-color-scheme: dark)').matches
})

function toggleTheme() {
  setTheme(isDark.value ? 'light' : 'dark')
}

async function logout() {
  try {
    await api('/auth/logout', { method: 'POST' })
  } finally {
    store.user = null
    stopLive()
    router.push('/login')
  }
}

watch(
  () => store.user?.id,
  async (id) => {
    if (!id) return
    await Promise.all([loadRooms(), loadActiveAlerts()])
    startLive()
    if ('Notification' in window && Notification.permission === 'default') Notification.requestPermission()
  },
  { immediate: true },
)
</script>

<template>
  <header v-if="store.user" class="topbar">
    <RouterLink to="/" class="brand">
      <img src="/favicon.svg" alt="" width="28" height="28" />
      <span>КлимаКлас</span>
    </RouterLink>
    <nav class="nav">
      <RouterLink v-for="l in links" :key="l.to" :to="l.to" class="nav-link">
        {{ l.label }}
        <span v-if="l.to === '/alerts' && store.activeAlerts.length" class="badge">
          {{ store.activeAlerts.length }}
        </span>
      </RouterLink>
    </nav>
    <div class="user">
      <span class="live-dot" :class="{ on: store.liveConnected }" :title="store.liveConnected ? 'На живо' : 'Няма връзка'"></span>
      <span class="who">
        {{ store.user.full_name }}<small>{{ ROLE_LABELS[store.user.role] }}</small>
      </span>
      <button class="icon-btn" :aria-label="isDark ? 'Светла тема' : 'Тъмна тема'" @click="toggleTheme">
        {{ isDark ? '☀️' : '🌙' }}
      </button>
      <button class="btn ghost small" @click="logout">Изход</button>
    </div>
  </header>

  <main class="container">
    <RouterView />
  </main>

  <div class="toasts" aria-live="polite">
    <div v-for="t in store.toasts" :key="t.id" class="toast" :class="t.kind">{{ t.text }}</div>
  </div>
</template>
