import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))


class Config:
    """Application global config."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-please-change-in-prod'

    # Template autoreload (dev convenience)
    TEMPLATES_AUTO_RELOAD = True

    # Database: default to PostgreSQL
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql+psycopg2://prompt_manager:prompt_manager@db:5432/prompt_manager'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Upload config
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or 'static/uploads'
    MAX_REF_IMAGES = int(os.environ.get('MAX_REF_IMAGES') or 10)

    # Rate limits
    UPLOAD_RATE_LIMIT = os.environ.get('UPLOAD_RATE_LIMIT') or '100 per hour'
    LOGIN_RATE_LIMIT = os.environ.get('LOGIN_RATE_LIMIT') or '10 per minute'

    # Admin account
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME') or 'admin'
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') or '123456'

    # Pagination
    ITEMS_PER_PAGE = int(os.environ.get('ITEMS_PER_PAGE') or 24)
    ADMIN_PER_PAGE = int(os.environ.get('ADMIN_PER_PAGE') or 12)

    # Image processing
    IMG_MAX_DIMENSION = int(os.environ.get('IMG_MAX_DIMENSION') or 1600)
    IMG_QUALITY = int(os.environ.get('IMG_QUALITY') or 85)

    @staticmethod
    def _str_to_bool(s):
        return str(s).lower() == 'true'

    ENABLE_IMG_COMPRESS = _str_to_bool(os.environ.get('ENABLE_IMG_COMPRESS', 'True'))
    USE_THUMBNAIL_IN_PREVIEW = _str_to_bool(os.environ.get('USE_THUMBNAIL_IN_PREVIEW', 'True'))

    # Static resources mode
    USE_LOCAL_RESOURCES = _str_to_bool(os.environ.get('USE_LOCAL_RESOURCES', 'True'))

    # Visitor toggle control
    ALLOW_PUBLIC_SENSITIVE_TOGGLE = True

    # Object storage config
    STORAGE_TYPE = os.environ.get('STORAGE_TYPE') or 'local'

    S3_ENDPOINT = os.environ.get('S3_ENDPOINT')
    S3_ACCESS_KEY = os.environ.get('S3_ACCESS_KEY')
    S3_SECRET_KEY = os.environ.get('S3_SECRET_KEY')
    S3_BUCKET = os.environ.get('S3_BUCKET')
    S3_DOMAIN = os.environ.get('S3_DOMAIN')
    S3_THUMB_SUFFIX = os.environ.get('S3_THUMB_SUFFIX') or ''