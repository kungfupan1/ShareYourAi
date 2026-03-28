"""
初始化管理员账号
"""
from database import SessionLocal
from models import PluginUser
from utils import hash_password

def init_admin():
    db = SessionLocal()

    try:
        # 检查是否已存在管理员
        admin = db.query(PluginUser).filter(PluginUser.username == 'admin').first()

        if admin:
            print("管理员账号已存在")
            # 确保是管理员角色
            admin.role = 'admin'
            db.commit()
            print("已更新为管理员角色")
        else:
            # 创建管理员
            admin = PluginUser(
                username='admin',
                password_hash=hash_password('admin123'),
                email='admin@shareyour.ai',
                role='admin',
                status='active',
                balance=0.0
            )
            db.add(admin)
            db.commit()
            print("管理员账号创建成功")

        print(f"用户名: admin")
        print(f"密码: admin123")

    finally:
        db.close()


if __name__ == '__main__':
    init_admin()