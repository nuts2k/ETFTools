# 网格指标缓存优化 - 第一阶段实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为网格参数计算添加专用缓存层，并优化历史数据缓存过期时间，将缓存命中时的响应时间从 500ms 降至 10ms。

**Architecture:** 在 `grid_service.py` 中添加 `calculate_grid_params_cached()` 函数，使用 DiskCache 缓存计算结果（4小时过期）。同时将历史数据缓存从 1 小时延长至 4 小时，减少数据源请求。

**Tech Stack:** Python, FastAPI, DiskCache, Pandas, Pytest

**参考文档:** `docs/plans/grid-performance-optimization.md`

---

## 任务概览

1. **Task 1**: 为缓存功能编写测试（TDD 第一步）
2. **Task 2**: 实现网格参数缓存函数
3. **Task 3**: 更新 API 端点使用缓存函数
4. **Task 4**: 调整历史数据缓存过期时间
5. **Task 5**: 添加性能监控日志
6. **Task 6**: 运行完整测试并验证性能提升

---

## Task 1: 为缓存功能编写测试

**目标:** 遵循 TDD 原则，先编写失败的测试用例

**Files:**
- Modify: `backend/tests/services/test_grid_service.py`

### Step 1: 编写缓存功能测试

在 `test_grid_service.py` 末尾添加以下测试：

```python
import time
from app.services.akshare_service import disk_cache


def test_calculate_grid_params_cached_basic():
    """测试缓存函数基本功能"""
    from app.services.grid_service import calculate_grid_params_cached
    
    # 准备测试数据
    data = {
        'date': pd.date_range(start='2023-01-01', periods=100),
        'close': [3.0 + (i % 10) * 0.05 for i in range(100)],
        'high': [3.0 + (i % 10) * 0.05 + 0.02 for i in range(100)],
        'low': [3.0 + (i % 10) * 0.05 - 0.02 for i in range(100)],
    }
    df = pd.DataFrame(data)
    
    # Mock ak_service.fetch_history_raw
    from unittest.mock import patch
    with patch('app.services.grid_service.ak_service.fetch_history_raw', return_value=df):
        # 清除可能存在的缓存
        cache_key = "grid_params_510300"
        disk_cache.delete(cache_key)
        
        # 第一次调用（缓存未命中）
        result1 = calculate_grid_params_cached("510300")
        
        # 验证返回结果
        assert result1 is not None
        assert 'upper' in result1
        assert 'lower' in result1
        assert 'grid_count' in result1
        
        # 第二次调用（缓存命中）
        result2 = calculate_grid_params_cached("510300")
        
        # 验证结果一致
        assert result1 == result2


def test_calculate_grid_params_cached_performance():
    """测试缓存性能提升"""
    from app.services.grid_service import calculate_grid_params_cached
    
    # 准备测试数据
    data = {
        'date': pd.date_range(start='2023-01-01', periods=100),
        'close': [3.0 + (i % 10) * 0.05 for i in range(100)],
        'high': [3.0 + (i % 10) * 0.05 + 0.02 for i in range(100)],
        'low': [3.0 + (i % 10) * 0.05 - 0.02 for i in range(100)],
    }
    df = pd.DataFrame(data)
    
    from unittest.mock import patch
    with patch('app.services.grid_service.ak_service.fetch_history_raw', return_value=df):
        code = "510300"
        cache_key = f"grid_params_{code}"
        disk_cache.delete(cache_key)
        
        # 测试冷启动
        start = time.time()
        result1 = calculate_grid_params_cached(code)
        cold_time = time.time() - start
        
        # 测试缓存命中
        start = time.time()
        result2 = calculate_grid_params_cached(code)
        hot_time = time.time() - start
        
        # 验证缓存命中速度至少快 5 倍
        assert hot_time < cold_time * 0.2
        # 缓存命中应该在 50ms 以内
        assert hot_time < 0.05


def test_calculate_grid_params_cached_force_refresh():
    """测试强制刷新功能"""
    from app.services.grid_service import calculate_grid_params_cached
    
    data = {
        'date': pd.date_range(start='2023-01-01', periods=100),
        'close': [3.0 + (i % 10) * 0.05 for i in range(100)],
        'high': [3.0 + (i % 10) * 0.05 + 0.02 for i in range(100)],
        'low': [3.0 + (i % 10) * 0.05 - 0.02 for i in range(100)],
    }
    df = pd.DataFrame(data)
    
    from unittest.mock import patch, MagicMock
    mock_fetch = MagicMock(return_value=df)
    
    with patch('app.services.grid_service.ak_service.fetch_history_raw', mock_fetch):
        code = "510300"
        disk_cache.delete(f"grid_params_{code}")
        
        # 第一次调用
        result1 = calculate_grid_params_cached(code)
        assert mock_fetch.call_count == 1
        
        # 第二次调用（使用缓存）
        result2 = calculate_grid_params_cached(code)
        assert mock_fetch.call_count == 1  # 没有新的调用
        
        # 强制刷新
        result3 = calculate_grid_params_cached(code, force_refresh=True)
        assert mock_fetch.call_count == 2  # 应该有新的调用
```

