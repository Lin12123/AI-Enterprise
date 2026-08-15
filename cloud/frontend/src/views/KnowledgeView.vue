<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { standardsApi, knowledgeApi } from '@/api'

const loading = ref(false)
const keyword = ref('')
const standards = ref([])

async function loadStandards() {
  loading.value = true
  try {
    standards.value = await standardsApi.list({ keyword: keyword.value })
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

// 导入表单
const form = ref({ standard_no: '', type: '', title: '', version: '', source: '' })
const fileRef = ref(null)
const importing = ref(false)

function onFileChange(file) {
  fileRef.value = file.raw
}

async function doImport() {
  if (!fileRef.value) {
    ElMessage.warning('请先选择文件')
    return
  }
  const fd = new FormData()
  fd.append('file', fileRef.value)
  Object.entries(form.value).forEach(([k, v]) => fd.append(k, v))
  importing.value = true
  try {
    const res = await knowledgeApi.import(fd)
    ElMessage.success(`导入成功，入库规则 ${res.inserted ?? 0} 条`)
    await loadStandards()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    importing.value = false
  }
}

onMounted(loadStandards)
</script>

<template>
  <el-tabs>
    <el-tab-pane label="标准列表">
      <div class="toolbar">
        <el-input v-model="keyword" placeholder="按标准号/标题搜索" clearable style="width: 240px" />
        <el-button type="primary" @click="loadStandards">查询</el-button>
      </div>
      <el-table :data="standards" v-loading="loading" border style="width: 100%">
        <el-table-column prop="standard_no" label="标准号" width="180" />
        <el-table-column prop="title" label="标题" />
        <el-table-column prop="type" label="类型" width="120" />
        <el-table-column prop="version" label="版本" width="120" />
        <el-table-column prop="status" label="状态" width="120" />
        <el-table-column prop="updated_at" label="更新时间" width="180" />
      </el-table>
    </el-tab-pane>

    <el-tab-pane label="导入知识">
      <el-form :model="form" label-width="90px" style="max-width: 520px">
        <el-form-item label="标准号">
          <el-input v-model="form.standard_no" />
        </el-form-item>
        <el-form-item label="类型">
          <el-input v-model="form.type" placeholder="如 国标/企标" />
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="form.title" />
        </el-form-item>
        <el-form-item label="版本">
          <el-input v-model="form.version" />
        </el-form-item>
        <el-form-item label="来源">
          <el-input v-model="form.source" />
        </el-form-item>
        <el-form-item label="文件">
          <el-upload :auto-upload="false" :limit="1" :on-change="onFileChange">
            <el-button>选择文件（Excel/JSON/Word/PDF/图片）</el-button>
          </el-upload>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="importing" @click="doImport">开始导入</el-button>
        </el-form-item>
      </el-form>
    </el-tab-pane>
  </el-tabs>
</template>

<style scoped>
.toolbar { display: flex; gap: 8px; margin-bottom: 12px; }
</style>