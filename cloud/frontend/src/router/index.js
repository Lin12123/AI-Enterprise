import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/knowledge' },
  {
    path: '/knowledge',
    name: 'knowledge',
    component: () => import('@/views/KnowledgeView.vue'),
    meta: { title: '知识库管理' },
  },
  {
    path: '/basedata',
    name: 'basedata',
    component: () => import('@/views/BaseDataView.vue'),
    meta: { title: '基础数据' },
  },
  {
    path: '/artifacts',
    name: 'artifacts',
    component: () => import('@/views/ArtifactsView.vue'),
    meta: { title: '产物管理' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.afterEach((to) => {
  document.title = to.meta?.title ? `${to.meta.title} - AI-SW 云平台` : 'AI-SW 云平台'
})

export default router