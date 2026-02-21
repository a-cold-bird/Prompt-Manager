# 更新指南速览

本项目为你的 Docker Compose V2 环境提供了两套完整的更新指南：

## 📁 文档选择

### 🎯 选择 1: 快速更新（推荐首选）
**文件**: `DOCKER_UPDATE_CHECKLIST_V2.md`
- ⏱️ 阅读时间: 5 分钟
- 📝 内容: 快速步骤 + 验证清单
- 👥 适合: 想快速了解流程的用户

### 📚 选择 2: 完整指南（详细参考）
**文件**: `DOCKER_UPDATE_GUIDE_V2.md`
- ⏱️ 阅读时间: 15-20 分钟
- 📝 内容: 详细步骤 + 文件内容 + 问题排查
- 👥 适合: 想完全理解细节的用户

---

## ✨ V2 专属优化

两份指南都已针对 **Docker Compose V2** 优化：
- ✅ 使用 `docker compose` 命令（不带连字符）
- ✅ 包含 V1 vs V2 命令对比表
- ✅ 详细的兼容性说明

---

## 🚀 快速开始

1. **第一次更新？** → 先看 `DOCKER_UPDATE_CHECKLIST_V2.md`
2. **遇到问题？** → 查看 `DOCKER_UPDATE_GUIDE_V2.md` 的问题排查部分
3. **想看细节？** → 完整指南包含所有文件内容和配置说明

---

## 📋 更新步骤总结

```bash
# 第 1 步：停机备份 (2 分钟)
docker compose down
cp -r data data.backup
cp -r uploads uploads.backup
cp -r logs logs.backup

# 第 2 步：上传新文件 (1 分钟)
# 使用 SCP 或 Git pull 上传文件

# 第 3 步：重建启动 (2 分钟)
docker compose build --no-cache
docker compose up -d
sleep 10
docker compose ps
```

**总时间**: 5-10 分钟

---

## 🎯 关键改进

更新到新版本后，你将获得：

| 功能 | 之前 | 之后 |
|------|------|------|
| 数据库初始化 | 手动 | 自动 |
| 错误处理 | 基础 | 完善 |
| .env 支持 | 缺失 | 完整 |
| 启动日志 | 简单 | 详细 |

---

## 💡 常用命令速查

```bash
# 启动应用
docker compose up -d

# 停止应用
docker compose down

# 查看日志
docker compose logs -f web

# 进入容器
docker compose exec web bash

# 重启服务
docker compose restart web

# 备份数据
tar -czf backup-$(date +%Y%m%d).tar.gz data/ uploads/ logs/
```

---

## 📞 需要帮助？

- 快速问题 → 查看本文件
- 实际步骤 → `DOCKER_UPDATE_CHECKLIST_V2.md`
- 详细说明 → `DOCKER_UPDATE_GUIDE_V2.md`
- 问题排查 → `DOCKER_UPDATE_GUIDE_V2.md` 的"常见问题"部分

---

**祝更新顺利！**
