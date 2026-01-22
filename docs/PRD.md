# ETFTool (A股版) - 产品需求文档

## 1. 产品概述 (Product Overview)
*   **产品名称**: ETFTool
*   **目标用户**: 关注 A 股 ETF 的个人投资者。
*   **平台**: Web 应用 (FastAPI + Next.js)，移动端优先。
*   **核心价值**: 基于**前复权 (QFQ)** 数据进行专业分析，通过还原真实收益，帮助投资者理性评估 ETF 的长期表现与风险。

## 2. 技术架构 (Technical Architecture)

### 2.1 后端 (Backend)
*   **框架**: FastAPI (Python 3.9+)
*   **数据源**: AkShare
    *   **历史数据**: `ak.fund_etf_hist_em(adjust="qfq")` (东方财富源，前复权)
    *   **实时信息**: `ak.fund_etf_spot_em()` (用于获取名称和实时价格)
*   **数据处理**: Pandas (时间序列分析)
*   **缓存**: 内存缓存 (In-Memory LRU) - MVP 阶段使用。

### 2.2 前端 (Frontend)
*   **框架**: Next.js 14+ (App Router)
*   **语言**: TypeScript
*   **UI 组件库**: Shadcn/UI + Tailwind CSS
*   **图表库**: Recharts (响应式设计，触摸友好)

## 3. 功能需求 (Functional Requirements) - MVP

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

## 4. API 设计草案 (API Design Draft)
*   `GET /api/v1/etf/search?q={keyword}` -> `[{code, name, price, change_pct}, ...]` (搜索)
*   `GET /api/v1/etf/{code}/info` -> `{name, price, change_pct, update_time, market}` (详情头信息)
*   `GET /api/v1/etf/{code}/history?period=5y` -> `[{date, close}, ...]` (图表数据)
*   `GET /api/v1/etf/{code}/metrics?period=5y` -> `{cagr, mdd, volatility, total_return, risk_level, mdd_date}` (核心指标)
*   *(注: 自选列表建议 MVP 阶段存储在客户端 LocalStorage，暂不需要后端存储 API)*

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
