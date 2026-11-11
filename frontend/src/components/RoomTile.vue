<script setup>
import { STATUS_LABELS, timeAgo } from '../store.js'

defineProps({ room: { type: Object, required: true } })
</script>

<template>
  <RouterLink :to="`/rooms/${room.id}`" class="tile" :class="`st-${room.status}`">
    <div class="top">
      <span class="name">Стая {{ room.name }}</span>
      <span v-if="room.alert_active" class="bell" title="Активно известие">🔔</span>
    </div>
    <div class="value">
      <template v-if="room.latest">{{ room.latest.co2 }}<small> ppm</small></template>
      <template v-else>—</template>
    </div>
    <div class="label">{{ STATUS_LABELS[room.status] }}</div>
    <div v-if="room.latest" class="meta">
      <span v-if="room.latest.temperature != null">{{ room.latest.temperature.toFixed(1) }} °C</span>
      <span v-if="room.latest.humidity != null">{{ Math.round(room.latest.humidity) }} %</span>
      <span>{{ timeAgo(room.latest.measured_at) }}</span>
    </div>
  </RouterLink>
</template>

<style scoped>
.tile {
  display: block; padding: 14px; border-radius: var(--radius);
  background: var(--st-bg); border: 2px solid var(--st);
  color: var(--text); text-decoration: none;
  transition: transform 0.15s;
}
.tile:hover { transform: translateY(-2px); }
.top { display: flex; justify-content: space-between; font-weight: 600; }
.value { font-size: 2rem; font-weight: 700; color: var(--st); line-height: 1.2; margin-top: 6px; }
.value small { font-size: 0.9rem; font-weight: 500; }
.label { font-weight: 600; color: var(--st); font-size: 14px; }
.meta { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 6px; font-size: 13px; color: var(--muted); }
.st-red .bell { animation: ring 1s infinite; }
@keyframes ring { 50% { transform: rotate(15deg); } }
@media (prefers-reduced-motion: reduce) { .st-red .bell { animation: none; } }
</style>
