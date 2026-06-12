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
const displayMode = ref('点位')
const displayScale = ref('')

const defects = ref([])
const selected = ref(null)
const selectedDetails = ref([])
const detailsLoading = ref(false)
const detailsError = ref('')

let mapInstance = null
let AMapRef = null
let refreshTimer = null
let markers = []
let heatmapLayer = null
let heatmapReady = false
let currentOverlayMode = 'markers'
const tileCache = new Map()
let pickingEnabled = false
let geocoder = null
let drivingLive = null
let drivingOriginal = null
let livePath = []
let originalPath = []
let livePointMarkers = []
let originalPointMarkers = []
const WS_BASE = import.meta.env.VITE_WS_BASE || ''
let droneMarkers = new Map()
let droneTracks = new Map()
let ws = null
const HEATMAP_TRIGGER_METERS_PER_PIXEL = 10

function loadAMap(key, sec) {
  return new Promise((resolve, reject) => {
    if (window.AMap) { resolve(window.AMap); return }
    if (!key) { reject(new Error('Missing AMap key')); return }
    if (sec) { window._AMapSecurityConfig = { securityJsCode: sec } }
    const script = document.createElement('script')
    script.src = `https://webapi.amap.com/maps?v=2.0&key=${encodeURIComponent(key)}`
    script.async = true
    script.onload = () => resolve(window.AMap)
    script.onerror = () => reject(new Error('AMap load failed'))
    document.head.appendChild(script)
  })
}

