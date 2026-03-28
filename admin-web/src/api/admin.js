import request from './request'

// 获取仪表盘数据
export function getDashboard() {
  const userId = JSON.parse(localStorage.getItem('user'))?.id
  return request.get(`/admin/dashboard?user_id=${userId}`)
}

// 获取用户列表
export function getUsers(params) {
  const userId = JSON.parse(localStorage.getItem('user'))?.id
  return request.get('/admin/users', { params: { user_id: userId, ...params } })
}

// 切换黑名单
export function toggleBlacklist(userId, targetId) {
  return request.post(`/admin/users/${targetId}/blacklist?user_id=${userId}`)
}

// 获取节点列表
export function getNodes(params) {
  const userId = JSON.parse(localStorage.getItem('user'))?.id
  return request.get('/admin/nodes', { params: { user_id: userId, ...params } })
}

// 获取模型列表
export function getModels() {
  const userId = JSON.parse(localStorage.getItem('user'))?.id
  return request.get(`/admin/models?user_id=${userId}`)
}

// 创建模型
export function createModel(data) {
  const userId = JSON.parse(localStorage.getItem('user'))?.id
  return request.post(`/admin/models?user_id=${userId}`, data)
}

// 更新模型
export function updateModel(modelId, data) {
  const userId = JSON.parse(localStorage.getItem('user'))?.id
  return request.put(`/admin/models/${modelId}?user_id=${userId}`, data)
}

// 删除模型
export function deleteModel(modelId) {
  const userId = JSON.parse(localStorage.getItem('user'))?.id
  return request.delete(`/admin/models/${modelId}?user_id=${userId}`)
}

// 获取收益审核列表
export function getEarnings(params) {
  const userId = JSON.parse(localStorage.getItem('user'))?.id
  return request.get('/admin/earnings', { params: { user_id: userId, ...params } })
}

// 通过收益审核
export function approveEarning(taskId) {
  const userId = JSON.parse(localStorage.getItem('user'))?.id
  return request.post(`/admin/earnings/${taskId}/approve?user_id=${userId}`)
}

// 拒绝收益
export function rejectEarning(taskId, reason) {
  const userId = JSON.parse(localStorage.getItem('user'))?.id
  return request.post(`/admin/earnings/${taskId}/reject?user_id=${userId}`, null, { params: { reason } })
}

// 获取提现列表
export function getWithdrawals(params) {
  const userId = JSON.parse(localStorage.getItem('user'))?.id
  return request.get('/admin/withdrawals', { params: { user_id: userId, ...params } })
}

// 完成提现
export function completeWithdrawal(withdrawalId, transactionId) {
  const userId = JSON.parse(localStorage.getItem('user'))?.id
  return request.post(`/admin/withdrawals/${withdrawalId}/complete?user_id=${userId}`, null, { params: { transaction_id: transactionId } })
}

// 拒绝提现
export function rejectWithdrawal(withdrawalId, reason) {
  const userId = JSON.parse(localStorage.getItem('user'))?.id
  return request.post(`/admin/withdrawals/${withdrawalId}/reject?user_id=${userId}`, null, { params: { reason } })
}

// 获取派单策略
export function getDispatcherStrategy() {
  const userId = JSON.parse(localStorage.getItem('user'))?.id
  return request.get(`/admin/dispatcher-strategy?user_id=${userId}`)
}

// 更新派单策略
export function updateDispatcherStrategy(data) {
  const userId = JSON.parse(localStorage.getItem('user'))?.id
  return request.post(`/admin/dispatcher-strategy?user_id=${userId}`, data)
}

// 获取系统配置
export function getSystemConfig() {
  const userId = JSON.parse(localStorage.getItem('user'))?.id
  return request.get(`/admin/system-config?user_id=${userId}`)
}

// 更新系统配置
export function updateSystemConfig(key, value) {
  const userId = JSON.parse(localStorage.getItem('user'))?.id
  return request.post(`/admin/system-config?user_id=${userId}`, null, { params: { key, value } })
}