"""
派单引擎
"""
import random
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import PluginNode, PluginModel, PluginTask
from redis_client import redis_client


class DispatcherStrategy:
    """派单策略基类"""

    def select_node(self, nodes: List[PluginNode], model_id: str) -> Optional[PluginNode]:
        raise NotImplementedError


class RandomStrategy(DispatcherStrategy):
    """随机策略"""

    def select_node(self, nodes: List[PluginNode], model_id: str) -> Optional[PluginNode]:
        if not nodes:
            return None
        return random.choice(nodes)


class BestNodeStrategy(DispatcherStrategy):
    """优胜略汰策略"""

    def __init__(self,
                 success_rate_weight: float = 0.5,
                 speed_weight: float = 0.3,
                 stability_weight: float = 0.2,
                 base_score: float = 50.0,
                 min_tasks_for_score: int = 10,
                 consecutive_fail_penalty: float = 0.5,
                 recent_tasks_count: int = 10):
        self.success_rate_weight = success_rate_weight
        self.speed_weight = speed_weight
        self.stability_weight = stability_weight
        self.base_score = base_score
        self.min_tasks_for_score = min_tasks_for_score
        self.consecutive_fail_penalty = consecutive_fail_penalty
        self.recent_tasks_count = recent_tasks_count

    def calculate_score(self, node: PluginNode) -> float:
        """计算节点综合评分"""
        # 如果任务数不足，使用基础评分
        if node.total_tasks < self.min_tasks_for_score:
            return self.base_score

        # 成功率评分 (0-100)
        success_rate = node.success_tasks / node.total_tasks if node.total_tasks > 0 else 0
        success_score = success_rate * 100

        # 速度评分 (假设平均耗时200秒为基准)
        # 耗时越短分数越高
        if node.avg_duration and node.avg_duration > 0:
            # 200秒为基准，每少10秒加5分，每多10秒减5分
            speed_score = max(0, min(100, 100 - (node.avg_duration - 200) / 10 * 5))
        else:
            speed_score = self.base_score

        # 稳定性评分 (基于成功率的波动，简化处理)
        stability_score = success_score  # 简化：用成功率代替

        # 综合评分
        total_score = (
            success_score * self.success_rate_weight +
            speed_score * self.speed_weight +
            stability_score * self.stability_weight
        )

        return round(total_score, 2)

    def select_node(self, nodes: List[PluginNode], model_id: str) -> Optional[PluginNode]:
        if not nodes:
            return None

        # 计算每个节点的评分
        scored_nodes = [(node, self.calculate_score(node)) for node in nodes]

        # 按评分排序
        scored_nodes.sort(key=lambda x: x[1], reverse=True)

        # 加权随机选择（评分高的节点有更高概率被选中）
        total_score = sum(score for _, score in scored_nodes)
        if total_score <= 0:
            return random.choice(nodes)

        # 加权随机选择
        r = random.uniform(0, total_score)
        cumulative = 0
        for node, score in scored_nodes:
            cumulative += score
            if r <= cumulative:
                return node

        return scored_nodes[0][0]


