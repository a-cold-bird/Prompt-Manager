from flask import Blueprint, render_template, request, current_app, url_for, jsonify
from flask_login import current_user
from sqlalchemy.sql.expression import func
from models import db, Image, Tag, SystemSetting
from extensions import limiter
from services.image_service import ImageService

bp = Blueprint('public', __name__)


def can_see_sensitive():
    """判断当前用户是否有权查看敏感内容"""
    if current_user.is_authenticated: return True

    # 修改点：从数据库读取开关 (持久化)
    allow_toggle = SystemSetting.get_bool('allow_sensitive_toggle', default=True)

    if not allow_toggle: return False
    return request.cookies.get('pm_show_sensitive') == '1'


def _get_common_data(category_filter=None):
    """
    提取画廊和模板页通用的查询逻辑
    :param category_filter: None(所有) 或 'template'(仅模板)
    """
    page = request.args.get('page', 1, type=int)
    tag_filter = request.args.get('tag', '').strip()
    search_query = request.args.get('q', '').strip()
    sort_by = request.args.get('sort', 'date')
    type_filter = request.args.get('type', '').strip()  # 图片类型过滤: text2img, img2img
    show_sensitive = can_see_sensitive()

    # 构建图片查询
    query = Image.query.filter_by(status='approved')

    if category_filter:
        query = query.filter_by(category=category_filter)

    if not show_sensitive:
        query = query.filter(~Image.tags.any(Tag.is_sensitive == True))

    if tag_filter:
        query = query.filter(Image.tags.any(name=tag_filter))

    # 支持两种写法: txt2img 和 text2img（规范化为 txt2img）
    if type_filter:
        # 规范化type_filter
        if type_filter == 'text2img':
            type_filter = 'txt2img'

        if type_filter in ['txt2img', 'img2img']:
            query = query.filter_by(type=type_filter)

    if search_query:
        query = query.filter(
            Image.title.contains(search_query) |
            Image.prompt.contains(search_query) |
            Image.author.contains(search_query)
        )

    # 排序
    if sort_by == 'hot':
        query = query.order_by(Image.heat_score.desc(), Image.created_at.desc())
    elif sort_by == 'random':
        query = query.order_by(func.random())
    else:
        query = query.order_by(Image.created_at.desc())

    pagination = query.paginate(page=page, per_page=current_app.config['ITEMS_PER_PAGE'])

    # 构建标签筛选列表，并统计每个标签的图片数量
    tags_query = db.session.query(
        Tag,
        func.count(Image.id).label('image_count')
    ).join(Tag.images).filter(Image.status == 'approved')

    if category_filter:
        tags_query = tags_query.filter(Image.category == category_filter)

    if not show_sensitive:
        tags_query = tags_query.filter(Tag.is_sensitive == False)

    tags_with_counts = tags_query.group_by(Tag.id).order_by(Tag.name).all()

    # 将结果转换为更易用的格式
    all_tags = [{'tag': tag, 'count': count} for tag, count in tags_with_counts]

    return {
        'images': pagination.items,
        'pagination': pagination,
        'active_tag': tag_filter,
        'active_search': search_query,
        'active_type': type_filter,
        'all_tags': all_tags,
        'current_sort': sort_by
    }


@bp.route('/')
def index():
    """画廊主页"""
    data = _get_common_data(category_filter=None)
    return render_template('index.html', **data)


@bp.route('/templates')
def templates_index():
    """模板库"""
    data = _get_common_data(category_filter='template')
    return render_template('index.html', **data)


@bp.route('/upload', methods=['GET', 'POST'])
@limiter.limit(lambda: current_app.config['UPLOAD_RATE_LIMIT'])
def upload():
    """发布新作品"""
    if request.method == 'GET':
        return render_template('upload.html')

    file = request.files.get('image')
    if not file: return "缺少主图", 400

    # 1. 获取用户选择的分类 (gallery 或 template)
    category = request.form.get('category', 'gallery')

    # 2. 从数据库读取审核配置
    if category == 'template':
        need_approval = SystemSetting.get_bool('approval_template', default=True)
    else:
        # 默认为 gallery
        need_approval = SystemSetting.get_bool('approval_gallery', default=True)

    # 3. 决定初始状态
    initial_status = 'pending' if need_approval else 'approved'

    try:
        # 构造表单数据复本以修改状态
        form_data = request.form.to_dict()
        form_data['status'] = initial_status

        new_image = ImageService.create_image(
            file=file,
            data=form_data,
            ref_files=request.files.getlist('ref_images')
        )
        return render_template('success.html', status=initial_status, image=new_image)
    except Exception as e:
        current_app.logger.error(f"Upload Error: {e}")
        return f"发布失败: {str(e)}", 500


@bp.route('/about')
def about():
    return render_template('about.html')


def _get_api_data(category_filter):
    """
    API 通用查询逻辑 (Internal Helper)
    :param category_filter: 'gallery' 或 'template'

    默认返回所有数据（不分页）。可通过参数切换：
    - ?all=1 或不传参数：返回所有数据
    - ?page=X&per_page=Y：启用分页
    """
    # 基础查询：只看已发布的
    query = Image.query.filter_by(status='approved')

    # 强制分类筛选
    if category_filter:
        query = query.filter_by(category=category_filter)

    # 排序：默认按时间倒序
    query = query.order_by(Image.created_at.desc())

    # 检查是否需要分页
    use_pagination = request.args.get('page') or request.args.get('per_page')

    if use_pagination:
        # 用户明确指定了分页参数，则启用分页
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return {
            'current_page': page,
            'pages': pagination.pages,
            'total': pagination.total,
            'data': [img.to_dict() for img in pagination.items]
        }
    else:
        # 默认返回所有数据（无分页）
        all_items = query.all()
        return {
            'current_page': 1,
            'pages': 1,
            'total': len(all_items),
            'data': [img.to_dict() for img in all_items]
        }


@bp.route('/api/gallery')
def api_gallery_list():
    """获取画廊数据 (JSON)"""
    return jsonify(_get_api_data('gallery'))


@bp.route('/api/templates')
def api_templates_list():
    """获取模板数据 (JSON)"""
    return jsonify(_get_api_data('template'))


@bp.route('/api/stats/view/<int:img_id>', methods=['POST'])
def stat_view(img_id):
    """增加浏览计数"""
    img = db.session.get(Image, img_id)
    if img:
        img.views_count += 1
        img.heat_score = img.views_count * 1 + img.copies_count * 10
        db.session.commit()
    return {'status': 'ok'}


@bp.route('/api/stats/copy/<int:img_id>', methods=['POST'])
def stat_copy(img_id):
    """增加复制计数"""
    img = db.session.get(Image, img_id)
    if img:
        img.copies_count += 1
        img.heat_score = img.views_count * 1 + img.copies_count * 10
        db.session.commit()
    return {'status': 'ok'}