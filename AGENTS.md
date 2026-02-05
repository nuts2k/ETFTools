# ETFTool - AI 协作上下文 (AGENTS.md)

本文档旨在为 AI 代理（Agent）和开发者提供项目的全景视图，包含技术栈、架构决策、核心原则及关键代码路径，以便快速理解和维护项目。

## 1. 项目概览 (Project Identity)

*   **项目名称**: ETFTool (A股版)
*   **目标**: 打造一款专注于 **前复权 (QFQ)** 收益分析的专业 A 股 ETF 工具。
*   **平台**: Web 应用 (FastAPI + Next.js)，采用 **移动端优先 (Mobile-First)** 设计理念。
*   **核心价值**: 解决市场上大多数工具未对历史价格进行复权处理的问题，提供真实的长期收益回测数据。

## 2. 技术栈 (Tech Stack)

### 后端 (Backend)
*   **语言**: Python 3.9+
*   **框架**: FastAPI
*   **数据源**: `akshare` (东方财富接口)
*   **数据处理**: `pandas` (时间序列分析)
*   **缓存层**: 
    *   **DiskCache**: 持久化缓存，用于存储历史数据和计算结果（默认 4 小时过期）。
    *   **In-Memory**: 用于高频访问的实时行情数据。
*   **数据库**: SQLite + SQLModel (用于存储用户数据和自选列表)。
*   **认证**: OAuth2 + JWT。

### 前端 (Frontend)
*   **框架**: Next.js 16 (App Router)
*   **语言**: TypeScript
*   **UI 组件库**: Shadcn/UI + Tailwind CSS
*   **图表库**: Recharts (响应式、触摸友好)
*   **交互**: `@dnd-kit` (拖拽排序), `use-long-press` (长按操作)
*   **状态管理**: React Context (Auth, Watchlist, Settings)

## 3. 快速开始 (Quick Start)

项目提供了一键管理脚本 `manage.sh`，用于快速启动和管理服务。

### 常用命令
*   **启动服务**: `./manage.sh start` (同时启动前后端)
*   **安装依赖并启动**: `./manage.sh start --install`
*   **停止服务**: `./manage.sh stop`
*   **查看状态**: `./manage.sh status`
*   **重启服务**: `./manage.sh restart`

### 手动启动
*   **后端**: `cd backend && uvicorn app.main:app --reload --port 8000`
*   **前端**: `cd frontend && npm run dev` (运行在 3000 端口)

## 4. 项目结构 (Project Structure)

### 后端结构 (`backend/app/`)
*   **`main.py`**: 应用入口，CORS 配置，生命周期管理。
*   **`core/`**: 核心配置 (`config.py`)，数据库 (`database.py`)，缓存 (`cache.py`)。
*   **`api/v1/endpoints/`**:
    *   `etf.py`: 核心 ETF 业务（搜索、行情、历史、指标）。
    *   `watchlist.py`: 自选股管理与云端同步。
    *   `auth.py`: 用户注册与登录。
*   **`services/`**:
    *   `akshare_service.py`: 数据获取层，包含 DiskCache 和降级逻辑。
    *   `metrics_service.py`: 指标计算服务 (ATR, 回撤)。
    *   `valuation_service.py`: 估值分位服务（可选）。
*   **`data/`**: 静态数据和配置文件 (`metrics_config.json`, `etf_fallback.json`)。

### 前端结构 (`frontend/app/`)
*   **`page.tsx`**: 首页（自选列表），支持拖拽排序。
*   **`search/page.tsx`**: 搜索页，支持模糊搜索。
*   **`etf/[code]/page.tsx`**: ETF 详情页，包含图表和核心指标卡片。
*   **`settings/page.tsx`**: 设置页（主题、刷新频率、密码修改）。
*   **`login/` & `register/`**: 认证页面。

## 5. 核心开发原则 (Core Principles)

### 5.1 数据一致性
*   **前复权 (QFQ)**: 所有历史价格图表和收益率计算**必须**使用前复权数据 (`adjust="qfq"`)。
*   **实时拼接**: 历史收盘价数据必须与当日实时价格无缝拼接，确保图表显示最新动态。
*   **本地优先**: 自选列表和用户设置优先读取本地 LocalStorage，登录后进行云端合并。

### 5.2 性能策略
*   **预加载**: 服务启动时后台线程预加载 ETF 列表。
*   **缓存降级**: 优先读取 DiskCache → 内存 → 实时接口。
*   **防抖**: 搜索输入框需配置 `useDebounce` (300ms)。

