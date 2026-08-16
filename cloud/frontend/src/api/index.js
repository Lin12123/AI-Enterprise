/**
 * 业务 API 模块：按资源聚合后端端点，对齐 docs/cloud_platform_design.md §5。
 */
import { get, post, put, del } from './client'
import http from './client'

// ---------- 知识库：标准 ----------
export const standardsApi = {
  list: (params) => get('/standards', params),
  detail: (id) => get(`/standards/${id}`),
  create: (body) => post('/standards', body),
  update: (id, body) => put(`/standards/${id}`, body),
  remove: (id) => del(`/standards/${id}`),
}

// ---------- 知识库：条目 ----------
export const rulesApi = {
  list: (params) => get('/rules', params),
  create: (body) => post('/rules', body),
  update: (id, body) => put(`/rules/${id}`, body),
  remove: (id) => del(`/rules/${id}`),
}

// ---------- 知识库：导入/拉取 ----------
export const knowledgeApi = {
  pull: (params) => get('/knowledge/pull', params),
  // 大文件上传:去掉超时限制(timeout:0)，只做落盘+登记，抽取转后台异步
  import: (formData, onUploadProgress) =>
    http.post('/knowledge/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 0,
      onUploadProgress,
    }),
  // 轮询后台抽取进度
  importStatus: (attachmentId) =>
    get('/knowledge/import/status', { attachment_id: attachmentId }),
  // 原始附件下载(二进制流，直连 URL，避开 axios JSON 拦截)
  downloadUrl: (standardId) =>
    `/api/knowledge/import/download?standard_id=${standardId}`,
}

// ---------- 基础数据：材料 ----------
export const materialsApi = {
  list: (params) => get('/materials', params),
  create: (body) => post('/materials', body),
  update: (id, body) => put(`/materials/${id}`, body),
  remove: (id) => del(`/materials/${id}`),
}

// ---------- 基础数据：模板 ----------
export const templatesApi = {
  list: (params) => get('/templates', params),
  create: (body) => post('/templates', body),
  update: (id, body) => put(`/templates/${id}`, body),
  remove: (id) => del(`/templates/${id}`),
}

// ---------- 产物：任务 / 文件 ----------
export const tasksApi = {
  list: (params) => get('/tasks', params),
  detail: (id) => get(`/tasks/${id}`),
}

export const filesApi = {
  list: (params) => get('/files', params),
  downloadUrl: (id) => `/api/files/${id}/download`,
}

// ---------- 假数据模块（暂未对接后端）----------
import {
  overviewStats,
  approvalTasks,
  coverageMetrics,
  mockProjects,
  mockMembers,
  mockDrawingList,
  mockPlugins,
  pluginMetrics,
  pluginManifest,
  pluginSbom,
} from './mock'

// 字节数格式化为可读文本
const fmtSize = (n) => {
  const b = Number(n) || 0
  if (b <= 0) return '-'
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
  return `${(b / 1024 / 1024).toFixed(1)} MB`
}

// file 记录 → 图纸表格行（版本/状态/更新人后端暂无，mock 兜底）
const fileToDrawing = (f, idx) => ({
  id: f.id ?? `f-${idx}`,
  code: (f.file_name || `DWG-${idx + 1}`).replace(/\.[^.]+$/, ''),
  name: f.file_name || `图纸 ${idx + 1}`,
  desc: f.file_type ? `${f.file_type} 产物文件` : '云端产物文件',
  version: 'A0',
  status: idx === 0 ? '已审批' : '未审批',
  fileType: (f.file_type || '').toUpperCase() || 'FILE',
  size: fmtSize(f.size_bytes),
  updatedBy: '系统',
  updatedAt: f.created_at || '',
  fileId: f.id,
})

const delay = (data, ms = 200) =>
  new Promise((resolve) => setTimeout(() => resolve(data), ms))

// 企业运营总览：假数据
export const dashboardApi = {
  stats: () => delay(overviewStats),
  approvals: () => delay(approvalTasks),
  coverage: () => delay(coverageMetrics),
}

// 项目图纸管理：以 task 为一张卡片，files 数由 /api/files 本地聚合。
// 后端暂无 project 聚合表，一条 task = 一次插件"上传到云平台"会话。
export const projectsApi = {
  async list() {
    try {
      const [tasks, files] = await Promise.all([
        get('/tasks'),
        get('/files'),
      ])
      if (!Array.isArray(tasks) || tasks.length === 0) {
        // 空库时用 mock 兜底，避免运营页空白
        return delay(mockProjects)
      }
      const fileCount = new Map()
      for (const f of files || []) {
        const k = f.task_id || 0
        fileCount.set(k, (fileCount.get(k) || 0) + 1)
      }
      // task → 卡片字段
      return tasks.map((t) => {
        const st = (t.status || '').toLowerCase()
        const enabled = !(st === 'archived' || st === 'disabled')
        const partName = t.part_name || t.title || `任务 #${t.id}`
        return {
          id: t.task_uid || `TASK-${t.id}`,
          tid: t.id,
          name: t.title || partName,
          enabled,
          desc: '',
          drawings: fileCount.get(t.id) || 0,
          members: 1,
          updatedAt: t.created_at || '',
        }
      })
    } catch (e) {
      // 后端不可达时给 mock 兜底
      return delay(mockProjects)
    }
  },
  // 删除项目：连带删除其产物文件(后端级联)。tid 为 task 数字主键。
  remove: (tid) => del(`/tasks/${tid}`),
  // 项目详情：返回 { project, members, drawings }。
  // tid 为数字主键时取真实 task+files；否则(mock 卡片)用 mock 明细兜底。
  async detail(card) {
    const tid = card && card.tid
    if (tid == null) {
      // mock 卡片：优先用 mock 明细
      const m = mockProjects.find((p) => p.id === (card && card.id))
      return delay({
        project: card || {},
        members: (m && m.memberList) || mockMembers,
        drawings: (m && m.drawingList) || mockDrawingList,
      })
    }
    try {
      const data = await get(`/tasks/${tid}`)
      const files = (data && data.files) || []
      const drawings = files.length
        ? files.map((f, i) => fileToDrawing(f, i))
        : mockDrawingList
      return {
        project: {
          id: (data && data.task_uid) || card.id,
          name: (data && data.title) || card.name,
          enabled: card.enabled,
          desc: (data && data.part_name) ? `零件：${data.part_name}` : card.desc,
          updatedAt: (data && data.created_at) || card.updatedAt,
        },
        members: mockMembers,
        drawings,
      }
    } catch (e) {
      return {
        project: card || {},
        members: mockMembers,
        drawings: mockDrawingList,
      }
    }
  },
}

// 插件管理：假数据
export const pluginsApi = {
  list: () => delay(mockPlugins),
  metrics: () => delay(pluginMetrics),
  manifest: () => delay(pluginManifest),
  sbom: () => delay(pluginSbom),
}