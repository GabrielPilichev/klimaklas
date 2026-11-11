<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api, csvUrl } from '../api.js'
import { store } from '../store.js'

function mondayOf(d) {
  const x = new Date(d)
  x.setDate(x.getDate() - ((x.getDay() + 6) % 7))
  return x.toLocaleDateString('sv-SE') // YYYY-MM-DD в местно време
}

const schools = ref([])
const schoolId = ref(null)
const week = ref(mondayOf(new Date()))
const report = ref(null)
const error = ref('')

async function load() {
  error.value = ''
  try {
    const q = new URLSearchParams({ week_start: mondayOf(week.value) })
    if (schoolId.value) q.set('school_id', schoolId.value)
    report.value = await api(`/reports/weekly?${q}`)
  } catch (e) {
    error.value = e.message
  }
}

function shiftWeek(days) {
  const d = new Date(week.value)
  d.setDate(d.getDate() + days)
  week.value = mondayOf(d)
}

const csv = computed(() => {
  const q = new URLSearchParams({ week_start: mondayOf(week.value), format: 'csv' })
  if (schoolId.value) q.set('school_id', schoolId.value)
  return csvUrl(`/reports/weekly?${q}`)
})

const statusOf = (r) => (r.avg_co2 == null ? 'offline' : r.percent_over_alert > 10 ? 'red' : r.percent_over_alert > 2 ? 'yellow' : 'green')
const worst = computed(() =>
  report.value ? [...report.value.rooms].filter((r) => r.avg_co2 != null).sort((a, b) => b.percent_over_alert - a.percent_over_alert)[0] : null,
)

onMounted(async () => {
  schools.value = await api('/schools')
  schoolId.value = store.user.role === 'director' ? store.user.school_id : schools.value[0]?.id
  load()
})
watch([week, schoolId], load)
</script>

<template>
  <h1>Седмичен отчет</h1>
  <p class="muted">Обобщение за директора: колко време всяка стая е била с лош въздух.</p>

  <div class="row controls">
    <select v-if="store.user.role === 'admin'" v-model.number="schoolId" style="width: auto">
      <option v-for="s in schools" :key="s.id" :value="s.id">{{ s.name }}</option>
    </select>
    <button class="btn ghost small" @click="shiftWeek(-7)">← Предишна</button>
    <input v-model="week" type="date" style="width: auto" aria-label="Седмица" />
    <button class="btn ghost small" @click="shiftWeek(7)">Следваща →</button>
    <div class="spacer"></div>
    <a class="btn small" :href="csv" download>⬇ Експорт CSV</a>
  </div>

  <p v-if="error" class="error">{{ error }}</p>

  <template v-if="report">
    <p class="muted">{{ report.school_name }} · {{ report.week_start }} – {{ report.week_end }}</p>
    <div v-if="worst && worst.percent_over_alert > 0" class="card summary st-red">
      Най-задушна стая: <strong>{{ worst.room_name }}</strong> – {{ worst.percent_over_alert }}% от времето над
      1200 ppm ({{ worst.minutes_over_alert }} мин), {{ worst.alerts }} известия.
    </div>
    <div class="card table-wrap">
      <table>
        <thead>
          <tr>
            <th>Стая</th><th>Среден CO₂</th><th>Макс. CO₂</th><th>Над 1200 ppm</th><th></th>
            <th>Ср. темп.</th><th>Ср. влажност</th><th>Известия</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in report.rooms" :key="r.room_id" :class="`st-${statusOf(r)}`">
            <td><RouterLink :to="`/rooms/${r.room_id}`">{{ r.room_name }}</RouterLink></td>
            <td>{{ r.avg_co2 ?? '—' }}</td>
            <td>{{ r.max_co2 ?? '—' }}</td>
            <td>{{ r.minutes_over_alert }} мин</td>
            <td class="bar-cell">
              <div class="bar"><div :style="{ width: Math.min(100, r.percent_over_alert * 3) + '%' }"></div></div>
              <span class="pill">{{ r.percent_over_alert }}%</span>
            </td>
            <td>{{ r.avg_temperature ?? '—' }} °C</td>
            <td>{{ r.avg_humidity ?? '—' }} %</td>
            <td>{{ r.alerts }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </template>
</template>

<style scoped>
.controls { margin: 12px 0; }
.summary { margin-bottom: 12px; border-left: 6px solid var(--st); }
.bar-cell { display: flex; align-items: center; gap: 8px; min-width: 160px; }
.bar { flex: 1; height: 8px; border-radius: 4px; background: var(--surface-2); overflow: hidden; }
.bar div { height: 100%; background: var(--st); }
</style>
