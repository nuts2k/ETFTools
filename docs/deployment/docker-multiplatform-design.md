# ETFTool Docker 多平台构建设计文档

## 文档信息

- **项目名称**: ETFTool
- **文档版本**: 1.0
- **创建日期**: 2026-02-02
- **作者**: Claude
- **目标**: 在 macOS ARM 环境下实现 x86_64 和 ARM64 双平台 Docker 镜像构建

---

## 1. 背景与目标

### 1.1 当前状况

ETFTool 是一个基于 FastAPI + Next.js 的 ETF 分析工具，目前采用传统方式部署：
- 后端：Python 虚拟环境 + uvicorn
- 前端：Node.js + Next.js dev server
- 管理：通过 `manage.sh` 脚本启动和停止服务

**存在的问题：**
- 环境依赖复杂，部署到新环境需要手动配置
- 缺乏隔离性，可能与系统环境冲突
- 难以在不同平台间迁移

### 1.2 目标

实现 Docker 容器化部署，并支持多平台镜像构建：

**主要目标：**
1. 在 macOS ARM (Apple Silicon) 环境下构建 x86_64 (amd64) 镜像
2. 同时支持 ARM64 镜像构建
3. 使用 docker-compose 简化服务编排
4. 优化镜像体积和构建速度
5. 确保生产环境可用性

**目标平台：**
- `linux/amd64` - 主要目标，用于云服务器部署
- `linux/arm64` - 兼容 ARM 架构服务器和本地开发

---

## 2. 技术方案

### 2.1 核心技术：Docker Buildx

Docker Buildx 是 Docker 的扩展构建工具，基于 Moby BuildKit，支持多平台镜像构建。

**关键特性：**
- 支持同时构建多个平台的镜像
- 使用 QEMU 模拟器实现跨平台构建
- 支持构建缓存优化
- 可以直接推送到镜像仓库

**工作原理：**
```
┌─────────────────┐
│  macOS ARM Host │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Docker Buildx   │
│  + QEMU         │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌────────┐
│ ARM64  │ │ AMD64  │
│ Image  │ │ Image  │
└────────┘ └────────┘
```

### 2.2 QEMU 用户模式模拟

QEMU (Quick Emulator) 是一个开源的处理器模拟器，Docker Desktop for Mac 已内置支持。

**工作机制：**
- 在 ARM 主机上模拟 x86 指令集
- 透明地运行 x86 二进制文件
- 自动处理系统调用转换

**性能影响：**
- ARM 原生构建：快速（5-10 分钟）
- x86 模拟构建：较慢（15-30 分钟）
- 运行时无性能损失（镜像在目标平台原生运行）

### 2.3 多阶段构建策略

采用多阶段构建（Multi-stage Build）减小镜像体积并提升安全性。

**后端构建流程：**
```
Stage 1: Builder
├─ 基础镜像: python:3.11-slim
├─ 安装构建工具
├─ 安装 Python 依赖
└─ 编译二进制扩展

Stage 2: Runtime
├─ 基础镜像: python:3.11-slim
├─ 仅复制运行时依赖
├─ 复制应用代码
└─ 创建非 root 用户
```

**前端构建流程：**
```
Stage 1: Dependencies
├─ 基础镜像: node:20-alpine
└─ 安装 node_modules

Stage 2: Builder
├─ 复制依赖和源码
└─ Next.js 生产构建

Stage 3: Runner
├─ 基础镜像: node:20-alpine
├─ 复制 standalone 输出
└─ 复制静态资源
```

**优势：**
- 最终镜像不包含构建工具，体积更小
- 减少攻击面，提升安全性
- 利用层缓存，加速重复构建

---

## 3. 架构设计

### 3.1 整体架构

```
┌─────────────────────────────────────────┐
│         Docker Compose 编排              │
├─────────────────────────────────────────┤
│                                          │
│  ┌──────────────┐    ┌──────────────┐  │
│  │   Frontend   │───▶│   Backend    │  │
│  │  (Next.js)   │    │  (FastAPI)   │  │
│  │  Port: 3000  │    │  Port: 8000  │  │
│  └──────────────┘    └──────┬───────┘  │
│                              │           │
│                              ▼           │
│                      ┌──────────────┐   │
│                      │   SQLite DB  │   │
│                      │   + Cache    │   │
│                      └──────────────┘   │
│                                          │
└─────────────────────────────────────────┘
         │                    │
         ▼                    ▼
    Volume Mount         Volume Mount
    (static files)       (data persist)
```

