<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api.js'
import { fmtTime, loadActiveAlerts, toast } from '../store.js'

const alerts = ref([])
const error = ref('')

async function load() {
  try {
    alerts.value = await api('/alerts?limit=100')
  } catch (e) {
    error.value = e.message
  }
}

async function ack(a) {
  try {
    Object.assign(a, await api(`/alerts/${a.id}/ack`, { method: 'POST' }))
    toast(`Благодарим! Отбелязано за стая ${a.room_name}.`, 'success')
    loadActiveAlerts()
  } catch (e) {
    toast(e.message, 'danger')
  }
}

const minutes = (a) =>
  Math.round(((a.resolved_at ? new Date(a.resolved_at) : new Date()) - new Date(a.started_at)) / 60000)

onMounted(load)
</script>

<template>
  <h1>Известия</h1>
  <p class="muted">Известие се изпраща, когато CO₂ е над 1200 ppm повече от 5 минути.</p>
  <p v-if="error" class="error">{{ error }}</p>

  <div class="card table-wrap">
    <table>
      <thead>
        <tr><th>Стая</th><th>Начало</th><th>Продължителност</th><th>Макс. CO₂</th><th>Състояние</th><th></th></tr>
      </thead>
      <tbody>
        <tr v-for="a in alerts" :key="a.id">
          <td><RouterLink :to="`/rooms/${a.room_id}`">Стая {{ a.room_name }}</RouterLink></td>
          <td>{{ fmtTime(a.started_at) }}</td>
          <td>{{ minutes(a) }} мин</td>
          <td><strong>{{ a.max_co2 }}</strong> ppm</td>
          <td>
            <span v-if="a.active" class="pill st-red">активно</span>
            <span v-else class="pill st-green">проветрено</span>
          </td>
          <td>
            <button v-if="!a.acknowledged_at" class="btn small" @click="ack(a)">Отворих прозореца</button>
            <span v-else class="muted">✓ {{ fmtTime(a.acknowledged_at) }}</span>
          </td>
        </tr>
        <tr v-if="!alerts.length"><td colspan="6" class="muted">Няма известия. 🌿</td></tr>
      </tbody>
    </table>
  </div>
</template>
