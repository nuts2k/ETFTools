# 指标缓存优化 - 执行计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为趋势和温度指标实现增量计算和缓存机制，减少重复计算开销

**Architecture:** 新建 `trend_cache_service` 和 `temperature_cache_service` 两个缓存服务层，包装现有的纯计算服务。使用 DiskCache 存储中间状态，通过日期判断实现增量更新，盘中数据不写入缓存。

**Tech Stack:** Python 3.9+, DiskCache, Pandas, pytest

**Design Doc:** `docs/plans/2026-01-29-metrics-cache-design.md`

---

## 代码探索摘要

### 关键文件

| 文件 | 说明 |
|------|------|
| `backend/app/services/trend_service.py` | 现有趋势计算服务（纯计算） |
| `backend/app/services/temperature_service.py` | 现有温度计算服务（纯计算） |
| `backend/app/services/akshare_service.py:36` | DiskCache 实例 `disk_cache` |
| `backend/app/services/metrics_service.py` | 参考：现有缓存模式 |
| `backend/app/api/v1/endpoints/etf.py:291-302` | 当前调用位置，需修改 |
| `backend/tests/conftest.py` | 测试 fixtures |

### DiskCache 使用模式

```python
from app.services.akshare_service import disk_cache

# 读取
cached = disk_cache.get(cache_key)

# 写入（无过期）
disk_cache.set(cache_key, data)

# 写入（带过期）
disk_cache.set(cache_key, data, expire=3600)
```

---

## Phase 1: 趋势缓存服务

### Task 1.1: 创建趋势缓存服务测试文件

**Files:**
- Create: `backend/tests/services/test_trend_cache_service.py`

**Steps:**

1. 创建测试文件，编写以下测试用例：
   - `test_get_daily_trend_cache_miss_writes_cache` - 缓存未命中时写入缓存
   - `test_get_daily_trend_cache_hit_returns_cached` - 缓存命中时直接返回
   - `test_get_daily_trend_intraday_no_cache_write` - 盘中数据不写入缓存
   - `test_get_daily_trend_force_refresh_bypasses_cache` - force_refresh 跳过缓存
   - `test_get_weekly_trend_cache_miss_writes_cache` - 周趋势缓存未命中
   - `test_get_weekly_trend_cache_hit_returns_cached` - 周趋势缓存命中
   - `test_is_intraday_same_date_returns_true` - 盘中判断：相同日期
   - `test_is_intraday_different_date_returns_false` - 盘中判断：不同日期

2. 运行测试确认全部失败（TDD 红灯阶段）

**Commit:** `test: add trend_cache_service test cases`

---

### Task 1.2: 实现趋势缓存服务

**Files:**
- Create: `backend/app/services/trend_cache_service.py`

**Steps:**

1. 创建 `TrendCacheService` 类
2. 实现 `_is_intraday(realtime_date, history_last_date)` - 盘中判断
3. 实现 `_get_cache_key(code, trend_type)` - 生成缓存 key
4. 实现 `_build_daily_cache_data(df, result)` - 构建日趋势缓存数据结构
5. 实现 `get_daily_trend(code, df, realtime_price, force_refresh)` - 日趋势主函数
6. 实现 `_build_weekly_cache_data(df, result)` - 构建周趋势缓存数据结构
7. 实现 `get_weekly_trend(code, df, force_refresh)` - 周趋势主函数
8. 创建全局单例 `trend_cache_service`
9. 运行测试确认全部通过（TDD 绿灯阶段）

**Commit:** `feat: implement trend_cache_service with incremental calculation`

---

## Phase 2: 温度缓存服务

### Task 2.1: 创建温度缓存服务测试文件

**Files:**
- Create: `backend/tests/services/test_temperature_cache_service.py`

**Steps:**

1. 创建测试文件，编写以下测试用例：
   - `test_calculate_temperature_cache_miss_writes_cache` - 缓存未命中时写入
   - `test_calculate_temperature_cache_hit_returns_cached` - 缓存命中时返回
   - `test_calculate_temperature_intraday_no_cache_write` - 盘中不写缓存
   - `test_calculate_temperature_force_refresh_bypasses_cache` - force_refresh 跳过缓存
   - `test_rsi_state_preserved_in_cache` - RSI 中间状态正确缓存
   - `test_historical_peak_updated_on_new_high` - 新高时更新历史峰值

2. 运行测试确认全部失败

**Commit:** `test: add temperature_cache_service test cases`

---

### Task 2.2: 实现温度缓存服务

**Files:**
- Create: `backend/app/services/temperature_cache_service.py`

**Steps:**

