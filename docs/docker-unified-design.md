# ETFTool Docker 统一镜像构建设计文档

## 文档信息

- **项目名称**: ETFTool
- **文档版本**: 2.1
- **创建日期**: 2026-02-02
- **最后更新**: 2026-02-03
- **作者**: Claude
- **目标**: 将前后端统一构建到单个 Docker 镜像中，简化部署和管理

## 版本历史

| 版本 | 日期 | 更新内容 |
|------|------|---------|
| 1.0 | 2026-02-02 | 初始版本，基础架构设计 |
| 2.0 | 2026-02-02 23:30 | 新增 Nginx 反向代理优势分析、CORS 环境感知配置、完善 Docker Compose 配置 |
| 2.1 | 2026-02-03 | 更新架构图和配置，反映 Next.js standalone 模式需要 Node.js 服务器（非静态文件） |
| 2.2 | 2026-02-03 | 新增 ENCRYPTION_SALT 配置项，用于加密敏感信息 |
| 2.3 | 2026-02-03 | 新增告警通知系统说明，包括 Telegram 通知和 APScheduler 调度器 |

---

## 1. 背景与目标

### 1.1 与多容器方案的对比

**多容器方案的问题：**
- 需要管理两个独立的镜像和容器
- 容器间网络配置相对复杂
- 部署时需要协调多个服务启动顺序
- 资源开销相对较大（两个容器的基础开销）

**统一镜像方案的优势：**
- 单一镜像，部署更简单
- 无需容器间网络配置
- 启动更快，资源占用更少
- 更适合小型应用和快速部署场景

### 1.2 目标

**主要目标：**
1. 将 FastAPI 后端和 Next.js 前端打包到同一个 Docker 镜像
2. 支持多平台构建（linux/amd64 和 linux/arm64）
3. 使用 Nginx 作为反向代理，统一对外提供服务
4. 优化镜像体积和构建速度
5. 确保生产环境可用性

**目标平台：**
- `linux/amd64` - 主要目标，用于云服务器部署
- `linux/arm64` - 兼容 ARM 架构服务器和本地开发

---

## 2. 技术方案

### 2.1 架构设计

**整体架构：**
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
│  └─────────────┘   └──────┬──────┘    │
│                            │           │
│                     ┌──────┴──────┐   │
│                     │             │   │
│                     ▼             ▼   │
│            ┌──────────────┐  ┌────────────┐
│            │  SQLite DB   │  │  Alert     │
│            │  + Cache     │  │  Scheduler │
│            └──────────────┘  │ (APScheduler)│
│                              └────────────┘
│                                        │
└────────────────────────────────────────┘
         │
         ▼
    Host Port 3000
```

**请求流程：**
1. 用户访问 `http://localhost:3000`
2. Nginx 接收请求
3. 静态资源请求 (`/_next/static/*`, `/public/*`) → 直接返回静态文件
4. API 请求 (`/api/*`) → 反向代理到 FastAPI (localhost:8000)
5. 页面请求 (`/*`) → 反向代理到 Next.js Server (localhost:3001)
6. FastAPI 处理业务逻辑，访问 SQLite 数据库
7. Alert Scheduler 定时触发告警检查（每天 15:30，周一至周五）

**重要说明：Next.js Standalone 模式**
- Next.js standalone 输出模式生成的是一个 Node.js 服务器，而非纯静态文件
- 需要运行 `node server.js` 来启动 Next.js 服务器（监听 3001 端口）
- Nginx 将页面请求代理到 Next.js 服务器，而非直接返回 HTML 文件
- 只有 `/_next/static` 和 `/public` 目录下的资源才是真正的静态文件

### 2.2 为什么使用 Nginx 反向代理

**核心问题：为什么不直接暴露前后端端口？**

**方案对比：**

| 特性 | 直接暴露端口 | Nginx 反向代理 |
|------|-------------|---------------|
| 端口数量 | 2 个（3000 + 8000） | 1 个（3000） |
| CORS 配置 | 必需（跨域） | 不需要（同源） |
| 安全性 | 后端直接暴露 | 后端仅内部访问 |
| 静态文件性能 | Node.js 处理 | Nginx 原生处理（快 2-3 倍） |
| SSL 终止 | 前后端都需配置 | 统一在 Nginx 层 |
| 负载均衡 | 需要额外工具 | Nginx 内置支持 |

**主要优势：**

1. **安全性提升** 🔒
   - 后端只监听 `127.0.0.1:8000`（容器内部），不直接暴露到外部
   - 统一入口便于实施安全策略（IP 白名单、WAF 规则）
   - 减少攻击面

