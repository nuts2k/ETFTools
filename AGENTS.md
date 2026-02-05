# ETFTool - AI 协作快速参考手册

本文档为 AI 代理和开发者提供项目核心信息的快速参考，包含强制性开发规范、技术栈、关键代码路径等。

## 1. 项目身份 (Project Identity)

*   **项目名称**: ETFTool (A股版)
*   **核心价值**: 专注于 **前复权 (QFQ)** 收益分析的专业 A 股 ETF 工具
*   **平台定位**: Web 应用 (FastAPI + Next.js)，**移动端优先 (Mobile-First)** 设计

## 2. 技术栈速查 (Tech Stack)

| 层级 | 技术 | 说明 |
|------|------|------|
| **后端框架** | FastAPI + Python 3.9+ | 异步 Web 框架 |
| **数据源** | akshare | 东方财富接口 |
| **数据处理** | pandas | 时间序列分析 |
| **缓存** | DiskCache + In-Memory | 持久化缓存（4h）+ 实时数据缓存 |
| **数据库** | SQLite + SQLModel | 用户数据和自选列表 |
| **认证** | OAuth2 + JWT | 用户认证和授权 |
| **前端框架** | Next.js 16 (App Router) + TypeScript | React 框架 |
| **UI 组件** | Shadcn/UI + Tailwind CSS | 组件库和样式 |
| **图表** | Recharts | 响应式、触摸友好 |
| **交互** | @dnd-kit, use-long-press | 拖拽排序、长按操作 |
| **状态管理** | React Context | Auth, Watchlist, Settings |

## 3. 快速启动 (Quick Start)

**一键启动**: `./manage.sh start` (同时启动前后端)
**手动启动**:
- 后端: `cd backend && uvicorn app.main:app --reload --port 8000`
- 前端: `cd frontend && npm run dev`

## 4. 强制性开发规范 (Mandatory Standards)

### 4.1 数据一致性规范

⚠️ **【强制】前复权数据**
- 所有历史价格图表和收益率计算**必须**使用前复权数据 (`adjust="qfq"`)
- 示例：`ak.fund_etf_hist_em(symbol=code, adjust="qfq")`

⚠️ **【强制】实时数据拼接**
- 历史收盘价数据必须与当日实时价格无缝拼接
- 确保图表显示最新动态，避免数据断层

⚠️ **【强制】本地优先策略**
- 自选列表和用户设置优先读取本地 LocalStorage
- 登录后进行云端合并（并集策略）

### 4.2 UI/UX 强制规范

