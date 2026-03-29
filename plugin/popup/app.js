/**
 * ShareYourAi 插件主程序
 */

// API 基础地址（从 config.js 获取）
const API_BASE = config.API_BASE;

// 状态
let token = null;
let user = null;
let nodeId = null;
let currentAIPlatform = null; // 当前检测到的AI平台
let ws = null;

// 生成浏览器指纹
async function generateFingerprint() {
  const components = [];

  // 用户代理
  components.push(navigator.userAgent);

  // 语言
  components.push(navigator.language);

  // 屏幕信息
  components.push(screen.width + 'x' + screen.height + 'x' + screen.colorDepth);

  // 时区
  components.push(Intl.DateTimeFormat().resolvedOptions().timeZone);

  // 平台
  components.push(navigator.platform);

  // Canvas 指纹
  try {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    ctx.textBaseline = 'top';
    ctx.font = '14px Arial';
    ctx.fillText('fingerprint', 2, 2);
    components.push(canvas.toDataURL());
  } catch (e) {}

  // 生成哈希
  const str = components.join('|');
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }

  return 'NODE-' + Math.abs(hash).toString(36).toUpperCase();
}

// 检测当前AI平台
async function detectAIPlatform() {
  try {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tabs.length === 0) return null;

    const url = tabs[0].url;
    if (url.includes('grok.com')) return 'Grok';
    if (url.includes('sora.com')) return 'Sora';
    if (url.includes('runwayml.com')) return 'Runway';
    if (url.includes('gemini.google.com')) return 'Gemini';
    if (url.includes('chatgpt.com') || url.includes('chat.openai.com')) return 'ChatGPT';
    if (url.includes('claude.ai')) return 'Claude';

    return null;
  } catch (e) {
    return null;
  }
}

// 初始化节点
async function initNode() {
  // 检查是否已有节点ID
  const storage = await chrome.storage.local.get(['nodeId']);

  if (storage.nodeId) {
    nodeId = storage.nodeId;
  } else {
    // 生成新的节点ID
    nodeId = await generateFingerprint();
    await chrome.storage.local.set({ nodeId });
  }

  return nodeId;
}

// 初始化
document.addEventListener('DOMContentLoaded', async () => {
  // 从 storage 加载状态
  const result = await chrome.storage.local.get(['token', 'user', 'nodeId']);
  token = result.token;
  user = result.user;
  nodeId = result.nodeId;

  // 初始化节点
  await initNode();

  if (token && user) {
    showPage('panel-page');
    loadPanelData();
    connectWebSocket();
  }

  // 绑定事件监听器
  bindEventListeners();
});

// 绑定所有事件监听器
function bindEventListeners() {
  // 登录页面
  document.getElementById('btn-login')?.addEventListener('click', handleLogin);
  document.getElementById('btn-code-login-page')?.addEventListener('click', () => showPage('code-login-page'));
  document.getElementById('link-to-register')?.addEventListener('click', (e) => { e.preventDefault(); showPage('register-page'); });
  document.getElementById('link-to-forgot')?.addEventListener('click', (e) => { e.preventDefault(); showPage('forgot-page'); });

  // 邮箱验证码登录页面
  document.getElementById('btn-code-login')?.addEventListener('click', handleCodeLogin);
  document.getElementById('send-code-btn')?.addEventListener('click', () => sendCode('code-email', 'send-code-btn'));
  document.getElementById('btn-user-login-page')?.addEventListener('click', () => showPage('login-page'));
  document.getElementById('link-to-register2')?.addEventListener('click', (e) => { e.preventDefault(); showPage('register-page'); });

  // 注册页面
  document.getElementById('btn-register')?.addEventListener('click', handleRegister);
  document.getElementById('reg-send-code-btn')?.addEventListener('click', () => sendCode('reg-email', 'reg-send-code-btn'));
  document.getElementById('link-to-login-from-reg')?.addEventListener('click', (e) => { e.preventDefault(); showPage('login-page'); });

  // 忘记密码页面
  document.getElementById('btn-reset-password')?.addEventListener('click', handleResetPassword);
  document.getElementById('forgot-send-code-btn')?.addEventListener('click', () => sendCode('forgot-email', 'forgot-send-code-btn'));
  document.getElementById('link-to-login-from-forgot')?.addEventListener('click', (e) => { e.preventDefault(); showPage('login-page'); });

  // 控制面板
  document.getElementById('btn-logout')?.addEventListener('click', handleLogout);
  document.getElementById('btn-user-more')?.addEventListener('click', showUserDetail);
  document.getElementById('btn-close-user-modal')?.addEventListener('click', closeUserDetail);
  document.getElementById('stat-today-tasks-item')?.addEventListener('click', showTaskHistory);
  document.getElementById('btn-close-task-history')?.addEventListener('click', closeTaskHistory);
}

