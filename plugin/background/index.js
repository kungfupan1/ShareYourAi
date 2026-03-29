/**
 * Background Service Worker
 */

// ============ 环境配置 ============
// 切换环境修改这里
const ENV = 'development';

const CONFIG = {
  development: {
    API_BASE: 'http://127.0.0.1:8000/api',
    WS_URL: 'ws://127.0.0.1:8000/ws'
  },
  production: {
    API_BASE: 'https://shareyouai.winepipeline.com/api',
    WS_URL: 'wss://shareyouai.winepipeline.com/ws'
  }
};

const API_BASE = CONFIG[ENV].API_BASE;
const WS_URL = CONFIG[ENV].WS_URL;

let ws = null;
let reconnectTimer = null;
let currentTask = null;

// ============ 通知功能 ============

function showNotification(title, message, type = 'info') {
  chrome.notifications.create({
    type: 'basic',
    iconUrl: 'icons/icon128.png',
    title: title,
    message: message,
    priority: type === 'error' ? 2 : 1
  });
}

// 更新插件图标徽章
function updateBadge(text, color = '#4CAF50') {
  chrome.action.setBadgeText({ text: text });
  chrome.action.setBadgeBackgroundColor({ color: color });
}

// ============ 初始化 ============

// 初始化
chrome.storage.onChanged.addListener((changes, namespace) => {
  if (namespace === 'local' && changes.token) {
    if (changes.token.newValue) {
      connectWebSocket();
    } else {
      disconnectWebSocket();
    }
  }
});

// 启动时检查是否已登录
chrome.storage.local.get(['token', 'nodeId'], (result) => {
  if (result.token && result.nodeId) {
    connectWebSocket();
  }
});

// 连接 WebSocket
async function connectWebSocket() {
  const storage = await chrome.storage.local.get(['token', 'nodeId']);
  if (!storage.token || !storage.nodeId) {
    console.log('缺少 token 或 nodeId，无法连接 WebSocket');
    return;
  }

  if (ws && ws.readyState === WebSocket.OPEN) {
    console.log('WebSocket 已连接');
    return;
  }

  const wsUrl = `${WS_URL}/${storage.token}/${storage.nodeId}`;
  console.log('正在连接 WebSocket:', wsUrl);

  try {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket 已连接');
      chrome.storage.local.set({ wsConnected: true });
      // 重置重连计时器
      if (reconnectTimer) {
        clearInterval(reconnectTimer);
        reconnectTimer = null;
      }
    };

    ws.onclose = () => {
      console.log('WebSocket 已断开');
      chrome.storage.local.set({ wsConnected: false });
      ws = null;
      // 5秒后重连
      if (!reconnectTimer) {
        reconnectTimer = setTimeout(() => {
          reconnectTimer = null;
          connectWebSocket();
        }, 5000);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket 错误:', error);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('收到 WebSocket 消息:', data);
        handleWebSocketMessage(data);
      } catch (e) {
        console.error('解析消息失败:', e);
      }
    };
  } catch (error) {
    console.error('创建 WebSocket 失败:', error);
  }
}

// 断开 WebSocket
function disconnectWebSocket() {
  if (ws) {
    ws.close();
    ws = null;
  }
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  chrome.storage.local.set({ wsConnected: false });
}

// 处理 WebSocket 消息
function handleWebSocketMessage(data) {
  switch (data.type) {
    case 'connected':
      console.log('节点已连接:', data.node_id);
      break;
    case 'new_task':
      handleNewTask(data.task);
      break;
    case 'ping':
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'pong' }));
      }
      break;
    case 'kicked':
      console.log('被踢下线:', data.reason);
      disconnectWebSocket();
      break;
  }
}

