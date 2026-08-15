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
  mockPlugins,
  pluginMetrics,
  pluginManifest,
  pluginSbom,
} from './mock'

const delay = (data, ms = 200) =>
  new Promise((resolve) => setTimeout(() => resolve(data), ms))

// 企业运营总览：假数据
export const dashboardApi = {
  stats: () => delay(overviewStats),
  approvals: () => delay(approvalTasks),
  coverage: () => delay(coverageMetrics),
}

// 项目图纸管理：前端 mock（后端暂无 projects 表）
export const projectsApi = {
  list: () => delay(mockProjects),
}

// 插件管理：假数据
export const pluginsApi = {
  list: () => delay(mockPlugins),
  metrics: () => delay(pluginMetrics),
  manifest: () => delay(pluginManifest),
  sbom: () => delay(pluginSbom),
}