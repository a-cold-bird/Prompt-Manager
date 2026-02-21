# -*- coding: utf-8 -*-
"""
批量导入脚本 - 支持指定文件夹版本
功能：从指定的 JSON 文件和图片文件夹导入数据到数据库
支持命令行参数和交互式输入
"""

import json
import os
import sys
import io
import shutil
import argparse
from datetime import datetime
from app import create_app, db
from models import Image, ReferenceImage, Tag
from services.image_service import ImageService
from utils import process_image, generate_lqip
from PIL import Image as PilImage

# 配置标准输出为UTF-8编码
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def import_data(json_file, images_folder, upload_folder='static/uploads', database_uri=None):
    """导入数据

    Args:
        json_file: JSON数据文件路径
        images_folder: 图片文件夹路径
        upload_folder: 上传目标文件夹，如果不以'static/'开头会自动添加
        database_uri: 数据库URI，用于Docker环境或指定数据库位置
    """
    app = create_app()

    # 如果指定了数据库URI，覆盖配置
    if database_uri:
        app.config['SQLALCHEMY_DATABASE_URI'] = database_uri
        print(f"[INFO] 使用指定数据库: {database_uri}")

    # 确保上传文件夹路径包含 static/ 前缀
    if not upload_folder.startswith('static/') and not upload_folder.startswith('/'):
        upload_folder = f'static/{upload_folder}'
        print(f"[INFO] 自动添加static前缀: {upload_folder}")

    with app.app_context():
        print("=" * 60)
        print("[Prompt Manager] 批量数据导入工具")
        print("=" * 60)
        print()

        try:
            # 读取JSON数据
            if not os.path.exists(json_file):
                print(f"[ERROR] JSON文件不存在: {json_file}")
                return False

            if not os.path.exists(images_folder):
                print(f"[ERROR] 图片文件夹不存在: {images_folder}")
                return False

            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if 'images' not in data:
                print("[ERROR] JSON文件缺少'images'字段")
                return False

            records = data['images']
            print(f"[INFO] 读取到 {len(records)} 条记录")
            print(f"[INFO] 数据源: {images_folder}")
            print(f"[INFO] 上传目标: {upload_folder}")
            print()

            # 统计type分布
            type_dist = {}
            for record in records:
                img_type = record.get('type', 'unknown')
                type_dist[img_type] = type_dist.get(img_type, 0) + 1

            print("[INFO] 原始type分布:")
            for img_type, count in sorted(type_dist.items()):
                print(f"   {img_type}: {count}")
            print()

            # 确保上传文件夹存在
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder, exist_ok=True)
                print(f"[INFO] 创建上传文件夹: {upload_folder}")

            # 导入统计
            success_count = 0
            error_count = 0
            skip_count = 0

            for idx, record in enumerate(records, 1):
                try:
                    # 提取字段
                    title = record.get('title', f'Imported Image {idx}').strip()
                    author = record.get('author', '匿名').strip() if record.get('author') else '匿名'
                    prompt = record.get('prompt', '').strip()
                    description = record.get('description', '').strip() if record.get('description') else ''
                    image_type = record.get('type', 'txt2img').strip()
                    category = record.get('category', 'gallery') or 'gallery'
                    tags_list = record.get('tags', []) or []

                    # 处理图片文件路径
                    file_name = record.get('file_path', '').split('/')[-1]
                    source_image = os.path.join(images_folder, file_name)

                    # 检查图片文件是否存在
                    if not os.path.exists(source_image):
                        print(f"[WARN] #{idx} 跳过 - 图片不存在: {file_name}")
                        skip_count += 1
                        continue

                    # 复制图片到上传文件夹
                    dest_image = os.path.join(upload_folder, file_name)
                    if not os.path.exists(dest_image):
                        shutil.copy2(source_image, dest_image)

                    # 创建Image记录（使用正确的路径分隔符处理）
                    web_path = os.path.join(upload_folder, file_name).replace('\\', '/')

                    # 改进的重复检测：同时检查title、author和file_path
                    existing = Image.query.filter(
                        db.or_(
                            db.and_(Image.title == title, Image.author == author),
                            Image.file_path == web_path
                        )
                    ).first()
                    if existing:
                        print(f"[SKIP] #{idx} {title[:30]} - 已存在")
                        skip_count += 1
                        continue

                    image = Image(
                        title=title,
                        author=author,
                        prompt=prompt,
                        description=description,
                        type=image_type,
                        category=category,
                        file_path=web_path,
                        thumbnail_path=web_path,
                        status='approved'  # 直接标记为已批准
                    )

                    # 生成 LQIP（为导入的图片生成占位图）
                    try:
                        pil_img = PilImage.open(source_image)
                        pil_img.load()  # 强制加载图片数据
                        image.lqip_data = generate_lqip(pil_img)
                    except Exception as lqip_err:
                        print(f"[WARN] #{idx} LQIP生成失败: {str(lqip_err)[:40]}")
                        image.lqip_data = ""

                    # 处理标签
                    if tags_list:
                        for tag_name in tags_list:
                            tag_name = tag_name.strip()
                            if tag_name:
                                tag = Tag.query.filter_by(name=tag_name).first()
                                if not tag:
                                    tag = Tag(name=tag_name, is_sensitive=False)
                                    db.session.add(tag)
                                image.tags.append(tag)

                    db.session.add(image)
                    db.session.commit()

                    if idx % 50 == 0:
                        print(f"[PROGRESS] 已处理 {idx} / {len(records)}")

                    success_count += 1

                except Exception as e:
                    db.session.rollback()
                    print(f"[ERROR] #{idx} 导入失败: {str(e)[:60]}")
                    error_count += 1

            print()
            print("[SUCCESS] 导入完成！")
            print(f"   - 成功导入: {success_count}")
            print(f"   - 跳过: {skip_count}")
            print(f"   - 错误: {error_count}")
            print()

            # 验证结果
            total_images = Image.query.count()
            total_tags = Tag.query.count()
            print("[INFO] 数据库统计：")
            print(f"   - 总图片数: {total_images}")
            print(f"   - 总标签数: {total_tags}")
            print()

            # 统计导入后的type分布
            txt2img_count = Image.query.filter_by(type='txt2img').count()
            img2img_count = Image.query.filter_by(type='img2img').count()
            print("[INFO] 导入后type分布:")
            print(f"   txt2img: {txt2img_count}")
            print(f"   img2img: {img2img_count}")
            print()

            # 路径验证：检查新导入的图片路径是否正确
            if success_count > 0:
                print("[INFO] 验证导入的图片路径...")
                invalid_paths = []
                recent_images = Image.query.order_by(Image.id.desc()).limit(success_count).all()
                for img in recent_images:
                    # 检查路径是否以 static/ 开头
                    if not img.file_path.startswith('static/') and not img.file_path.startswith('/'):
                        invalid_paths.append(f"   - ID {img.id}: {img.file_path} (缺少static前缀)")
                    # 检查文件是否存在
                    elif not os.path.exists(img.file_path):
                        invalid_paths.append(f"   - ID {img.id}: {img.file_path} (文件不存在)")

                if invalid_paths:
                    print(f"[WARN] 发现 {len(invalid_paths)} 个路径问题:")
                    for path in invalid_paths[:5]:  # 只显示前5个
                        print(path)
                    if len(invalid_paths) > 5:
                        print(f"   ... 还有 {len(invalid_paths) - 5} 个问题")
                else:
                    print(f"[OK] 所有 {success_count} 个导入的图片路径验证通过！")
                print()

            return True

        except Exception as e:
            print(f"[ERROR] 导入失败: {e}")
            db.session.rollback()
            return False


