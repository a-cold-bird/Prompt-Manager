from flask import current_app
from models import SystemSetting


class ConfigService:
    """运行时配置读写服务（数据库优先，配置文件兜底）。"""

    @staticmethod
    def get_img_max_dimension():
        val = SystemSetting.get_int('img_max_dimension', default=0)
        return val if val > 0 else current_app.config.get('IMG_MAX_DIMENSION', 1600)

    @staticmethod
    def set_img_max_dimension(value):
        v = max(1, int(value))
        SystemSetting.set_int('img_max_dimension', v)
        current_app.config['IMG_MAX_DIMENSION'] = v

    @staticmethod
    def get_img_quality():
        val = SystemSetting.get_int('img_quality', default=0)
        return val if val > 0 else current_app.config.get('IMG_QUALITY', 85)

    @staticmethod
    def set_img_quality(value):
        v = max(1, min(100, int(value)))
        SystemSetting.set_int('img_quality', v)
        current_app.config['IMG_QUALITY'] = v

    @staticmethod
    def get_enable_img_compress():
        db_val = SystemSetting.get_str('enable_img_compress', default='')
        if db_val:
            return db_val == '1'
        return current_app.config.get('ENABLE_IMG_COMPRESS', True)

    @staticmethod
    def set_enable_img_compress(value):
        v = bool(value)
        SystemSetting.set_bool('enable_img_compress', v)
        current_app.config['ENABLE_IMG_COMPRESS'] = v

    @staticmethod
    def get_max_ref_images():
        val = SystemSetting.get_int('max_ref_images', default=0)
        return val if val > 0 else current_app.config.get('MAX_REF_IMAGES', 10)

    @staticmethod
    def set_max_ref_images(value):
        v = max(1, int(value))
        SystemSetting.set_int('max_ref_images', v)
        current_app.config['MAX_REF_IMAGES'] = v

    @staticmethod
    def get_items_per_page():
        val = SystemSetting.get_int('items_per_page', default=0)
        return val if val > 0 else current_app.config.get('ITEMS_PER_PAGE', 24)

    @staticmethod
    def set_items_per_page(value):
        v = max(1, int(value))
        SystemSetting.set_int('items_per_page', v)
        current_app.config['ITEMS_PER_PAGE'] = v

    @staticmethod
    def get_admin_per_page():
        val = SystemSetting.get_int('admin_per_page', default=0)
        return val if val > 0 else current_app.config.get('ADMIN_PER_PAGE', 12)

    @staticmethod
    def set_admin_per_page(value):
        v = max(1, int(value))
        SystemSetting.set_int('admin_per_page', v)
        current_app.config['ADMIN_PER_PAGE'] = v

    @staticmethod
    def get_use_thumbnail_in_preview():
        db_val = SystemSetting.get_str('use_thumbnail_in_preview', default='')
        if db_val:
            return db_val == '1'
        return current_app.config.get('USE_THUMBNAIL_IN_PREVIEW', True)

    @staticmethod
    def set_use_thumbnail_in_preview(value):
        v = bool(value)
        SystemSetting.set_bool('use_thumbnail_in_preview', v)
        current_app.config['USE_THUMBNAIL_IN_PREVIEW'] = v

    @staticmethod
    def get_upload_rate_limit():
        val = SystemSetting.get_str('upload_rate_limit', default='')
        return val or current_app.config.get('UPLOAD_RATE_LIMIT', '100 per hour')

    @staticmethod
    def set_upload_rate_limit(value):
        v = str(value)
        SystemSetting.set_str('upload_rate_limit', v)
        current_app.config['UPLOAD_RATE_LIMIT'] = v

    @staticmethod
    def get_login_rate_limit():
        val = SystemSetting.get_str('login_rate_limit', default='')
        return val or current_app.config.get('LOGIN_RATE_LIMIT', '10 per minute')

    @staticmethod
    def set_login_rate_limit(value):
        v = str(value)
        SystemSetting.set_str('login_rate_limit', v)
        current_app.config['LOGIN_RATE_LIMIT'] = v

    @staticmethod
    def get_upload_settings():
        return {
            'img_max_dimension': ConfigService.get_img_max_dimension(),
            'img_quality': ConfigService.get_img_quality(),
            'enable_img_compress': ConfigService.get_enable_img_compress(),
            'max_ref_images': ConfigService.get_max_ref_images(),
        }

    @staticmethod
    def get_display_settings():
        return {
            'items_per_page': ConfigService.get_items_per_page(),
            'admin_per_page': ConfigService.get_admin_per_page(),
            'use_thumbnail_in_preview': ConfigService.get_use_thumbnail_in_preview(),
        }

    @staticmethod
    def get_rate_limit_settings():
        return {
            'upload_rate_limit': ConfigService.get_upload_rate_limit(),
            'login_rate_limit': ConfigService.get_login_rate_limit(),
        }

    @staticmethod
    def get_readonly_settings():
        db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
        return {
            'storage_type': current_app.config.get('STORAGE_TYPE', 'local'),
            'db_type': db_uri.split(':')[0] if db_uri else 'sqlite',
            'upload_folder': current_app.config.get('UPLOAD_FOLDER', 'static/uploads'),
            'use_local_resources': current_app.config.get('USE_LOCAL_RESOURCES', True),
        }
