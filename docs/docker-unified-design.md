# ETFTool Docker 统一镜像构建设计文档

## 文档信息

- **项目名称**: ETFTool
- **文档版本**: 1.0
- **创建日期**: 2026-02-02
- **作者**: Claude
- **目标**: 将前后端统一构建到单个 Docker 镜像中，简化部署和管理

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
│  │         Nginx (Port 80)          │  │
│  │      反向代理 + 静态文件服务      │  │
│  └────────┬─────────────────┬───────┘  │
│           │                 │           │
│           ▼                 ▼           │
│  ┌─────────────┐   ┌─────────────┐    │
│  │  Next.js    │   │  FastAPI    │    │
│  │  静态文件    │   │  (uvicorn)  │    │
│  │             │   │  Port 8000  │    │
│  └─────────────┘   └──────┬──────┘    │
│                            │           │
│                            ▼           │
│                    ┌──────────────┐   │
│                    │  SQLite DB   │   │
│                    │  + Cache     │   │
│                    └──────────────┘   │
│                                        │
└────────────────────────────────────────┘
         │
         ▼
    Host Port 80/3000
```

**请求流程：**
1. 用户访问 `http://localhost:3000`
2. Nginx 接收请求
3. 静态资源请求 → 直接返回 Next.js 构建的静态文件
4. API 请求 (`/api/*`) → 反向代理到 FastAPI (localhost:8000)
5. FastAPI 处理业务逻辑，访问 SQLite 数据库

### 2.2 核心技术栈

**基础镜像：** `python:3.11-slim`

**选择理由：**
- Python 环境是必需的（FastAPI 依赖）
- 可以在其中安装 Node.js 来构建前端
- slim 变体体积适中
- 官方维护，安全可靠

**关键组件：**
- **Nginx**: 反向代理和静态文件服务
- **Supervisor**: 进程管理工具，同时管理 Nginx 和 uvicorn
- **uvicorn**: FastAPI ASGI 服务器
- **Node.js**: 用于构建 Next.js（仅构建阶段）

### 2.3 多阶段构建策略

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
├─ 安装 Nginx + Supervisor
├─ 复制前端构建产物
├─ 复制后端代码和依赖
├─ 配置 Nginx 和 Supervisor
└─ 创建非 root 用户
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

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    supervisor \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制 Python 依赖
COPY --from=backend-builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

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

# 创建非 root 用户
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app /var/log/nginx /var/lib/nginx

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
        }

        # 健康检查端点
        location /health {
            proxy_pass http://127.0.0.1:8000/health;
        }

        # 所有其他请求返回 Next.js 页面
        location / {
            root /app/frontend;
            try_files $uri $uri.html /index.html;
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

[program:nginx]
command=/usr/sbin/nginx -g "daemon off;"
autostart=true
autorestart=true
stdout_logfile=/var/log/supervisor/nginx.log
stderr_logfile=/var/log/supervisor/nginx_error.log
priority=10

[program:fastapi]
command=/root/.local/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
directory=/app/backend
autostart=true
autorestart=true
stdout_logfile=/var/log/supervisor/fastapi.log
stderr_logfile=/var/log/supervisor/fastapi_error.log
priority=20
user=appuser
environment=PYTHONPATH="/app/backend"
```

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
| `backend/.env.example` | 添加 Docker 配置说明 | 文档完善 |
| `backend/app/main.py` | 确保 CORS 配置正确 | 允许同源请求 |

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

### 5.3 Docker Compose 配置（可选）

**docker-compose.yml：**
```yaml
version: '3.8'

services:
  etftool:
    build: .
    ports:
      - "3000:3000"
    environment:
      - DATABASE_URL=sqlite:///./etftool.db
    volumes:
      - ./backend/cache:/app/backend/cache
      - ./backend/etftool.db:/app/backend/etftool.db
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 30s
      timeout: 3s
      retries: 3
```

**使用方式：**
```bash
# 启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止
docker-compose down
```

---

## 6. 镜像优化

### 6.1 预估镜像大小

**各层大小估算：**
- 基础镜像 (python:3.11-slim): ~120MB
- Nginx + Supervisor: ~20MB
- Python 依赖: ~100MB
- 前端构建产物: ~50MB
- 后端代码: ~10MB

**总计：约 300MB**

### 6.2 优化策略

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

## 7. 安全考虑

### 7.1 镜像安全

**最佳实践：**
1. 使用官方基础镜像
2. 定期更新基础镜像
3. 最小化安装的包
4. 使用非 root 用户运行应用（Supervisor 以 root 启动，但应用以 appuser 运行）

### 7.2 运行时安全

**环境变量管理：**
- 敏感信息通过环境变量传递
- 不要将 .env 文件打包到镜像中
- 使用 Docker secrets 或密钥管理服务

**网络安全：**
- FastAPI 只监听 127.0.0.1:8000（容器内部）
- 只暴露 Nginx 端口（3000）到外部
- 配置适当的 CORS 策略

---

## 8. 监控和日志

### 8.1 日志管理

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

### 8.2 健康检查

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

## 9. 故障排查

### 9.1 常见问题

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

### 9.2 调试技巧

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

## 10. 与多容器方案对比

### 10.1 优势

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

### 10.2 劣势

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

### 10.3 适用场景

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

## 11. 总结

### 11.1 方案特点

**核心优势：**
- 单一镜像，部署简单
- Nginx 反向代理，性能优秀
- Supervisor 进程管理，稳定可靠
- 多平台支持，兼容性好

**技术要点：**
- 多阶段构建优化镜像体积
- Nginx 处理静态文件和反向代理
- Supervisor 管理多个进程
- 健康检查确保服务可用

### 11.2 实施步骤

**阶段 1：准备配置文件（1 小时）**
1. 创建 Dockerfile
2. 创建 Nginx 配置
3. 创建 Supervisor 配置
4. 创建 .dockerignore

**阶段 2：构建测试（30 分钟）**
1. 单平台构建测试
2. 本地运行验证
3. 功能测试

**阶段 3：多平台构建（1 小时）**
1. 配置 buildx
2. 多平台构建测试
3. 推送到镜像仓库（可选）

**阶段 4：文档完善（30 分钟）**
1. 编写使用文档
2. 添加故障排查指南

**总计：约 3 小时**

### 11.3 后续优化

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

## 12. 参考资料

- [Docker Multi-stage builds](https://docs.docker.com/build/building/multi-stage/)
- [Nginx 官方文档](https://nginx.org/en/docs/)
- [Supervisor 文档](http://supervisord.org/)
- [Next.js Docker 部署](https://nextjs.org/docs/deployment#docker-image)
- [FastAPI 部署指南](https://fastapi.tiangolo.com/deployment/)

---

**文档结束**

*本文档描述了 ETFTool 项目的 Docker 统一镜像构建方案，将前后端打包到单个容器中，简化部署流程。*
