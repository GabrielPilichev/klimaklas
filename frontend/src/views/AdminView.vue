<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '../api.js'
import { ROLE_LABELS, fmtTime, loadRooms, store, timeAgo, toast } from '../store.js'

const tab = ref('users')
const users = ref([])
const devices = ref([])
const schools = ref([])
const newToken = ref(null)
const error = ref('')

const roomName = (id) => store.rooms.find((r) => r.id === id)?.name ?? `#${id}`
const schoolName = (id) => schools.value.find((s) => s.id === id)?.name ?? '—'

async function loadAll() {
  ;[users.value, devices.value, schools.value] = await Promise.all([api('/users'), api('/devices'), api('/schools')])
  await loadRooms()
}

async function run(fn, okText) {
  error.value = ''
  try {
    await fn()
    if (okText) toast(okText, 'success')
    await loadAll()
    return true
  } catch (e) {
    error.value = e.message
    return false
  }
}

// ---------- потребители ----------
const u = reactive({ email: '', full_name: '', password: '', role: 'teacher', school_id: null, room_ids: [] })
const schoolRooms = computed(() => store.rooms.filter((r) => r.school_id === u.school_id))
async function createUser() {
  const body = { ...u, school_id: u.role === 'admin' ? null : u.school_id, room_ids: u.role === 'teacher' ? u.room_ids : [] }
  if (await run(() => api('/users', { method: 'POST', body }), 'Потребителят е създаден.')) {
    Object.assign(u, { email: '', full_name: '', password: '', room_ids: [] })
  }
}
function deleteUser(user) {
  if (confirm(`Да изтрия ли ${user.full_name}?`)) run(() => api(`/users/${user.id}`, { method: 'DELETE' }), 'Изтрит.')
}

// ---------- устройства ----------
const d = reactive({ room_id: null, name: '' })
async function createDevice() {
  await run(async () => {
    newToken.value = await api('/devices', { method: 'POST', body: d })
    d.name = ''
  })
}
async function rotate(dev) {
  if (!confirm(`Нов токен за „${dev.name}“? Старият спира да работи веднага.`)) return
  await run(async () => (newToken.value = await api(`/devices/${dev.id}/rotate-token`, { method: 'POST' })))
}
function deleteDevice(dev) {
  if (confirm(`Да изтрия ли „${dev.name}“?`)) run(() => api(`/devices/${dev.id}`, { method: 'DELETE' }), 'Изтрито.')
}
async function copyToken() {
  try {
    await navigator.clipboard.writeText(newToken.value.token)
    toast('Токенът е копиран.', 'success')
  } catch {
    toast('Копирайте токена ръчно.', 'info')
  }
}

// ---------- стаи и училища ----------
const r = reactive({ school_id: null, name: '', floor: 1, capacity: 28 })
const createRoom = () => run(() => api('/rooms', { method: 'POST', body: r }), `Стая ${r.name} е добавена.`)
function deleteRoom(room) {
  if (confirm(`Да изтрия ли стая ${room.name} и всичките ѝ измервания?`))
    run(() => api(`/rooms/${room.id}`, { method: 'DELETE' }), 'Изтрита.')
}
const s = reactive({ name: '', city: '' })
const createSchool = () => run(() => api('/schools', { method: 'POST', body: s }), 'Училището е добавено.')

onMounted(async () => {
  await loadAll()
  u.school_id = r.school_id = schools.value[0]?.id ?? null
  d.room_id = store.rooms[0]?.id ?? null
})
</script>

