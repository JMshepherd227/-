<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
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
let pickingEnabled = false
let geocoder = null
let drivingLive = null
let drivingOriginal = null
let livePath = []
let originalPath = []
let livePointMarkers = []
let originalPointMarkers = []
const WS_BASE = import.meta.env.VITE_WS_BASE || ''
const TILE_CACHE_TTL_MS = 60 * 1000
const TILE_REFRESH_DEBOUNCE_MS = 400
const AUTO_REFRESH_INTERVAL_MS = 15 * 1000
let droneMarkers = new Map()
let droneTracks = new Map()
let ws = null
let reconnectTimer = null
const RECONNECT_DELAY_MS = 3000
let tileRefreshFlushTimer = null
let autoRefreshTimer = null
const pendingTileRefreshKeys = new Set()

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
    AMapRef.plugin(['AMap.Scale','AMap.ToolBar','AMap.ControlBar'], () => {
      try { mapInstance.addControl(new AMapRef.Scale()) } catch {}
      try { mapInstance.addControl(new AMapRef.ToolBar()) } catch {}
      try { mapInstance.addControl(new AMapRef.ControlBar()) } catch {}
    })
    mapReady.value = true
    mapError.value = ''

    mapInstance.on('moveend', () => { if (autoLoad.value) scheduleLoad() })
    mapInstance.on('zoomend', () => { if (autoLoad.value) scheduleLoad() })
    autoRefreshTimer = setInterval(() => {
      if (autoLoad.value && mapReady.value) {
        loadViewport().catch(() => {})
      }
    }, AUTO_REFRESH_INTERVAL_MS)
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
          searchLiveDrivingRoute()
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
      dispatchPlannedRoutePoints([])
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
      searchLiveDrivingRoute()
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
        searchLiveDrivingRoute()
      }
    })
    connectTelemetryWS()
  } catch (e) {
    mapError.value = e?.message || '地图初始化失败'
  }
})