// 页面切换
function showPage(pageId) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById(pageId)?.classList.add('active');
}

// 切换密码显示
function togglePassword(inputId) {
  const input = document.getElementById(inputId);
  input.type = input.type === 'password' ? 'text' : 'password';
}

// 发送验证码
async function sendCode(emailInputId, btnId) {
  const email = document.getElementById(emailInputId)?.value;
  if (!email) {
    alert('请输入邮箱');
    return;
  }

  const btn = document.getElementById(btnId);
  btn.disabled = true;
  let countdown = 60;

  const timer = setInterval(() => {
    btn.textContent = `${countdown}秒后重试`;
    countdown--;
    if (countdown < 0) {
      clearInterval(timer);
      btn.textContent = '获取验证码';
      btn.disabled = false;
    }
  }, 1000);

  try {
    const response = await fetch(`${API_BASE}/auth/send-code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    });

    const data = await response.json();
    if (!data.success) {
      alert(data.message || '发送失败');
    }
  } catch (error) {
    console.error('发送验证码失败:', error);
    alert('发送失败，请稍后重试');
  }
}

// 登录
async function handleLogin() {
  const username = document.getElementById('login-username')?.value;
  const password = document.getElementById('login-password')?.value;

  if (!username || !password) {
    alert('请输入用户名和密码');
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });

    const data = await response.json();
    console.log('登录响应:', data);

    if (data.access_token) {
      token = data.access_token;
      user = data.user;

      // 保存到 storage
      try {
        await chrome.storage.local.set({ token, user });
        console.log('Token 已保存');
      } catch (storageError) {
        console.error('保存 Token 失败:', storageError);
        alert('保存登录信息失败: ' + storageError.message);
        return;
      }

      showPage('panel-page');
      loadPanelData();
    } else {
      alert(data.detail || '登录失败');
    }
  } catch (error) {
    console.error('登录失败:', error);
    alert('登录失败: ' + error.message);
  }
}

// 验证码登录
async function handleCodeLogin() {
  const email = document.getElementById('code-email')?.value;
  const code = document.getElementById('code-input')?.value;

  if (!email || !code) {
    alert('请输入邮箱和验证码');
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/auth/login-with-code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, code })
    });

    const data = await response.json();
    if (data.access_token) {
      token = data.access_token;
      user = data.user;

      await chrome.storage.local.set({ token, user });

      showPage('panel-page');
      loadPanelData();
      connectWebSocket();
    } else {
      alert(data.detail || '登录失败');
    }
  } catch (error) {
    console.error('登录失败:', error);
    alert('登录失败，请稍后重试');
  }
}

// 注册
async function handleRegister() {
  const username = document.getElementById('reg-username')?.value;
  const email = document.getElementById('reg-email')?.value;
  const code = document.getElementById('reg-code')?.value;
  const password = document.getElementById('reg-password')?.value;
  const confirm = document.getElementById('reg-confirm')?.value;
  const agreed = document.getElementById('agree-terms')?.checked;

  if (!username || !email || !code || !password || !confirm) {
    alert('请填写所有必填项');
    return;
  }

  if (password !== confirm) {
    alert('两次密码不一致');
    return;
  }

  if (!agreed) {
    alert('请阅读并同意用户协议');
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, email, code, password })
    });

    const data = await response.json();
    if (data.access_token) {
      token = data.access_token;
      user = data.user;

      await chrome.storage.local.set({ token, user });

      showPage('panel-page');
      loadPanelData();
      connectWebSocket();
    } else {
      alert(data.detail || '注册失败');
    }
  } catch (error) {
    console.error('注册失败:', error);
    alert('注册失败，请稍后重试');
  }
}

// 重置密码
async function handleResetPassword() {
  const email = document.getElementById('forgot-email')?.value;
  const code = document.getElementById('forgot-code')?.value;
  const password = document.getElementById('forgot-password')?.value;
  const confirm = document.getElementById('forgot-confirm')?.value;

  if (!email || !code || !password || !confirm) {
    alert('请填写所有必填项');
    return;
  }

  if (password !== confirm) {
    alert('两次密码不一致');
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/auth/reset-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, code, new_password: password })
    });

    const data = await response.json();
    if (data.success) {
      alert('密码重置成功');
      showPage('login-page');
    } else {
      alert(data.message || '重置失败');
    }
  } catch (error) {
    console.error('重置失败:', error);
    alert('重置失败，请稍后重试');
  }
}

// 退出登录
async function handleLogout() {
  if (ws) {
    ws.close();
  }

  await chrome.storage.local.remove(['token', 'user']);
  token = null;
  user = null;

  showPage('login-page');
}

// 加载面板数据
async function loadPanelData() {
  if (!user) return;

  // 显示用户信息
  document.getElementById('panel-username').textContent = user.username;
  document.getElementById('panel-balance').textContent = user.balance?.toFixed(2) || '0.00';

  // 显示节点ID
  document.getElementById('node-id').textContent = nodeId || '未初始化';

  // 检测当前AI平台
  currentAIPlatform = await detectAIPlatform();
  updatePlatformDisplay();

  // 加载节点统计
  try {
    const response = await fetch(`${API_BASE}/nodes/stats`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });

    const stats = await response.json();
    document.getElementById('stat-today-tasks').textContent = stats.today_tasks || 0;
    document.getElementById('stat-today-earnings').textContent = '¥' + (stats.today_earnings || 0).toFixed(2);
  } catch (error) {
    console.error('加载统计失败:', error);
  }

  // 加载当前任务
  updateCurrentTask();
}

// 更新平台显示
function updatePlatformDisplay() {
  const platformEl = document.getElementById('current-platform');
  if (platformEl) {
    if (currentAIPlatform) {
      platformEl.textContent = currentAIPlatform;
      platformEl.className = 'platform-badge platform-' + currentAIPlatform.toLowerCase();
    } else {
      platformEl.textContent = '未检测到';
      platformEl.className = 'platform-badge platform-none';
    }
  }
}

// 更新当前任务显示
async function updateCurrentTask() {
  try {
    const task = await chrome.runtime.sendMessage({ action: 'GET_TASK' });

    const taskCard = document.getElementById('task-card');

    if (task && task.task_id) {
      taskCard.style.display = 'block';
      document.getElementById('task-id-display').textContent = task.task_id;
      document.getElementById('task-model-display').textContent = task.model_id || '-';
      document.getElementById('task-prompt-display').textContent = task.prompt || '-';
      document.getElementById('task-prompt-display').title = task.prompt || '';

      // 展开popup窗口
      document.body.classList.add('task-expanded');
      document.getElementById('app').classList.add('task-expanded');
    } else {
      taskCard.style.display = 'none';

      // 收回popup窗口
      document.body.classList.remove('task-expanded');
      document.getElementById('app').classList.remove('task-expanded');
    }
  } catch (error) {
    // 静默失败，不打印日志
  }
}

// 定期更新任务显示
setInterval(updateCurrentTask, 2000);

// 显示用户详情（更多按钮）
async function showUserDetail() {
  const modal = document.getElementById('user-detail-modal');
  if (modal) {
    modal.classList.add('active');

    // 加载所有节点详情
    try {
      const response = await fetch(`${API_BASE}/nodes/my-nodes`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      const nodes = await response.json();
      renderNodesDetail(nodes);
    } catch (error) {
      console.error('加载节点详情失败:', error);
    }
  }
}

// 关闭用户详情
function closeUserDetail() {
  const modal = document.getElementById('user-detail-modal');
  if (modal) {
    modal.classList.remove('active');
  }
}

// 显示任务历史
async function showTaskHistory() {
  const modal = document.getElementById('task-history-modal');
  if (modal) {
    modal.classList.add('active');

    // 加载任务历史
    try {
      const response = await fetch(`${API_BASE}/nodes/tasks`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      const tasks = await response.json();
      renderTaskHistory(tasks);
    } catch (error) {
      console.error('加载任务历史失败:', error);
      document.getElementById('task-history-list').innerHTML = '<div class="no-data">加载失败</div>';
    }
  }
}

// 关闭任务历史
function closeTaskHistory() {
  const modal = document.getElementById('task-history-modal');
  if (modal) {
    modal.classList.remove('active');
  }
}

// 渲染任务历史列表
function renderTaskHistory(tasks) {
  const container = document.getElementById('task-history-list');
  if (!container) return;

  if (!tasks || tasks.length === 0) {
    container.innerHTML = '<div class="no-data">暂无任务记录</div>';
    return;
  }

  container.innerHTML = tasks.map(task => `
    <div class="task-history-item">
      <div class="task-history-header">
        <span class="task-history-id">${task.task_id}</span>
        <span class="task-history-status status-${task.status}">${getTaskStatusText(task.status)}</span>
      </div>
      <div class="task-history-info">
        <div class="task-history-model">模型: ${task.model_id || '-'}</div>
        <div class="task-history-time">${formatTime(task.create_time)}</div>
      </div>
    </div>
  `).join('');
}

// 获取任务状态文本
function getTaskStatusText(status) {
  const texts = {
    pending: '等待中',
    processing: '执行中',
    success: '成功',
    failed: '失败',
    timeout: '超时',
    cancelled: '已取消'
  };
  return texts[status] || status;
}

// 格式化时间
function formatTime(time) {
  if (!time) return '-';
  return new Date(time).toLocaleString('zh-CN');
}

// 渲染节点详情列表
function renderNodesDetail(nodes) {
  const container = document.getElementById('nodes-detail-list');
  if (!container) return;

  if (!nodes || nodes.length === 0) {
    container.innerHTML = '<div class="no-data">暂无节点数据</div>';
    return;
  }

  container.innerHTML = nodes.map(node => `
    <div class="node-detail-item ${node.node_id === nodeId ? 'current' : ''}">
      <div class="node-detail-header">
        <span class="node-id">${node.node_id}</span>
        ${node.node_id === nodeId ? '<span class="current-badge">当前设备</span>' : ''}
      </div>
      <div class="node-detail-info">
        <div class="node-platform">
          <span class="label">支持平台:</span>
          <span class="platform-list">${node.supported_models?.join(', ') || '-'}</span>
        </div>
        <div class="node-stats">
          <span>今日任务: ${node.today_tasks || 0}</span>
          <span>状态: ${node.status === 'online' ? '在线' : '离线'}</span>
        </div>
      </div>
    </div>
  `).join('');
}

// 更新 WebSocket 连接状态（从 background 获取）
async function updateWsStatus() {
  try {
    const status = await chrome.runtime.sendMessage({ action: 'GET_WS_STATUS' });
    const statusEl = document.getElementById('connection-status');

    if (status && status.connected) {
      statusEl.textContent = '已连接';
      statusEl.className = 'status-connected';
    } else {
      statusEl.textContent = '已断开';
      statusEl.className = 'status-disconnected';
    }
  } catch (error) {
    console.error('获取 WS 状态失败:', error);
  }
}

// 连接 WebSocket（通过 background）
function connectWebSocket() {
  chrome.runtime.sendMessage({ action: 'CONNECT_WS' });
  setTimeout(updateWsStatus, 1000);
}

// 定期更新连接状态显示
setInterval(updateWsStatus, 3000);