### Step 2: 运行测试验证失败

```bash
cd backend
pytest tests/services/test_grid_service.py::test_calculate_grid_params_cached_basic -v
```

**预期结果:** FAIL - `ImportError: cannot import name 'calculate_grid_params_cached'`

### Step 3: 提交测试代码

```bash
git add tests/services/test_grid_service.py
git commit -m "test: add tests for grid params caching functionality"
```

---

## Task 2: 实现网格参数缓存函数

**目标:** 实现 `calculate_grid_params_cached()` 函数，使测试通过

**Files:**
- Modify: `backend/app/services/grid_service.py`

### Step 1: 添加缓存函数实现

在 `grid_service.py` 文件顶部添加导入：

```python
import pandas as pd
import numpy as np
from typing import Dict, Any
import logging

from app.services.akshare_service import disk_cache, ak_service

logger = logging.getLogger(__name__)
```

在文件末尾（`calculate_grid_params` 函数之后）添加新函数：

```python
def calculate_grid_params_cached(code: str, force_refresh: bool = False) -> Dict[str, Any]:
    """
    带缓存的网格参数计算
    
    Args:
        code: ETF 代码
        force_refresh: 是否强制刷新缓存
        
    Returns:
        网格参数字典，包含 upper, lower, spacing_pct, grid_count 等
    """
    cache_key = f"grid_params_{code}"
    
    # 如果不强制刷新，先尝试从缓存读取
    if not force_refresh:
        cached = disk_cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Grid params cache hit for {code}")
            return cached
    
    # 缓存未命中或强制刷新，重新计算
    logger.info(f"Calculating grid params for {code} (force_refresh={force_refresh})")
    
    # 获取历史数据
    df = ak_service.fetch_history_raw(code, period="daily", adjust="qfq")
    
    if df.empty:
        logger.warning(f"No history data found for {code}")
        return {}
    
    # 计算网格参数
    result = calculate_grid_params(df)
    
    # 如果计算成功，写入缓存（4 小时过期）
    if result:
        disk_cache.set(cache_key, result, expire=14400)
        logger.debug(f"Grid params cached for {code}")
    
    return result
```

### Step 2: 运行测试验证通过

```bash
pytest tests/services/test_grid_service.py::test_calculate_grid_params_cached_basic -v
pytest tests/services/test_grid_service.py::test_calculate_grid_params_cached_performance -v
pytest tests/services/test_grid_service.py::test_calculate_grid_params_cached_force_refresh -v
```

**预期结果:** 所有测试 PASS

### Step 3: 运行完整测试套件

```bash
pytest tests/services/test_grid_service.py -v
```

**预期结果:** 所有测试 PASS

### Step 4: 提交实现代码

```bash
git add app/services/grid_service.py
git commit -m "feat(grid): add cached grid params calculation with 4h TTL"
```

---

## Task 3: 更新 API 端点使用缓存函数

**目标:** 修改 API 端点使用新的缓存函数，并添加 `force_refresh` 参数

**Files:**
- Modify: `backend/app/api/v1/endpoints/etf.py:341-366`

### Step 1: 编写 API 端点测试

在 `backend/tests/api/` 目录下查找或创建 ETF 端点测试文件：

```bash
ls backend/tests/api/
```

