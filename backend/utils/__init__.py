"""
工具函数模块
"""
import hashlib
import secrets
import string
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Optional

from passlib.context import CryptContext

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ============ 密码相关 ============
def hash_password(password: str) -> str:
    """加密密码"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


# ============ Token 相关 ============
def generate_token(length: int = 32) -> str:
    """生成随机 token"""
    return secrets.token_urlsafe(length)


def generate_node_id() -> str:
    """生成节点 ID"""
    import time
    timestamp = int(time.time() * 1000) % 100000000
    random_part = random.randint(1000, 9999)
    return f"N{timestamp}{random_part}"


def generate_task_id() -> str:
    """生成任务 ID"""
    import time
    timestamp = int(time.time() * 1000) % 100000000
    random_part = random.randint(1000, 9999)
    return f"T{timestamp}{random_part}"


def generate_client_id() -> str:
    """生成平台客户 ID"""
    import time
    timestamp = int(time.time() * 1000) % 100000000
    random_part = random.randint(1000, 9999)
    return f"CLIENT-{timestamp}{random_part}"


def generate_api_key() -> str:
    """生成 API Key (sk_ 前缀 + 32位随机字符)"""
    return f"sk_{secrets.token_urlsafe(32)}"


def generate_transaction_id() -> str:
    """生成交易 ID"""
    import time
    timestamp = int(time.time() * 1000) % 100000000
    random_part = random.randint(1000, 9999)
    return f"TXN{timestamp}{random_part}"


def generate_log_id() -> str:
    """生成日志 ID"""
    import time
    timestamp = int(time.time() * 1000) % 100000000
    random_part = random.randint(1000, 9999)
    return f"LOG{timestamp}{random_part}"


# ============ 验证码相关 ============
def generate_code(length: int = 6) -> str:
    """生成数字验证码"""
    return ''.join(random.choices(string.digits, k=length))


# ============ 邮件服务 ============
class EmailService:
    """邮件发送服务"""

    def __init__(self, smtp_server: str, smtp_port: int,
                 smtp_user: str, smtp_password: str):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password

    def send_verification_code(self, to_email: str, code: str) -> bool:
        """发送验证码邮件"""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = 'ShareYourAi 邮箱验证码'
            msg['From'] = self.smtp_user
            msg['To'] = to_email

            # 纯文本版本
            text = f'您的验证码是：{code}，有效期5分钟。请勿泄露给他人。'

            # HTML版本
            html = f'''
            <div style="padding: 20px; background: #f5f5f5; border-radius: 8px;">
                <h2 style="color: #4F46E5;">ShareYourAi 邮箱验证</h2>
                <p>您的验证码是：</p>
                <p style="font-size: 32px; font-weight: bold; color: #4F46E5; letter-spacing: 5px;">
                    {code}
                </p>
                <p style="color: #666;">验证码有效期 5 分钟，请勿泄露给他人。</p>
                <hr style="margin: 20px 0; border: none; border-top: 1px solid #ddd;">
                <p style="color: #999; font-size: 12px;">此邮件由系统自动发送，请勿回复。</p>
            </div>
            '''

            msg.attach(MIMEText(text, 'plain'))
            msg.attach(MIMEText(html, 'html'))

            # 发送邮件
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.smtp_user, to_email, msg.as_string())

            return True
        except Exception as e:
            print(f"发送邮件失败: {e}")
            return False


# ============ 文件校验相关 ============
def get_file_type_from_header(header_bytes: bytes) -> Optional[str]:
    """根据文件头判断文件类型"""
    if len(header_bytes) < 8:
        return None

    # MP4/MOV: ftyp
    if header_bytes[4:8] == b'ftyp':
        return 'mp4'

    # WebM
    if header_bytes[0:4] == b'\x1a\x45\xdf\xa3':
        return 'webm'

    # PNG
    if header_bytes[0:8] == b'\x89PNG\r\n\x1a\n':
        return 'png'

    # JPEG
    if header_bytes[0:3] == b'\xff\xd8\xff':
        return 'jpg'

    # GIF
    if header_bytes[0:6] in (b'GIF87a', b'GIF89a'):
        return 'gif'

    return None


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} TB"


# ============ 时间相关 ============
def get_expire_time(days: int = 3) -> datetime:
    """获取冻结期结束时间"""
    return datetime.now() + timedelta(days=days)


def is_same_day(dt1: datetime, dt2: datetime = None) -> bool:
    """判断是否是同一天"""
    if dt2 is None:
        dt2 = datetime.now()
    return dt1.date() == dt2.date()


def get_today_str() -> str:
    """获取今日日期字符串"""
    return datetime.now().strftime("%Y-%m-%d")