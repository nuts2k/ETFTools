# ETFTool - AI 协作上下文 (AGENT.md)

## 1. 项目身份 (Project Identity)
*   **项目名称**: ETFTool (A股版)
*   **目标**: 专注于 **前复权 (QFQ)** 收益分析的专业 A 股 ETF 工具。
*   **平台**: Web 应用 (FastAPI + Next.js)，**移动端优先 (Mobile-First)** 设计。

## 2. 技术栈 (严格遵守)
*   **后端 (Backend)**:
    *   Python 3.9+
    *   **框架**: FastAPI
    *   **数据源**: `akshare` (东方财富接口)
    *   **数据处理**: `pandas`
    *   **缓存**: 内存缓存 (In-memory LRU) - MVP 阶段使用。
*   **前端 (Frontend)**:
    *   **框架**: Next.js 14+ (App Router)
    *   **语言**: TypeScript
    *   **UI 组件库**: Shadcn/UI + Tailwind CSS
    *   **图表库**: Recharts (响应式设计，触摸友好)

## 3. 核心开发原则
1.  **数据口径 (至关重要)**:
    *   历史数据必须使用 **前复权 (QFQ)** 价格。
    *   API: `ak.fund_etf_hist_em(adjust="qfq")`。
    *   **图表拼接**: 历史收盘价数据必须与当前的实时价格 (Spot Price) 无缝拼接，以展示最新动态。
2.  **性能优化**:
    *   **搜索**: **严禁**每次用户搜索都调用上游 API。必须在服务启动时预加载 ETF 列表到内存并缓存。
    *   **行情**: 缓存高频访问的数据，遵守上游接口的访问限制。
3.  **UI/UX 体验**:
    *   **移动优先**: 界面设计需适应窄屏和触摸操作。
    *   **配色**: 默认遵循国内习惯：**红涨 (#ef4444)** / **绿跌 (#22c55e)**。
    *   **图表交互**: 移动端 Tooltip 需固定位置显示（避免手指遮挡）。

## 4. 架构决策
*   **无数据库 (MVP)**: 后端状态使用内存缓存。用户的“自选列表 (Watchlist)”存储在客户端 `localStorage` 中。
*   **API 设计**:
    *   RESTful 风格。
    *   前缀 `/api/v1/...`。
    *   返回严格类型的 JSON (使用 Pydantic 模型)。

## 5. 当前进度
*   [x] PRD 已定稿 (`docs/PRD.md`)
*   [x] 后端环境搭建 (`backend/`) - 完成 (Skeleton & Env)
*   [x] 前端环境搭建 (`frontend/`) - 完成 (Next.js + Shadcn + Tailwind v3)

## 6. 常用命令 (待补充)
*   *启动后端*: `cd backend && uvicorn app.main:app --reload`
*   *启动前端*: `cd frontend && npm run dev`
