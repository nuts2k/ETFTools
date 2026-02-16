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
| **数据源** | akshare, baostock | 东方财富 + Baostock 混合策略 |
| **数据处理** | pandas | 时间序列分析 |
| **缓存** | DiskCache + In-Memory | 持久化缓存（4h）+ 实时数据缓存 |
| **数据库** | SQLite + SQLModel | 用户数据和自选列表 |
| **认证** | OAuth2 + JWT | 用户认证和授权 |
| **前端框架** | Next.js 16 (App Router) + TypeScript | React 框架 |
| **UI 组件** | Shadcn/UI + Tailwind CSS | 组件库和样式 |
| **图表** | Recharts | 响应式、触摸友好 |
| **交互** | @dnd-kit, use-long-press, use-pull-to-refresh | 拖拽排序、长按操作、下拉刷新 |
| **状态管理** | React Context | Auth, Watchlist, Settings |
| **PWA 支持** | manifest.json + Apple meta tags | iOS/Android 主屏幕安装 |

## 3. 快速启动 (Quick Start)

**一键启动**: `./manage.sh start` (同时启动前后端)
**手动启动**:
- 后端: `cd backend && uvicorn app.main:app --reload --port 8000`
- 前端: `cd frontend && npm run dev`

**远程调试**: `./scripts/remote-diagnose.sh` (快速诊断远程服务器)

### 3.1 远程调试配置 (Remote Debugging)

**配置文件**: `.remote-config.json` (本地配置，不提交到 Git)

**首次配置**:
```bash
cp .remote-config.template.json .remote-config.json
# 编辑 .remote-config.json 填写真实的服务器信息
```

**AI 代理使用说明**:
- 当需要排查远程服务器问题时，AI 代理会自动读取 `.remote-config.json` 获取服务器连接信息
- 配置文件包含：SSH host、服务器地址、容器名称等
- 详细的调试命令和排查流程参见 [远程调试文档](docs/deployment/remote-debug.md)

**安全提醒**:
- ⚠️ `.remote-config.json` 包含敏感信息，已添加到 `.gitignore`
- ⚠️ 不要在公开文档中包含真实的服务器地址、域名等信息
- ⚠️ 使用模板文件 `.remote-config.template.json` 作为公开的配置示例

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

⚠️ **【强制】PWA 全屏模式**
- iOS 必须配置 `viewport-fit=cover` 和 `apple-mobile-web-app-capable`
- 所有固定定位元素必须使用 safe-area-inset 避免被系统 UI 遮挡

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

### 4.5 时区处理规范

⚠️ **【强制】数据库时间存储**
- 数据库必须使用 UTC 时间存储（`datetime.utcnow()`）
- 禁止使用 `datetime.now()` 存储到数据库

⚠️ **【强制】A股交易时间判断**
- 交易时间判断必须使用中国时区（`Asia/Shanghai`）
- 示例：`datetime.now(ZoneInfo("Asia/Shanghai"))`
- 禁止依赖系统本地时区

⚠️ **【强制】调度器时区配置**
- APScheduler 的 CronTrigger 必须明确指定中国时区
- 示例：`CronTrigger(hour=15, minute=30, timezone=ZoneInfo("Asia/Shanghai"))`

⚠️ **【强制】API 时间返回**
- API 返回的时间字符串必须使用中国时区
- 格式：`YYYY-MM-DD HH:MM:SS`（北京时间）
- 前端统一显示中国时区时间

⚠️ **【强制】时区转换注意事项**
- 使用 `zoneinfo.ZoneInfo` 而不是 `pytz`（Python 3.9+）
- 时间比较和计算统一使用 UTC 或明确指定时区
- 避免混用本地时区和 UTC 时区

### 4.6 测试规范

⚠️ **【强制】单元测试**
- 新增业务逻辑函数必须编写单元测试
- 后端：pytest（`cd backend && pytest`）
- 前端：vitest + @testing-library/react（`cd frontend && npx vitest run`）
- 测试文件位置：`backend/tests/` 和 `frontend/__tests__/`

⚠️ **【强制】API 测试**
- 新增或修改 API 端点必须有集成测试
- 使用 pytest 和 FastAPI TestClient

⚠️ **【强制】TypeScript 编译验证**
- 所有前端开发任务在宣称完成前，必须验证 TypeScript 编译成功
- 验证命令：`cd frontend && npm run build`
- 确保没有类型错误，避免 CI/CD 构建失败
- 本地开发时的类型警告可能不会阻止 dev server 运行，但会导致生产构建失败

⚠️ **【推荐】测试覆盖率**
- 核心业务逻辑测试覆盖率应达到 80% 以上
- 使用 `pytest --cov` 检查覆盖率

### 4.7 文档维护规范

⚠️ **【强制】提交前更新文档**
- 代码变更必须同步更新相关文档，禁止"先提交代码，后补文档"
- 文档更新与代码变更必须在同一个 commit 中提交

⚠️ **【强制】文档更新检查清单**

根据变更类型，必须检查并更新以下文档：

| 变更类型 | 必须检查的文档 | 更新内容 |
|---------|---------------|---------|
| **新增/修改 API 接口** | `API_REFERENCE.md` | 更新 API 接口速查表 |
| **修改技术栈** | `AGENTS.md` 第 2 节, `README.md` | 更新技术栈列表 |
| **新增/修改配置文件** | `CODE_NAVIGATION.md` | 更新关键配置文件说明 |
| **修改核心代码路径** | `CODE_NAVIGATION.md` | 更新核心代码导航表 |
| **修改常见任务指引** | `CODE_NAVIGATION.md` | 更新任务到文件的映射关系 |
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

## 5. 代码和 API 参考 (Code & API Reference)

详细的代码路径、API 端点、配置文件等参考信息已分离到独立文档：

- **代码导航**: [CODE_NAVIGATION.md](CODE_NAVIGATION.md) - 前后端关键文件、配置文件、常见任务指引
- **API 参考**: [API_REFERENCE.md](API_REFERENCE.md) - 完整的 API 端点列表和说明

需要查找具体文件路径或 API 端点时，请查阅上述文档。

## 6. 文档导航 (Documentation)

**完整文档索引**: [docs/README.md](docs/README.md) - 包含所有文档的分类导航和查找指南

**快速链接**:
- **项目规划**: [PRD](docs/planning/PRD.md), [PLAN](docs/planning/PLAN.md)
- **部署指南**: [Docker 部署](docs/deployment/docker-guide.md), [多架构支持](docs/deployment/docker-multiarch-guide.md), [远程调试](docs/deployment/remote-debug.md)
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

---
**重要提醒**: 修改代码时务必遵守第 4 节的强制性开发规范，特别是数据一致性（QFQ）和安全规范。
