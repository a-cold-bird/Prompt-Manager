# Python 3.10 slim 基础镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 创建必要的目录
RUN mkdir -p instance static/uploads static/thumbnails logs

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py
ENV DATABASE_URL=sqlite:////app/instance/data.sqlite

# 暴露端口
EXPOSE 5000

# 创建初始化和启动脚本
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# 初始化数据库（幂等）并确保管理员账户存在\n\
echo "[INFO] Running database initialization..."\n\
python -m flask init-db\n\
echo "[OK] Database initialization finished"\n\
\n\
# 启动应用\n\
exec gunicorn \\\n\
  -w ${GUNICORN_WORKERS:-2} \\\n\
  -b ${GUNICORN_BIND:-0.0.0.0:5000} \\\n\
  --threads ${GUNICORN_THREADS:-4} \\\n\
  --log-level ${GUNICORN_LOG_LEVEL:-info} \\\n\
  --access-logfile - \\\n\
  --error-logfile - \\\n\
  app:app' > /start.sh && chmod +x /start.sh

# 启动命令
CMD ["/start.sh"]
