<script setup>
import { RouterView } from 'vue-router'

const navs = [
  { path: '/knowledge', label: '知识库管理' },
  { path: '/basedata', label: '基础数据' },
  { path: '/artifacts', label: '产物管理' },
]
</script>

<template>
  <el-container class="app-root">
    <el-header class="app-header">
      <span class="brand">AI-SW 云平台</span>
      <el-menu mode="horizontal" router :default-active="$route.path" class="app-menu">
        <el-menu-item v-for="n in navs" :key="n.path" :index="n.path">
          {{ n.label }}
        </el-menu-item>
      </el-menu>
    </el-header>
    <el-main>
      <RouterView />
    </el-main>
  </el-container>
</template>

<style scoped>
.app-root { height: 100vh; }
.app-header { display: flex; align-items: center; border-bottom: 1px solid #e4e7ed; }
.brand { font-weight: 600; font-size: 18px; margin-right: 32px; white-space: nowrap; }
.app-menu { flex: 1; border-bottom: none; }
</style>