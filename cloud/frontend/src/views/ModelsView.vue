<script setup>
// 模型管理：当前使用本地模型，功能开发中，先做占位
</script>

<template>
  <div>
    <div class="tf-page-head">
      <div>
        <h2 class="tf-page-title">模型管理</h2>
        <div class="tf-page-desc">本地/私有化模型的注册、版本与推理配置管理</div>
      </div>
    </div>

    <div class="tf-card model-placeholder">
      <div class="ph-icon">🧠</div>
      <el-empty description="模型管理功能开发中，当前使用本地模型，敬请期待">
        <div class="ph-tip">
          规划中：本地模型注册 · 版本切换 · 推理参数配置 · 私有化部署监控
        </div>
      </el-empty>
    </div>
  </div>
</template>

<style scoped>
.model-placeholder { text-align: center; padding: 40px 0; }
.ph-icon { font-size: 56px; margin-bottom: 8px; }
.ph-tip { font-size: 13px; color: #94a3b8; margin-top: 8px; }
</style>