<template>
  <h1>Администрация</h1>
  <div class="tabs" role="tablist">
    <button v-for="[k, label] in [['users', 'Потребители'], ['devices', 'Устройства'], ['rooms', 'Стаи'], ['schools', 'Училища']]"
            :key="k" class="tab" :class="{ active: tab === k }" role="tab" @click="tab = k">{{ label }}</button>
  </div>
  <p v-if="error" class="error">{{ error }}</p>

  <!-- Потребители -->
  <section v-if="tab === 'users'">
    <form class="card form-grid" @submit.prevent="createUser">
      <div><label>Имейл</label><input v-model="u.email" type="email" required /></div>
      <div><label>Име</label><input v-model="u.full_name" required maxlength="120" /></div>
      <div><label>Парола (мин. 8)</label><input v-model="u.password" type="password" minlength="8" maxlength="72" required autocomplete="new-password" /></div>
      <div>
        <label>Роля</label>
        <select v-model="u.role">
          <option v-for="(label, key) in ROLE_LABELS" :key="key" :value="key">{{ label }}</option>
        </select>
      </div>
      <div v-if="u.role !== 'admin'">
        <label>Училище</label>
        <select v-model.number="u.school_id"><option v-for="x in schools" :key="x.id" :value="x.id">{{ x.name }}</option></select>
      </div>
      <div v-if="u.role === 'teacher'" class="rooms-pick">
        <label>Стаи на учителя</label>
        <label v-for="room in schoolRooms" :key="room.id" class="chk">
          <input v-model="u.room_ids" type="checkbox" :value="room.id" /> {{ room.name }}
        </label>
      </div>
      <button class="btn">Добави потребител</button>
    </form>
    <div class="card table-wrap" style="margin-top: 16px">
      <table>
        <thead><tr><th>Име</th><th>Имейл</th><th>Роля</th><th>Училище</th><th>Стаи</th><th></th></tr></thead>
        <tbody>
          <tr v-for="x in users" :key="x.id">
            <td>{{ x.full_name }}</td><td>{{ x.email }}</td><td>{{ ROLE_LABELS[x.role] }}</td>
            <td>{{ schoolName(x.school_id) }}</td>
            <td>{{ x.room_ids.map(roomName).join(', ') || '—' }}</td>
            <td><button v-if="x.id !== store.user.id" class="btn ghost small" @click="deleteUser(x)">Изтрий</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>

  <!-- Устройства -->
  <section v-if="tab === 'devices'">
    <div v-if="newToken" class="card token">
      <strong>Токен за „{{ newToken.name }}“</strong> – запишете го във <code>firmware/include/secrets.h</code>.
      Показва се само сега!
      <div class="row" style="margin-top: 8px">
        <code class="tok">{{ newToken.token }}</code>
        <button class="btn small" @click="copyToken">Копирай</button>
        <button class="btn ghost small" @click="newToken = null">Готово</button>
      </div>
    </div>
    <form class="card form-grid" @submit.prevent="createDevice">
      <div>
        <label>Стая</label>
        <select v-model.number="d.room_id" required><option v-for="x in store.rooms" :key="x.id" :value="x.id">{{ x.name }}</option></select>
      </div>
      <div><label>Име на устройството</label><input v-model="d.name" required maxlength="60" placeholder="Сензор 214" /></div>
      <button class="btn">Регистрирай устройство</button>
    </form>
    <div class="card table-wrap" style="margin-top: 16px">
      <table>
        <thead><tr><th>Устройство</th><th>Стая</th><th>Последно видяно</th><th>Създадено</th><th></th></tr></thead>
        <tbody>
          <tr v-for="x in devices" :key="x.id">
            <td>{{ x.name }}</td><td>{{ roomName(x.room_id) }}</td>
            <td>{{ timeAgo(x.last_seen_at) }}</td><td>{{ fmtTime(x.created_at) }}</td>
            <td class="row">
              <button class="btn ghost small" @click="rotate(x)">Нов токен</button>
              <button class="btn ghost small" @click="deleteDevice(x)">Изтрий</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>

  <!-- Стаи -->
  <section v-if="tab === 'rooms'">
    <form class="card form-grid" @submit.prevent="createRoom">
      <div><label>Училище</label><select v-model.number="r.school_id"><option v-for="x in schools" :key="x.id" :value="x.id">{{ x.name }}</option></select></div>
      <div><label>Номер/име</label><input v-model="r.name" required maxlength="60" /></div>
      <div><label>Етаж</label><input v-model.number="r.floor" type="number" min="-2" max="20" /></div>
      <div><label>Ученици</label><input v-model.number="r.capacity" type="number" min="1" max="200" /></div>
      <button class="btn">Добави стая</button>
    </form>
    <div class="card table-wrap" style="margin-top: 16px">
      <table>
        <thead><tr><th>Стая</th><th>Етаж</th><th>Ученици</th><th>Училище</th><th></th></tr></thead>
        <tbody>
          <tr v-for="x in store.rooms" :key="x.id">
            <td>{{ x.name }}</td><td>{{ x.floor }}</td><td>{{ x.capacity }}</td><td>{{ schoolName(x.school_id) }}</td>
            <td><button class="btn ghost small" @click="deleteRoom(x)">Изтрий</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>

  <!-- Училища -->
  <section v-if="tab === 'schools'">
    <form class="card form-grid" @submit.prevent="createSchool">
      <div><label>Име</label><input v-model="s.name" required maxlength="120" /></div>
      <div><label>Град</label><input v-model="s.city" maxlength="80" /></div>
      <button class="btn">Добави училище</button>
    </form>
    <div class="card table-wrap" style="margin-top: 16px">
      <table>
        <thead><tr><th>Училище</th><th>Град</th></tr></thead>
        <tbody><tr v-for="x in schools" :key="x.id"><td>{{ x.name }}</td><td>{{ x.city }}</td></tr></tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.rooms-pick { grid-column: 1 / -1; display: flex; flex-wrap: wrap; gap: 4px 14px; }
.rooms-pick > label:first-child { flex-basis: 100%; }
.chk { display: inline-flex; gap: 6px; align-items: center; color: var(--text); }
.chk input { width: auto; }
.token { border-left: 6px solid var(--yellow); margin-bottom: 16px; background: var(--yellow-bg); }
.tok { word-break: break-all; padding: 6px 8px; background: var(--surface); border-radius: 6px; flex: 1; }
</style>
