from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, Response, \
    stream_with_context, send_file, jsonify
from flask_login import login_required
from models import db, Image, Tag, ReferenceImage, SystemSetting
from services.image_service import ImageService
from services.data_service import DataService
import json
import time
import zipfile
import io
import os

bp = Blueprint('admin', __name__, url_prefix='/admin')


@bp.route('/')
@login_required
def dashboard():
    """管理后台主页"""
    active_tab = request.args.get('tab', 'pending')
    search_query = request.args.get('q', '').strip()

    # 待审核队列
    pending_images = Image.query.filter_by(status='pending').order_by(Image.created_at.asc()).all()

    # 已发布列表（含搜索和分页）
    approved_query = Image.query.filter_by(status='approved')
    if search_query:
        approved_query = approved_query.filter(
            Image.title.contains(search_query) |
            Image.author.contains(search_query) |
            Image.prompt.contains(search_query)
        )

    page = request.args.get('page', 1, type=int)
    # 支持动态 per_page 参数，否则使用默认配置
    per_page = request.args.get('per_page', None, type=int)
    if not per_page:
        per_page = current_app.config['ADMIN_PER_PAGE']
    # 限制 per_page 在合理范围内 (6-100)
    per_page = max(6, min(100, per_page))

    approved_pagination = approved_query.order_by(Image.created_at.desc()).paginate(page=page, per_page=per_page)

    all_tags = Tag.query.order_by(Tag.name).all()

    stats = {
        'total_images': Image.query.count(),
        'total_tags': Tag.query.count()
    }

    # 获取系统设置 (从数据库读取持久化配置)
    approval_settings = {
        'gallery': SystemSetting.get_bool('approval_gallery', default=True),
        'template': SystemSetting.get_bool('approval_template', default=True)
    }

    # 获取敏感内容开关设置
    allow_sensitive_toggle = SystemSetting.get_bool('allow_sensitive_toggle', default=True)
    current_app.config['ALLOW_PUBLIC_SENSITIVE_TOGGLE'] = allow_sensitive_toggle

    return render_template('admin.html',
                           pending_images=pending_images,
                           approved_pagination=approved_pagination,
                           active_tab=active_tab,
                           search_query=search_query,
                           all_tags=all_tags,
                           stats=stats,
                           approval_settings=approval_settings,
                           allow_sensitive_toggle=allow_sensitive_toggle)


@bp.route('/approve/<int:img_id>', methods=['POST'])
@login_required
def approve(img_id):
    """审核通过单个作品"""
    img = db.session.get(Image, img_id)
    if img:
        img.status = 'approved'
        db.session.commit()
        flash('作品已发布')
    return redirect(url_for('admin.dashboard', tab='pending'))


@bp.route('/approve-all', methods=['POST'])
@login_required
def approve_all():
    """一键通过所有待审核作品"""
    try:
        # 批量更新效率更高
        updated_count = Image.query.filter_by(status='pending').update({'status': 'approved'})
        db.session.commit()
        if updated_count > 0:
            flash(f'🎉 已一键通过 {updated_count} 个作品！')
        else:
            flash('没有待审核的作品。')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Batch approve error: {e}")
        flash('操作失败，请查看日志')

    return redirect(url_for('admin.dashboard', tab='pending'))


@bp.route('/delete/<int:img_id>', methods=['POST'])
@login_required
def delete(img_id):
    """删除作品"""
    if ImageService.delete_image(img_id):
        flash('删除成功')
    else:
        flash('删除失败：找不到图片')

    next_url = request.args.get('next')
    if next_url: return redirect(next_url)
    return redirect(url_for('admin.dashboard'))


@bp.route('/edit/<int:img_id>', methods=['GET', 'POST'])
@login_required
def edit_image(img_id):
    """编辑作品"""
    img = db.session.get(Image, img_id)
    if not img: return redirect(url_for('admin.dashboard'))

    if request.method == 'POST':
        # 处理前端传来的逗号分隔 ID 字符串
        raw_ids = request.form.get('deleted_ref_ids', '')
        deleted_ids_list = raw_ids.split(',') if raw_ids else []

        try:
            ImageService.update_image(
                image_id=img.id,
                data=request.form,
                new_main_file=request.files.get('new_image'),
                new_ref_files=request.files.getlist('add_refs'),
                deleted_ref_ids=deleted_ids_list
            )
            flash('修改保存成功')
        except Exception as e:
            flash(f'保存失败: {e}')

        next_url = request.form.get('next')
        if next_url: return redirect(next_url)
        return redirect(url_for('admin.dashboard', tab='approved' if img.status == 'approved' else 'pending'))

    next_url = request.args.get('next')
    return render_template('admin_edit.html', img=img, next_url=next_url)


