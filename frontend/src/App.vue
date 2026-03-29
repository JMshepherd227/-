<script setup>
import { ref, onMounted } from 'vue'
import DeviceManager from './components/DeviceManager.vue'
import TaskManager from './components/TaskManager.vue'

const mapEl = ref(null)
const active = ref('map')

const AMAP_KEY = import.meta.env.VITE_AMAP_KEY
const AMAP_SECURITY_JS_CODE = import.meta.env.VITE_AMAP_SECURITY_JS_CODE

function loadAMap(key, sec) {
  return new Promise((resolve, reject) => {
    if (window.AMap) { resolve(window.AMap); return }
    if (!key) { reject(new Error('Missing AMap key')); return }
    if (sec) { window._AMapSecurityConfig = { securityJsCode: sec } }
    const script = document.createElement('script')
    script.src = `https://webapi.amap.com/maps?v=2.0&key=${encodeURIComponent(key)}&plugin=AMap.Scale,AMap.ToolBar,AMap.ControlBar`
    script.async = true
    script.onload = () => resolve(window.AMap)
    script.onerror = () => reject(new Error('AMap load failed'))
    document.head.appendChild(script)
  })
}

onMounted(async () => {
  try {
    const AMap = await loadAMap(AMAP_KEY, AMAP_SECURITY_JS_CODE)
    const map = new AMap.Map(mapEl.value, {
      viewMode: '2D',
      zoom: 11,
      center: [116.397428, 39.90923]
    })
    map.addControl(new AMap.Scale())
    map.addControl(new AMap.ToolBar())
    map.addControl(new AMap.ControlBar())
  } catch (e) {
    console.error(e)
  }
})
</script>

<template>
  <div class="page">
    <div class="topbar">
      <div class="brand">无人机道路病害检测</div>
      <div class="tabs">
        <button :class="{on: active==='map'}" @click="active='map'">地图</button>
        <button :class="{on: active==='devices'}" @click="active='devices'">设备</button>
        <button :class="{on: active==='tasks'}" @click="active='tasks'">任务</button>
      </div>
    </div>
    <div class="content">
      <div ref="mapEl" class="map" v-show="active==='map'"></div>
      <DeviceManager v-show="active==='devices'" class="devices-root" />
      <TaskManager v-show="active==='tasks'" class="tasks-root" />
    </div>
  </div>
</template>

<style>
.page{position:fixed;inset:0;display:flex;flex-direction:column;background:#0b0f19}
.topbar{height:56px;display:flex;align-items:center;justify-content:space-between;padding:0 16px;background:#111827;color:#e5e7eb;border-bottom:1px solid #1f2937}
.brand{font-size:16px;font-weight:600}
.tabs{display:flex;gap:8px}
.tabs button{background:#1f2937;color:#e5e7eb;border:1px solid #334155;padding:6px 12px;border-radius:6px;cursor:pointer}
.tabs button.on{background:#2563eb;border-color:#2563eb}
.content{flex:1;display:flex}
.map{flex:1}
.devices-root{flex:1}
</style>
