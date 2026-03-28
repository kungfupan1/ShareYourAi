/**
 * Content Script - AI 请求拦截与自动操作
 */

(function() {
  'use strict';

  // ============ 配置 ============
  const CONFIG = {
    MAX_RETRIES: 5,
    TASK_TIMEOUT: 300000,
    VIDEO_CHECK_INTERVAL: 3000,  // 增加检测间隔
    PAGE_READY_WAIT: 3000
  };

  // ============ 状态管理 ============
  let currentTask = null;
  let isExecuting = false;
  let videoCheckTimer = null;
  let timeoutTimer = null;
  let taskStartTime = null;
  let processedVideoUrls = new Set();
  let taskSubmittedTime = null; // 任务提交时间

  // ============ 视频URL缓存（拦截网络请求） ============
  window.__syaVideoUrls = [];
  window.__syaCapturedResponses = []; // 存储捕获的完整响应

  // ============ 工具函数 ============（必须最先定义）

  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  function log(...args) {
    console.log('[ShareYourAi]', new Date().toLocaleTimeString(), ...args);
  }

  function updateStatus(message) {
    showTaskStatus(message);
    log(message);
    chrome.runtime.sendMessage({
      action: 'STATUS_UPDATE',
      taskId: currentTask?.task_id,
      status: message
    }).catch(() => {});
  }

  // ============ 网络请求拦截 ============

  // 拦截 fetch 请求
  const originalFetch = window.fetch;
  window.fetch = async function(...args) {
    const [url, options] = args;
    const urlStr = typeof url === 'string' ? url : url.toString();

    try {
      const response = await originalFetch(...args);

      // 检查是否是视频相关的请求
      const contentType = response.headers.get('content-type') || '';
      const isVideo = urlStr.includes('.mp4') ||
                      urlStr.includes('.webm') ||
                      urlStr.includes('video') ||
                      contentType.includes('video') ||
                      contentType.includes('octet-stream');

      if (isVideo) {
        log('🎯 拦截到视频请求:', urlStr);
        log('   Content-Type:', contentType);
        window.__syaVideoUrls.push({
          url: urlStr,
          time: Date.now(),
          type: 'fetch'
        });
      }

      // 检查 API 响应中的视频 URL
      if (contentType.includes('application/json')) {
        try {
          const clonedResponse = response.clone();
          const data = await clonedResponse.json();

          // 存储响应用于调试
          window.__syaCapturedResponses.push({
            url: urlStr,
            data: data,
            time: Date.now()
          });

          // 递归搜索视频 URL
          const videoUrls = extractVideoUrls(data);
          for (const vUrl of videoUrls) {
            log('🎥 从 API 响应中发现视频 URL:', vUrl);
            window.__syaVideoUrls.push({
              url: vUrl,
              time: Date.now(),
              type: 'api'
            });
          }

          // 保持缓存不超过30个
          if (window.__syaVideoUrls.length > 30) {
            window.__syaVideoUrls = window.__syaVideoUrls.slice(-30);
          }
          if (window.__syaCapturedResponses.length > 10) {
            window.__syaCapturedResponses = window.__syaCapturedResponses.slice(-10);
          }
        } catch (e) {
          // JSON 解析失败，忽略
        }
      }

      return response;
    } catch (error) {
      throw error;
    }
  };

  // 拦截 XMLHttpRequest
  const originalXHR = window.XMLHttpRequest;
  window.XMLHttpRequest = function() {
    const xhr = new originalXHR();
    const originalOpen = xhr.open;
    const originalSend = xhr.send;

    let requestUrl = '';

    xhr.open = function(method, url, ...rest) {
      requestUrl = typeof url === 'string' ? url : url.toString();
      return originalOpen.call(xhr, method, url, ...rest);
    };

    xhr.send = function(...args) {
      xhr.addEventListener('load', function() {
        // 检查是否是视频相关请求
        if (requestUrl.includes('.mp4') ||
            requestUrl.includes('.webm') ||
            requestUrl.includes('video')) {
          log('🎯 XHR 拦截到视频请求:', requestUrl);
          window.__syaVideoUrls.push({
            url: requestUrl,
            time: Date.now(),
            type: 'xhr'
          });
        }

        // 尝试解析 JSON 响应
        try {
          const contentType = xhr.getResponseHeader('content-type') || '';
          if (contentType.includes('application/json')) {
            const data = JSON.parse(xhr.responseText);
            const videoUrls = extractVideoUrls(data);
            for (const vUrl of videoUrls) {
              log('🎥 从 XHR 响应中发现视频 URL:', vUrl);
              window.__syaVideoUrls.push({
                url: vUrl,
                time: Date.now(),
                type: 'xhr-api'
              });
            }
          }
        } catch (e) {}
      });

      return originalSend.call(xhr, ...args);
    };

    return xhr;
  };

  // 递归提取 JSON 中的视频 URL
  function extractVideoUrls(obj, urls = []) {
    if (!obj) return urls;

    if (typeof obj === 'string') {
      // 扩展匹配模式
      if ((obj.includes('.mp4') || obj.includes('.webm') || obj.includes('video') || obj.includes('media'))
          && (obj.startsWith('http') || obj.startsWith('//') || obj.startsWith('/'))) {
        urls.push(obj);
      }
      return urls;
    }

    if (Array.isArray(obj)) {
      for (const item of obj) {
        extractVideoUrls(item, urls);
      }
      return urls;
    }

    if (typeof obj === 'object') {
      for (const key of Object.keys(obj)) {
        extractVideoUrls(obj[key], urls);
      }
    }

    return urls;
  }

  // ============ Grok 自动操作 ============

  const GrokOperator = {
    waitForElement: function(selectors, timeout = 15000) {
      return new Promise((resolve, reject) => {
        const selectorList = Array.isArray(selectors) ? selectors : [selectors];

        for (const selector of selectorList) {
          const el = document.querySelector(selector);
          if (el) {
            resolve(el);
            return;
          }
        }

        const observer = new MutationObserver(() => {
          for (const selector of selectorList) {
            const el = document.querySelector(selector);
            if (el) {
              observer.disconnect();
              resolve(el);
              return;
            }
          }
        });

        observer.observe(document.body, { childList: true, subtree: true });

        setTimeout(() => {
          observer.disconnect();
          for (const selector of selectorList) {
            const el = document.querySelector(selector);
            if (el) {
              resolve(el);
              return;
            }
          }
          reject(new Error('等待元素超时: ' + selectorList.join(', ')));
        }, timeout);
      });
    },

    simulateInput: function(element, text) {
      element.focus();
      element.click();

      if (element.isContentEditable || element.contentEditable === 'true') {
        document.execCommand('selectAll', false, null);
        document.execCommand('delete', false, null);
        for (const char of text) {
          document.execCommand('insertText', false, char);
        }
      } else {
        element.value = text;
      }

      ['input', 'change', 'blur'].forEach(eventType => {
        element.dispatchEvent(new Event(eventType, { bubbles: true }));
      });
    },

    simulateClick: async function(element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
      await sleep(300);

      const rect = element.getBoundingClientRect();
      const x = rect.left + rect.width / 2;
      const y = rect.top + rect.height / 2;

      ['mousedown', 'mouseup', 'click'].forEach(eventType => {
        element.dispatchEvent(new MouseEvent(eventType, {
          bubbles: true,
          cancelable: true,
          clientX: x,
          clientY: y
        }));
      });
    },

    findAndClickSubmit: async function() {
      // Grok 特定的按钮选择器（按优先级排序）
      const buttonSelectors = [
        // Grok 发送按钮
        'button[aria-label*="Send"]',
        'button[aria-label*="Generate"]',
        'button[aria-label*="Submit"]',
        'button[aria-label*="发送"]',
        'button[data-testid*="send"]',
        'button[data-testid*="submit"]',
        // 带特定 class 的按钮
        'button.send-button',
        'button.submit-button',
        'button.primary-button',
        // 表单提交按钮
        'button[type="submit"]',
        // 最后尝试：找到输入框附近的按钮
      ];

      // 先尝试精确匹配
      for (const selector of buttonSelectors) {
        try {
          const buttons = document.querySelectorAll(selector);
          for (const btn of buttons) {
            if (btn && !btn.disabled && btn.offsetParent !== null) {
              log('找到精确匹配按钮:', selector, btn);
              await this.simulateClick(btn);
              await sleep(500);
              // 检查是否有反应（输入框是否清空或页面是否有变化）
              return true;
            }
          }
        } catch (e) {
          log('选择器错误:', selector, e);
        }
      }

      // 如果精确匹配失败，尝试查找输入框附近的按钮
      log('精确匹配失败，尝试查找输入框附近的按钮');
      const inputBox = document.querySelector('textarea, div[contenteditable="true"], div.ProseMirror');
      if (inputBox) {
        // 查找输入框父容器中的按钮
        const container = inputBox.closest('div[class*="container"], div[class*="wrapper"], form, div');
        if (container) {
          const buttons = container.querySelectorAll('button:not([disabled])');
          for (const btn of buttons) {
            // 检查按钮是否在输入框右侧或下方（发送按钮通常在这里）
            const inputRect = inputBox.getBoundingClientRect();
            const btnRect = btn.getBoundingClientRect();

            // 按钮应该在输入框右侧或下方附近
            const isRightSide = btnRect.left >= inputRect.right - 100;
            const isBelow = btnRect.top >= inputRect.bottom - 50 && btnRect.top <= inputRect.bottom + 100;
            const isSameRow = Math.abs(btnRect.top - inputRect.top) < 50;

            if ((isRightSide && isSameRow) || isBelow) {
              // 排除一些明显的非发送按钮（如附件、表情等）
              const ariaLabel = btn.getAttribute('aria-label') || '';
              const btnText = btn.textContent || '';
              const excludeKeywords = ['attach', 'emoji', 'image', 'file', 'upload', '附件', '表情', '图片', '文件', '上传'];

              if (!excludeKeywords.some(kw => ariaLabel.toLowerCase().includes(kw) || btnText.toLowerCase().includes(kw))) {
                log('找到输入框附近的按钮:', btn, 'aria-label:', ariaLabel);
                await this.simulateClick(btn);
                return true;
              }
            }
          }
        }
      }

      // 最后尝试：任何可点击的按钮
      log('尝试查找任何可点击的按钮');
      const allButtons = document.querySelectorAll('button:not([disabled])');
      for (const btn of allButtons) {
        if (btn.offsetParent !== null) {
          const rect = btn.getBoundingClientRect();
          // 按钮应该在可见区域
          if (rect.top > 0 && rect.top < window.innerHeight) {
            const ariaLabel = btn.getAttribute('aria-label') || '';
            log('候选按钮:', btn, 'aria-label:', ariaLabel, 'rect:', rect);
          }
        }
      }

      return false;
    },

    executeTask: async function(task) {
      if (isExecuting) {
        log('已有任务在执行中');
        return { success: false, error: '已有任务在执行中' };
      }

      // 清理上一次任务的状态
      if (videoCheckTimer) clearInterval(videoCheckTimer);
      if (timeoutTimer) clearTimeout(timeoutTimer);
      if (window._syaObserver) window._syaObserver.disconnect();

      // 清理视频缓存和状态
      window.__syaVideoUrls = [];
      window.__syaCapturedResponses = [];
      processedVideoUrls = new Set();
      taskStartTime = Date.now();
      log('🚀 任务开始时间:', taskStartTime);

      // 记录页面上已存在的视频，避免误判为新生成的
      const existingVideos = document.querySelectorAll('video[src], source[src], a[href*=".mp4"]');
      for (const v of existingVideos) {
        const src = v.src || v.href;
        if (src) {
          processedVideoUrls.add(src);
          log('📝 记录已存在的视频:', src);
        }
      }

      isExecuting = true;
      currentTask = task;
      log('开始执行任务:', task.task_id);

      try {
        updateStatus('等待页面加载...');
        await sleep(CONFIG.PAGE_READY_WAIT);

        updateStatus('查找输入框...');

        const inputSelectors = [
          'textarea[placeholder*="message"]',
          'textarea[placeholder*="Ask"]',
          'textarea[placeholder*="Describe"]',
          'div[contenteditable="true"]',
          'div.ProseMirror',
          'textarea:not([disabled])'
        ];

        let inputBox = null;
        try {
          inputBox = await this.waitForElement(inputSelectors, 15000);
        } catch (e) {
          updateStatus('未找到输入框');
          throw new Error('无法找到输入框');
        }

        log('找到输入框');
        updateStatus('填写提示词...');

        this.simulateInput(inputBox, task.prompt);
        await sleep(500);

        updateStatus('提交任务...');

        const clicked = await this.findAndClickSubmit();

        if (!clicked) {
          log('未找到按钮，尝试 Enter 键');
          inputBox.dispatchEvent(new KeyboardEvent('keydown', {
            key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true
          }));
        }

        // 记录任务提交时间
        taskSubmittedTime = Date.now();
        log('📤 任务已提交，时间:', taskSubmittedTime);

        updateStatus('任务已提交，等待视频生成...');

        // 等待一段时间后再开始监控，避免检测到旧视频
        await sleep(5000);

        startVideoMonitoring(task.task_id);

        return { success: true };

      } catch (error) {
        log('执行失败:', error);
        updateStatus('执行失败: ' + error.message);
        isExecuting = false;
        return { success: false, error: error.message };
      }
    }
  };

  // ============ 视频监控 ============

  function startVideoMonitoring(taskId) {
    log('👀 开始监控视频生成...');

    if (videoCheckTimer) clearInterval(videoCheckTimer);
    if (timeoutTimer) clearTimeout(timeoutTimer);

    timeoutTimer = setTimeout(() => {
      log('⏰ 任务超时');
      updateStatus('任务超时');
      handleTaskFailed(taskId, '任务超时');
    }, CONFIG.TASK_TIMEOUT);

    videoCheckTimer = setInterval(() => {
      checkForVideo(taskId);
    }, CONFIG.VIDEO_CHECK_INTERVAL);

    // 同时监控 DOM 变化
    const observer = new MutationObserver(() => {
      checkForVideo(taskId);
    });
    observer.observe(document.body, { childList: true, subtree: true });
    window._syaObserver = observer;
  }

  function checkForVideo(taskId) {
    // 先检查拦截到的视频 URL
    if (window.__syaVideoUrls && window.__syaVideoUrls.length > 0) {
      // 过滤出任务提交后捕获的 URL
      const recentUrls = window.__syaVideoUrls.filter(u => {
        const urlObj = typeof u === 'object' ? u : { url: u, time: 0 };
        return urlObj.time > (taskSubmittedTime || 0);
      });

      if (recentUrls.length > 0) {
        const latest = recentUrls[recentUrls.length - 1];
        const url = typeof latest === 'object' ? latest.url : latest;
        log('🔍 从拦截列表发现视频 URL:', url);
        if (!processedVideoUrls.has(url)) {
          processedVideoUrls.add(url);
          handleVideoFound(taskId, url, null);
          return;
        }
      }
    }

    // 检查页面上的 video 元素
    const videoSelectors = [
      'video[src]',
      'video source[src]',
      'a[href*=".mp4"]'
    ];

    for (const selector of videoSelectors) {
      const elements = document.querySelectorAll(selector);
      for (const el of elements) {
        const src = el.src || el.href || el.getAttribute('src');
        if (src && !processedVideoUrls.has(src)) {
          // 对于 video 元素，检查是否已加载
          if (el.tagName === 'VIDEO' || el.tagName === 'SOURCE') {
            const video = el.tagName === 'VIDEO' ? el : el.closest('video');
            if (video && video.readyState >= 2) {
              processedVideoUrls.add(src);
              log('🎬 检测到已加载视频:', src, 'readyState:', video.readyState);
              handleVideoFound(taskId, src, video);
              return;
            }
          } else {
            processedVideoUrls.add(src);
            log('🎬 检测到视频链接:', src);
            handleVideoFound(taskId, src, null);
            return;
          }
        }
      }
    }
  }

  async function handleVideoFound(taskId, videoUrl, videoElement) {
    // 停止监控
    if (videoCheckTimer) clearInterval(videoCheckTimer);
    if (timeoutTimer) clearTimeout(timeoutTimer);
    if (window._syaObserver) window._syaObserver.disconnect();

    updateStatus('检测到视频，开始下载...');
    log('📥 开始下载视频:', videoUrl);

    let blob = null;

    // 1. 优先使用拦截到的真实视频 URL
    if (window.__syaVideoUrls && window.__syaVideoUrls.length > 0) {
      // 过滤出任务提交后的 URL，按时间排序
      const candidateUrls = window.__syaVideoUrls
        .filter(u => {
          const urlObj = typeof u === 'object' ? u : { url: u, time: Date.now() };
          return urlObj.time > (taskSubmittedTime || 0);
        })
        .map(u => typeof u === 'object' ? u.url : u);

      log('📋 候选视频 URL 列表:', candidateUrls);

      for (const url of candidateUrls) {
        if (url && !url.startsWith('blob:')) {
          try {
            log('尝试下载:', url);
            const response = await fetch(url, {
              mode: 'cors',
              credentials: 'include'
            });
            if (response.ok) {
              blob = await response.blob();
              log('✅ 下载成功，大小:', blob.size, '类型:', blob.type);
              if (blob.size > 10000) break; // 至少 10KB
              blob = null;
            }
          } catch (e) {
            log('❌ 下载失败:', e.message);
          }
        }
      }
    }

    // 2. 如果是普通 URL，直接下载
    if (!blob && videoUrl && !videoUrl.startsWith('blob:')) {
      try {
        log('直接下载视频 URL:', videoUrl);
        const response = await fetch(videoUrl, {
          mode: 'cors',
          credentials: 'include'
        });
        blob = await response.blob();
        log('✅ 直接下载成功，大小:', blob.size);
      } catch (e) {
        log('❌ 直接下载失败:', e.message);
      }
    }

    // 3. 如果是 blob URL，尝试特殊处理
    if (!blob && videoUrl && videoUrl.startsWith('blob:')) {
      log('检测到 blob URL，尝试特殊处理...');

      // 尝试直接 fetch blob（有时可行）
      try {
        const response = await fetch(videoUrl);
        blob = await response.blob();
        log('✅ blob fetch 成功，大小:', blob.size);
      } catch (e) {
        log('❌ blob fetch 失败:', e.message);
      }

      // 如果失败，查找下载按钮
      if (!blob || blob.size < 10000) {
        blob = await findAndClickDownloadButton(taskId);
      }
    }

    // 4. 最后尝试：从页面找下载按钮
    if (!blob || blob.size < 10000) {
      log('尝试从页面找下载按钮...');
      blob = await findAndClickDownloadButton(taskId);
    }

    if (!blob || blob.size < 10000) {
      log('❌ 所有下载方式都失败');
      updateStatus('视频下载失败');

      // 打印调试信息
      log('=== 调试信息 ===');
      log('拦截到的 URL:', window.__syaVideoUrls);
      log('捕获的响应:', window.__syaCapturedResponses);
      log('当前 videoUrl:', videoUrl);

      handleTaskFailed(taskId, '视频下载失败，请重试');
      return;
    }

    // 上传视频
    try {
      updateStatus('上传中...');

      const reader = new FileReader();
      const base64Promise = new Promise((resolve) => {
        reader.onloadend = () => {
          log('base64 转换完成，长度:', reader.result?.length);
          resolve(reader.result);
        };
        reader.onerror = () => {
          log('base64 转换失败');
          resolve(null);
        };
        reader.readAsDataURL(blob);
      });
      const base64Data = await base64Promise;

      if (!base64Data) {
        throw new Error('base64 转换失败');
      }

      const result = await chrome.runtime.sendMessage({
        action: 'UPLOAD_VIDEO',
        taskId: taskId,
        videoData: base64Data,
        fileSize: blob.size
      });

      log('上传结果:', result);

      if (!result?.success) {
        throw new Error(result?.error || '上传失败');
      }

      log('✅ 上传成功:', result);

      chrome.runtime.sendMessage({
        action: 'TASK_COMPLETE',
        data: {
          taskId: taskId,
          resultUrl: result.result_url,
          fileSize: blob.size,
          fileFormat: blob.type.includes('webm') ? 'webm' : 'mp4'
        }
      });

      updateStatus('上传完成！');
      isExecuting = false;

    } catch (error) {
      log('视频处理失败:', error);
      handleTaskFailed(taskId, error.message);
    }
  }

  // 查找并点击下载按钮
  async function findAndClickDownloadButton(taskId) {
    log('🔍 查找下载按钮...');

    // 查找各种可能的下载按钮
    const downloadSelectors = [
      'a[download]',
      'button[download]',
      '[aria-label*="download"]',
      '[aria-label*="Download"]',
      'a[href*="download"]',
      'button[data-url*=".mp4"]',
      'a[href*=".mp4"]'
    ];

    for (const selector of downloadSelectors) {
      const elements = document.querySelectorAll(selector);
      for (const el of elements) {
        const href = el.href || el.getAttribute('href') || el.getAttribute('data-url') || el.download;
        log('找到可能的下载元素:', selector, href);

        if (href && !href.startsWith('blob:') && !href.startsWith('javascript:')) {
          try {
            log('尝试下载:', href);
            const response = await fetch(href, {
              mode: 'cors',
              credentials: 'include'
            });
            const blob = await response.blob();
            if (blob.size > 10000) {
              log('✅ 从下载按钮获取成功，大小:', blob.size);
              return blob;
            }
          } catch (e) {
            log('下载按钮 fetch 失败:', e.message);
          }
        }
      }
    }

    return null;
  }

  function handleTaskFailed(taskId, error) {
    chrome.runtime.sendMessage({
      action: 'TASK_FAILED',
      data: { taskId: taskId, error: error }
    });
    isExecuting = false;
  }

  // ============ 状态显示 ============

  function showTaskStatus(message) {
    let statusDiv = document.getElementById('shareyourai-status');

    if (!statusDiv) {
      statusDiv = document.createElement('div');
      statusDiv.id = 'shareyourai-status';
      statusDiv.style.cssText = `
        position: fixed; top: 20px; right: 20px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white; padding: 12px 20px; border-radius: 8px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        font-size: 14px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        z-index: 2147483647; max-width: 300px;
      `;
      document.body.appendChild(statusDiv);
    }

    statusDiv.textContent = message;
    statusDiv.style.display = 'block';
  }

  // ============ 消息处理 ============

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    log('收到消息:', message.action);

    switch (message.action) {
      case 'START_TASK':
        currentTask = message.task;
        GrokOperator.executeTask(currentTask).then(sendResponse);
        return true;

      case 'STOP_TASK':
        if (videoCheckTimer) clearInterval(videoCheckTimer);
        if (timeoutTimer) clearTimeout(timeoutTimer);
        isExecuting = false;
        updateStatus('任务已停止');
        sendResponse({ success: true });
        break;

      case 'PING':
        sendResponse({ status: isExecuting ? 'executing' : 'ready', task: currentTask });
        break;

      case 'DEBUG':
        // 调试命令，返回当前状态
        sendResponse({
          videoUrls: window.__syaVideoUrls,
          responses: window.__syaCapturedResponses,
          processedUrls: Array.from(processedVideoUrls),
          taskSubmittedTime: taskSubmittedTime
        });
        break;
    }
  });

  log('✅ Content script 已加载');
})();