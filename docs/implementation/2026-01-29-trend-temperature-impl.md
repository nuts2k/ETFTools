# 趋势与投资温度指标 - 执行计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 ETFTool 实现周趋势、日趋势、综合投资温度三个核心指标，包含完整的后端服务、API 扩展和前端展示

**Architecture:** 新增 trend_service 和 temperature_service 两个独立服务，通过 metrics_config.json 配置参数，扩展 /etf/{code}/metrics API，前端首页卡片和详情页同步更新

**Tech Stack:** Python 3.9+, FastAPI, Pandas, NumPy, pytest | Next.js 16, TypeScript, Tailwind CSS

**Design Doc:** `docs/plans/2026-01-29-trend-temperature-design.md`

---

## 代码探索摘要

### 后端关键文件

| 文件 | 行号 | 说明 |
|------|------|------|
| `backend/app/data/metrics_config.json` | 1-4 | 当前仅有 `drawdown_days` 和 `atr_period` |
| `backend/app/core/config_loader.py` | 8-56 | 单例模式配置加载器，支持热加载 |
| `backend/app/services/metrics_service.py` | 1-99 | 现有指标服务，可参考其缓存模式 |
| `backend/app/api/v1/endpoints/etf.py` | 79-308 | `/metrics` 端点，需在此集成新服务 |
| `backend/app/services/akshare_service.py` | 206-240 | 历史数据获取方式 |

### 前端关键文件

| 文件 | 行号 | 说明 |
|------|------|------|
| `frontend/lib/api.ts` | 71-90 | `ETFMetrics` 类型定义，需扩展 |
| `frontend/lib/api.ts` | 36-44 | `ETFItem` 类型定义，需扩展 |
| `frontend/components/SortableWatchlistItem.tsx` | 63-83 | 首页卡片指标行，需添加新指标 |
| `frontend/app/etf/[code]/page.tsx` | 236-307 | 详情页指标网格，需添加趋势卡片 |
| `frontend/app/etf/[code]/page.tsx` | 313-336 | `MetricCard` 组件定义 |

### 测试现状

项目当前**无测试文件**，需创建 `backend/tests/` 目录结构。

---

## Phase 1: 测试基础设施搭建

### Task 1.1: 创建 pytest 目录结构和配置

