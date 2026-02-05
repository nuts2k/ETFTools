# Frontend Design Upgrade Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 ETFTool 升级为移动端优先的现代金融应用设计（参考 Apple Stocks），提升数据可读性与交互质感。

**Architecture:** 纯前端样式与组件重构。保留现有业务逻辑与数据流，仅修改 CSS (`globals.css`)、UI 组件 (`StockCard`, `ETFChart`) 和页面布局。

**Tech Stack:** Next.js, Tailwind CSS, Recharts, Lucide React.

---

### Task 1: 全局设计系统 (Global Design System)

**Files:**
- Modify: `frontend/app/globals.css`

**Step 1: 更新颜色变量**
- 修改 `--up` 为 `#f43f5e` (Rose-500)
- 修改 `--down` 为 `#10b981` (Emerald-500)
- 修改 Dark Mode 背景 `--background` 为 `#0f172a` (Slate-900)
- 增加新的辅助色变量（如需）

**Step 2: 全局排版优化**
- 在 `body` 或通用工具类中添加 `font-feature-settings: "tnum"` 确保数字等宽。
- 增加全局安全区域处理 (`pt-safe`, `pb-safe`) 的背景适配。

---

### Task 2: 首页列表组件 (Watchlist Components)

**Files:**
- Modify: `frontend/components/SortableWatchlistItem.tsx`
- Modify: `frontend/components/StockCard.tsx`

**Step 1: SortableWatchlistItem 样式重构**
- 移除边框，改为纯背景色 + 轻微阴影 (`shadow-sm`)。
- 调整布局：价格与涨跌幅垂直对齐于右侧。
- 涨跌幅样式改为胶囊形 (`bg-up/10 text-up`)。
- 添加拖拽时的“上浮”效果 (Scale 1.02)。

**Step 2: StockCard 样式统一**
- 保持与 WatchlistItem 类似的视觉风格（用于搜索结果）。
- 移除左侧通用的 LineChart 图标，改为基于代码/名称的动态占位符（如首字母圆圈）。

---

### Task 3: 首页布局优化 (Home Page Layout)

**Files:**
- Modify: `frontend/app/page.tsx`

**Step 1: 头部 (Header) 改造**
- 实现“大标题”过渡效果（或优化静态大标题）。
- 将搜索图标改为“伪搜索栏”（灰底输入框样式），点击触发搜索模式。

**Step 2: 空状态 (Empty State)**
- 替换纯文本提示为更具吸引力的视觉元素（SVG 或图标组合）。
- 优化“立即添加”引导按钮。

**Step 3: 列表容器调整**
- 增加列表项之间的间距 (`gap-3` 或 `gap-4`)。
- 确保底部导航栏不遮挡最后一行内容。

---

### Task 4: 图表组件升级 (Chart Upgrade)

**Files:**
- Modify: `frontend/components/ETFChart.tsx`

**Step 1: 视觉增强**
- 为 `AreaChart` 添加渐变填充 (`defs` linearGradient)，从主色过渡到透明。
- 调整网格线 (`CartesianGrid`) 为极淡的虚线。

**Step 2: 交互优化**
- 优化 `Tooltip`，防止手指遮挡。
- 将时间周期切换 (`1y`, `3y`...) 改为 iOS 风格的分段滑块 (Segmented Control)。

---

### Task 5: 详情页布局重构 (Detail Page Layout)

**Files:**
- Modify: `frontend/app/etf/[code]/page.tsx`

**Step 1: Hero 区域**
- 极大号显示当前价格。
- 将“沪/深”和“交易状态”作为高对比度标签（Badge）放置。

**Step 2: 核心指标卡片**
- 重新设计 Grid 布局，不再平均分布。
- 突出“总收益”和“CAGR”。
- 尝试在卡片内添加简单的视觉元素（如进度条表示回撤深度）。

**Step 3: 底部操作栏 (Floating Bar)**
- 移除底部静态导航链接（详情页不需要底栏导航）。
- 将“加入/移除自选”设计为悬浮且带有玻璃拟态 (`backdrop-blur`) 的操作条。

---

### Task 6: 搜索体验 (Search Experience)

**Files:**
- Modify: `frontend/app/page.tsx` (搜索模式逻辑)

**Step 1: 转场动画**
- 优化搜索模式打开时的动画（Shared Element 感觉的展开）。

**Step 2: 结果高亮**
- 在搜索结果中高亮匹配的字符（如输入 "300" 时高亮显示）。
