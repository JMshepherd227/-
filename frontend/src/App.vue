<script setup>
import { ref, onMounted } from 'vue'
import DeviceManager from './components/DeviceManager.vue'
import TaskManager from './components/TaskManager.vue'
import IngestConsole from './components/IngestConsole.vue'

const mapEl = ref(null)
const active = ref('map')

const API_BASE = import.meta.env.VITE_API_BASE || ''

const AMAP_KEY = import.meta.env.VITE_AMAP_KEY
const AMAP_SECURITY_JS_CODE = import.meta.env.VITE_AMAP_SECURITY_JS_CODE

const mapReady = ref(false)
const mapError = ref('')
const mapLoading = ref(false)
const autoLoad = ref(true)
const tileHint = ref('')

const defects = ref([])
const selected = ref(null)
const selectedDetails = ref([])
const detailsLoading = ref(false)
const detailsError = ref('')

let mapInstance = null
let AMapRef = null
let refreshTimer = null
let markers = []
const tileCache = new Map()

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
    AMapRef = await loadAMap(AMAP_KEY, AMAP_SECURITY_JS_CODE)
    mapInstance = new AMapRef.Map(mapEl.value, {
      viewMode: '2D',
      zoom: 11,
      center: [116.397428, 39.90923]
    })
    mapInstance.addControl(new AMapRef.Scale())
    mapInstance.addControl(new AMapRef.ToolBar())
    mapInstance.addControl(new AMapRef.ControlBar())
    mapReady.value = true
    mapError.value = ''

    mapInstance.on('moveend', () => { if (autoLoad.value) scheduleLoad() })
    mapInstance.on('zoomend', () => { if (autoLoad.value) scheduleLoad() })
    scheduleLoad()
  } catch (e) {
    mapError.value = e.message || '地图初始化失败'
  }
})

function joinUrl(base, path) {
  const b = (base || '').replace(/\/+$/, '')
  const p = String(path || '').replace(/^\/+/, '')
  return `${b}/${p}`
}

function clamp(n, min, max) {
  return Math.min(max, Math.max(min, n))
}

function lon2tileX(lon, z) {
  const n = 2 ** z
  return Math.floor(((lon + 180) / 360) * n)
}

