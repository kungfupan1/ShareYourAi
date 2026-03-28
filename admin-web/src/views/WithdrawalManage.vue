<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <span>提现管理</span>
      </template>

      <div style="margin-bottom: 20px;">
        <el-radio-group v-model="statusFilter" @change="fetchData">
          <el-radio-button label="">全部</el-radio-button>
          <el-radio-button label="pending">待处理</el-radio-button>
          <el-radio-button label="processing">处理中</el-radio-button>
          <el-radio-button label="completed">已完成</el-radio-button>
          <el-radio-button label="rejected">已拒绝</el-radio-button>
        </el-radio-group>
      </div>

      <el-table :data="withdrawals" v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="user_id" label="用户ID" width="80" />
        <el-table-column prop="amount" label="金额" width="100">
          <template #default="{ row }">
            ¥{{ row.amount?.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="method" label="方式" width="80">
          <template #default="{ row }">
            {{ row.method === 'alipay' ? '支付宝' : row.method === 'wechat' ? '微信' : '银行卡' }}
          </template>
        </el-table-column>
        <el-table-column prop="account" label="账号" />
        <el-table-column prop="real_name" label="姓名" width="100" />
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'completed' ? 'success' : row.status === 'pending' ? 'warning' : row.status === 'rejected' ? 'danger' : 'info'">
              {{ row.status === 'completed' ? '已完成' : row.status === 'pending' ? '待处理' : row.status === 'rejected' ? '已拒绝' : '处理中' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="transaction_id" label="交易号" />
        <el-table-column prop="create_time" label="申请时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.create_time) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <template v-if="row.status === 'pending'">
              <el-button type="success" size="small" @click="handleComplete(row)">确认打款</el-button>
              <el-button type="danger" size="small" @click="handleReject(row)">拒绝</el-button>
            </template>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        :total="total"
        :page-size="20"
        layout="total, prev, pager, next"
        style="margin-top: 20px; justify-content: flex-end;"
        @current-change="fetchData"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getWithdrawals, completeWithdrawal, rejectWithdrawal } from '@/api/admin'

const loading = ref(false)
const withdrawals = ref([])
const total = ref(0)
const page = ref(1)
const statusFilter = ref('')

onMounted(() => {
  fetchData()
})

async function fetchData() {
  loading.value = true
  try {
    const res = await getWithdrawals({ page: page.value, status: statusFilter.value })
    withdrawals.value = res.withdrawals
    total.value = res.total
  } catch (error) {
    console.error('获取数据失败:', error)
  } finally {
    loading.value = false
  }
}

async function handleComplete(row) {
  const { value } = await ElMessageBox.prompt('请输入交易流水号', '确认打款', {
    inputPattern: /.+/,
    inputErrorMessage: '请输入交易流水号'
  })
  try {
    await completeWithdrawal(row.id, value)
    ElMessage.success('打款完成')
    fetchData()
  } catch (error) {
    console.error('操作失败:', error)
  }
}

async function handleReject(row) {
  const { value } = await ElMessageBox.prompt('请输入拒绝原因', '拒绝', {
    inputPattern: /.+/,
    inputErrorMessage: '请输入拒绝原因'
  })
  try {
    await rejectWithdrawal(row.id, value)
    ElMessage.success('已拒绝')
    fetchData()
  } catch (error) {
    console.error('操作失败:', error)
  }
}

function formatTime(time) {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}
</script>