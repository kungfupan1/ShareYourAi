"""
数据库初始化脚本
"""
from database import engine, Base, SessionLocal
from models import (
    PluginUser, PluginModel, PluginSystemConfig,
    PluginStorageBucket
)
from utils import hash_password, generate_token
import json


def init_database():
    """初始化数据库"""
    print("创建数据库表...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # 检查是否已有管理员
        admin = db.query(PluginUser).filter(PluginUser.role == 'admin').first()
        if not admin:
            print("创建默认管理员...")
            admin = PluginUser(
                username='admin',
                password_hash=hash_password('admin123'),
                email='admin@shareyourai.com',
                role='admin',
                is_verified=True
            )
            db.add(admin)
            db.commit()
            print(f"管理员创建成功: admin / admin123")

        # 检查是否已有模型
        models_count = db.query(PluginModel).count()
        if models_count == 0:
            print("创建默认模型...")

            models = [
                PluginModel(
                    model_id='grok_video',
                    name='Grok 视频生成',
                    model_type='video',
                    provider='Grok',
                    page_url='https://grok.com/imagine',
                    timeout=300,
                    max_retry=3,
                    node_reward=0.1,
                    user_price=0.30,
                    min_duration=60,
                    max_duration=600,
                    min_file_size=1048576,
                    max_file_size=209715200,
                    allowed_formats=json.dumps(['mp4', 'webm']),
                    min_status_checks=2,
                    allowed_video_domains=json.dumps(['*.grok.com', '*.x.ai']),
                    max_tasks_per_hour=20,
                    max_tasks_per_user_hour=100
                ),
                PluginModel(
                    model_id='sora2_video',
                    name='Sora2 视频生成',
                    model_type='video',
                    provider='OpenAI',
                    page_url='https://sora.com',
                    timeout=300,
                    max_retry=3,
                    node_reward=0.07,
                    user_price=0.10,
                    min_duration=60,
                    max_duration=600,
                    min_file_size=1048576,
                    max_file_size=209715200,
                    allowed_formats=json.dumps(['mp4', 'webm']),
                    min_status_checks=2,
                    allowed_video_domains=json.dumps(['*.sora.com', '*.openai.com']),
                    max_tasks_per_hour=20,
                    max_tasks_per_user_hour=100
                ),
                PluginModel(
                    model_id='runway_video',
                    name='Runway 视频生成',
                    model_type='video',
                    provider='Runway',
                    page_url='https://runwayml.com',
                    timeout=300,
                    max_retry=3,
                    node_reward=0.08,
                    user_price=0.12,
                    min_duration=60,
                    max_duration=600,
                    min_file_size=1048576,
                    max_file_size=209715200,
                    allowed_formats=json.dumps(['mp4', 'webm']),
                    min_status_checks=2,
                    allowed_video_domains=json.dumps(['*.runwayml.com']),
                    max_tasks_per_hour=20,
                    max_tasks_per_user_hour=100
                )
            ]

            for model in models:
                db.add(model)

            db.commit()
            print(f"创建了 {len(models)} 个模型")

        # 创建系统配置
        configs = [
            ('external_api_key', generate_token(), 'string', '外部 API Key'),
            ('task_timeout', '300', 'number', '任务超时时间（秒）'),
            ('node_heartbeat_timeout', '60', 'number', '节点心跳超时（秒）'),
            ('min_withdrawal', '10', 'number', '最低提现金额（元）'),
            ('max_withdrawal', '5000', 'number', '最高提现金额（元）'),
            ('daily_withdrawal_limit', '10000', 'number', '每日提现上限（元）'),
            ('daily_withdrawal_count', '3', 'number', '每日提现次数'),
            ('earning_freeze_days', '3', 'number', '收益冻结期（天）'),
        ]

        for key, value, config_type, description in configs:
            existing = db.query(PluginSystemConfig).filter(
                PluginSystemConfig.config_key == key
            ).first()
            if not existing:
                config = PluginSystemConfig(
                    config_key=key,
                    config_value=value,
                    config_type=config_type,
                    description=description
                )
                db.add(config)

        db.commit()
        print("系统配置初始化完成")

        print("\n数据库初始化完成!")
        print("\n默认账号:")
        print("  管理员: admin / admin123")
        print("\n启动服务:")
        print("  uvicorn main:app --reload --port 8000")

    finally:
        db.close()


if __name__ == "__main__":
    init_database()