@bp.route('/import-zip', methods=['POST'])
@login_required
def import_zip():
    """导入备份数据包 (流式响应)"""
    file = request.files.get('zip_file')
    if not file: return "请上传 ZIP 文件", 400

    temp_zip_path = os.path.join(current_app.instance_path, 'temp_import.zip')
    if not os.path.exists(current_app.instance_path): os.makedirs(current_app.instance_path)
    file.save(temp_zip_path)

    return Response(stream_with_context(DataService.import_zip_stream(temp_zip_path)), mimetype='text/plain')


@bp.route('/export-zip', methods=['POST'])
@login_required
def export_zip():
    """导出全量数据包 (含图片和元数据)"""
    images = Image.query.all()
    if not images:
        flash('没有数据可导出')
        return redirect(url_for('admin.dashboard', tab='data-mgmt'))

    memory_file = io.BytesIO()

    # 构建 ZIP
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        json_data = []
        upload_root = os.path.join(current_app.root_path, current_app.config['UPLOAD_FOLDER'])

        for img in images:
            # 准备元数据
            item_data = img.to_dict()

            img_filename = os.path.basename(img.file_path)
            item_data['zip_image_path'] = f"images/{img_filename}"

            if img.thumbnail_path:
                thumb_name = os.path.basename(img.thumbnail_path)
                item_data['zip_thumb_path'] = f"images/{thumb_name}"

            # 写入主图
            abs_img_path = os.path.join(upload_root, img_filename)
            if os.path.exists(abs_img_path):
                zf.write(abs_img_path, f"images/{img_filename}")

            # 写入缩略图
            if img.thumbnail_path:
                abs_thumb = os.path.join(upload_root, os.path.basename(img.thumbnail_path))
                if os.path.exists(abs_thumb):
                    zf.write(abs_thumb, f"images/{os.path.basename(img.thumbnail_path)}")

            # 写入参考图
            item_data['refs'] = []
            for ref in img.refs:
                ref_fname = os.path.basename(ref.file_path)
                abs_ref_path = os.path.join(upload_root, ref_fname)
                if os.path.exists(abs_ref_path):
                    zf.write(abs_ref_path, f"images/{ref_fname}")
                    item_data['refs'].append(f"images/{ref_fname}")

            json_data.append(item_data)

        # 写入 JSON 索引
        zf.writestr("data.json", json.dumps({"images": json_data}, ensure_ascii=False, indent=2))

    memory_file.seek(0)
    filename = f"backup_{time.strftime('%Y%m%d')}.zip"
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=filename
    )


@bp.route('/tag/update', methods=['POST'])
@login_required
def update_tag():
    """标签管理：重命名与敏感设置"""
    is_json = request.is_json
    data = request.get_json() if is_json else request.form

    tag_id = data.get('tag_id')
    new_name = data.get('new_name', '').strip()
    is_sensitive = data.get('is_sensitive')

    # 兼容 Form 表单的 Checkbox
    if not is_json and 'is_sensitive' in request.form:
        is_sensitive = True
    elif not is_json:
        is_sensitive = False

    tag = db.session.get(Tag, int(tag_id))
    if not tag:
        return (jsonify({'status': 'error'}), 404) if is_json else redirect(url_for('admin.dashboard'))

    # 更新状态
    if tag.is_sensitive != is_sensitive:
        tag.is_sensitive = is_sensitive
        db.session.commit()

    # 更新名称（合并逻辑）
    if new_name and new_name != tag.name:
        existing = Tag.query.filter_by(name=new_name).first()
        if existing:
            for img in tag.images:
                if img not in existing.images:
                    existing.images.append(img)
            db.session.delete(tag)
            flash(f'标签已合并至: {new_name}')
        else:
            tag.name = new_name
        db.session.commit()

    if is_json: return jsonify({'status': 'ok'})
    return redirect(url_for('admin.dashboard'))


