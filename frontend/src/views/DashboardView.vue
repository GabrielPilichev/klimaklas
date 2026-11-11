<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import RoomTile from '../components/RoomTile.vue'
import { loadRooms, store } from '../store.js'

const now = ref(Date.now())
let timer
onMounted(() => {
  timer = setInterval(() => (now.value = Date.now()), 30000) // опреснява „преди X мин“
  loadRooms()
})
onUnmounted(() => clearInterval(timer))

const floors = computed(() => {
  void now.value
  const byFloor = new Map()
  for (const r of store.rooms) {
    if (!byFloor.has(r.floor)) byFloor.set(r.floor, [])
    byFloor.get(r.floor).push(r)
  }
  return [...byFloor.entries()].sort((a, b) => b[0] - a[0]) // горният етаж отгоре, като в сграда
})

const counts = computed(() => {
  const c = { green: 0, yellow: 0, red: 0, offline: 0 }
  store.rooms.forEach((r) => c[r.status]++)
  return c
})
</script>

<template>
  <div class="row head">
    <div>
      <h1>План на сградата</h1>
      <p class="muted">Въздухът във всяка стая на живо · обновява се автоматично</p>
    </div>
    <div class="spacer"></div>
    <div class="legend">
      <span class="pill st-green">под 800 ppm · {{ counts.green }}</span>
      <span class="pill st-yellow">800–1200 · {{ counts.yellow }}</span>
      <span class="pill st-red">над 1200 · {{ counts.red }}</span>
      <span v-if="counts.offline" class="pill st-offline">без данни · {{ counts.offline }}</span>
    </div>
  </div>

  <p v-if="!store.rooms.length" class="muted">Нямате стаи за наблюдение. Помолете администратора да ви добави.</p>

  <section v-for="[floor, rooms] in floors" :key="floor" class="floor">
    <div class="floor-label">{{ floor }} етаж</div>
    <div class="grid">
      <RoomTile v-for="room in rooms" :key="room.id" :room="room" />
    </div>
  </section>
</template>

<style scoped>
.head { margin-bottom: 16px; align-items: flex-end; }
.head p { margin: 0; }
.legend { display: flex; gap: 6px; flex-wrap: wrap; }
.floor { display: grid; grid-template-columns: 70px 1fr; gap: 12px; padding: 14px 0; border-top: 1px dashed var(--border); }
.floor-label { font-weight: 700; color: var(--muted); padding-top: 14px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }
@media (max-width: 600px) {
  .floor { grid-template-columns: 1fr; }
  .floor-label { padding-top: 0; }
  .grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
