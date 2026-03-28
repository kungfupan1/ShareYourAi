import request from './request'

// 登录
export function login(data) {
  return request.post('/auth/login', data)
}

// 获取当前用户
export function getCurrentUser() {
  return request.get('/auth/me')
}

// 退出登录
export function logout() {
  return request.post('/auth/logout')
}

// 发送验证码
export function sendCode(email) {
  return request.post('/auth/send-code', { email })
}