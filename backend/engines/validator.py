"""
结果校验引擎
"""
import json
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import PluginTask, PluginModel, PluginRiskLog
from redis_client import redis_client


class ValidationResult:
    """校验结果"""

    def __init__(self):
        self.passed = True
        self.warnings = []
        self.errors = []
        self.details = {}

    def add_error(self, check_name: str, message: str):
        """添加错误"""
        self.passed = False
        self.errors.append({"check": check_name, "message": message})
        self.details[check_name] = {"status": "failed", "message": message}

    def add_warning(self, check_name: str, message: str):
        """添加警告"""
        self.warnings.append({"check": check_name, "message": message})
        self.details[check_name] = {"status": "warning", "message": message}

    def add_pass(self, check_name: str, message: str):
        """添加通过"""
        self.details[check_name] = {"status": "passed", "message": message}

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "warnings": self.warnings,
            "errors": self.errors,
            "details": self.details
        }


class TaskValidator:
    """任务结果校验器"""

    def __init__(self, db: Session):
        self.db = db

    def validate(self, task: PluginTask, proof: dict) -> ValidationResult:
        """执行完整校验"""
        result = ValidationResult()

        # 获取模型配置
        model = self.db.query(PluginModel).filter(
            PluginModel.model_id == task.model_id
        ).first()

        if not model:
            result.add_error("model", "模型配置不存在")
            return result

        # 1. 时间合理性校验
        self._check_time(task, proof, model, result)

        # 2. 文件有效性校验
        self._check_file(task, proof, model, result)

        # 3. 链路完整性校验
        self._check_proof_chain(task, proof, model, result)

        # 4. 频率限制校验
        self._check_frequency(task, model, result)

        # 保存校验结果
        task.validation_result = json.dumps(result.to_dict(), ensure_ascii=False)
        task.validation_status = 'passed' if result.passed else 'failed'
        self.db.commit()

        # 如果校验失败，记录风控日志
        if not result.passed:
            self._log_risk(task, result)

        return result

    def _check_time(self, task: PluginTask, proof: dict, model: PluginModel, result: ValidationResult):
        """时间合理性校验"""
        duration = task.duration_seconds

        if not duration:
            result.add_error("time", "任务耗时未知")
            return

        # 检查最小耗时
        if duration < model.min_duration:
            result.add_error("time", f"耗时 {duration} 秒小于最小要求 {model.min_duration} 秒")
            return

        # 检查最大耗时
        if duration > model.max_duration:
            result.add_warning("time", f"耗时 {duration} 秒超过建议值 {model.max_duration} 秒")
        else:
            result.add_pass("time", f"耗时 {duration} 秒，在合理范围内")

        # 检查时间顺序
        if proof:
            request_time = proof.get('request_time')
            video_detected_time = proof.get('video_detected_time')

            if request_time and video_detected_time:
                if video_detected_time < request_time:
                    result.add_error("time_sequence", "时间顺序异常：视频检测时间早于请求时间")
                else:
                    result.add_pass("time_sequence", "时间顺序正常")

    def _check_file(self, task: PluginTask, proof: dict, model: PluginModel, result: ValidationResult):
        """文件有效性校验"""
        file_size = task.file_size or proof.get('video_size')

        if not file_size:
            result.add_warning("file", "文件大小未知")
            return

        # 检查最小文件大小
        if file_size < model.min_file_size:
            result.add_error("file_size", f"文件大小 {file_size} 字节小于最小要求 {model.min_file_size} 字节")
            return

        # 检查最大文件大小
        if file_size > model.max_file_size:
            result.add_error("file_size", f"文件大小 {file_size} 字节超过最大限制 {model.max_file_size} 字节")
            return

        result.add_pass("file_size", f"文件大小 {file_size / 1024 / 1024:.2f} MB，在允许范围内")

        # 检查文件格式
        file_format = task.file_format
        if file_format:
            allowed_formats = []
            if model.allowed_formats:
                try:
                    allowed_formats = json.loads(model.allowed_formats)
                except:
                    pass

            if allowed_formats and file_format not in allowed_formats:
                result.add_error("file_format", f"文件格式 {file_format} 不在允许列表中")
            else:
                result.add_pass("file_format", f"文件格式 {file_format}，符合要求")

    def _check_proof_chain(self, task: PluginTask, proof: dict, model: PluginModel, result: ValidationResult):
        """链路完整性校验"""
        if not proof:
            result.add_error("proof", "缺少链路证据")
            return

        # 检查 AI 任务 ID
        ai_task_id = proof.get('ai_task_id')
        if model.min_status_checks > 0 and not ai_task_id:
            result.add_error("ai_task_id", "缺少 AI 任务 ID")
        elif ai_task_id:
            result.add_pass("ai_task_id", f"AI 任务 ID: {ai_task_id}")

        # 检查状态查询次数
        status_checks = proof.get('status_checks', [])
        if len(status_checks) < model.min_status_checks:
            result.add_warning("status_checks",
                               f"状态查询次数 {len(status_checks)} 少于建议值 {model.min_status_checks}")
        else:
            result.add_pass("status_checks", f"状态查询 {len(status_checks)} 次")

        # 检查原始视频 URL
        video_url_original = proof.get('video_url_original')
        if video_url_original:
            # 检查域名
            allowed_domains = []
            if model.allowed_video_domains:
                try:
                    allowed_domains = json.loads(model.allowed_video_domains)
                except:
                    pass

            if allowed_domains:
                from urllib.parse import urlparse
                domain = urlparse(video_url_original).netloc
                is_allowed = any(
                    domain.endswith(d.lstrip('*.')) or domain == d.lstrip('*.')
                    for d in allowed_domains
                )
                if not is_allowed:
                    result.add_warning("video_domain", f"视频来源域名 {domain} 不在允许列表中")
                else:
                    result.add_pass("video_domain", f"视频来源域名验证通过")
        else:
            result.add_warning("video_url", "缺少原始视频 URL")

    def _check_frequency(self, task: PluginTask, model: PluginModel, result: ValidationResult):
        """频率限制校验"""
        # 检查节点每小时任务数
        if task.assigned_node_id:
            node_hourly = redis_client.incr_node_hourly_tasks(task.assigned_node_id)
            if node_hourly > model.max_tasks_per_hour:
                result.add_warning("node_frequency",
                                   f"节点本小时任务数 {node_hourly} 超过限制 {model.max_tasks_per_hour}")
            else:
                result.add_pass("node_frequency", f"节点本小时任务数 {node_hourly}")

        # 检查用户每小时任务数
        if task.user_id:
            user_hourly = redis_client.incr_user_hourly_tasks(task.user_id)
            if user_hourly > model.max_tasks_per_user_hour:
                result.add_warning("user_frequency",
                                   f"用户本小时任务数 {user_hourly} 超过限制 {model.max_tasks_per_user_hour}")
            else:
                result.add_pass("user_frequency", f"用户本小时任务数 {user_hourly}")

    def _log_risk(self, task: PluginTask, result: ValidationResult):
        """记录风控日志"""
        risk_log = PluginRiskLog(
            task_id=task.task_id,
            node_id=task.assigned_node_id,
            user_id=task.user_id,
            risk_type='anomaly',
            risk_level='high' if len(result.errors) > 0 else 'medium',
            description=f"任务校验失败: {', '.join([e['message'] for e in result.errors])}",
            detail=json.dumps(result.to_dict(), ensure_ascii=False)
        )
        self.db.add(risk_log)
        self.db.commit()