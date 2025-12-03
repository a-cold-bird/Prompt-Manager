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

# 暴露端口
EXPOSE 5000

# 启动命令
CMD ["gunicorn", "-w", "${GUNICORN_WORKERS:-2}", "-b", "0.0.0.0:5000", "--threads", "${GUNICORN_THREADS:-4}", "--log-level", "${GUNICORN_LOG_LEVEL:-info}", "app:app"]
