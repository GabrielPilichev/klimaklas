<script setup>
// Графика с Chart.js. Цветовете се четат от CSS променливите, затова работи и в тъмна тема.
import { onMounted, onUnmounted, ref, watch } from 'vue'
import {
  Chart, LineController, LineElement, PointElement, LinearScale, CategoryScale, Filler, Tooltip, Legend,
} from 'chart.js'
import { store } from '../store.js'

Chart.register(LineController, LineElement, PointElement, LinearScale, CategoryScale, Filler, Tooltip, Legend)

const props = defineProps({
  labels: { type: Array, required: true },
  datasets: { type: Array, required: true }, // [{label, data, colorVar, yAxisID?}]
  thresholds: { type: Array, default: () => [] }, // [{value, colorVar, label}]
  unit: { type: String, default: '' },
  height: { type: Number, default: 300 },
  y2Unit: { type: String, default: '' },
})

const canvas = ref(null)
let chart = null

const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim()

const thresholdPlugin = {
  id: 'thresholds',
  afterDatasetsDraw(c) {
    const y = c.scales.y
    const { left, right } = c.chartArea
    const ctx = c.ctx
    for (const t of props.thresholds) {
      if (t.value < y.min || t.value > y.max) continue
      const py = y.getPixelForValue(t.value)
      ctx.save()
      ctx.strokeStyle = css(t.colorVar)
      ctx.setLineDash([6, 4])
      ctx.beginPath()
      ctx.moveTo(left, py)
      ctx.lineTo(right, py)
      ctx.stroke()
      ctx.fillStyle = css(t.colorVar)
      ctx.font = '12px system-ui'
      ctx.fillText(t.label, left + 6, py - 4)
      ctx.restore()
    }
  },
}

function build() {
  chart?.destroy()
  const grid = css('--border')
  const text = css('--muted')
  const hasY2 = props.datasets.some((d) => d.yAxisID === 'y2')
  chart = new Chart(canvas.value, {
    type: 'line',
    data: {
      labels: props.labels,
      datasets: props.datasets.map((d) => ({
        label: d.label,
        data: d.data,
        yAxisID: d.yAxisID || 'y',
        borderColor: css(d.colorVar),
        backgroundColor: css(d.colorVar) + '22',
        fill: d.fill ?? false,
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.25,
        spanGaps: true,
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: props.datasets.length > 1, labels: { color: text } },
        tooltip: {
          callbacks: { label: (c) => `${c.dataset.label}: ${c.formattedValue}` },
        },
      },
      scales: {
        x: { ticks: { color: text, maxTicksLimit: 8, maxRotation: 0 }, grid: { color: grid } },
        y: { ticks: { color: text }, grid: { color: grid }, title: { display: !!props.unit, text: props.unit, color: text } },
        ...(hasY2
          ? { y2: { position: 'right', ticks: { color: text }, grid: { display: false }, title: { display: true, text: props.y2Unit, color: text } } }
          : {}),
      },
    },
    plugins: [thresholdPlugin],
  })
}

function update() {
  if (!chart) return build()
  chart.data.labels = props.labels
  props.datasets.forEach((d, i) => (chart.data.datasets[i].data = d.data))
  chart.update('none')
}

onMounted(build)
onUnmounted(() => chart?.destroy())
watch(() => [props.labels, props.datasets], update, { deep: true })
watch(() => store.theme, () => setTimeout(build))
</script>

<template>
  <div :style="{ height: height + 'px', position: 'relative' }">
    <canvas ref="canvas" role="img" :aria-label="datasets.map((d) => d.label).join(', ')"></canvas>
  </div>
</template>