### 3.2 网络设计

**网络模式：** 桥接网络（Bridge Network）

```
etftool-network (自定义桥接网络)
├─ backend (服务名)
│  └─ 容器内部: 0.0.0.0:8000
│  └─ 主机映射: localhost:8000
│
└─ frontend (服务名)
   └─ 容器内部: 0.0.0.0:3000
   └─ 主机映射: localhost:3000
   └─ 后端连接: http://backend:8000
```

**服务发现：**
- 容器间通过服务名通信（Docker DNS）
- 前端通过 `http://backend:8000` 访问后端
- 外部通过 `localhost:3000` 和 `localhost:8000` 访问

### 3.3 数据持久化设计

**后端数据卷：**
```yaml
volumes:
  - ./backend/cache:/app/cache        # 缓存目录
  - ./backend/etftool.db:/app/etftool.db  # SQLite 数据库
```

**前端数据卷：**
- 无需持久化（静态资源已打包在镜像中）

**优势：**
- 容器重启数据不丢失
- 便于备份和迁移
- 可以直接访问宿主机文件

---

## 4. 镜像设计

### 4.1 后端镜像 (Backend)

**基础镜像选择：** `python:3.11-slim`

**选择理由：**
- 官方维护，安全可靠
- slim 变体体积小（约 120MB）
- 原生支持 amd64 和 arm64
- 包含必要的系统库

**镜像结构：**
```
etftool-backend:latest
├─ 基础层: python:3.11-slim
├─ 系统依赖层: gcc, build-essential
├─ Python 依赖层: pip install
├─ 应用代码层: COPY app/
└─ 运行配置: CMD, EXPOSE, USER
```

**预估大小：** 200-300MB

**Dockerfile 关键配置：**
```dockerfile
# 多阶段构建
FROM python:3.11-slim as builder
# 安装依赖...

FROM python:3.11-slim as runtime
# 复制依赖和代码
# 创建非 root 用户
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s \
  CMD curl -f http://localhost:8000/health || exit 1
```

### 4.2 前端镜像 (Frontend)

**基础镜像选择：** `node:20-alpine`

**选择理由：**
- Alpine Linux 极致轻量（约 40MB）
- 原生支持多平台
- Node.js 20 LTS 版本
- 包含 npm 和基础工具

**镜像结构：**
```
etftool-frontend:latest
├─ 基础层: node:20-alpine
├─ 依赖层: node_modules (生产依赖)
├─ 构建产物: .next/standalone
├─ 静态资源: .next/static, public/
└─ 运行配置: CMD node server.js
```

**预估大小：** 150-200MB

**Next.js Standalone 输出：**
- 自动分析依赖，只打包必需的文件
- 减少约 80% 的镜像体积
- 包含内置的 Node.js 服务器

### 4.3 镜像优化策略

**1. 层缓存优化**
```dockerfile
# ❌ 错误：每次代码变更都重新安装依赖
COPY . /app
RUN pip install -r requirements.txt

# ✅ 正确：先复制依赖文件，利用缓存
COPY requirements.txt /app/
RUN pip install -r requirements.txt
COPY . /app
```

**2. .dockerignore 配置**
排除不必要的文件，减小构建上下文：
- `__pycache__/`, `*.pyc`, `.pytest_cache/`
- `node_modules/`, `.next/`
- `.git/`, `.env`, `*.log`

**3. 安全加固**
- 使用非 root 用户运行
- 最小化安装的包
- 定期更新基础镜像

---

## 5. 构建流程设计

### 5.1 Buildx Builder 配置

**创建 Builder：**
```bash
docker buildx create \
  --name multiplatform \
  --driver docker-container \
  --use
```

**Driver 选择：** `docker-container`
- 独立的构建容器
- 支持多平台构建
- 更好的缓存管理

**验证配置：**
```bash
docker buildx inspect --bootstrap
```

### 5.2 构建命令设计

**单平台构建（快速测试）：**
```bash
docker buildx build \
  --platform linux/amd64 \
  -t etftool-backend:latest \
  --load \
  ./backend
```

**多平台构建（生产部署）：**
```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t registry/etftool-backend:latest \
  --push \
  ./backend
```

**参数说明：**
- `--platform`: 目标平台列表
- `--load`: 加载到本地 Docker（仅支持单平台）
- `--push`: 推送到镜像仓库（支持多平台）
- `--cache-from/--cache-to`: 缓存配置

### 5.3 自动化构建脚本

**脚本功能：** `build.sh`

