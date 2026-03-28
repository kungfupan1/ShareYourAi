/**
 * Background Service Worker
 */

// API 基础地址
const API_BASE = 'http://127.0.0.1:8000/api';
const WS_URL = 'ws://127.0.0.1:8000/ws';

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
      // 获取上传凭证
      getUploadCredential(message.taskId).then(sendResponse);
      return true;
    case 'UPLOAD_VIDEO':
      // 上传视频（background 有 token）
      uploadVideo(message.taskId, message.videoData, message.fileSize).then(sendResponse);
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
        console.log('GET_TASK 请求，当前任务:', result.currentTask);
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
  }
});

// 处理新任务
async function handleNewTask(task) {
  console.log('处理新任务:', task);
  currentTask = task;

  // 存储到 chrome.storage（持久化）
  await chrome.storage.local.set({ currentTask: task });

  // 显示通知和徽章
  showNotification('ShareYourAi', `开始执行任务: ${task.prompt?.substring(0, 30)}...`);
  updateBadge('执行中', '#FF9800');

  // 打开对应的 AI 页面
  // 优先使用任务中的 page_url，否则使用默认映射
  const defaultModelUrls = {
    'grok_video': 'https://grok.com',
    'sora2_video': 'https://sora.com',
    'runway_video': 'https://runwayml.com'
  };

  const url = task.page_url || defaultModelUrls[task.model_id];
  console.log('任务 page_url:', task.page_url, '最终 URL:', url);
  if (url) {
    try {
      let targetTab = null;

      // 查找是否已有该页面
      const tabs = await chrome.tabs.query({ url: `${url}/*` });
      if (tabs.length > 0) {
        targetTab = tabs[0];
        await chrome.tabs.update(targetTab.id, { active: true });
        await chrome.windows.update(targetTab.windowId, { focused: true });
      } else {
        targetTab = await chrome.tabs.create({ url });
      }
      console.log('已打开/激活页面:', url, 'tabId:', targetTab.id);

      // 等待页面加载完成后发送任务给 content script
      if (targetTab) {
        // 等待页面加载
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
            // 超时保护
            setTimeout(resolve, 5000);
          }
        });

        // 额外等待确保 content script 已注入
        await new Promise(resolve => setTimeout(resolve, 1000));

        // 发送任务给 content script 执行
        console.log('发送 START_TASK 给 content script');
        try {
          const response = await chrome.tabs.sendMessage(targetTab.id, {
            action: 'START_TASK',
            task: task
          });
          console.log('Content script 响应:', response);
        } catch (error) {
          console.error('发送任务给 content script 失败:', error);
          // 尝试注入 content script
          try {
            await chrome.scripting.executeScript({
              target: { tabId: targetTab.id },
              files: ['content/index.js']
            });
            console.log('已注入 content script');
            // 等待脚本初始化
            await new Promise(resolve => setTimeout(resolve, 500));
            // 重试发送
            const retryResponse = await chrome.tabs.sendMessage(targetTab.id, {
              action: 'START_TASK',
              task: task
            });
            console.log('重试发送成功:', retryResponse);
          } catch (e) {
            console.error('注入脚本或重试失败:', e);
          }
        }
      }
    } catch (error) {
      console.error('打开页面失败:', error);
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

// 获取上传凭证
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

// 上传视频
async function uploadVideo(taskId, base64Data, fileSize) {
  const storage = await chrome.storage.local.get(['token']);
  try {
    console.log('开始上传视频, taskId:', taskId, 'base64Data长度:', base64Data?.length, 'fileSize:', fileSize);

    if (!base64Data) {
      return { success: false, error: '没有视频数据' };
    }

    // 将 base64 转换为 Blob
    const response = await fetch(base64Data);
    const blob = await response.blob();
    console.log('Blob 大小:', blob.size, '类型:', blob.type);

    if (blob.size === 0) {
      return { success: false, error: 'Blob 大小为 0' };
    }

    // 创建 FormData
    const formData = new FormData();
    formData.append('file', blob, `${taskId}.mp4`);

    // 上传
    const uploadResponse = await fetch(`${API_BASE}/tasks/upload/${taskId}`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${storage.token}`
      },
      body: formData
    });

    if (!uploadResponse.ok) {
      const errorText = await uploadResponse.text();
      console.error('上传失败:', errorText);
      return { success: false, error: `上传失败: ${uploadResponse.status}` };
    }

    const result = await uploadResponse.json();
    console.log('上传成功:', result);
    return { success: true, result_url: result.result_url };
  } catch (error) {
    console.error('上传视频失败:', error);
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

// 定时清理过期数据
setInterval(async () => {
  const result = await chrome.storage.local.get(['currentTask']);
  if (result.currentTask) {
    const taskTime = new Date(result.currentTask.create_time);
    const now = new Date();
    if (now - taskTime > 3600000) {
      await chrome.storage.local.remove(['currentTask']);
    }
  }
}, 60000);

// 发送心跳
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
}, 30000);

console.log('Background Service Worker 已启动');