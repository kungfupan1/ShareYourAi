<template>
  <div class="test-generator">
    <el-card>
      <template #header>
        <span>调用测试</span>
      </template>

      <el-form :model="form" label-width="100px">
        <el-form-item label="模型选择">
          <el-select v-model="form.model_id" placeholder="选择模型" style="width: 100%;">
            <el-option
              v-for="model in models"
              :key="model.model_id"
              :label="model.name"
              :value="model.model_id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="提示词">
          <el-input
            v-model="form.prompt"
            type="textarea"
            :rows="4"
            placeholder="请输入视频生成提示词，例如：A cute cat playing with a ball in a sunny garden"
          />
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="视频时长">
              <el-input-number
                v-model="form.duration"
                :min="1"
                :max="60"
                :step="1"
                style="width: 100%;"
              />
              <span class="input-unit">秒</span>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="画面比例">
              <el-select v-model="form.aspect_ratio" placeholder="选择比例" style="width: 100%;">
                <el-option label="1:1" value="1:1" />
                <el-option label="2:3" value="2:3" />
                <el-option label="3:2" value="3:2" />
                <el-option label="9:16" value="9:16" />
                <el-option label="16:9" value="16:9" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="清晰度">
              <el-select v-model="form.resolution" placeholder="选择清晰度" style="width: 100%;">
                <el-option label="480p" value="480p" />
                <el-option label="720p" value="720p" />
                <el-option label="1080p" value="1080p" />
                <el-option label="1024×1024" value="1024x1024" />
                <el-option label="2048×2048" value="2048x2048" />
                <el-option label="4096×4096" value="4096x4096" />
                <el-option label="720×1280" value="720x1280" />
                <el-option label="1280×720" value="1280x720" />
                <el-option label="1080×1920" value="1080x1920" />
                <el-option label="1920×1080" value="1920x1080" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="参考图片">
          <el-upload
            class="image-uploader"
            :show-file-list="false"
            :before-upload="beforeImageUpload"
            accept="image/*"
          >
            <img v-if="imageUrl" :src="imageUrl" class="uploaded-image" />
            <el-icon v-else class="upload-icon"><Plus /></el-icon>
          </el-upload>
          <div class="upload-tip">可选，上传参考图片</div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="submitTask" :loading="loading">
            提交任务
          </el-button>
          <el-button @click="resetForm">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 任务状态 -->
    <el-card v-if="currentTask" style="margin-top: 20px;">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span>当前任务</span>
          <div>
            <el-tag :type="getTaskStatusType(currentTask.status)" style="margin-right: 10px;">
              {{ getTaskStatusText(currentTask.status) }}
            </el-tag>
            <el-button
              v-if="['pending', 'processing'].includes(currentTask.status)"
              type="danger"
              size="small"
              @click="cancelTask"
              :loading="cancelling"
            >
              取消任务
            </el-button>
          </div>
        </div>
      </template>

      <el-descriptions :column="2" border>
        <el-descriptions-item label="任务ID">{{ currentTask.task_id }}</el-descriptions-item>
        <el-descriptions-item label="模型">{{ currentTask.model_id }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ currentTask.status }}</el-descriptions-item>
        <el-descriptions-item label="节点">{{ currentTask.assigned_node_id || '-' }}</el-descriptions-item>
        <el-descriptions-item label="提示词" :span="2">{{ currentTask.prompt }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatTime(currentTask.create_time) }}</el-descriptions-item>
        <el-descriptions-item label="耗时">{{ currentTask.duration_seconds ? currentTask.duration_seconds + '秒' : '-' }}</el-descriptions-item>
      </el-descriptions>

      <!-- 结果展示 -->
      <div v-if="currentTask.status === 'success'" style="margin-top: 20px;">
        <h4>生成结果</h4>

        <!-- 视频预览 -->
        <div v-if="currentTask.result_url" class="video-preview-wrapper">
          <video
            ref="videoPlayer"
            :src="getVideoUrl(currentTask.result_url)"
            controls
            class="video-player"
            @loadedmetadata="onVideoLoaded"
            @error="handleVideoError"
          />
        </div>

        <!-- 文件信息 -->
        <div class="file-info">
          <p><strong>文件大小：</strong>{{ formatFileSize(currentTask.file_size) }}</p>
          <p><strong>格式：</strong>{{ currentTask.file_format || 'mp4' }}</p>
        </div>

        <!-- 操作按钮 -->
        <div class="action-buttons">
          <el-button type="primary" @click="downloadResult">
            <el-icon><Download /></el-icon> 下载视频
          </el-button>
          <el-button @click="copyResultUrl">
            <el-icon><Link /></el-icon> 复制链接
          </el-button>
          <el-button @click="openInNewTab">
            <el-icon><View /></el-icon> 新窗口打开
          </el-button>
        </div>
      </div>

      <!-- 错误信息 -->
      <el-alert
        v-if="currentTask.status === 'failed'"
        :title="currentTask.error_message || '任务失败'"
        type="error"
        style="margin-top: 20px;"
      />

      <!-- 刷新按钮 -->
      <div style="margin-top: 20px;">
        <el-button @click="refreshTask" :loading="refreshing">
          刷新状态
        </el-button>
      </div>
    </el-card>

    <!-- 历史记录 -->
    <el-card style="margin-top: 20px;">
      <template #header>
        <span>测试历史</span>
      </template>

      <el-table :data="taskHistory" style="width: 100%">
        <el-table-column prop="task_id" label="任务ID" width="150" />
        <el-table-column prop="model_id" label="模型" width="120" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getTaskStatusType(row.status)" size="small">
              {{ getTaskStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="prompt" label="提示词" show-overflow-tooltip />
        <el-table-column prop="create_time" label="时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.create_time) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="viewTask(row)">
              查看
            </el-button>
            <el-button
              v-if="row.status === 'success' && row.result_url"
              type="success"
              link
              size="small"
              @click="previewVideo(row)"
            >
              预览
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { Plus, Download, Link, View } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import request from '@/api/request'

const form = ref({
  model_id: 'grok_video',
  prompt: '',
  duration: 5,
  aspect_ratio: '16:9',
  resolution: '1080p'
})

const models = ref([])
const imageUrl = ref('')
const imageBase64 = ref('')
const loading = ref(false)
const cancelling = ref(false)
const currentTask = ref(null)
const taskHistory = ref([])
const refreshing = ref(false)
const videoPlayer = ref(null)
let pollTimer = null

const getUserId = () => JSON.parse(localStorage.getItem('user'))?.id

onMounted(async () => {
  await fetchModels()
  await fetchHistory()
})

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
  }
})