// 监听来自 popup 或 content script 的消息
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  switch (message.action) {
    case 'NEW_TASK':
      handleNewTask(message.task);
      break;
    case 'TASK_RESULT':
      submitTaskResult(message.result);
      break;
    case 'GET_UPLOAD_CREDENTIAL':
      // 获取预签名URL
      getUploadCredential(message.taskId).then(sendResponse);
      return true;
    case 'UPLOAD_VIDEO_FALLBACK':
      // Fallback上传：Background下载并上传（CSP被拦截时）
      uploadVideoFallback(message.taskId, message.videoUrl).then(sendResponse);
      return true;
    case 'TASK_COMPLETE':
      // 任务完成
      handleTaskComplete(message.data);
      sendResponse({ success: true });
      return true;
    case 'TASK_FAILED':
      // 任务失败
      handleTaskFailed(message.data);
      sendResponse({ success: true });
      return true;
    case 'TASK_TIMEOUT':
      // 任务超时
      updateBadge('超时', '#9E9E9E');
      showNotification('ShareYourAi', '任务超时，未检测到视频');
      currentTask = null;
      chrome.storage.local.remove(['currentTask']);
      sendResponse({ success: true });
      break;
    case 'STATUS_UPDATE':
      // 状态更新，更新徽章和日志
      console.log('状态更新:', message.status);
      if (message.type === 'error') {
        updateBadge('错误', '#F44336');
      }
      sendResponse({ success: true });
      break;
    case 'GET_TASK':
      chrome.storage.local.get(['currentTask'], (result) => {
        sendResponse(result.currentTask);
      });
      return true;
    case 'CHECK_TASK_STATUS':
      // 检查后端任务状态
      checkTaskStatusFromBackend(message.taskId).then(sendResponse);
      return true;
    case 'CLEAR_TASK':
      // 清理存储的任务
      currentTask = null;
      chrome.storage.local.remove(['currentTask']);
      console.log('任务已清理');
      sendResponse({ success: true });
      break;
    case 'GET_WS_STATUS':
      sendResponse({
        connected: ws && ws.readyState === WebSocket.OPEN,
        readyState: ws ? ws.readyState : null
      });
      return true;
    case 'CONNECT_WS':
      connectWebSocket();
      sendResponse({ success: true });
      return true;
    case 'DISCONNECT_WS':
      disconnectWebSocket();
      sendResponse({ success: true });
      return true;
    case 'CLOSE_CURRENT_TAB':
      // 关闭当前任务标签页
      closeCurrentTaskTab();
      sendResponse({ success: true });
      return true;
  }
});

// 处理新任务 - 每次都新建标签页
async function handleNewTask(task) {
  console.log('处理新任务:', task);
  currentTask = task;

  // 存储到 chrome.storage（不包含 images 大数据，避免超出配额）
  const taskForStorage = {
    task_id: task.task_id,
    model_id: task.model_id,
    prompt: task.prompt,
    page_url: task.page_url,
    params: task.params,
    create_time: task.create_time || new Date().toISOString()
  };
  await chrome.storage.local.set({ currentTask: taskForStorage });

  // 显示通知和徽章
  showNotification('ShareYourAi', `开始执行任务: ${task.prompt?.substring(0, 30)}...`);
  updateBadge('执行中', '#FF9800');

  // 获取任务 URL
  const defaultModelUrls = {
    'grok_video': 'https://grok.com',
    'sora2_video': 'https://sora.com',
    'runway_video': 'https://runwayml.com'
  };

  const url = task.page_url || defaultModelUrls[task.model_id];
  console.log('任务 URL:', url);

  if (url) {
    try {
      // 始终新建标签页
      const targetTab = await chrome.tabs.create({ url });
      console.log('已新建标签页:', url, 'tabId:', targetTab.id);

      // 存储当前任务标签页ID
      await chrome.storage.local.set({ currentTaskTabId: targetTab.id });

      // 等待页面加载完成（最多30秒）
      await new Promise(resolve => {
        if (targetTab.status === 'complete') {
          resolve();
        } else {
          const listener = (tabId, changeInfo) => {
            if (tabId === targetTab.id && changeInfo.status === 'complete') {
              chrome.tabs.onUpdated.removeListener(listener);
              resolve();
            }
          };
          chrome.tabs.onUpdated.addListener(listener);
          setTimeout(resolve, 30000); // 增加超时时间到30秒
        }
      });

      // 额外等待页面稳定和VPN翻墙（增加到5秒）
      console.log('页面加载完成，等待5秒让页面稳定...');
      await new Promise(resolve => setTimeout(resolve, 5000));

      // 发送任务给 content script（使用完整的 task，包含 images）
      console.log('发送 START_TASK 给 content script');
      let sent = false;
      for (let i = 0; i < 5 && !sent; i++) {
        try {
          const response = await chrome.tabs.sendMessage(targetTab.id, {
            action: 'START_TASK',
            task: task  // 完整任务数据（内存中的，包含 images）
          });
          console.log('Content script 响应:', response);
          sent = true;
        } catch (error) {
          console.log(`第${i + 1}次发送失败，尝试注入 content script:`, error.message);
          try {
            await chrome.scripting.executeScript({
              target: { tabId: targetTab.id },
              files: ['content/index.js']
            });
            // 每次重试等待更长时间
            await new Promise(resolve => setTimeout(resolve, 2000 + i * 1000));
          } catch (e) {
            console.error('注入失败:', e);
          }
        }
      }

      if (!sent) {
        console.error('多次重试后仍无法发送任务');
        showNotification('ShareYourAi', '任务发送失败，请检查VPN连接', 'error');
        updateBadge('失败', '#F44336');
      }
    } catch (error) {
      console.error('新建标签页失败:', error);
      showNotification('ShareYourAi', '任务执行失败: ' + error.message, 'error');
      updateBadge('失败', '#F44336');
    }
  }
}