2. **无需 CORS 配置** ✅
   - 前后端都通过 `localhost:3000` 访问，同源请求
   - 避免复杂的 CORS 配置和安全风险
   - 减少 preflight 请求，提升性能

3. **静态文件服务性能** ⚡
   - Nginx 处理静态文件比 Node.js 快 2-3 倍
   - 内置 Gzip 压缩和缓存优化
   - 支持高并发（10000+ 连接）

4. **统一的请求路由** 🎯
   - 前端无需知道后端地址，使用相对路径即可
   - 便于环境切换（开发/测试/生产）
   - 统一的 URL 结构

5. **部署简化** 🚀
   - 只需管理一个端口
   - 防火墙只需开放一个端口
   - 便于负载均衡和扩展

6. **SSL/TLS 终止** 🔐
   - 在 Nginx 层统一处理 HTTPS
   - 后端无需处理加密，减少 CPU 开销
   - 统一的证书管理

**适用场景：**
- ✅ 生产环境部署（强烈推荐）
- ✅ 需要 HTTPS 的场景
- ✅ 高并发访问
- ✅ 对安全性有要求

### 2.3 核心技术栈

**基础镜像：** `python:3.11-slim`

**选择理由：**
- Python 环境是必需的（FastAPI 依赖）
- 可以在其中安装 Node.js 来构建前端
- slim 变体体积适中
- 官方维护，安全可靠

**关键组件：**
- **Nginx**: 反向代理和静态文件服务
- **Supervisor**: 进程管理工具，同时管理 Nginx、Next.js Server 和 uvicorn
- **uvicorn**: FastAPI ASGI 服务器
- **Node.js**: 运行 Next.js standalone 服务器（构建阶段和运行时都需要）
- **APScheduler**: 定时任务调度器，用于告警通知自动触发
- **python-telegram-bot**: Telegram Bot API 客户端，用于发送告警消息

### 2.4 多阶段构建策略

采用多阶段构建，分离构建环境和运行环境：

**构建流程：**
```
Stage 1: Frontend Builder
├─ 基础镜像: node:20-alpine
├─ 安装前端依赖
├─ Next.js 生产构建
└─ 输出: .next/standalone + static

Stage 2: Backend Builder
├─ 基础镜像: python:3.11-slim
├─ 安装 Python 依赖
└─ 编译二进制扩展

Stage 3: Runtime
├─ 基础镜像: python:3.11-slim
├─ 安装 Nginx + Supervisor + Node.js 20.x
├─ 复制前端构建产物
├─ 复制后端代码和依赖
├─ 配置 Nginx 和 Supervisor
└─ 配置非 root 用户权限
```

---

## 3. 详细实现设计

### 3.1 Dockerfile 结构

**完整的 Dockerfile 设计：**

```dockerfile
# ============================================
# Stage 1: 前端构建
# ============================================
FROM node:20-alpine AS frontend-builder

WORKDIR /frontend

# 复制前端依赖文件
COPY frontend/package*.json ./

# 安装依赖
RUN npm ci --only=production

# 复制前端源码
COPY frontend/ ./

# 构建 Next.js（standalone 模式）
RUN npm run build

# ============================================
# Stage 2: 后端依赖构建
# ============================================
FROM python:3.11-slim AS backend-builder

WORKDIR /backend

# 安装构建工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 复制后端依赖文件
COPY backend/requirements.txt ./

# 安装 Python 依赖
RUN pip install --no-cache-dir --user -r requirements.txt

# ============================================
# Stage 3: 运行时环境
# ============================================
FROM python:3.11-slim

WORKDIR /app

# 安装运行时依赖（包括 Node.js）
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    supervisor \
    curl \
    ca-certificates \
    gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制 Python 依赖到系统路径
COPY --from=backend-builder /root/.local /usr/local

# 复制后端代码
COPY backend/ /app/backend/

# 从前端构建阶段复制构建产物
COPY --from=frontend-builder /frontend/.next/standalone /app/frontend/
COPY --from=frontend-builder /frontend/.next/static /app/frontend/.next/static
COPY --from=frontend-builder /frontend/public /app/frontend/public

# 复制 Nginx 配置
COPY docker/nginx.conf /etc/nginx/nginx.conf

# 复制 Supervisor 配置
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# 创建必要的目录
RUN mkdir -p /app/backend/cache /app/backend/logs /var/log/supervisor

# 设置权限
RUN chown -R www-data:www-data /app /var/log/nginx /var/lib/nginx /var/log/supervisor

# 暴露端口
EXPOSE 3000

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD curl -f http://localhost:3000/api/health || exit 1

# 使用 Supervisor 启动所有服务
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
```

