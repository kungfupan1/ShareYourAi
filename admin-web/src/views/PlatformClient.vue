<template>
  <div class="platform-client">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>平台客户管理</span>
          <el-button type="primary" @click="showCreateDialog">新增平台</el-button>
        </div>
      </template>

      <!-- 搜索栏 -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="关键词">
          <el-input v-model="searchForm.keyword" placeholder="平台名称/Client ID" clearable />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="全部" clearable>
            <el-option label="正常" value="active" />
            <el-option label="暂停" value="suspended" />
            <el-option label="停用" value="disabled" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">搜索</el-button>
        </el-form-item>
      </el-form>

      <!-- 表格 -->
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="client_id" label="Client ID" width="150" />
        <el-table-column prop="client_name" label="平台名称" min-width="120" />
        <el-table-column prop="api_key" label="API Key" width="180">
          <template #default="{ row }">
            <el-tooltip :content="row.api_key" placement="top">
              <span>{{ row.api_key }}</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="balance" label="余额" width="100">
          <template #default="{ row }">
            <span :class="{ 'text-danger': row.balance < 10 }">¥{{ row.balance?.toFixed(2) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="frozen_balance" label="冻结" width="80">
          <template #default="{ row }">¥{{ row.frozen_balance?.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ getStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_calls" label="调用次数" width="90" />
        <el-table-column prop="total_spent" label="累计消费" width="100">
          <template #default="{ row }">¥{{ row.total_spent?.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="create_time" label="创建时间" width="160">
          <template #default="{ row }">{{ formatTime(row.create_time) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="showDetail(row)">详情</el-button>
            <el-button type="success" link @click="showRechargeDialog(row)">充值</el-button>
            <el-button type="warning" link @click="toggleStatus(row)">
              {{ row.status === 'active' ? '停用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @size-change="loadData"
        @current-change="loadData"
        class="pagination"
      />
    </el-card>

    <!-- 新增平台对话框 -->
    <el-dialog v-model="createDialogVisible" title="新增平台客户" width="500px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="平台名称" required>
          <el-input v-model="createForm.client_name" placeholder="请输入平台名称" />
        </el-form-item>
        <el-form-item label="联系人">
          <el-input v-model="createForm.contact_name" placeholder="联系人姓名" />
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input v-model="createForm.contact_phone" placeholder="联系电话" />
        </el-form-item>
        <el-form-item label="联系邮箱">
          <el-input v-model="createForm.contact_email" placeholder="联系邮箱" />
        </el-form-item>
        <el-form-item label="回调地址">
          <el-input v-model="createForm.callback_url" placeholder="任务完成回调URL" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCreate" :loading="createLoading">创建</el-button>
      </template>
    </el-dialog>

    <!-- 充值对话框 -->
    <el-dialog v-model="rechargeDialogVisible" title="平台充值" width="400px">
      <el-form :model="rechargeForm" label-width="100px">
        <el-form-item label="平台">
          <span>{{ currentClient?.client_name }}</span>
        </el-form-item>
        <el-form-item label="当前余额">
          <span>¥{{ currentClient?.balance?.toFixed(2) }}</span>
        </el-form-item>
        <el-form-item label="充值金额" required>
          <el-input-number v-model="rechargeForm.amount" :min="1" :precision="2" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="rechargeForm.remark" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rechargeDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleRecharge" :loading="rechargeLoading">确认充值</el-button>
      </template>
    </el-dialog>

    <!-- 详情对话框 -->
    <el-dialog v-model="detailDialogVisible" title="平台详情" width="800px">
      <el-descriptions :column="2" border v-if="currentClient">
        <el-descriptions-item label="Client ID">{{ currentClient.client_id }}</el-descriptions-item>
        <el-descriptions-item label="平台名称">{{ currentClient.client_name }}</el-descriptions-item>
        <el-descriptions-item label="API Key">
          <div style="display: flex; align-items: center; gap: 10px;">
            <span>{{ currentClient.api_key }}</span>
            <el-button type="primary" link @click="handleResetKey">重置</el-button>
          </div>
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(currentClient.status)">{{ getStatusText(currentClient.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="余额">¥{{ currentClient.balance?.toFixed(2) }}</el-descriptions-item>
        <el-descriptions-item label="冻结金额">¥{{ currentClient.frozen_balance?.toFixed(2) }}</el-descriptions-item>
        <el-descriptions-item label="累计充值">¥{{ currentClient.total_recharged?.toFixed(2) }}</el-descriptions-item>
        <el-descriptions-item label="累计消费">¥{{ currentClient.total_spent?.toFixed(2) }}</el-descriptions-item>
        <el-descriptions-item label="联系人">{{ currentClient.contact_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="联系电话">{{ currentClient.contact_phone || '-' }}</el-descriptions-item>
        <el-descriptions-item label="联系邮箱">{{ currentClient.contact_email || '-' }}</el-descriptions-item>
        <el-descriptions-item label="回调地址">{{ currentClient.callback_url || '-' }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatTime(currentClient.create_time) }}</el-descriptions-item>
      </el-descriptions>

      <!-- 操作按钮 -->
      <div style="margin-top: 20px; display: flex; gap: 10px;">
        <el-button type="success" @click="showRechargeDialog(currentClient)">充值</el-button>
        <el-button type="warning" @click="showAdjustDialog(currentClient)">调整余额</el-button>
        <el-button @click="handleToggleStatus(currentClient)">
          {{ currentClient.status === 'active' ? '停用' : '启用' }}
        </el-button>
      </div>
    </el-dialog>

    <!-- 调整余额对话框 -->
    <el-dialog v-model="adjustDialogVisible" title="调整余额" width="400px">
      <el-form :model="adjustForm" label-width="100px">
        <el-form-item label="平台">
          <span>{{ currentClient?.client_name }}</span>
        </el-form-item>
        <el-form-item label="当前余额">
          <span>¥{{ currentClient?.balance?.toFixed(2) }}</span>
        </el-form-item>
        <el-form-item label="调整类型" required>
          <el-radio-group v-model="adjustForm.adjust_type">
            <el-radio label="add">增加</el-radio>
            <el-radio label="subtract">减少</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="金额" required>
          <el-input-number v-model="adjustForm.amount" :min="0.01" :precision="2" />
        </el-form-item>
        <el-form-item label="原因" required>
          <el-input v-model="adjustForm.remark" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="adjustDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleAdjust" :loading="adjustLoading">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getPlatformList, createPlatform, rechargePlatform, adjustPlatformBalance, updatePlatform, resetApiKey } from '@/api/platform'

// 数据
const loading = ref(false)
const tableData = ref([])
const searchForm = reactive({
  keyword: '',
  status: ''
})
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

// 创建对话框
const createDialogVisible = ref(false)
const createLoading = ref(false)
const createForm = reactive({
  client_name: '',
  contact_name: '',
  contact_phone: '',
  contact_email: '',
  callback_url: ''
})

// 充值对话框
const rechargeDialogVisible = ref(false)
const rechargeLoading = ref(false)
const rechargeForm = reactive({
  amount: 100,
  remark: ''
})

// 调整余额对话框
const adjustDialogVisible = ref(false)
const adjustLoading = ref(false)
const adjustForm = reactive({
  adjust_type: 'add',
  amount: 0,
  remark: ''
})

// 详情对话框
const detailDialogVisible = ref(false)
const currentClient = ref(null)

// 加载数据
const loadData = async () => {
  loading.value = true
  try {
    const res = await getPlatformList({
      user_id: 1,
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    })
    tableData.value = res.data || []
    pagination.total = res.total || 0
  } catch (error) {
    console.error(error)
  } finally {
    loading.value = false
  }
}

// 显示创建对话框
const showCreateDialog = () => {
  Object.assign(createForm, {
    client_name: '',
    contact_name: '',
    contact_phone: '',
    contact_email: '',
    callback_url: ''
  })
  createDialogVisible.value = true
}

// 创建平台
const handleCreate = async () => {
  if (!createForm.client_name) {
    ElMessage.warning('请输入平台名称')
    return
  }
  createLoading.value = true
  try {
    const res = await createPlatform(createForm)
    if (res.success) {
      ElMessage.success('创建成功')
      ElMessageBox.alert(`请保存 API Key: ${res.data.api_key}`, 'API Key', {
        confirmButtonText: '已保存'
      })
      createDialogVisible.value = false
      loadData()
    }
  } catch (error) {
    ElMessage.error('创建失败')
  } finally {
    createLoading.value = false
  }
}

// 显示详情
const showDetail = async (row) => {
  currentClient.value = row
  detailDialogVisible.value = true
}

// 显示充值对话框
const showRechargeDialog = (row) => {
  currentClient.value = row
  rechargeForm.amount = 100
  rechargeForm.remark = ''
  rechargeDialogVisible.value = true
}

// 充值
const handleRecharge = async () => {
  if (rechargeForm.amount <= 0) {
    ElMessage.warning('请输入正确的金额')
    return
  }
  rechargeLoading.value = true
  try {
    const res = await rechargePlatform(currentClient.value.client_id, rechargeForm)
    if (res.success) {
      ElMessage.success('充值成功')
      rechargeDialogVisible.value = false
      loadData()
    }
  } catch (error) {
    ElMessage.error('充值失败')
  } finally {
    rechargeLoading.value = false
  }
}

// 显示调整余额对话框
const showAdjustDialog = (row) => {
  currentClient.value = row
  adjustForm.adjust_type = 'add'
  adjustForm.amount = 0
  adjustForm.remark = ''
  adjustDialogVisible.value = true
}

// 调整余额
const handleAdjust = async () => {
  if (adjustForm.amount <= 0 || !adjustForm.remark) {
    ElMessage.warning('请填写完整信息')
    return
  }
  adjustLoading.value = true
  try {
    const res = await adjustPlatformBalance(currentClient.value.client_id, adjustForm)
    if (res.success) {
      ElMessage.success('调整成功')
      adjustDialogVisible.value = false
      loadData()
    }
  } catch (error) {
    ElMessage.error('调整失败')
  } finally {
    adjustLoading.value = false
  }
}

// 切换状态
const toggleStatus = async (row) => {
  const newStatus = row.status === 'active' ? 'disabled' : 'active'
  const action = newStatus === 'disabled' ? '停用' : '启用'

  try {
    await ElMessageBox.confirm(`确认${action}该平台？`, '提示')
    const res = await updatePlatform(row.client_id, { status: newStatus })
    if (res.success) {
      ElMessage.success(`${action}成功`)
      loadData()
    }
  } catch (error) {
    // 用户取消
  }
}

// 重置 API Key
const handleResetKey = async () => {
  try {
    await ElMessageBox.confirm('重置后旧 API Key 将立即失效，确认重置？', '警告')
    const res = await resetApiKey(currentClient.value.client_id)
    if (res.success) {
      ElMessage.success('API Key 已重置')
      ElMessageBox.alert(`新的 API Key: ${res.data.api_key}`, '请保存', {
        confirmButtonText: '已保存'
      })
      currentClient.value.api_key = res.data.api_key
      loadData()
    }
  } catch (error) {
    // 用户取消
  }
}

// 状态样式
const getStatusType = (status) => {
  const map = {
    active: 'success',
    suspended: 'warning',
    disabled: 'danger'
  }
  return map[status] || 'info'
}

const getStatusText = (status) => {
  const map = {
    active: '正常',
    suspended: '暂停',
    disabled: '停用'
  }
  return map[status] || status
}

// 格式化时间
const formatTime = (time) => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.platform-client {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  margin-bottom: 20px;
}

.pagination {
  margin-top: 20px;
  justify-content: flex-end;
}

.text-danger {
  color: #f56c6c;
}
</style>