// 提交任务结果
async function submitTaskResult(result) {
  const storage = await chrome.storage.local.get(['token', 'nodeId']);

  try {
    const response = await fetch(`${API_BASE}/tasks/result`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${storage.token}`
      },
      body: JSON.stringify({
        task_id: result.task_id,
        node_id: storage.nodeId,
        status: result.status,
        result_url: result.result_url,
        error_message: result.error_message,
        proof: result.proof,
        file_size: result.file_size,
        file_format: result.file_format
      })
    });

    const data = await response.json();
    console.log('任务结果提交:', data);

    if (data.success) {
      updateBadge('完成', '#4CAF50');
      showNotification('ShareYourAi', '任务完成！');
      currentTask = null;
      await chrome.storage.local.remove(['currentTask']);
    }
  } catch (error) {
    console.error('提交任务结果失败:', error);
    updateBadge('失败', '#F44336');
  }
}

// 获取上传凭证（预签名URL）
async function getUploadCredential(taskId) {
  const storage = await chrome.storage.local.get(['token']);
  try {
    const response = await fetch(`${API_BASE}/tasks/upload-credential?task_id=${taskId}`, {
      headers: {
        'Authorization': `Bearer ${storage.token}`
      }
    });
    return await response.json();
  } catch (error) {
    console.error('获取上传凭证失败:', error);
    return { success: false, error: error.message };
  }
}

/**
 * Fallback上传：Background下载视频URL并直传COS
 * 用于Content Script被CSP拦截时
 */
async function uploadVideoFallback(taskId, videoUrl) {
  const storage = await chrome.storage.local.get(['token']);
  try {
    console.log('[Fallback] 开始下载视频:', videoUrl);

    // 1. 下载视频
    const downloadResponse = await fetch(videoUrl);
    if (!downloadResponse.ok) {
      throw new Error(`下载失败: ${downloadResponse.status}`);
    }

    const blob = await downloadResponse.blob();
    console.log('[Fallback] 下载完成, size:', blob.size);

    if (blob.size < 10000) {
      throw new Error('视频文件太小，可能下载不完整');
    }

    // 2. 获取预签名URL
    const credential = await getUploadCredential(taskId);
    if (!credential?.success) {
      throw new Error(credential?.error || '获取上传凭证失败');
    }

    // 3. 上传到COS
    const uploadResponse = await fetch(credential.presigned_url, {
      method: 'PUT',
      body: blob,
      headers: {
        'Content-Type': credential.content_type || 'video/mp4'
      }
    });

    if (!uploadResponse.ok) {
      throw new Error(`COS上传失败: ${uploadResponse.status}`);
    }

    console.log('[Fallback] 上传成功');
    return {
      success: true,
      result_url: credential.result_url
    };

  } catch (error) {
    console.error('[Fallback] 失败:', error);
    return { success: false, error: error.message };
  }
}

// 处理任务完成
async function handleTaskComplete(data) {
  console.log('任务完成:', data);

  updateBadge('完成', '#4CAF50');
  showNotification('ShareYourAi', '任务完成！视频已上传');

  // 提交结果到后端
  const storage = await chrome.storage.local.get(['token', 'nodeId']);
  try {
    await fetch(`${API_BASE}/tasks/result`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${storage.token}`
      },
      body: JSON.stringify({
        task_id: data.taskId,
        node_id: storage.nodeId,
        status: 'success',
        result_url: data.resultUrl,
        proof: data.proof,
        file_size: data.fileSize,
        file_format: data.fileFormat
      })
    });
  } catch (error) {
    console.error('提交结果失败:', error);
  }

  currentTask = null;
  await chrome.storage.local.remove(['currentTask']);
}

