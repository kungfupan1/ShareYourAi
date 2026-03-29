/**
 * Bridge Script - 运行在 Isolated World
 * 负责接收 inject.js (MAIN World) 的消息并转发给 background
 *
 * 注意：此脚本可以访问 Chrome Extension API
 */
(function() {
  'use strict';

  const INJECT_ID = '__SYA_INJECT__';
  const BRIDGE_ID = '__SYA_BRIDGE__';

  // 防止重复初始化
  if (window[BRIDGE_ID]) {
    console.log('[SYA Bridge] 已初始化，跳过');
    return;
  }
  window[BRIDGE_ID] = true;

  console.log('[SYA Bridge] 桥接脚本已加载');

  // ========== 动态注入 inject.js 到 MAIN World ==========
  function injectToMainWorld() {
    const script = document.createElement('script');
    script.src = chrome.runtime.getURL('content/inject.js');
    script.onload = function() {
      console.log('[SYA Bridge] inject.js 注入成功');
      this.remove();
    };
    script.onerror = function() {
      console.error('[SYA Bridge] inject.js 注入失败');
    };
    (document.head || document.documentElement).appendChild(script);
  }

  // 立即注入
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectToMainWorld);
  } else {
    injectToMainWorld();
  }

  // 存储捕获的数据
  const capturedData = {
    apiResponses: [],
    videoUrls: [],
    lastActivity: null
  };

  /**
   * 监听来自 inject.js 的消息
   */
  window.addEventListener('message', function(event) {
    // 🔒 安全检查：只接受来自当前窗口的消息
    if (event.source !== window) {
      return;
    }

    // 检查消息来源
    if (!event.data || event.data.source !== INJECT_ID) {
      return;
    }

    const { type, data, timestamp } = event.data;

    console.log(`[SYA Bridge] 收到消息: ${type}`);

    // 更新活动时间
    capturedData.lastActivity = timestamp;

    switch (type) {
      case 'INJECT_READY':
        console.log('[SYA Bridge] inject.js 已就绪');
        break;

      case 'API_RESPONSE':
        // 存储 API 响应
        capturedData.apiResponses.push({
          ...data,
          receivedAt: timestamp
        });

        // 只保留最近 20 条
        if (capturedData.apiResponses.length > 20) {
          capturedData.apiResponses.shift();
        }

        // 转发给 background
        forwardToBackground('API_CAPTURED', data);

        // 同时暴露给全局（供 content/index.js 使用）
        if (!window.__syaCapturedResponses) {
          window.__syaCapturedResponses = [];
        }
        window.__syaCapturedResponses.push(data);
        break;

      case 'VIDEO_URL':
        // 存储视频 URL
        capturedData.videoUrls.push({
          url: data.url,
          timestamp: timestamp
        });

        // 只保留最近 10 条
        if (capturedData.videoUrls.length > 10) {
          capturedData.videoUrls.shift();
        }

        // 转发给 background
        forwardToBackground('VIDEO_URL_CAPTURED', data);

        // 同时暴露给全局（供 content/index.js 使用）
        if (!window.__syaVideoUrls) {
          window.__syaVideoUrls = [];
        }
        window.__syaVideoUrls.push({
          url: data.url,
          time: timestamp
        });
        break;

      default:
        console.log(`[SYA Bridge] 未知消息类型: ${type}`);
    }
  });

  /**
   * 转发消息给 background
   */
  function forwardToBackground(type, data) {
    try {
      chrome.runtime.sendMessage({
        action: 'INTERCEPT_DATA',
        type: type,
        data: data
      }).catch(err => {
        // 忽略发送失败的错误（可能 background 未准备好）
      });
    } catch (e) {
      // 忽略错误
    }
  }

  /**
   * 提供数据访问接口
   */
  window.__syaGetCapturedData = function() {
    return {
      ...capturedData,
      apiResponses: [...capturedData.apiResponses],
      videoUrls: [...capturedData.videoUrls]
    };
  };

  /**
   * 清空捕获的数据
   */
  window.__syaClearCapturedData = function() {
    capturedData.apiResponses = [];
    capturedData.videoUrls = [];
    capturedData.lastActivity = null;
    window.__syaCapturedResponses = [];
    window.__syaVideoUrls = [];
  };

  // 初始化全局存储
  if (!window.__syaVideoUrls) {
    window.__syaVideoUrls = [];
  }
  if (!window.__syaCapturedResponses) {
    window.__syaCapturedResponses = [];
  }

  console.log('[SYA Bridge] 桥接脚本已就绪，等待 inject.js 消息...');

})();