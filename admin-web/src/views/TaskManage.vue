<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <span>任务管理</span>
      </template>

      <div style="margin-bottom: 20px;">
        <el-radio-group v-model="statusFilter" @change="fetchData">
          <el-radio-button label="">全部</el-radio-button>
          <el-radio-button label="pending">待处理</el-radio-button>
          <el-radio-button label="processing">处理中</el-radio-button>
          <el-radio-button label="success">成功</el-radio-button>
          <el-radio-button label="failed">失败</el-radio-button>
        </el-radio-group>
      </div>

      <el-table :data="tasks" v-loading="loading">
        <el-table-column prop="task_id" label="任务ID" width="120" />
        <el-table-column prop="model_id" label="模型" width="120" />
        <el-table-column prop="assigned_node_id" label="节点" width="100" />
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'success' ? 'success' : row.status === 'failed' ? 'danger' : row.status === 'processing' ? 'warning' : 'info'">
              {{ row.status === 'success' ? '成功' : row.status === 'failed' ? '失败' : row.status === 'processing' ? '处理中' : '待处理' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="node_reward" label="奖励" width="80">
          <template #default="{ row }">
            ¥{{ row.node_reward?.toFixed(2) || '0.00' }}
          </template>
        </el-table-column>
        <el-table-column prop="earning_status" label="收益状态" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.earning_status" :type="row.earning_status === 'withdrawable' ? 'success' : row.earning_status === 'auditing' ? 'warning' : 'info'" size="small">
              {{ row.earning_status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="duration_seconds" label="耗时" width="80">
          <template #default="{ row }">
            {{ row.duration_seconds ? row.duration_seconds + 's' : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="create_time" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.create_time) }}
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
import request from '@/api/request'

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
    const userId = JSON.parse(localStorage.getItem('user'))?.id
    const res = await request.get(`/admin/tasks?user_id=${userId}&page=${page.value}&status=${statusFilter.value}`)
    tasks.value = res.tasks
    total.value = res.total
  } catch (error) {
    console.error('获取数据失败:', error)
  } finally {
    loading.value = false
  }
}

function formatTime(time) {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}
</script>