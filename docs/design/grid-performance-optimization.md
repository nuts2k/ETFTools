# 网格指标计算性能优化方案

## 📊 当前实现分析

### 网格指标计算流程 (`grid_service.py`)

1. **数据获取**: 通过 `ak_service.fetch_history_raw()` 获取 QFQ 历史数据
2. **数据处理**: 取最近 60 天数据
3. **指标计算**:
   - 使用分位数计算上下界 (95% / 5%)
   - 使用 ATR 动态计算网格间距
   - 计算网格数量 (5-20 个)

### 当前缓存策略

- `fetch_history_raw()` 使用 DiskCache，过期时间 **3600 秒 (1 小时)**
- 缓存 key: `hist_{code}_{period}_{adjust}`
- 无网格参数专用缓存

### 代码位置

- 网格服务: `backend/app/services/grid_service.py`
- API 端点: `backend/app/api/v1/endpoints/etf.py:341`
- 数据服务: `backend/app/services/akshare_service.py:207`

---

## 🎯 性能优化最佳实践建议

### 1. 增加网格参数专用缓存层 ⭐⭐⭐

**问题**: 当前每次调用 `/etf/{code}/grid-suggestion` 都会：
- 获取完整历史数据 (可能数千条记录)
- 重新计算 ATR 和分位数

**建议**: 参考 `metrics_service.py` 的模式，添加网格参数缓存：

```python
# 在 grid_service.py 中添加
from app.services.akshare_service import disk_cache

def calculate_grid_params_cached(code: str, force_refresh: bool = False) -> Dict[str, Any]:
    """带缓存的网格参数计算"""
    cache_key = f"grid_params_{code}"
    
    if not force_refresh:
        cached = disk_cache.get(cache_key)
        if cached:
            return cached
    
    # 获取原始数据并计算
    df = ak_service.fetch_history_raw(code, period="daily", adjust="qfq")
    result = calculate_grid_params(df)
    
    if result:
        # 缓存 4 小时（与 metrics_service 保持一致）
        disk_cache.set(cache_key, result, expire=14400)
    
    return result
```

**API 端点修改**:

```python
# backend/app/api/v1/endpoints/etf.py
@router.get("/{code}/grid-suggestion")
async def get_grid_suggestion(code: str, force_refresh: bool = False):
    """获取网格交易建议参数"""
    result = calculate_grid_params_cached(code, force_refresh)
    
    if not result:
        raise HTTPException(status_code=400, detail="Insufficient data for grid calculation")
    
    return result
```

**收益**: 
- 减少 95% 的重复计算
- API 响应时间从 ~500ms 降至 ~10ms

---

### 2. 优化 ATR 计算 ⭐⭐

**问题**: 当前 `_calculate_atr()` 使用 `pd.concat()` 创建临时 DataFrame：

```python
tr = pd.concat([
    df['high'] - df['low'],
    (df['high'] - prev_close).abs(),
    (df['low'] - prev_close).abs()
], axis=1).max(axis=1)
```

**建议**: 使用 NumPy 向量化操作，避免 DataFrame 拼接：

```python
def _calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """优化版 ATR 计算"""
    if len(df) < period + 1:
        return 0.0
    
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    
    # 使用 NumPy 向量化计算
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]  # 第一个值用当前收盘价
    
    tr = np.maximum.reduce([
        high - low,
        np.abs(high - prev_close),
        np.abs(low - prev_close)
    ])
    
    # 使用 pandas rolling 计算均值
    atr_series = pd.Series(tr).rolling(window=period).mean()
    
    if pd.isna(atr_series.iloc[-1]):
        return 0.0
    
    return float(atr_series.iloc[-1])
```

**收益**: 
- ATR 计算速度提升 30-50%
- 内存占用减少

---

### 3. 数据切片优化 ⭐

**问题**: 当前先获取全量数据，再 `tail(60)`：

```python
df = ak_service.fetch_history_raw(code, period="daily", adjust="qfq")
recent_df = df.tail(60).copy()
```

**建议**: 在数据获取层就限制数据量（如果 API 支持）：

```python
# 方案 A: 如果 akshare 支持日期范围
from datetime import datetime, timedelta
start_date = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d")

# 方案 B: 在缓存层添加"最近 N 天"的专用缓存
def fetch_recent_history(code: str, days: int = 60) -> pd.DataFrame:
    """获取最近 N 天数据（带专用缓存）"""
    cache_key = f"hist_recent_{code}_{days}"
    cached = disk_cache.get(cache_key)
    if cached is not None:
        return cached
    
    # 获取全量数据并切片
    df_full = fetch_history_raw(code, "daily", "qfq")
    df_recent = df_full.tail(days)
    
    # 缓存 1 小时
    disk_cache.set(cache_key, df_recent, expire=3600)
    return df_recent
```

