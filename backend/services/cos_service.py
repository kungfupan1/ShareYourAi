"""
COS 云存储服务
"""
import json
from typing import Optional
from datetime import datetime


class COSService:
    """腾讯云 COS 服务封装"""

    def __init__(self, secret_id: str, secret_key: str,
                 bucket: str, region: str):
        self.secret_id = secret_id
        self.secret_key = secret_key
        self.bucket = bucket
        self.region = region
        self._client = None

    @property
    def client(self):
        """延迟初始化 COS 客户端"""
        if self._client is None:
            try:
                from qcloud_cos import CosS3Client, CosConfig
                config = CosConfig(
                    Region=self.region,
                    SecretId=self.secret_id,
                    SecretKey=self.secret_key,
                )
                self._client = CosS3Client(config)
            except ImportError:
                print("警告: qcloud_cos 未安装，COS 功能不可用")
                return None
            except Exception as e:
                print(f"COS 客户端初始化失败: {e}")
                return None
        return self._client

    def get_upload_credentials(self, task_id: str, model_type: str = 'video',
                               expire_seconds: int = 300) -> dict:
        """
        获取上传凭证
        返回前端可以直接使用的上传信息
        """
        # 生成存储路径
        now = datetime.now()
        date_path = now.strftime("%Y/%m")
        ext = 'mp4' if model_type == 'video' else 'png'
        key = f"tasks/{model_type}s/{date_path}/{task_id}.{ext}"

        # 构造上传凭证
        return {
            "bucket": self.bucket,
            "region": self.region,
            "key": key,
            "expire_seconds": expire_seconds,
            # 实际项目中应该生成临时密钥
            # 这里简化处理，直接返回固定密钥（生产环境不推荐）
            "secret_id": self.secret_id,
            "secret_key": self.secret_key,
        }

    def get_file_info(self, key: str) -> Optional[dict]:
        """获取文件信息（不下载文件）"""
        if not self.client:
            return None

        try:
            meta = self.client.head_object(Bucket=self.bucket, Key=key)
            return {
                "size": int(meta.get('Content-Length', 0)),
                "content_type": meta.get('Content-Type', ''),
                "last_modified": meta.get('Last-Modified', ''),
                "etag": meta.get('ETag', ''),
            }
        except Exception as e:
            print(f"获取文件信息失败: {e}")
            return None

    def get_file_header(self, key: str, header_size: int = 32) -> Optional[bytes]:
        """获取文件头部字节（用于格式校验）"""
        if not self.client:
            return None

        try:
            response = self.client.get_object(
                Bucket=self.bucket,
                Key=key,
                Range=f'bytes=0-{header_size - 1}'
            )
            return response['Body'].read()
        except Exception as e:
            print(f"获取文件头失败: {e}")
            return None

    def get_signed_url(self, key: str, expire_seconds: int = 3600) -> Optional[str]:
        """获取签名访问 URL"""
        if not self.client:
            return None

        try:
            url = self.client.get_presigned_url(
                Method='GET',
                Bucket=self.bucket,
                Key=key,
                Expired=expire_seconds
            )
            return url
        except Exception as e:
            print(f"获取签名URL失败: {e}")
            return None

    def delete_file(self, key: str) -> bool:
        """删除文件"""
        if not self.client:
            return False

        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
            return True
        except Exception as e:
            print(f"删除文件失败: {e}")
            return False


# 全局 COS 服务实例（需要在使用前初始化）
cos_service: Optional[COSService] = None


def init_cos_service(secret_id: str, secret_key: str,
                     bucket: str, region: str):
    """初始化 COS 服务"""
    global cos_service
    cos_service = COSService(secret_id, secret_key, bucket, region)
    return cos_service


def get_cos_service() -> Optional[COSService]:
    """获取 COS 服务实例"""
    return cos_service