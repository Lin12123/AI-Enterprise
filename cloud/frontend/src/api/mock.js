/**
 * 前端假数据（mock）：用于"企业运营总览""插件管理""项目图纸管理"等暂未对接后端的模块。
 * 上线接入真实接口后可逐步替换。
 */

// ---------- 企业运营总览 ----------
export const overviewStats = [
  { key: 'projects', label: '活跃项目', value: 2, unit: '个', trend: '+1 本月', color: '#6366f1' },
  { key: 'devices', label: '受管设备', value: 142, unit: '台', trend: '5 台待接入', color: '#0ea5e9' },
  { key: 'approvals', label: '待审批图纸', value: 2, unit: '份', trend: '需尽快处理', color: '#f59e0b' },
  { key: 'coverage', label: 'Stable 覆盖', value: 60, unit: '%', trend: '目标 80%', color: '#10b981' },
]

export const approvalTasks = [
  {
    id: 'task-001',
    title: '[公狼项目]-相机支架图纸',
    project: 'PRJ-AERO-2026',
    applicant: '李工',
    deadline: '2026-08-18 18:00',
    priority: 'high',
  },
  {
    id: 'task-002',
    title: '[分播墙项目]-三段式供包台标准',
    project: 'PRJ-FLANGE-01',
    applicant: '王工',
    deadline: '2026-08-20 12:00',
    priority: 'normal',
  },
]

export const coverageMetrics = [
  { label: '插件版本覆盖', value: 94.2 },
  { label: 'AI 模型覆盖', value: 92.5 },
  { label: '标准规则覆盖', value: 96.8 },
]

// ---------- 项目图纸管理 ----------
// 默认成员样例（项目详情弹窗兜底展示用）
export const mockMembers = [
  { id: 'm1', name: '李工', role: '主设计师', email: 'li.gong@corp.local' },
  { id: 'm2', name: '王工', role: '结构工程师', email: 'wang.gong@corp.local' },
  { id: 'm3', name: '张审', role: '审批人', email: 'zhang.shen@corp.local' },
]

// 默认图纸明细样例（项目详情弹窗兜底展示用）
export const mockDrawingList = [
  {
    id: 'd1',
    code: 'TF-WING-001-A1',
    name: '主翼连接支架',
    desc: '航空级铝合金连接支架，含公差与技术要求。',
    version: 'A1',
    status: '已审批',
    fileType: 'SLDPRT',
    size: '2.4 MB',
    updatedBy: '李工',
    updatedAt: '2026-08-14 09:20',
  },
  {
    id: 'd2',
    code: 'TF-WING-002-A0',
    name: '相机支架底板',
    desc: '相机固定底板，STEP 交付件。',
    version: 'A0',
    status: '未审批',
    fileType: 'STEP',
    size: '1.1 MB',
    updatedBy: '王工',
    updatedAt: '2026-08-13 15:40',
  },
  {
    id: 'd3',
    code: 'TF-WING-003-D',
    name: '加强筋组件',
    desc: '草稿版本，待补充公差标注。',
    version: 'draft',
    status: '草稿',
    fileType: 'PRT',
    size: '0.8 MB',
    updatedBy: '李工',
    updatedAt: '2026-08-12 10:05',
  },
]

export const mockProjects = [
  {
    id: 'PRJ-AERO-2026',
    name: '航空结构件协同项目',
    enabled: true,
    desc: '航空支架、连接件系列的智能出图与版本管理。',
    drawings: 128,
    members: 12,
    updatedAt: '2026-08-14 09:20',
    memberList: mockMembers,
    drawingList: mockDrawingList,
  },
  {
    id: 'PRJ-FLANGE-01',
    name: '标准法兰盘产线',
    enabled: true,
    desc: '基于企业标准件库的法兰批量建模与出图。',
    drawings: 64,
    members: 6,
    updatedAt: '2026-08-12 16:05',
    memberList: mockMembers.slice(0, 2),
    drawingList: mockDrawingList.slice(0, 2),
  },
  {
    id: 'PRJ-LEGACY-09',
    name: '存量图纸归档',
    enabled: false,
    desc: '历史图纸迁移与合规归档，暂停维护。',
    drawings: 320,
    members: 3,
    updatedAt: '2026-06-30 11:00',
    memberList: mockMembers,
    drawingList: mockDrawingList,
  },
]

// ---------- 插件管理 ----------
export const mockPlugins = [
  {
    id: 'aisw-addin',
    name: 'AI-SW SolidWorks 插件-2019',
    version: 'v3.2.1',
    channel: 'Stable',
    signed: true,
    adoption: 94.2,
  },
  {
    id: 'aisw-drawing',
    name: '智能出图增强包-2022',
    version: 'v1.4.0-beta',
    channel: 'Beta',
    signed: true,
    adoption: 31.7,
  },
]

export const pluginMetrics = [
  { label: '覆盖采用率', value: '94.2%', color: '#6366f1' },
  { label: '崩溃失败率', value: '0.18%', color: '#10b981' },
  { label: '推理耗时', value: '42ms', color: '#0ea5e9' },
  { label: '识别准确率', value: '98.9%', color: '#f59e0b' },
]

export const pluginManifest = {
  name: 'AiSwAddin',
  entry: 'AiSwAddin.dll',
  host: 'SolidWorks 2019+',
  permissions: ['文档读写', '特征建模', '出图导出'],
}

export const pluginSbom = [
  { name: 'Newtonsoft.Json', version: '13.0.3', license: 'MIT' },
  { name: 'SolidWorks.Interop', version: '28.0', license: 'Proprietary' },
  { name: 'System.Text.Json', version: '8.0.4', license: 'MIT' },
]

// ---------- 知识库分类 ----------
export const knowledgeCategories = [
  { key: 'industry', label: '行业标准规则', desc: 'GB/ISO 等公开行业标准' },
  { key: 'enterprise', label: '企业标准规则', desc: '企业内部工艺与设计规范' },
  { key: 'parts', label: '企业标准件', desc: '可复用的标准件模型库' },
]