/**
 * Inject Script - 运行在 MAIN World
 * 用于拦截页面的 fetch 请求，捕获 AI API 调用
 *
 * 注意：此脚本运行在页面上下文，无法访问 Chrome Extension API
 * 通过 window.postMessage 与 bridge.js 通信
 */
(function() {
  'use strict';

  const INJECT_ID = '__SYA_INJECT__';
  const BRIDGE_ID = '__SYA_BRIDGE__';

  // 防止重复注入
  if (window[INJECT_ID]) {
    console.log('[SYA Inject] 已注入，跳过');
    return;
  }
  window[INJECT_ID] = true;

  console.log('[SYA Inject] 开始注入 fetch 拦截器');

  // 保存原始 fetch
  const originalFetch = window.fetch;

  // 需要拦截的 API 路径
  const INTERCEPT_PATTERNS = [
    // Grok
    { pattern: /grok\.com\/api\/.*generate/i, platform: 'grok' },
    { pattern: /grok\.com\/api\/.*imagine/i, platform: 'grok' },
    { pattern: /grok\.com\/api\/.*video/i, platform: 'grok' },
    { pattern: /x\.ai\/api\/.*generate/i, platform: 'grok' },
    // Sora
    { pattern: /sora\.com\/api\/.*generate/i, platform: 'sora' },
    { pattern: /sora\.com\/api\/.*video/i, platform: 'sora' },
    // Runway
    { pattern: /runwayml\.com\/api\/.*generate/i, platform: 'runway' },
    { pattern: /runwayml\.com\/api\/.*video/i, platform: 'runway' },
    // 通用视频生成 API
    { pattern: /\/api\/.*generate.*video/i, platform: 'unknown' },
    { pattern: /\/api\/.*video.*create/i, platform: 'unknown' },
  ];

  // 视频URL模式
  const VIDEO_URL_PATTERNS = [
    /\.mp4(\?|$)/i,
    /video.*\.mp4/i,
    /cdn.*video/i,
    /\/videos?\//i,
  ];

  /**
   * 检查URL是否匹配拦截模式
   */
  function shouldIntercept(url) {
    for (const item of INTERCEPT_PATTERNS) {
      if (item.pattern.test(url)) {
        return item.platform;
      }
    }
    return null;
  }

  /**
   * 检查URL是否是视频URL
   */
  function isVideoUrl(url) {
    return VIDEO_URL_PATTERNS.some(pattern => pattern.test(url));
  }

  /**
   * 发送消息给 Bridge（Isolated World）
   */
  function sendToBridge(type, data) {
    window.postMessage({
      source: INJECT_ID,
      type: type,
      data: data,
      timestamp: Date.now()
    }, '*');
  }

  /**
   * 拦截 fetch
   */
  window.fetch = async function(input, init = {}) {
    const url = typeof input === 'string' ? input : input.url;

    // 检查是否需要拦截
    const platform = shouldIntercept(url);

    if (platform) {
      console.log(`[SYA Inject] 拦截 API 请求: ${url}`);

      try {
        // 执行原始请求
        const response = await originalFetch.call(this, input, init);

        // 克隆响应以便读取
        const clonedResponse = response.clone();

        // 尝试解析响应
        try {
          const responseText = await clonedResponse.text();
          let responseData = null;

          // 尝试解析 JSON
          try {
            responseData = JSON.parse(responseText);
          } catch (e) {
            // 不是 JSON，保持原始文本
            responseData = { rawText: responseText.substring(0, 1000) };
          }

          // 发送给 Bridge
          sendToBridge('API_RESPONSE', {
            platform: platform,
            url: url,
            method: init.method || 'GET',
            requestBody: init.body ? (typeof init.body === 'string' ? init.body.substring(0, 500) : '[FormData/Body]') : null,
            responseData: responseData,
            status: response.status,
            timestamp: Date.now()
          });

        } catch (e) {
          console.error('[SYA Inject] 解析响应失败:', e);
        }

        return response;

      } catch (error) {
        console.error('[SYA Inject] 请求失败:', error);
        throw error;
      }
    }

    // 检查是否是视频URL
    if (isVideoUrl(url)) {
      console.log(`[SYA Inject] 检测到视频URL: ${url}`);

      // 执行原始请求
      const response = await originalFetch.call(this, input, init);

      // 发送视频URL信息
      sendToBridge('VIDEO_URL', {
        url: url,
        method: init.method || 'GET',
        timestamp: Date.now()
      });

      return response;
    }

    // 不需要拦截，直接执行原始 fetch
    return originalFetch.call(this, input, init);
  };

  console.log('[SYA Inject] Fetch 拦截器已安装');

  // 通知 Bridge 注入成功
  sendToBridge('INJECT_READY', {
    timestamp: Date.now()
  });

})();