**收益**: 
- 减少内存拷贝
- 提升缓存命中率

---

### 4. 异步预热机制 ⭐⭐⭐

**问题**: 用户首次访问网格建议时需要等待计算完成。

**建议**: 参考 `metrics_service.py` 的异步预热模式：

```python
import threading
import logging

logger = logging.getLogger(__name__)

class GridService:
    def __init__(self):
        self._fetching_codes = set()
        self._lock = threading.Lock()
    
    def _async_calculate_grid(self, code: str):
        """后台线程预计算网格参数"""
        with self._lock:
            if code in self._fetching_codes:
                return
            self._fetching_codes.add(code)
        
        try:
            logger.info(f"Background calculating grid for {code}")
            calculate_grid_params_cached(code, force_refresh=True)
        finally:
            with self._lock:
                self._fetching_codes.remove(code)
    
    def get_grid_params_async(self, code: str) -> Optional[Dict]:
        """异步获取网格参数（立即返回缓存或 None）"""
        cache_key = f"grid_params_{code}"
        cached = disk_cache.get(cache_key)
        
        if cached:
            return cached
        
        # 触发后台计算
        t = threading.Thread(target=self._async_calculate_grid, args=(code,))
        t.daemon = True
        t.start()
        
        return None  # 前端可显示 loading 状态

grid_service = GridService()
```

**API 端点修改**:

```python
@router.get("/{code}/grid-suggestion")
async def get_grid_suggestion(code: str, wait: bool = True):
    """
    获取网格交易建议参数
    
    Args:
        code: ETF 代码
        wait: 是否等待计算完成（False 时立即返回，可能为空）
    """
    if wait:
        # 同步模式：等待计算完成
        result = calculate_grid_params_cached(code)
    else:
        # 异步模式：立即返回缓存或触发后台计算
        result = grid_service.get_grid_params_async(code)
    
    if not result:
        raise HTTPException(status_code=202, detail="Calculation in progress")
    
    return result
```

**收益**: 
- 首次访问响应时间从 500ms 降至 <50ms
- 用户体验提升（可显示加载动画）

---

### 5. 批量预热热门 ETF ⭐⭐

**建议**: 在应用启动时预热热门 ETF 的网格参数：

```python
# 在 backend/app/main.py 的 startup 事件中
@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化任务"""
    
    # 预热热门 ETF 网格参数
    hot_etfs = [
        "510300",  # 沪深300ETF
        "510500",  # 中证500ETF
        "159915",  # 创业板ETF
        "512690",  # 酒ETF
        "159949",  # 创业板50
        "512880",  # 证券ETF
        "515050",  # 5GETF
        "159941",  # 纳指ETF
    ]
    
    def preheat_grids():
        for code in hot_etfs:
            try:
                calculate_grid_params_cached(code, force_refresh=True)
                logger.info(f"✓ Preheated grid params for {code}")
            except Exception as e:
                logger.error(f"✗ Failed to preheat {code}: {e}")
    
    # 后台线程执行预热
    t = threading.Thread(target=preheat_grids)
    t.daemon = True
    t.start()
    
    logger.info("Grid params preheating started in background")
```

**收益**:
- 热门 ETF 首次访问无需等待
- 提升用户体验

---

### 6. 缓存过期策略优化 ⭐

**当前问题**: 
- 历史数据缓存 1 小时 (`expire=3600`)
- 网格参数无独立缓存

**建议**: 差异化缓存策略

| 数据类型 | 当前过期时间 | 建议过期时间 | 理由 |
|---------|------------|------------|------|
| 历史数据 (QFQ) | 1 小时 | **4 小时** | 历史数据不会变化，只需在收盘后更新 |
| 网格参数 | 无 | **4 小时** | 基于历史数据计算，可与历史数据同步 |
| 实时行情 | 60 秒 | 60 秒 | 保持不变 |

**代码修改**:

```python
# backend/app/services/akshare_service.py:220
# 修改前
disk_cache.set(cache_key, df, expire=3600)

# 修改后
disk_cache.set(cache_key, df, expire=14400)  # 4 小时
```

**收益**:
- 减少 75% 的数据源请求
- 降低 API 限流风险

---

### 7. 盘中/盘后智能缓存 ⭐⭐

**建议**: 参考 `trend_cache_service.py` 的盘中判断逻辑：

