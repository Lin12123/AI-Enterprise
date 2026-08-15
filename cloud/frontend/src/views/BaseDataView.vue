<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { materialsApi, templatesApi } from '@/api'

const materials = ref([])
const templates = ref([])

async function loadMaterials() {
  try {
    materials.value = await materialsApi.list()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function loadTemplates() {
  try {
    templates.value = await templatesApi.list()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

// 材料新增
const matForm = ref({ name: '', density: null, remark: '' })
async function addMaterial() {
  try {
    await materialsApi.create(matForm.value)
    ElMessage.success('已新增材料')
    matForm.value = { name: '', density: null, remark: '' }
    await loadMaterials()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function removeMaterial(row) {
  await ElMessageBox.confirm(`删除材料「${row.name}」？`, '确认')
  await materialsApi.remove(row.id)
  await loadMaterials()
}

// 模板新增
const tplForm = ref({ name: '', category: '', file_path: '', remark: '' })
async function addTemplate() {
  try {
    await templatesApi.create(tplForm.value)
    ElMessage.success('已新增模板')
    tplForm.value = { name: '', category: '', file_path: '', remark: '' }
    await loadTemplates()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function removeTemplate(row) {
  await ElMessageBox.confirm(`删除模板「${row.name}」？`, '确认')
  await templatesApi.remove(row.id)
  await loadTemplates()
}

onMounted(() => {
  loadMaterials()
  loadTemplates()
})
</script>

<template>
  <el-tabs>
    <el-tab-pane label="材料">
      <div class="form-row">
        <el-input v-model="matForm.name" placeholder="名称" style="width: 160px" />
        <el-input v-model.number="matForm.density" placeholder="密度" style="width: 120px" />
        <el-input v-model="matForm.remark" placeholder="备注" style="width: 200px" />
        <el-button type="primary" @click="addMaterial">新增</el-button>
      </div>
      <el-table :data="materials" border style="width: 100%">
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="density" label="密度" width="120" />
        <el-table-column prop="remark" label="备注" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button link type="danger" @click="removeMaterial(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-tab-pane>

    <el-tab-pane label="模板">
      <div class="form-row">
        <el-input v-model="tplForm.name" placeholder="名称" style="width: 160px" />
        <el-input v-model="tplForm.category" placeholder="分类" style="width: 120px" />
        <el-input v-model="tplForm.file_path" placeholder="文件路径" style="width: 220px" />
        <el-button type="primary" @click="addTemplate">新增</el-button>
      </div>
      <el-table :data="templates" border style="width: 100%">
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="category" label="分类" width="120" />
        <el-table-column prop="file_path" label="文件路径" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button link type="danger" @click="removeTemplate(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-tab-pane>
  </el-tabs>
</template>

<style scoped>
.form-row { display: flex; gap: 8px; margin-bottom: 12px; }
</style>