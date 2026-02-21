# Docker Compose V2 远程更新 - 快速检查清单

## 🎯 5 分钟快速更新流程

适用于 **Docker Compose V2** (新版本)

### 在远程服务器执行

#### 第 1 步：停机备份（2 分钟）
```bash
cd /path/to/prompt-manager

# 停止容器 (V2 命令)
docker compose down

# 备份数据
cp -r data data.backup
cp -r uploads uploads.backup
cp -r logs logs.backup

# 备份 Docker 文件
cp Dockerfile Dockerfile.old
cp docker-compose.yml docker-compose.yml.old
```

#### 第 2 步：更新文件（1 分钟）

**方式 A：使用 SCP（从本地开发机）**
```bash
# 在本地开发机执行
scp Dockerfile user@remote:/path/to/prompt-manager/
scp docker-compose.yml user@remote:/path/to/prompt-manager/
```

**方式 B：使用 Git**
```bash
# 在远程服务器执行
git pull origin main
```

#### 第 3 步：重建并启动（2 分钟）
```bash
# 在远程服务器执行
cd /path/to/prompt-manager

# 重建镜像 (V2 命令)
docker compose build --no-cache

# 启动容器 (V2 命令)
docker compose up -d

# 等待初始化完成
sleep 10

# 验证 (V2 命令)
docker compose ps
curl http://localhost:5000/
```

---

## ✅ 验证清单

- [ ] 容器已停止：`docker compose down`
- [ ] 数据已备份：`ls -lah data.backup`
- [ ] 新文件已复制：`cat Dockerfile | head -5`
- [ ] 镜像已重建：`docker images | grep prompt-manager`
- [ ] 容器已启动：`docker compose ps`
- [ ] 服务可访问：`curl http://localhost:5000/`
- [ ] 日志正常：`docker compose logs web | tail -5`
- [ ] 状态健康：`docker compose ps | grep healthy`

---

## 🔙 如何回滚（如有问题）

```bash
# 恢复旧文件
cp Dockerfile.old Dockerfile
cp docker-compose.yml.old docker-compose.yml

# 恢复数据
rm -rf data uploads logs
cp -r data.backup data
cp -r uploads.backup uploads
cp -r logs.backup logs

# 重启 (V2 命令)
docker compose build
docker compose up -d
```

---

## 📋 更新内容

**修复的问题：**
1. ✅ 数据库自动初始化
2. ✅ 完善错误处理
3. ✅ .env 配置支持
4. ✅ 更清晰的日志

**关键改动：**
- Dockerfile 第 21-22 行：添加 .env.example 复制
- Dockerfile 第 35-53 行：改进启动脚本，添加数据库初始化
- docker-compose.yml 第 1 行：添加版本标记

---

## 🚨 常见问题速查

**Q: 使用什么命令？**
A: Docker Compose V2 使用 `docker compose` (无连字符)

**Q: 容器启动失败？**
A: `docker compose logs web` 查看详细日志

**Q: 数据库初始化失败？**
A: `docker compose exec web flask init-db`

**Q: 想回滚？**
A: 运行回滚命令，恢复旧文件和数据

**Q: 需要完整指南？**
A: 查看 DOCKER_UPDATE_GUIDE_V2.md 完整指南

---

## 📚 V1 vs V2 快速对比

| 功能 | V1 命令 | V2 命令 |
|------|--------|--------|
| 启动 | `docker-compose up -d` | `docker compose up -d` |
| 停止 | `docker-compose down` | `docker compose down` |
| 构建 | `docker-compose build` | `docker compose build` |
| 日志 | `docker-compose logs` | `docker compose logs` |

**关键点**: V2 使用 `docker compose` 代替 `docker-compose`

---

**预计停机时间：5-10 分钟** ⏱️