### 3.2 Nginx 配置

**nginx.conf 设计：**

```nginx
user appuser;
worker_processes auto;
pid /run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # 日志配置
    access_log /var/log/nginx/access.log;
    error_log /var/log/nginx/error.log;

    # 性能优化
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;

    # Gzip 压缩
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript
               application/json application/javascript application/xml+rss;

    server {
        listen 3000;
        server_name _;

        # Next.js 静态文件
        location /_next/static {
            alias /app/frontend/.next/static;
            expires 1y;
            add_header Cache-Control "public, immutable";
        }

        # Public 静态文件
        location /static {
            alias /app/frontend/public;
            expires 1y;
            add_header Cache-Control "public, immutable";
        }

        # API 请求代理到 FastAPI
        location /api {
            proxy_pass http://127.0.0.1:8000;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_cache_bypass $http_upgrade;

            # 超时配置
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }

        # 健康检查端点
        location /health {
            proxy_pass http://127.0.0.1:8000/health;
        }

        # 所有其他请求代理到 Next.js 服务器
        location / {
            proxy_pass http://127.0.0.1:3001;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_cache_bypass $http_upgrade;

            # 超时配置
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }
    }
}
```

### 3.3 Supervisor 配置

**supervisord.conf 设计：**

```ini
[supervisord]
nodaemon=true
user=root
logfile=/var/log/supervisor/supervisord.log
pidfile=/var/run/supervisord.pid

[program:nextjs]
command=node server.js
directory=/app/frontend
autostart=true
autorestart=true
stdout_logfile=/var/log/supervisor/nextjs.log
stderr_logfile=/var/log/supervisor/nextjs_error.log
priority=10
user=www-data
environment=PORT="3001",HOSTNAME="127.0.0.1"
startsecs=3

[program:fastapi]
command=uvicorn app.main:app --host 127.0.0.1 --port 8000
directory=/app/backend
autostart=true
autorestart=true
stdout_logfile=/var/log/supervisor/fastapi.log
stderr_logfile=/var/log/supervisor/fastapi_error.log
priority=20
user=www-data
environment=PYTHONPATH="/app/backend"
startsecs=3

[program:nginx]
command=/usr/sbin/nginx -g "daemon off;"
autostart=true
autorestart=true
stdout_logfile=/var/log/supervisor/nginx.log
stderr_logfile=/var/log/supervisor/nginx_error.log
priority=30
startsecs=5
```

### 3.4 CORS 环境感知配置

**核心原则：根据环境动态启用/禁用 CORS**

**环境对比：**

| 环境 | CORS 状态 | 原因 | 后端监听地址 |
|------|----------|------|-------------|
| 开发环境 | ✅ 启用 | 前后端分离运行，跨域访问 | 0.0.0.0:8000 |
| Docker 生产环境 | ❌ 禁用 | Nginx 反向代理，同源访问 | 127.0.0.1:8000 |

**backend/app/main.py 配置：**

```python
# CORS Configuration - 环境感知
if settings.is_development:
    # 开发环境：启用 CORS（支持本地开发 + 局域网访问）
    allow_origin_regex = r"http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2[0-9]|3[0-1])\.\d+\.\d+):(3000|8000)"

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_origin_regex=allow_origin_regex
    )
    logger.info("✅ CORS enabled for development (local + LAN access)")
else:
    # 生产环境（Docker）：禁用 CORS
    # Nginx 反向代理确保同源，无需 CORS
    logger.info("✅ CORS disabled (production mode with Nginx reverse proxy)")
```

**环境变量配置：**

```bash
# 开发环境 (.env)
ENVIRONMENT=development
BACKEND_HOST=0.0.0.0
BACKEND_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
SECRET_KEY=your-dev-secret-key-min-32-chars
ENCRYPTION_SALT=etftool_telegram_salt

# Docker 生产环境 (.env.docker 文件)
# 在 docker-compose.yml 中通过 ${SECRET_KEY} 引用
SECRET_KEY=your-super-secret-key-at-least-32-characters-long
ENCRYPTION_SALT=your-random-salt-16-chars

# ENCRYPTION_SALT 说明：
# - 用途：加密敏感信息（如 Telegram Bot Token）
# - 要求：随机字符串，建议 16 字符以上
# - 生成方法：python -c "import secrets; print(secrets.token_urlsafe(16))"
# - 重要性：生产环境强烈建议修改默认值
# - 注意：更改此值会导致已加密的数据无法解密，需重新配置
```

