# ETFTool Docker 部署指南

本文档介绍如何使用 Docker 部署 ETFTool 应用。

## 目录

- [快速开始](#快速开始)
- [架构说明](#架构说明)
- [环境变量配置](#环境变量配置)
- [数据库迁移](#数据库迁移)
- [管理员初始化](#管理员初始化)
- [构建镜像](#构建镜像)
  - [CI/CD 自动化构建](#cicd-自动化构建)
- [运行容器](#运行容器)
- [使用 Docker Compose](#使用-docker-compose)
- [数据持久化](#数据持久化)
- [健康检查](#健康检查)
- [日志查看](#日志查看)
- [故障排查](#故障排查)
- [安全建议](#安全建议)

---

## 快速开始

### 使用 Docker Compose（推荐）

```bash
# 1. 创建数据目录和数据库文件
mkdir -p data/cache data/logs
touch data/etftool.db

# 2. 生成 SECRET_KEY（必需）
python -c "import secrets; print(secrets.token_urlsafe(32))"

# 3. 生成 ENCRYPTION_SALT（推荐）
python -c "import secrets; print(secrets.token_urlsafe(16))"

# 4. 创建环境变量文件
cat > .env.docker <<EOF
SECRET_KEY=your-generated-secret-key-here
ENCRYPTION_SALT=your-generated-salt-here
ENABLE_RATE_LIMIT=true
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-secure-password-here
EOF

# 5. 启动服务
docker-compose up -d

# 6. 查看日志
docker-compose logs -f

# 7. 访问应用
# 浏览器打开: http://localhost:3000
```

> ⚠️ **重要提示**：
> - 必须在启动容器前创建 `data/etftool.db` 文件（使用 `touch` 命令）
> - 如果该文件不存在，Docker 会将其创建为目录，导致容器启动失败
> - **无需手动设置文件权限**：容器启动时会自动检测并修复数据库文件权限

### 使用 Docker 命令

```bash
# 1. 创建数据目录和数据库文件
mkdir -p data/cache data/logs
touch data/etftool.db

# 2. 构建镜像
docker build -t etftool:latest .

# 3. 运行容器
docker run -d \
  --name etftool \
  -p 3000:3000 \
  -e SECRET_KEY="your-secret-key-at-least-32-characters" \
  -v $(pwd)/data/etftool.db:/app/backend/etftool.db \
  -v $(pwd)/data/cache:/app/backend/cache \
  etftool:latest

# 4. 访问应用
# 浏览器打开: http://localhost:3000
```

---

## 架构说明

### 容器内部架构

```
┌─────────────────────────────────────────┐
│         Docker 容器                      │
├─────────────────────────────────────────┤
│                                          │
│  ┌──────────────────────────────────┐  │
│  │      Nginx (Port 3000)           │  │
│  │      反向代理 + 静态文件服务      │  │
│  └────────┬─────────────────┬───────┘  │
│           │                 │           │
│           ▼                 ▼           │
│  ┌─────────────┐   ┌─────────────┐    │
│  │  Next.js    │   │  FastAPI    │    │
│  │  Server     │   │  (uvicorn)  │    │
│  │  Port 3001  │   │  Port 8000  │    │
│  └─────────────┘   └─────────────┘    │
│                                        │
└────────────────────────────────────────┘
         │
         ▼
    Host Port 3000
```

### 服务说明

- **Nginx**: 统一入口，处理静态文件和反向代理
- **Next.js Server**: 前端应用服务器（standalone 模式）
- **FastAPI**: 后端 API 服务
- **Supervisor**: 进程管理，确保所有服务正常运行

### 请求路由

- `/_next/static/*` → Nginx 直接返回静态文件
- `/public/*` → Nginx 直接返回静态文件
- `/api/*` → Nginx 代理到 FastAPI (port 8000)
- `/*` → Nginx 代理到 Next.js Server (port 3001)

---

## 环境变量配置

### 必需的环境变量

| 变量名 | 说明 | 默认值 | 示例 |
|--------|------|--------|------|
| `SECRET_KEY` | JWT 签名密钥（至少 32 字符） | 无 | `your-super-secret-key-32-chars` |

### 可选的环境变量

| 变量名 | 说明 | 默认值 | 示例 |
|--------|------|--------|------|
| `PROJECT_NAME` | 项目名称 | `ETFTool` | `ETFTool` |
| `API_V1_STR` | API 路径前缀 | `/api/v1` | `/api/v1` |
| `ENVIRONMENT` | 运行环境 | `production` | `production` |
| `DATABASE_URL` | 数据库连接 | `sqlite:///./etftool.db` | `sqlite:///./etftool.db` |
| `CACHE_DIR` | 缓存目录 | `/app/backend/cache` | `/app/backend/cache` |
| `CACHE_TTL` | 缓存过期时间（秒） | `3600` | `3600` |
| `ENABLE_RATE_LIMIT` | 启用速率限制 | `false` | `true` |
| `ENCRYPTION_SALT` | 加密 Salt（用于 Telegram Token 加密） | `etftool_telegram_salt` | `your-random-salt-16-chars` |
| `ADMIN_USERNAME` | 初始管理员用户名（可选） | 无 | `admin` |
| `ADMIN_PASSWORD` | 初始管理员密码（可选） | 无 | `your-secure-password` |

### 管理员账户配置

ETFTool 支持通过环境变量自动初始化管理员账户（推荐用于 Docker 部署）。

**环境变量说明：**

| 变量名 | 说明 | 是否必需 | 示例 |
|--------|------|---------|------|
| `ADMIN_USERNAME` | 初始管理员用户名 | 可选 | `admin` |
| `ADMIN_PASSWORD` | 初始管理员密码 | 可选 | `your-secure-password` |

**自动初始化机制：**
- 如果同时设置了 `ADMIN_USERNAME` 和 `ADMIN_PASSWORD`，应用启动时会自动创建管理员账户
- 如果用户名已存在但不是管理员，会自动升级为管理员
- 如果用户名已存在且已是管理员，不会重复创建
- 如果未设置这两个环境变量，跳过自动初始化（可后续手动创建）

**配置示例：**
```bash
# 在 .env.docker 文件中添加
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-secure-password-here
```

**安全建议：**
- ✅ 生产环境密码至少 12 位，包含大小写字母、数字和特殊字符
- ✅ 不要使用默认密码（如 `admin`、`123456`）
- ✅ 首次登录后立即修改密码
- ✅ 定期更换管理员密码
- ❌ 不要在代码或公开文档中硬编码密码
- ❌ 不要将包含密码的 `.env.docker` 文件提交到 Git

### 生成 SECRET_KEY

**方法 1：使用 Python**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**方法 2：使用 OpenSSL**
```bash
openssl rand -base64 32
```

**方法 3：使用在线工具**
```bash
# 访问: https://generate-secret.vercel.app/32
```

### 数据库配置

应用默认使用 SQLite 数据库。数据库位置通过 `DATABASE_URL` 环境变量配置。

#### 支持的数据库 URL 格式

**相对路径（推荐）：**
```bash
# 相对于 backend 目录
DATABASE_URL=sqlite:///./etftool.db
# 结果：容器内 /app/backend/etftool.db
```

**绝对路径：**
```bash
# 使用四个斜杠表示绝对路径
DATABASE_URL=sqlite:////data/custom/mydb.db
# 结果：容器内 /data/custom/mydb.db
```

**其他数据库：**
```bash
# PostgreSQL
DATABASE_URL=postgresql://user:password@host:5432/dbname

# MySQL
DATABASE_URL=mysql://user:password@host:3306/dbname
```

#### 重要说明

1. **文件必须预先创建**：在启动容器前，必须使用 `touch` 创建数据库文件，否则 Docker 会将其创建为目录
2. **卷挂载必须匹配**：`docker-compose.yml` 中的卷挂载路径必须与 `DATABASE_URL` 配置的路径一致
3. **相对路径解析**：相对路径（`sqlite:///./filename.db`）会自动解析为相对于 backend 目录的绝对路径
4. **安全限制**：为防止路径遍历攻击，相对路径中不允许使用 `../`

#### 安全考虑

**数据库文件权限**：
- 容器启动时会自动将数据库文件权限设置为 `660`（所有者和组可读写）
- 文件所有权自动设置为 `www-data:www-data`
- 这确保只有应用进程可以访问数据库

**生产环境建议**：
- 对于生产部署，建议使用专用数据库服务器（PostgreSQL/MySQL）
- 定期备份数据库文件并加密存储
- 限制容器访问权限
- 定期进行安全审计
- 不要在 `DATABASE_URL` 中硬编码数据库密码，使用环境变量

#### 示例配置

**默认配置（docker-compose.yml）：**
```yaml
environment:
  - DATABASE_URL=sqlite:///./etftool.db
volumes:
  - ./data/etftool.db:/app/backend/etftool.db
```

**自定义路径：**
```yaml
environment:
  - DATABASE_URL=sqlite:////data/myapp.db
volumes:
  - ./data/myapp.db:/data/myapp.db
```

---

## 数据库迁移

### 管理员字段迁移

管理员系统需要在 User 表中添加新字段（`is_admin`、`is_active`、`updated_at`）。

**迁移命令：**
```bash
# 在容器内执行迁移脚本
docker exec etftool python scripts/migrate_add_admin_fields.py
```

**迁移说明：**
- 脚本会自动检查字段是否已存在，避免重复添加
- 迁移脚本是幂等的，可以安全地重复执行
- 如果字段已存在，会跳过并显示提示信息
- 迁移完成后会显示成功消息

**预期输出：**
```
开始数据库迁移...
✅ 添加 is_admin 字段
✅ 添加 is_active 字段
✅ 添加 updated_at 字段
✅ 数据库迁移完成
```

**注意事项：**
- 首次部署时需要执行此迁移
- 如果是全新部署（空数据库），应用启动时会自动创建完整的表结构，无需手动迁移
- 仅在从旧版本升级时需要执行此迁移

---

## 管理员初始化

管理员账户可以通过两种方式创建：

### 方式一：环境变量自动初始化（推荐用于 Docker）

**步骤：**

1. 在 `.env.docker` 文件中添加管理员配置：
```bash
cat >> .env.docker <<EOF
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-secure-password-here
EOF
```

2. 启动或重启容器：
```bash
docker-compose up -d
```

3. 查看日志确认创建成功：
```bash
docker-compose logs | grep "管理员"
# 预期输出: 管理员 'admin' 创建成功
```

**优势：**
- 自动化部署，无需手动干预
- 适合 CI/CD 流程
- 容器重启时自动检查和创建

### 方式二：交互式脚本创建

**步骤：**

1. 进入容器并执行创建脚本：
```bash
docker exec -it etftool bash
cd /app/backend
python scripts/create_admin.py
```

2. 按提示输入用户名和密码：
```
=== ETFTool 管理员创建工具 ===

用户名: admin
密码: ********
确认密码: ********

✅ 管理员创建成功! 用户名: admin, ID: 1
```

**优势：**
- 交互式输入，密码不会显示在命令历史中
- 可以在运行时随时创建新管理员
- 会检查现有管理员并提示确认

### 验证管理员账户

创建完成后，可以通过以下方式验证：

1. **登录测试：**
   - 访问 http://localhost:3000
   - 使用管理员账户登录
   - 进入"设置" → "管理员"页面（仅管理员可见）

2. **API 测试：**
```bash
# 获取 Token
curl -X POST http://localhost:3000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your-password"}'

# 使用 Token 访问管理员 API
curl http://localhost:3000/api/v1/admin/users \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## 构建镜像

### 单平台构建（本地测试）

```bash
# 构建 amd64 架构镜像
docker build -t etftool:latest .

# 或使用 buildx
docker buildx build \
  --platform linux/amd64 \
  -t etftool:latest \
  --load \
  .
```

### 多平台构建（生产部署）

```bash
# 构建 amd64 和 arm64 架构镜像
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t your-registry/etftool:latest \
  --push \
  .
```

### 构建优化

**使用构建缓存：**
```bash
# 使用 Docker 层缓存
docker build --cache-from etftool:latest -t etftool:latest .
```

**查看镜像大小：**
```bash
docker images etftool
```

### CI/CD 自动化构建

本项目已配置 GitHub Actions 自动化工作流，支持：
- ✅ 多平台镜像构建（linux/amd64, linux/arm64）
- ✅ 自动推送到 DockerHub
- ✅ 语义化版本标签管理
- ✅ 自动创建 GitHub Release

**详细配置指南**: [GitHub Actions 配置指南](github-actions-setup.md)

**快速使用：**
```bash
# 推送到 main 分支 → 自动构建并推送 latest 标签
git push origin main

# 创建版本标签 → 自动构建并推送版本镜像
git tag v1.0.0
git push origin v1.0.0

# 拉取自动构建的镜像
docker pull yourname/etftool:latest
```

---

## 运行容器

### 基本运行

```bash
docker run -d \
  --name etftool \
  -p 3000:3000 \
  -e SECRET_KEY="your-secret-key-here" \
  etftool:latest
```

### 完整配置运行

```bash
docker run -d \
  --name etftool \
  -p 3000:3000 \
  \
  -e SECRET_KEY="your-secret-key-at-least-32-characters" \
  -e ENABLE_RATE_LIMIT=true \
  -e CACHE_TTL=7200 \
  -e ADMIN_USERNAME="admin" \
  -e ADMIN_PASSWORD="your-secure-password" \
  \
  -v $(pwd)/data/etftool.db:/app/backend/etftool.db \
  -v $(pwd)/data/cache:/app/backend/cache \
  -v $(pwd)/data/logs:/var/log/supervisor \
  \
  --restart unless-stopped \
  \
  etftool:latest
```

### 容器管理命令

```bash
# 启动容器
docker start etftool

# 停止容器
docker stop etftool

# 重启容器
docker restart etftool

# 查看容器状态
docker ps -a | grep etftool

# 查看容器日志
docker logs -f etftool

# 进入容器
docker exec -it etftool bash

# 删除容器
docker rm -f etftool
```

---

## 使用 Docker Compose

### docker-compose.yml 配置

项目已包含 `docker-compose.yml` 文件，配置如下：

```yaml
version: '3.8'

services:
  etftool:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: etftool
    ports:
      - "3000:3000"
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - ENABLE_RATE_LIMIT=true
    volumes:
      - ./data/etftool.db:/app/backend/etftool.db
      - ./data/cache:/app/backend/cache
      - ./data/logs:/var/log/supervisor
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/api/v1/health"]
      interval: 30s
      timeout: 3s
      retries: 3
      start_period: 40s
```

### 使用步骤

```bash
# 1. 创建数据目录和数据库文件
mkdir -p data/cache data/logs
touch data/etftool.db

# 2. 创建 .env.docker 文件
cat > .env.docker <<EOF
SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
ENABLE_RATE_LIMIT=true
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-secure-password-here
EOF

# 3. 启动服务
docker-compose up -d

# 4. 查看服务状态
docker-compose ps

# 5. 查看日志
docker-compose logs -f

# 6. 停止服务
docker-compose down

# 7. 重启服务
docker-compose restart

# 8. 重新构建并启动
docker-compose up -d --build
```

---

## 数据持久化

### 推荐的数据目录结构

```
data/
├── etftool.db      # SQLite 数据库文件
├── cache/          # 缓存目录
└── logs/           # 日志目录
```

### 创建数据目录

```bash
mkdir -p data/cache data/logs
touch data/etftool.db
```

> ⚠️ **重要**：必须预先创建 `data/etftool.db` 文件，否则 Docker 会将其创建为目录导致挂载失败。

### 数据备份

```bash
# 备份数据库
cp data/etftool.db data/etftool.db.backup.$(date +%Y%m%d)

# 备份整个数据目录
tar -czf etftool-data-backup-$(date +%Y%m%d).tar.gz data/
```

### 数据恢复

```bash
# 恢复数据库
cp data/etftool.db.backup.20260203 data/etftool.db

# 恢复整个数据目录
tar -xzf etftool-data-backup-20260203.tar.gz
```

### ⚠️ 常见问题：数据库文件被创建为目录

**问题现象**：
容器启动失败，错误信息包含 "not a directory" 或 "vice-versa"

```
error mounting "/host_mnt/.../data/etftool.db" to rootfs at "/app/backend/etftool.db":
not a directory: Are you trying to mount a directory onto a file (or vice-versa)?
```

**原因**：
Docker 挂载不存在的文件时会自动创建为目录，导致应用无法正常写入数据库文件。

**解决方法**：
```bash
# 1. 停止并删除容器
docker-compose down

# 2. 删除错误的目录
rm -rf data/etftool.db

# 3. 创建正确的空文件
touch data/etftool.db

# 4. 重新启动
docker-compose up -d
```

**预防措施**：
在首次部署时，务必按照快速开始部分的步骤，先创建数据库文件再启动容器。

---

## 健康检查

### 健康检查端点

```bash
# 检查应用健康状态
curl http://localhost:3000/api/v1/health
```

**正常响应：**
```json
{
  "status": "ok",
  "data_ready": true,
  "environment": "production"
}
```

### Docker 健康检查

```bash
# 查看容器健康状态
docker ps

# 查看详细健康检查信息
docker inspect etftool | grep -A 10 Health
```

### Supervisor 进程状态

```bash
# 进入容器查看进程状态
docker exec -it etftool supervisorctl status

# 预期输出：
# nginx      RUNNING   pid 123, uptime 0:05:00
# nextjs     RUNNING   pid 124, uptime 0:05:00
# fastapi    RUNNING   pid 125, uptime 0:05:00
```

---

## 日志查看

### 容器日志

```bash
# 查看所有日志
docker logs etftool

# 实时查看日志
docker logs -f etftool

# 查看最近 100 行日志
docker logs --tail 100 etftool
```

### 服务日志

```bash
# 进入容器
docker exec -it etftool bash

# 查看 Nginx 访问日志
tail -f /var/log/nginx/access.log

# 查看 Nginx 错误日志
tail -f /var/log/nginx/error.log

# 查看 Next.js 日志
tail -f /var/log/supervisor/nextjs.log

# 查看 FastAPI 日志
tail -f /var/log/supervisor/fastapi.log

# 查看 Supervisor 日志
tail -f /var/log/supervisor/supervisord.log
```

### 使用 Docker Compose 查看日志

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f etftool
```

---

## 故障排查

### 问题 1：容器启动失败

**症状：** 容器启动后立即退出

**排查步骤：**
```bash
# 1. 查看容器日志
docker logs etftool

# 2. 检查 Supervisor 状态
docker exec -it etftool supervisorctl status

# 3. 手动重启服务
docker exec -it etftool supervisorctl restart all
```

**常见原因：**
- SECRET_KEY 未设置或长度不足
- 端口 3000 已被占用
- 数据目录权限问题

### 问题 2：前端无法访问

**症状：** 浏览器访问 http://localhost:3000 失败

**排查步骤：**
```bash
# 1. 检查容器是否运行
docker ps | grep etftool

# 2. 检查端口映射
docker port etftool

# 3. 测试 Nginx
docker exec -it etftool curl http://localhost:3000

# 4. 查看 Nginx 错误日志
docker exec -it etftool tail -f /var/log/nginx/error.log
```

### 问题 3：API 请求失败

**症状：** 前端可以访问，但 API 请求返回 502/504

**排查步骤：**
```bash
# 1. 检查 FastAPI 是否运行
docker exec -it etftool supervisorctl status fastapi

# 2. 测试 FastAPI 健康检查
docker exec -it etftool curl http://127.0.0.1:8000/api/v1/health

# 3. 查看 FastAPI 日志
docker exec -it etftool tail -f /var/log/supervisor/fastapi.log

# 4. 检查 Nginx 代理配置
docker exec -it etftool cat /etc/nginx/nginx.conf
```

### 问题 4：数据丢失

**症状：** 重启容器后数据丢失

**原因：** 未正确挂载数据卷

**解决方案：**
```bash
# 确保使用 -v 参数挂载数据目录
docker run -d \
  -v $(pwd)/data/etftool.db:/app/backend/etftool.db \
  -v $(pwd)/data/cache:/app/backend/cache \
  etftool:latest
```

### 问题 5：权限错误

**症状：** 日志显示 Permission denied

**排查步骤：**
```bash
# 1. 检查数据目录权限
ls -la data/

# 2. 修复权限（如果需要）
chmod -R 755 data/
chown -R $(id -u):$(id -g) data/

# 3. 重启容器
docker restart etftool
```

---

## 安全建议

### 1. SECRET_KEY 管理

- ✅ 使用强随机密钥（至少 32 字符）
- ✅ 不要在代码中硬编码
- ✅ 使用环境变量或密钥管理服务
- ❌ 不要使用默认值
- ❌ 不要提交到 Git 仓库

### 2. 网络安全

- ✅ 只暴露必要的端口（3000）
- ✅ 使用防火墙限制访问
- ✅ 生产环境启用 HTTPS
- ✅ 启用速率限制（ENABLE_RATE_LIMIT=true）

### 3. 数据安全

- ✅ 定期备份数据库
- ✅ 使用独立的数据目录
- ✅ 设置适当的文件权限
- ✅ 加密敏感数据

### 4. 容器安全

- ✅ 使用官方基础镜像
- ✅ 定期更新镜像
- ✅ 应用进程使用非 root 用户（www-data）
- ✅ 限制容器资源使用

### 5. 生产环境配置

```bash
# 推荐的生产环境配置
docker run -d \
  --name etftool \
  -p 3000:3000 \
  \
  -e SECRET_KEY="$(cat /run/secrets/etftool_secret_key)" \
  -e ENABLE_RATE_LIMIT=true \
  -e ENVIRONMENT=production \
  -e ADMIN_USERNAME="$(cat /run/secrets/admin_username)" \
  -e ADMIN_PASSWORD="$(cat /run/secrets/admin_password)" \
  \
  -v /data/etftool/db:/app/backend/etftool.db \
  -v /data/etftool/cache:/app/backend/cache \
  -v /data/etftool/logs:/var/log/supervisor \
  \
  --restart unless-stopped \
  --memory="2g" \
  --cpus="2.0" \
  \
  etftool:latest
```

---

## 告警通知功能

ETFTool 支持通过 Telegram 发送 ETF 信号告警通知。

### 功能说明

- **自动调度**: 每天 15:30（周一至周五）自动检查并发送告警
- **手动触发**: 支持通过 API 手动触发告警检查
- **加密存储**: Telegram Bot Token 使用 Fernet 加密存储
- **优先级过滤**: 支持按信号优先级（HIGH/MEDIUM/LOW）过滤

### 配置步骤

1. **创建 Telegram Bot**
   ```bash
   # 1. 在 Telegram 中搜索 @BotFather
   # 2. 发送 /newbot 创建新 Bot
   # 3. 获取 Bot Token（格式: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz）
   ```

2. **获取 Chat ID**
   ```bash
   # 1. 在 Telegram 中搜索你的 Bot 并发送任意消息
   # 2. 访问: https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   # 3. 在返回的 JSON 中找到 "chat":{"id":123456789}
   ```

3. **在应用中配置**
   - 登录 ETFTool
   - 进入"设置" → "告警设置"
   - 填写 Bot Token 和 Chat ID
   - 点击"测试连接"验证配置
   - 保存配置

### 网络要求

- 容器需要能够访问 Telegram API (`api.telegram.org`)
- 如果使用代理，需要配置相应的环境变量

### 测试连接

```bash
# 方法 1: 使用 Web UI
# 在"告警设置"页面点击"测试连接"按钮

# 方法 2: 使用 API
curl -X POST http://localhost:3000/api/v1/notifications/telegram/test \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json"
```

### 告警调度

- **调度时间**: 每天 15:30（周一至周五）
- **时区**: 使用系统时区
- **调度器**: APScheduler (AsyncIOScheduler)
- **日志位置**: `/var/log/supervisor/fastapi.log`

### 查看调度日志

```bash
# 查看 FastAPI 日志（包含调度信息）
docker exec -it etftool tail -f /var/log/supervisor/fastapi.log

# 查看启动日志
docker logs etftool | grep "Alert scheduler"
```

### 故障排查

**问题 1: 无法发送 Telegram 消息**
- 检查 Bot Token 是否正确
- 检查 Chat ID 是否正确
- 确认容器可以访问互联网
- 查看 FastAPI 日志中的错误信息

**问题 2: 调度器未运行**
```bash
# 检查 FastAPI 进程状态
docker exec -it etftool supervisorctl status fastapi

# 查看启动日志
docker logs etftool | grep "Alert scheduler"
```

**问题 3: Token 解密失败**
- 确认 ENCRYPTION_SALT 环境变量已设置
- 如果更改了 ENCRYPTION_SALT，需要重新配置 Telegram

---

## 局域网访问

Docker 容器默认支持局域网访问，无需额外配置。

### 访问步骤

```bash
# 1. 获取本机 IP 地址
# macOS/Linux
ifconfig | grep "inet " | grep -v 127.0.0.1

# 输出示例: inet 192.168.1.100

# 2. 启动容器
docker-compose up -d

# 3. 从局域网其他设备访问
# 手机/平板/其他电脑浏览器打开:
# http://192.168.1.100:3000
```

### 优势

- 无需配置 CORS（Nginx 统一入口）
- 所有请求都是同源请求
- 比开发环境更简单

---

## 性能优化

### 1. 资源限制

```yaml
# docker-compose.yml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 2G
    reservations:
      cpus: '0.5'
      memory: 512M
```

### 2. Nginx 缓存

```nginx
# 在 nginx.conf 中添加
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=my_cache:10m max_size=1g inactive=60m;

location /api {
    proxy_cache my_cache;
    proxy_cache_valid 200 5m;
    # ...
}
```

### 3. 增加 FastAPI 工作进程

```bash
# 修改 supervisord.conf
command=uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4
```

---

## 更多信息

- **设计文档**: [docs/docker-unified-design.md](docs/docker-unified-design.md)
- **项目主页**: [README.md](README.md)
- **问题反馈**: [GitHub Issues](https://github.com/your-repo/issues)

---

**文档版本**: 1.1
**最后更新**: 2026-02-05
