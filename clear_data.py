# -*- coding: utf-8 -*-
"""
清空数据库脚本 (Clear Database Script)
功能：清空所有导入的数据，但保留管理员账户和系统设置
"""

import os
import sys
import io
from app import create_app, db
from models import Image, ReferenceImage, Tag, User, SystemSetting
from utils import remove_physical_file
from config import Config

# 配置标准输出为UTF-8编码
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def clear_all_data():
    """清空所有导入数据"""
    app = create_app()

    with app.app_context():
        print("=" * 60)
        print("[Prompt Manager] 数据清空工具")
        print("=" * 60)
        print()

        try:
            # 统计当前数据
            total_images = Image.query.count()
            total_tags = Tag.query.count()
            total_refs = ReferenceImage.query.count()
            total_users = User.query.count()
            total_settings = SystemSetting.query.count()

            print("[INFO] 当前数据库统计：")
            print(f"   - 图片数量: {total_images}")
            print(f"   - 参考图数量: {total_refs}")
            print(f"   - 标签数量: {total_tags}")
            print(f"   - 用户数量: {total_users}")
            print(f"   - 系统设置: {total_settings}")
            print()

            if total_images == 0:
                print("[SUCCESS] 数据库已为空，无需清空。")
                return

            # 确认操作
            confirmation = input("[WARN] 确认清空所有图片和参考图数据？(y/N): ").strip().lower()
            if confirmation != 'y':
                print("[CANCEL] 操作已取消。")
                return

            print("\n[PROGRESS] 正在清空数据...")

            # 删除所有图片（级联删除参考图）
            images = Image.query.all()
            deleted_count = 0

            for image in images:
                try:
                    # 删除图片物理文件
                    if image.file_path:
                        remove_physical_file(image.file_path)
                    if image.thumbnail_path:
                        remove_physical_file(image.thumbnail_path)

                    # 删除参考图物理文件
                    for ref in image.refs:
                        if ref.file_path and not ref.is_placeholder:
                            remove_physical_file(ref.file_path)

                    # 删除数据库记录
                    db.session.delete(image)
                    deleted_count += 1

                except Exception as e:
                    print(f"[WARN] 删除图片 {image.id} 时出错: {e}")

            # 删除孤立的标签
            orphaned_tags = Tag.query.filter(~Tag.images.any()).all()
            tag_deleted_count = len(orphaned_tags)
            for tag in orphaned_tags:
                db.session.delete(tag)

            # 提交事务
            db.session.commit()

            print()
            print("[SUCCESS] 清空完成！")
            print(f"   - 已删除图片: {deleted_count}")
            print(f"   - 已删除孤立标签: {tag_deleted_count}")
            print(f"   - 保留管理员账户和系统设置")
            print()

            # 验证结果
            remaining_images = Image.query.count()
            remaining_tags = Tag.query.count()
            remaining_refs = ReferenceImage.query.count()

            print("[INFO] 清空后数据库统计：")
            print(f"   - 图片数量: {remaining_images}")
            print(f"   - 参考图数量: {remaining_refs}")
            print(f"   - 标签数量: {remaining_tags}")
            print(f"   - 用户数量: {User.query.count()}")
            print(f"   - 系统设置: {SystemSetting.query.count()}")
            print()

        except Exception as e:
            print(f"[ERROR] 清空失败: {e}")
            db.session.rollback()
            sys.exit(1)


if __name__ == '__main__':
    clear_all_data()
