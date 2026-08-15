<script setup>
import { ref, onMounted } from 'vue'
import { dashboardApi } from '@/api'

const stats = ref([])
const tasks = ref([])
const coverage = ref([])

async function load() {
  stats.value = await dashboardApi.stats()
  tasks.value = await dashboardApi.approvals()
  coverage.value = await dashboardApi.coverage()
}

onMounted(load)
</script>

<template>
  <div>
    <div class="tf-page-head">
      <div>
        <h2 class="tf-page-title">企业运营总览</h2>
        <div class="tf-page-desc">3DCAD 智能协同平台的运营态势、审批任务与版本覆盖概览</div>
      </div>
      <el-button type="primary">导出运营报表</el-button>
    </div>

    <!-- 统计卡片 -->
    <div class="tf-grid tf-grid-4">
      <div v-for="s in stats" :key="s.key" class="tf-card stat-card">
        <div class="stat-bar" :style="{ background: s.color }"></div>
        <div class="stat-label">{{ s.label }}</div>
        <div class="stat-value">
          {{ s.value }}<span class="stat-unit">{{ s.unit }}</span>
     </div>
        <div class="stat-trend">{{ s.trend }}</div>
      </div>
    </div>

    <div class="tf-grid tf-grid-3" style="margin-top: 16px">
      <!-- 审批任务 -->
      <div class="tf-card" style="grid-column: span 2">
        <div class="section-title">图纸审批任务</div>
        <div v-for="t in tasks" :key="t.id" class="task-row">
          <div>
            <div class="task-title">
              {{ t.title }}
              <el-tag v-if="t.priority === 'high'" type="danger" size="small">紧急</el-tag>
            </div>
            <div class="task-meta">
              {{ t.id }} · {{ t.project }} · 申请人 {{ t.applicant }} · 截止 {{ t.deadline }}
            </div>
          </div>
          <div class="task-actions">
            <el-button type="success" size="small">通过</el-button>
            <el-button type="danger" size="small" plain>驳回</el-button>
          </div>
        </div>
      </div>

      <!-- 版本覆盖率 -->
      <div class="tf-card">
        <div class="section-title">新版本设备侧覆盖率</div>
        <div v-for="c in coverage" :key="c.label" class="cov-row">
          <div class="cov-head">
            <span>{{ c.label }}</span>
            <b>{{ c.value }}%</b>
          </div>
          <el-progress :percentage="c.value" :show-text="false" :stroke-width="8" color="#6366f1" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stat-card {
  position: relative;
  overflow: hidden;
  height: 100%;
  min-height: 118px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.stat-bar { position: absolute; left: 0; top: 0; width: 4px; height: 100%; }
.stat-label { font-size: 13px; color: #64748b; }
.stat-value { font-size: 30px; font-weight: 700; margin: 6px 0; }
.stat-unit { font-size: 14px; color: #94a3b8; margin-left: 4px; }
.stat-trend { font-size: 12px; color: #94a3b8; min-height: 18px; }

.section-title { font-size: 15px; font-weight: 600; margin-bottom: 16px; }

.task-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 0; border-bottom: 1px solid #f1f5f9;
}
.task-row:last-child { border-bottom: none; }
.task-title { font-weight: 600; display: flex; align-items: center; gap: 8px; }
.task-meta { font-size: 12px; color: #94a3b8; margin-top: 4px; }

.cov-row { margin-bottom: 16px; }
.cov-head { display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 6px; }
</style>