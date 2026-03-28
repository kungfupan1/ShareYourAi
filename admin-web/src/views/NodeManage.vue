<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>节点管理</span>
          <div class="header-actions">
            <el-input
              v-model="search"
              placeholder="搜索节点ID"
              style="width: 200px; margin-right: 10px;"
              clearable
            />
            <el-select v-model="statusFilter" placeholder="状态" clearable style="width: 120px;">
              <el-option label="空闲" value="idle" />
              <el-option label="忙碌" value="busy" />
              <el-option label="离线" value="offline" />
            </el-select>
          </div>
        </div>
      </template>

      <el-table :data="nodes" v-loading="loading">
        <el-table-column prop="node_id" label="节点ID" width="120" />
        <el-table-column prop="node_name" label="节点名称" />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'idle' ? 'success' : row.status === 'busy' ? 'warning' : 'info'">
              {{ row.status === 'idle' ? '空闲' : row.status === 'busy' ? '忙碌' : '离线' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="score" label="评分" width="80">
          <template #default="{ row }">
            <span :style="{ color: row.score >= 80 ? '#10B981' : row.score >= 60 ? '#F59E0B' : '#EF4444' }">
              {{ row.score?.toFixed(1) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="supported_models" label="支持模型" width="200">
          <template #default="{ row }">
            {{ row.supported_models || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="today_tasks" label="今日任务" width="80" />
        <el-table-column prop="total_tasks" label="总任务" width="80" />
        <el-table-column prop="success_rate" label="成功率" width="80">
          <template #default="{ row }">
            {{ row.success_rate }}%
          </template>
        </el-table-column>
        <el-table-column prop="last_heartbeat" label="最后心跳" width="180">
          <template #default="{ row }">
            {{ formatTime(row.last_heartbeat) }}
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        style="margin-top: 20px; justify-content: flex-end;"
        @size-change="fetchNodes"
        @current-change="fetchNodes"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { getNodes } from '@/api/admin'

const loading = ref(false)
const nodes = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const search = ref('')
const statusFilter = ref('')

onMounted(() => {
  fetchNodes()
})

watch([search, statusFilter], () => {
  page.value = 1
  fetchNodes()
})

async function fetchNodes() {
  loading.value = true
  try {
    const res = await getNodes({
      page: page.value,
      page_size: pageSize.value,
      keyword: search.value,
      status: statusFilter.value
    })
    nodes.value = res.nodes
    total.value = res.total
  } catch (error) {
    console.error('获取节点失败:', error)
  } finally {
    loading.value = false
  }
}

function formatTime(time) {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  align-items: center;
}
</style>