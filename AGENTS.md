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

---
**注意**: 在修改代码时，请务必遵守上述原则，特别是保持数据口径的一致性（QFQ）。