```python
from datetime import datetime, time

def _should_cache_grid(code: str) -> bool:
    """判断是否应该缓存网格参数"""
    now = datetime.now()
    
    # 周末直接缓存
    if now.weekday() >= 5:
        return True
    
    current_time = now.time()
    
    # 盘中时间不缓存（数据可能不完整）
    # 交易时间: 9:15-11:30, 13:00-15:00
    if time(9, 15) <= current_time <= time(11, 30):
        return False
    if time(13, 0) <= current_time <= time(15, 0):
        return False
    
    return True

def calculate_grid_params_cached(code: str, force_refresh: bool = False) -> Dict[str, Any]:
    """带缓存的网格参数计算（智能盘中判断）"""
    cache_key = f"grid_params_{code}"
    
    # 盘中时间：总是重新计算，不读取缓存
    if not _should_cache_grid(code) or force_refresh:
        df = ak_service.fetch_history_raw(code, period="daily", adjust="qfq")
        result = calculate_grid_params(df)
        return result
    
    # 盘后时间：优先读取缓存
    cached = disk_cache.get(cache_key)
    if cached:
        return cached
    
    # 缓存未命中：计算并缓存
    df = ak_service.fetch_history_raw(code, period="daily", adjust="qfq")
    result = calculate_grid_params(df)
    
    if result:
        disk_cache.set(cache_key, result, expire=14400)
    
    return result
```

**收益**:
- 盘中数据实时性更好
- 盘后减少不必要的计算

---

## 📈 性能对比预估

| 场景 | 当前耗时 | 优化后耗时 | 提升 |
|-----|---------|-----------|------|
| 首次访问（冷启动） | ~500ms | ~500ms | - |
| 缓存命中 | ~500ms | ~10ms | **98%** |
| 热门 ETF（预热） | ~500ms | ~5ms | **99%** |
| 并发 10 个请求 | ~5s | ~50ms | **99%** |

---

## 🎬 推荐实施顺序

### 第一阶段：立即实施 (高收益/低风险)

