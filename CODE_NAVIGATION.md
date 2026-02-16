# 代码导航

本文档提供 ETFTools 项目的详细代码路径参考、配置文件说明和常见任务指引。

## 1. 后端代码导航

### 1.1 应用核心

| 功能模块 | 文件路径 | 说明 |
|---------|---------|------|
| **应用入口** | `backend/app/main.py` | CORS 配置、生命周期管理 |
| **核心配置** | `backend/app/core/config.py` | 环境变量、SECRET_KEY |
| **日志配置** | `backend/app/core/logging_config.py` | 集中日志格式和输出配置 |
| **数据源指标** | `backend/app/core/metrics.py` | 数据源成功率、延迟追踪 |
| **数据库** | `backend/app/core/database.py` | SQLite 连接和会话管理 |
| **缓存管理** | `backend/app/core/cache.py` | DiskCache 配置 |
| **份额历史数据库** | `backend/app/core/share_history_database.py` | 独立 SQLite 数据库配置 |

### 1.2 API 端点

| 功能模块 | 文件路径 | 说明 |
|---------|---------|------|
| **ETF 接口** | `backend/app/api/v1/endpoints/etf.py` | 搜索、行情、历史、指标计算 |
| **自选管理** | `backend/app/api/v1/endpoints/watchlist.py` | 云端同步逻辑 |
| **用户认证** | `backend/app/api/v1/endpoints/auth.py` | 注册、登录、JWT |
| **管理员端点** | `backend/app/api/v1/endpoints/admin.py` | 用户管理、系统配置 |
| **对比端点** | `backend/app/api/v1/endpoints/compare.py` | ETF 对比 API |

### 1.3 服务层

| 功能模块 | 文件路径 | 说明 |
|---------|---------|------|
| **系统配置服务** | `backend/app/services/system_config_service.py` | 全局配置服务 |
| **数据源** | `backend/app/services/akshare_service.py` | AkShare 接口封装、缓存降级 |
| **指标计算** | `backend/app/services/metrics_service.py` | ATR, 回撤, CAGR 算法 |
| **估值服务** | `backend/app/services/valuation_service.py` | PE 分位数（可选） |
| **分类器服务** | `backend/app/services/etf_classifier.py` | ETF 自动分类标签生成 |
| **资金流向采集** | `backend/app/services/fund_flow_collector.py` | 份额数据采集 + APScheduler 调度 |
| **资金流向服务** | `backend/app/services/fund_flow_service.py` | 份额规模、排名业务逻辑 |
| **资金流向缓存** | `backend/app/services/fund_flow_cache_service.py` | 资金流向数据缓存（4h TTL） |
| **份额备份服务** | `backend/app/services/share_history_backup_service.py` | CSV 导出和月度备份 |
| **对比服务** | `backend/app/services/compare_service.py` | 归一化、相关性、降采样计算 |
| **管理员告警** | `backend/app/services/admin_alert_service.py` | 数据源故障 Telegram 告警广播 |

### 1.4 数据模型

| 功能模块 | 文件路径 | 说明 |
|---------|---------|------|
| **份额历史模型** | `backend/app/models/etf_share_history.py` | ETF 份额历史数据模型 |

### 1.5 静态配置

| 功能模块 | 文件路径 | 说明 |
|---------|---------|------|
| **静态配置** | `backend/app/data/metrics_config.json` | 动态指标参数 |

## 2. 前端代码导航

### 2.1 页面

| 功能模块 | 文件路径 | 说明 |
|---------|---------|------|
| **首页** | `frontend/app/page.tsx` | 自选列表、拖拽排序、下拉刷新 |
| **搜索页** | `frontend/app/search/page.tsx` | 模糊搜索、防抖 |
| **详情页** | `frontend/app/etf/[code]/page.tsx` | 图表、指标卡片 |
| **对比页** | `frontend/app/compare/page.tsx` | ETF 对比（选择器+图表+指标） |
| **设置页** | `frontend/app/settings/page.tsx` | 主题、刷新频率 |
| **登录/注册** | `frontend/app/login/`, `frontend/app/register/` | 认证页面 |

### 2.2 组件

| 功能模块 | 文件路径 | 说明 |
|---------|---------|------|
| **图表组件** | `frontend/components/ETFChart.tsx` | Recharts 配置、交互 |
| **下拉刷新指示器** | `frontend/components/PullToRefreshIndicator.tsx` | 下拉视觉反馈 |
| **资金流向卡片** | `frontend/components/FundFlowCard.tsx` | 份额规模、排名展示 |

### 2.3 Hooks 和上下文

| 功能模块 | 文件路径 | 说明 |
|---------|---------|------|
| **自选逻辑** | `frontend/hooks/use-watchlist.ts` | 本地存储、云端同步 |
| **下拉刷新 Hook** | `frontend/hooks/use-pull-to-refresh.ts` | 触摸手势状态机 |
| **认证上下文** | `frontend/contexts/AuthContext.tsx` | JWT 管理 |

### 2.4 PWA 配置

| 功能模块 | 文件路径 | 说明 |
|---------|---------|------|
| **PWA 配置** | `frontend/public/manifest.json` | PWA 清单、图标、主屏幕安装 |

## 3. 关键配置文件

| 配置文件 | 位置 | 说明 |
|---------|------|------|
| **环境配置** | `backend/.env` | SECRET_KEY, CORS, 速率限制 |
| **动态指标** | `backend/app/data/metrics_config.json` | `drawdown_days`, `atr_period` (无需重启) |
| **ETF 映射** | `backend/app/data/etf_index_map.json` | ETF 到指数的映射表（估值功能） |
| **降级数据** | `backend/app/data/etf_fallback.json` | 接口失败时的备用数据 |
| **版本提取** | `scripts/get_version.sh` | 从 Git 标签提取版本号 |
| **版本升级** | `scripts/bump_version.sh` | 语义化版本升级脚本 |
| **PWA 清单** | `frontend/public/manifest.json` | PWA 名称、图标、显示模式、主题色 |
| **份额历史数据库** | `backend/etf_share_history.db` | 独立 SQLite 数据库（份额历史） |
| **份额备份目录** | `backend/backups/share_history/` | 月度 CSV 备份文件 |

**版本管理环境变量**：
- `APP_VERSION`: 后端应用版本（自动从 Git 标签提取，默认 `dev`）
- `NEXT_PUBLIC_APP_VERSION`: 前端应用版本（构建时注入）

**估值分位功能开关**：
- 默认关闭，节省 API 资源
- 开启方法：在 `backend/app/api/v1/endpoints/etf.py:get_etf_metrics` 中取消 `valuation_service.get_valuation(code)` 的注释

## 4. 常见任务快速指引

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

**最后更新**: 2026-02-16
