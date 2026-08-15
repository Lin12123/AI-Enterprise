<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const menus = [
  { path: '/overview', label: '企业运营总览', icon: '📊', badge: '4' },
  { path: '/projects', label: '项目图纸管理', icon: '📁' },
  { path: '/knowledge', label: '知识库', icon: '📚' },
  { path: '/models', label: '模型管理', icon: '🧠' },
  { path: '/plugins', label: '插件管理', icon: '🧩', badge: 'v3.2.1' },
]

const activePath = computed(() => route.path)
</script>

<template>
  <el-container class="tf-root">
    <!-- 顶栏 -->
    <el-header class="tf-header">
      <div class="tf-brand">
        <div class="tf-logo">TF</div>
        <div class="tf-brand-text">
          <div class="tf-title">
            Think Form
            <span class="tf-tag">企业级 v3.2</span>
          </div>
          <div class="tf-subtitle">3DCAD 智能协同与插件模型制品总控平台</div>
        </div>
      </div>
      <div class="tf-header-right">
        <div class="tf-host">
          <span class="tf-dot online"></span>
          CAD 宿主协同 <b>3/5</b> 在线
        </div>
        <el-badge :value="4" class="tf-bell">
          <span class="tf-bell-icon">🔔</span>
        </el-badge>
        <div class="tf-user">
          <el-avatar :size="34" style="background: #6366f1">管</el-avatar>
          <div class="tf-user-text">
            <div class="tf-user-name">高级管理员</div>
            <div class="tf-user-role">ThinkForm 认证组</div>
          </div>
        </div>
      </div>
    </el-header>

    <el-container class="tf-body">
      <!-- 左侧导航 -->
      <el-aside width="230px" class="tf-aside">
        <div class="tf-aside-title">控制台中心模块</div>
        <el-menu :default-active="activePath" router class="tf-menu">
          <el-menu-item v-for="m in menus" :key="m.path" :index="m.path">
            <span class="tf-menu-icon">{{ m.icon }}</span>
            <span class="tf-menu-label">{{ m.label }}</span>
            <el-tag v-if="m.badge" size="small" class="tf-menu-badge" effect="dark">
              {{ m.badge }}
            </el-tag>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <!-- 主内容区 -->
      <el-main class="tf-main">
        <RouterView />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.tf-root { height: 100vh; }

/* 顶栏 */
.tf-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 64px;
  background: linear-gradient(90deg, #1e1b4b 0%, #312e81 60%, #4338ca 100%);
  color: #fff;
  padding: 0 24px;
}
.tf-brand { display: flex; align-items: center; gap: 12px; }
.tf-logo {
  width: 40px; height: 40px; border-radius: 10px;
  background: linear-gradient(135deg, #818cf8, #6366f1);
  display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 16px;
}
.tf-title { font-size: 18px; font-weight: 600; display: flex; align-items: center; gap: 8px; }
.tf-tag {
  font-size: 11px; padding: 1px 8px; border-radius: 10px;
  background: rgba(255, 255, 255, 0.18); font-weight: 500;
}
.tf-subtitle { font-size: 12px; opacity: 0.75; margin-top: 2px; }

.tf-header-right { display: flex; align-items: center; gap: 22px; }
.tf-host { font-size: 13px; opacity: 0.9; }
.tf-host b { color: #a5f3fc; }
.tf-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
.tf-dot.online { background: #34d399; box-shadow: 0 0 6px #34d399; }
.tf-bell { cursor: pointer; }
.tf-user { display: flex; align-items: center; gap: 10px; }
.tf-user-name { font-size: 13px; font-weight: 600; }
.tf-user-role { font-size: 11px; opacity: 0.7; }

/* 左侧导航 */
.tf-body { height: calc(100vh - 64px); }
.tf-aside {
  background: #1e293b;
  padding-top: 16px;
  overflow-y: auto;
}
.tf-aside-title {
  color: #94a3b8; font-size: 12px; padding: 0 20px 12px;
  letter-spacing: 1px;
}
.tf-menu {
  background: transparent;
  border-right: none;
}
.tf-menu :deep(.el-menu-item) {
  color: #cbd5e1;
  margin: 4px 12px;
  border-radius: 8px;
  height: 46px;
}
.tf-menu :deep(.el-menu-item:hover) {
  background: rgba(99, 102, 241, 0.18);
  color: #fff;
}
.tf-menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(90deg, #6366f1, #4f46e5);
  color: #fff;
}
.tf-menu-label { flex: 1; }
.tf-menu-icon { margin-right: 10px; font-size: 16px; }
.tf-bell-icon { font-size: 18px; cursor: pointer; }
.tf-menu-badge {
  border: none;
  background: rgba(255, 255, 255, 0.2);
}

/* 主区 */
.tf-main {
  background: #f1f5f9;
  padding: 24px;
  overflow-y: auto;
  overflow-x: hidden;
}
</style>