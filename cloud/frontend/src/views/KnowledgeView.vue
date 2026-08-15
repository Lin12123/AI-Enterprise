<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
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

// 下载原始附件(直连 URL 触发浏览器下载)
function downloadStandard(row) {
  window.open(knowledgeApi.downloadUrl(row.id), '_blank')
}

// 删除标准(级联删除其下所有抽取规则，二次确认)
async function removeStandard(row) {
  try {
    await ElMessageBox.confirm(
      `删除标准「${row.title || row.standard_no}」将同时删除其下所有已抽取的规则，且不可恢复。确定删除？`,
      '删除确认',
      { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    const res = await standardsApi.remove(row.id)
    ElMessage.success(res?.message || '已删除')
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

// 规则导入模板：与后端 importer.parse_json 期望结构一致（高置信直接发布）。
// PDF/Word 上传后由本地 LLM 后台自动抽取为草稿规则(draft)，待人工确认后发布；图片暂只归档溯源。也可直接用此 JSON（或同列名 Excel）导入。
const ruleTemplate = {
  rules: [
    {
      scope_material: 'Q235',
      scope_feature: 'hole',
      clause: '普通螺栓过孔直径按 GB/T 5277 选取，M8 对应 φ9',
      params_json: { bolt: 'M8', hole_diameter_mm: 9, tolerance: 'H12' },
    },
    {
      scope_material: '',
      scope_feature: 'drawing',
      clause: '2D 工程图默认标注：第一角投影，单位 mm，未注公差按 GB/T 1804-m',
      params_json: { projection: 'first_angle', unit: 'mm', general_tolerance: 'GB/T 1804-m' },
    },
  ],
}

function downloadTemplate() {
  const blob = new Blob([JSON.stringify(ruleTemplate, null, 2)], {
    type: 'application/json',
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'knowledge_rules_template.json'
  a.click()
  URL.revokeObjectURL(url)
}

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
    if (res.async && res.attachment_id) {
      // 文档类:后台异步抽取，轮询进度
      dialogVisible.value = false
      ElMessage.success('文件已上传，正在后台抽取规则…')
      pollExtractStatus(res.attachment_id)
    } else {
      ElMessage.success(`导入成功，入库规则 ${res.inserted ?? 0} 条`)
      dialogVisible.value = false
    }
    await loadStandards()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    importing.value = false
  }
}

// 轮询后台抽取进度(最多约 10 分钟)
function pollExtractStatus(attachmentId) {
  let ticks = 0
  const maxTicks = 200 // 200 * 3s ≈ 10min
  const timer = setInterval(async () => {
    ticks += 1
    try {
      const st = await knowledgeApi.importStatus(attachmentId)
      if (st.status === 'done') {
        clearInterval(timer)
        ElMessage.success(st.message || `已抽取 ${st.inserted ?? 0} 条草稿规则`)
        await loadStandards()
      } else if (st.status === 'failed') {
        clearInterval(timer)
        ElMessage.error(st.message || '后台抽取失败，请人工补录')
      }
    } catch (e) {
      // 单次查询失败忽略，继续轮询
    }
    if (ticks >= maxTicks) {
      clearInterval(timer)
      ElMessage.warning('后台抽取仍在进行，可稍后刷新查看草稿规则')
    }
  }, 3000)
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
            <el-button size="small" link @click="downloadStandard(row)">下载</el-button>
            <el-button size="small" type="danger" link @click="removeStandard(row)">删除</el-button>
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
        <el-form-item>
          <el-alert type="info" :closable="false" show-icon>
            <template #title>
              PDF / Word 上传后由本地大模型<b>后台自动抽取</b>为草稿规则(draft)，待人工确认后发布；图片暂只归档溯源。
              大文件（如数百 MB）上传后即刻返回，抽取在后台进行，可稍后刷新查看；
              也可直接用 <b>Excel / JSON</b> 导入（自动入库并发布）。
            </template>
          </el-alert>
          <el-button link type="primary" style="margin-top: 6px" @click="downloadTemplate">
            下载 JSON 规则模板
          </el-button>
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