**Files:**
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/services/__init__.py`

**Steps:**
1. 创建 `backend/tests/` 和 `backend/tests/services/` 目录
2. 在 `conftest.py` 中创建共享 fixtures：
   - `sample_daily_data`: 120 天模拟日线数据（含 OHLCV）
   - `sample_long_history`: 10 年模拟历史数据（用于分位计算）
   - `bullish_trend_data`: 多头排列测试数据
   - `bearish_trend_data`: 空头排列测试数据
3. 运行 `pytest --collect-only` 验证配置正确

**Commit:** `test: add pytest infrastructure and shared fixtures`

---

## Phase 2: 配置文件扩展

### Task 2.1: 扩展 metrics_config.json

**Files:**
- Modify: `backend/app/data/metrics_config.json`

**Steps:**
1. 添加 `trend` 配置块（daily_ma_periods, weekly_ma_periods）
2. 添加 `temperature` 配置块（percentile_years, rsi_period, weights）
3. 验证 JSON 格式正确

**Commit:** `config: add trend and temperature settings`

---

### Task 2.2: 扩展 config_loader.py

**Files:**
- Modify: `backend/app/core/config_loader.py:43-54`

**Steps:**
1. 添加 `trend_config` 属性（返回 trend 配置块）
2. 添加 `temperature_config` 属性（返回 temperature 配置块）
3. 添加便捷属性：`daily_ma_periods`, `weekly_ma_periods`, `rsi_period`, `percentile_years`, `temperature_weights`
4. 手动测试热加载功能

**Commit:** `feat(config): add trend and temperature config accessors`

---

## Phase 3: 趋势服务 (trend_service)

### Task 3.1: 创建趋势服务测试文件

**Files:**
- Create: `backend/tests/services/test_trend_service.py`

**Steps:**
1. 编写 `test_calculate_ma_values` - 验证均线计算正确性
2. 编写 `test_determine_position_above` - 价格在均线上方
3. 编写 `test_determine_position_below` - 价格在均线下方
4. 编写 `test_determine_position_crossing_up` - 向上突破检测
5. 编写 `test_determine_position_crossing_down` - 向下破位检测
6. 编写 `test_ma_alignment_bullish` - 多头排列判断
7. 编写 `test_ma_alignment_bearish` - 空头排列判断
8. 编写 `test_weekly_resample` - 周线重采样正确性
9. 编写 `test_consecutive_weeks_up` - 连涨周数统计
10. 编写 `test_consecutive_weeks_down` - 连跌周数统计
11. 运行测试确认全部失败（TDD 红灯阶段）

**Commit:** `test: add trend_service test cases`

---

### Task 3.2: 实现趋势服务

**Files:**
- Create: `backend/app/services/trend_service.py`

**Steps:**
1. 创建 `TrendService` 类
2. 实现 `_calculate_ma(df, period)` - 计算单条均线
3. 实现 `_determine_position(price, ma_today, price_yesterday, ma_yesterday)` - 判断位置关系
4. 实现 `_determine_alignment(ma_values)` - 判断均线排列
5. 实现 `_find_latest_signal(daily_trend)` - 提取最重要的突破信号
6. 实现 `get_daily_trend(df)` - 日趋势主函数
7. 实现 `_resample_to_weekly(df)` - 日线转周线
8. 实现 `_count_consecutive_weeks(weekly_df)` - 统计连续周数
9. 实现 `_get_weekly_ma_status(weekly_df)` - 周均线排列状态
10. 实现 `get_weekly_trend(df)` - 周趋势主函数
11. 创建全局单例 `trend_service`
12. 运行测试确认全部通过（TDD 绿灯阶段）

**Commit:** `feat: implement trend_service with daily and weekly trend calculation`

---

## Phase 4: 温度服务 (temperature_service)

### Task 4.1: 创建温度服务测试文件

**Files:**
- Create: `backend/tests/services/test_temperature_service.py`

**Steps:**
1. 编写 `test_calculate_rsi_wilder` - Wilder EMA RSI 算法验证
2. 编写 `test_rsi_overbought` - RSI > 70 超买状态
3. 编写 `test_rsi_oversold` - RSI < 30 超卖状态
4. 编写 `test_drawdown_score_at_peak` - 新高时得分 100
5. 编写 `test_drawdown_score_at_30pct` - -30% 回撤得分 0
6. 编写 `test_percentile_calculation` - 历史分位计算
7. 编写 `test_percentile_with_short_history` - 不足 10 年数据处理
8. 编写 `test_volatility_score` - 波动率分位得分
9. 编写 `test_trend_score_bullish` - 多头趋势得分 80
10. 编写 `test_trend_score_bearish` - 空头趋势得分 20
11. 编写 `test_temperature_weighted_sum` - 加权总分计算
12. 编写 `test_temperature_level_freezing` - 0-30 冰点等级
13. 编写 `test_temperature_level_hot` - 71-100 过热等级
14. 运行测试确认全部失败

**Commit:** `test: add temperature_service test cases`

---

### Task 4.2: 实现温度服务

**Files:**
- Create: `backend/app/services/temperature_service.py`

**Steps:**
1. 创建 `TemperatureService` 类
2. 实现 `_calculate_rsi_wilder(df, period)` - Wilder EMA RSI
3. 实现 `_calculate_drawdown_score(current_drawdown)` - 回撤得分映射
4. 实现 `_calculate_percentile(df, years)` - 历史分位计算
5. 实现 `_calculate_volatility_score(df)` - 波动率分位得分
6. 实现 `_calculate_trend_score(ma_alignment)` - 趋势强度得分
7. 实现 `_determine_level(score)` - 温度等级判断
8. 实现 `get_temperature(df, current_drawdown, ma_alignment)` - 温度主函数
9. 创建全局单例 `temperature_service`
10. 运行测试确认全部通过

**Commit:** `feat: implement temperature_service with 5-factor weighted scoring`

---

## Phase 5: API 集成

### Task 5.1: 扩展 /metrics 端点

**Files:**
- Modify: `backend/app/api/v1/endpoints/etf.py:79-308`

**Steps:**
1. 导入 `trend_service` 和 `temperature_service`
2. 在 `get_etf_metrics` 函数中调用 `trend_service.get_daily_trend(df)`
3. 调用 `trend_service.get_weekly_trend(df)`
4. 调用 `temperature_service.get_temperature(df, current_drawdown, ma_alignment)`
5. 将新字段添加到响应字典
6. 手动测试 API 响应格式

**Commit:** `feat(api): integrate trend and temperature into /metrics endpoint`

---

### Task 5.2: 添加 API 集成测试

**Files:**
- Create: `backend/tests/api/test_etf_metrics.py`

**Steps:**
1. 创建 `backend/tests/api/__init__.py`
2. 编写 `test_metrics_response_contains_weekly_trend`
3. 编写 `test_metrics_response_contains_daily_trend`
4. 编写 `test_metrics_response_contains_temperature`
5. 运行完整测试套件

**Commit:** `test: add API integration tests for new metrics fields`

---

## Phase 6: 前端类型定义

### Task 6.1: 扩展 TypeScript 类型

**Files:**
- Modify: `frontend/lib/api.ts:71-90`

**Steps:**
1. 添加 `WeeklyTrend` 接口定义
2. 添加 `DailyTrend` 接口定义
3. 添加 `Temperature` 接口定义
4. 扩展 `ETFMetrics` 接口，添加 `weekly_trend`, `daily_trend`, `temperature` 字段
5. 扩展 `ETFItem` 接口，添加首页展示所需的摘要字段
6. 运行 `npm run build` 验证类型正确

**Commit:** `feat(types): add trend and temperature type definitions`

---

## Phase 7: 首页卡片更新

### Task 7.1: 更新 SortableWatchlistItem 组件

**Files:**
- Modify: `frontend/components/SortableWatchlistItem.tsx:63-83`

**Steps:**
1. 创建 `TrendIndicator` 辅助组件（显示周趋势箭头和文字）
2. 创建 `SignalBadge` 辅助组件（显示均线突破信号）
3. 创建 `TemperatureIndicator` 辅助组件（显示温度图标和数值）
4. 修改指标行布局，替换或补充现有 ATR/回撤显示
5. 处理数据加载中和无数据状态
6. 测试不同屏幕宽度下的显示效果

**Commit:** `feat(ui): add trend and temperature indicators to watchlist cards`

---

## Phase 8: 详情页趋势分析卡片

### Task 8.1: 创建 TrendAnalysisCard 组件

**Files:**
- Create: `frontend/components/TrendAnalysisCard.tsx`

**Steps:**
1. 创建组件骨架，接收 `weeklyTrend`, `dailyTrend`, `temperature` props
2. 实现周趋势区块（方向箭头 + 连续周数 + 周均线状态）
3. 实现日均线状态区块（三线位置指示器 + 数值 + 排列状态）
4. 实现温度计可视化（进度条 + 等级文字 + 分数）
5. 实现因子明细折叠区（5 个因子的得分和说明）
6. 添加加载状态骨架屏
7. 样式适配移动端

**Commit:** `feat(ui): create TrendAnalysisCard component`

---

### Task 8.2: 集成到详情页

**Files:**
- Modify: `frontend/app/etf/[code]/page.tsx:225-234`

**Steps:**
1. 导入 `TrendAnalysisCard` 组件
2. 在估值卡片下方（或替代位置）添加趋势分析卡片
3. 传递 metrics 数据中的新字段
4. 调整页面布局间距
5. 测试完整页面渲染

**Commit:** `feat(ui): integrate TrendAnalysisCard into ETF detail page`

---

## Phase 9: 集成测试与验收

### Task 9.1: 端到端验证

**Steps:**
1. 启动后端服务：`./manage.sh start`
2. 使用 curl 测试 `/api/v1/etf/510300/metrics` 响应格式
3. 验证新字段存在且数值合理
4. 访问前端首页，检查卡片指标显示
5. 访问详情页，检查趋势分析卡片
6. 测试不同 ETF（新上市 vs 老牌 ETF）的数据差异处理

**Commit:** N/A (验证步骤)

---

### Task 9.2: 代码清理和文档

**Steps:**
1. 运行 `ruff check backend/` 检查代码风格
2. 运行 `npm run lint` 检查前端代码
3. 更新 `AGENTS.md` 中的 API 接口速查表
4. 确认所有测试通过：`pytest backend/tests/ -v`

**Commit:** `chore: code cleanup and documentation update`

---

## 文件变更清单

### 后端新建文件
| 文件 | 说明 |
|------|------|
| `backend/tests/__init__.py` | 测试包初始化 |
| `backend/tests/conftest.py` | pytest 共享 fixtures |
| `backend/tests/services/__init__.py` | 服务测试包初始化 |
| `backend/tests/services/test_trend_service.py` | 趋势服务测试 |
| `backend/tests/services/test_temperature_service.py` | 温度服务测试 |
| `backend/tests/api/__init__.py` | API 测试包初始化 |
| `backend/tests/api/test_etf_metrics.py` | API 集成测试 |
| `backend/app/services/trend_service.py` | 趋势计算服务 |
| `backend/app/services/temperature_service.py` | 温度计算服务 |

### 后端修改文件
| 文件 | 修改内容 |
|------|----------|
| `backend/app/data/metrics_config.json` | 新增 trend 和 temperature 配置块 |
| `backend/app/core/config_loader.py` | 新增配置属性访问器 |
| `backend/app/api/v1/endpoints/etf.py` | 集成新服务，扩展返回字段 |

### 前端新建文件
| 文件 | 说明 |
|------|------|
| `frontend/components/TrendAnalysisCard.tsx` | 趋势分析卡片组件 |

### 前端修改文件
| 文件 | 修改内容 |
|------|----------|
| `frontend/lib/api.ts` | 扩展类型定义 |
| `frontend/components/SortableWatchlistItem.tsx` | 添加趋势/温度指标 |
| `frontend/app/etf/[code]/page.tsx` | 集成趋势分析卡片 |

---

## 依赖关系图

```
Phase 1 (测试基础) 
    ↓
Phase 2 (配置扩展)
    ↓
Phase 3 (趋势服务) ──┐
    ↓               │
Phase 4 (温度服务) ←─┘ (温度依赖趋势的 ma_alignment)
    ↓
Phase 5 (API 集成)
    ↓
Phase 6 (前端类型)
    ↓
Phase 7 (首页卡片) ──┐
    ↓               │
Phase 8 (详情页) ←───┘ (可并行)
    ↓
Phase 9 (验收)
```

---

## 风险与注意事项

1. **数据不足处理**: ETF 上市不足 60 天时，MA60 无法计算，需返回 null 并在前端优雅降级
2. **周线边界**: 周线重采样需注意节假日导致的不完整周，建议使用 `closed='right'` 参数
3. **RSI 冷启动**: RSI 计算需要至少 `period + 1` 天数据，不足时返回 null
4. **性能考虑**: 温度计算涉及 10 年历史数据，考虑在 metrics_service 中复用缓存的历史数据
5. **前端兼容**: 新字段可能为 null，所有前端展示需做空值检查
