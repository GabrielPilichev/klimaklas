<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api.js'
import { store } from '../store.js'

const router = useRouter()
const route = useRoute()
const email = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

const demo = [
  { email: 'admin@klimaklas.test', label: 'Администратор' },
  { email: 'direktor@klimaklas.test', label: 'Директор' },
  { email: 'uchitel@klimaklas.test', label: 'Учител' },
]

async function submit() {
  error.value = ''
  busy.value = true
  try {
    store.user = await api('/auth/login', { method: 'POST', body: { email: email.value, password: password.value } })
    const next = typeof route.query.next === 'string' && route.query.next.startsWith('/') ? route.query.next : '/'
    router.replace(next)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="login">
    <div class="card">
      <div class="head">
        <img src="/favicon.svg" alt="" width="44" height="44" />
        <div>
          <h1>КлимаКлас</h1>
          <p class="muted">Чист въздух във всяка класна стая</p>
        </div>
      </div>
      <form @submit.prevent="submit">
        <div class="field">
          <label for="email">Имейл</label>
          <input id="email" v-model="email" type="email" autocomplete="username" required />
        </div>
        <div class="field">
          <label for="password">Парола</label>
          <input id="password" v-model="password" type="password" autocomplete="current-password" required />
        </div>
        <p v-if="error" class="error">{{ error }}</p>
        <button class="btn full" :disabled="busy">{{ busy ? 'Влизане…' : 'Вход' }}</button>
      </form>
      <div class="demo">
        <p class="muted">Тестови акаунти:</p>
        <button v-for="d in demo" :key="d.email" type="button" class="btn ghost small" @click="email = d.email">
          {{ d.label }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login { min-height: 80vh; display: grid; place-items: center; }
.card { width: 100%; max-width: 380px; padding: 28px; }
.head { display: flex; gap: 12px; align-items: center; margin-bottom: 20px; }
.head p { margin: 0; }
.full { width: 100%; margin-top: 4px; }
.demo { margin-top: 20px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.demo p { margin: 0 4px 0 0; font-size: 14px; }
</style>
