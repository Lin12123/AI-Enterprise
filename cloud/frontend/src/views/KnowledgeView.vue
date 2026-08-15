<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { standardsApi, knowledgeApi } from '@/api'
import { knowledgeCategories } from '@/api/mock'

const categories = knowledgeCategories
const activeCat = ref('industry')
const loading = ref(false)
const keyword = ref('')
const statusFilter = ref('all')
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

// 分类匹配：优先用后端 category 字段，缺省时用 standard_type 兜底匹配。
// 企业/标准件优先判定，剩余（含国标/行业/空）归入 industry，避免记录“无处可去”。
function matchCategory(s, key) {
  const cat = s.category || s.standard_type || ''
  if (/标准件|parts/i.test(cat)) return key === 'parts'
  if (/企标|企业|enterprise/i.test(cat)) return key === 'enterprise'
  return key === 'industry'
}

// 各分类数量（受搜索关键字影响，不受状态筛选影响，便于总览每类有多少）
const catCounts = computed(() => {
  const map = { industry: 0, enterprise: 0, parts: 0 }
  standards.value.forEach((s) => {
    if (matchCategory(s, 'industry')) map.industry += 1
    else if (matchCategory(s, 'enterprise')) map.enterprise += 1
    else if (matchCategory(s, 'parts')) map.parts += 1
  })
  return map
})

const filtered = computed(() =>
  standards.value.filter((s) => {
    const matchCat = matchCategory(s, activeCat.value)
    const matchStatus =
      statusFilter.value === 'all' || s.status === statusFilter.value
    return matchCat && matchStatus
  }),
)

function statusTag(status) {
  if (status === 'published') return { type: 'success', text: '已发布' }
  if (status === 'archived') return { type: 'info', text: '历史发布' }
  return { type: 'warning', text: '未发布' }
}

async function publish(row) {
  try {
    await standardsApi.update(row.id, { ...row, status: 'published' })
    ElMessage.success('已发布')
    await loadStandards()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

// 上传对话框
const dialogVisible = ref(false)
const form = ref({ standard_no: '', standard_type: '', title: '', version: '', source: '' })
const fileRef = ref(null)
const importing = ref(false)

// 类型下拉：值需能被分类正则识别（企业标准→enterprise，企业标准件→parts，国标/行业→industry）
const typeOptions = [
  { label: '国标 / 行业标准', value: '国标' },
  { label: '企业标准', value: '企业标准' },
  { label: '企业标准件', value: '企业标准件' },
]
// 版本建议：默认给出当天日期版本号，也允许手动输入
const today = new Date()
const defaultVersion = `v${today.getFullYear()}.${today.getMonth() + 1}.${today.getDate()}.1`
const versionOptions = [defaultVersion]
// 来源固定为文件格式
const sourceOptions = ['PDF', 'Word', 'Excel', 'JSON', '图片']

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
    dialogVisible.value = false
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
  <div>
    <div class="tf-page-head">
      <div>
        <h2 class="tf-page-title">知识库管理</h2>
        <div class="tf-page-desc">管理行业/企业标准规则与标准件，支持发布状态与版本追踪</div>
      </div>
      <el-button type="primary" @click="dialogVisible = true">+ 上传知识/规则文件</el-button>
    </div>

    <div class="tf-card">
      <div class="cat-tabs">
        <div
          v-for="c in categories"
          :key="c.key"
          class="cat-tab"
          :class="{ active: activeCat === c.key }"
          @click="activeCat = c.key"
        >
          <div class="cat-label">
            {{ c.label }}
            <span class="cat-count">{{ catCounts[c.key] }}</span>
          </div>
          <div class="cat-desc">{{ c.desc }}</div>
        </div>
      </div>

      <div class="tf-toolbar" style="margin-top: 16px">
        <el-input
          v-model="keyword"
          placeholder="按标准号/标题搜索"
          clearable
          style="width: 240px"
          @keyup.enter="loadStandards"
        />
        <el-select v-model="statusFilter" style="width: 140px">
          <el-option label="全部状态" value="all" />
          <el-option label="已发布" value="published" />
          <el-option label="未发布" value="draft" />
          <el-option label="历史发布" value="archived" />
        </el-select>
        <el-button type="primary" @click="loadStandards">查询</el-button>
      </div>

      <el-table :data="filtered" v-loading="loading" border style="width: 100%; margin-top: 12px">
        <el-table-column prop="standard_no" label="标准号" width="170" />
        <el-table-column prop="title" label="规则名称 / 说明" min-width="200" />
        <el-table-column label="版本 / 格式" width="150">
          <template #default="{ row }">
            {{ row.version || '-' }}
            <el-tag size="small" type="info" effect="plain">{{ row.source || 'PDF' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="updated_at" label="创建时间" width="170" />
        <el-table-column label="发布状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status).type" size="small">
              {{ statusTag(row.status).text }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status !== 'published'"
              size="small"
              type="primary"
              link
              @click="publish(row)"
            >发布</el-button>
            <el-button size="small" link>下载</el-button>
            <el-button size="small" type="danger" link>删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" title="上传知识 / 规则文件" width="560px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="标准号">
          <el-input v-model="form.standard_no" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.standard_type" placeholder="请选择标准类型" style="width: 100%">
            <el-option
              v-for="opt in typeOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="form.title" />
        </el-form-item>
        <el-form-item label="版本">
          <el-select
            v-model="form.version"
            filterable
            allow-create
            default-first-option
            placeholder="选择或输入版本，如 v2026.1"
            style="width: 100%"
          >
            <el-option v-for="v in versionOptions" :key="v" :label="v" :value="v" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源">
          <el-select v-model="form.source" placeholder="请选择文件来源" style="width: 100%">
            <el-option v-for="s in sourceOptions" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item label="文件">
          <el-upload :auto-upload="false" :limit="1" :on-change="onFileChange">
            <el-button>选择文件（Excel/JSON/Word/PDF/图片）</el-button>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="importing" @click="doImport">开始导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.cat-tabs { display: flex; gap: 12px; }
.cat-tab {
  flex: 1; border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px 16px;
  cursor: pointer; transition: all 0.2s;
}
.cat-tab:hover { border-color: #c7d2fe; }
.cat-tab.active { border-color: #6366f1; background: #eef2ff; }
.cat-label { font-size: 15px; font-weight: 600; color: #1e293b; }
.cat-count {
  display: inline-block; min-width: 18px; padding: 0 6px; margin-left: 6px;
  font-size: 12px; line-height: 18px; text-align: center; color: #6366f1;
  background: #eef2ff; border-radius: 9px; vertical-align: middle;
}
.cat-tab.active .cat-count { color: #fff; background: #6366f1; }
.cat-desc { font-size: 12px; color: #94a3b8; margin-top: 4px; }
</style>