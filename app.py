import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template
from werkzeug.security import generate_password_hash
from flask_login import current_user

from config import Config
from extensions import db, login_manager, csrf, migrate, limiter
from models import User
from utils import ensure_local_resources, cleanup_pending_deletions


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    os.makedirs(app.instance_path, exist_ok=True)

    # 修复 Flask 3.0+ JSON 中文显示
    app.json.ensure_ascii = False

    # 初始化扩展
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)

    # 注册蓝图
    from blueprints.public import bp as public_bp
    from blueprints.auth import bp as auth_bp
    from blueprints.admin import bp as admin_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)

    # 检查静态资源
    with app.app_context():
        apply_dynamic_config(app)
        cleanup_pending_deletions(app)
        ensure_local_resources(app)

    # 配置登录
    login_manager.login_view = 'auth.login'

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # 全局模版变量
    @app.context_processor
    def inject_global_vars():
        return dict(
            current_user=current_user,
            config=app.config
        )

    # 配置日志与错误处理
    configure_logging(app)
    register_error_handlers(app)
    register_commands(app)

    return app


def configure_logging(app):
    if not app.debug and not app.testing:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        log_file = os.path.abspath('logs/prompt_manager.log')
        has_same_handler = any(
            hasattr(h, 'baseFilename') and os.path.abspath(getattr(h, 'baseFilename', '')) == log_file
            for h in app.logger.handlers
        )
        if not has_same_handler:
            if os.name == 'nt':
                file_handler = logging.FileHandler(log_file, encoding='utf-8')
            else:
                file_handler = RotatingFileHandler(log_file, maxBytes=10240, backupCount=10)
            file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
            file_handler.setLevel(logging.INFO)
            app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Prompt Manager startup')


def register_error_handlers(app):
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('500.html'), 500


def register_commands(app):
    @app.cli.command("init-db")
    def init_db_command():
        """初始化数据库和管理员账户"""
        db.create_all()
        admin_user = app.config['ADMIN_USERNAME']
        admin_pass = app.config['ADMIN_PASSWORD']

        if not User.query.filter_by(username=admin_user).first():
            admin = User(username=admin_user, password_hash=generate_password_hash(admin_pass))
            db.session.add(admin)
            db.session.commit()
            print(f"[OK] Admin user created: {admin_user}")
        else:
            print(f"[INFO] Admin user already exists: {admin_user}")


def apply_dynamic_config(app):
    """将数据库中的热更新配置同步到 app.config（应用启动时）。"""
    try:
        from sqlalchemy import inspect as sa_inspect
        from services.config_service import ConfigService
        if not sa_inspect(db.engine).has_table('system_setting'):
            return
        app.config['IMG_MAX_DIMENSION'] = ConfigService.get_img_max_dimension()
        app.config['IMG_QUALITY'] = ConfigService.get_img_quality()
        app.config['ENABLE_IMG_COMPRESS'] = ConfigService.get_enable_img_compress()
        app.config['MAX_REF_IMAGES'] = ConfigService.get_max_ref_images()
        app.config['ITEMS_PER_PAGE'] = ConfigService.get_items_per_page()
        app.config['ADMIN_PER_PAGE'] = ConfigService.get_admin_per_page()
        app.config['USE_THUMBNAIL_IN_PREVIEW'] = ConfigService.get_use_thumbnail_in_preview()
        app.config['UPLOAD_RATE_LIMIT'] = ConfigService.get_upload_rate_limit()
        app.config['LOGIN_RATE_LIMIT'] = ConfigService.get_login_rate_limit()
    except Exception as e:
        app.logger.warning(f"Dynamic config load skipped: {e}")


app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000)