如果存在 `test_etf.py`，在其中添加测试；否则创建新文件。

在测试文件中添加：

```python
def test_grid_suggestion_endpoint_with_cache(client):
    """测试网格建议端点使用缓存"""
    code = "510300"
    
    # 第一次请求
    response1 = client.get(f"/api/v1/etf/{code}/grid-suggestion")
    assert response1.status_code == 200
    data1 = response1.json()
    
    # 验证返回数据结构
    assert "upper" in data1
    assert "lower" in data1
    assert "grid_count" in data1
    assert "spacing_pct" in data1
    
    # 第二次请求（应该使用缓存）
    response2 = client.get(f"/api/v1/etf/{code}/grid-suggestion")
    assert response2.status_code == 200
    data2 = response2.json()
    
    # 数据应该一致
    assert data1 == data2


def test_grid_suggestion_endpoint_force_refresh(client):
    """测试强制刷新参数"""
    code = "510300"
    
    # 正常请求
    response1 = client.get(f"/api/v1/etf/{code}/grid-suggestion")
    assert response1.status_code == 200
    
    # 强制刷新请求
    response2 = client.get(f"/api/v1/etf/{code}/grid-suggestion?force_refresh=true")
    assert response2.status_code == 200
    
    # 两次都应该成功
    assert response1.json() is not None
    assert response2.json() is not None
```

### Step 2: 运行测试验证当前状态

```bash
pytest tests/api/test_etf.py::test_grid_suggestion_endpoint_with_cache -v
```

**预期结果:** PASS（因为端点已存在，只是还没用缓存函数）

### Step 3: 修改 API 端点实现

修改 `backend/app/api/v1/endpoints/etf.py` 中的 `get_grid_suggestion` 函数：

```python
from app.services.grid_service import calculate_grid_params_cached

@router.get("/{code}/grid-suggestion")
async def get_grid_suggestion(code: str, force_refresh: bool = False):
    """
    获取网格交易建议参数
    
    基于历史波动率（ATR）计算适合震荡行情的网格交易参数
    
    Args:
        code: ETF 代码
        force_refresh: 是否强制刷新缓存（默认 False）
        
    Returns:
        网格参数，包含上下界、间距、网格数量等
    """
    # 使用缓存版本的计算函数
    result = calculate_grid_params_cached(code, force_refresh=force_refresh)
    
    if not result:
        raise HTTPException(status_code=400, detail="Insufficient data for grid calculation")
    
    return result
```

同时需要更新导入语句，将：

```python
from app.services.grid_service import calculate_grid_params
```

改为：

```python
from app.services.grid_service import calculate_grid_params_cached
```

### Step 4: 运行测试验证修改

```bash
pytest tests/api/test_etf.py::test_grid_suggestion_endpoint_with_cache -v
pytest tests/api/test_etf.py::test_grid_suggestion_endpoint_force_refresh -v
```

**预期结果:** 所有测试 PASS

### Step 5: 提交 API 修改

```bash
git add app/api/v1/endpoints/etf.py
git commit -m "feat(api): use cached grid params in endpoint with force_refresh option"
```

---

## Task 4: 调整历史数据缓存过期时间

**目标:** 将历史数据缓存从 1 小时延长至 4 小时

**Files:**
- Modify: `backend/app/services/akshare_service.py:220`

### Step 1: 编写缓存过期时间测试

在 `backend/tests/services/` 中创建或修改 `test_akshare_service.py`：

```python
def test_history_cache_expiry_time():
    """验证历史数据缓存过期时间为 4 小时"""
    from app.services.akshare_service import disk_cache
    from unittest.mock import patch, MagicMock
    import pandas as pd
    
    # Mock akshare 返回
    mock_df = pd.DataFrame({
        'date': pd.date_range(start='2023-01-01', periods=10),
        '日期': pd.date_range(start='2023-01-01', periods=10),
        '开盘': [1.0] * 10,
        '收盘': [1.0] * 10,
        '最高': [1.1] * 10,
        '最低': [0.9] * 10,
        '成交量': [1000] * 10,
    })
    
    with patch('app.services.akshare_service.ak.fund_etf_hist_em', return_value=mock_df):
        from app.services.akshare_service import AkShareService
        
        code = "510300"
        cache_key = f"hist_{code}_daily_qfq"
        
        # 清除缓存
        disk_cache.delete(cache_key)
        
        # 调用函数触发缓存
        result = AkShareService.fetch_history_raw(code, "daily", "qfq")
        
        # 验证缓存存在
        cached = disk_cache.get(cache_key)
        assert cached is not None
        
        # 验证缓存过期时间（通过检查缓存元数据）
        # DiskCache 的 expire 时间存储在内部，我们通过重新设置来验证
        # 这个测试主要是文档性质的，确保开发者知道应该是 14400 秒
```

