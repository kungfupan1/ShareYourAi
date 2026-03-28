/**
 * Content Script - AI 请求拦截与自动操作
 * 重构版：每次任务新建页面，完成后关闭页面
 */

(function() {
  'use strict';

  // ============ 配置 ============
  const CONFIG = {
    MAX_RETRIES: 5,
    TASK_TIMEOUT: 300000,
    VIDEO_CHECK_INTERVAL: 3000,
    PAGE_READY_WAIT: 3000
  };

  // ============ 状态管理 ============
  let currentTask = null;
  let isExecuting = false;
  let videoCheckTimer = null;
  let timeoutTimer = null;
  let taskStartTime = null;
  let processedVideoUrls = new Set();
  let taskSubmittedTime = null;

  // ============ 视频URL缓存 ============
  window.__syaVideoUrls = [];
  window.__syaCapturedResponses = [];

  // ============ 工具函数 ============

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

  const originalFetch = window.fetch;
  window.fetch = async function(...args) {
    const [url, options] = args;
    const urlStr = typeof url === 'string' ? url : url.toString();

    try {
      const response = await originalFetch(...args);

      const contentType = response.headers.get('content-type') || '';
      const isVideo = urlStr.includes('.mp4') ||
                      urlStr.includes('.webm') ||
                      urlStr.includes('video') ||
                      contentType.includes('video') ||
                      contentType.includes('octet-stream');

      if (isVideo) {
        log('🎯 拦截到视频请求:', urlStr);
        window.__syaVideoUrls.push({
          url: urlStr,
          time: Date.now(),
          type: 'fetch'
        });
      }

      if (contentType.includes('application/json')) {
        try {
          const clonedResponse = response.clone();
          const data = await clonedResponse.json();

          window.__syaCapturedResponses.push({
            url: urlStr,
            data: data,
            time: Date.now()
          });

          const videoUrls = extractVideoUrls(data);
          for (const vUrl of videoUrls) {
            log('🎥 从 API 响应中发现视频 URL:', vUrl);
            window.__syaVideoUrls.push({
              url: vUrl,
              time: Date.now(),
              type: 'api'
            });
          }

          if (window.__syaVideoUrls.length > 30) {
            window.__syaVideoUrls = window.__syaVideoUrls.slice(-30);
          }
          if (window.__syaCapturedResponses.length > 10) {
            window.__syaCapturedResponses = window.__syaCapturedResponses.slice(-10);
          }
        } catch (e) {}
      }

      return response;
    } catch (error) {
      throw error;
    }
  };

  // 递归提取视频URL
  function extractVideoUrls(obj, urls = []) {
    if (!obj) return urls;

    if (typeof obj === 'string') {
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
    // 将 base64 转换为 File 对象
    base64ToFile: function(base64Data, filename) {
      try {
        const arr = base64Data.split(',');
        const mimeMatch = arr[0].match(/:(.*?);/);
        const mime = mimeMatch ? mimeMatch[1] : 'image/png';
        const bstr = atob(arr[1]);
        let n = bstr.length;
        const u8arr = new Uint8Array(n);
        while (n--) {
          u8arr[n] = bstr.charCodeAt(n);
        }
        return new File([u8arr], filename, { type: mime });
      } catch (e) {
        log('base64 转换失败:', e);
        return null;
      }
    },

    // 等待元素出现
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

    // 模拟输入
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

    // 模拟点击 - 支持多种事件类型以适配不同UI框架
    simulateClick: async function(element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
      await sleep(300);

      const rect = element.getBoundingClientRect();
      const x = rect.left + rect.width / 2;
      const y = rect.top + rect.height / 2;

      // 先触发 pointer events（Radix UI 等现代组件库使用）
      ['pointerdown', 'pointerup'].forEach(eventType => {
        element.dispatchEvent(new PointerEvent(eventType, {
          bubbles: true,
          cancelable: true,
          clientX: x,
          clientY: y,
          pointerType: 'mouse',
          isPrimary: true
        }));
      });

      await sleep(100);

      // 再触发 mouse events
      ['mousedown', 'mouseup', 'click'].forEach(eventType => {
        element.dispatchEvent(new MouseEvent(eventType, {
          bubbles: true,
          cancelable: true,
          clientX: x,
          clientY: y
        }));
      });

      await sleep(100);

      // 最后触发 focus
      element.focus?.();
    },

    // 通过background下载图片并返回blob URL
    downloadImageViaBackground: async function(base64Data, index) {
      return new Promise((resolve) => {
        chrome.runtime.sendMessage({
          action: 'DOWNLOAD_IMAGE',
          imageData: base64Data,
          index: index
        }, (response) => {
          if (response && response.success) {
            log('图片已下载到临时文件:', response.filePath);
            resolve(response.filePath);
          } else {
            log('图片下载失败:', response?.error);
            resolve(null);
          }
        });
      });
    },

    // 上传图片 - 只使用精确选择器
    uploadImages: async function(images) {
      if (!images || images.length === 0) {
        log('没有图片需要上传');
        return true;
      }

      // 限制最多5张
      const maxImages = 5;
      const imagesToUpload = images.slice(0, maxImages);
      if (images.length > maxImages) {
        log(`⚠️ 图片数量超过${maxImages}张，只上传前${maxImages}张`);
      }

      log('📸 开始上传图片，数量:', imagesToUpload.length);
      updateStatus('上传参考图片...');

      // 精确查找上传按钮：aria-label="Upload"
      const uploadBtn = document.querySelector('button[aria-label="Upload"]');
      if (!uploadBtn) {
        log('⚠️ 未找到上传按钮 button[aria-label="Upload"]');
        return false;
      }

      log('找到上传按钮，准备点击');
      await this.simulateClick(uploadBtn);
      await sleep(1000);

      // 查找文件输入框
      const fileInput = document.querySelector('input[type="file"]');
      if (!fileInput) {
        log('⚠️ 未找到文件输入框');
        return false;
      }

      // 将所有图片转换为 File 对象
      const files = [];
      for (let i = 0; i < imagesToUpload.length; i++) {
        const base64Data = imagesToUpload[i];
        const file = this.base64ToFile(base64Data, `image_${i}.png`);
        if (file) {
          files.push(file);
          log('准备图片:', file.name, '大小:', file.size);
        }
      }

      if (files.length === 0) {
        log('⚠️ 没有有效的图片文件');
        return false;
      }

      // 一次性设置所有文件到 DataTransfer
      const dataTransfer = new DataTransfer();
      for (const file of files) {
        dataTransfer.items.add(file);
      }
      fileInput.files = dataTransfer.files;

      log(`📤 一次性上传 ${files.length} 张图片`);

      // 触发事件
      fileInput.dispatchEvent(new Event('change', { bubbles: true }));
      fileInput.dispatchEvent(new Event('input', { bubbles: true }));

      log('✅ 图片上传事件已触发');
      await sleep(2000);

      updateStatus('图片上传完成');
      return true;
    },

    // 设置参数（分辨率、时长、画面比例）- 通过点击UI按钮
    setParameters: async function(params) {
      if (!params) return;

      log('设置参数:', params);

      // 画面比例
      if (params.aspect_ratio) {
        await this.setAspectRatio(params.aspect_ratio);
        await sleep(300);
      }

      // 分辨率
      if (params.resolution) {
        await this.setResolution(params.resolution);
        await sleep(300);
      }

      // 时长
      if (params.duration) {
        await this.setDuration(params.duration);
        await sleep(300);
      }
    },

    // 检查并修复参数设置 - 提交前的最终确认
    verifyAndFixParameters: async function(params) {
      log('🔍 最终检查参数设置...');

      let needsFix = false;

      // 1. 检查视频模式
      const modeGroup = document.querySelector('div[aria-label="生成模式"][role="radiogroup"]');
      if (modeGroup) {
        const radioButtons = modeGroup.querySelectorAll('button[role="radio"]');
        let videoModeActive = false;
        for (const btn of radioButtons) {
          const text = btn.textContent || '';
          if (text.includes('视频') && btn.getAttribute('aria-checked') === 'true') {
            videoModeActive = true;
            break;
          }
        }
        if (!videoModeActive) {
          log('⚠️ 视频模式未激活，需要重新设置');
          needsFix = true;
        } else {
          log('✅ 视频模式已激活');
        }
      }

      // 2. 检查分辨率
      if (params.resolution) {
        const resGroup = document.querySelector('div[aria-label="视频分辨率"][role="radiogroup"]');
        if (resGroup) {
          const targetText = params.resolution.toLowerCase();
          const radioButtons = resGroup.querySelectorAll('button[role="radio"]');
          let resCorrect = false;
          for (const btn of radioButtons) {
            const text = (btn.textContent || '').toLowerCase();
            if (text.includes(targetText.replace('p', '')) && btn.getAttribute('aria-checked') === 'true') {
              resCorrect = true;
              break;
            }
          }
          if (!resCorrect) {
            log('⚠️ 分辨率未正确设置，需要重新设置');
            needsFix = true;
          } else {
            log('✅ 分辨率设置正确:', params.resolution);
          }
        }
      }

      // 3. 检查时长
      if (params.duration) {
        const durationGroup = document.querySelector('div[aria-label="视频持续时间"][role="radiogroup"]');
        if (durationGroup) {
          const targetText = params.duration + 's';
          const radioButtons = durationGroup.querySelectorAll('button[role="radio"]');
          let durationCorrect = false;
          for (const btn of radioButtons) {
            const text = btn.textContent || '';
            if (text.includes(targetText) && btn.getAttribute('aria-checked') === 'true') {
              durationCorrect = true;
              break;
            }
          }
          if (!durationCorrect) {
            log('⚠️ 时长未正确设置，需要重新设置');
            needsFix = true;
          } else {
            log('✅ 时长设置正确:', params.duration + 's');
          }
        }
      }

      // 4. 检查画面比例
      if (params.aspect_ratio) {
        const aspectBtn = document.querySelector('button[aria-label="宽高比"]');
        if (aspectBtn) {
          const currentText = aspectBtn.textContent || '';
          if (!currentText.includes(params.aspect_ratio)) {
            log('⚠️ 画面比例未正确设置，需要重新设置');
            needsFix = true;
          } else {
            log('✅ 画面比例设置正确:', params.aspect_ratio);
          }
        }
      }

      // 如果有参数不正确，重新设置所有参数
      if (needsFix) {
        log('🔧 发现参数不一致，重新设置所有参数...');
        await this.switchToVideoMode();
        await sleep(500);
        await this.setParameters(params);
        await sleep(500);
        log('✅ 参数重新设置完成');
      } else {
        log('✅ 所有参数检查通过');
      }

      return !needsFix;
    },

    // 切换到视频模式（从图像模式切换）
    switchToVideoMode: async function() {
      log('尝试切换到视频模式...');

      // 精确选择器：aria-label="生成模式" 的 radiogroup
      const modeGroup = document.querySelector('div[aria-label="生成模式"][role="radiogroup"]');
      if (!modeGroup) {
        log('⚠️ 未找到生成模式切换组');
        return false;
      }

      // 查找包含"视频"文字的 radio 按钮
      const radioButtons = modeGroup.querySelectorAll('button[role="radio"]');
      for (const btn of radioButtons) {
        const text = btn.textContent || '';
        log('模式按钮:', text, 'aria-checked:', btn.getAttribute('aria-checked'));

        if (text.includes('视频')) {
          const isChecked = btn.getAttribute('aria-checked') === 'true';
          if (!isChecked) {
            log('点击切换到视频模式');
            await this.simulateClick(btn);
            await sleep(1000);
            return true;
          } else {
            log('✅ 视频模式已激活');
            return true;
          }
        }
      }

      log('⚠️ 未找到视频模式按钮');
      return false;
    },

    // 设置时长
    setDuration: async function(duration) {
      log('设置时长:', duration);

      // 精确选择器：aria-label="视频持续时间" 的 radiogroup
      const durationGroup = document.querySelector('div[aria-label="视频持续时间"][role="radiogroup"]');
      if (!durationGroup) {
        log('⚠️ 未找到时长切换组');
        return false;
      }

      // 将数字转换为显示文本，例如 6 -> "6s", 10 -> "10s"
      const targetText = duration + 's';

      const radioButtons = durationGroup.querySelectorAll('button[role="radio"]');
      for (const btn of radioButtons) {
        const text = btn.textContent || '';
        log('时长按钮:', text, 'aria-checked:', btn.getAttribute('aria-checked'));

        if (text.includes(targetText)) {
          const isChecked = btn.getAttribute('aria-checked') === 'true';
          if (!isChecked) {
            log('点击设置时长:', targetText);
            await this.simulateClick(btn);
            await sleep(500);
            return true;
          } else {
            log('✅ 时长已设置为:', targetText);
            return true;
          }
        }
      }

      log('⚠️ 未找到时长按钮:', targetText);
      return false;
    },

    // 设置画面比例
    setAspectRatio: async function(ratio) {
      log('🎯 设置画面比例:', ratio);
      updateStatus('设置画面比例: ' + ratio);

      // 查找宽高比按钮 - 使用多种选择器尝试
      const selectors = [
        'button[aria-label="宽高比"]',
        'button[aria-label="Aspect ratio"]',
        'button[aria-label*="ratio"]',
        'button[aria-label*="比例"]'
      ];

      let aspectBtn = null;
      for (const selector of selectors) {
        aspectBtn = document.querySelector(selector);
        if (aspectBtn) {
          log('找到宽高比按钮，选择器:', selector);
          break;
        }
      }

      if (!aspectBtn) {
        log('⚠️ 未找到宽高比按钮，尝试遍历所有按钮');
        const allButtons = document.querySelectorAll('button');
        for (const btn of allButtons) {
          const text = btn.textContent || '';
          const ariaLabel = btn.getAttribute('aria-label') || '';
          if (text.includes(':') && (text.includes('16:9') || text.includes('9:16') || text.includes('1:1') || text.includes('2:3') || text.includes('3:2'))) {
            if (ariaLabel.includes('宽高比') || ariaLabel.includes('ratio') || ariaLabel.includes('比例')) {
              aspectBtn = btn;
              log('通过遍历找到宽高比按钮:', ariaLabel, '文本:', text);
              break;
            }
          }
        }
      }

      if (!aspectBtn) {
        log('⚠️ 未找到宽高比按钮');
        return false;
      }

      // 检查当前值 - 从 span 中获取
      const spanEl = aspectBtn.querySelector('span');
      const currentText = spanEl ? spanEl.textContent.trim() : (aspectBtn.textContent || '').trim();
      log('当前宽高比显示:', currentText);

      // 如果已经是目标值，直接返回
      if (currentText === ratio || currentText.includes(ratio)) {
        log('✅ 画面比例已正确:', ratio);
        return true;
      }

      log('📍 准备点击宽高比按钮，当前值:', currentText, '目标值:', ratio);

      // 点击打开下拉菜单
      await this.simulateClick(aspectBtn);
      log('已点击按钮，等待菜单打开...');
      await sleep(800);

      // 通过 aria-controls 找到菜单ID
      const menuId = aspectBtn.getAttribute('aria-controls');
      log('aria-controls 属性:', menuId);

      let menu = null;
      if (menuId) {
        menu = document.getElementById(menuId);
        if (menu) {
          log('通过 ID 找到菜单:', menuId);
        }
      }

      // 如果没找到，尝试其他选择器
      if (!menu) {
        log('尝试其他菜单选择器...');
        const menuSelectors = [
          '[role="menu"][data-state="open"]',
          '[role="listbox"][data-state="open"]',
          '[role="menu"]',
          '[role="listbox"]',
          'div[data-state="open"]'
        ];
        for (const sel of menuSelectors) {
          menu = document.querySelector(sel);
          if (menu) {
            log('通过选择器找到菜单:', sel);
            break;
          }
        }
      }

      // 如果还是没找到，查找最近出现的弹出层
      if (!menu) {
        log('尝试查找弹出层...');
        const popovers = document.querySelectorAll('[role="dialog"], [data-radix-popper-content-wrapper], div[class*="popover"], div[class*="dropdown"]');
        for (const pop of popovers) {
          if (pop.offsetParent !== null) {
            const items = pop.querySelectorAll('button, [role="menuitem"], [role="option"]');
            if (items.length > 0) {
              menu = pop;
              log('找到弹出层，包含选项数量:', items.length);
              break;
            }
          }
        }
      }

      if (!menu) {
        log('⚠️ 未找到下拉菜单，可能点击未生效');
        // 再次点击尝试
        await this.simulateClick(aspectBtn);
        await sleep(800);

        // 再次查找
        if (menuId) {
          menu = document.getElementById(menuId);
        }
        if (!menu) {
          menu = document.querySelector('[role="menu"][data-state="open"]') ||
                  document.querySelector('[role="listbox"][data-state="open"]');
        }

        if (!menu) {
          log('⚠️ 再次尝试仍未找到菜单');
          document.body.click();
          return false;
        }
      }

      log('找到菜单容器:', menu.id || menu.className || menu.tagName);

      // 在菜单中查找选项
      const items = menu.querySelectorAll('[role="menuitem"], [role="option"], button, div[role="menuitemradio"]');
      log('菜单选项数量:', items.length);

      let foundAndClicked = false;
      for (const item of items) {
        const text = (item.textContent || '').trim();
        const ariaLabel = item.getAttribute('aria-label') || '';
        log('选项:', text, 'aria-label:', ariaLabel);

        // 匹配目标比例
        if (text === ratio || text.includes(ratio) || ariaLabel.includes(ratio)) {
          log('🎯 找到目标选项:', text, '准备点击');
          await this.simulateClick(item);
          await sleep(500);
          foundAndClicked = true;
          break;
        }
      }

      if (!foundAndClicked) {
        log('⚠️ 未找到匹配的比例选项:', ratio);
        // 关闭菜单
        document.body.click();
        await sleep(300);
        return false;
      }

      // 验证设置结果
      await sleep(300);
      const newSpanEl = aspectBtn.querySelector('span');
      const newText = newSpanEl ? newSpanEl.textContent.trim() : (aspectBtn.textContent || '').trim();
      log('设置后的宽高比:', newText);

      if (newText === ratio || newText.includes(ratio)) {
        log('✅ 画面比例设置成功:', ratio);
        updateStatus('画面比例设置完成');
        return true;
      } else {
        log('⚠️ 设置可能未生效，当前显示:', newText);
        return false;
      }
    },

    // 设置分辨率
    setResolution: async function(resolution) {
      log('设置分辨率:', resolution);

      // 精确选择器：aria-label="视频分辨率" 的 radiogroup
      const resGroup = document.querySelector('div[aria-label="视频分辨率"][role="radiogroup"]');
      if (!resGroup) {
        log('⚠️ 未找到分辨率切换组');
        return false;
      }

      // 目标文本映射
      const targetText = resolution.toLowerCase().includes('480') ? '480p' :
                         resolution.toLowerCase().includes('720') ? '720p' :
                         resolution.toLowerCase().includes('1080') ? '1080p' : resolution;

      const radioButtons = resGroup.querySelectorAll('button[role="radio"]');
      for (const btn of radioButtons) {
        const text = btn.textContent || '';
        log('分辨率按钮:', text, 'aria-checked:', btn.getAttribute('aria-checked'));

        if (text.includes(targetText)) {
          const isChecked = btn.getAttribute('aria-checked') === 'true';
          if (!isChecked) {
            log('点击设置分辨率:', targetText);
            await this.simulateClick(btn);
            await sleep(500);
            return true;
          } else {
            log('✅ 分辨率已设置为:', targetText);
            return true;
          }
        }
      }

      log('⚠️ 未找到分辨率按钮:', targetText);
      return false;
    },

    // 等待提交按钮可用
    waitForSubmitButtonReady: async function(timeout = 30000) {
      log('等待提交按钮变为可用状态...');

      const startTime = Date.now();

      while (Date.now() - startTime < timeout) {
        // 查找可能的提交按钮
        const buttons = document.querySelectorAll('button[type="submit"], button[aria-label*="Send"], button[aria-label*="Generate"], button[aria-label*="发送"], button[aria-label*="生成"]');

        for (const btn of buttons) {
          // 检查按钮是否可用（非禁用状态）
          if (!btn.disabled && btn.offsetParent !== null) {
            log('找到可用的提交按钮:', btn.getAttribute('aria-label') || btn.textContent);
            return btn;
          }
        }

        // 也检查输入框附近的按钮
        const inputBox = document.querySelector('textarea, div[contenteditable="true"], div.ProseMirror');
        if (inputBox) {
          const container = inputBox.closest('div[class*="container"], div[class*="wrapper"], form, div');
          if (container) {
            const nearbyButtons = container.querySelectorAll('button');
            for (const btn of nearbyButtons) {
              if (!btn.disabled && btn.offsetParent !== null) {
                const ariaLabel = btn.getAttribute('aria-label') || '';
                const btnText = btn.textContent || '';
                // 排除非提交按钮
                const excludeKeywords = ['attach', 'emoji', 'file', 'upload', '附件', '表情', '文件', '上传'];
                if (!excludeKeywords.some(kw => ariaLabel.toLowerCase().includes(kw) || btnText.toLowerCase().includes(kw))) {
                  log('找到附近可用的按钮:', ariaLabel || btnText);
                  return btn;
                }
              }
            }
          }
        }

        log('按钮仍不可用，等待中...');
        await sleep(1000);
      }

      log('⚠️ 等待按钮超时');
      return null;
    },

    // 查找并点击提交按钮
    findAndClickSubmit: async function() {
      const buttonSelectors = [
        'button[aria-label*="Send"]',
        'button[aria-label*="Generate"]',
        'button[aria-label*="Submit"]',
        'button[aria-label*="发送"]',
        'button[aria-label*="生成"]',
        'button[data-testid*="send"]',
        'button[data-testid*="submit"]',
        'button[type="submit"]'
      ];

      for (const selector of buttonSelectors) {
        try {
          const buttons = document.querySelectorAll(selector);
          for (const btn of buttons) {
            if (btn && !btn.disabled && btn.offsetParent !== null) {
              log('找到提交按钮:', selector);
              await this.simulateClick(btn);
              await sleep(500);
              return true;
            }
          }
        } catch (e) {}
      }

      // 尝试查找输入框附近的按钮
      const inputBox = document.querySelector('textarea, div[contenteditable="true"], div.ProseMirror');
      if (inputBox) {
        const container = inputBox.closest('div[class*="container"], div[class*="wrapper"], form, div');
        if (container) {
          const buttons = container.querySelectorAll('button:not([disabled])');
          for (const btn of buttons) {
            const inputRect = inputBox.getBoundingClientRect();
            const btnRect = btn.getBoundingClientRect();

            const isRightSide = btnRect.left >= inputRect.right - 100;
            const isSameRow = Math.abs(btnRect.top - inputRect.top) < 50;

            if (isRightSide && isSameRow) {
              const ariaLabel = btn.getAttribute('aria-label') || '';
              const btnText = btn.textContent || '';
              const excludeKeywords = ['attach', 'emoji', 'image', 'file', 'upload', '附件', '表情', '图片', '文件', '上传'];

              if (!excludeKeywords.some(kw => ariaLabel.toLowerCase().includes(kw) || btnText.toLowerCase().includes(kw))) {
                log('找到输入框附近的按钮:', ariaLabel);
                await this.simulateClick(btn);
                return true;
              }
            }
          }
        }
      }

      return false;
    },

    // 执行任务
    executeTask: async function(task) {
      if (isExecuting) {
        log('已有任务在执行中');
        return { success: false, error: '已有任务在执行中' };
      }

      // 清理状态
      if (videoCheckTimer) clearInterval(videoCheckTimer);
      if (timeoutTimer) clearTimeout(timeoutTimer);
      if (window._syaObserver) window._syaObserver.disconnect();

      window.__syaVideoUrls = [];
      window.__syaCapturedResponses = [];
      processedVideoUrls = new Set();
      taskStartTime = Date.now();

      isExecuting = true;
      currentTask = task;
      log('🚀 开始执行任务:', task.task_id, 'params:', task.params);

      try {
        updateStatus('等待页面加载...');
        await sleep(CONFIG.PAGE_READY_WAIT);

        // 查找输入框
        updateStatus('查找输入框...');

        const inputSelectors = [
          'textarea[placeholder*="message"]',
          'textarea[placeholder*="Ask"]',
          'textarea[placeholder*="Describe"]',
          'textarea[placeholder*="想象"]',
          'div[contenteditable="true"]',
          'div.ProseMirror',
          'textarea:not([disabled])'
        ];

        let inputBox = null;
        try {
          inputBox = await this.waitForElement(inputSelectors, 15000);
        } catch (e) {
          updateStatus('未找到输入框');
          isExecuting = false;
          return { success: false, error: '无法找到输入框' };
        }

        log('找到输入框:', inputBox.tagName, inputBox.placeholder || inputBox.contentEditable);

        // 0. 根据model_id切换模式（视频/图像）
        if (task.model_id && task.model_id.includes('video')) {
          updateStatus('切换到视频模式...');
          await this.switchToVideoMode();
          await sleep(500);
        }

        // 1. 先填写提示词
        updateStatus('填写提示词...');
        log('原始提示词:', task.prompt);
        this.simulateInput(inputBox, task.prompt);
        await sleep(500);

        // 验证提示词是否填入成功
        let inputContent = '';
        if (inputBox.isContentEditable || inputBox.contentEditable === 'true') {
          inputContent = inputBox.innerText || inputBox.textContent || '';
        } else {
          inputContent = inputBox.value || '';
        }
        log('输入框内容:', inputContent.substring(0, 100));

        if (!inputContent || inputContent.length < 5) {
          log('⚠️ 提示词可能未正确填入，尝试重新填写');
          this.simulateInput(inputBox, task.prompt);
          await sleep(500);
        }

        // 2. 设置参数（分辨率、时长、画面比例）
        updateStatus('设置参数...');
        await this.setParameters(task.params);
        await sleep(500);

        // 3. 最后上传图片（如果有）- 放在填写提示词之后
        if (task.images && task.images.length > 0) {
          updateStatus('上传图片...');
          await this.uploadImages(task.images);

          // 等待图片处理完成，提交按钮变为可用
          updateStatus('等待图片处理...');
          await sleep(2000);

          // 等待提交按钮可用
          const readyBtn = await this.waitForSubmitButtonReady(30000);
          if (readyBtn) {
            log('提交按钮已就绪');
          } else {
            log('⚠️ 提交按钮可能仍处于禁用状态');
          }
        }

        // 4. 最终检查参数设置（确保所有设置正确）
        updateStatus('检查参数设置...');
        await this.verifyAndFixParameters(task.params);
        await sleep(500);

        // 5. 提交任务
        updateStatus('提交任务...');

        const clicked = await this.findAndClickSubmit();

        if (!clicked) {
          log('未找到按钮，尝试 Enter 键');
          inputBox.dispatchEvent(new KeyboardEvent('keydown', {
            key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true
          }));
        }

        taskSubmittedTime = Date.now();
        log('📤 任务已提交，时间:', taskSubmittedTime);

        updateStatus('任务已提交，等待视频生成...');

        // 等待更长时间后再开始监控，避免检测到示例视频
        await sleep(15000);

        // 重新扫描并记录页面上当前所有视频（包括示例视频）
        log('📊 扫描页面上已存在的视频...');
        const existingVideos = document.querySelectorAll('video[src], video source[src], a[href*=".mp4"]');
        for (const v of existingVideos) {
          const src = v.src || v.href || v.getAttribute('src') || v.closest('video')?.src;
          if (src && !processedVideoUrls.has(src)) {
            processedVideoUrls.add(src);
            log('📝 记录已存在的视频:', src);
          }
        }
        log('已记录的视频数量:', processedVideoUrls.size);

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

    const observer = new MutationObserver(() => {
      checkForVideo(taskId);
    });
    observer.observe(document.body, { childList: true, subtree: true });
    window._syaObserver = observer;
  }

  function checkForVideo(taskId) {
    if (window.__syaVideoUrls && window.__syaVideoUrls.length > 0) {
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

    const videoSelectors = ['video[src]', 'video source[src]', 'a[href*=".mp4"]'];

    for (const selector of videoSelectors) {
      const elements = document.querySelectorAll(selector);
      for (const el of elements) {
        const src = el.src || el.href || el.getAttribute('src');
        if (src && !processedVideoUrls.has(src)) {
          if (el.tagName === 'VIDEO' || el.tagName === 'SOURCE') {
            const video = el.tagName === 'VIDEO' ? el : el.closest('video');
            if (video && video.readyState >= 2) {
              processedVideoUrls.add(src);
              log('🎬 检测到已加载视频:', src);
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
    if (videoCheckTimer) clearInterval(videoCheckTimer);
    if (timeoutTimer) clearTimeout(timeoutTimer);
    if (window._syaObserver) window._syaObserver.disconnect();

    updateStatus('检测到视频，开始下载...');
    log('📥 开始下载视频:', videoUrl);

    let blob = null;

    // 尝试下载
    if (window.__syaVideoUrls && window.__syaVideoUrls.length > 0) {
      const candidateUrls = window.__syaVideoUrls
        .filter(u => {
          const urlObj = typeof u === 'object' ? u : { url: u, time: Date.now() };
          return urlObj.time > (taskSubmittedTime || 0);
        })
        .map(u => typeof u === 'object' ? u.url : u);

      for (const url of candidateUrls) {
        if (url && !url.startsWith('blob:')) {
          try {
            const response = await fetch(url, { mode: 'cors', credentials: 'include' });
            if (response.ok) {
              blob = await response.blob();
              if (blob.size > 10000) break;
              blob = null;
            }
          } catch (e) {
            log('❌ 下载失败:', e.message);
          }
        }
      }
    }

    if (!blob && videoUrl && !videoUrl.startsWith('blob:')) {
      try {
        const response = await fetch(videoUrl, { mode: 'cors', credentials: 'include' });
        blob = await response.blob();
      } catch (e) {}
    }

    if (!blob && videoUrl && videoUrl.startsWith('blob:')) {
      try {
        const response = await fetch(videoUrl);
        blob = await response.blob();
      } catch (e) {}
    }

    if (!blob || blob.size < 10000) {
      updateStatus('视频下载失败');
      handleTaskFailed(taskId, '视频下载失败');
      return;
    }

    // 上传视频
    try {
      updateStatus('上传中...');

      const reader = new FileReader();
      const base64Promise = new Promise((resolve) => {
        reader.onloadend = () => resolve(reader.result);
        reader.onerror = () => resolve(null);
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

      // 通知 background 关闭当前标签页
      log('通知 background 关闭当前页面');
      chrome.runtime.sendMessage({
        action: 'CLOSE_CURRENT_TAB'
      });

    } catch (error) {
      log('视频处理失败:', error);
      handleTaskFailed(taskId, error.message);
    }
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