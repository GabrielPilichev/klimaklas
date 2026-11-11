<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import LineChart from '../components/LineChart.vue'
import { api, csvUrl } from '../api.js'
import { onLive } from '../live.js'
import { STATUS_LABELS, store, timeAgo } from '../store.js'

const props = defineProps({ id: { type: Number, required: true } })

const RANGES = [
  { hours: 3, label: '3 ч' },
  { hours: 24, label: '24 ч' },
  { hours: 24 * 7, label: '7 дни' },
]
const hours = ref(24)
const points = ref([])
const error = ref('')
const loading = ref(false)

const room = computed(() => store.rooms.find((r) => r.id === props.id))

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await api(`/rooms/${props.id}/readings?hours=${hours.value}&max_points=1200`)
    points.value = data.points
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

const fmt = (iso) => {
  const d = new Date(iso)
  return hours.value > 24
    ? d.toLocaleString('bg-BG', { weekday: 'short', hour: '2-digit', minute: '2-digit' })
    : d.toLocaleTimeString('bg-BG', { hour: '2-digit', minute: '2-digit' })
}
const labels = computed(() => points.value.map((p) => fmt(p.measured_at)))
const co2Sets = computed(() => [
  { label: 'CO₂ (ppm)', data: points.value.map((p) => p.co2), colorVar: '--accent', fill: true },
])
const climateSets = computed(() => [
  { label: 'Температура (°C)', data: points.value.map((p) => p.temperature), colorVar: '--red' },
  { label: 'Влажност (%)', data: points.value.map((p) => p.humidity), colorVar: '--accent', yAxisID: 'y2' },
])
const thresholds = [
  { value: 800, colorVar: '--yellow', label: '800 ppm' },
  { value: 1200, colorVar: '--red', label: '1200 ppm – проветрете' },
]

const stats = computed(() => {
  const v = points.value.map((p) => p.co2)
  if (!v.length) return null
  return {
    avg: Math.round(v.reduce((a, b) => a + b, 0) / v.length),
    max: Math.max(...v),
    over: Math.round((100 * v.filter((x) => x > 1200).length) / v.length),
  }
})

// Новите стойности от WebSocket се добавят директно в графиката.
const off = onLive((msg) => {
  if (msg.type === 'reading' && msg.room_id === props.id && hours.value <= 24) {
    points.value = [...points.value, msg.reading]
  }
})

onMounted(load)
onUnmounted(off)
watch([hours, () => props.id], load)
</script>

<template>
  <RouterLink to="/" class="back">← Към сградата</RouterLink>

  <div v-if="room" class="hero card" :class="`st-${room.status}`">
    <div>
      <h1>Стая {{ room.name }}</h1>
      <span class="pill">{{ STATUS_LABELS[room.status] }}</span>
      <span v-if="room.alert_active" class="pill st-red">🔔 активно известие</span>
    </div>
    <div class="now">
      <div class="big">{{ room.latest?.co2 ?? '—' }}<small> ppm CO₂</small></div>
      <div class="muted" v-if="room.latest">
        {{ room.latest.temperature?.toFixed(1) ?? '—' }} °C ·
        {{ room.latest.humidity != null ? Math.round(room.latest.humidity) : '—' }} % влажност ·
        {{ timeAgo(room.latest.measured_at) }}
      </div>
    </div>
  </div>

  <div class="row controls">
    <div class="seg" role="group" aria-label="Период">
      <button v-for="r in RANGES" :key="r.hours" class="btn small" :class="{ ghost: hours !== r.hours }" @click="hours = r.hours">
        {{ r.label }}
      </button>
    </div>
    <div class="spacer"></div>
    <a class="btn ghost small" :href="csvUrl(`/rooms/${id}/export.csv?hours=${Math.max(hours, 24)}`)" download>
      ⬇ Експорт CSV
    </a>
  </div>

  <p v-if="error" class="error">{{ error }}</p>

  <div class="card">
    <div class="row">
      <h2 style="margin: 0">Въглероден диоксид</h2>
      <div class="spacer"></div>
      <span v-if="stats" class="muted">средно {{ stats.avg }} · макс. {{ stats.max }} · {{ stats.over }}% от времето над 1200</span>
    </div>
    <p v-if="!loading && !points.length" class="muted">Няма измервания за този период.</p>
    <LineChart v-else :labels="labels" :datasets="co2Sets" :thresholds="thresholds" unit="ppm" :height="320" />
  </div>

  <div class="card" style="margin-top: 16px">
    <h2 style="margin-top: 0">Температура и влажност</h2>
    <LineChart :labels="labels" :datasets="climateSets" unit="°C" y2-unit="%" :height="220" />
  </div>
</template>

<style scoped>
.back { display: inline-block; margin-bottom: 12px; text-decoration: none; }
.hero { display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap; border-left: 6px solid var(--st); }
.hero h1 { margin-bottom: 6px; }
.hero .pill { margin-right: 6px; }
.big { font-size: 2.6rem; font-weight: 800; color: var(--st); line-height: 1; }
.big small { font-size: 1rem; font-weight: 500; }
.now { text-align: right; }
.controls { margin: 16px 0; }
.seg { display: flex; gap: 4px; }
@media (max-width: 600px) { .now { text-align: left; } }
</style>