async function fetchModels() {
  try {
    const res = await request.get(`/admin/models?user_id=${getUserId()}`)
    models.value = res.data || res
  } catch (error) {
    console.error('获取模型列表失败:', error)
  }
}

async function fetchHistory() {
  try {
    const res = await request.get('/admin/tasks', {
      params: { user_id: getUserId(), limit: 10 }
    })
    taskHistory.value = res.tasks || res.data || res
  } catch (error) {
    console.error('获取历史记录失败:', error)
  }
}

function beforeImageUpload(file) {
  const reader = new FileReader()
  reader.onload = (e) => {
    imageUrl.value = e.target.result
    imageBase64.value = e.target.result
  }
  reader.readAsDataURL(file)
  return false
}

async function submitTask() {
  if (!form.value.prompt) {
    ElMessage.warning('请输入提示词')
    return
  }

  loading.value = true

  try {
    const res = await request.post('/tasks/submit', {
      model_id: form.value.model_id,
      prompt: form.value.prompt,
      images: imageBase64.value ? [imageBase64.value] : null,
      params: {
        duration: form.value.duration,
        aspect_ratio: form.value.aspect_ratio,
        resolution: form.value.resolution
      }
    })

    if (res.success) {
      ElMessage.success('任务已提交')
      currentTask.value = {
        task_id: res.data.task_id,
        model_id: form.value.model_id,
        prompt: form.value.prompt,
        status: 'pending'
      }

      // 开始轮询任务状态
      startPolling(res.data.task_id)

      // 刷新历史
      await fetchHistory()
    }
  } catch (error) {
    ElMessage.error('提交失败: ' + error.message)
  } finally {
    loading.value = false
  }
}

function startPolling(taskId) {
  if (pollTimer) {
    clearInterval(pollTimer)
  }

  pollTimer = setInterval(async () => {
    await refreshTask()
  }, 3000)
}

async function refreshTask() {
  if (!currentTask.value) return

  refreshing.value = true

  try {
    const res = await request.get(`/admin/tasks/${currentTask.value.task_id}`, {
      params: { user_id: getUserId() }
    })
    currentTask.value = res.task || res

    // 如果任务完成或失败，停止轮询
    if (['success', 'failed', 'timeout', 'cancelled'].includes(res.task?.status || res.status)) {
      if (pollTimer) {
        clearInterval(pollTimer)
        pollTimer = null
      }
      await fetchHistory()
    }
  } catch (error) {
    console.error('刷新任务状态失败:', error)
  } finally {
    refreshing.value = false
  }
}

async function cancelTask() {
  if (!currentTask.value) return

  cancelling.value = true

  try {
    await request.post(`/admin/tasks/${currentTask.value.task_id}/cancel`, null, {
      params: { user_id: getUserId() }
    })
    ElMessage.success('任务已取消')

    // 停止轮询
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }

    // 刷新状态
    await refreshTask()
    await fetchHistory()
  } catch (error) {
    ElMessage.error('取消失败: ' + error.message)
  } finally {
    cancelling.value = false
  }
}

