"""
计费服务 - 平台客户余额管理
"""
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from models import PlatformClient, ClientTransaction, PluginTask
from utils import generate_transaction_id


class BillingService:
    """计费服务"""

    def __init__(self, db: Session):
        self.db = db

    def get_client_by_api_key(self, api_key: str) -> Optional[PlatformClient]:
        """通过 API Key 获取平台客户"""
        return self.db.query(PlatformClient).filter(
            PlatformClient.api_key == api_key
        ).first()

    def check_balance(self, client: PlatformClient, amount: float) -> bool:
        """检查余额是否充足"""
        return client.balance >= amount

    def freeze_balance(self, client: PlatformClient, amount: float, task_id: str) -> bool:
        """
        冻结余额（预扣费）
        在任务提交时调用，将金额从可用余额转入冻结余额
        """
        if client.balance < amount:
            return False

        # 记录变动前余额
        balance_before = client.balance

        # 执行冻结
        client.balance -= amount
        client.frozen_balance = (client.frozen_balance or 0) + amount

        self.db.commit()
        return True

    def confirm_deduction(self, client: PlatformClient, amount: float, task_id: str) -> bool:
        """
        确认扣费
        任务成功时调用，从冻结余额中扣除
        """
        if client.frozen_balance < amount:
            return False

        # 记录变动前余额（可用余额）
        balance_before = client.balance

        # 从冻结余额扣除
        client.frozen_balance -= amount

        # 更新统计
        client.total_spent = (client.total_spent or 0) + amount
        client.total_calls = (client.total_calls or 0) + 1

        # 创建交易记录
        transaction = ClientTransaction(
            transaction_id=generate_transaction_id(),
            client_id=client.client_id,
            type='consume',
            amount=-amount,  # 消费用负数
            balance_before=balance_before,
            balance_after=client.balance,
            related_task_id=task_id,
            remark='任务消费'
        )
        self.db.add(transaction)
        self.db.commit()
        return True

    def refund_frozen(self, client: PlatformClient, amount: float, task_id: str, reason: str = '任务失败退款') -> bool:
        """
        退回冻结金额
        任务失败或取消时调用，将冻结金额退回可用余额
        """
        if client.frozen_balance < amount:
            return False

        # 记录变动前余额
        balance_before = client.balance

        # 退回冻结金额
        client.frozen_balance -= amount
        client.balance += amount

        # 创建交易记录
        transaction = ClientTransaction(
            transaction_id=generate_transaction_id(),
            client_id=client.client_id,
            type='refund',
            amount=amount,  # 退款用正数
            balance_before=balance_before,
            balance_after=client.balance,
            related_task_id=task_id,
            remark=reason
        )
        self.db.add(transaction)
        self.db.commit()
        return True

    def recharge(self, client: PlatformClient, amount: float, operator_id: int = None, remark: str = None) -> bool:
        """
        充值
        """
        if amount <= 0:
            return False

        balance_before = client.balance
        client.balance += amount
        client.total_recharged = (client.total_recharged or 0) + amount

        # 创建交易记录
        transaction = ClientTransaction(
            transaction_id=generate_transaction_id(),
            client_id=client.client_id,
            type='recharge',
            amount=amount,
            balance_before=balance_before,
            balance_after=client.balance,
            operator_id=operator_id,
            remark=remark or '账户充值'
        )
        self.db.add(transaction)
        self.db.commit()
        return True

    def adjust_balance(self, client: PlatformClient, amount: float, operator_id: int, remark: str) -> bool:
        """
        调整余额（管理员操作）
        amount 为正数表示增加，负数表示减少
        """
        if amount == 0:
            return False

        # 检查减少时余额是否充足
        if amount < 0 and client.balance < abs(amount):
            return False

        balance_before = client.balance
        client.balance += amount

        # 创建交易记录
        transaction = ClientTransaction(
            transaction_id=generate_transaction_id(),
            client_id=client.client_id,
            type='adjust',
            amount=amount,
            balance_before=balance_before,
            balance_after=client.balance,
            operator_id=operator_id,
            remark=remark
        )
        self.db.add(transaction)
        self.db.commit()
        return True

    def get_frozen_amount_for_task(self, task: PluginTask) -> float:
        """
        获取任务对应的冻结金额
        通常是 user_price
        """
        return task.user_price or 0.0