# 开发计划 (Development Plan)

## Phase 1: 后端核心 (Backend Core)
- [ ] **数据源服务**: 封装 `akshare` 调用，确保获取前复权 (QFQ) 数据。
- [ ] **缓存机制**: 实现内存缓存 (In-memory Cache)，用于 ETF 基础列表（启动时预加载）和高频行情数据。
- [ ] **API - 搜索**: 实现 `GET /api/v1/etf/search`，基于预加载的内存列表进行模糊匹配。
- [ ] **API - 详情**: 实现 `GET /api/v1/etf/{code}/info`，返回实时价格与基础信息。
- [ ] **API - 历史**: 实现 `GET /api/v1/etf/{code}/history`，核心逻辑：**拼接**“历史 QFQ 收盘价”与“当前实时价”。
- [ ] **API - 指标**: 实现 `GET /api/v1/etf/{code}/metrics`，后端计算年化收益 (CAGR)、最大回撤 (MDD) 和波动率。

## Phase 2: 前端基础与搜索 (Frontend Basis & Search)
- [ ] **API Client**: 封装统一的 HTTP 请求库 (fetch/axios)，处理 baseUrl 和错误拦截。
- [ ] **布局 (Layout)**: 实现移动端风格的底部导航栏 (Bottom Tab Bar)。
- [ ] **搜索页 (Search Tab)**:
    - [ ] 搜索输入框 (防抖)。
    - [ ] 结果列表组件 (支持“添加自选”操作)。
    - [ ] 骨架屏 (Skeleton) 加载状态。

## Phase 3: 自选与详情 (Watchlist & Detail)
- [ ] **自选页 (Watchlist Tab)**:
    - [ ] 基于 `localStorage` 的状态管理 (Zustand 或 Context)。
    - [ ] 自选列表展示 (红涨绿跌)。
- [ ] **详情页 (Detail Tab)**:
    - [ ] **头部**: 实时价格大字展示，动态刷新。
    - [ ] **图表**: 集成 Recharts，实现 1Y/3Y/5Y/All 时间切换，移动端 Tooltip 适配。
    - [ ] **指标**: 展示后端计算的风险收益指标。

## Phase 4: 设置与优化 (Settings & Polish)
- [ ] **设置页**: 涨跌色切换 (红/绿配置)，缓存清理界面。
- [ ] **UI/UX 细节**: 
    - [ ] 增加 Loading 动画。
    - [ ] 异常处理 (网络错误提示)。
    - [ ] 移动端触摸体验优化。
- [ ] **构建检查**: 运行 Lint 和 Type Check，确保无报错。