// 处理任务失败
async function handleTaskFailed(data) {
  console.log('任务失败:', data);

  updateBadge('失败', '#F44336');
  showNotification('ShareYourAi', '任务失败: ' + data.error, 'error');

  // 提交失败结果到后端
  const storage = await chrome.storage.local.get(['token', 'nodeId']);
  try {
    await fetch(`${API_BASE}/tasks/result`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${storage.token}`
      },
      body: JSON.stringify({
        task_id: data.taskId,
        node_id: storage.nodeId,
        status: 'failed',
        error_message: data.error,
        proof: data.proof
      })
    });
  } catch (error) {
    console.error('提交失败结果失败:', error);
  }

  currentTask = null;
  await chrome.storage.local.remove(['currentTask']);
}

// 关闭当前任务标签页
async function closeCurrentTaskTab() {
  console.log('关闭当前任务标签页');

  const storage = await chrome.storage.local.get(['currentTaskTabId']);
  const tabId = storage.currentTaskTabId;

  if (tabId) {
    try {
      await chrome.tabs.remove(tabId);
      console.log('已关闭标签页:', tabId);
    } catch (error) {
      console.log('关闭标签页失败:', error);
    }
    await chrome.storage.local.remove(['currentTaskTabId']);
  }

  currentTask = null;
  await chrome.storage.local.remove(['currentTask']);
}

// 检查后端任务状态
async function checkTaskStatusFromBackend(taskId) {
  const storage = await chrome.storage.local.get(['token']);
  try {
    const response = await fetch(`${API_BASE}/tasks/status/${taskId}`, {
      headers: {
        'Authorization': `Bearer ${storage.token}`
      }
    });
    if (response.ok) {
      const data = await response.json();
      return { status: data.status, taskId: data.task_id };
    }
  } catch (error) {
    console.error('检查任务状态失败:', error);
  }
  return { status: null };
}

// 定时清理过期数据和检查任务状态
setInterval(async () => {
  const result = await chrome.storage.local.get(['currentTask', 'token']);
  if (result.currentTask) {
    const task = result.currentTask;
    const taskTime = new Date(task.create_time || task.start_time);
    const now = new Date();

    // 1小时过期的任务，直接清理
    if (now - taskTime > 3600000) {
      console.log('[清理] 任务已过期1小时，清理:', task.task_id);
      await chrome.storage.local.remove(['currentTask']);
      currentTask = null;
      updateBadge('', '#4CAF50');
      return;
    }

    // 检查后端任务状态，如果已结束则清理本地任务
    try {
      const response = await fetch(`${API_BASE}/tasks/status/${task.task_id}`, {
        headers: {
          'Authorization': `Bearer ${result.token}`
        }
      });
      if (response.ok) {
        const data = await response.json();
        // 如果任务状态不是 pending 或 processing，说明已结束
        if (data.status && data.status !== 'pending' && data.status !== 'processing') {
          console.log('[清理] 后端任务已结束:', data.status, '清理本地任务:', task.task_id);
          await chrome.storage.local.remove(['currentTask']);
          currentTask = null;
          updateBadge('', '#4CAF50');
        }
      }
    } catch (error) {
      console.error('[清理] 检查任务状态失败:', error);
    }
  }
}, 30000);  // 每30秒检查一次

// 发送心跳（每25秒，配合Redis TTL 60秒）
setInterval(async () => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    const storage = await chrome.storage.local.get(['token', 'nodeId']);
    if (storage.token && storage.nodeId) {
      // 通过 HTTP API 发送心跳
      try {
        await fetch(`${API_BASE}/nodes/heartbeat`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${storage.token}`
          },
          body: JSON.stringify({ node_id: storage.nodeId })
        });
      } catch (error) {
        console.error('心跳发送失败:', error);
      }
    }
  }
}, 25000);

console.log('Background Service Worker 已启动');