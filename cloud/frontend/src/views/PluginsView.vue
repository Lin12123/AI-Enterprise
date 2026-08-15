<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { pluginsApi } from '@/api'

const loading = ref(false)
const plugins = ref([])
const metrics = ref([])
const manifest = ref({})
const sbom = ref([])
const activeId = ref('')

async function load() {
  loading.value = true
  try {
    const [pl, mt, mf, sb] = await Promise.all([
      pluginsApi.list(),
      pluginsApi.metrics(),
      pluginsApi.manifest(),
      pluginsApi.sbom(),
    ])
    plugins.value = pl
    metrics.value = mt
    manifest.value = mf
    sbom.value = sb
    activeId.value = pl[0]?.id || ''
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

function upload() {
  ElMessage.info('上传新插件包功能待接入')
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <div class="tf-page-head">
      <div>
        <h2 class="tf-page-title">插件管理</h2>
        <div class="tf-page-desc">插件版本与包仓库、Manifest 清单、SBOM 依赖与采用指标</div>
      </div>
      <el-button type="primary" @click="upload">+ 新建上传</el-button>
    </div>

    <el-tabs>
      <el-tab-pane label="插件版本与包仓库">
        <div class="plg-layout">
          <div class="plg-list">
            <div
              v-for="p in plugins"
              :key="p.id"
              class="plg-item"
              :class="{ active: activeId === p.id }"
              @click="activeId = p.id"
            >
              <div class="plg-item-top">
                <span class="plg-name">{{ p.name }}</span>
                <el-tag :type="p.channel === 'Stable' ? 'success' : 'warning'" size="small">
                  {{ p.channel }}
           </el-tag>
              </div>
              <div class="plg-item-sub">
                <span>{{ p.version }}</span>
                <span v-if="p.signed" class="signed">✅ 已签名</span>
                <span>采用率 {{ p.adoption }}%</span>
              </div>
            </div>
          </div>

          <div class="plg-detail">
            <div class="tf-grid tf-grid-4">
              <div v-for="m in metrics" :key="m.label" class="tf-card metric-card">
                <div class="metric-label">{{ m.label }}</div>
                <div class="metric-value" :style="{ color: m.color }">{{ m.value }}</div>
              </div>
            </div>

            <div class="tf-card" style="margin-top: 16px">
              <h4 class="sec-title">Manifest 清单</h4>
              <div class="mf-row"><span>插件名</span><b>{{ manifest.name }}</b></div>
              <div class="mf-row"><span>入口</span><b>{{ manifest.entry }}</b></div>
              <div class="mf-row"><span>CAD 宿主兼容</span><b>{{ manifest.host }}</b></div>
              <div class="mf-row">
                <span>权限声明</span>
                <span>
                  <el-tag
                    v-for="perm in manifest.permissions"
                    :key="perm"
               size="small"
                    style="margin-right: 6px"
                  >{{ perm }}</el-tag>
                </span>
              </div>
            </div>

            <div class="tf-card" style="margin-top: 16px">
              <h4 class="sec-title">SBOM 依赖清单</h4>
              <el-table :data="sbom" border style="width: 100%">
                <el-table-column prop="name" label="组件" />
                <el-table-column prop="version" label="版本" width="140" />
                <el-table-column prop="license" label="许可证" width="160" />
              </el-table>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="采用与指标">
        <div class="tf-grid tf-grid-4">
          <div v-for="m in metrics" :key="m.label" class="tf-card metric-card">
            <div class="metric-label">{{ m.label }}</div>
            <div class="metric-value" :style="{ color: m.color }">{{ m.value }}</div>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="推送记录">
        <el-empty description="暂无推送记录（假数据模块）" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.plg-layout { display: flex; gap: 16px; }
.plg-list { width: 300px; flex-shrink: 0; }
.plg-item {
  border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px; margin-bottom: 12px;
  cursor: pointer; background: #fff; transition: all 0.2s;
}
.plg-item:hover { border-color: #c7d2fe; }
.plg-item.active { border-color: #6366f1; box-shadow: 0 0 0 2px #eef2ff; }
.plg-item-top { display: flex; justify-content: space-between; align-items: center; }
.plg-name { font-weight: 600; font-size: 14px; }
.plg-item-sub { display: flex; gap: 12px; font-size: 12px; color: #64748b; margin-top: 8px; }
.signed { color: #10b981; }
.plg-detail { flex: 1; min-width: 0; }
.metric-card {
  text-align: center;
  height: 100%;
  min-height: 108px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.metric-label { font-size: 13px; color: #64748b; }
.metric-value { font-size: 26px; font-weight: 700; margin-top: 6px; }
.sec-title { margin: 0 0 12px; font-size: 15px; color: #1e293b; }
.mf-row {
  display: flex; justify-content: space-between; padding: 8px 0;
  border-bottom: 1px dashed #e2e8f0; font-size: 13px; color: #475569;
}
.mf-row:last-child { border-bottom: none; }
</style>