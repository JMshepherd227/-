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

const uploadPreview = ref('')

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
  disconnectWs()
})
</script>

<template>
  <div class="ingest">
    <div class="toolbar">
      <button @click="refreshMeta">刷新设备/任务</button>
      <button v-if="canConnectWs" @click="connectWs">连接 WebSocket</button>
      <button v-else @click="disconnectWs">断开 WebSocket</button>
      <button class="secondary" @click="clearLogs">清空日志</button>
      <span class="muted">WS: {{ wsStatus }}{{ wsLastAt ? (' · '+wsLastAt) : '' }}</span>
      <span v-if="wsError" class="error">{{ wsError }}</span>
      <span v-if="busy" class="muted">处理中…</span>
      <span v-if="error" class="error">{{ error }}</span>
    </div>

    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th width="100">时间</th>
            <th width="100">类型</th>
            <th>消息</th>
            <th>详情 / 操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(it, idx) in logs" :key="idx">
            <td class="time">{{ it.at }}</td>
            <td><span class="tag" :class="it.type">{{ it.type }}</span></td>
            <td class="msg">{{ it.message }}</td>
            <td>
              <div class="detail-cell">
                <pre v-if="it.payload !== undefined" class="payload-mini">{{ typeof it.payload === 'string' ? it.payload : JSON.stringify(it.payload) }}</pre>
                <div v-if="it.type==='defect' && it.payload?.data?.imageUrl" class="links">
                  <a :href="it.payload.data.imageUrl" target="_blank" rel="noreferrer">查看结果图</a>
                </div>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="logs.length===0" class="empty-hint">暂无实时事件日志数据</div>
    </div>
  </div>
</template>

<style scoped>
.ingest{display:flex;flex-direction:column;height:100%;padding:12px;box-sizing:border-box;color:#e5e7eb}
.toolbar{display:flex;gap:12px;align-items:center;margin-bottom:12px;background:rgba(17,24,39,0.9);border:1px solid #374151;border-radius:8px;padding:8px}
.table-wrap{flex:1;overflow:auto;background:rgba(17,24,39,0.4);border:1px solid #374151;border-radius:8px}
.table{width:100%;border-collapse:collapse;table-layout:fixed}
.table th,.table td{border:1px solid #334155;padding:10px;text-align:left;font-size:13px;word-break:break-all}
.table th{background:#1f2937;color:#9ca3af;font-weight:600;position:sticky;top:0;z-index:10}
.table tbody tr:nth-child(odd){background:rgba(11,15,25,0.5)}
.table tbody tr:hover{background:rgba(37,99,235,0.1)}

.time{color:#9ca3af;font-family:monospace}
.tag{padding:2px 8px;border-radius:999px;border:1px solid #334155;background:#111827;font-size:11px;text-transform:uppercase}
.tag.error{border-color:#ef4444;color:#fecaca}
.tag.defect{border-color:#f59e0b;color:#fde68a}
.tag.upload{border-color:#60a5fa;color:#bfdbfe}
.tag.telemetry{border-color:#34d399;color:#bbf7d0}
.tag.ws{border-color:#8b5cf6;color:#ddd6fe}

.detail-cell{display:flex;flex-direction:column;gap:6px}
.payload-mini{margin:0;white-space:pre-wrap;color:#9ca3af;font-size:11px;max-height:60px;overflow:auto;background:rgba(0,0,0,0.2);padding:4px;border-radius:4px}

.empty-hint{padding:40px;text-align:center;color:#6b7280;font-size:14px}
.links a{color:#3b82f6;text-decoration:none;font-size:12px}
.links a:hover{text-decoration:underline}

button{background:#2563eb;color:#fff;border:none;padding:6px 14px;cursor:pointer;border-radius:6px;font-size:13px;transition:all 0.2s}
button:hover{background:#1d4ed8}
button.secondary{background:#1f2937;border:1px solid #334155;color:#e5e7eb}
button.secondary:hover{background:#374151}

.muted{color:#9ca3af;font-size:12px}
.error{color:#f87171;font-size:12px}
</style>