onMounted(async () => {
  try {
    if (!AMAP_KEY) throw new Error('未配置 VITE_AMAP_KEY')
    AMapRef = await loadAMap(AMAP_KEY, AMAP_SECURITY_JS_CODE)
    if (!AMapRef || !AMapRef.Map) throw new Error('AMap 加载失败')
    mapInstance = new AMapRef.Map(mapEl.value, {
      viewMode: '2D',
      zoom: 11,
      center: [116.397428, 39.90923]
    })
    AMapRef.plugin(['AMap.Scale','AMap.ToolBar','AMap.ControlBar','AMap.HeatMap'], () => {
      try { mapInstance.addControl(new AMapRef.Scale()) } catch {}
      try { mapInstance.addControl(new AMapRef.ToolBar()) } catch {}
      try { mapInstance.addControl(new AMapRef.ControlBar()) } catch {}
      try {
        if (AMapRef.HeatMap) {
          heatmapLayer = new AMapRef.HeatMap(mapInstance, {
            radius: 28,
            opacity: [0, 0.9],
            zooms: [3, 20],
            gradient: {
              0.2: '#38bdf8',
              0.45: '#84cc16',
              0.65: '#facc15',
              0.82: '#fb7185',
              1.0: '#dc2626'
            }
          })
          heatmapReady = true
          try { heatmapLayer.hide() } catch {}
        }
      } catch {}
      updateMapVisualization(defects.value, true)
    })
    mapReady.value = true
    mapError.value = ''

    mapInstance.on('moveend', () => {
      updateMapVisualization(defects.value)
      if (autoLoad.value) scheduleLoad()
    })
    mapInstance.on('zoomend', () => {
      updateMapVisualization(defects.value)
      if (autoLoad.value) scheduleLoad()
    })
    scheduleLoad()
    AMapRef.plugin(['AMap.Geocoder','AMap.Driving'], () => {
      try { geocoder = new AMapRef.Geocoder() } catch {}
      try {
        drivingLive = new AMapRef.Driving({ map: mapInstance, policy: AMapRef.DrivingPolicy.LEAST_TIME, autoFitView: true, hideMarkers: false })
        drivingOriginal = new AMapRef.Driving({ map: mapInstance, policy: AMapRef.DrivingPolicy.LEAST_TIME, autoFitView: true, hideMarkers: false })
        if (drivingLive?.setRenderOptions) {
          drivingLive.setRenderOptions({ polylineOptions: { strokeColor: '#2b78f2', strokeWeight: 5, isOutline: true, outlineColor: '#bcd2f9' } })
        }
        if (drivingOriginal?.setRenderOptions) {
          drivingOriginal.setRenderOptions({ polylineOptions: { strokeColor: '#60a5fa', strokeWeight: 4, isOutline: true, outlineColor: 'rgba(0,0,0,0.2)' } })
        }
        if (drivingLive?.on) {
          drivingLive.on('complete', () => { mapError.value = '' })
          drivingLive.on('error', (e) => { mapError.value = (e && e.info) || '路线规划失败' })
        }
        if (drivingLive && livePath.length >= 2) {
          const start = livePath[0]
          const end = livePath[livePath.length - 1]
          const waypoints = livePath.slice(1, livePath.length - 1)
          try {
            const S = new AMapRef.LngLat(start[0], start[1])
            const E = new AMapRef.LngLat(end[0], end[1])
            const W = waypoints.map(p => new AMapRef.LngLat(p[0], p[1]))
            drivingLive.clear()
            if (W.length) {
              drivingLive.search(S, E, { waypoints: W }, (status, result) => {
                if (status === 'complete') mapError.value = ''
                else mapError.value = String(result?.info || result?.message || '路线规划失败')
              })
            } else {
              drivingLive.search(S, E, (status, result) => {
                if (status === 'complete') mapError.value = ''
                else mapError.value = String(result?.info || result?.message || '路线规划失败')
              })
            }
          } catch {}
        }
        if (drivingOriginal && originalPath.length >= 2) {
          const startO = originalPath[0]
          const endO = originalPath[originalPath.length - 1]
          const waypointsO = originalPath.slice(1, originalPath.length - 1)
          try {
            const S = new AMapRef.LngLat(startO[0], startO[1])
            const E = new AMapRef.LngLat(endO[0], endO[1])
            const W = waypointsO.map(p => new AMapRef.LngLat(p[0], p[1]))
            drivingOriginal.clear()
            drivingOriginal.search(S, E, { waypoints: W }, (status, result) => {
              if (status === 'complete') {
                mapError.value = ''
                if (originalFallbackLine) { try { mapInstance.remove(originalFallbackLine) } catch {} ; originalFallbackLine = null }
              } else {
                mapError.value = String(result?.info || result?.message || '路线规划失败')
                try {
                  if (!originalFallbackLine) { originalFallbackLine = new AMapRef.Polyline({ strokeColor: '#a7f3d0', strokeWeight: 3, isOutline: true, outlineColor: 'rgba(0,0,0,0.2)' }); mapInstance.add(originalFallbackLine) }
                  originalFallbackLine.setPath(originalPath)
                } catch {}
              }
            })
          } catch {}
        }
      } catch {}
    })
    window.addEventListener('route-picking-toggle', (evt) => { pickingEnabled = !!(evt?.detail) })
    window.addEventListener('route-points-clear', () => {
      livePath = []
      try { drivingLive && drivingLive.clear() } catch {}
      try { if (livePointMarkers.length) { mapInstance.remove(livePointMarkers); livePointMarkers = [] } } catch {}
    })
    window.addEventListener('route-points-update', (evt) => {
      const pts = Array.isArray(evt?.detail) ? evt.detail : []
      livePath = pts.filter(p => Array.isArray(p) && p.length >= 2)
      try { if (livePointMarkers.length) { mapInstance.remove(livePointMarkers); livePointMarkers = [] } } catch {}
      for (let i = 0; i < livePath.length; i++) {
        const pos = livePath[i]
        try {
          const m = new AMapRef.Marker({ position: pos, anchor: 'center' })
          m.setLabel({ direction: 'top', offset: new AMapRef.Pixel(0, -8), content: `<div style="background:#2b78f2;color:#fff;padding:2px 6px;border-radius:999px;font-size:12px;">${i+1}</div>` })
          livePointMarkers.push(m)
        } catch {}
      }
      if (livePointMarkers.length) { try { mapInstance.add(livePointMarkers) } catch {} }
      if (drivingLive) {
        if (livePath.length >= 2) {
          const start = livePath[0]
          const end = livePath[livePath.length - 1]
          const waypoints = livePath.slice(1, livePath.length - 1)
          try {
            const S = new AMapRef.LngLat(start[0], start[1])
            const E = new AMapRef.LngLat(end[0], end[1])
            const W = waypoints.map(p => new AMapRef.LngLat(p[0], p[1]))
            drivingLive.clear()
            if (W.length) {
              drivingLive.search(S, E, { waypoints: W }, (status, result) => {
                if (status === 'complete') mapError.value = ''
                else mapError.value = String(result?.info || result?.message || '路线规划失败')
              })
            } else {
              drivingLive.search(S, E, (status, result) => {
                if (status === 'complete') mapError.value = ''
                else mapError.value = String(result?.info || result?.message || '路线规划失败')
              })
            }
          } catch {}
        } else {
          try { drivingLive.clear() } catch {}
        }
      }
    })
    window.addEventListener('route-original-set', (evt) => {
      const pts = Array.isArray(evt?.detail) ? evt.detail : []
      originalPath = pts.filter(p => Array.isArray(p) && p.length >= 2)
      try { if (originalPointMarkers.length) { mapInstance.remove(originalPointMarkers); originalPointMarkers = [] } } catch {}
      for (let i = 0; i < originalPath.length; i++) {
        const pos = originalPath[i]
        try {
          const m = new AMapRef.Marker({ position: pos, anchor: 'center' })
          m.setLabel({ direction: 'top', offset: new AMapRef.Pixel(0, -8), content: `<div style="background:#60a5fa;color:#111827;padding:2px 6px;border-radius:999px;font-size:12px;">${i+1}</div>` })
          originalPointMarkers.push(m)
        } catch {}
      }
      if (originalPointMarkers.length) { try { mapInstance.add(originalPointMarkers) } catch {} }
      if (drivingOriginal && originalPath.length >= 2) {
        const start = originalPath[0]
        const end = originalPath[originalPath.length - 1]
        const waypoints = originalPath.slice(1, originalPath.length - 1)
        try {
          const S = new AMapRef.LngLat(start[0], start[1])
          const E = new AMapRef.LngLat(end[0], end[1])
          const W = waypoints.map(p => new AMapRef.LngLat(p[0], p[1]))
          drivingOriginal.clear()
          if (W.length) {
            drivingOriginal.search(S, E, { waypoints: W }, (status, result) => {
              if (status === 'complete') mapError.value = ''
              else mapError.value = String(result?.info || result?.message || '路线规划失败')
            })
          } else {
            drivingOriginal.search(S, E, (status, result) => {
              if (status === 'complete') mapError.value = ''
              else mapError.value = String(result?.info || result?.message || '路线规划失败')
            })
          }
        } catch {}
      } else {
        try { drivingOriginal && drivingOriginal.clear() } catch {}
      }
    })
    mapInstance.on('click', (e) => {
      if (!pickingEnabled) return
      const lng = e?.lnglat?.lng, lat = e?.lnglat?.lat
      if (typeof lng !== 'number' || typeof lat !== 'number') return
      const addEvt = (addr) => { window.dispatchEvent(new CustomEvent('route-point-picked', { detail: { lng, lat, address: addr || '' } })) }
      if (geocoder && geocoder.getAddress) {
        try {
          geocoder.getAddress([lng, lat], (status, result) => {
            const addr = (result && result.regeocode && result.regeocode.formattedAddress) || ''
            addEvt(addr)
          })
        } catch { addEvt('') }
      } else { addEvt('') }
      livePath.push([lng, lat])
      try {
        const m = new AMapRef.Marker({ position: [lng, lat], anchor: 'center' })
        m.setLabel({ direction: 'top', offset: new AMapRef.Pixel(0, -8), content: `<div style="background:#2b78f2;color:#fff;padding:2px 6px;border-radius:999px;font-size:12px;">${livePath.length}</div>` })
        livePointMarkers.push(m)
        mapInstance.add(m)
      } catch {}
      if (drivingLive && livePath.length >= 2) {
        const start = livePath[0]
        const end = livePath[livePath.length - 1]
        const waypoints = livePath.slice(1, livePath.length - 1)
        try {
          const S = new AMapRef.LngLat(start[0], start[1])
          const E = new AMapRef.LngLat(end[0], end[1])
          const W = waypoints.map(p => new AMapRef.LngLat(p[0], p[1]))
          drivingLive.clear()
          if (W.length) {
            drivingLive.search(S, E, { waypoints: W }, (status, result) => {
              if (status === 'complete') mapError.value = ''
              else mapError.value = String(result?.info || result?.message || '路线规划失败')
            })
          } else {
            drivingLive.search(S, E, (status, result) => {
              if (status === 'complete') mapError.value = ''
              else mapError.value = String(result?.info || result?.message || '路线规划失败')
            })
          }
        } catch {}
      }
    })
    connectTelemetryWS()
  } catch (e) {
    mapError.value = e?.message || '地图初始化失败'
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
  const lng = img.lng
  const lat = img.lat
  if (lng == null || lat == null) return null
  const Lng = Number(lng)
  const Lat = Number(lat)
  if (Number.isNaN(Lng) || Number.isNaN(Lat)) return null
  return [Lng, Lat]
}

function getCenterLat() {
  if (!mapInstance || !mapInstance.getCenter) return 0
  try {
    const center = mapInstance.getCenter()
    if (typeof center?.getLat === 'function') return Number(center.getLat()) || 0
    return Number(center?.lat) || 0
  } catch {
    return 0
  }
}

function getMetersPerPixel() {
  if (!mapInstance || !mapInstance.getZoom) return 0
  const zoom = Number(mapInstance.getZoom())
  if (Number.isNaN(zoom)) return 0
  const lat = getCenterLat()
  const metersPerPixel = (156543.03392 * Math.cos((lat * Math.PI) / 180)) / (2 ** zoom)
  return Number.isFinite(metersPerPixel) ? metersPerPixel : 0
}

function shouldShowHeatmap() {
  return heatmapReady && getMetersPerPixel() >= HEATMAP_TRIGGER_METERS_PER_PIXEL
}

function hideHeatmap() {
  if (!heatmapLayer) return
  try { heatmapLayer.hide() } catch {}
}

function buildHeatmapDataset(list) {
  const metersPerPixel = Math.max(getMetersPerPixel(), 1)
  const cellMeters = Math.max(metersPerPixel * 24, 10)
  const centerLat = getCenterLat()
  const latStep = cellMeters / 111320
  const lngStep = cellMeters / Math.max(111320 * Math.cos((centerLat * Math.PI) / 180), 0.000001)
  const buckets = new Map()

  for (const img of list) {
    const pos = pointOf(img)
    if (!pos) continue
    const keyX = Math.round(pos[0] / lngStep)
    const keyY = Math.round(pos[1] / latStep)
    const key = `${keyX}:${keyY}`
    const bucket = buckets.get(key) || { lngSum: 0, latSum: 0, count: 0 }
    bucket.lngSum += pos[0]
    bucket.latSum += pos[1]
    bucket.count += 1
    buckets.set(key, bucket)
  }

  let max = 0
  const data = Array.from(buckets.values()).map((bucket) => {
    max = Math.max(max, bucket.count)
    return {
      lng: bucket.lngSum / bucket.count,
      lat: bucket.latSum / bucket.count,
      count: bucket.count,
    }
  })

  return { data, max: Math.max(max, 1) }
}

function renderHeatmap(list) {
  if (!heatmapLayer) return
  const dataset = buildHeatmapDataset(list)
  try {
    heatmapLayer.setDataSet(dataset)
    heatmapLayer.show()
  } catch {}
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
    markers.push(m)
  }
  mapInstance.add(markers)
}

function updateMapVisualization(list, forceRefresh = false) {
  if (!mapInstance) return
  const metersPerPixel = getMetersPerPixel()
  displayScale.value = metersPerPixel > 0 ? `${metersPerPixel.toFixed(metersPerPixel >= 100 ? 0 : 1)} m/px` : ''

  if (shouldShowHeatmap()) {
    displayMode.value = '热力图'
    clearMarkers()
    renderHeatmap(Array.isArray(list) ? list : [])
    currentOverlayMode = 'heatmap'
    return
  }

  displayMode.value = '点位'
  hideHeatmap()
  if (forceRefresh || currentOverlayMode !== 'markers') {
    updateMarkers(Array.isArray(list) ? list : [])
  }
  currentOverlayMode = 'markers'
}

function ensureDroneMarker(id) {
  if (!mapInstance || !AMapRef) return null
  const key = String(id)
  let mk = droneMarkers.get(key)
  if (!mk) {
    mk = new AMapRef.Marker({ position: [0, 0], anchor: 'center', title: `无人机#${key}` })
    droneMarkers.set(key, mk)
    mapInstance.add(mk)
  }
  return mk
}

function updateDroneMarker(id, lng, lat) {
  const mk = ensureDroneMarker(id)
  if (!mk) return
  mk.setPosition([lng, lat])
}

function appendTrack(id, lng, lat) {
  if (!mapInstance || !AMapRef) return
  const key = String(id)
  let tr = droneTracks.get(key)
  if (!tr) {
    tr = { path: [], polyline: new AMapRef.Polyline({ strokeColor: '#34d399', strokeWeight: 3, isOutline: true, outlineColor: 'rgba(0,0,0,0.3)' }) }
    droneTracks.set(key, tr)
    mapInstance.add(tr.polyline)
  }
  tr.path.push([lng, lat])
  if (tr.path.length > 2000) tr.path.splice(0, tr.path.length - 2000)
  tr.polyline.setPath(tr.path)
}

function connectTelemetryWS() {
  try {
    const url = WS_BASE || `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/telemetry`
    if (ws) { try { ws.close() } catch {} ; ws = null }
    ws = new WebSocket(url)
    ws.onmessage = (evt) => {
      const text = String(evt.data ?? '')
      try {
        const data = JSON.parse(text)
        if (data && data.type === 'telemetry') {
          const id = Number(data.droneId)
          const Lng = Number(data.lng)
          const Lat = Number(data.lat)
          if (!Number.isNaN(id) && !Number.isNaN(Lng) && !Number.isNaN(Lat)) {
            updateDroneMarker(id, Lng, Lat)
            appendTrack(id, Lng, Lat)
          }
        }
      } catch {}
    }
  } catch {}
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
      if (it && it.id != null) uniq.set(String(it.id), it)  // DefectEntity.id
    }
    const list = Array.from(uniq.values())
    defects.value = list
    updateMapVisualization(list, true)
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
      <div class="map-wrap">
        <div ref="mapEl" class="map-canvas"></div>
        <div class="map-toolbar">
          <button @click="loadViewport">刷新</button>
          <button class="secondary" @click="autoLoad = !autoLoad">{{ autoLoad ? '自动刷新：开' : '自动刷新：关' }}</button>
          <span v-if="mapLoading" class="muted">加载中…</span>
          <span v-else class="muted">病害：{{ defects.length }} · {{ displayMode }}{{ displayScale ? (' · ' + displayScale) : '' }} {{ tileHint ? ('· '+tileHint) : '' }}</span>
          <span v-if="mapError" class="error">{{ mapError }}</span>
        </div>

        <div class="drawer" :class="{ wide: active==='devices' || active==='ingest', narrow: active==='tasks' }" v-if="selected || active==='devices' || active==='tasks' || active==='ingest'">
          <div class="drawer-head">
            <div class="drawer-title">
              {{ active==='devices' ? '设备管理' : (active==='tasks' ? '任务管理' : (active==='ingest' ? '采集控制台' : '病害详情')) }}
            </div>
            <button class="secondary" @click="active='map'; selected=null">关闭</button>
          </div>
          <div class="drawer-body">
            <DeviceManager v-if="active==='devices'" class="devices-root" />
            <TaskManager v-else-if="active==='tasks'" class="tasks-root" />
            <IngestConsole v-else-if="active==='ingest'" class="ingest-root" />
            <template v-else>
              <div class="kv">
                <div class="k">实体ID</div><div class="v">{{ selected.id }}</div>
                <div class="k">病害类型</div><div class="v">{{ selected.defectType ?? '-' }}</div>
                <div class="k">状态</div><div class="v">{{ selected.status ?? '-' }}</div>
                <div class="k">坐标</div>
                <div class="v">{{ selected.lng ?? '-' }}, {{ selected.lat ?? '-' }}</div>
                <div class="k">创建时间</div><div class="v">{{ selected.createTime ?? '-' }}</div>
              </div>


              <div class="detail">
                <div class="detail-title">识别列表</div>
                <div v-if="detailsLoading" class="muted">加载中…</div>
                <div v-else-if="detailsError" class="error">{{ detailsError }}</div>
                <div v-else-if="selectedDetails.length===0" class="muted">暂无详情</div>
                <table v-else class="table">
                  <thead>
                  <tr><th>类型</th><th>置信度</th><th>地址</th><th>时间</th><th>图片</th></tr>
                  </thead>
                  <tbody>
                  <tr v-for="d in selectedDetails" :key="d.id">
                    <td>{{ d.defectType }}</td>
                    <td>{{ d.confidence }}</td>
                    <td>{{ d.address || d.roadName || '-' }}</td>
                    <td>{{ d.createTime ?? '-' }}</td>
                    <td>
                      <a v-if="d.resultImageUrl" :href="joinUrl(API_BASE, d.resultImageUrl)" target="_blank" rel="noreferrer" style="color:#60a5fa;font-size:12px;">结果图</a>
                      <a v-if="d.originalImageUrl" :href="joinUrl(API_BASE, d.originalImageUrl)" target="_blank" rel="noreferrer" style="color:#9ca3af;font-size:12px;margin-left:6px;">原图</a>
                    </td>
                  </tr>
                  </tbody>
                </table>
              </div>
            </template>
          </div>
        </div>
      </div>
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
.drawer{position:absolute;right:0;top:0;bottom:0;z-index:20;width:520px;background:rgba(17,24,39,0.96);border:1px solid #374151;border-radius:0;display:flex;flex-direction:column;overflow:hidden}
.drawer.wide{width:960px}
.drawer.narrow{width:700px}
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
