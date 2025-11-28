from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# 初始化核心扩展
db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()

# 限流器 (具体限制在各蓝图中定义)
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
    default_limits=["5000 per day", "1000 per hour"]
)