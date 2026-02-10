# ETFTool (A股版) - 产品需求文档

## 1. 产品概述 (Product Overview)
*   **产品名称**: ETFTool
*   **目标用户**: 关注 A 股 ETF 的个人投资者。
*   **平台**: Web 应用 (FastAPI + Next.js)，移动端优先。
*   **核心价值**: 基于**前复权 (QFQ)** 数据进行专业分析，通过还原真实收益，帮助投资者理性评估 ETF 的长期表现与风险。

## 2. 技术架构 (Technical Architecture)

### 2.1 后端 (Backend)
*   **框架**: FastAPI (Python 3.9+)
*   **数据库**: SQLite (配合 SQLModel)。轻量级文件数据库，用于存储用户数据、配置和自选列表。
*   **认证**: OAuth2 Password Flow + JWT (JSON Web Tokens)。
*   **数据源**: AkShare
    *   **历史数据**: `ak.fund_etf_hist_em(adjust="qfq")` (东方财富源，前复权)
    *   **实时信息**: `ak.fund_etf_spot_em()` (用于获取名称和实时价格)
*   **数据处理**: Pandas (时间序列分析)
*   **缓存**: **DiskCache** (基于文件的持久化缓存)。替代原有的内存缓存，确保历史数据和计算结果在服务重启后不丢失，提升启动速度。

### 2.2 前端 (Frontend)
*   **框架**: Next.js 14+ (App Router)
*   **语言**: TypeScript
*   **UI 组件库**: Shadcn/UI + Tailwind CSS
*   **图表库**: Recharts (响应式设计，触摸友好)
*   **状态管理**: React Context (用于管理 Auth 用户登录状态)。

## 3. 功能需求 (Functional Requirements)

基于设计稿 (Design Files) 的界面结构，APP 分为三个主要模块：搜索、自选、设置。

### 3.1 导航结构 (Navigation)
*   **底部导航栏 (Bottom Tab Bar)**:
    1.  **搜索 (Search)**: 首页，用于查找 ETF 并查看详情。
    2.  **自选 (Watchlist)**: 展示用户关注的 ETF 列表。
    3.  **设置 (Settings)**: 应用偏好设置与数据管理。

### 3.2 搜索页 (Search Tab)
*   **搜索功能**:
    *   顶部搜索框，支持输入 **6 位代码** 或 **名称关键字** (如 "沪深300", "半导体")。
    *   空状态提示: "尝试搜索 '沪深300' 或 '半导体'"。
*   **搜索结果列表**:
    *   展示匹配的 ETF 卡片。
    *   **卡片内容**: ETF 名称、代码 (带市场标识如 SH/SZ)、最新价格 (Price)、当日涨跌幅 (Change %)。
    *   **操作**: 每行提供 "加入自选" (Add) 按钮。
    *   **标签**: 列表顶部需标注 "数据已前复权 (QFQ)"。

### 3.3 自选页 (Watchlist Tab)
*   **自选列表**:
    *   展示用户已收藏的 ETF。
    *   **卡片展示**: 与搜索结果类似，强调最新价和涨跌幅。
    *   **颜色编码**: 涨(红)、跌(绿)、平(灰) (需支持在设置中切换红/绿习惯，默认红涨绿跌)。
    *   **交互**: 点击卡片进入 **详情页**。

### 3.4 详情页 (Detail Page)
*   **头部信息**:
    *   返回按钮、代码/名称。
    *   **实时行情**: 大号字体显示最新价，动态涨跌幅 (百分比 & 绝对值)，交易状态 (如 "已收盘", "交易中")。
*   **历史走势图 (Historical Chart)**
    *   **可视化**: 交互式折线图 (十字光标显示具体日期和价格)。
    *   **数据口径**: **前复权收盘价 (Adjusted Close, QFQ)** (需在图表显著位置标注)。
    *   **时间维度**: 1年 (1Y), 3年 (3Y), **5年 (5Y, 默认)**, 全部 (All)。
    *   **Y 轴**: 绝对价格 (CNY)。
*   **核心指标 (Key Metrics)**
    *   **区间总收益 (Total Return)**: 显示收益率，以及 "相对指数" 表现 (可选)。
    *   **年化收益率 (CAGR)**: 几何平均年增长率。
    *   **最大回撤 (Max Drawdown)**: 显示回撤比例及发生的具体月份 (如 "2022年10月")。
    *   **波动率 (Volatility)**: 显示数值及风险等级评估 (如 "高/中/低")。
*   **底部操作栏**:
    *   **加入/移除自选**: 悬浮或底部固定的操作按钮，状态需实时同步。

### 3.5 设置页 (Settings Tab)
*   **通用设置**:
    *   **行情刷新频率**: 提供选项 (如 5秒, 10秒, 手动)，默认 5秒。
    *   **涨跌颜色**: 支持 "红涨绿跌" (默认) 或 "绿涨红跌" (国际/加密货币习惯)。
    *   **主题模式**: 浅色 (Light) / 深色 (Dark) / 跟随系统。
*   **数据与存储**:
    *   **清除缓存**: 显示当前缓存占用大小 (如 "24.5 MB")，提供清除按钮。