@bp.route('/setting/global', methods=['POST'])
@login_required
def update_global_setting():
    """全局设置：更新各类系统开关"""
    is_json = request.is_json
    data = request.get_json() if is_json else request.form

    # 1. 敏感内容开关
    if 'allow_toggle' in data:
        val = data.get('allow_toggle', False)
        # 兼容表单
        if not is_json and 'allow_toggle' in request.form:
            val = True
        elif not is_json:
            val = False

        SystemSetting.set_bool('allow_sensitive_toggle', val)
        current_app.config['ALLOW_PUBLIC_SENSITIVE_TOGGLE'] = val

    # 2. 画廊审核开关
    if 'approval_gallery' in data:
        SystemSetting.set_bool('approval_gallery', data.get('approval_gallery'))

    # 3. 模板审核开关
    if 'approval_template' in data:
        SystemSetting.set_bool('approval_template', data.get('approval_template'))

    if is_json: return jsonify({'status': 'ok'})
    flash('系统设置已更新')
    return redirect(url_for('admin.dashboard', tab='data-mgmt'))


@bp.route('/batch/delete', methods=['POST'])
@login_required
def batch_delete():
    """批量删除图片"""
    data = request.get_json()
    img_ids = data.get('image_ids', [])

    if not img_ids:
        return jsonify({'status': 'error', 'message': '未选择任何图片'}), 400

    try:
        deleted_count = 0
        for img_id in img_ids:
            if ImageService.delete_image(img_id):
                deleted_count += 1

        return jsonify({
            'status': 'ok',
            'deleted': deleted_count,
            'message': f'成功删除 {deleted_count} 张图片'
        })
    except Exception as e:
        current_app.logger.error(f"Batch delete error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@bp.route('/batch/tags', methods=['POST'])
@login_required
def batch_modify_tags():
    """批量修改标签"""
    data = request.get_json()
    img_ids = data.get('image_ids', [])
    tag_ids = data.get('tag_ids', [])
    action = data.get('action', 'add')  # 'add' 或 'remove'

    if not img_ids or not tag_ids:
        return jsonify({'status': 'error', 'message': '缺少必要参数'}), 400

    try:
        # 获取标签对象
        tags = Tag.query.filter(Tag.id.in_(tag_ids)).all()
        if not tags:
            return jsonify({'status': 'error', 'message': '标签不存在'}), 404

        # 批量修改
        modified_count = 0
        for img_id in img_ids:
            img = db.session.get(Image, img_id)
            if not img:
                continue

            if action == 'add':
                # 添加标签（避免重复）
                for tag in tags:
                    if tag not in img.tags:
                        img.tags.append(tag)
                        modified_count += 1
            elif action == 'remove':
                # 删除标签
                for tag in tags:
                    if tag in img.tags:
                        img.tags.remove(tag)
                        modified_count += 1

        db.session.commit()

        action_text = '添加' if action == 'add' else '删除'
        return jsonify({
            'status': 'ok',
            'modified': len(img_ids),
            'message': f'成功为 {len(img_ids)} 张图片{action_text}标签'
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Batch modify tags error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@bp.route('/toggle-category/<int:img_id>/<category>', methods=['POST'])
@login_required
def toggle_category(img_id, category):
    """快速切换图片分类（画廊/模板）"""
    if category not in ('gallery', 'template'):
        return jsonify({'status': 'error', 'message': '无效的分类'}), 400

    img = db.session.get(Image, img_id)
    if not img:
        return jsonify({'status': 'error', 'message': '图片不存在'}), 404

    try:
        old_category = img.category
        img.category = category
        db.session.commit()
        category_text = '画廊' if category == 'gallery' else '模板'

        # 记录成功的分类切换操作 - API操作日志
        current_app.logger.info(
            f"[API:TOGGLE-CATEGORY] User={request.environ.get('REMOTE_USER', 'Unknown')} | "
            f"ImgID={img_id} | Title={img.title[:50]} | "
            f"Change={old_category}→{category} | Time={time.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        return jsonify({
            'status': 'ok',
            'category': category,
            'message': f'已切换为: {category_text}'
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"[API:TOGGLE-CATEGORY-ERROR] ImgID={img_id} | Category={category} | "
            f"Error={str(e)[:100]} | Time={time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return jsonify({'status': 'error', 'message': str(e)}), 500