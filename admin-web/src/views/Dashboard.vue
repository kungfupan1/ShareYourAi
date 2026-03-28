<template>
  <div class="dashboard">
    <el-row :gutter="20">
      <!-- 统计卡片 -->
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #4F46E5;">
            <el-icon><Monitor /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.online_nodes }}</div>
            <div class="stat-label">在线节点</div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #10B981;">
            <el-icon><Loading /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.processing_tasks }}</div>
            <div class="stat-label">处理中</div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #F59E0B;">
            <el-icon><List /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.today_tasks }}</div>
            <div class="stat-label">今日任务</div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #EF4444;">
            <el-icon><Coin /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">¥{{ stats.today_earnings?.toFixed(2) || '0.00' }}</div>
            <div class="stat-label">今日收益</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px;">
      <!-- 任务趋势图 -->
      <el-col :span="16">
        <el-card>
          <template #header>
            <span>任务趋势（近7天）</span>
          </template>
          <div ref="chartRef" style="height: 300px;"></div>
        </el-card>
      </el-col>

      <!-- 节点状态分布 -->
      <el-col :span="8">
        <el-card>
          <template #header>
            <span>节点状态分布</span>
          </template>
          <div class="node-status">
            <div class="status-item">
              <span class="status-dot" style="background: #10B981;"></span>
              <span>空闲</span>
              <span class="status-count">{{ stats.node_status_distribution?.idle || 0 }}</span>
            </div>
            <div class="status-item">
              <span class="status-dot" style="background: #F59E0B;"></span>
              <span>忙碌</span>
              <span class="status-count">{{ stats.node_status_distribution?.busy || 0 }}</span>
            </div>
            <div class="status-item">
              <span class="status-dot" style="background: #9CA3AF;"></span>
              <span>离线</span>
              <span class="status-count">{{ stats.node_status_distribution?.offline || 0 }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px;">
      <!-- 最近异常 -->
      <el-col :span="24">
        <el-card>
          <template #header>
            <span>最近异常告警</span>
          </template>
          <el-table :data="stats.recent_risks" style="width: 100%">
            <el-table-column prop="risk_type" label="类型" width="120" />
            <el-table-column prop="risk_level" label="等级" width="100">
              <template #default="{ row }">
                <el-tag
                  :type="row.risk_level === 'critical' ? 'danger' : row.risk_level === 'high' ? 'warning' : 'info'"
                >
                  {{ row.risk_level }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="描述" />
            <el-table-column prop="create_time" label="时间" width="180">
              <template #default="{ row }">
                {{ formatTime(row.create_time) }}
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Monitor, Loading, List, Coin } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { getDashboard } from '@/api/admin'

const chartRef = ref()
const stats = ref({})

onMounted(async () => {
  await fetchStats()
  initChart()
})

async function fetchStats() {
  try {
    stats.value = await getDashboard()
  } catch (error) {
    console.error('获取统计失败:', error)
  }
}

function initChart() {
  const chart = echarts.init(chartRef.value)

  const dates = stats.value.trend_data?.map(d => d.date) || []
  const totals = stats.value.trend_data?.map(d => d.total) || []
  const successes = stats.value.trend_data?.map(d => d.success) || []

  chart.setOption({
    tooltip: {
      trigger: 'axis'
    },
    legend: {
      data: ['任务量', '成功量']
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: dates
    },
    yAxis: {
      type: 'value'
    },
    series: [
      {
        name: '任务量',
        type: 'line',
        data: totals,
        smooth: true,
        itemStyle: { color: '#4F46E5' }
      },
      {
        name: '成功量',
        type: 'line',
        data: successes,
        smooth: true,
        itemStyle: { color: '#10B981' }
      }
    ]
  })

  window.addEventListener('resize', () => chart.resize())
}

function formatTime(time) {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}
</script>

<style scoped>
.stat-card {
  display: flex;
  align-items: center;
}

.stat-card :deep(.el-card__body) {
  display: flex;
  align-items: center;
  width: 100%;
}

.stat-icon {
  width: 50px;
  height: 50px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 24px;
}

.stat-info {
  margin-left: 15px;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: #333;
}

.stat-label {
  font-size: 14px;
  color: #999;
  margin-top: 4px;
}

.node-status {
  padding: 20px 0;
}

.status-item {
  display: flex;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
}

.status-item:last-child {
  border-bottom: none;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-right: 10px;
}

.status-count {
  margin-left: auto;
  font-weight: 600;
}
</style>