**优势：**
- 开发环境保留 CORS，支持本地开发和局域网访问（手机测试）
- 生产环境禁用 CORS，提升安全性和性能
- 自动根据环境切换，无需手动修改代码

---

## 4. 配置文件清单

### 4.1 需要创建的文件

| 文件路径 | 说明 | 优先级 |
|---------|------|--------|
| `Dockerfile` | 统一镜像定义 | 高 |
| `.dockerignore` | 构建排除文件 | 高 |
| `docker/nginx.conf` | Nginx 配置 | 高 |
| `docker/supervisord.conf` | Supervisor 配置 | 高 |
| `build.sh` | 构建脚本 | 中 |
| `docker-compose.yml` | 可选的编排配置 | 低 |
| `README-Docker.md` | Docker 使用文档 | 中 |

### 4.2 需要修改的文件

| 文件路径 | 修改内容 | 原因 |
|---------|---------|------|
| `frontend/next.config.ts` | 添加 `output: 'standalone'` | 启用独立输出 |
| `backend/.env.example` | 添加 Docker 环境变量说明 | 文档完善 |
| `backend/app/main.py` | 添加环境感知的 CORS 配置 | 开发环境启用 CORS，生产环境禁用 |
| `Dockerfile` | 设置生产环境变量 | 确保 Docker 环境使用正确配置 |

---

## 5. 构建和部署

### 5.1 构建命令

**单平台构建（本地测试）：**
```bash
docker buildx build \
  --platform linux/amd64 \
  -t etftool:latest \
  --load \
  .
```

**多平台构建（生产部署）：**
```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t registry/etftool:latest \
  --push \
  .
```

### 5.2 运行容器

**基本运行：**
```bash
docker run -d \
  --name etftool \
  -p 3000:3000 \
  -v $(pwd)/backend/cache:/app/backend/cache \
  -v $(pwd)/backend/etftool.db:/app/backend/etftool.db \
  etftool:latest
```

**使用环境变量：**
```bash
docker run -d \
  --name etftool \
  -p 3000:3000 \
  -e DATABASE_URL=sqlite:///./etftool.db \
  -e API_KEY=your_api_key \
  -v $(pwd)/backend/cache:/app/backend/cache \
  -v $(pwd)/backend/etftool.db:/app/backend/etftool.db \
  etftool:latest
```

### 5.3 Docker Compose 配置（推荐）

**为什么使用 Docker Compose：**
- 简化容器管理和配置
- 环境变量集中管理
- 便于版本控制和团队协作
- 支持一键启动和停止

**docker-compose.yml（生产环境）：**
```yaml
version: '3.8'

services:
  etftool:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: etftool

    # 端口映射
    ports:
      - "3000:3000"

    # 环境变量配置
    environment:
      # 应用配置
      - PROJECT_NAME=ETFTool
      - API_V1_STR=/api/v1
      - ENVIRONMENT=production

      # 安全配置（生产环境必须修改）
      - SECRET_KEY=${SECRET_KEY:-please-change-this-secret-key-in-production-min-32-chars}
      - ENCRYPTION_SALT=${ENCRYPTION_SALT:-etftool_telegram_salt}
      - ALGORITHM=HS256
      - ACCESS_TOKEN_EXPIRE_MINUTES=10080

      # 服务器配置（Docker 环境）
      - BACKEND_HOST=127.0.0.1
      - BACKEND_PORT=8000

      # 数据库配置
      - DATABASE_URL=sqlite:///./etftool.db

      # 缓存配置
      - CACHE_DIR=/app/backend/cache
      - CACHE_TTL=3600

      # 速率限制（生产环境建议启用）
      - ENABLE_RATE_LIMIT=true

    # 数据持久化
    volumes:
      - ./data/etftool.db:/app/backend/etftool.db
      - ./data/cache:/app/backend/cache
      - ./data/logs:/var/log/supervisor

    # 重启策略
    restart: unless-stopped

    # 健康检查
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/api/v1/health"]
      interval: 30s
      timeout: 3s
      retries: 3
      start_period: 40s

    # 资源限制（可选）
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M
```

**使用方式：**

```bash
# 1. 创建数据目录
mkdir -p data/cache data/logs

# 2. 创建环境变量文件（可选）
cp .env.docker.example .env.docker
# 编辑 .env.docker，设置必要的安全配置：
# - SECRET_KEY: 应用密钥（必须修改）
# - ENCRYPTION_SALT: 加密 salt（生产环境建议修改）

# 3. 启动服务
docker-compose up -d

# 4. 查看日志
docker-compose logs -f

# 5. 查看服务状态
docker-compose ps

# 6. 停止服务
docker-compose down

# 7. 重启服务
docker-compose restart

# 8. 查看资源使用
docker stats etftool
```