1. 创建 `TemperatureCacheService` 类
2. 实现 `_get_cache_key(code)` - 生成缓存 key
3. 实现 `_build_cache_data(df, result)` - 构建缓存数据结构
4. 实现 `_extract_rsi_state(df)` - 提取 RSI 中间状态（avg_gain, avg_loss）
5. 实现 `calculate_temperature(code, df, realtime_price, force_refresh)` - 温度计算主函数
6. 创建全局单例 `temperature_cache_service`
7. 运行测试确认全部通过

**Commit:** `feat: implement temperature_cache_service with incremental calculation`

---

## Phase 3: API 集成

### Task 3.1: 修改 /metrics 端点

**Files:**
- Modify: `backend/app/api/v1/endpoints/etf.py:291-326`

**Steps:**

1. 导入 `trend_cache_service` 和 `temperature_cache_service`
2. 添加 `force_refresh: bool = False` 参数到 `get_etf_metrics` 函数
3. 替换直接调用为缓存服务调用：
   - `trend_service.get_daily_trend(df)` → `trend_cache_service.get_daily_trend(code, df, None, force_refresh)`
   - `trend_service.get_weekly_trend(df)` → `trend_cache_service.get_weekly_trend(code, df, force_refresh)`
   - `temperature_service.calculate_temperature(df)` → `temperature_cache_service.calculate_temperature(code, df, None, force_refresh)`
4. 手动测试 API 响应

**Commit:** `feat(api): integrate cache services into /metrics endpoint`

---

### Task 3.2: 添加 API 集成测试

**Files:**
- Create: `backend/tests/api/__init__.py`
- Create: `backend/tests/api/test_metrics_cache.py`

**Steps:**

1. 创建测试目录和文件
2. 编写集成测试：
   - `test_metrics_endpoint_uses_cache` - 验证缓存被使用
   - `test_metrics_endpoint_force_refresh` - 验证 force_refresh 参数生效
3. 运行完整测试套件

**Commit:** `test: add API integration tests for metrics caching`

---

## Phase 4: 验收与清理

### Task 4.1: 端到端验证

**Steps:**

1. 启动后端服务：`./manage.sh start`
2. 首次请求 `/api/v1/etf/510300/metrics`，观察响应时间
3. 再次请求同一接口，验证响应时间显著减少
4. 检查 `.cache/` 目录，确认缓存文件已创建
5. 使用 `?force_refresh=true` 参数，验证强制刷新功能
6. 在交易时段测试（如果可能），验证盘中数据不污染缓存

**Commit:** N/A (验证步骤)

---

### Task 4.2: 代码清理

**Steps:**

1. 运行 `ruff check backend/app/services/trend_cache_service.py backend/app/services/temperature_cache_service.py`
2. 运行 `pytest backend/tests/ -v` 确认所有测试通过
3. 检查日志输出，确认缓存命中/未命中日志正常

**Commit:** `chore: code cleanup and lint fixes`

---

## 文件变更清单

### 新建文件

| 文件 | 说明 |
|------|------|
| `backend/app/services/trend_cache_service.py` | 趋势缓存服务 |
| `backend/app/services/temperature_cache_service.py` | 温度缓存服务 |
| `backend/tests/services/test_trend_cache_service.py` | 趋势缓存服务测试 |
| `backend/tests/services/test_temperature_cache_service.py` | 温度缓存服务测试 |
| `backend/tests/api/__init__.py` | API 测试包初始化 |
| `backend/tests/api/test_metrics_cache.py` | API 集成测试 |

### 修改文件

| 文件 | 修改内容 |
|------|----------|
| `backend/app/api/v1/endpoints/etf.py` | 集成缓存服务，添加 force_refresh 参数 |

---

## 依赖关系图

```
Phase 1 (趋势缓存服务)
    ↓
Phase 2 (温度缓存服务)
    ↓
Phase 3 (API 集成)
    ↓
Phase 4 (验收)
```

---

## 缓存 Key 格式

| 缓存类型 | Key 格式 | 示例 |
|----------|----------|------|
| 日趋势 | `daily_trend:{code}` | `daily_trend:510300` |
| 周趋势 | `weekly_trend:{code}` | `weekly_trend:510300` |
| 温度 | `temperature:{code}` | `temperature:510300` |

---

## 风险与注意事项

1. **测试隔离**: 测试中需要 mock `disk_cache`，避免污染真实缓存
2. **日期格式**: 确保日期比较使用一致的字符串格式 `YYYY-MM-DD`
3. **空值处理**: 缓存数据可能包含 None 值，读取时需做空值检查
4. **并发安全**: DiskCache 本身是线程安全的，无需额外加锁