function lat2tileY(lat, z) {
  const n = 2 ** z
  const r = (lat * Math.PI) / 180
  const y = (1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2
  return Math.floor(y * n)
}

function getVisibleTiles() {
  if (!mapInstance) return []
  const z = clamp(Math.floor(mapInstance.getZoom()), 1, 18)
  const b = mapInstance.getBounds()
  const sw = b.getSouthWest()
  const ne = b.getNorthEast()

  const n = 2 ** z
  let xMin = lon2tileX(sw.lng, z)
  let xMax = lon2tileX(ne.lng, z)
  let yMin = lat2tileY(ne.lat, z)
  let yMax = lat2tileY(sw.lat, z)

  xMin = clamp(xMin, 0, n - 1)
  xMax = clamp(xMax, 0, n - 1)
  yMin = clamp(yMin, 0, n - 1)
  yMax = clamp(yMax, 0, n - 1)

  const tiles = []
  for (let x = xMin; x <= xMax; x++) {
    for (let y = yMin; y <= yMax; y++) {
      tiles.push({ z, x, y })
    }
  }

  const cap = 32
  if (tiles.length > cap) {
    const step = Math.ceil(tiles.length / cap)
    return tiles.filter((_, idx) => idx % step === 0)
  }
  return tiles
}

function scheduleLoad() {
  if (refreshTimer) clearTimeout(refreshTimer)
  refreshTimer = setTimeout(loadViewport, 250)
}

async function fetchTile(z, x, y) {
  const key = `${z}:${x}:${y}`
  if (tileCache.has(key)) return tileCache.get(key)
  const url = `${API_BASE}/api/v1/map/tile?z=${encodeURIComponent(z)}&x=${encodeURIComponent(x)}&y=${encodeURIComponent(y)}`
  const res = await fetch(url)
  const json = await res.json()
  if (json && json.code === 200) {
    const data = Array.isArray(json.data) ? json.data : []
    tileCache.set(key, data)
    return data
  }
  throw new Error(json?.msg || '瓦片加载失败')
}

function clearMarkers() {
  if (!mapInstance) return
  for (const m of markers) {
    try { mapInstance.remove(m) } catch {}
  }
  markers = []
}

function pointOf(img) {
  const lng = img.matchedLng ?? img.rawLng
  const lat = img.matchedLat ?? img.rawLat
  if (lng === null || lng === undefined || lat === null || lat === undefined) return null
  const Lng = Number(lng)
  const Lat = Number(lat)
  if (Number.isNaN(Lng) || Number.isNaN(Lat)) return null
  return [Lng, Lat]
}

function updateMarkers(list) {
  if (!mapInstance || !AMapRef) return
  clearMarkers()
  for (const img of list) {
    const pos = pointOf(img)
    if (!pos) continue
    const m = new AMapRef.Marker({
      position: pos,
      anchor: 'center'
    })
    m.on('click', () => {
      openDetail(img)
    })
    m.setLabel({
      direction: 'top',
      offset: new AMapRef.Pixel(0, -8),
      content: `<div style="background:${img.isDefect ? '#ef4444' : '#2563eb'};color:#fff;padding:2px 6px;border-radius:999px;border:1px solid rgba(255,255,255,0.2);font-size:12px;">${img.defectCount ?? 0}</div>`
    })
    markers.push(m)
  }
  mapInstance.add(markers)
}

async function loadViewport() {
  if (!mapReady.value) return
  mapLoading.value = true
  mapError.value = ''
  tileHint.value = ''
  try {
    const tiles = getVisibleTiles()
    tileHint.value = tiles.length ? `tiles=${tiles.length}` : ''
    const results = await Promise.all(tiles.map(t => fetchTile(t.z, t.x, t.y).catch(() => [])))
    const merged = results.flat()
    const uniq = new Map()
    for (const it of merged) {
      if (it && it.id != null) uniq.set(String(it.id), it)
    }
    const list = Array.from(uniq.values())
    defects.value = list
    updateMarkers(list)
  } catch (e) {
    mapError.value = e.message || '加载失败'
  } finally {
    mapLoading.value = false
  }
}

async function openDetail(img) {
  selected.value = img
  selectedDetails.value = []
  detailsError.value = ''
  detailsLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/api/v1/map/${encodeURIComponent(img.id)}/details`)
    const json = await res.json()
    if (json && json.code === 200) {
      selectedDetails.value = Array.isArray(json.data) ? json.data : []
    } else {
      throw new Error(json?.msg || '详情加载失败')
    }
  } catch (e) {
    detailsError.value = e.message || '详情加载失败'
  } finally {
    detailsLoading.value = false
  }
}

function closeDetail() {
  selected.value = null
  selectedDetails.value = []
  detailsError.value = ''
  detailsLoading.value = false
}
</script>

<template>
  <div class="page">
    <div class="topbar">
      <div class="brand">无人机道路病害检测</div>
      <div class="tabs">
        <button :class="{on: active==='map'}" @click="active='map'">地图</button>
        <button :class="{on: active==='devices'}" @click="active='devices'">设备</button>
        <button :class="{on: active==='tasks'}" @click="active='tasks'">任务</button>
        <button :class="{on: active==='ingest'}" @click="active='ingest'">采集</button>
      </div>
    </div>
    <div class="content">
      <div class="map-wrap" v-show="active==='map'">
        <div ref="mapEl" class="map-canvas"></div>
        <div class="map-toolbar">
          <button @click="loadViewport">刷新</button>
          <button class="secondary" @click="autoLoad = !autoLoad">{{ autoLoad ? '自动刷新：开' : '自动刷新：关' }}</button>
          <span v-if="mapLoading" class="muted">加载中…</span>
          <span v-else class="muted">点位：{{ defects.length }} {{ tileHint ? ('· '+tileHint) : '' }}</span>
          <span v-if="mapError" class="error">{{ mapError }}</span>
        </div>

        <div class="drawer" v-if="selected">
          <div class="drawer-head">
            <div class="drawer-title">病害详情</div>
            <button class="secondary" @click="closeDetail">关闭</button>
          </div>
          <div class="drawer-body">
            <div class="kv">
              <div class="k">图片ID</div><div class="v">{{ selected.id }}</div>
              <div class="k">任务ID</div><div class="v">{{ selected.taskId }}</div>
              <div class="k">无人机ID</div><div class="v">{{ selected.droneId }}</div>
              <div class="k">病害数</div><div class="v">{{ selected.defectCount ?? 0 }}</div>
              <div class="k">状态</div><div class="v">{{ selected.status ?? '-' }}</div>
              <div class="k">坐标</div>
              <div class="v">{{ (selected.matchedLng ?? selected.rawLng) ?? '-' }}, {{ (selected.matchedLat ?? selected.rawLat) ?? '-' }}</div>
            </div>

            <div class="imgs">
              <a v-if="selected.originalImageUrl" class="img-link" :href="joinUrl(API_BASE, selected.originalImageUrl)" target="_blank" rel="noreferrer">
                <div class="img-title">原图</div>
                <img :src="joinUrl(API_BASE, selected.originalImageUrl)" alt="origin" />
              </a>
              <a v-if="selected.resultImageUrl" class="img-link" :href="joinUrl(API_BASE, selected.resultImageUrl)" target="_blank" rel="noreferrer">
                <div class="img-title">结果图</div>
                <img :src="joinUrl(API_BASE, selected.resultImageUrl)" alt="result" />
              </a>
            </div>

            <div class="detail">
              <div class="detail-title">识别列表</div>
              <div v-if="detailsLoading" class="muted">加载中…</div>
              <div v-else-if="detailsError" class="error">{{ detailsError }}</div>
              <div v-else-if="selectedDetails.length===0" class="muted">暂无详情</div>
              <table v-else class="table">
                <thead>
                  <tr><th>类型</th><th>置信度</th><th>时间</th></tr>
                </thead>
                <tbody>
                  <tr v-for="d in selectedDetails" :key="d.id">
                    <td>{{ d.defectType }}</td>
                    <td>{{ d.confidence }}</td>
                    <td>{{ d.createTime ?? '-' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
      <DeviceManager v-show="active==='devices'" class="devices-root" />
      <TaskManager v-show="active==='tasks'" class="tasks-root" />
      <IngestConsole v-show="active==='ingest'" class="ingest-root" />
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
.map-wrap{flex:1;position:relative}
.map-canvas{position:absolute;inset:0;z-index:0}
.map-toolbar{position:absolute;left:12px;top:12px;z-index:20;display:flex;gap:8px;align-items:center;flex-wrap:wrap;background:rgba(17,24,39,0.9);border:1px solid #374151;border-radius:8px;padding:8px;color:#e5e7eb;max-width:calc(100% - 24px)}
.drawer{position:absolute;right:12px;top:12px;bottom:12px;z-index:20;width:420px;background:rgba(17,24,39,0.96);border:1px solid #374151;border-radius:10px;display:flex;flex-direction:column;overflow:hidden}
.drawer-head{display:flex;align-items:center;justify-content:space-between;padding:10px 12px;border-bottom:1px solid #374151}
.drawer-title{font-weight:600}
.drawer-body{padding:12px;overflow:auto;display:flex;flex-direction:column;gap:12px}
.kv{display:grid;grid-template-columns:88px 1fr;gap:6px 10px}
.k{color:#9ca3af}
.v{color:#e5e7eb;word-break:break-all}
.imgs{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.img-link{display:block;border:1px solid #334155;border-radius:8px;overflow:hidden;text-decoration:none;color:#e5e7eb;background:#0b0f19}
.img-title{padding:6px 8px;border-bottom:1px solid #334155;color:#9ca3af;font-size:12px}
.img-link img{display:block;width:100%;height:160px;object-fit:cover}
.detail-title{font-weight:600;margin-bottom:8px}
.table{width:100%;border-collapse:collapse}
.table th,.table td{border:1px solid #334155;padding:6px 8px;font-size:12px}
.table thead{background:#1f2937}
.devices-root{flex:1}
.tasks-root{flex:1}
.ingest-root{flex:1}
button{background:#2563eb;color:#fff;border:none;padding:6px 12px;cursor:pointer;border-radius:6px}
button.secondary{background:#1f2937;border:1px solid #334155}
.muted{color:#9ca3af}
.error{color:#f87171}
</style>
