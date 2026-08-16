<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
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

// ---------- 项目详情弹窗 ----------
const detailVisible = ref(false)
const detailLoading = ref(false)
const current = ref(null)
const memberList = ref([])
const drawingList = ref([])

const statusTagType = (s) => {
  if (s === '已审批') return 'success'
  if (s === '未审批') return 'warning'
  return 'info'
}

async function openDetail(p) {
  current.value = p
  detailVisible.value = true
  detailLoading.value = true
  memberList.value = []
  drawingList.value = []
  try {
    const data = await projectsApi.detail(p)
    current.value = data.project || p
    memberList.value = data.members || []
    drawingList.value = data.drawings || []
  } catch (e) {
    ElMessage.error(e.message || '加载详情失败')
  } finally {
    detailLoading.value = false
  }
}

function removeMember(m) {
  memberList.value = memberList.value.filter((x) => x.id !== m.id)
  ElMessage.success(`已移除成员 ${m.name}`)
}

function addMember() {
  ElMessage.info('添加成员功能待接入后端')
}

function uploadDrawing() {
  ElMessage.info('上传图纸功能待接入后端')
}

function downloadDrawing(d) {
  ElMessage.info(`下载 ${d.name}（待接入后端）`)
}

function approveDrawing(d) {
  ElMessage.success(`已提交审批操作：${d.name}`)
}

function removeDrawing(d) {
  drawingList.value = drawingList.value.filter((x) => x.id !== d.id)
  ElMessage.success(`已删除图纸 ${d.name}`)
}

async function removeProject(p) {
  try {
    await ElMessageBox.confirm(
      `确定要删除项目「${p.name}」吗？该操作会一并删除其名下的所有产物图纸文件，且不可恢复。`,
      '删除项目',
      {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        confirmButtonClass: 'el-button--danger',
      },
    )
  } catch {
    return // 用户取消
  }
  if (!p.tid) {
    ElMessage.warning('该项目暂无可删除的后端记录')
    return
  }
  try {
    await projectsApi.remove(p.tid)
    ElMessage.success(`已删除项目 ${p.id}`)
    await load()
  } catch (e) {
    ElMessage.error(e.message || '删除失败')
  }
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
          <el-button size="small" type="danger" plain @click="removeProject(p)">删除</el-button>
          <el-button size="small" type="primary" plain @click="openDetail(p)">查看详情</el-button>
        </div>
      </div>

      <el-empty v-if="!loading && filtered.length === 0" description="没有匹配的项目" />
    </div>

    <!-- 项目详情弹窗：项目头 + 成员管理 + 图纸管理 -->
    <el-dialog
      v-model="detailVisible"
      width="1120px"
      top="6vh"
      :destroy-on-close="true"
      class="prj-detail-dialog"
    >
      <template #header>
        <div class="dlg-head">
          <span class="dlg-title">{{ current?.name || '项目详情' }}</span>
          <el-tag size="small" type="primary" effect="plain">{{ current?.id }}</el-tag>
          <el-tag size="small" :type="current?.enabled ? 'success' : 'info'">
            {{ current?.enabled ? '启用中' : '已禁用' }}
          </el-tag>
        </div>
        <div class="dlg-sub">{{ current?.desc || '暂无项目描述' }}</div>
      </template>

      <div v-loading="detailLoading">
        <!-- 成员管理 -->
        <div class="sec-head">
          <span class="sec-title">成员管理</span>
          <el-button size="small" type="primary" plain @click="addMember">+ 添加项目成员</el-button>
        </div>
        <div class="member-grid">
          <div v-for="m in memberList" :key="m.id" class="member-card">
            <div class="member-main">
              <div class="member-name">{{ m.name }}</div>
              <div class="member-role">{{ m.role }}</div>
              <div class="member-email">{{ m.email }}</div>
            </div>
            <el-button
              class="member-del"
              size="small"
              type="danger"
              text
              @click="removeMember(m)"
            >移除</el-button>
          </div>
          <el-empty v-if="memberList.length === 0" description="暂无成员" :image-size="60" />
        </div>

        <!-- 图纸管理 -->
        <div class="sec-head" style="margin-top: 18px">
          <span class="sec-title">图纸管理</span>
          <el-button size="small" type="primary" @click="uploadDrawing">+ 上传 / 新增图纸</el-button>
        </div>
     <el-table :data="drawingList" size="small" border stripe style="width: 100%">
          <el-table-column prop="code" label="图号" min-width="150" />
          <el-table-column label="图纸名称" min-width="220">
            <template #default="{ row }">
              <div class="dwg-name">{{ row.name }}</div>
              <div class="dwg-desc">{{ row.desc }}</div>
            </template>
          </el-table-column>
          <el-table-column prop="version" label="版本" width="80" align="center" />
          <el-table-column label="状态" width="100" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="statusTagType(row.status)">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="类型 / 大小" width="130" align="center">
            <template #default="{ row }">
              <el-tag size="small" effect="plain">{{ row.fileType }}</el-tag>
              <div class="dwg-size">{{ row.size }}</div>
            </template>
          </el-table-column>
          <el-table-column label="更新人 / 时间" min-width="170">
            <template #default="{ row }">
              <div>{{ row.updatedBy }}</div>
              <div class="dwg-time">{{ row.updatedAt }}</div>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200" align="center">
            <template #default="{ row }">
              <el-button size="small" text type="primary" @click="downloadDrawing(row)">下载</el-button>
              <el-button size="small" text type="warning" @click="approveDrawing(row)">
                {{ row.status === '未审批' ? '进行审批' : '发起审批' }}
              </el-button>
              <el-button size="small" text type="danger" @click="removeDrawing(row)">删除</el-button>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty description="该项目暂无图纸" :image-size="60" />
          </template>
        </el-table>
      </div>

      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
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

/* ---- 详情弹窗 ---- */
.dlg-head { display: flex; align-items: center; gap: 10px; }
.dlg-title { font-size: 18px; font-weight: 700; }
.dlg-sub { font-size: 13px; color: #64748b; margin-top: 6px; }
.sec-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.sec-title { font-size: 15px; font-weight: 600; }
.member-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.member-card {
  display: flex; align-items: flex-start; justify-content: space-between;
  border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px 12px; background: #f8fafc;
}
.member-name { font-weight: 600; font-size: 14px; }
.member-role { font-size: 12px; color: #6366f1; margin: 2px 0; }
.member-email { font-size: 12px; color: #94a3b8; }
.dwg-name { font-weight: 600; }
.dwg-desc { font-size: 12px; color: #94a3b8; }
.dwg-size { font-size: 12px; color: #94a3b8; margin-top: 2px; }
.dwg-time { font-size: 12px; color: #94a3b8; }
</style>