onBeforeUnmount(() => {
  if (refreshTimer) clearTimeout(refreshTimer)
  if (tileRefreshFlushTimer) clearTimeout(tileRefreshFlushTimer)
  if (autoRefreshTimer) clearInterval(autoRefreshTimer)
  if (ws) {
    try { ws.close() } catch {}
    ws = null
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

function dispatchPlannedRoutePoints(points) {
  const detail = Array.isArray(points) ? points : []
  window.dispatchEvent(new CustomEvent('route-planned-path-update', { detail }))
}

function normalizeDrivingPathPoint(point) {
  const lngValue = Array.isArray(point)
    ? point[0]
    : (typeof point?.getLng === 'function' ? point.getLng() : point?.lng)
  const latValue = Array.isArray(point)
    ? point[1]
    : (typeof point?.getLat === 'function' ? point.getLat() : point?.lat)
  const lng = Number(lngValue)
  const lat = Number(latValue)
  if (Number.isNaN(lng) || Number.isNaN(lat)) return null
  return { lng, lat }
}

function extractDrivingRoutePoints(result) {
  const routes = Array.isArray(result?.routes) ? result.routes : []
  const route = routes[0]
  if (!route) return []
  const rawPath = Array.isArray(route.path) && route.path.length
    ? route.path
    : (Array.isArray(route.steps) ? route.steps.flatMap(step => Array.isArray(step?.path) ? step.path : []) : [])
  const normalized = []
  for (const item of rawPath) {
    const point = normalizeDrivingPathPoint(item)
    if (!point) continue
    const prev = normalized[normalized.length - 1]
    if (prev && prev.lng === point.lng && prev.lat === point.lat) continue
    normalized.push(point)
  }
  return normalized
}

function handleLiveDrivingResult(status, result) {
  if (status === 'complete') {
    mapError.value = ''
    dispatchPlannedRoutePoints(extractDrivingRoutePoints(result))
  } else {
    mapError.value = String(result?.info || result?.message || '路线规划失败')
    dispatchPlannedRoutePoints([])
  }
}

function searchLiveDrivingRoute() {
  if (!drivingLive || !AMapRef) return
  if (livePath.length < 2) {
    dispatchPlannedRoutePoints([])
    try { drivingLive.clear() } catch {}
    return
  }
  const start = livePath[0]
  const end = livePath[livePath.length - 1]
  const waypoints = livePath.slice(1, livePath.length - 1)
  try {
    const S = new AMapRef.LngLat(start[0], start[1])
    const E = new AMapRef.LngLat(end[0], end[1])
    const W = waypoints.map(p => new AMapRef.LngLat(p[0], p[1]))
    drivingLive.clear()
    if (W.length) {
      drivingLive.search(S, E, { waypoints: W }, handleLiveDrivingResult)
    } else {
      drivingLive.search(S, E, handleLiveDrivingResult)
    }
  } catch {
    dispatchPlannedRoutePoints([])
  }
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

function tileKey(z, x, y) {
  return `${z}:${x}:${y}`
}

function pruneTileCache() {
  const now = Date.now()
  for (const [key, entry] of tileCache.entries()) {
    if (!entry || entry.expiresAt <= now) {
      tileCache.delete(key)
    }
  }
}

function evictTileCacheKeys(keys) {
  for (const key of keys) {
    tileCache.delete(key)
  }
}

function pointToTileKey(lng, lat, z) {
  const Lng = Number(lng)
  const Lat = Number(lat)
  if (Number.isNaN(Lng) || Number.isNaN(Lat)) return ''
  return tileKey(z, lon2tileX(Lng, z), lat2tileY(Lat, z))
}

function hasVisibleTileKey(keys) {
  if (!mapInstance || !keys || keys.size === 0) return false
  const visibleKeys = new Set(getVisibleTiles().map(t => tileKey(t.z, t.x, t.y)))
  for (const key of keys) {
    if (visibleKeys.has(key)) return true
  }
  return false
}

function queueTileRefreshForPoint(lng, lat) {
  if (!mapInstance || !mapReady.value) return
  const z = clamp(Math.floor(mapInstance.getZoom()), 1, 18)
  const key = pointToTileKey(lng, lat, z)
  if (!key) return
  pendingTileRefreshKeys.add(key)
  tileCache.delete(key)
  if (tileRefreshFlushTimer) clearTimeout(tileRefreshFlushTimer)
  tileRefreshFlushTimer = setTimeout(async () => {
    const forceKeys = new Set(pendingTileRefreshKeys)
    pendingTileRefreshKeys.clear()
    tileRefreshFlushTimer = null
    evictTileCacheKeys(forceKeys)
    if (hasVisibleTileKey(forceKeys)) {
      await loadViewport({ forceKeys })
    }
  }, TILE_REFRESH_DEBOUNCE_MS)
}

async function fetchTile(z, x, y, options = {}) {
  pruneTileCache()
  const { force = false } = options
  const key = tileKey(z, x, y)
  const cached = tileCache.get(key)
  if (!force && cached && cached.expiresAt > Date.now()) return cached.data
  if (force) tileCache.delete(key)
  const query = new URLSearchParams({
    z: String(z),
    x: String(x),
    y: String(y),
    forceRefresh: force ? 'true' : 'false'
  })
  const url = `${API_BASE}/api/v1/map/tile?${query.toString()}`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`瓦片加载失败(${res.status})`)
  const json = await res.json()
  const data = json && json.code === 200 && Array.isArray(json.data) ? json.data : null
  if (data) {
    tileCache.set(key, { data, expiresAt: Date.now() + TILE_CACHE_TTL_MS })
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
  const lng = img.matchedLng ?? img.rawLng ?? img.lng
  const lat = img.matchedLat ?? img.rawLat ?? img.lat
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
    // 兼容 DefectEntity (由 /api/v1/map/tile 返回) 和 InspectionImage
    const isDefect = img.isDefect || (img.defectType !== undefined)
    const count = img.defectCount ?? (img.defectType !== undefined ? 1 : 0)
    
    m.setLabel({
      direction: 'top',
      offset: new AMapRef.Pixel(0, -8),
      content: `<div style="background:${isDefect ? '#ef4444' : '#2563eb'};color:#fff;padding:2px 6px;border-radius:999px;border:1px solid rgba(255,255,255,0.2);font-size:12px;">${count}</div>`
    })
    markers.push(m)
  }
  mapInstance.add(markers)
}

function ensureDroneMarker(id) {
  if (!mapInstance || !AMapRef) return null
  const key = String(id)
  let mk = droneMarkers.get(key)
  if (!mk) {
    // 使用本地无人机图标
    const droneIcon = new AMapRef.Icon({
      size: new AMapRef.Size(40, 40),
      image: '/drone.png', // 指向 public/drone.png
      imageSize: new AMapRef.Size(40, 40)
    })

    mk = new AMapRef.Marker({
      position: [0, 0],
      anchor: 'center',
      title: `无人机#${key}`,
      icon: droneIcon,
      offset: new AMapRef.Pixel(-20, -20)
    })
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
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return
  
  try {
    const url = WS_BASE || `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/telemetry`
    if (ws) { try { ws.close() } catch {} ; ws = null }
    
    ws = new WebSocket(url)
    
    ws.onopen = () => {
      console.log('Telemetry WebSocket connected')
      if (reconnectTimer) {
        clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
    }

    ws.onclose = () => {
      console.log('Telemetry WebSocket disconnected, scheduling reconnect...')
      ws = null
      scheduleReconnect()
    }

    ws.onerror = (err) => {
      console.error('Telemetry WebSocket error:', err)
      ws = null
    }

    ws.onmessage = (evt) => {
      const text = String(evt.data ?? '')
      try {
        const data = JSON.parse(text)
        if (data && data.type === 'telemetry') {
          const payload = Array.isArray(data.data) ? data.data : [data.data ?? data]
          for (const item of payload) {
            const id = Number(item?.droneId ?? item?.id)
            const Lng = Number(item?.lng)
            const Lat = Number(item?.lat)
            if (!Number.isNaN(id) && !Number.isNaN(Lng) && !Number.isNaN(Lat)) {
              updateDroneMarker(id, Lng, Lat)
              appendTrack(id, Lng, Lat)
              queueTileRefreshForPoint(Lng, Lat)
            }
          }
        } else if (data && data.type === 'new_defect') {
          const Lng = Number(data?.data?.lng)
          const Lat = Number(data?.data?.lat)
          if (!Number.isNaN(Lng) && !Number.isNaN(Lat)) queueTileRefreshForPoint(Lng, Lat)
        }
      } catch {}
    }
  } catch (e) {
    console.error('Failed to create WebSocket:', e)
    scheduleReconnect()
  }
}

function scheduleReconnect() {
  if (reconnectTimer) return
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null
    connectTelemetryWS()
  }, RECONNECT_DELAY_MS)
}

async function loadViewport(options = {}) {
  const { force = false, forceKeys = null } = options
  if (!mapReady.value) return
  mapLoading.value = true
  mapError.value = ''
  tileHint.value = ''
  try {
    const tiles = getVisibleTiles()
    tileHint.value = tiles.length ? `tiles=${tiles.length}` : ''
    const results = await Promise.all(tiles.map(t => {
      const shouldForce = force || !!forceKeys?.has(tileKey(t.z, t.x, t.y))
      return fetchTile(t.z, t.x, t.y, { force: shouldForce }).catch(() => [])
    }))
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
      <div class="map-wrap">
        <div ref="mapEl" class="map-canvas"></div>
        <div class="map-toolbar">
          <button @click="loadViewport({ force: true })">刷新</button>
          <button class="secondary" @click="autoLoad = !autoLoad">{{ autoLoad ? '自动刷新：开' : '自动刷新：关' }}</button>
          <span v-if="mapLoading" class="muted">加载中…</span>
          <span v-else class="muted">点位：{{ defects.length }} {{ tileHint ? ('· '+tileHint) : '' }}</span>
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
                <div class="k">图片ID</div><div class="v">{{ selected.id }}</div>
                <div class="k">任务ID</div><div class="v">{{ selected.taskId }}</div>
                <div class="k">无人机ID</div><div class="v">{{ selected.droneId }}</div>
                <div class="k">病害数</div><div class="v">{{ selected.defectCount ?? (selected.defectType !== undefined ? 1 : 0) }}</div>
                <div class="k">状态</div><div class="v">{{ selected.status ?? '-' }}</div>
                <div class="k">坐标</div>
                <div class="v">{{ (selected.matchedLng ?? selected.rawLng ?? selected.lng) ?? '-' }}, {{ (selected.matchedLat ?? selected.rawLat ?? selected.lat) ?? '-' }}</div>
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
.detail-title{font-weight:600;margin-bottom:8px;color:#ffffff}
.table{width:100%;border-collapse:collapse;color:#ffffff}
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
