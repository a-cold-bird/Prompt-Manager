# Docker 远程服务器更新指南

## 📋 更新概述

您的远程服务器上已经运行了旧版 Docker，现在需要更新到修复版本。

**主要改进：**
- ✅ 自动数据库初始化
- ✅ 完善的错误处理
- ✅ .env.example 支持
- ✅ 更清晰的日志输出

---

## 🛑 第一步：停机备份（在远程服务器执行）

### 1. 停止容器并备份数据

```bash
# 进入项目目录
cd /path/to/prompt-manager

# 停止容器
docker-compose down

# 备份数据
cp -r data data.backup
cp -r uploads uploads.backup
cp -r logs logs.backup

# 验证备份
ls -lah data.backup uploads.backup logs.backup
```

### 2. 备份当前的 Docker 文件

```bash
# 保存旧版本
cp Dockerfile Dockerfile.old
cp docker-compose.yml docker-compose.yml.old

echo "备份完成！"
```

---

## 📥 第二步：获取新文件

### 从本地开发机复制更新的文件到远程服务器

**方式 1：使用 SCP 复制文件（推荐）**

在本地开发机执行：
```bash
# 进入项目目录
cd F:\SHIRO_Object\Prompt-Manager

# 复制 Dockerfile
scp Dockerfile user@remote_server:/path/to/prompt-manager/

# 复制 docker-compose.yml
scp docker-compose.yml user@remote_server:/path/to/prompt-manager/

# 复制其他修改的文件
scp requirements.txt user@remote_server:/path/to/prompt-manager/
scp .env.example user@remote_server:/path/to/prompt-manager/
```

**方式 2：使用 Git（如果项目在 Git 仓库）**

在远程服务器执行：
```bash
cd /path/to/prompt-manager

# 拉取最新代码
git pull origin main

# 查看更新内容
git diff Dockerfile.old Dockerfile
git diff docker-compose.yml.old docker-compose.yml
```

**方式 3：手动编辑（如果无法复制）**

在远程服务器编辑 Dockerfile 和 docker-compose.yml，参照下面的文件内容。

---

## 🔧 第三步：重建和启动（在远程服务器执行）

### 1. 重建镜像

```bash
cd /path/to/prompt-manager

# 重建镜像（无缓存，确保使用最新代码）
docker-compose build --no-cache

# 查看构建进度
docker-compose logs web
```

### 2. 启动容器

```bash
# 启动容器
docker-compose up -d

# 等待容器初始化（第一次启动会初始化数据库）
sleep 10

# 查看日志
docker-compose logs -f web

# 等待看到类似输出：
# [INFO] 初始化数据库...
# [OK] 数据库初始化完成
# gunicorn: xxxx
```

### 3. 验证服务

```bash
# 检查容器运行状态
docker-compose ps

# 测试 API
curl http://localhost:5000/

# 查看健康检查状态
docker-compose ps | grep prompt-manager

# 如果状态为 "healthy"，说明更新成功！
```

---

## 📁 文件内容参考

### Dockerfile（需要替换的内容）

```dockerfile
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

# 复制环境文件示例
COPY .env.example .env.example

# 创建必要的目录
RUN mkdir -p instance static/uploads static/thumbnails logs

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py

# 暴露端口
EXPOSE 5000

# 创建初始化和启动脚本
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# 检查并初始化数据库\n\
if [ ! -f instance/data.sqlite ]; then\n\
  echo "[INFO] 初始化数据库..."\n\
  flask init-db\n\
  echo "[OK] 数据库初始化完成"\n\
fi\n\
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
```

### docker-compose.yml（需要替换的内容）

```yaml
version: '3.8'

services:
  web:
    build:
      context: .
      dockerfile: Dockerfile
    image: prompt-manager:local
    container_name: prompt-manager

    env_file: .env

    environment:
      GUNICORN_WORKERS: "2"
      GUNICORN_THREADS: "4"
      GUNICORN_BIND: 0.0.0.0:5000
      GUNICORN_LOG_LEVEL: info
      LOG_TO_FILE: "false"
      TZ: Asia/Shanghai

    ports:
      - "5000:5000"

    volumes:
      - ./data:/app/instance
      - ./uploads:/app/static/uploads
      - ./logs:/app/logs

    restart: unless-stopped

    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:5000/ || exit 1"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s

    stop_grace_period: 20s
```

---

## ✅ 更新验证清单

在远程服务器执行：

```bash
# 1. 检查容器状态
docker-compose ps

# 2. 查看最近日志
docker-compose logs web | tail -20

# 3. 测试 API 端点
curl -v http://localhost:5000/

# 4. 检查数据库是否初始化
docker-compose exec web ls -lah instance/

# 5. 验证数据持久化
docker-compose exec web ls -lah /app/instance/data.sqlite

# 6. 检查环境变量
docker-compose exec web env | grep FLASK
```

预期结果：
- ✅ 容器状态：Up (healthy)
- ✅ 日志显示：[OK] 数据库初始化完成
- ✅ API 返回：200 OK 或重定向到登录页
- ✅ 数据库文件存在
- ✅ 环境变量正确

---

## 🆘 常见问题和解决方案

### 问题 1：容器启动失败

```bash
# 查看详细日志
docker-compose logs web

# 重新构建（不使用缓存）
docker-compose build --no-cache
docker-compose up -d
```

### 问题 2：数据库初始化失败

```bash
# 检查 flask 命令是否可用
docker-compose exec web flask --version

# 手动初始化
docker-compose exec web flask init-db

# 查看数据库文件
docker-compose exec web ls -lah instance/
```

### 问题 3：权限问题

```bash
# 修复数据文件夹权限
sudo chmod -R 755 data/ uploads/ logs/

# 重启容器
docker-compose restart
```

### 问题 4：端口被占用

```bash
# 检查 5000 端口占用情况
sudo lsof -i :5000

# 如需更改端口，编辑 docker-compose.yml：
# ports:
#   - "8080:5000"  # 改为 8080

docker-compose build
docker-compose up -d
```

### 问题 5：回滚到旧版本

```bash
# 恢复旧文件
cp Dockerfile.old Dockerfile
cp docker-compose.yml.old docker-compose.yml

# 恢复数据
rm -rf data uploads logs
cp -r data.backup data
cp -r uploads.backup uploads
cp -r logs.backup logs

# 重新启动
docker-compose build
docker-compose up -d
```

---

## 📊 更新前后对比

| 功能 | 更新前 | 更新后 |
|------|--------|--------|
| 数据库初始化 | ❌ 手动 | ✅ 自动 |
| 错误处理 | ⚠️ 基础 | ✅ 完善 |
| .env 支持 | ❌ 缺失 | ✅ 完整 |
| 启动日志 | ⚠️ 简单 | ✅ 详细 |
| 生产就绪 | ⚠️ 部分 | ✅ 完全 |

---

## 🚀 更新后的日常操作

### 启动应用
```bash
cd /path/to/prompt-manager
docker-compose up -d
```

### 停止应用
```bash
docker-compose down
```

### 查看日志
```bash
docker-compose logs -f web
```

### 重启服务
```bash
docker-compose restart web
```

### 进入容器
```bash
docker-compose exec web bash
```

### 备份数据
```bash
tar -czf backup-$(date +%Y%m%d).tar.gz data/ uploads/ logs/
```

---

## 📞 需要帮助？

如果遇到问题：

1. 查看日志：`docker-compose logs web`
2. 检查状态：`docker-compose ps`
3. 测试连接：`curl http://localhost:5000/`
4. 查看此指南的常见问题部分

---

**更新应该在 5-10 分钟内完成！** 🎉