**使用 .env 文件管理环境变量：**

创建 `.env.docker` 文件：

```bash
# .env.docker
SECRET_KEY=your-super-secret-key-at-least-32-characters-long
ENABLE_RATE_LIMIT=true
```

修改 `docker-compose.yml`：

```yaml
services:
  etftool:
    env_file:
      - .env.docker
    # ... 其他配置
```

### 5.4 局域网访问配置

**Docker 环境的局域网访问：**

Docker 容器默认支持局域网访问，无需额外配置 CORS。

**访问方式：**

```bash
# 1. 获取本机 IP 地址
# macOS/Linux
ifconfig | grep "inet " | grep -v 127.0.0.1

# 输出示例: inet 192.168.1.100

# 2. 启动 Docker 容器
docker-compose up -d

# 3. 从局域网其他设备访问
# 手机/平板/其他电脑访问:
# http://192.168.1.100:3000
```

**环境对比：**

| 环境 | 前端地址 | 后端地址 | CORS | 局域网访问 |
|------|---------|---------|------|-----------|
| 本地开发 | localhost:3000 | localhost:8000 | ✅ 需要 | ✅ 支持（需配置 CORS） |
| Docker 部署 | localhost:3000 | 内部 127.0.0.1:8000 | ❌ 不需要 | ✅ 支持（Nginx 统一入口） |

**优势：**
- Docker 环境通过 Nginx 统一入口，局域网访问无需 CORS
- 手机访问 `http://192.168.1.100:3000` 即可，所有请求都是同源
- 比开发环境更简单，无需复杂的 CORS 正则配置

---

## 6. 安全配置说明

### 6.1 必需的安全配置

#### SECRET_KEY
- **用途**: JWT token 签名和应用安全
- **要求**: 至少 32 字符的随机字符串
- **生成方法**:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- **重要性**: ⚠️ 生产环境必须修改，否则应用拒绝启动

#### ENCRYPTION_SALT
- **用途**: 加密敏感信息（如 Telegram Bot Token）
- **要求**: 随机字符串，建议 16 字符以上
- **生成方法**:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(16))"
  ```
- **重要性**: 🔒 生产环境强烈建议修改，提高加密安全性
- **默认值**: `etftool_telegram_salt`（仅用于开发环境）

### 6.2 配置示例

**开发环境 (.env)**:
```bash
SECRET_KEY=dev-secret-key-for-testing-only-min-32-chars
ENCRYPTION_SALT=dev_encryption_salt
```

**生产环境 (.env.docker)**:
```bash
SECRET_KEY=<使用上述命令生成的随机密钥>
ENCRYPTION_SALT=<使用上述命令生成的随机 salt>
```

### 6.3 安全最佳实践

1. **永远不要**在代码仓库中提交真实的密钥
2. **使用环境变量**管理敏感配置
3. **定期轮换**密钥和 salt（建议每 6-12 个月）
4. **备份配置**：更换密钥前备份旧配置，避免数据无法解密
5. **不同环境使用不同密钥**：开发、测试、生产环境应使用不同的密钥

### 6.4 密钥轮换指南

**⚠️ 重要警告**：更换 `SECRET_KEY` 或 `ENCRYPTION_SALT` 会导致所有已加密的数据（如 Telegram Bot Token）无法解密。

**密钥轮换步骤**：

1. **备份当前配置**：
   ```bash
   # 备份环境变量文件
   cp .env.docker .env.docker.backup
   # 备份数据库
   cp data/etftool.db data/etftool.db.backup
   ```

2. **导出敏感数据**（如果需要保留）：
   - 在更换密钥前，先在设置页面重新输入 Telegram Bot Token
   - 或者记录下需要保留的敏感信息

3. **生成新密钥**：
   ```bash
   # 生成新的 SECRET_KEY
   python -c "import secrets; print(secrets.token_urlsafe(32))"

   # 生成新的 ENCRYPTION_SALT
   python -c "import secrets; print(secrets.token_urlsafe(16))"
   ```

4. **更新配置文件**：
   - 编辑 `.env.docker` 文件，替换新密钥

5. **重启服务**：
   ```bash
   docker-compose down
   docker-compose up -d
   ```

6. **重新配置敏感信息**：
   - 登录应用，在设置页面重新输入 Telegram Bot Token 等敏感信息

---

## 7. 镜像优化

### 6.1 预估镜像大小

**各层大小估算：**
- 基础镜像 (python:3.11-slim): ~120MB
- Nginx + Supervisor: ~20MB
- Python 依赖: ~100MB
- 前端构建产物: ~50MB
- 后端代码: ~10MB

**总计：约 300MB**

### 7.2 优化策略

**1. 层缓存优化**
- 先复制依赖文件，再复制源码
- 利用 Docker 层缓存加速重复构建

**2. .dockerignore 配置**
```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
.pytest_cache/
*.log

