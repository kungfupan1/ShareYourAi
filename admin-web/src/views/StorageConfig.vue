<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>存储桶配置</span>
          <el-button type="primary" @click="showDialog()">
            添加存储桶
          </el-button>
        </div>
      </template>

      <el-table :data="buckets" v-loading="loading">
        <el-table-column prop="name" label="名称" width="150" />
        <el-table-column prop="bucket_name" label="Bucket名称" width="200" />
        <el-table-column prop="region" label="地域" width="120" />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_private ? 'warning' : 'success'">
              {{ row.is_private ? '私有' : '公开' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="默认" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.is_default" type="success">是</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="自动清理" width="100">
          <template #default="{ row }">
            <span v-if="row.auto_clean">{{ row.retention_days }}天</span>
            <span v-else>否</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'">
              {{ row.status === 'active' ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220">
          <template #default="{ row }">
            <el-button size="small" @click="testBucket(row)">测试</el-button>
            <el-button size="small" @click="showDialog(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteBucket(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 添加/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑存储桶' : '添加存储桶'"
      width="500px"
    >
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="如：生产环境存储" />
        </el-form-item>

        <el-form-item label="Bucket名称" prop="bucket_name">
          <el-input v-model="form.bucket_name" placeholder="腾讯云COS存储桶名称" />
        </el-form-item>

        <el-form-item label="地域" prop="region">
          <el-select v-model="form.region" placeholder="选择地域" style="width: 100%">
            <el-option label="北京 (ap-beijing)" value="ap-beijing" />
            <el-option label="上海 (ap-shanghai)" value="ap-shanghai" />
            <el-option label="广州 (ap-guangzhou)" value="ap-guangzhou" />
            <el-option label="成都 (ap-chengdu)" value="ap-chengdu" />
            <el-option label="重庆 (ap-chongqing)" value="ap-chongqing" />
            <el-option label="深圳金融 (ap-shenzhen-fsi)" value="ap-shenzhen-fsi" />
            <el-option label="上海金融 (ap-shanghai-fsi)" value="ap-shanghai-fsi" />
            <el-option label="北京金融 (ap-beijing-fsi)" value="ap-beijing-fsi" />
            <el-option label="香港 (ap-hongkong)" value="ap-hongkong" />
            <el-option label="新加坡 (ap-singapore)" value="ap-singapore" />
          </el-select>
        </el-form-item>

        <el-form-item label="SecretId" prop="secret_id">
          <el-input v-model="form.secret_id" placeholder="腾讯云API密钥ID" />
        </el-form-item>

        <el-form-item label="SecretKey" prop="secret_key">
          <el-input v-model="form.secret_key" type="password" show-password placeholder="腾讯云API密钥Key" />
        </el-form-item>

        <el-form-item label="访问类型">
          <el-switch
            v-model="form.is_private"
            active-text="私有"
            inactive-text="公开"
          />
        </el-form-item>

        <el-form-item label="设为默认">
          <el-switch v-model="form.is_default" />
        </el-form-item>

        <el-form-item label="自动清理">
          <div style="display: flex; align-items: center; gap: 10px;">
            <el-switch v-model="form.auto_clean" />
            <span v-if="form.auto_clean">
              <el-input-number v-model="form.retention_days" :min="1" :max="365" size="small" />
              天后清理
            </span>
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/api/request'

const loading = ref(false)
const buckets = ref([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const submitting = ref(false)
const formRef = ref()
const editId = ref(null)

const form = reactive({
  name: '',
  bucket_name: '',
  region: '',
  secret_id: '',
  secret_key: '',
  is_private: true,
  is_default: false,
  auto_clean: false,
  retention_days: 7
})

const rules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  bucket_name: [{ required: true, message: '请输入Bucket名称', trigger: 'blur' }],
  region: [{ required: true, message: '请选择地域', trigger: 'change' }],
  secret_id: [{ required: true, message: '请输入SecretId', trigger: 'blur' }],
  secret_key: [{ required: true, message: '请输入SecretKey', trigger: 'blur' }]
}

async function loadBuckets() {
  loading.value = true
  try {
    const user = JSON.parse(localStorage.getItem('user') || '{}')
    const res = await request.get('/admin/storage-buckets', {
      params: { user_id: user.id }
    })
    buckets.value = res.buckets || []
  } catch (error) {
    console.error('加载存储桶失败:', error)
  } finally {
    loading.value = false
  }
}

function showDialog(row = null) {
  isEdit.value = !!row
  editId.value = row?.id || null

  if (row) {
    Object.assign(form, {
      name: row.name,
      bucket_name: row.bucket_name,
      region: row.region,
      secret_id: row.secret_id || '',
      secret_key: row.secret_key || '',
      is_private: row.is_private,
      is_default: row.is_default,
      auto_clean: row.auto_clean,
      retention_days: row.retention_days
    })
  } else {
    Object.assign(form, {
      name: '',
      bucket_name: '',
      region: '',
      secret_id: '',
      secret_key: '',
      is_private: true,
      is_default: false,
      auto_clean: false,
      retention_days: 7
    })
  }

  dialogVisible.value = true
}

async function submitForm() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const user = JSON.parse(localStorage.getItem('user') || '{}')
    const params = { user_id: user.id, ...form }

    if (isEdit.value) {
      await request.put(`/admin/storage-buckets/${editId.value}`, null, { params })
      ElMessage.success('更新成功')
    } else {
      await request.post('/admin/storage-buckets', null, { params })
      ElMessage.success('创建成功')
    }

    dialogVisible.value = false
    loadBuckets()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  } finally {
    submitting.value = false
  }
}

async function testBucket(row) {
  try {
    const user = JSON.parse(localStorage.getItem('user') || '{}')
    const res = await request.post(`/admin/storage-buckets/${row.id}/test`, null, {
      params: { user_id: user.id }
    })

    if (res.success) {
      ElMessage.success('连接测试成功')
    } else {
      ElMessage.error(res.message || '连接失败')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '测试失败')
  }
}

async function deleteBucket(row) {
  try {
    await ElMessageBox.confirm('确定删除该存储桶配置吗？', '确认', {
      type: 'warning'
    })

    const user = JSON.parse(localStorage.getItem('user') || '{}')
    await request.delete(`/admin/storage-buckets/${row.id}`, {
      params: { user_id: user.id }
    })

    ElMessage.success('删除成功')
    loadBuckets()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  }
}

onMounted(() => {
  loadBuckets()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
</style>