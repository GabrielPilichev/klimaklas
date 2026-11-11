import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router.js'
import { setTheme } from './store.js'
import './styles.css'

try {
  const saved = localStorage.getItem('kk-theme')
  if (saved) setTheme(saved)
} catch {
  /* няма достъп до localStorage */
}

createApp(App).use(router).mount('#app')
