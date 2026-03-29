<script setup>
import { ref, reactive, onMounted } from 'vue'

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

const formVisible = ref(false)
const formMode = ref('create')
const form = reactive({
  id: null,
  taskName: '',
  droneId: '',
  routePointsText: '[]'
})

function openCreate() {
  formMode.value = 'create'
  Object.assign(form, { id: null, taskName: '', droneId: '', routePointsText: '[]' })
  formVisible.value = true
}

function openEdit(row) {
  formMode.value = 'edit'
  const rp = row.routePoints ? JSON.stringify(row.routePoints, null, 2) : '[]'
  Object.assign(form, {
    id: row.id,
    taskName: row.taskName || '',
    droneId: row.droneId || '',
    routePointsText: rp
  })
  formVisible.value = true
}

function parseRoutePoints(text) {
  try {
    const arr = JSON.parse(text)
    if (!Array.isArray(arr)) throw new Error('routePoints 必须是数组')
    for (const it of arr) {
      if (typeof it !== 'object' || it === null) throw new Error('每个点应为对象')
      const lng = Number(it.lng)
      const lat = Number(it.lat)
      if (Number.isNaN(lng) || Number.isNaN(lat)) throw new Error('点位需包含数值 lng/lat')
      if (lng < -180 || lng > 180) throw new Error('经度需在 -180~180')
      if (lat < -90 || lat > 90) throw new Error('纬度需在 -90~90')
    }
    return arr
  } catch (e) {
    throw new Error(e.message || 'routePoints 解析失败')
  }
}

async function submitForm() {
  error.value = ''
  if (!form.taskName.trim()) { error.value = '任务名称不能为空'; return }
  if (!form.droneId) { error.value = '请选择无人机'; return }
  let routePoints = []
  try {
    routePoints = parseRoutePoints(form.routePointsText)
  } catch (e) {
    error.value = e.message
    return
  }

  const payload = { taskName: form.taskName.trim(), droneId: Number(form.droneId), routePoints }
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
      formVisible.value = false
      await getList()
    } else {
      throw new Error(json?.msg || '保存失败')
    }
  } catch (e) {
    error.value = e.message || '请求失败'
  }
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

    <div class="table-wrap">
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

    <div v-if="formVisible" class="modal">
      <div class="dialog">
        <div class="dialog-title">{{ formMode === 'create' ? '新建任务' : '编辑任务' }}</div>
        <div class="dialog-body">
          <label>任务名称
            <input v-model="form.taskName" placeholder="请输入任务名称" />
          </label>
          <label>绑定无人机
            <select v-model="form.droneId">
              <option value="" disabled>请选择</option>
              <option v-for="d in devices" :key="d.id" :value="d.id">{{ d.droneName }}</option>
            </select>
          </label>
          <label>航线点位(JSON 数组，元素含 lng/lat)
            <textarea v-model="form.routePointsText" rows="8" placeholder='例如: [{"lng":116.39,"lat":39.90}]'></textarea>
          </label>
        </div>
        <div class="dialog-actions">
          <button @click="submitForm">保存</button>
          <button @click="formVisible=false">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tasks{display:flex;flex-direction:column;height:100%;padding:12px;box-sizing:border-box;color:#e5e7eb}
.toolbar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:12px}
.input,.select,.num,textarea{padding:8px;background:#0b0f19;border:1px solid #374151;color:#e5e7eb;border-radius:4px}
.num{width:120px}
button{background:#2563eb;color:#fff;border:none;padding:6px 12px;cursor:pointer;border-radius:4px}
button.danger{background:#ef4444}
.muted{color:#9ca3af;margin-left:8px}
.error{color:#f87171;margin-left:8px}
.table-wrap{flex:1;overflow:auto}
.table{width:100%;border-collapse:collapse}
.table th,.table td{border:1px solid #334155;padding:8px;vertical-align:top}
.table thead{background:#1f2937}
.ops button+button{margin-left:6px}
.modal{position:fixed;inset:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center}
.dialog{width:680px;max-width:90vw;background:#111827;border:1px solid #374151;border-radius:8px;padding:16px}
.dialog-title{font-weight:600;margin-bottom:12px}
.dialog-body label{display:flex;flex-direction:column;gap:6px;margin-bottom:12px}
.dialog-body input,.dialog-body select,textarea{font-family:inherit}
</style>