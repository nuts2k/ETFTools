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

# 安装构建工具（包括 git，用于从 Git 仓库安装依赖）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    git \
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

# 设置权限
RUN chown -R www-data:www-data /app /var/log/nginx /var/lib/nginx /var/log/supervisor

# 设置生产环境变量
ENV ENVIRONMENT=production
ENV BACKEND_HOST=127.0.0.1
ENV BACKEND_PORT=8000

# 暴露端口
EXPOSE 3000

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --retries=3 --start-period=40s \
    CMD curl -f http://localhost:3000/api/v1/health || exit 1

# 使用 Supervisor 启动所有服务
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
