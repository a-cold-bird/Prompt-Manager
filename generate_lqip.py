# -*- coding: utf-8 -*-
"""
为现有的图片生成 LQIP (Low Quality Image Placeholder)

使用说明:
  # 本地开发环境（自动使用 .env 中的 DATABASE_URL）
  python generate_lqip.py

  # Docker 环境（使用 sqlite:///data.sqlite）
  python generate_lqip.py --docker

  # 自定义数据库位置
  python generate_lqip.py -d "sqlite:///path/to/data.sqlite"
"""

import os
import sys
import io
from app import create_app, db
from models import Image
from utils import generate_lqip
from PIL import Image as PilImage
import argparse

def main(app=None):
    app = app or create_app()

    with app.app_context():
        print("=" * 60)
        print("[Prompt Manager] LQIP 批量生成工具")
        print("=" * 60)
        print()

        # 查询所有缺少 LQIP 的图片
        images_without_lqip = Image.query.filter(
            (Image.lqip_data == None) | (Image.lqip_data == '')
        ).all()

        if not images_without_lqip:
            print("[INFO] 所有图片都已有 LQIP，无需处理")
            print()
            return True

        total = len(images_without_lqip)
        success = 0
        failed = 0

        print(f"[INFO] 发现 {total} 张图片需要生成 LQIP")
        print(f"[INFO] 开始处理...")
        print()

        for idx, img in enumerate(images_without_lqip, 1):
            try:
                # 构建文件路径
                file_path = img.file_path.lstrip('/')
                full_path = os.path.join(app.root_path, file_path)

                # 检查文件是否存在
                if not os.path.exists(full_path):
                    print(f"[WARN] #{idx}/{total} 跳过 - 文件不存在: {img.title[:30]}")
                    failed += 1
                    continue

                # 打开图片并生成 LQIP
                with open(full_path, 'rb') as f:
                    pil_img = PilImage.open(f)
                    pil_img.load()  # 强制加载图片数据
                    lqip_data = generate_lqip(pil_img)

                if lqip_data:
                    img.lqip_data = lqip_data
                    db.session.add(img)
                    print(f"[✓] #{idx}/{total} 成功: {img.title[:40]}")
                    success += 1
                else:
                    print(f"[WARN] #{idx}/{total} 跳过 - 生成失败: {img.title[:30]}")
                    failed += 1

                # 每 10 条记录提交一次，避免内存占用过高
                if idx % 10 == 0:
                    db.session.commit()
                    print(f"[INFO] 已处理 {idx}/{total}，进度: {int(idx/total*100)}%")

            except Exception as e:
                print(f"[ERROR] #{idx}/{total} 处理失败 - {img.title[:30]}: {str(e)[:50]}")
                failed += 1
                continue

        # 最后提交一次
        try:
            db.session.commit()
        except Exception as e:
            print(f"[ERROR] 数据库提交失败: {e}")
            db.session.rollback()
            return False

        print()
        print("[SUCCESS] LQIP 生成完成！")
        print(f"   - 成功: {success}")
        print(f"   - 失败: {failed}")
        print(f"   - 总计: {total}")
        print()

        return True

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Prompt Manager LQIP 批量生成工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  # 本地开发环境（使用 .env 中的 DATABASE_URL）
  python generate_lqip.py

  # Docker 环境（使用 sqlite:///data.sqlite）
  python generate_lqip.py --docker

  # 自定义数据库位置
  python generate_lqip.py -d "sqlite:///path/to/data.sqlite"
        '''
    )

    parser.add_argument(
        '-d', '--database',
        dest='database_uri',
        help='数据库URI（例如: sqlite:///data.sqlite）'
    )

    parser.add_argument(
        '--docker',
        action='store_true',
        help='Docker模式：使用 sqlite:///data.sqlite 作为数据库'
    )

    args = parser.parse_args()

    # 创建应用
    from app import create_app as _create_app
    app = _create_app()

    # 处理数据库 URI
    if args.docker:
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.sqlite'
        print("[INFO] Docker模式已启用，使用数据库: sqlite:///data.sqlite")
    elif args.database_uri:
        app.config['SQLALCHEMY_DATABASE_URI'] = args.database_uri
        print(f"[INFO] 使用自定义数据库: {args.database_uri}")

    try:
        success = main(app)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"[FATAL] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
