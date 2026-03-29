/**
 * ShareYourAi 插件配置 (popup 使用)
 * 切换环境只需修改 ENV 值
 */

// 当前环境：'development' 或 'production'
const ENV = 'development';

// 环境配置
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

// 全局配置对象
const config = CONFIG[ENV];