# Node.js
node_modules/
.next/
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# Git
.git/
.gitignore

# IDE
.vscode/
.idea/
*.swp
*.swo

# 环境变量
.env
.env.local

# 文档
*.md
docs/

# 测试
tests/
*.test.js
*.spec.js
```

**3. 多阶段构建**
- 构建阶段使用完整工具链
- 运行阶段只包含必需组件
- 减少最终镜像体积

---

## 8. 安全考虑

### 8.1 镜像安全

**最佳实践：**
1. 使用官方基础镜像
2. 定期更新基础镜像
3. 最小化安装的包
4. 使用非 root 用户运行应用（Supervisor 以 root 启动，但应用以 appuser 运行）

### 8.2 运行时安全

**环境变量管理：**
- 敏感信息通过环境变量传递
- 不要将 .env 文件打包到镜像中
- 使用 Docker secrets 或密钥管理服务

**网络安全：**
- FastAPI 只监听 127.0.0.1:8000（容器内部）
- 只暴露 Nginx 端口（3000）到外部
- 配置适当的 CORS 策略

---

## 9. 监控和日志

### 9.1 日志管理

**日志位置：**
- Supervisor 日志: `/var/log/supervisor/`
- Nginx 访问日志: `/var/log/nginx/access.log`
- Nginx 错误日志: `/var/log/nginx/error.log`
- FastAPI 日志: `/var/log/supervisor/fastapi.log`

**查看日志：**
```bash
# 查看所有日志
docker logs etftool

# 进入容器查看详细日志
docker exec -it etftool bash
tail -f /var/log/supervisor/fastapi.log
tail -f /var/log/nginx/access.log
```

### 9.2 健康检查

**健康检查配置：**
- 检查间隔: 30 秒
- 超时时间: 3 秒
- 重试次数: 3 次
- 检查端点: `http://localhost:3000/health`

**查看健康状态：**
```bash
docker ps
docker inspect etftool | grep Health -A 10
```

---

## 10. 故障排查

### 10.1 常见问题

**问题 1：容器启动失败**

**排查步骤：**
```bash
# 查看容器日志
docker logs etftool

# 查看 Supervisor 状态
docker exec -it etftool supervisorctl status

# 手动启动服务测试
docker exec -it etftool bash
supervisorctl restart all
```

**问题 2：前端无法访问后端 API**

**排查步骤：**
```bash
# 检查 Nginx 配置
docker exec -it etftool nginx -t

# 测试后端是否运行
docker exec -it etftool curl http://127.0.0.1:8000/health

# 查看 Nginx 错误日志
docker exec -it etftool tail -f /var/log/nginx/error.log
```

**问题 3：静态文件 404**

**排查步骤：**
```bash
# 检查文件是否存在
docker exec -it etftool ls -la /app/frontend/.next/static
docker exec -it etftool ls -la /app/frontend/public

# 检查 Nginx 配置中的路径
docker exec -it etftool cat /etc/nginx/nginx.conf
```

### 10.2 调试技巧

**进入容器调试：**
```bash
# 进入容器
docker exec -it etftool bash

# 检查进程
ps aux | grep nginx
ps aux | grep uvicorn

# 检查端口监听
netstat -tlnp

# 测试服务
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:3000/
```

---

## 11. 与多容器方案对比

### 11.1 优势

✅ **部署简单**
- 单个镜像，单个容器
- 无需配置容器间网络
- 启动命令更简单

✅ **资源占用更少**
- 只有一个容器的基础开销
- 共享系统资源
- 内存占用更低

✅ **管理方便**
- 统一的日志查看
- 统一的健康检查
- 统一的版本管理

### 11.2 劣势

❌ **灵活性较低**
- 前后端无法独立扩展
- 无法单独重启某个服务
- 更新需要重建整个镜像

❌ **镜像体积较大**
- 包含前后端所有依赖
- 约 300MB vs 多容器方案的 200MB + 150MB

❌ **构建时间较长**
- 需要构建前后端
- 任何改动都需要重建整个镜像

### 11.3 适用场景