⚠️ **【强制】配色规范**
- 遵循国内习惯：**红涨 (#ef4444)** / **绿跌 (#22c55e)**
- 禁止使用国际惯例的绿涨红跌

⚠️ **【强制】移动端优先**
- 布局必须适应窄屏（320px+）
- Tooltip 需防止手指遮挡
- 按钮可点击区域 ≥ 44x44px

### 4.3 性能强制规范

⚠️ **【强制】防抖处理**
- 搜索输入框必须配置 `useDebounce` (300ms)
- 避免频繁 API 调用

⚠️ **【强制】缓存策略**
- 优先级：DiskCache → 内存缓存 → 实时接口
- DiskCache 默认 4 小时过期

### 4.4 安全规范

⚠️ **【强制】输入验证**
- 所有用户输入必须进行验证和清理
- API 端点必须验证请求参数的类型和范围

⚠️ **【强制】SQL 注入防护**
- 使用 SQLModel 的参数化查询，禁止字符串拼接 SQL
- 示例：`session.exec(select(User).where(User.id == user_id))` ✓

⚠️ **【强制】XSS 防护**
- 前端输出用户内容时必须转义
- React 默认转义，但使用 `dangerouslySetInnerHTML` 时需特别注意

⚠️ **【强制】认证和授权**
- 敏感操作必须验证 JWT token
- 检查用户权限后再执行操作

### 4.5 测试规范

⚠️ **【强制】单元测试**
- 新增业务逻辑函数必须编写单元测试
- 测试文件位置：`backend/tests/` 和 `frontend/__tests__/`

⚠️ **【强制】API 测试**
- 新增或修改 API 端点必须有集成测试
- 使用 pytest 和 FastAPI TestClient

⚠️ **【推荐】测试覆盖率**
- 核心业务逻辑测试覆盖率应达到 80% 以上
- 使用 `pytest --cov` 检查覆盖率

### 4.6 文档维护规范

⚠️ **【强制】提交前更新文档**
- 代码变更必须同步更新相关文档，禁止"先提交代码，后补文档"
- 文档更新与代码变更必须在同一个 commit 中提交

⚠️ **【强制】文档更新检查清单**

根据变更类型，必须检查并更新以下文档：

| 变更类型 | 必须检查的文档 | 更新内容 |
|---------|---------------|---------|
| **新增/修改 API 接口** | `AGENTS.md` 第 6 节 | 更新 API 接口速查表 |
| **修改技术栈** | `AGENTS.md` 第 2 节, `README.md` | 更新技术栈列表 |
| **新增/修改配置文件** | `AGENTS.md` 第 7 节 | 更新关键配置文件说明 |
| **修改核心代码路径** | `AGENTS.md` 第 5 节 | 更新核心代码导航表 |
| **新增强制性规范** | `AGENTS.md` 第 4 节 | 添加新的强制规范 |
| **修改 Docker 配置** | `docs/deployment/docker-*.md` | 更新部署文档 |
| **新增功能特性** | `README.md`, `docs/planning/PRD.md` | 更新功能列表和产品需求 |
| **修改启动方式** | `AGENTS.md` 第 3 节, `README.md` | 更新快速启动说明 |
| **架构/设计变更** | `docs/design/` | 创建或更新设计文档 |
| **实现重要功能** | `docs/implementation/` | 创建实现文档 |

⚠️ **【强制】文档更新标准**
- 保持文档与代码实现完全一致，不允许过时信息
- 更新涉及日期的文档时，修改文档底部的"最后更新"日期
- 使用清晰、准确的语言描述变更内容
- 表格、列表等结构化内容必须保持格式一致

⚠️ **【推荐】文档审查**
- 提交前通读修改的文档，确保逻辑连贯
- 检查文档中的链接是否有效
- 确认代码示例与实际代码一致

## 5. 核心代码导航 (Key Paths)

### 后端关键文件

| 功能模块 | 文件路径 | 说明 |
|---------|---------|------|
| **应用入口** | `backend/app/main.py` | CORS 配置、生命周期管理 |
| **核心配置** | `backend/app/core/config.py` | 环境变量、SECRET_KEY |
| **数据库** | `backend/app/core/database.py` | SQLite 连接和会话管理 |
| **缓存管理** | `backend/app/core/cache.py` | DiskCache 配置 |
| **ETF 接口** | `backend/app/api/v1/endpoints/etf.py` | 搜索、行情、历史、指标计算 |
| **自选管理** | `backend/app/api/v1/endpoints/watchlist.py` | 云端同步逻辑 |
| **用户认证** | `backend/app/api/v1/endpoints/auth.py` | 注册、登录、JWT |
| **数据源** | `backend/app/services/akshare_service.py` | AkShare 接口封装、缓存降级 |
| **指标计算** | `backend/app/services/metrics_service.py` | ATR, 回撤, CAGR 算法 |
| **估值服务** | `backend/app/services/valuation_service.py` | PE 分位数（可选） |
| **静态配置** | `backend/app/data/metrics_config.json` | 动态指标参数 |

### 前端关键文件

| 功能模块 | 文件路径 | 说明 |
|---------|---------|------|
| **首页** | `frontend/app/page.tsx` | 自选列表、拖拽排序 |
| **搜索页** | `frontend/app/search/page.tsx` | 模糊搜索、防抖 |
| **详情页** | `frontend/app/etf/[code]/page.tsx` | 图表、指标卡片 |
| **设置页** | `frontend/app/settings/page.tsx` | 主题、刷新频率 |
| **登录/注册** | `frontend/app/login/`, `frontend/app/register/` | 认证页面 |
| **图表组件** | `frontend/components/ETFChart.tsx` | Recharts 配置、交互 |
| **自选逻辑** | `frontend/hooks/use-watchlist.ts` | 本地存储、云端同步 |
| **认证上下文** | `frontend/contexts/AuthContext.tsx` | JWT 管理 |

## 6. API 接口速查 (API Reference)

所有 API 前缀均为 `/api/v1`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/etf/search?q={keyword}` | GET | 搜索 ETF |
| `/etf/{code}/info` | GET | 获取实时基础信息（含交易状态） |
| `/etf/{code}/history` | GET | 获取 QFQ 历史数据 |
| `/etf/{code}/metrics` | GET | 获取核心指标 (CAGR, MDD, ATR, Volatility) |
| `/watchlist` | GET | 获取云端自选列表 |
| `/watchlist/sync` | POST | 同步本地自选数据到云端（并集策略） |
| `/auth/token` | POST | 用户登录，获取 JWT |
| `/auth/register` | POST | 用户注册 |

## 7. 关键配置文件 (Configuration Files)

| 配置文件 | 位置 | 说明 |
|---------|------|------|
| **环境配置** | `backend/.env` | SECRET_KEY, CORS, 速率限制 |
| **动态指标** | `backend/app/data/metrics_config.json` | `drawdown_days`, `atr_period` (无需重启) |
| **ETF 映射** | `backend/app/data/etf_index_map.json` | ETF 到指数的映射表（估值功能） |
| **降级数据** | `backend/app/data/etf_fallback.json` | 接口失败时的备用数据 |

**估值分位功能开关**：
- 默认关闭，节省 API 资源
- 开启方法：在 `backend/app/api/v1/endpoints/etf.py:get_etf_metrics` 中取消 `valuation_service.get_valuation(code)` 的注释

## 8. 文档导航 (Documentation)

**完整文档索引**: [docs/README.md](docs/README.md) - 包含所有文档的分类导航和查找指南

**快速链接**:
- **项目规划**: [PRD](docs/planning/PRD.md), [PLAN](docs/planning/PLAN.md)
- **部署指南**: [Docker 部署](docs/deployment/docker-guide.md), [多架构支持](docs/deployment/docker-multiarch-guide.md)
- **技术研究**: [ETF 估值](docs/research/etf-valuation-research.md), [PE 分位数](docs/research/pe-percentile-research.md)
- **测试报告**: [docs/testing/](docs/testing/)

**文档目录结构**:
```
docs/
├── planning/          # 项目规划、产品需求
├── research/          # 技术研究、算法分析
├── design/            # 功能设计、架构设计
├── implementation/    # 实现计划、技术细节
├── deployment/        # 部署指南、运维手册
└── testing/           # 测试计划、测试报告
```

## 9. 常见任务快速指引 (Quick Task Guide)

| 任务 | 关键文件 |
|------|---------|
| **添加新 ETF 指标** | `backend/app/services/metrics_service.py`, `backend/app/api/v1/endpoints/etf.py` |
| **修改图表样式** | `frontend/components/ETFChart.tsx` |
| **调整缓存策略** | `backend/app/core/cache.py`, `backend/app/services/akshare_service.py` |
| **修改配色方案** | `frontend/app/globals.css` (Tailwind 变量) |
| **添加新 API 端点** | `backend/app/api/v1/endpoints/` (新建或修改文件) |
| **修改自选同步逻辑** | `frontend/hooks/use-watchlist.ts`, `backend/app/api/v1/endpoints/watchlist.py` |
| **调整指标参数** | `backend/app/data/metrics_config.json` (无需重启) |
| **添加单元测试** | `backend/tests/` (后端), `frontend/__tests__/` (前端) |

---
**重要提醒**: 修改代码时务必遵守第 4 节的强制性开发规范，特别是数据一致性（QFQ）和安全规范。
