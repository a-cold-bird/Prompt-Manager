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

    # 从数据库读取开关，确保持久化配置生效
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
    show_sensitive = can_see_sensitive()

    # 构建图片查询
    query = Image.query.filter_by(status='approved')

    if category_filter:
        query = query.filter_by(category=category_filter)

    if not show_sensitive:
        query = query.filter(~Image.tags.any(Tag.is_sensitive == True))

    if tag_filter:
        query = query.filter(Image.tags.any(name=tag_filter))

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

    # 构建标签筛选列表
    tags_query = db.session.query(Tag).join(Tag.images).filter(Image.status == 'approved')

    if category_filter:
        tags_query = tags_query.filter(Image.category == category_filter)

    if not show_sensitive:
        tags_query = tags_query.filter(Tag.is_sensitive == False)

    all_tags = tags_query.group_by(Tag.id).order_by(Tag.name).all()

    return {
        'images': pagination.items,
        'pagination': pagination,
        'active_tag': tag_filter,
        'active_search': search_query,
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

    # 2. 根据分类读取对应的持久化配置开关
    if category == 'template':
        need_approval = SystemSetting.get_bool('approval_template', default=True)
    else:
        need_approval = SystemSetting.get_bool('approval_gallery', default=True)

    # 3. 决定初始状态
    initial_status = 'pending' if need_approval else 'approved'

    try:
        # 4. 构造表单数据副本以注入状态
        form_data = request.form.to_dict()
        form_data['status'] = initial_status

        new_image = ImageService.create_image(
            file=file,
            data=form_data,
            ref_files=request.files.getlist('ref_images')
        )

        # 5. 渲染成功页面，传递状态以决定显示内容
        return render_template('success.html', status=initial_status, image=new_image)

    except Exception as e:
        current_app.logger.error(f"Upload Error: {e}")
        return f"发布失败: {str(e)}", 500


@bp.route('/about')
def about():
    return render_template('about.html')


@bp.route('/api/list')
def api_list():
    """获取作品列表 API"""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 100, type=int), 1000)
    category = request.args.get('category')

    query = Image.query.filter_by(status='approved')

    if category:
        query = query.filter_by(category=category)

    query = query.order_by(Image.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'current_page': page,
        'pages': pagination.pages,
        'total': pagination.total,
        'data': [img.to_dict() for img in pagination.items]
    })


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