class Dispatcher:
    """派单引擎"""

    def __init__(self, db: Session, strategy: DispatcherStrategy = None):
        self.db = db
        self.strategy = strategy or BestNodeStrategy()

    def get_available_nodes(self, model_id: str) -> List[PluginNode]:
        """获取可用节点列表"""
        from models import PluginUser

        # 查询数据库中 idle 的节点
        nodes = self.db.query(PluginNode).join(
            PluginUser, PluginNode.user_id == PluginUser.id
        ).filter(
            PluginNode.status == 'idle',
            PluginUser.is_blacklisted == False
        ).all()

        print(f"[Dispatcher] 找到 {len(nodes)} 个 idle 节点")

        # 筛选支持该模型且 WebSocket 在线的节点
        available_nodes = []
        for node in nodes:
            ws_session = redis_client.get_ws_session(node.node_id)
            print(f"[Dispatcher] 节点 {node.node_id}: ws_session = {ws_session}")

            if not ws_session:
                # 没有活跃的 WebSocket 连接，更新数据库状态并跳过
                print(f"[Dispatcher] 节点 {node.node_id} 无 WebSocket，设为 offline")
                node.status = 'offline'
                continue

            # 如果没有指定支持的模型，默认支持所有模型
            if not node.supported_models or node.supported_models == '[]':
                available_nodes.append(node)
            else:
                import json
                try:
                    models = json.loads(node.supported_models)
                    if model_id in models:
                        available_nodes.append(node)
                except:
                    available_nodes.append(node)

        if available_nodes:
            self.db.commit()

        print(f"[Dispatcher] 可用节点: {[n.node_id for n in available_nodes]}")
        return available_nodes

    def dispatch(self, task: PluginTask) -> Optional[PluginNode]:
        """派单"""
        # 获取可用节点
        available_nodes = self.get_available_nodes(task.model_id)

        if not available_nodes:
            return None

        # 使用策略选择节点
        selected_node = self.strategy.select_node(available_nodes, task.model_id)

        if selected_node:
            # 更新任务
            task.assigned_node_id = selected_node.node_id
            task.assigned_time = datetime.now()
            task.status = 'processing'

            # 更新节点状态
            selected_node.status = 'busy'
            selected_node.current_task_id = task.task_id

            # 记录 Redis
            redis_client.set_node_busy(selected_node.node_id, task.task_id)

            self.db.commit()

        return selected_node

    def release_node(self, node_id: str):
        """释放节点"""
        node = self.db.query(PluginNode).filter(
            PluginNode.node_id == node_id
        ).first()

        if node:
            node.status = 'idle'
            node.current_task_id = None
            redis_client.clear_node_busy(node_id)
            self.db.commit()

    def update_node_score(self, node_id: str, success: bool, duration: float):
        """更新节点评分相关数据"""
        node = self.db.query(PluginNode).filter(
            PluginNode.node_id == node_id
        ).first()

        if not node:
            return

        # 更新统计
        node.total_tasks += 1
        if success:
            node.success_tasks += 1
        else:
            node.failed_tasks += 1

        # 更新平均耗时
        if success and duration > 0:
            if node.avg_duration > 0:
                node.avg_duration = (node.avg_duration * (node.success_tasks - 1) + duration) / node.success_tasks
            else:
                node.avg_duration = duration

        # 更新今日统计
        from utils import get_today_str, is_same_day
        today = get_today_str()
        if node.today_date != today:
            node.today_date = today
            node.today_tasks = 0
            node.today_success = 0

        node.today_tasks += 1
        if success:
            node.today_success += 1

        # 更新收益
        if success:
            node.total_earnings = (node.total_earnings or 0) + 0.07  # 默认奖励

        self.db.commit()


# 策略配置
def get_strategy_from_config(db: Session) -> DispatcherStrategy:
    """从数据库配置获取策略"""
    from models import PluginSystemConfig

    config = db.query(PluginSystemConfig).filter(
        PluginSystemConfig.config_key == 'dispatcher_strategy'
    ).first()

    if config:
        import json
        try:
            config_data = json.loads(config.config_value)
            strategy_type = config_data.get('strategy_type', 'best_node')

            if strategy_type == 'random':
                return RandomStrategy()
            else:
                return BestNodeStrategy(
                    success_rate_weight=config_data.get('success_rate_weight', 0.5),
                    speed_weight=config_data.get('speed_weight', 0.3),
                    stability_weight=config_data.get('stability_weight', 0.2),
                    base_score=config_data.get('base_score', 50.0),
                    min_tasks_for_score=config_data.get('min_tasks_for_score', 10),
                    consecutive_fail_penalty=config_data.get('consecutive_fail_penalty', 0.5),
                    recent_tasks_count=config_data.get('recent_tasks_count', 10)
                )
        except:
            pass

    return BestNodeStrategy()