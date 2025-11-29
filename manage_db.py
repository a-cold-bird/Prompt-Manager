import os
import time
from flask_migrate import migrate, upgrade, init
from app import create_app, db

# 1. 创建应用上下文
app = create_app()


def sync_database():
    """
    一键数据库同步工具 (One-Click DB Sync)
    功能：自动初始化 -> 检测模型变动 -> 生成迁移脚本 -> 应用到数据库
    """
    print("=" * 50)
    print("🛠️  Prompt Manager 数据库自动同步工具")
    print("=" * 50)

    with app.app_context():
        # --- 第一步：检查初始化 ---
        if not os.path.exists('migrations'):
            print("📦 未检测到 migrations 文件夹，正在初始化...")
            try:
                init()
                print("✅ 初始化完成！")
            except Exception as e:
                print(f"❌ 初始化失败: {e}")
                return

        # --- 第二步：检测变动 (Migrate) ---
        print("🔍 正在扫描模型变动 (Models vs Database)...")

        # 生成一个唯一的迁移消息，包含时间戳，避免冲突
        migration_message = f"update_{int(time.time())}"

        try:
            # 尝试生成迁移脚本
            # 注意：如果没有变动，Alembic 可能会生成一个空脚本或什么都不做，这很正常
            migrate(message=migration_message)
        except Exception as e:
            print(f"⚠️  生成脚本阶段提示 (通常可忽略): {e}")

        # --- 第三步：应用变动 (Upgrade) ---
        print("🚀 正在执行数据库升级 (Upgrade)...")
        try:
            upgrade()
            print("\n✅ 数据库已成功同步到最新版本！")
        except Exception as e:
            print(f"\n❌ 升级失败: {e}")
            print("提示：如果提示'table already exists'，说明数据库和迁移记录不匹配。")
            print("解决：如果是开发环境，可尝试删除 data.sqlite 后重新运行此脚本。")


if __name__ == '__main__':
    sync_database()