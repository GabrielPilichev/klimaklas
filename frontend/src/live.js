// WebSocket връзка за стойности на живо. При прекъсване се свързва отново с нарастващо изчакване.
import { store, toast } from './store.js'

let ws = null
let retry = 1000
let pingTimer = null
let stopped = true
const listeners = new Set()

export function onLive(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

function handle(msg) {
  if (msg.type === 'reading') {
    const room = store.rooms.find((r) => r.id === msg.room_id)
    if (room) {
      room.latest = msg.reading
      room.status = msg.status
    }
  } else if (msg.type === 'alert') {
    const room = store.rooms.find((r) => r.id === msg.room_id)
    if (room) room.alert_active = true
    store.activeAlerts.unshift({
      id: msg.alert_id,
      room_id: msg.room_id,
      room_name: msg.room_name,
      max_co2: msg.co2,
      started_at: msg.started_at,
      active: true,
    })
    const text = `Отворете прозореца в стая ${msg.room_name}! CO₂: ${msg.co2} ppm`
    toast(text, 'danger', 15000)
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification('КлимаКлас', { body: text, icon: '/favicon.svg' })
    }
  }
  listeners.forEach((fn) => fn(msg))
}

function connect() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  ws = new WebSocket(`${proto}://${location.host}/api/v1/ws`)
  ws.onopen = () => {
    store.liveConnected = true
    retry = 1000
    pingTimer = setInterval(() => ws?.readyState === 1 && ws.send('ping'), 25000)
  }
  ws.onmessage = (e) => {
    try {
      handle(JSON.parse(e.data))
    } catch {
      /* игнорираме невалидни съобщения */
    }
  }
  ws.onclose = () => {
    store.liveConnected = false
    clearInterval(pingTimer)
    if (!stopped) setTimeout(connect, (retry = Math.min(retry * 2, 30000)))
  }
}

export function startLive() {
  if (!stopped) return
  stopped = false
  connect()
}

export function stopLive() {
  stopped = true
  ws?.close()
  ws = null
}
