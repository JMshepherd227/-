<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, watch, computed } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE || ''

const loading = ref(false)
const error = ref('')
const tasks = ref([])
const devices = ref([])

const STATUS = { 0: '未开始', 1: '执行中', 2: '已完成' }
function statusText(s) { return STATUS[s] ?? '未开始' }

const filters = reactive({
  taskName: '',
  status: '',
  droneId: '',
  defectCountMin: '',
  defectCountMax: ''
})

async function loadDevices() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/devices`)
    const json = await res.json()
    if (json && json.code === 200) {
      devices.value = json.data || []
    }
  } catch {}
}

async function getList() {
  loading.value = true
  error.value = ''
  try {
    const p = new URLSearchParams()
    if (filters.taskName) p.append('taskName', filters.taskName)
    if (filters.status !== '' && filters.status !== null) p.append('status', String(filters.status))
    if (filters.droneId) p.append('droneId', String(filters.droneId))
    if (filters.defectCountMin !== '') p.append('defectCountMin', String(filters.defectCountMin))
    if (filters.defectCountMax !== '') p.append('defectCountMax', String(filters.defectCountMax))
    const url = `${API_BASE}/api/v1/tasks${p.toString() ? ('?'+p.toString()) : ''}`
    const res = await fetch(url)
    const json = await res.json()
    if (json && json.code === 200) {
      tasks.value = json.data || []
    } else {
      throw new Error(json?.msg || '获取失败')
    }
  } catch (e) {
    error.value = e.message || '请求失败'
  } finally {
    loading.value = false
  }
}

const panelMode = ref('list')
const pickingEnabled = ref(false)
const routePoints = ref([])
const plannedRoutePoints = ref([])
const draggingRouteIndex = ref(-1)
const dragOverRouteIndex = ref(-1)
const formMode = ref('create')
const form = reactive({
  id: null,
  taskName: '',
  droneId: ''
})

const panelTitle = computed(() => {
  if (panelMode.value === 'view') return '查看任务'
  return formMode.value === 'create' ? '新建任务' : '编辑任务'
})

function normalizeRoutePoints(list) {
  const points = Array.isArray(list) ? list : []
  return points.map(p => ({
    lng: Number(p.lng),
    lat: Number(p.lat),
    address: String(p.address || '')
  })).filter(p => !Number.isNaN(p.lng) && !Number.isNaN(p.lat))
}

function normalizeUploadRoutePoints(list) {
  return normalizeRoutePoints(list).map(({ lng, lat }) => ({ lng, lat }))
}

function emitEditableRoute() {
  const pts = routePoints.value.map(p => [Number(p.lng), Number(p.lat)]).filter(a => !Number.isNaN(a[0]) && !Number.isNaN(a[1]))
  window.dispatchEvent(new CustomEvent('route-points-update', { detail: pts }))
}

function showReadonlyRoute(points) {
  const pts = normalizeRoutePoints(points).map(p => [p.lng, p.lat])
  window.dispatchEvent(new CustomEvent('route-points-clear'))
  window.dispatchEvent(new CustomEvent('route-original-set', { detail: pts }))
}

function hideAllRoutes() {
  window.dispatchEvent(new CustomEvent('route-picking-toggle', { detail: false }))
  window.dispatchEvent(new CustomEvent('route-points-clear'))
  window.dispatchEvent(new CustomEvent('route-original-set', { detail: [] }))
}

function closePanel() {
  panelMode.value = 'list'
  pickingEnabled.value = false
  routePoints.value = []
  plannedRoutePoints.value = []
  resetRouteDragState()
  hideAllRoutes()
}

function openCreate() {
  formMode.value = 'create'
  Object.assign(form, { id: null, taskName: '', droneId: '' })
  routePoints.value = []
  pickingEnabled.value = false
  plannedRoutePoints.value = []
  resetRouteDragState()
  hideAllRoutes()
  panelMode.value = 'form'
}

function openEdit(row) {
  formMode.value = 'edit'
  routePoints.value = normalizeRoutePoints(row.routePoints)
  hideAllRoutes()
  Object.assign(form, {
    id: row.id,
    taskName: row.taskName || '',
    droneId: row.droneId || ''
  })
  pickingEnabled.value = false
  plannedRoutePoints.value = []
  resetRouteDragState()
  panelMode.value = 'form'
}

function openView(row) {
  routePoints.value = normalizeRoutePoints(row.routePoints)
  Object.assign(form, {
    id: row.id,
    taskName: row.taskName || '',
    droneId: row.droneId || ''
  })
  pickingEnabled.value = false
  plannedRoutePoints.value = []
  resetRouteDragState()
  panelMode.value = 'view'
  showReadonlyRoute(routePoints.value)
}


async function submitForm() {
  error.value = ''
  if (!form.taskName.trim()) { error.value = '任务名称不能为空'; return }
  if (!form.droneId) { error.value = '请选择无人机'; return }
  const uploadRoutePoints = plannedRoutePoints.value.length >= 2
    ? normalizeUploadRoutePoints(plannedRoutePoints.value)
    : normalizeUploadRoutePoints(routePoints.value)
  const payload = { taskName: form.taskName.trim(), droneId: Number(form.droneId), routePoints: uploadRoutePoints }
  try {
    let url, method
    if (formMode.value === 'create') {
      url = `${API_BASE}/api/v1/tasks`
      method = 'POST'
    } else {
      url = `${API_BASE}/api/v1/tasks/${form.id}`
      method = 'PUT'
    }
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    const json = await res.json()
    if (json && json.code === 200) {
      closePanel()
      await getList()
    } else {
      throw new Error(json?.msg || '保存失败')
    }
  } catch (e) {
    error.value = e.message || '请求失败'
  }
}

function startPicking() {
  pickingEnabled.value = true
  window.dispatchEvent(new CustomEvent('route-picking-toggle', { detail: true }))
}
function stopPicking() {
  pickingEnabled.value = false
  window.dispatchEvent(new CustomEvent('route-picking-toggle', { detail: false }))
}
function clearRoutePoints() {
  routePoints.value = []
  plannedRoutePoints.value = []
  resetRouteDragState()
  window.dispatchEvent(new CustomEvent('route-points-clear'))
}

function removeRoutePoint(index) {
  if (panelMode.value !== 'form') return
  if (index < 0 || index >= routePoints.value.length) return
  routePoints.value.splice(index, 1)
  resetRouteDragState()
}

function resetRouteDragState() {
  draggingRouteIndex.value = -1
  dragOverRouteIndex.value = -1
}

function handleRouteDragStart(index, event) {
  if (panelMode.value !== 'form') return
  draggingRouteIndex.value = index
  dragOverRouteIndex.value = index
  if (event?.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', String(index))
  }
}

function handleRouteDragOver(index, event) {
  if (panelMode.value !== 'form' || draggingRouteIndex.value < 0) return
  event.preventDefault()
  if (dragOverRouteIndex.value !== index) {
    dragOverRouteIndex.value = index
  }
  if (event?.dataTransfer) {
    event.dataTransfer.dropEffect = 'move'
  }
}

function handleRouteDrop(index, event) {
  if (panelMode.value !== 'form') return
  event.preventDefault()
  const fromIndex = draggingRouteIndex.value
  const toIndex = index
  if (fromIndex < 0 || toIndex < 0 || fromIndex === toIndex || fromIndex >= routePoints.value.length || toIndex >= routePoints.value.length) {
    resetRouteDragState()
    return
  }
  const next = routePoints.value.slice()
  const [moved] = next.splice(fromIndex, 1)
  next.splice(toIndex, 0, moved)
  routePoints.value = next
  resetRouteDragState()
}

function handleRouteDragEnd() {
  resetRouteDragState()
}

async function startTask(row) {
  try {
    const res = await fetch(`${API_BASE}/api/v1/tasks/${row.id}/start`, { method: 'PUT' })
    const json = await res.json()
    if (json && json.code === 200) {
      await getList()
    } else {
      throw new Error(json?.msg || '启动失败')
    }
  } catch (e) {
    error.value = e.message || '请求失败'
  }
}

async function finishTask(row) {
  if (!row.droneId) { error.value = '该任务缺少无人机ID，无法结束'; return }
  try {
    const res = await fetch(`${API_BASE}/api/v1/tasks/${row.droneId}/finish`, { method: 'PUT' })
    const json = await res.json()
    if (json && json.code === 200) {
      await getList()
    } else {
      throw new Error(json?.msg || '结束失败')
    }
  } catch (e) {
    error.value = e.message || '请求失败'
  }
}

async function removeTask(row) {
  if (!confirm('确认删除该任务吗？')) return
  try {
    const res = await fetch(`${API_BASE}/api/v1/tasks/${row.id}`, { method: 'DELETE' })
    const json = await res.json()
    if (json && json.code === 200) {
      await getList()
    } else {
      throw new Error(json?.msg || '删除失败')
    }
  } catch (e) {
    error.value = e.message || '请求失败'
  }
}

onMounted(async () => {
  await loadDevices()
  await getList()
  window.addEventListener('route-point-picked', handleRoutePointPicked)
  window.addEventListener('route-planned-path-update', handlePlannedRouteUpdated)
})

function handleRoutePointPicked(evt) {
  if (panelMode.value !== 'form' || !pickingEnabled.value) return
  try {
    const d = evt.detail || {}
    const lng = Number(d.lng), lat = Number(d.lat)
    const address = String(d.address || '')
    if (!Number.isNaN(lng) && !Number.isNaN(lat)) {
      routePoints.value.push({ lng, lat, address })
    }
  } catch {}
}

function handlePlannedRouteUpdated(evt) {
  if (panelMode.value !== 'form') return
  plannedRoutePoints.value = normalizeUploadRoutePoints(evt?.detail)
}

watch(routePoints, (list) => {
  if (panelMode.value === 'form') {
    emitEditableRoute()
    return
  }
  if (panelMode.value === 'view') {
    showReadonlyRoute(list)
  }
}, { deep: true })

watch(panelMode, (mode) => {
  if (mode === 'form') {
    window.dispatchEvent(new CustomEvent('route-original-set', { detail: [] }))
    emitEditableRoute()
    return
  }
  if (mode === 'view') {
    showReadonlyRoute(routePoints.value)
    return
  }
  hideAllRoutes()
})

onBeforeUnmount(() => {
  window.removeEventListener('route-point-picked', handleRoutePointPicked)
  window.removeEventListener('route-planned-path-update', handlePlannedRouteUpdated)
  hideAllRoutes()
})
</script>

<template>
  <div class="tasks">
    <div class="toolbar">
      <input class="input" v-model="filters.taskName" placeholder="任务名称(模糊)" />
      <select class="select" v-model="filters.status">
        <option value="">全部状态</option>
        <option :value="0">未开始</option>
        <option :value="1">执行中</option>
        <option :value="2">已完成</option>
      </select>
      <select class="select" v-model="filters.droneId">
        <option value="">全部无人机</option>
        <option v-for="d in devices" :key="d.id" :value="d.id">{{ d.droneName }}</option>
      </select>
      <input class="num" type="number" v-model="filters.defectCountMin" placeholder="病害数≥" />
      <input class="num" type="number" v-model="filters.defectCountMax" placeholder="病害数≤" />
      <button @click="getList">查询</button>
      <button @click="openCreate">新建任务</button>
      <span v-if="loading" class="muted">加载中…</span>
      <span v-if="error" class="error">{{ error }}</span>
    </div>

    <div class="table-wrap" v-if="panelMode==='list'">
      <table class="table">
        <thead>
          <tr>
            <th>ID</th>
            <th>任务名称</th>
            <th>无人机</th>
            <th>状态</th>
            <th>病害数</th>
            <th>创建时间</th>
            <th>更新时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in tasks" :key="t.id">
            <td>{{ t.id }}</td>
            <td>{{ t.taskName }}</td>
            <td>{{ t.droneId }}</td>
            <td>{{ statusText(t.status) }}</td>
            <td>{{ t.defectCount ?? 0 }}</td>
            <td>{{ t.createTime ?? '-' }}</td>
            <td>{{ t.updateTime ?? '-' }}</td>
            <td class="ops">
              <button class="secondary" @click="openView(t)">查看</button>
              <button v-if="t.status===0" @click="startTask(t)">启动</button>
              <button v-if="t.status===1" @click="finishTask(t)">结束</button>
              <button @click="openEdit(t)">编辑</button>
              <button class="danger" @click="removeTask(t)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!loading && tasks.length===0" class="muted">暂无任务</div>
    </div>

    <div v-if="panelMode==='form' || panelMode==='view'" class="panel-form">
      <div class="dialog">
        <div class="dialog-title">{{ panelTitle }}</div>
        <div class="dialog-body">
          <label>任务名称
            <input v-model="form.taskName" placeholder="请输入任务名称" :disabled="panelMode==='view'" />
          </label>
          <label>绑定无人机
            <select v-model="form.droneId" :disabled="panelMode==='view'">
              <option value="" disabled>请选择</option>
              <option v-for="d in devices" :key="d.id" :value="d.id">{{ d.droneName }}</option>
            </select>
          </label>
          <div>
            <div class="detail-title">航线点位</div>
            <div class="muted">{{ panelMode==='view' ? '当前任务规划轨迹' : '在地图上点击选点，自动识别地址' }}</div>
            <table class="table" v-if="routePoints.length">
              <thead>
                <tr>
                  <th>#</th>
                  <th>经度</th>
                  <th>纬度</th>
                  <th>地址</th>
                  <th v-if="panelMode==='form'">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(p,i) in routePoints"
                  :key="i"
                  :draggable="panelMode==='form'"
                  :class="{ dragging: panelMode==='form' && draggingRouteIndex===i, 'drag-over': panelMode==='form' && dragOverRouteIndex===i && draggingRouteIndex!==i }"
                  @dragstart="handleRouteDragStart(i, $event)"
                  @dragover="handleRouteDragOver(i, $event)"
                  @drop="handleRouteDrop(i, $event)"
                  @dragend="handleRouteDragEnd"
                >
                  <td>{{ i+1 }}</td>
                  <td>{{ p.lng }}</td>
                  <td>{{ p.lat }}</td>
                  <td>{{ p.address || '-' }}</td>
                  <td v-if="panelMode==='form'">
                    <button class="danger" @click="removeRoutePoint(i)">删除</button>
                  </td>
                </tr>
              </tbody>
            </table>
            <div v-if="panelMode==='form'" class="dialog-actions">
              <button @click="startPicking" v-if="!pickingEnabled">开始选点</button>
              <button @click="stopPicking" v-else>停止选点</button>
              <button class="secondary" @click="clearRoutePoints">清空点位</button>
            </div>
          </div>
        </div>
        <div class="dialog-actions">
          <button v-if="panelMode==='form'" @click="submitForm">保存</button>
          <button class="secondary" @click="closePanel()">{{ panelMode==='view' ? '关闭' : '取消' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tasks{display:flex;flex-direction:column;height:100%;padding:12px;box-sizing:border-box;color:#e5e7eb}
.toolbar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:12px;background:rgba(17,24,39,0.9);border:1px solid #374151;border-radius:8px;padding:8px}
.input,.select,.num,textarea{padding:8px;background:#0b0f19;border:1px solid #374151;color:#e5e7eb;border-radius:6px}
.num{width:120px}
button{background:#2563eb;color:#fff;border:none;padding:6px 12px;cursor:pointer;border-radius:6px}
button.danger{background:#ef4444}
.muted{color:#9ca3af;margin-left:8px}
.error{color:#f87171;margin-left:8px}
.table-wrap{flex:1;overflow:auto}
.table{width:100%;border-collapse:collapse}
.table th,.table td{border:1px solid #334155;padding:8px;vertical-align:top}
.table thead{background:#1f2937}
.table tbody tr:nth-child(odd){background:#0b0f19}
.table tbody tr:hover{background:#0f172a}
.table tbody tr[draggable="true"]{cursor:move}
.table tbody tr.dragging{opacity:0.55}
.table tbody tr.drag-over td{background:rgba(37,99,235,0.2)}
.ops button+button{margin-left:6px}
.panel-form .dialog{width:auto;max-width:none;background:transparent;border:none;border-radius:0;padding:0}
.dialog-title{font-weight:600;margin-bottom:12px}
.dialog-body label{display:flex;flex-direction:column;gap:6px;margin-bottom:12px}
.dialog-body input,.dialog-body select,textarea{font-family:inherit}
</style>
