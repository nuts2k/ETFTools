# ETFTool

全栈 ETF 分析工具，基于 FastAPI (后端) 和 Next.js (前端)。

## 功能特性

- 📈 ETF 历史行情与实时数据查询
- 📊 核心指标计算 (CAGR, 最大回撤, 波动率)
- 🔒 安全认证 (JWT, 速率限制)
- 📱 响应式设计，支持局域网访问

## 快速开始

### 1. 后端配置

```bash
cd backend

# 1. 创建虚拟环境 (推荐)
python3 -m venv .venv
source .venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 生成安全密钥
python scripts/generate_secret.py
# 将生成的 SECRET_KEY 填入 .env 文件

# 4. 启动后端
python -m app.main
```

后端服务将在 `http://localhost:8000` 启动（支持局域网访问）。

### 2. 前端配置

```bash
cd frontend

# 1. 安装依赖
npm install

# 2. 配置环境变量 (可选，已自动配置为本地 API)
# 如果需要，可以创建 .env.local 覆盖配置
# echo "NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api/v1" > .env.local

# 3. 启动前端
npm run dev
```

前端应用将在 `http://localhost:3000` 启动。

## 开发指南

### 安全配置

项目使用了 `.env` 文件进行配置管理。在首次运行时，必须从 `.env.example` 创建 `.env` 文件并设置 `SECRET_KEY`。

- **SECRET_KEY**: 用于 JWT 签名，生产环境必须使用强随机字符串。
- **CORS**: 开发环境默认允许 `localhost:3000` 和局域网 IP (`192.168.x.x`)。
- **速率限制**: 默认关闭 (`ENABLE_RATE_LIMIT=false`)，可通过 `.env` 开启。

### 依赖管理

后端依赖通过 `requirements.txt` 锁定版本。如需添加新依赖：

1. 编辑 `backend/pyproject.toml`
2. 运行 `cd backend && ./scripts/freeze_requirements.sh`

## 文档

更多详细文档请参考：
- [文档导航索引](docs/README.md) - 完整的文档目录和查找指南
- [项目开发计划](docs/planning/PLAN.md) - 开发路线图和里程碑
- [产品需求文档](docs/planning/PRD.md) - 产品功能需求和规格说明
- [阶段一：安全加固设计](docs/design/2026-01-25-phase1-security-hardening-design.md)
- [Docker 部署指南](docs/deployment/docker-guide.md) - 容器化部署说明