def interactive_input():
    """交互式输入文件夹路径"""
    print("=" * 60)
    print("[Prompt Manager] 交互式导入工具")
    print("=" * 60)
    print()

    # 输入 JSON 文件路径
    while True:
        json_file = input("请输入 data.json 文件的完整路径: ").strip()
        if json_file and os.path.exists(json_file):
            break
        print(f"[ERROR] 文件不存在: {json_file}")

    # 输入图片文件夹路径
    while True:
        images_folder = input("请输入图片文件夹的完整路径: ").strip()
        if images_folder and os.path.isdir(images_folder):
            break
        print(f"[ERROR] 文件夹不存在: {images_folder}")

    # 可选：输入上传目标文件夹
    upload_folder = input("请输入上传目标文件夹 (默认: static/uploads): ").strip()
    if not upload_folder:
        upload_folder = 'static/uploads'

    return json_file, images_folder, upload_folder


def main():
    parser = argparse.ArgumentParser(
        description='Prompt Manager 批量导入工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  # 交互式输入模式
  python import_from_folder.py

  # 指定路径模式
  python import_from_folder.py -j "./prompt_backup/20251210/data.json" -i "./prompt_backup/20251210/images"

  # 自动添加static前缀（推荐）
  python import_from_folder.py -j "data.json" -i "images" -o "uploads"

  # Docker环境模式（直接指定数据库）
  python import_from_folder.py -j "data.json" -i "images" --docker

  # 自定义数据库位置
  python import_from_folder.py -j "data.json" -i "images" -d "sqlite:////app/instance/data.sqlite"

  # 显示帮助
  python import_from_folder.py -h
        '''
    )

    parser.add_argument(
        '-j', '--json',
        dest='json_file',
        help='data.json 文件的完整路径'
    )

    parser.add_argument(
        '-i', '--images',
        dest='images_folder',
        help='图片文件夹的完整路径'
    )

    parser.add_argument(
        '-o', '--output',
        dest='upload_folder',
        default='static/uploads',
        help='上传文件夹路径（会自动添加static前缀，默认: static/uploads）'
    )

    parser.add_argument(
        '-d', '--database',
        dest='database_uri',
        help='数据库URI（例如: sqlite:////path/to/data.sqlite）'
    )

    parser.add_argument(
        '--docker',
        action='store_true',
        help='Docker模式：使用 sqlite:///data.sqlite 作为数据库'
    )

    args = parser.parse_args()

    # 判断是否使用命令行参数或交互式输入
    if args.json_file and args.images_folder:
        json_file = args.json_file
        images_folder = args.images_folder
        upload_folder = args.upload_folder
    else:
        # 交互式输入
        json_file, images_folder, upload_folder = interactive_input()

    # 处理数据库URI
    database_uri = None
    if args.docker:
        # Docker模式：使用标准的 .env 配置
        # DATABASE_URL=sqlite:///data.sqlite
        database_uri = 'sqlite:///data.sqlite'
        print(f"[INFO] Docker模式已启用，使用数据库: {database_uri}")
    elif hasattr(args, 'database_uri') and args.database_uri:
        database_uri = args.database_uri

    # 执行导入
    success = import_data(json_file, images_folder, upload_folder, database_uri)

    # 返回退出代码
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