function viewTask(task) {
  currentTask.value = { ...task }

  if (!['success', 'failed', 'timeout', 'cancelled'].includes(task.status)) {
    startPolling(task.task_id)
  }
}

function resetForm() {
  form.value = {
    model_id: 'grok_video',
    prompt: '',
    duration: 5,
    aspect_ratio: '16:9',
    resolution: '1080p'
  }
  imageUrl.value = ''
  imageBase64.value = ''
}

function downloadResult() {
    if (!currentTask.value?.result_url) return
    const url = getVideoUrl(currentTask.value.result_url)
    const link = document.createElement('a')
    link.href = url
    link.download = `${currentTask.value.task_id}.mp4`
    link.target = '_blank'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  // 获取完整的视频 URL
  function getVideoUrl(url) {
    if (!url) return ''
    // 如果是相对路径，添加后端地址
    if (url.startsWith('/')) {
      return 'http://127.0.0.1:8000' + url
    }
    // 如果是带签名的 COS URL（直接返回）
    if (url.startsWith('http')) {
      return url
    }
    // cos:// 格式（需要后端处理）
    if (url.startsWith('cos://')) {
      return `http://127.0.0.1:8000/api/tasks/download/${currentTask.value?.task_id}`
    }
    return url
  }

  // 格式化文件大小
  function formatFileSize(bytes) {
    if (!bytes) return '-'
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
  }

  // 处理视频加载错误
  function handleVideoError(e) {
    console.error('视频加载失败:', e)
    ElMessage.error('视频加载失败，请尝试下载或新窗口打开')
  }

  // 视频加载完成，自适应尺寸
  function onVideoLoaded(e) {
    const video = e.target
    const width = video.videoWidth
    const height = video.videoHeight
    console.log(`视频尺寸: ${width}x${height}`)

    // 根据视频比例设置容器宽度
    const wrapper = video.closest('.video-preview-wrapper')
    if (wrapper && width && height) {
      const aspectRatio = width / height
      if (aspectRatio > 1.5) {
        // 宽视频（如 16:9）
        wrapper.style.maxWidth = '800px'
      } else if (aspectRatio < 0.8) {
        // 高视频（如 9:16）
        wrapper.style.maxWidth = '400px'
      } else {
        // 近似正方形
        wrapper.style.maxWidth = '500px'
      }
    }
  }

  // 复制链接
  function copyResultUrl() {
    if (!currentTask.value?.result_url) return
    const url = getVideoUrl(currentTask.value.result_url)
    navigator.clipboard.writeText(url).then(() => {
      ElMessage.success('链接已复制到剪贴板')
    }).catch(() => {
      ElMessage.error('复制失败')
    })
  }

  // 新窗口打开
  function openInNewTab() {
    if (!currentTask.value?.result_url) return
    const url = getVideoUrl(currentTask.value.result_url)
    window.open(url, '_blank')
  }

  // 预览历史视频
  function previewVideo(task) {
    if (task.result_url) {
      window.open(getVideoUrl(task.result_url), '_blank')
    }
  }

function getTaskStatusType(status) {
  const types = {
    pending: 'info',
    processing: 'warning',
    success: 'success',
    failed: 'danger',
    timeout: 'danger',
    cancelled: 'info'
  }
  return types[status] || 'info'
}

function getTaskStatusText(status) {
  const texts = {
    pending: '等待中',
    processing: '处理中',
    success: '成功',
    failed: '失败',
    timeout: '超时',
    cancelled: '已取消'
  }
  return texts[status] || status
}

function formatTime(time) {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}
</script>

<style scoped>
.test-generator {
  padding: 0;
}

.image-uploader {
  border: 1px dashed #d9d9d9;
  border-radius: 6px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  width: 200px;
  height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.image-uploader:hover {
  border-color: #409eff;
}

.uploaded-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.upload-icon {
  font-size: 28px;
  color: #8c939d;
}

.upload-tip {
  margin-top: 8px;
  color: #999;
  font-size: 12px;
}

.input-unit {
  margin-left: 8px;
  color: #666;
  font-size: 14px;
}

.video-preview-wrapper {
  margin: 15px auto;
  border-radius: 8px;
  overflow: hidden;
  background: #000;
  max-width: 800px;
  width: fit-content;
}

.video-player {
  display: block;
  max-height: 500px;
  width: auto;
  max-width: 100%;
}

.file-info {
  background: #f5f7fa;
  padding: 12px 16px;
  border-radius: 6px;
  margin: 15px 0;
}

.file-info p {
  margin: 4px 0;
  color: #606266;
}

.action-buttons {
  display: flex;
  gap: 10px;
  margin-top: 15px;
}
</style>