**统一镜像方案适合：**
- 小型应用
- 单机部署
- 快速原型
- 资源受限环境

**多容器方案适合：**
- 大型应用
- 需要独立扩展
- 微服务架构
- 高可用部署

---

## 12. 总结

### 12.1 方案特点

**核心优势：**
- 单一镜像，部署简单
- Nginx 反向代理，性能优秀（静态文件服务快 2-3 倍）
- 无需 CORS 配置，安全性更高
- Supervisor 进程管理，稳定可靠
- 多平台支持，兼容性好
- 支持局域网访问，无需额外配置

**技术要点：**
- 多阶段构建优化镜像体积
- Nginx 处理静态文件和反向代理
- 环境感知的 CORS 配置（开发启用，生产禁用）
- Supervisor 管理多个进程
- 健康检查确保服务可用
- 完善的 Docker Compose 配置

### 12.2 实施步骤

**阶段 1：准备配置文件**
1. 创建 `Dockerfile`（统一镜像定义）
2. 创建 `docker/nginx.conf`（Nginx 配置）
3. 创建 `docker/supervisord.conf`（Supervisor 配置）
4. 创建 `.dockerignore`（构建排除文件）
5. 创建 `docker-compose.yml`（编排配置）
6. 创建 `.env.docker.example`（环境变量示例）

**阶段 2：修改现有代码**
1. 修改 `frontend/next.config.ts`（添加 standalone 输出）
2. 修改 `backend/app/main.py`（添加环境感知 CORS 配置）
3. 更新 `backend/.env.example`（添加 Docker 环境说明）

**阶段 3：构建测试**
1. 单平台构建测试（linux/amd64）
2. 本地运行验证
3. 功能测试（前端访问、API 调用、健康检查）
4. 局域网访问测试

**阶段 4：多平台构建（可选）**
1. 配置 buildx
2. 多平台构建测试（linux/amd64 + linux/arm64）
3. 推送到镜像仓库

**阶段 5：文档完善**
1. 编写 `README-Docker.md`（使用文档）
2. 添加故障排查指南
3. 更新项目 README

### 12.3 后续优化

1. **性能优化**
   - 配置 Nginx 缓存
   - 启用 HTTP/2
   - 优化 uvicorn 工作进程数

2. **监控集成**
   - 添加 Prometheus 指标
   - 集成日志收集
   - 配置告警

3. **CI/CD**
   - GitHub Actions 自动构建
   - 自动推送到镜像仓库
   - 自动部署到服务器

---

## 13. 关键决策点总结

### 13.1 Nginx 反向代理 vs 直接暴露端口

**决策：使用 Nginx 反向代理** ✅

**理由：**
1. **安全性**：后端只监听 127.0.0.1，不直接暴露
2. **无需 CORS**：同源请求，避免跨域问题
3. **性能**：静态文件服务快 2-3 倍
4. **简化部署**：只需一个端口
5. **SSL 终止**：统一在 Nginx 层处理 HTTPS

**适用场景：** 生产环境部署（强烈推荐）

### 13.2 CORS 配置策略

**决策：环境感知的 CORS 配置** ✅

**策略：**
- **开发环境**：启用 CORS（支持本地开发 + 局域网访问）
- **Docker 生产环境**：禁用 CORS（Nginx 反向代理，同源）

**优势：**
- 开发环境保留灵活性（支持手机测试）
- 生产环境提升安全性和性能
- 自动根据 `ENVIRONMENT` 环境变量切换

### 13.3 数据持久化路径

**决策：使用独立的 data/ 目录** ✅

**路径规划：**
```
data/
├── etftool.db      # 数据库文件
├── cache/          # 缓存目录
└── logs/           # 日志目录
```

**理由：**
- 与源码分离，便于备份
- 避免污染 backend/ 目录
- 符合 Docker 最佳实践

### 13.4 Docker Compose 配置

**决策：提供完善的 Docker Compose 配置** ✅

**包含内容：**
- 完整的环境变量配置
- 健康检查（正确的 API 路径）
- 资源限制
- 数据持久化
- 重启策略

**优势：**
- 简化部署流程
- 环境变量集中管理
- 便于版本控制

---

## 14. 参考资料

