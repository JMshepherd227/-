<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, computed } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE || ''
const WS_BASE = import.meta.env.VITE_WS_BASE || ''

const devices = ref([])
const tasks = ref([])

const busy = ref(false)
const error = ref('')

const wsStatus = ref('disconnected')
const wsError = ref('')
const wsLastAt = ref('')
let ws = null

const logs = ref([])
function nowText() {
  const d = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}
function pushLog(type, message, payload) {
  logs.value.unshift({ at: nowText(), type, message, payload })
  if (logs.value.length > 200) logs.value.length = 200
}

async function loadDevices() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/devices`)
    const json = await res.json()
    if (json && json.code === 200) {
      devices.value = json.data || []
      return
    }
    devices.value = []
    throw new Error(json?.msg || '获取无人机列表失败')
  } catch (e) {
    const msg = e.message || '获取无人机列表失败'
    error.value = msg
    pushLog('error', '获取无人机列表失败', { error: msg })
  }
}

async function loadTasks() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/tasks`)
    const json = await res.json()
    if (json && json.code === 200) {
      tasks.value = json.data || []
      return
    }
    tasks.value = []
    throw new Error(json?.msg || '获取任务列表失败')
  } catch (e) {
    const msg = e.message || '获取任务列表失败'
    error.value = msg
    pushLog('error', '获取任务列表失败', { error: msg })
  }
}

const upload = reactive({
  taskId: '',
  droneId: '',
  lng: '',
  lat: '',
  file: null
})
const uploadPreview = ref('')

function onPickFile(e) {
  const f = e.target.files && e.target.files[0]
  upload.file = f || null
  if (uploadPreview.value) URL.revokeObjectURL(uploadPreview.value)
  uploadPreview.value = f ? URL.createObjectURL(f) : ''
}

function validateLngLat(lngText, latText) {
  const lng = Number(lngText)
  const lat = Number(latText)
  if (Number.isNaN(lng) || lng < -180 || lng > 180) throw new Error('经度需为 -180~180 的数值')
  if (Number.isNaN(lat) || lat < -90 || lat > 90) throw new Error('纬度需为 -90~90 的数值')
  return { lng, lat }
}

async function submitUpload() {
  error.value = ''
  if (!upload.taskId) { error.value = '请选择任务'; return }
  if (!upload.droneId) { error.value = '请选择无人机'; return }
  if (!upload.file) { error.value = '请选择图片文件'; return }
  let pos
  try {
    pos = validateLngLat(upload.lng, upload.lat)
  } catch (e) {
    error.value = e.message || '坐标不合法'
    return
  }

  const p = new URLSearchParams({
    taskId: String(upload.taskId),
    droneId: String(upload.droneId),
    lng: String(pos.lng),
    lat: String(pos.lat)
  })
  const url = `${API_BASE}/api/v1/drones/upload?${p.toString()}`
  const fd = new FormData()
  fd.append('file', upload.file)

  busy.value = true
  try {
    const res = await fetch(url, { method: 'POST', body: fd })
    const json = await res.json()
    if (json && json.code === 200) {
      pushLog('upload', '图片上传成功（AI 异步处理中）', { taskId: upload.taskId, droneId: upload.droneId, lng: pos.lng, lat: pos.lat })
    } else {
      throw new Error(json?.msg || '上传失败')
    }
  } catch (e) {
    error.value = e.message || '上传失败'
    pushLog('error', '图片上传失败', { error: error.value })
  } finally {
    busy.value = false
  }
}

const telemetry = reactive({
  taskId: '',
  droneId: '',
  lng: '',
  lat: '',
  heading: ''
})
const telemetryLoop = reactive({
  running: false,
  intervalMs: 200
})
let telemetryTimer = null

