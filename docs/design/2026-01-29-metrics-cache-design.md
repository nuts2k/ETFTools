# 指标缓存优化设计

> **目标**: 优化趋势和温度指标的计算性能，通过增量计算和缓存减少重复计算开销

## 背景

当前 `/api/v1/etf/{code}/metrics` API 每次请求都会全量计算日趋势、周趋势和市场温度指标。这些指标的历史部分是稳定的，只有当日/当周数据需要实时计算。

### 现状分析

| 指标 | 计算位置 | 缓存机制 |
|------|----------|----------|
| 日趋势 | `trend_service.get_daily_trend()` | 无 |
| 周趋势 | `trend_service.get_weekly_trend()` | 无 |
| 市场温度 | `temperature_service.calculate_temperature()` | 无 |

## 设计决策

| 项目 | 决策 |
|------|------|
| 计算模式 | 请求时增量计算 |
| 存储方式 | DiskCache（复用现有机制） |
| 缓存 key | 分离存储 |
| 盘中保护 | 基于数据日期判断，盘中不写缓存 |
| 架构分层 | 新建缓存服务层包装原有服务 |
| API 入口 | 双入口，支持 `force_refresh` 参数 |
| 过期策略 | 永不过期，通过日期判断更新 |

## 缓存 Key 设计

```
daily_trend:{code}      # 日趋势缓存
weekly_trend:{code}     # 周趋势缓存
temperature:{code}      # 温度缓存
```

## 盘中判断逻辑

**核心原则**: 盘中实时价格只用于计算，不能污染缓存。

```python
def is_intraday(realtime_date: str, history_last_date: str) -> bool:
    """
    判断是否为盘中数据
    
    - 实时数据日期 == 历史最新日期 → 盘中（不写缓存）
    - 实时数据日期 > 历史最新日期 → 收盘后（写缓存）
    """
    return realtime_date == history_last_date
```

**优点**:
- 不需要维护交易日历
- 自动适应节假日（节假日没有新数据，自然不会误判）
- 逻辑简单可靠

## 缓存数据结构

### 日趋势缓存

```python
{
    "last_date": "2026-01-28",        # 最后计算日期
    "yesterday_close": 3.456,          # 昨日收盘价
    "yesterday_ma": {                  # 昨日均线值（用于判断 crossing）
        "ma5": 3.45,
        "ma20": 3.42,
        "ma60": 3.38
    },
    "result": {                        # 完整计算结果
        "ma5_position": "above",
        "ma20_position": "above",
        "ma60_position": "crossing_up",
        "ma_alignment": "bullish",
        "ma_values": {...},
        "latest_signal": "break_above_ma60"
    }
}
```

### 周趋势缓存

```python
{
    "last_complete_week": "2026-01-24",  # 最后完整周的周五日期
    "result": {                           # 完整计算结果
        "consecutive_weeks": 3,
        "direction": "up",
        "ma_status": "bullish"
    }
}
```

### 温度缓存

```python
{
    "last_date": "2026-01-28",
    "historical_peak": 4.123,             # 历史最高价
    "rsi_state": {                        # RSI 的 Wilder EMA 状态
        "avg_gain": 0.023,
        "avg_loss": 0.018
    },
    "price_distribution_percentiles": [...],  # 历史价格分位点
    "volatility_distribution_percentiles": [...],  # 历史波动率分位点
    "result": {                           # 完整计算结果
        "score": 65,
        "level": "warm",
        "factors": {...},
        ...
    }
}
```

## 增量计算流程

### 日趋势流程

```
请求 /metrics API
    ↓
读取缓存 daily_trend:{code}
    ↓
┌─ 缓存存在？
│   ├─ 否 → 全量计算 → 判断是否盘中 → 非盘中则写入缓存
│   └─ 是 → 检查 last_date
│           ├─ last_date == 今日 → 直接返回缓存结果
│           └─ last_date < 今日
│                   ↓
│               获取今日数据（实时或收盘）
│                   ↓
│               判断是否盘中
│                   ├─ 是盘中 → 增量计算，不写缓存，返回结果
│                   └─ 非盘中 → 增量计算，更新缓存，返回结果
```

### 周趋势流程

```
读取缓存 weekly_trend:{code}
    ↓
┌─ 缓存存在？
│   ├─ 否 → 全量计算周线 → 写入缓存
│   └─ 是 → 检查 last_complete_week
│           ├─ 当前仍在该周内 → 补算当周数据，不更新缓存
│           └─ 已进入新周 → 补算新完成的周 + 当周，更新缓存
```

### 温度流程

温度依赖日趋势的均线排列结果，流程类似日趋势，但需要：
1. 先获取日趋势结果（用于趋势得分因子）
2. 增量更新 RSI 状态
3. 重新计算各因子得分

## 架构设计

### 文件结构

```
backend/app/services/
├── trend_service.py              # 现有，纯计算（保持不变）
├── temperature_service.py        # 现有，纯计算（保持不变）
├── trend_cache_service.py        # 新建，缓存 + 增量计算
└── temperature_cache_service.py  # 新建，缓存 + 增量计算
```

### 接口设计

#### trend_cache_service

```python
class TrendCacheService:
    def get_daily_trend(
        self, 
        code: str, 
        df: pd.DataFrame, 
        realtime_price: float = None,
        force_refresh: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        获取日趋势（带缓存）
        
        Args:
            code: ETF 代码
            df: 历史 OHLCV 数据
            realtime_price: 可选的实时价格（盘中使用）
            force_refresh: 强制刷新，跳过缓存
        """
        
    def get_weekly_trend(
        self, 
        code: str, 
        df: pd.DataFrame,
        force_refresh: bool = False
    ) -> Optional[Dict[str, Any]]:
        """获取周趋势（带缓存）"""
```

#### temperature_cache_service

```python
class TemperatureCacheService:
    def calculate_temperature(
        self, 
        code: str, 
        df: pd.DataFrame, 
        realtime_price: float = None,
        force_refresh: bool = False
    ) -> Optional[Dict[str, Any]]:
        """计算市场温度（带缓存）"""
```

### API 层调用

```python
# etf.py

@router.get("/{code}/metrics")
async def get_etf_metrics(code: str, period: str = "5y", force_refresh: bool = False):
    # ... 获取历史数据 ...
    
    # 获取实时价格（如果需要）
    realtime_price = get_realtime_price(code)  # 可选
    
    # 调用缓存服务
    daily_trend = trend_cache_service.get_daily_trend(
        code, df_for_trend, realtime_price, force_refresh
    )
    weekly_trend = trend_cache_service.get_weekly_trend(
        code, df_for_trend, force_refresh
    )
    temperature = temperature_cache_service.calculate_temperature(
        code, df_for_trend, realtime_price, force_refresh
    )
    
    # ... 返回结果 ...
```

## 文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `backend/app/services/trend_cache_service.py` | 日/周趋势缓存服务 |
| 新建 | `backend/app/services/temperature_cache_service.py` | 温度缓存服务 |
| 修改 | `backend/app/api/v1/endpoints/etf.py` | 调用缓存服务，支持 force_refresh 参数 |

## 风险与注意事项

1. **缓存一致性**: 如果原始计算逻辑变更，需要清理旧缓存
2. **首次请求**: 首次请求仍需全量计算，冷启动时间不变
3. **内存占用**: DiskCache 会占用磁盘空间，但相比内存缓存更稳定
4. **调试支持**: 保留 `force_refresh` 参数便于调试和问题排查