1. ✅ **增加网格参数专用缓存层** (#1)
   - 文件: `backend/app/services/grid_service.py`
   - 预计工作量: 30 分钟
   - 风险: 低

2. ✅ **调整缓存过期时间** (#6)
   - 文件: `backend/app/services/akshare_service.py:220`
   - 预计工作量: 5 分钟
   - 风险: 极低

### 第二阶段：短期优化 (1-2 天)

3. ✅ **优化 ATR 计算** (#2)
   - 文件: `backend/app/services/grid_service.py:5`
   - 预计工作量: 1 小时
   - 风险: 低（需要测试数值一致性）

4. ✅ **批量预热热门 ETF** (#5)
   - 文件: `backend/app/main.py`
   - 预计工作量: 30 分钟
   - 风险: 低

### 第三阶段：中期优化 (1 周)

5. ✅ **异步预热机制** (#4)
   - 文件: `backend/app/services/grid_service.py`
   - 预计工作量: 2 小时
   - 风险: 中（需要处理并发）

6. ✅ **盘中/盘后智能缓存** (#7)
   - 文件: `backend/app/services/grid_service.py`
   - 预计工作量: 1 小时
   - 风险: 低

### 第四阶段：长期优化 (可选)

7. ✅ **数据切片优化** (#3)
   - 文件: `backend/app/services/akshare_service.py`
   - 预计工作量: 2 小时
   - 风险: 中（需要测试数据完整性）

---

## 💡 额外建议

### 1. 性能监控

添加性能监控，便于追踪优化效果：

```python
import time
import logging

logger = logging.getLogger(__name__)

@router.get("/{code}/grid-suggestion")
async def get_grid_suggestion(code: str):
    start = time.time()
    
    result = calculate_grid_params_cached(code)
    
    elapsed = time.time() - start
    logger.info(f"Grid calculation for {code}: {elapsed:.3f}s (cached: {elapsed < 0.1})")
    
    if not result:
        raise HTTPException(status_code=400, detail="Insufficient data for grid calculation")
    
    return result
```

### 2. 缓存预热 API

提供手动刷新接口，方便调试和强制更新：

```python
@router.post("/{code}/grid-suggestion/refresh")
async def refresh_grid_suggestion(code: str):
    """强制刷新网格参数缓存"""
    result = calculate_grid_params_cached(code, force_refresh=True)
    
    if not result:
        raise HTTPException(status_code=400, detail="Insufficient data for grid calculation")
    
    return {
        "status": "refreshed",
        "code": code,
        "data": result
    }
```

### 3. 错误降级

当计算失败时返回默认参数，避免完全失败：

```python
DEFAULT_GRID_PARAMS = {
    "upper": 0.0,
    "lower": 0.0,
    "spacing_pct": 1.5,
    "grid_count": 10,
    "range_start": "",
    "range_end": "",
    "is_out_of_range": False,
    "is_default": True  # 标记为默认值
}

def calculate_grid_params_cached(code: str, force_refresh: bool = False) -> Dict[str, Any]:
    """带缓存的网格参数计算（含降级逻辑）"""
    try:
        # ... 正常计算逻辑 ...
        return result
    except Exception as e:
        logger.error(f"Grid calculation failed for {code}: {e}")
        return DEFAULT_GRID_PARAMS
```

### 4. 缓存统计

添加缓存命中率统计：

```python
class GridCacheStats:
    def __init__(self):
        self.hits = 0
        self.misses = 0
    
    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

cache_stats = GridCacheStats()

@router.get("/grid-suggestion/stats")
async def get_cache_stats():
    """获取缓存统计信息"""
    return {
        "hits": cache_stats.hits,
        "misses": cache_stats.misses,
        "hit_rate": f"{cache_stats.hit_rate:.2%}"
    }
```

---

## 📝 测试计划

### 单元测试

```python
# tests/test_grid_service.py
import pytest
from app.services.grid_service import calculate_grid_params, _calculate_atr

def test_atr_calculation():
    """测试 ATR 计算准确性"""
    # 准备测试数据
    df = pd.DataFrame({
        'high': [10.5, 10.8, 10.6, 10.9],
        'low': [10.0, 10.2, 10.1, 10.3],
        'close': [10.3, 10.5, 10.4, 10.7]
    })
    
    atr = _calculate_atr(df, period=3)
    assert atr > 0
    assert isinstance(atr, float)

def test_grid_params_cache():
    """测试网格参数缓存"""
    code = "510300"
    
    # 第一次调用（缓存未命中）
    start = time.time()
    result1 = calculate_grid_params_cached(code)
    time1 = time.time() - start
    
    # 第二次调用（缓存命中）
    start = time.time()
    result2 = calculate_grid_params_cached(code)
    time2 = time.time() - start
    
    assert result1 == result2
    assert time2 < time1 * 0.1  # 缓存命中应该快 10 倍以上
```

### 性能测试

```python
# tests/test_grid_performance.py
import pytest
import time

def test_grid_calculation_performance():
    """测试网格计算性能"""
    code = "510300"
    
    # 清除缓存
    disk_cache.delete(f"grid_params_{code}")
    
    # 测试冷启动
    start = time.time()
    result = calculate_grid_params_cached(code)
    cold_time = time.time() - start
    
    # 测试缓存命中
    start = time.time()
    result = calculate_grid_params_cached(code)
    hot_time = time.time() - start
    
    print(f"Cold start: {cold_time:.3f}s")
    print(f"Cache hit: {hot_time:.3f}s")
    print(f"Speedup: {cold_time / hot_time:.1f}x")
    
    assert hot_time < 0.05  # 缓存命中应该在 50ms 以内
```

---

## 📚 参考资料

### 项目内部参考

- `backend/app/services/metrics_service.py` - 异步预热模式
- `backend/app/services/trend_cache_service.py` - 盘中判断逻辑
- `backend/app/services/temperature_cache_service.py` - 缓存策略

### 外部参考

- [Pandas Performance Tips](https://pandas.pydata.org/docs/user_guide/enhancingperf.html)
- [NumPy Vectorization](https://numpy.org/doc/stable/user/basics.broadcasting.html)
- [DiskCache Documentation](http://www.grantjenks.com/docs/diskcache/)

---

## 📅 更新日志

- **2026-01-30**: 初始版本，基于今天的提交分析
- 分析提交范围: `e65a1bc..fe10608`
- 主要变更: 添加 ATR 逻辑，修复日期格式问题

---

## ✅ 验收标准

优化完成后，应满足以下标准：

1. **性能指标**:
   - 缓存命中时响应时间 < 50ms
   - 缓存命中率 > 90%
   - 并发 10 个请求总耗时 < 1s

2. **功能完整性**:
   - 所有现有功能正常工作
   - 计算结果与优化前一致
   - 错误处理完善

3. **代码质量**:
   - 单元测试覆盖率 > 80%
   - 性能测试通过
   - 代码审查通过

4. **用户体验**:
   - 热门 ETF 首次访问无明显延迟
   - 盘中数据实时性良好
   - 错误提示友好