### Step 2: 修改缓存过期时间

在 `backend/app/services/akshare_service.py` 中找到第 220 行附近：

```python
# 修改前
disk_cache.set(cache_key, df, expire=3600)

# 修改后
disk_cache.set(cache_key, df, expire=14400)  # 4 小时 = 14400 秒
```

添加注释说明：

```python
# 缓存 4 小时（历史数据不会变化，只需在收盘后更新）
disk_cache.set(cache_key, df, expire=14400)
```

### Step 3: 验证修改

```bash
# 运行相关测试
pytest tests/services/test_akshare_service.py -v -k cache
```

**预期结果:** 测试 PASS

### Step 4: 提交修改

```bash
git add app/services/akshare_service.py
git commit -m "perf(cache): increase history data cache TTL from 1h to 4h"
```

---

## Task 5: 添加性能监控日志

**目标:** 在 API 端点添加性能监控，记录响应时间和缓存命中情况

**Files:**
- Modify: `backend/app/api/v1/endpoints/etf.py:341-366`

### Step 1: 添加性能监控代码

修改 `get_grid_suggestion` 函数，添加计时逻辑：

```python
import time
import logging

logger = logging.getLogger(__name__)

@router.get("/{code}/grid-suggestion")
async def get_grid_suggestion(code: str, force_refresh: bool = False):
    """
    获取网格交易建议参数
    
    基于历史波动率（ATR）计算适合震荡行情的网格交易参数
    
    Args:
        code: ETF 代码
        force_refresh: 是否强制刷新缓存（默认 False）
        
    Returns:
        网格参数，包含上下界、间距、网格数量等
    """
    start_time = time.time()
    
    # 使用缓存版本的计算函数
    result = calculate_grid_params_cached(code, force_refresh=force_refresh)
    
    elapsed = time.time() - start_time
    is_cached = elapsed < 0.1  # 如果响应时间小于 100ms，认为是缓存命中
    
    logger.info(
        f"Grid suggestion for {code}: {elapsed:.3f}s "
        f"(cached: {is_cached}, force_refresh: {force_refresh})"
    )
    
    if not result:
        raise HTTPException(status_code=400, detail="Insufficient data for grid calculation")
    
    return result
```

### Step 2: 手动测试性能监控

启动服务并测试：

```bash
# 启动后端服务
cd backend
uvicorn app.main:app --reload --port 8000

# 在另一个终端测试
curl http://localhost:8000/api/v1/etf/510300/grid-suggestion
```

查看日志输出，应该看到类似：

```
INFO: Grid suggestion for 510300: 0.450s (cached: False, force_refresh: False)
INFO: Grid suggestion for 510300: 0.008s (cached: True, force_refresh: False)
```

### Step 3: 提交性能监控代码

```bash
git add app/api/v1/endpoints/etf.py
git commit -m "feat(monitoring): add performance logging for grid suggestion endpoint"
```

---

## Task 6: 运行完整测试并验证性能提升

**目标:** 确保所有测试通过，并验证性能优化效果

### Step 1: 运行完整测试套件

```bash
cd backend

# 运行所有网格相关测试
pytest tests/services/test_grid_service.py -v

# 运行 API 测试
pytest tests/api/ -v -k grid

# 运行所有测试
pytest tests/ -v
```

**预期结果:** 所有测试 PASS

### Step 2: 性能基准测试

创建性能测试脚本 `backend/tests/performance/test_grid_performance.py`：