### 5.3 UI/UX 规范
*   **配色**: 遵循国内习惯，**红涨 (#ef4444)** / **绿跌 (#22c55e)**。
*   **移动适配**: 布局需适应窄屏，Tooltip 需防止手指遮挡，按钮需有合适的可点击区域。

## 6. API 接口速查 (API Reference)

所有 API 前缀均为 `/api/v1`。

### ETF 数据
*   `GET /etf/search?q={keyword}`: 搜索 ETF。
*   `GET /etf/{code}/info`: 获取实时基础信息（含交易状态）。
*   `GET /etf/{code}/history`: 获取 QFQ 历史数据。
*   `GET /etf/{code}/metrics`: 获取核心指标 (CAGR, MDD, ATR, Volatility)。

### 自选与用户
*   `GET /watchlist`: 获取云端自选列表。
*   `POST /watchlist/sync`: 同步本地自选数据到云端（并集策略）。
*   `POST /auth/token`: 用户登录，获取 JWT。

## 7. 功能开关与配置 (Configuration)

### 7.1 动态指标配置
文件位置: `backend/app/data/metrics_config.json`
*   `drawdown_days`: 计算当前回撤的历史回溯天数（默认 120 天）。
*   `atr_period`: ATR 指标计算周期（默认 14 天）。
无需重启服务，修改 JSON 后自动生效（由 `config_loader.py` 管理）。

### 7.2 估值分位功能 (Feature Toggle)
目前该功能默认**关闭**，以节省 API 资源。
*   **开启方法**: 在 `backend/app/api/v1/endpoints/etf.py` 的 `get_etf_metrics` 函数中取消 `valuation_service.get_valuation(code)` 的注释。
*   **依赖文件**: `backend/app/data/etf_index_map.json` (ETF 到指数的映射表)。

## 8. 关键代码导航 (Key Paths)

| 功能模块 | 关键文件路径 | 说明 |
| :--- | :--- | :--- |
| **指标计算** | `backend/app/api/v1/endpoints/etf.py` | CAGR, MaxDrawdown 等核心算法实现位置 |
| **数据源** | `backend/app/services/akshare_service.py` | AkShare 接口调用封装与缓存逻辑 |
| **图表组件** | `frontend/components/ETFChart.tsx` | Recharts 图表配置与交互逻辑 |
| **自选逻辑** | `frontend/hooks/use-watchlist.ts` | 本地存储与云端同步的混合逻辑 |
| **应用配置** | `backend/app/core/config.py` | CORS, SECRET_KEY 等环境配置 |

## 9. 文档组织规范 (Documentation Structure)

### 9.1 文档目录结构

项目文档采用分类组织的方式，所有文档集中在 `docs/` 目录下，按功能和用途分为 6 个子目录：

```
ETFTool/
├── README.md              # 项目主文档
├── AGENTS.md              # AI 协作上下文（本文档）
├── CHANGELOG.md           # 版本变更记录
│
└── docs/                  # 文档根目录
    ├── README.md          # 文档导航索引
    ├── planning/          # 规划类文档
    ├── research/          # 研究类文档
    ├── design/            # 设计文档
    ├── implementation/    # 实现计划
    ├── deployment/        # 部署文档
    └── testing/           # 测试报告
```

### 9.2 文档分类说明

| 目录 | 用途 | 典型文档 |
|------|------|---------|
| **planning/** | 项目规划、产品需求等战略性文档 | PRD.md, PLAN.md |
| **research/** | 技术研究、算法分析、业务逻辑研究 | etf-valuation-research.md, pe-percentile-research.md |
| **design/** | 功能设计、架构设计、技术方案设计 | *-design.md |
| **implementation/** | 具体功能的实现步骤、技术细节 | *-impl.md, *-implementation.md |
| **deployment/** | 部署指南、运维手册、环境配置 | docker-guide.md, docker-multiarch-guide.md |
| **testing/** | 测试计划、测试报告、测试结果 | *-test-report.md |

### 9.3 文档命名规范

为保持文档的一致性和可维护性，请遵循以下命名规范：

| 文档类型 | 命名格式 | 示例 |
|---------|---------|------|
| 设计文档 | `YYYY-MM-DD-feature-design.md` | `2026-02-04-admin-system-design.md` |
| 实现计划 | `YYYY-MM-DD-feature-impl.md` | `2026-02-03-alert-notification-impl.md` |
| 测试报告 | `feature-test-report.md` | `auth-flow-test-report.md` |
| 研究文档 | `topic-research.md` | `etf-valuation-research.md` |
| 部署指南 | `platform-guide.md` | `docker-guide.md` |

**命名原则：**
- 使用小写字母和连字符（kebab-case）
- 设计和实现文档使用日期前缀（YYYY-MM-DD）便于追溯
- 使用描述性的功能名称
- 文件扩展名统一使用 `.md`

### 9.4 文档查找指南

**按需求查找：**
- **了解项目整体** → 阅读 `README.md` 和 `docs/planning/PRD.md`
- **部署项目** → 查看 `docs/deployment/` 目录
- **了解功能设计** → 在 `docs/design/` 目录中搜索功能名称
- **了解实现细节** → 在 `docs/implementation/` 目录中查找对应文档
- **查看测试情况** → 查看 `docs/testing/` 目录
- **了解技术原理** → 查看 `docs/research/` 目录

**按时间查找：**
设计和实现文档使用日期前缀，可按时间顺序查看项目演进：
```bash
ls -lt docs/design/        # 查看最近的设计文档
ls -lt docs/implementation/ # 查看最近的实现文档
```

### 9.5 文档维护原则

- **及时更新**：代码变更后及时更新相关文档
- **保持同步**：确保文档与实际实现保持一致
- **清晰简洁**：使用清晰的语言，避免冗余
- **结构化**：使用标题、列表、表格等组织内容
- **中文优先**：项目文档使用中文撰写，专业术语可保留英文

### 9.6 常用文档快速链接

**核心文档：**
- [文档导航索引](docs/README.md) - 完整的文档目录和查找指南
- [产品需求文档](docs/planning/PRD.md) - 产品功能需求和规格说明
- [项目开发计划](docs/planning/PLAN.md) - 开发路线图和里程碑

**部署相关：**
- [Docker 部署指南](docs/deployment/docker-guide.md) - 容器化部署说明
- [Docker 多架构支持](docs/deployment/docker-multiarch-guide.md) - 多平台镜像构建

**技术研究：**
- [ETF 估值研究](docs/research/etf-valuation-research.md) - 估值方法和指标研究
- [PE 分位数研究](docs/research/pe-percentile-research.md) - PE 分位数计算和应用

---
**注意**: 在修改代码时，请务必遵守上述原则，特别是保持数据口径的一致性（QFQ）。