```bash
#!/bin/bash
# 功能清单：
# 1. 检测 buildx 环境
# 2. 创建/使用 builder
# 3. 解析命令行参数
# 4. 构建前后端镜像
# 5. 可选推送到仓库
```

**使用示例：**
```bash
# 本地测试
./build.sh --platform linux/amd64

# 多平台构建
./build.sh --platform linux/amd64,linux/arm64

# 构建并推送
./build.sh --platform linux/amd64,linux/arm64 --push
```

---

## 6. Docker Compose 设计

### 6.1 服务定义

**docker-compose.yml 结构：**
```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=sqlite:///./etftool.db
    volumes:
      - ./backend/cache:/app/cache
      - ./backend/etftool.db:/app/etftool.db
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://backend:8000
    depends_on:
      - backend
    restart: unless-stopped

networks:
  default:
    name: etftool-network
```

### 6.2 环境变量管理

**后端环境变量：**
- 通过 `.env` 文件加载
- 支持容器内路径覆盖
- CORS 配置需包含前端容器地址

**前端环境变量：**
- `NEXT_PUBLIC_API_URL`: 后端服务地址
- 开发环境：`http://localhost:8000`
- 生产环境：`http://backend:8000`

### 6.3 健康检查配置

**后端健康检查：**
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 3s
  retries: 3
  start_period: 40s
```

**作用：**
- 自动检测服务健康状态
- 不健康时自动重启容器
- 依赖服务等待健康后再启动

---

## 7. 配置文件清单

### 7.1 需要创建的文件

| 文件路径 | 说明 | 优先级 |
|---------|------|--------|
| `backend/Dockerfile` | 后端镜像定义 | 高 |
| `backend/.dockerignore` | 后端构建排除 | 高 |
| `frontend/Dockerfile` | 前端镜像定义 | 高 |
| `frontend/.dockerignore` | 前端构建排除 | 高 |
| `docker-compose.yml` | 服务编排配置 | 高 |
| `build.sh` | 构建自动化脚本 | 中 |
| `README-Docker.md` | Docker 使用文档 | 中 |

### 7.2 需要修改的文件

| 文件路径 | 修改内容 | 原因 |
|---------|---------|------|
| `frontend/next.config.ts` | 添加 `output: 'standalone'` | 启用独立输出 |
| `backend/.env.example` | 添加 Docker 配置说明 | 文档完善 |

---

## 8. 部署方案

### 8.1 本地开发部署

**步骤：**
```bash
# 1. 配置环境变量
cp backend/.env.example backend/.env

# 2. 启动服务
docker-compose up -d

# 3. 查看日志
docker-compose logs -f

# 4. 访问服务
# 前端: http://localhost:3000
# 后端: http://localhost:8000
```

### 8.2 云服务器部署

**方案 A：直接部署**
```bash
# 1. 在服务器上安装 Docker
# 2. 克隆代码仓库
# 3. 配置环境变量
# 4. docker-compose up -d
```

**方案 B：镜像仓库部署**
```bash
# 本地构建并推送
./build.sh --platform linux/amd64 --push --registry your-registry.com

# 服务器拉取并运行
docker pull your-registry.com/etftool-backend:latest
docker pull your-registry.com/etftool-frontend:latest
docker-compose up -d
```

### 8.3 反向代理配置

**Nginx 配置示例：**
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:3000;
    }

    location /api {
        proxy_pass http://localhost:8000;
    }
}
```

---

## 9. 性能与优化

### 9.1 构建性能

**首次构建时间估算：**
- ARM64 镜像：5-10 分钟
- AMD64 镜像（QEMU 模拟）：15-30 分钟
- 总计（并行构建）：15-30 分钟

**优化策略：**
1. **使用构建缓存**
   ```bash
   --cache-from type=registry,ref=registry/image:cache
   --cache-to type=registry,ref=registry/image:cache
   ```

2. **分离开发和生产构建**
   - 开发：只构建 ARM64
   - 生产：CI/CD 构建多平台

3. **优化 Dockerfile 层顺序**
   - 不常变化的层放前面
   - 频繁变化的层放后面

### 9.2 运行性能

**资源占用估算：**
- 后端容器：CPU 0.5-1 核，内存 512MB-1GB
- 前端容器：CPU 0.5 核，内存 256MB-512MB
- 总计：CPU 1-1.5 核，内存 1-1.5GB

**性能监控：**
```bash
# 查看容器资源使用
docker stats

# 查看容器日志
docker-compose logs -f --tail=100
```

