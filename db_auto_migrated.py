import os
import sys
from flask_migrate import migrate, upgrade
from app import create_app, db

app = create_app()


def auto_migrate():
    """
    自动检测模型变动并升级数据库
    """
    with app.app_context():
        # 1. 确保 migrations 目录存在
        if not os.path.exists('migrations'):
            print("未找到 migrations 文件夹，请先运行 'flask db init'")
            return

        print("正在检测数据库模型变动...")

        # 2. 尝试生成迁移脚本 (对应 flask db migrate)
        # 这里的 message 使用时间戳防止冲突
        import time
        migration_msg = f"auto_migration_{int(time.time())}"

        try:
            # 以此捕获 stdout 防止 Alembic 输出过多干扰信息，或保留以供调试
            migrate(message=migration_msg)
        except Exception as e:
            print(f"生成迁移脚本时遇到提示 (可能是没有变动): {e}")

        # 3. 执行升级 (对应 flask db upgrade)
        print("正在执行数据库升级...")
        try:
            upgrade()
            print("数据库已成功同步到最新版本！")
        except Exception as e:
            print(f"升级失败: {e}")


if __name__ == '__main__':
    auto_migrate()