async function sendTelemetryOnce() {
  error.value = ''
  if (!telemetry.taskId) { error.value = '请选择任务'; return }
  if (!telemetry.droneId) { error.value = '请选择无人机'; return }
  let pos
  try {
    pos = validateLngLat(telemetry.lng, telemetry.lat)
  } catch (e) {
    error.value = e.message || '坐标不合法'
    return
  }

  const payload = {
    taskId: Number(telemetry.taskId),
    droneId: Number(telemetry.droneId),
    lng: pos.lng,
    lat: pos.lat
  }
  if (telemetry.heading !== '' && telemetry.heading !== null) {
    const h = Number(telemetry.heading)
    if (!Number.isNaN(h)) payload.heading = h
  }

  busy.value = true
  try {
    const res = await fetch(`${API_BASE}/api/v1/drones/telemetry`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    const json = await res.json()
    if (json && json.code === 200) {
      pushLog('telemetry', '遥测上报成功', payload)
    } else {
      throw new Error(json?.msg || '上报失败')
    }
  } catch (e) {
    error.value = e.message || '上报失败'
    pushLog('error', '遥测上报失败', { error: error.value })
  } finally {
    busy.value = false
  }
}

function startTelemetryLoop() {
  error.value = ''
  if (telemetryLoop.running) return
  const ms = Number(telemetryLoop.intervalMs)
  if (Number.isNaN(ms) || ms < 50) { error.value = '间隔需 ≥ 50ms'; return }
  telemetryLoop.running = true
  telemetryTimer = setInterval(() => {
    sendTelemetryOnce()
  }, ms)
  pushLog('telemetry', '已开始连续上报', { intervalMs: ms })
}

function stopTelemetryLoop() {
  telemetryLoop.running = false
  if (telemetryTimer) clearInterval(telemetryTimer)
  telemetryTimer = null
  pushLog('telemetry', '已停止连续上报')
}

const canConnectWs = computed(() => {
  return !!WS_BASE && wsStatus.value !== 'connected' && wsStatus.value !== 'connecting'
})

function connectWs() {
  wsError.value = ''
  if (!WS_BASE) { wsError.value = '缺少 VITE_WS_BASE'; return }
  if (ws && (ws.readyState === 0 || ws.readyState === 1)) return

  wsStatus.value = 'connecting'
  try {
    ws = new WebSocket(WS_BASE)
  } catch (e) {
    wsStatus.value = 'disconnected'
    wsError.value = e.message || 'WebSocket 创建失败'
    return
  }

  ws.onopen = () => {
    wsStatus.value = 'connected'
    wsLastAt.value = nowText()
    pushLog('ws', 'WebSocket 已连接', { url: WS_BASE })
  }
  ws.onclose = () => {
    wsStatus.value = 'disconnected'
    wsLastAt.value = nowText()
    pushLog('ws', 'WebSocket 已断开')
  }
  ws.onerror = () => {
    wsStatus.value = 'error'
    wsLastAt.value = nowText()
    wsError.value = 'WebSocket 连接异常'
    pushLog('error', 'WebSocket 连接异常')
  }
  ws.onmessage = (evt) => {
    wsLastAt.value = nowText()
    const text = String(evt.data ?? '')
    try {
      const data = JSON.parse(text)
      if (data && data.type === 'new_defect') {
        pushLog('defect', '发现新病害告警', data)
      } else if (data && data.type === 'telemetry') {
        pushLog('ws', '收到遥测广播', data)
      } else {
        pushLog('ws', '收到消息', data)
      }
    } catch {
      pushLog('ws', '收到消息', text)
    }
  }
}

function disconnectWs() {
  if (ws) {
    try { ws.close() } catch {}
  }
  ws = null
  wsStatus.value = 'disconnected'
}

function clearLogs() {
  logs.value = []
}

const tasksEmpty = computed(() => (tasks.value || []).length === 0)
const devicesEmpty = computed(() => (devices.value || []).length === 0)

async function refreshMeta() {
  error.value = ''
  busy.value = true
  try {
    await Promise.all([loadDevices(), loadTasks()])
    pushLog('ws', '已刷新设备/任务', { tasks: tasks.value.length, devices: devices.value.length })
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  await refreshMeta()
})

onBeforeUnmount(() => {
  if (uploadPreview.value) URL.revokeObjectURL(uploadPreview.value)
  stopTelemetryLoop()
  disconnectWs()
})
</script>

<template>
  <div class="ingest">
    <div class="toolbar">
      <button @click="refreshMeta">刷新设备/任务</button>
      <button v-if="canConnectWs" @click="connectWs">连接 WebSocket</button>
      <button v-else @click="disconnectWs">断开 WebSocket</button>
      <span class="muted">WS: {{ wsStatus }}{{ wsLastAt ? (' · '+wsLastAt) : '' }}</span>
      <span v-if="wsError" class="error">{{ wsError }}</span>
      <span v-if="busy" class="muted">处理中…</span>
      <span v-if="error" class="error">{{ error }}</span>
    </div>

    <div class="grid">
      <div class="left">
        <div class="card">
          <div class="card-title">图片上传（/api/v1/drones/upload）</div>
          <div class="form">
            <label>任务
              <select v-model="upload.taskId" :disabled="tasksEmpty">
                <option value="" disabled>{{ tasksEmpty ? '暂无任务（请先在「任务」页创建）' : '请选择任务' }}</option>
                <option v-for="t in tasks" :key="t.id" :value="t.id">{{ t.id }} · {{ t.taskName }}</option>
              </select>
            </label>
            <label>无人机
              <select v-model="upload.droneId" :disabled="devicesEmpty">
                <option value="" disabled>{{ devicesEmpty ? '暂无无人机（请先在「设备」页创建）' : '请选择无人机' }}</option>
                <option v-for="d in devices" :key="d.id" :value="d.id">{{ d.id }} · {{ d.droneName }}</option>
              </select>
            </label>
            <div class="row">
              <label>经度
                <input type="number" step="0.000001" v-model="upload.lng" placeholder="-180~180" />
              </label>
              <label>纬度
                <input type="number" step="0.000001" v-model="upload.lat" placeholder="-90~90" />
              </label>
            </div>
            <label>图片文件
              <input type="file" accept="image/*" @change="onPickFile" />
            </label>
            <div v-if="uploadPreview" class="preview">
              <img :src="uploadPreview" alt="preview" />
            </div>
            <div class="actions">
              <button @click="submitUpload">上传</button>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-title">遥测上报（/api/v1/drones/telemetry）</div>
          <div class="form">
            <label>任务
              <select v-model="telemetry.taskId" :disabled="tasksEmpty">
                <option value="" disabled>{{ tasksEmpty ? '暂无任务（请先在「任务」页创建）' : '请选择任务' }}</option>
                <option v-for="t in tasks" :key="t.id" :value="t.id">{{ t.id }} · {{ t.taskName }}</option>
              </select>
            </label>
            <label>无人机
              <select v-model="telemetry.droneId" :disabled="devicesEmpty">
                <option value="" disabled>{{ devicesEmpty ? '暂无无人机（请先在「设备」页创建）' : '请选择无人机' }}</option>
                <option v-for="d in devices" :key="d.id" :value="d.id">{{ d.id }} · {{ d.droneName }}</option>
              </select>
            </label>
            <div class="row">
              <label>经度
                <input type="number" step="0.000001" v-model="telemetry.lng" placeholder="-180~180" />
              </label>
              <label>纬度
                <input type="number" step="0.000001" v-model="telemetry.lat" placeholder="-90~90" />
              </label>
            </div>
            <label>航向（可选）
              <input type="number" step="0.01" v-model="telemetry.heading" placeholder="0~360" />
            </label>
            <div class="actions">
              <button @click="sendTelemetryOnce">发送一次</button>
              <button v-if="!telemetryLoop.running" class="secondary" @click="startTelemetryLoop">连续上报</button>
              <button v-else class="danger" @click="stopTelemetryLoop">停止</button>
              <input class="num" type="number" v-model="telemetryLoop.intervalMs" min="50" step="50" />
              <span class="muted">ms</span>
            </div>
          </div>
        </div>
      </div>

      <div class="right">
        <div class="card">
          <div class="card-title">
            事件日志
            <button class="secondary" @click="clearLogs">清空</button>
          </div>
          <div class="log">
            <div v-if="logs.length===0" class="muted">暂无日志</div>
            <div v-for="(it, idx) in logs" :key="idx" class="log-item">
              <div class="log-head">
                <span class="time">{{ it.at }}</span>
                <span class="tag" :class="it.type">{{ it.type }}</span>
                <span class="msg">{{ it.message }}</span>
              </div>
              <pre v-if="it.payload !== undefined" class="payload">{{ typeof it.payload === 'string' ? it.payload : JSON.stringify(it.payload, null, 2) }}</pre>
              <div v-if="it.type==='defect' && it.payload?.data?.imageUrl" class="links">
                <a :href="it.payload.data.imageUrl" target="_blank" rel="noreferrer">打开结果图</a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ingest{display:flex;flex-direction:column;height:100%;padding:12px;box-sizing:border-box;color:#e5e7eb}
.toolbar{display:flex;gap:12px;align-items:center;margin-bottom:12px;flex-wrap:wrap}
.grid{flex:1;display:flex;gap:12px;min-height:0}
.left{flex:1;display:flex;flex-direction:column;gap:12px;min-height:0;overflow:auto}
.right{width:520px;min-width:360px;display:flex;min-height:0}
.card{background:#111827;border:1px solid #374151;border-radius:8px;padding:12px}
.card-title{display:flex;align-items:center;justify-content:space-between;font-weight:600;margin-bottom:10px}
.form label{display:flex;flex-direction:column;gap:6px;margin-bottom:10px}
.form input,.form select{padding:8px;background:#0b0f19;border:1px solid #374151;color:#e5e7eb;border-radius:4px}
.row{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:6px}
button{background:#2563eb;color:#fff;border:none;padding:6px 12px;cursor:pointer;border-radius:4px}
button.secondary{background:#1f2937;border:1px solid #334155}
button.danger{background:#ef4444}
.num{width:96px}
.muted{color:#9ca3af}
.error{color:#f87171}
.preview{margin-top:6px}
.preview img{max-width:100%;max-height:180px;border-radius:6px;border:1px solid #334155}
.log{height:100%;max-height:calc(100vh - 140px);overflow:auto;display:flex;flex-direction:column;gap:10px}
.log-item{border:1px solid #334155;border-radius:6px;padding:10px;background:#0b0f19}
.log-head{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.time{color:#9ca3af}
.tag{padding:2px 8px;border-radius:999px;border:1px solid #334155;background:#111827}
.tag.error{border-color:#ef4444;color:#fecaca}
.tag.defect{border-color:#f59e0b;color:#fde68a}
.tag.upload{border-color:#60a5fa;color:#bfdbfe}
.tag.telemetry{border-color:#34d399;color:#bbf7d0}
.payload{margin:8px 0 0;white-space:pre-wrap;color:#e5e7eb}
.links{margin-top:8px}
.links a{color:#93c5fd}
</style>
