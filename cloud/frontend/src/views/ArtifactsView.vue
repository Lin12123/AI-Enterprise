<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { tasksApi, filesApi } from '@/api'

const loading = ref(false)
const tasks = ref([])

const drawerVisible = ref(false)
const currentTask = ref(null)
const files = ref([])

async function loadTasks() {
  loading.value = true
  try {
    tasks.value = await tasksApi.list()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function openTask(row) {
  currentTask.value = row
  drawerVisible.value = true
  files.value = []
  try {
    files.value = await filesApi.list({ task_id: row.id })
  } catch (e) {
    ElMessage.error(e.message)
  }
}

function download(row) {
  window.open(filesApi.downloadUrl(row.id), '_blank')
}

onMounted(loadTasks)
</script>

<template>
  <el-table :data="tasks" v-loading="loading" border style="width: 100%">
    <el-table-column prop="task_uid" label="任务号" width="200" />
    <el-table-column prop="title" label="标题" />
    <el-table-column prop="part_name" label="零件" width="160" />
    <el-table-column prop="material" label="材料" width="120" />
    <el-table-column prop="status" label="状态" width="120" />
    <el-table-column label="操作" width="120">
      <template #default="{ row }">
        <el-button link type="primary" @click="openTask(row)">产物</el-button>
      </template>
    </el-table-column>
  </el-table>

  <el-drawer v-model="drawerVisible" :title="currentTask?.title || '产物列表'" size="50%">
    <el-table :data="files" border style="width: 100%">
      <el-table-column prop="file_name" label="文件名" />
      <el-table-column prop="file_type" label="类型" width="120" />
      <el-table-column prop="size_bytes" label="大小(B)" width="120" />
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button link type="primary" @click="download(row)">下载</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-drawer>
</template>