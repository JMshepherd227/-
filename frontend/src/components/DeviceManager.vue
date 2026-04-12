<script setup>
import { ref, reactive, onMounted } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE || ''

const loading = ref(false)
const list = ref([])
const error = ref('')

const STATUS = { 0: '空闲', 1: '任务中', 2: '维护中' }
function statusText(s) { return STATUS[s] ?? '空闲' }

async function getList() {
  loading.value = true
  try {
    const res = await fetch(`${API_BASE}/api/v1/devices`)
    const json = await res.json()
    if (json && json.code === 200) {
      list.value = json.data || []
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
const form = reactive({ id: null, droneName: '' })

function openCreate() {
  formMode.value = 'create'
  Object.assign(form, { id: null, droneName: '' })
  formVisible.value = true
}
function openEdit(item) {
  formMode.value = 'edit'
  Object.assign(form, {
    id: item.id,
    droneName: item.droneName || ''
  })
  formVisible.value = true
}

async function submitForm() {
  if (!validateForm()) return
  const payload = {
    droneName: (form.droneName || '').trim(),
    status: 0
  }
  try {
    let url, method
    if (formMode.value === 'create') {
      url = `${API_BASE}/api/v1/devices`
      method = 'POST'
    } else {
      url = `${API_BASE}/api/v1/devices/${form.id}`
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

function validateForm() {
  const name = (form.droneName || '').trim()
  if (!name) { error.value = '名称不能为空'; return false }
  return true
}

async function removeDevice(id) {
  if (!confirm('确认删除该无人机吗？')) return
  try {
    const res = await fetch(`${API_BASE}/api/v1/devices/${id}`, { method: 'DELETE' })
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

onMounted(getList)
</script>

<template>
  <div class="devices">
    <div class="toolbar">
      <button @click="openCreate">新增无人机</button>
      <button @click="getList">刷新</button>
      <span v-if="loading" class="muted">加载中…</span>
      <span v-if="error" class="error">{{ error }}</span>
    </div>

    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th>ID</th>
            <th>名称</th>
            <th>状态</th>
            <th>创建时间</th>
            <th>更新时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in list" :key="d.id">
            <td>{{ d.id }}</td>
            <td>{{ d.droneName }}</td>
            <td>{{ statusText(d.status) }}</td>
            <td>{{ d.createTime ?? '-' }}</td>
            <td>{{ d.updateTime ?? '-' }}</td>
            <td>
              <button @click="openEdit(d)">编辑</button>
              <button class="danger" @click="removeDevice(d.id)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!loading && list.length===0" class="muted">暂无数据</div>
    </div>

    <div v-if="formVisible" class="modal">
      <div class="dialog">
        <div class="dialog-title">{{ formMode === 'create' ? '新增无人机' : '编辑无人机' }}</div>
        <div class="dialog-body">
          <label>名称
            <input v-model="form.droneName" placeholder="请输入无人机名称" />
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
.devices{display:flex;flex-direction:column;height:100%;padding:12px;box-sizing:border-box;color:#e5e7eb}
.toolbar{display:flex;gap:10px;align-items:center;margin-bottom:12px;background:rgba(17,24,39,0.9);border:1px solid #374151;border-radius:8px;padding:8px}
.table-wrap{flex:1;overflow:auto}
.table{width:100%;border-collapse:collapse}
.table th,.table td{border:1px solid #334155;padding:8px}
.table thead{background:#1f2937}
.table tbody tr:nth-child(odd){background:#0b0f19}
.table tbody tr:hover{background:#0f172a}
button{background:#2563eb;color:#fff;border:none;padding:6px 12px;cursor:pointer;border-radius:6px}
button.danger{background:#ef4444}
.muted{color:#9ca3af;margin-left:8px}
.error{color:#f87171;margin-left:8px}
.modal{position:fixed;inset:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center}
.dialog{width:420px;background:#111827;border:1px solid #374151;border-radius:10px;padding:16px}
.dialog-title{font-weight:600;margin-bottom:12px}
.dialog-body label{display:flex;flex-direction:column;gap:6px;margin-bottom:12px}
.dialog-body input,.dialog-body select{padding:8px;background:#0b0f19;border:1px solid #374151;color:#e5e7eb;border-radius:6px}
.dialog-actions{display:flex;justify-content:flex-end;gap:8px}
</style>