<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <span>系统配置</span>
      </template>

      <el-form :model="form" label-width="150px" style="max-width: 600px;">
        <el-divider>任务配置</el-divider>

        <el-form-item label="任务超时时间">
          <el-input-number v-model="form.task_timeout" :min="60" :max="600" />
          <span style="margin-left: 10px;">秒</span>
        </el-form-item>

        <el-form-item label="节点心跳超时">
          <el-input-number v-model="form.node_heartbeat_timeout" :min="30" :max="300" />
          <span style="margin-left: 10px;">秒</span>
        </el-form-item>

        <el-divider>提现配置</el-divider>

        <el-form-item label="最低提现金额">
          <el-input-number v-model="form.min_withdrawal" :min="1" :max="100" />
          <span style="margin-left: 10px;">元</span>
        </el-form-item>

        <el-form-item label="最高提现金额">
          <el-input-number v-model="form.max_withdrawal" :min="100" :max="10000" />
          <span style="margin-left: 10px;">元</span>
        </el-form-item>

        <el-form-item label="每日提现上限">
          <el-input-number v-model="form.daily_withdrawal_limit" :min="100" :max="50000" />
          <span style="margin-left: 10px;">元</span>
        </el-form-item>

        <el-form-item label="每日提现次数">
          <el-input-number v-model="form.daily_withdrawal_count" :min="1" :max="10" />
          <span style="margin-left: 10px;">次</span>
        </el-form-item>

        <el-divider>收益配置</el-divider>

        <el-form-item label="收益冻结期">
          <el-input-number v-model="form.earning_freeze_days" :min="0" :max="30" />
          <span style="margin-left: 10px;">天</span>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleSave" :loading="loading">保存配置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getSystemConfig, updateSystemConfig } from '@/api/admin'

const loading = ref(false)

const form = reactive({
  task_timeout: 300,
  node_heartbeat_timeout: 60,
  min_withdrawal: 10,
  max_withdrawal: 5000,
  daily_withdrawal_limit: 10000,
  daily_withdrawal_count: 3,
  earning_freeze_days: 3
})

onMounted(() => {
  fetchConfig()
})

async function fetchConfig() {
  try {
    const res = await getSystemConfig()
    res.configs.forEach(c => {
      if (form.hasOwnProperty(c.key)) {
        form[c.key] = parseInt(c.value)
      }
    })
  } catch (error) {
    console.error('获取配置失败:', error)
  }
}

async function handleSave() {
  loading.value = true
  try {
    for (const [key, value] of Object.entries(form)) {
      await updateSystemConfig(key, String(value))
    }
    ElMessage.success('保存成功')
  } catch (error) {
    console.error('保存失败:', error)
  } finally {
    loading.value = false
  }
}
</script>