### 9.3 镜像体积优化

**目标体积：**
- 后端：< 300MB
- 前端：< 200MB
- 总计：< 500MB

**优化技巧：**
1. 使用 Alpine 或 Slim 基础镜像
2. 多阶段构建分离构建和运行环境
3. 清理 apt/apk 缓存
4. 使用 .dockerignore 排除不必要文件
5. Next.js standalone 输出

---

## 10. 安全考虑

### 10.1 镜像安全

**最佳实践：**
1. **使用官方基础镜像**
   - `python:3.11-slim` (官方维护)
   - `node:20-alpine` (官方维护)

2. **非 root 用户运行**
   ```dockerfile
   RUN adduser -D appuser
   USER appuser
   ```

3. **最小化安装包**
   - 只安装必需的依赖
   - 构建后清理缓存

4. **定期更新**
   - 定期重新构建镜像
   - 更新基础镜像版本

### 10.2 运行时安全

**环境变量管理：**
- 敏感信息通过 `.env` 文件管理
- 不要将 `.env` 提交到版本控制
- 生产环境使用密钥管理服务

**网络隔离：**
- 使用自定义网络隔离服务
- 只暴露必要的端口
- 配置防火墙规则

---

## 11. 故障排查

### 11.1 常见问题

**问题 1：构建 x86 镜像很慢**

**原因：** QEMU 模拟器性能开销

**解决方案：**
- 开发时只构建 ARM64：`--platform linux/arm64`
- 使用 CI/CD 在云端构建
- 利用构建缓存

**问题 2：前端无法连接后端**

**排查步骤：**
```bash
# 1. 检查后端是否运行
docker-compose ps

# 2. 检查后端日志
docker-compose logs backend

# 3. 测试网络连接
docker-compose exec frontend ping backend

# 4. 检查环境变量
docker-compose exec frontend env | grep API_URL
```

**问题 3：数据库文件丢失**

**原因：** 卷挂载配置错误

**解决方案：**
- 检查 docker-compose.yml 中的 volumes 配置
- 确保宿主机路径存在
- 使用命名卷代替绑定挂载

**问题 4：镜像平台不匹配**

**验证镜像平台：**
```bash
# 方法 1
docker inspect image:tag | grep Architecture

# 方法 2（需要推送到仓库）
docker buildx imagetools inspect registry/image:tag
```

### 11.2 调试技巧

**进入容器调试：**
```bash
# 进入运行中的容器
docker-compose exec backend bash

# 查看容器文件系统
docker-compose exec backend ls -la /app

# 查看环境变量
docker-compose exec backend env
```

**查看构建日志：**
```bash
# 详细构建日志
docker buildx build --progress=plain .

# 查看构建历史
docker history image:tag
```

---

## 12. CI/CD 集成建议

### 12.1 GitHub Actions 示例

```yaml
name: Build Multi-Platform Images

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2

      - name: Build and push
        uses: docker/build-push-action@v4
        with:
          context: ./backend
          platforms: linux/amd64,linux/arm64
          push: true
          tags: registry/etftool-backend:latest
```

### 12.2 优势

- 自动化构建流程
- 云端构建速度更快
- 自动推送到镜像仓库
- 支持多分支策略

---

## 13. 测试验证计划

### 13.1 环境验证

```bash
# 检查 Docker 版本
docker version
# 要求：>= 19.03

# 检查 buildx
docker buildx version

# 创建 builder
docker buildx create --name multiplatform --use
docker buildx inspect --bootstrap

# 验证支持的平台
docker buildx inspect | grep Platforms
# 应包含：linux/amd64, linux/arm64
```

### 13.2 构建验证

```bash
# 单平台构建测试
docker buildx build --platform linux/amd64 -t test:amd64 --load ./backend

# 验证镜像
docker images | grep test
docker inspect test:amd64 | grep Architecture
```

### 13.3 功能验证

```bash
# 启动服务
docker-compose up -d

# 检查服务状态
docker-compose ps
# 应显示：backend 和 frontend 都是 Up 状态

# 测试后端健康检查
curl http://localhost:8000/health
# 应返回：{"status": "ok"}

# 测试前端访问
curl http://localhost:3000
# 应返回：HTML 内容

# 测试 API 调用
curl http://localhost:8000/api/v1/etf/list

# 检查数据持久化
docker-compose down
docker-compose up -d
# 数据库和缓存应保留
```

### 13.4 多平台验证

