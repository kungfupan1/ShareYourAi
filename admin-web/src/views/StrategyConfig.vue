<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <span>派单策略配置</span>
      </template>

      <el-form :model="form" label-width="150px" style="max-width: 600px;">
        <el-form-item label="策略类型">
          <el-radio-group v-model="form.strategy_type">
            <el-radio label="random">随机策略</el-radio>
            <el-radio label="best_node">优胜略汰策略</el-radio>
          </el-radio-group>
        </el-form-item>

        <template v-if="form.strategy_type === 'best_node'">
          <el-divider>评分权重配置</el-divider>

          <el-form-item label="成功率权重">
            <el-slider v-model="form.success_rate_weight" :min="0" :max="1" :step="0.1" show-input />
          </el-form-item>

          <el-form-item label="响应速度权重">
            <el-slider v-model="form.speed_weight" :min="0" :max="1" :step="0.1" show-input />
          </el-form-item>

          <el-form-item label="稳定性权重">
            <el-slider v-model="form.stability_weight" :min="0" :max="1" :step="0.1" show-input />
          </el-form-item>

          <el-alert
            :title="`权重之和: ${(form.success_rate_weight + form.speed_weight + form.stability_weight).toFixed(1)}`"
            :type="Math.abs(form.success_rate_weight + form.speed_weight + form.stability_weight - 1) < 0.01 ? 'success' : 'warning'"
            style="margin-bottom: 20px;"
          />

          <el-divider>阈值配置</el-divider>

          <el-form-item label="新节点基础评分">
            <el-input-number v-model="form.base_score" :min="0" :max="100" />
          </el-form-item>

          <el-form-item label="最低统计任务数">
            <el-input-number v-model="form.min_tasks_for_score" :min="1" :max="50" />
          </el-form-item>

          <el-form-item label="连续失败惩罚系数">
            <el-input-number v-model="form.consecutive_fail_penalty" :min="0" :max="1" :step="0.1" :precision="1" />
          </el-form-item>

          <el-form-item label="最近任务统计数">
            <el-input-number v-model="form.recent_tasks_count" :min="5" :max="50" />
          </el-form-item>
        </template>

        <el-form-item>
          <el-button type="primary" @click="handleSave" :loading="loading">保存配置</el-button>
          <el-button @click="fetchConfig">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getDispatcherStrategy, updateDispatcherStrategy } from '@/api/admin'

const loading = ref(false)

const form = reactive({
  strategy_type: 'best_node',
  success_rate_weight: 0.5,
  speed_weight: 0.3,
  stability_weight: 0.2,
  base_score: 50,
  min_tasks_for_score: 10,
  consecutive_fail_penalty: 0.5,
  recent_tasks_count: 10
})

onMounted(() => {
  fetchConfig()
})

async function fetchConfig() {
  try {
    const res = await getDispatcherStrategy()
    Object.assign(form, res)
  } catch (error) {
    console.error('获取配置失败:', error)
  }
}

async function handleSave() {
  const totalWeight = form.success_rate_weight + form.speed_weight + form.stability_weight
  if (Math.abs(totalWeight - 1) > 0.01) {
    ElMessage.warning('权重之和必须等于 1')
    return
  }

  loading.value = true
  try {
    await updateDispatcherStrategy(form)
    ElMessage.success('保存成功')
  } catch (error) {
    console.error('保存失败:', error)
  } finally {
    loading.value = false
  }
}
</script>