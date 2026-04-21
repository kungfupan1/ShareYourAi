/**
 * 平台客户管理 API
 */
import request from './request'

// 获取平台客户列表
export function getPlatformList(params) {
  return request.get('/admin/platforms', { params })
}

// 创建平台客户
export function createPlatform(data) {
  return request.post('/admin/platforms', data, { params: { user_id: 1 } })
}

// 获取平台客户详情
export function getPlatformDetail(clientId, params) {
  return request.get(`/admin/platforms/${clientId}`, { params })
}

// 更新平台客户
export function updatePlatform(clientId, data) {
  return request.put(`/admin/platforms/${clientId}`, data, { params: { user_id: 1 } })
}

// 平台充值
export function rechargePlatform(clientId, data) {
  return request.post(`/admin/platforms/${clientId}/recharge`, data, { params: { user_id: 1 } })
}

// 调整余额
export function adjustPlatformBalance(clientId, data) {
  return request.post(`/admin/platforms/${clientId}/adjust`, data, { params: { user_id: 1 } })
}

// 重置 API Key
export function resetApiKey(clientId) {
  return request.post(`/admin/platforms/${clientId}/reset-key`, null, { params: { user_id: 1 } })
}

// 获取交易记录
export function getTransactions(clientId, params) {
  return request.get(`/admin/platforms/${clientId}/transactions`, { params: { user_id: 1, ...params } })
}

// 获取调用日志
export function getCallLogs(clientId, params) {
  return request.get(`/admin/platforms/${clientId}/call-logs`, { params: { user_id: 1, ...params } })
}

// 获取平台任务
export function getClientTasks(clientId, params) {
  return request.get(`/admin/platforms/${clientId}/tasks`, { params: { user_id: 1, ...params } })
}

// 获取平台统计
export function getClientStats(clientId) {
  return request.get(`/admin/platforms/${clientId}/stats`, { params: { user_id: 1 } })
}