```bash
# 构建多平台镜像（需要推送到仓库）
./build.sh --platform linux/amd64,linux/arm64 --push

# 验证镜像清单
docker buildx imagetools inspect registry/etftool-backend:latest

# 应显示：
# MediaType: application/vnd.docker.distribution.manifest.list.v2+json
# Platform: linux/amd64
# Platform: linux/arm64
```

---

## 14. 总结

### 14.1 方案优势

✅ **跨平台构建能力**
- 在 ARM Mac 上构建 x86 镜像
- 无需额外硬件投入

✅ **简化部署流程**
- docker-compose 一键启动
- 环境一致性保证

✅ **优化的镜像**
- 多阶段构建减小体积
- 层缓存加速构建

✅ **生产就绪**
- 健康检查配置
- 数据持久化方案
- 安全加固措施

✅ **易于维护**
- 清晰的文档
- 自动化脚本
- 标准化流程

### 14.2 技术要点

**核心技术栈：**
- Docker Buildx + QEMU 实现跨平台构建
- 多阶段构建优化镜像体积
- docker-compose 简化服务编排
- Next.js standalone 输出减小前端镜像

**关键配置：**
- 基础镜像：`python:3.11-slim` + `node:20-alpine`
- 目标平台：`linux/amd64` + `linux/arm64`
- 网络模式：自定义桥接网络
- 数据持久化：卷挂载

### 14.3 实施路线

**阶段 1：基础配置（1-2 小时）**
- 创建 Dockerfile 和 .dockerignore
- 配置 docker-compose.yml
- 修改 Next.js 配置

**阶段 2：构建测试（30 分钟）**
- 创建 buildx builder
- 单平台构建测试
- 本地运行验证

**阶段 3：多平台构建（1 小时）**
- 编写构建脚本
- 多平台构建测试
- 推送到镜像仓库（可选）

**阶段 4：文档完善（30 分钟）**
- 编写使用文档
- 更新环境变量说明
- 添加故障排查指南

**总计：约 3-4 小时**

### 14.4 后续优化方向

1. **CI/CD 集成**
   - GitHub Actions 自动构建
   - 自动推送到镜像仓库
   - 多分支构建策略

2. **监控和日志**
   - 集成 Prometheus + Grafana
   - 集中式日志收集
   - 告警配置

3. **开发体验**
   - 开发版 Dockerfile（支持热重载）
   - VS Code Dev Containers
   - 调试配置

4. **生产优化**
   - Nginx 反向代理
   - SSL/TLS 证书
   - 负载均衡配置

---

## 15. 参考资料

### 15.1 官方文档

- [Docker Buildx 文档](https://docs.docker.com/buildx/working-with-buildx/)
- [Multi-platform images](https://docs.docker.com/build/building/multi-platform/)
- [Docker Compose 文档](https://docs.docker.com/compose/)
- [Next.js Docker 部署](https://nextjs.org/docs/deployment#docker-image)

### 15.2 最佳实践

- [Dockerfile 最佳实践](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)
- [Docker 安全最佳实践](https://docs.docker.com/develop/security-best-practices/)
- [多阶段构建指南](https://docs.docker.com/build/building/multi-stage/)

### 15.3 相关工具

- **Docker Desktop for Mac**: 内置 buildx 和 QEMU 支持
- **Docker Hub**: 公共镜像仓库
- **GitHub Container Registry**: 私有镜像仓库
- **Portainer**: Docker 可视化管理工具

---

## 附录 A：快速命令参考

```bash
# === Buildx 管理 ===
docker buildx create --name multiplatform --use
docker buildx inspect --bootstrap
docker buildx ls

# === 构建命令 ===
# 单平台构建
docker buildx build --platform linux/amd64 -t image:tag --load .

# 多平台构建
docker buildx build --platform linux/amd64,linux/arm64 -t image:tag --push .

# === Docker Compose ===
docker-compose up -d          # 启动服务
docker-compose down           # 停止服务
docker-compose ps             # 查看状态
docker-compose logs -f        # 查看日志
docker-compose restart        # 重启服务

# === 镜像管理 ===
docker images                 # 列出镜像
docker inspect image:tag      # 查看镜像详情
docker buildx imagetools inspect registry/image:tag  # 查看多平台清单

# === 调试命令 ===
docker-compose exec backend bash    # 进入后端容器
docker stats                         # 查看资源使用
docker system df                     # 查看磁盘使用
```

---

**文档结束**

*本文档描述了 ETFTool 项目的 Docker 多平台构建完整设计方案，涵盖技术选型、架构设计、实施步骤和最佳实践。*