- [Docker Multi-stage builds](https://docs.docker.com/build/building/multi-stage/)
- [Nginx 官方文档](https://nginx.org/en/docs/)
- [Supervisor 文档](http://supervisord.org/)
- [Next.js Docker 部署](https://nextjs.org/docs/deployment#docker-image)
- [FastAPI 部署指南](https://fastapi.tiangolo.com/deployment/)

---

**文档结束**

*本文档描述了 ETFTool 项目的 Docker 统一镜像构建方案，将前后端打包到单个容器中，简化部署流程。*

---

## 更新日志

### v2.0 (2026-02-02 23:30)

**新增内容：**
1. 添加"为什么使用 Nginx 反向代理"章节（2.2）
   - 详细对比直接暴露端口 vs Nginx 反向代理
   - 分析 6 大核心优势（安全性、CORS、性能、路由、部署、SSL）

2. 添加"CORS 环境感知配置"章节（3.4）
   - 开发环境启用 CORS（支持本地 + 局域网）
   - 生产环境禁用 CORS（Nginx 同源）
   - 提供完整的代码示例

3. 添加"局域网访问配置"章节（5.4）
   - Docker 环境局域网访问说明
   - 环境对比表格
   - 访问方式示例

4. 完善"Docker Compose 配置"章节（5.3）
   - 添加完整的环境变量配置
   - 修正健康检查路径（/api/v1/health）
   - 添加资源限制配置
   - 添加 .env 文件管理方式
   - 优化数据持久化路径（使用 data/ 目录）

5. 添加"关键决策点总结"章节（12）
   - 总结 4 个关键技术决策
   - 说明决策理由和优势

**改进内容：**
- 更新文档版本信息（添加版本历史表格）
- 更新章节编号（2.2 → 2.3 → 2.4）
- 完善"需要修改的文件"说明
- 优化"实施步骤"，添加更详细的任务清单
- 增强"方案特点"，突出新增优势

**修正内容：**
- 健康检查路径：/health → /api/v1/health
- 数据持久化路径：./backend/ → ./data/
- Docker Compose 优先级：低 → 推荐

### v2.1 (2026-02-03)

**架构更新：**
1. **Next.js Standalone 模式说明**
   - 明确 Next.js standalone 输出需要 Node.js 服务器运行
   - 更新架构图：Next.js Server (Port 3001) 而非静态文件
   - 添加请求流程说明：页面请求代理到 Next.js Server

2. **Dockerfile 改进**
   - 运行时阶段添加 Node.js 20.x 安装
   - Python 依赖从 /root/.local 改为 /usr/local（支持非 root 用户）
   - 使用 www-data 用户而非自定义 appuser

3. **Nginx 配置优化**
   - 添加 Next.js Server 代理配置（location /）
   - 为 API 和前端代理添加超时配置（60s）
   - 保留静态文件直接服务（/_next/static, /public）

4. **Supervisor 配置完善**
   - 添加 nextjs 进程配置（port 3001）
   - 调整启动优先级：Next.js (10) → FastAPI (20) → Nginx (30)
   - 添加 startsecs 确保服务稳定启动
   - 所有应用进程使用 www-data 用户运行

5. **安全改进**
   - 后端添加 SECRET_KEY 生产环境验证
   - 拒绝默认 SECRET_KEY 值
   - 应用进程使用非 root 用户（www-data）

**技术要点：**
- Next.js standalone 模式 = Node.js 服务器 + 静态资源，而非纯静态 HTML
- 需要同时运行 3 个进程：Nginx、Next.js Server、FastAPI
- Nginx 作为统一入口，代理到后端服务

### v2.3 (2026-02-03)

**告警通知系统：**
1. **新增功能**
   - Telegram 通知服务集成
   - APScheduler 定时任务调度器
   - 告警自动触发（每天 15:30，周一至周五）
   - Telegram Bot Token 加密存储（Fernet）

2. **依赖更新**
   - 添加 `python-telegram-bot==21.0`
   - 添加 `apscheduler==3.10.4`
   - 添加 `cryptography` (Fernet 加密)

3. **环境变量**
   - 新增 `ENCRYPTION_SALT` 配置项
   - 用于加密 Telegram Bot Token 等敏感信息
   - 默认值：`etftool_telegram_salt`（生产环境建议修改）

4. **架构更新**
   - FastAPI 集成 Alert Scheduler
   - 调度器在应用启动时自动初始化
   - 支持手动触发和自动调度两种模式

5. **API 端点**
   - `/api/v1/notifications/telegram/*` - Telegram 配置管理
   - `/api/v1/alerts/*` - 告警配置管理

6. **网络要求**
   - 容器需要访问 `api.telegram.org`
   - 如使用代理，需配置相应环境变量

### v1.0 (2026-02-02)

**初始版本：**
- 基础架构设计
- Dockerfile 多阶段构建
- Nginx 和 Supervisor 配置
- 基础 Docker Compose 示例

