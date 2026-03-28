<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <span>收益审核</span>
      </template>

      <div style="margin-bottom: 20px;">
        <el-radio-group v-model="statusFilter" @change="fetchData">
          <el-radio-button label="">全部</el-radio-button>
          <el-radio-button label="auditing">待审核</el-radio-button>
          <el-radio-button label="settled">已通过</el-radio-button>
          <el-radio-button label="cancelled">已拒绝</el-radio-button>
        </el-radio-group>
      </div>

      <el-table :data="tasks" v-loading="loading">
        <el-table-column prop="task_id" label="任务ID" width="120" />
        <el-table-column prop="node_id" label="节点" width="100" />
        <el-table-column prop="user_id" label="用户ID" width="80" />
        <el-table-column prop="model_id" label="模型" width="120" />
        <el-table-column prop="node_reward" label="金额" width="80">
          <template #default="{ row }">
            ¥{{ row.node_reward?.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="validation_status" label="校验" width="80">
          <template #default="{ row }">
            <el-tag :type="row.validation_status === 'passed' ? 'success' : 'danger'">
              {{ row.validation_status === 'passed' ? '通过' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="earning_status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.earning_status === 'settled' ? 'success' : row.earning_status === 'auditing' ? 'warning' : 'info'">
              {{ row.earning_status === 'settled' ? '已通过' : row.earning_status === 'auditing' ? '待审核' : '已拒绝' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="duration" label="耗时" width="80">
          <template #default="{ row }">
            {{ row.duration ? row.duration + 's' : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="create_time" label="时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.create_time) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <template v-if="row.earning_status === 'auditing'">
              <el-button type="success" size="small" @click="handleApprove(row)">通过</el-button>
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
import { getEarnings, approveEarning, rejectEarning } from '@/api/admin'

const loading = ref(false)
const tasks = ref([])
const total = ref(0)
const page = ref(1)
const statusFilter = ref('')

onMounted(() => {
  fetchData()
})

async function fetchData() {
  loading.value = true
  try {
    const res = await getEarnings({ page: page.value, status: statusFilter.value })
    tasks.value = res.tasks
    total.value = res.total
  } catch (error) {
    console.error('获取数据失败:', error)
  } finally {
    loading.value = false
  }
}

async function handleApprove(row) {
  await ElMessageBox.confirm(`确定通过任务 ${row.task_id} 的收益审核吗？`, '确认', { type: 'info' })
  try {
    await approveEarning(row.task_id)
    ElMessage.success('审核通过')
    fetchData()
  } catch (error) {
    console.error('审核失败:', error)
  }
}

async function handleReject(row) {
  const { value } = await ElMessageBox.prompt('请输入拒绝原因', '拒绝', {
    inputPattern: /.+/,
    inputErrorMessage: '请输入拒绝原因'
  })
  try {
    await rejectEarning(row.task_id, value)
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