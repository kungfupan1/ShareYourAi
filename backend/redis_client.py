"""
Redis 客户端配置
"""
import redis
import json
import os
from typing import Optional, Any

# Redis 配置
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# 创建 Redis 连接池
redis_pool = redis.ConnectionPool.from_url(REDIS_URL, decode_responses=True)


def get_redis():
    """获取 Redis 客户端"""
    return redis.Redis(connection_pool=redis_pool)


class RedisClient:
    """Redis 客户端封装"""

    def __init__(self):
        self.client = get_redis()

    # ============ 验证码相关 ============
    def set_email_code(self, email: str, code: str, expire: int = 300):
        """设置邮箱验证码，默认5分钟过期"""
        key = f"email_code:{email}"
        self.client.setex(key, expire, code)

    def get_email_code(self, email: str) -> Optional[str]:
        """获取邮箱验证码"""
        key = f"email_code:{email}"
        return self.client.get(key)

    def delete_email_code(self, email: str):
        """删除邮箱验证码"""
        key = f"email_code:{email}"
        self.client.delete(key)

    # ============ 任务队列相关 ============
    def push_task(self, task_id: str, priority: int = 0):
        """将任务推入队列"""
        if priority > 0:
            # 高优先级队列
            self.client.lpush("task_queue:high", task_id)
        else:
            # 普通队列
            self.client.lpush("task_queue:normal", task_id)

    def pop_task(self, timeout: int = 5) -> Optional[str]:
        """从队列取出任务（优先取高优先级）"""
        # 先检查高优先级队列
        result = self.client.rpop("task_queue:high")
        if result:
            return result
        # 再检查普通队列
        return self.client.rpop("task_queue:normal")

    def get_queue_length(self) -> dict:
        """获取队列长度"""
        return {
            "high": self.client.llen("task_queue:high"),
            "normal": self.client.llen("task_queue:normal")
        }

    # ============ 节点状态相关 ============
    def set_node_online(self, node_id: str, ttl: int = 120):
        """设置节点在线状态"""
        key = f"node_online:{node_id}"
        self.client.setex(key, ttl, "1")

    def is_node_online(self, node_id: str) -> bool:
        """检查节点是否在线"""
        key = f"node_online:{node_id}"
        return self.client.exists(key) > 0

    def set_node_busy(self, node_id: str, task_id: str, ttl: int = 600):
        """设置节点忙碌状态"""
        key = f"node_busy:{node_id}"
        self.client.setex(key, ttl, task_id)

    def clear_node_busy(self, node_id: str):
        """清除节点忙碌状态"""
        key = f"node_busy:{node_id}"
        self.client.delete(key)

    def get_node_task(self, node_id: str) -> Optional[str]:
        """获取节点当前任务"""
        key = f"node_busy:{node_id}"
        return self.client.get(key)

    # ============ 频率限制相关 ============
    def incr_node_hourly_tasks(self, node_id: str) -> int:
        """增加节点小时任务计数"""
        key = f"node_hourly:{node_id}"
        count = self.client.incr(key)
        if count == 1:
            self.client.expire(key, 3600)
        return count

    def incr_user_hourly_tasks(self, user_id: int) -> int:
        """增加用户小时任务计数"""
        key = f"user_hourly:{user_id}"
        count = self.client.incr(key)
        if count == 1:
            self.client.expire(key, 3600)
        return count

    # ============ WebSocket 会话相关 ============
    def set_ws_session(self, node_id: str, session_id: str, ttl: int = 86400):
        """设置 WebSocket 会话"""
        key = f"ws_session:{node_id}"
        self.client.setex(key, ttl, session_id)

    def get_ws_session(self, node_id: str) -> Optional[str]:
        """获取 WebSocket 会话"""
        key = f"ws_session:{node_id}"
        return self.client.get(key)

    def delete_ws_session(self, node_id: str):
        """删除 WebSocket 会话"""
        key = f"ws_session:{node_id}"
        self.client.delete(key)

    # ============ 统计相关 ============
    def incr_daily_stat(self, stat_key: str, date_str: str = None) -> int:
        """增加每日统计"""
        from datetime import datetime
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")
        key = f"daily_stat:{stat_key}:{date_str}"
        count = self.client.incr(key)
        if count == 1:
            self.client.expire(key, 86400 * 7)  # 保留7天
        return count

    def get_daily_stat(self, stat_key: str, date_str: str = None) -> int:
        """获取每日统计"""
        from datetime import datetime
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")
        key = f"daily_stat:{stat_key}:{date_str}"
        value = self.client.get(key)
        return int(value) if value else 0


# 创建全局实例
redis_client = RedisClient()