### 3.6 用户系统 (User System)
*   **注册与登录**:
    *   支持用户名/密码注册。
    *   **可选登录模式**: 用户不登录即可使用搜索、查看行情和本地自选股功能（数据存在 LocalStorage）。
    *   登录后解锁数据云端同步功能。
*   **数据同步策略**:
    *   **自选股同步**: 用户登录时，自动将本地自选股上传并与云端列表合并。之后以云端数据为准。
    *   **设置同步**: 用户偏好（如红涨绿跌、刷新频率、主题色）登录后自动同步到云端。
*   **个人中心**:
    *   展示用户名。
    *   提供"退出登录"按钮（退出后清除本地 Token，但不清除本地缓存的数据，保持可用性）。

### 3.7 ETF 分类与筛选 (ETF Classification & Filtering)
*   **自动分类标签**:
    *   系统基于 ETF 名称自动识别分类标签，采用**统一标签列表模型**（每个标签携带 `group` 元数据：type/industry/strategy/special）。
    *   **标签展示**: 在搜索结果、详情页、自选列表的卡片中展示 ETF 标签（最多 **2 个**），详情页可展示完整标签列表。
    *   **标签示例**: [宽基]、[半导体]、[医药]、[红利]、[跨境]、[LOF] 等。
*   **分类筛选**:
    *   **搜索页筛选**: 提供标签筛选器，支持按统一标签（`?tags=半导体,医药`）筛选 ETF。
    *   **多选逻辑**: 默认 **OR 逻辑**（更符合用户直觉，如"我想看半导体或医药"）。
    *   **快速清空**: 提供清空按钮，快速重置筛选条件。
*   **分类浏览**:
    *   **首页入口**: 在首页提供"热门分类"横向滚动标签，点击跳转到对应分类的 ETF 列表。
    *   **热门分类**: 半导体、医药、新能源、红利、券商、消费等（6-8 个）。
*   **同类推荐**:
    *   **详情页推荐**: 在 ETF 详情页展示"同类 ETF 对比"模块，推荐 3-5 个同类 ETF。
    *   **推荐算法**: 基于标签相似度计算，优先推荐同行业、不同基金公司的 ETF。
*   **自选分组**:
    *   **自动分组**: 自选列表支持按系统标签自动分组查看（如"宽基"、"科技"、"医药"等）。
    *   **分组切换**: 提供分组标签切换视图，显示各分组的 ETF 数量。
    *   **用户分组**: 未来支持用户自定义分组（如"核心持仓"、"观察中"等）。

## 4. API 设计草案 (API Design Draft)

### 基础数据 (ETF Data)
*   `GET /api/v1/etf/search?q={keyword}` -> `[{code, name, price, change_pct, tags: {...}}, ...]` (搜索，包含标签)
*   `GET /api/v1/etf/{code}/info` -> `{name, price, change_pct, update_time, market, tags: {...}}` (详情头信息，包含标签)
*   `GET /api/v1/etf/{code}/history?period=5y` -> `[{date, close}, ...]` (图表数据)
*   `GET /api/v1/etf/{code}/metrics?period=5y` -> `{cagr, mdd, volatility, total_return, risk_level, mdd_date}` (核心指标)

### 分类标签 (Classification Tags)
*   `GET /api/v1/etf/tags` -> `{groups: {type: [...], industry: [...], strategy: [...], special: [...]}}` (获取所有可用标签，按 group 分组)
*   `GET /api/v1/etf/search-by-tags?tags=半导体,医药` -> `{items: [{code, name, price, tags}, ...], total: N}` (按统一标签筛选，默认 OR 逻辑)
*   `GET /api/v1/etf/{code}/similar?limit=5` -> `{items: [{code, name, price, similarity_score, common_tags, tags}, ...]}` (同类推荐)

### 认证与用户 (Auth & User)
*   `POST /api/v1/auth/register` -> `{"msg": "User created"}`
    *   Body: `username`, `password`
*   `POST /api/v1/auth/token` -> `{"access_token": "...", "token_type": "bearer"}`
    *   Body: OAuth2 Form Data (`username`, `password`)
*   `GET /api/v1/users/me` -> `{username, settings: {theme, color_mode...}}`
*   `PATCH /api/v1/users/me/settings` -> Update settings JSON.

### 自选股 (Watchlist)
*   `GET /api/v1/watchlist` -> `[{code, name, price, ...}, ...]`
    *   获取当前用户的云端自选列表。
*   `POST /api/v1/watchlist/{code}` -> Add to watchlist.
*   `DELETE /api/v1/watchlist/{code}` -> Remove from watchlist.
*   `POST /api/v1/watchlist/sync` -> `{"synced_count": 5}`
    *   前端将本地代码列表上传，后端执行“并集”操作。

## 5. UI/UX 设计原则
*   **移动优先 (Mobile First)**: 采用纵向布局，底部导航，适合单手操作。
*   **视觉风格**: 极简、专业。
    *   **字体**: Inter (数字/英文), Noto Sans SC (中文)。
    *   **颜色**: 
        *   Primary: `#1269e2` (蓝色)
        *   Up: `#ef4444` (红)
        *   Down: `#22c55e` (绿)
        *   Background: `#f6f7f8` (Light) / `#101822` (Dark)
*   **交互反馈**: 按钮点击态 (Active scale)，加载骨架屏。
*   **免责声明**: 全局强调“价格已按前复权 (QFQ) 处理”。
