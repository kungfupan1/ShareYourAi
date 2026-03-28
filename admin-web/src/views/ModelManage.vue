<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>模型管理</span>
          <el-button type="primary" @click="showDialog()">新增模型</el-button>
        </div>
      </template>

      <el-table :data="models" v-loading="loading">
        <el-table-column prop="model_id" label="模型ID" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="model_type" label="类型" width="80">
          <template #default="{ row }">
            <el-tag>{{ row.model_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="provider" label="提供商" />
        <el-table-column prop="node_reward" label="节点奖励" width="100">
          <template #default="{ row }">
            ¥{{ row.node_reward?.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="user_price" label="用户价格" width="100">
          <template #default="{ row }">
            ¥{{ row.user_price?.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="showDialog(row)">编辑</el-button>
            <el-button type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="editingModel ? '编辑模型' : '新增模型'" width="600px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="模型ID" prop="model_id">
          <el-input v-model="form.model_id" :disabled="!!editingModel" />
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="类型" prop="model_type">
          <el-select v-model="form.model_type" style="width: 100%">
            <el-option label="视频" value="video" />
            <el-option label="图片" value="image" />
          </el-select>
        </el-form-item>
        <el-form-item label="提供商" prop="provider">
          <el-input v-model="form.provider" />
        </el-form-item>
        <el-form-item label="页面URL">
          <el-input v-model="form.page_url" />
        </el-form-item>
        <el-form-item label="超时时间">
          <el-input-number v-model="form.timeout" :min="60" :max="600" />
          <span style="margin-left: 10px;">秒</span>
        </el-form-item>
        <el-form-item label="节点奖励">
          <el-input-number v-model="form.node_reward" :min="0" :step="0.01" :precision="2" />
          <span style="margin-left: 10px;">元/次</span>
        </el-form-item>
        <el-form-item label="用户价格">
          <el-input-number v-model="form.user_price" :min="0" :step="0.01" :precision="2" />
          <span style="margin-left: 10px;">元/次</span>
        </el-form-item>
        <el-form-item label="最小耗时">
          <el-input-number v-model="form.min_duration" :min="30" :max="300" />
          <span style="margin-left: 10px;">秒</span>
        </el-form-item>
        <el-form-item label="最大耗时">
          <el-input-number v-model="form.max_duration" :min="300" :max="1200" />
          <span style="margin-left: 10px;">秒</span>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getModels, createModel, updateModel, deleteModel } from '@/api/admin'

const loading = ref(false)
const models = ref([])
const dialogVisible = ref(false)
const editingModel = ref(null)
const submitting = ref(false)
const formRef = ref()

const form = reactive({
  model_id: '',
  name: '',
  model_type: 'video',
  provider: '',
  page_url: '',
  timeout: 300,
  node_reward: 0.07,
  user_price: 0.10,
  min_duration: 60,
  max_duration: 600,
  is_active: true
})

const rules = {
  model_id: [{ required: true, message: '请输入模型ID', trigger: 'blur' }],
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  model_type: [{ required: true, message: '请选择类型', trigger: 'change' }],
  provider: [{ required: true, message: '请输入提供商', trigger: 'blur' }]
}

onMounted(() => {
  fetchModels()
})

async function fetchModels() {
  loading.value = true
  try {
    models.value = await getModels()
  } catch (error) {
    console.error('获取模型失败:', error)
  } finally {
    loading.value = false
  }
}

function showDialog(model = null) {
  editingModel.value = model
  if (model) {
    Object.assign(form, model)
  } else {
    Object.assign(form, {
      model_id: '',
      name: '',
      model_type: 'video',
      provider: '',
      page_url: '',
      timeout: 300,
      node_reward: 0.07,
      user_price: 0.10,
      min_duration: 60,
      max_duration: 600,
      is_active: true
    })
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (editingModel.value) {
      await updateModel(editingModel.value.model_id, form)
      ElMessage.success('更新成功')
    } else {
      await createModel(form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchModels()
  } catch (error) {
    console.error('保存失败:', error)
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定要删除模型 ${row.name} 吗？`, '确认', { type: 'warning' })
  try {
    await deleteModel(row.model_id)
    ElMessage.success('删除成功')
    fetchModels()
  } catch (error) {
    console.error('删除失败:', error)
  }
}
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>