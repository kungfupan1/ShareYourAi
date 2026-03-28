<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>用户管理</span>
          <div class="header-actions">
            <el-input
              v-model="search"
              placeholder="搜索用户名/邮箱"
              style="width: 200px; margin-right: 10px;"
              clearable
            />
            <el-select v-model="statusFilter" placeholder="状态" clearable style="width: 120px;">
              <el-option label="正常" value="active" />
              <el-option label="禁用" value="disabled" />
            </el-select>
          </div>
        </div>
      </template>

      <el-table :data="users" v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="username" label="用户名" />
        <el-table-column prop="email" label="邮箱" />
        <el-table-column label="实名认证" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_verified ? 'success' : 'info'">
              {{ row.is_verified ? '已认证' : '未认证' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="balance" label="余额" width="100">
          <template #default="{ row }">
            ¥{{ row.balance?.toFixed(2) || '0.00' }}
          </template>
        </el-table-column>
        <el-table-column prop="total_earned" label="累计收益" width="100">
          <template #default="{ row }">
            ¥{{ row.total_earned?.toFixed(2) || '0.00' }}
          </template>
        </el-table-column>
        <el-table-column label="风控等级" width="100">
          <template #default="{ row }">
            <el-tag :type="row.risk_level === 'danger' ? 'danger' : row.risk_level === 'warning' ? 'warning' : 'success'">
              {{ row.risk_level }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_blacklisted ? 'danger' : 'success'">
              {{ row.is_blacklisted ? '黑名单' : '正常' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="create_time" label="注册时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.create_time) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button
              :type="row.is_blacklisted ? 'success' : 'danger'"
              size="small"
              @click="handleBlacklist(row)"
            >
              {{ row.is_blacklisted ? '解除黑名单' : '加入黑名单' }}
            </el-button>
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
        @size-change="fetchUsers"
        @current-change="fetchUsers"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getUsers, toggleBlacklist } from '@/api/admin'

const loading = ref(false)
const users = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const search = ref('')
const statusFilter = ref('')

onMounted(() => {
  fetchUsers()
})

watch([search, statusFilter], () => {
  page.value = 1
  fetchUsers()
})

async function fetchUsers() {
  loading.value = true
  try {
    const res = await getUsers({
      page: page.value,
      page_size: pageSize.value,
      keyword: search.value,
      status: statusFilter.value
    })
    users.value = res.users
    total.value = res.total
  } catch (error) {
    console.error('获取用户失败:', error)
  } finally {
    loading.value = false
  }
}

async function handleBlacklist(row) {
  const action = row.is_blacklisted ? '解除黑名单' : '加入黑名单'
  await ElMessageBox.confirm(`确定要${action}用户 ${row.username} 吗？`, '确认', { type: 'warning' })

  try {
    await toggleBlacklist(JSON.parse(localStorage.getItem('user')).id, row.id)
    ElMessage.success(`已${action}`)
    fetchUsers()
  } catch (error) {
    console.error('操作失败:', error)
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