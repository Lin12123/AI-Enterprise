<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { projectsApi } from '@/api'

const loading = ref(false)
const keyword = ref('')
const statusFilter = ref('all')
const projects = ref([])

async function load() {
  loading.value = true
  try {
    projects.value = await projectsApi.list()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

const filtered = computed(() =>
  projects.value.filter((p) => {
    const kw = keyword.value.trim()
    const matchKw = !kw || p.id.includes(kw) || p.name.includes(kw)
    const matchStatus =
      statusFilter.value === 'all' ||
      (statusFilter.value === 'on' && p.enabled) ||
      (statusFilter.value === 'off' && !p.enabled)
    return matchKw && matchStatus
  }),
)

function toggle(p) {
  p.enabled = !p.enabled
  ElMessage.success(`已${p.enabled ? '启用' : '禁用'}项目 ${p.id}`)
}

function addProject() {
  ElMessage.info('新增项目功能待接入后端')
}

onMounted(load)
</script>

<template>
  <div>
    <div class="tf-page-head">
      <div>
        <h2 class="tf-page-title">项目图纸管理</h2>
        <div class="tf-page-desc">管理各协同项目的图纸集合、成员与启用状态</div>
      </div>
      <el-button type="primary" @click="addProject">+ 新增项目</el-button>
    </div>

    <div class="tf-toolbar">
      <el-input v-model="keyword" placeholder="按编号/名称搜索" clearable style="width: 260px" />
      <el-select v-model="statusFilter" style="width: 140px">
        <el-option label="全部状态" value="all" />
        <el-option label="启用中" value="on" />
        <el-option label="已禁用" value="off" />
      </el-select>
    </div>

    <div v-loading="loading" class="tf-grid tf-grid-3">
      <div v-for="p in filtered" :key="p.id" class="tf-card prj-card">
        <div class="prj-head">
          <span class="prj-id">{{ p.id }}</span>
          <el-tag :type="p.enabled ? 'success' : 'info'" size="small">
            {{ p.enabled ? '启用中' : '已禁用' }}
          </el-tag>
        </div>
        <div class="prj-name">{{ p.name }}</div>
        <div class="prj-desc">{{ p.desc }}</div>
        <div class="prj-meta">
          <span>📄 {{ p.drawings }} 张图纸</span>
          <span>👥 {{ p.members }} 人成员</span>
        </div>
        <div class="prj-time">更新于 {{ p.updatedAt }}</div>
        <div class="prj-actions">
          <el-button size="small" @click="toggle(p)">
            {{ p.enabled ? '禁用' : '启用' }}
          </el-button>
          <el-button size="small" type="primary" plain>查看详情</el-button>
        </div>
      </div>

      <el-empty v-if="!loading && filtered.length === 0" description="没有匹配的项目" />
    </div>
  </div>
</template>

<style scoped>
.prj-card { display: flex; flex-direction: column; }
.prj-head { display: flex; align-items: center; justify-content: space-between; }
.prj-id { font-size: 13px; color: #6366f1; font-weight: 600; }
.prj-name { font-size: 17px; font-weight: 700; margin: 10px 0 6px; }
.prj-desc { font-size: 13px; color: #64748b; line-height: 1.5; min-height: 40px; }
.prj-meta { display: flex; gap: 16px; font-size: 13px; color: #475569; margin: 12px 0 6px; }
.prj-time { font-size: 12px; color: #94a3b8; }
.prj-actions { display: flex; gap: 8px; margin-top: 16px; }
</style>