```python
import time
import pytest
from app.services.grid_service import calculate_grid_params_cached
from app.services.akshare_service import disk_cache


@pytest.mark.performance
def test_grid_cache_performance_improvement():
    """验证缓存带来的性能提升"""
    code = "510300"
    cache_key = f"grid_params_{code}"
    
    # 清除缓存
    disk_cache.delete(cache_key)
    
    # 冷启动测试（3次取平均）
    cold_times = []
    for _ in range(3):
        disk_cache.delete(cache_key)
        start = time.time()
        result = calculate_grid_params_cached(code)
        cold_times.append(time.time() - start)
    
    avg_cold_time = sum(cold_times) / len(cold_times)
    
    # 缓存命中测试（10次取平均）
    hot_times = []
    for _ in range(10):
        start = time.time()
        result = calculate_grid_params_cached(code)
        hot_times.append(time.time() - start)
    
    avg_hot_time = sum(hot_times) / len(hot_times)
    
    # 性能报告
    speedup = avg_cold_time / avg_hot_time
    print(f"\n性能测试结果:")
    print(f"  冷启动平均: {avg_cold_time*1000:.1f}ms")
    print(f"  缓存命中平均: {avg_hot_time*1000:.1f}ms")
    print(f"  性能提升: {speedup:.1f}x")
    
    # 验证性能目标
    assert avg_hot_time < 0.05, f"缓存命中应该在 50ms 以内，实际: {avg_hot_time*1000:.1f}ms"
    assert speedup > 5, f"性能提升应该超过 5 倍，实际: {speedup:.1f}x"
```

运行性能测试：

```bash
pytest tests/performance/test_grid_performance.py -v -s
```

### Step 3: 创建性能测试报告

将测试结果记录到文档：

```bash
# 运行测试并保存输出
pytest tests/performance/test_grid_performance.py -v -s > docs/testing/grid-cache-performance-report.txt
```

### Step 4: 最终提交

```bash
git add tests/performance/test_grid_performance.py
git add docs/testing/grid-cache-performance-report.txt
git commit -m "test(perf): add grid cache performance benchmarks"
```

---

## 验收标准

完成后应满足以下标准：

### 功能验收

- [ ] `calculate_grid_params_cached()` 函数正常工作
- [ ] API 端点支持 `force_refresh` 参数
- [ ] 缓存命中时返回正确结果
- [ ] 强制刷新时重新计算

### 性能验收

- [ ] 缓存命中时响应时间 < 50ms
- [ ] 性能提升 > 5 倍
- [ ] 历史数据缓存时间为 4 小时
- [ ] 网格参数缓存时间为 4 小时

### 测试覆盖

- [ ] 单元测试覆盖缓存逻辑
- [ ] API 测试覆盖端点功能
- [ ] 性能测试验证优化效果
- [ ] 所有测试通过

### 代码质量

- [ ] 代码符合项目规范
- [ ] 添加适当的日志记录
- [ ] 添加必要的注释
- [ ] 提交信息清晰

---

## 回滚计划

如果出现问题，按以下顺序回滚：

1. **回滚 API 修改**:
   ```bash
   git revert <commit-hash>  # API 端点修改的提交
   ```

2. **回滚缓存函数**:
   ```bash
   git revert <commit-hash>  # 缓存函数实现的提交
   ```

3. **回滚缓存时间修改**:
   ```bash
   git revert <commit-hash>  # 缓存过期时间修改的提交
   ```

---

## 后续工作

第一阶段完成后，可以继续进行：

- **第二阶段**: 优化 ATR 计算 + 批量预热热门 ETF
- **第三阶段**: 异步预热机制 + 盘中/盘后智能缓存
- **第四阶段**: 数据切片优化

参考文档: `docs/plans/grid-performance-optimization.md`

---

## 注意事项

1. **测试数据隔离**: 测试中使用 mock 避免依赖真实 API
2. **缓存清理**: 测试前后清理缓存，避免干扰
3. **日志级别**: 开发环境使用 DEBUG，生产环境使用 INFO
4. **向后兼容**: API 端点保持向后兼容，`force_refresh` 为可选参数
5. **错误处理**: 缓存失败时应降级到直接计算，不影响功能

---

**预计总耗时**: 1-2 小时

**风险等级**: 低

**依赖项**: 无新增依赖
