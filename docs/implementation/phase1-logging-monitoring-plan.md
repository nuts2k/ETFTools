# Phase 1 实施计划：日志系统优化 + 监控告警

**设计文档**: [phase1-logging-monitoring-design.md](../design/phase1-logging-monitoring-design.md)
**创建日期**: 2026-02-16
**状态**: 待实施

---

## Step 1: 集中日志配置

**新建** `backend/app/core/logging_config.py`

实现 `setup_logging()` 函数：
- 使用 `logging.config.dictConfig()` 集中配置
- 自定义 Formatter：`[2026-02-16 15:30:01] [INFO] [akshare_service] message`
- Handler：`StreamHandler(sys.stdout)`
- 根 logger 级别：INFO
- 第三方库（akshare、urllib3、httpx）级别：WARNING（减少噪音）

**改动** `backend/app/main.py`：
- 在文件顶部 import 后立即调用 `setup_logging()`（在任何 logger 使用之前）
- 删除 `logging.basicConfig(level=logging.INFO)` (第22行)

**改动** `backend/app/services/akshare_service.py`：
- 删除 `logging.basicConfig(level=logging.INFO)` (第58行)

**不改动** `backend/seed_data.py` 和 `backend/scripts/migrate_add_admin_fields.py`（独立脚本，不走 main.py 启动流程）

**验证**: 启动后端，确认日志格式统一，无重复 handler 输出

---

## Step 2: DataSourceMetrics 指标收集器

**新建** `backend/app/core/metrics.py`

```python
# 核心类
class SourceStats:
    """单个数据源的统计数据"""
    success_count: int = 0
    failure_count: int = 0
    latencies: deque  # maxlen=100，滑动窗口
    last_status: str  # "ok" | "error" | "unknown"
    last_success_at: Optional[datetime]
    last_failure_at: Optional[datetime]
    last_error: Optional[str]

class DataSourceMetrics:
    """数据源指标收集器（单例）"""
    _sources: Dict[str, SourceStats]  # 线程安全用 threading.Lock

    def record_success(self, source: str, latency_ms: float) -> None
    def record_failure(self, source: str, error: str, latency_ms: float) -> None
    def get_success_rate(self, source: str) -> Optional[float]  # 最近100次
    def get_avg_latency(self, source: str) -> Optional[float]
    def get_source_status(self, source: str) -> dict  # 单个源状态
    def get_summary(self) -> dict  # 所有源汇总
    def get_overall_status(self) -> str  # "healthy" | "degraded" | "critical"

# 模块级单例
datasource_metrics = DataSourceMetrics()
```

关键实现细节：
- 使用 `threading.Lock` 保护 `_sources` 字典（akshare_service 在后台线程中运行）
- `get_overall_status()` 逻辑：检查所有**曾被记录过的**源，全部 last_status=="ok" → healthy，部分 error → degraded，全部 error → critical
- 时间戳使用中国时区 `datetime.now(ZoneInfo("Asia/Shanghai"))`，格式化为 `YYYY-MM-DD HH:MM:SS`

**验证**: 单元测试（Step 6）

---

## Step 3: @track_datasource 装饰器 + 改造 akshare_service

### 3a: 装饰器实现

在 `backend/app/core/metrics.py` 中添加 `track_datasource` 装饰器：

```python
def track_datasource(source_name: str):
    """装饰器：自动追踪数据源调用的成功/失败/耗时"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.monotonic()
            try:
                result = func(*args, **kwargs)
                latency = (time.monotonic() - start) * 1000
                datasource_metrics.record_success(source_name, latency)
                logger.info(f"[{source_name}] {func.__name__} succeeded ({latency:.0f}ms)")
                return result
            except Exception as e:
                latency = (time.monotonic() - start) * 1000
                datasource_metrics.record_failure(source_name, str(e), latency)
                logger.warning(f"[{source_name}] {func.__name__} failed ({latency:.0f}ms): {e}")
                raise
        return wrapper
    return decorator
```

### 3b: 改造 akshare_service.py

将 `fetch_all_etfs()` 中的三个数据源获取逻辑拆成独立的私有方法：

```python
@staticmethod
@track_datasource("eastmoney")
def _fetch_etfs_eastmoney() -> List[Dict]:
    """从东方财富获取 ETF 列表（单次尝试，不含重试）"""
    df = ak.fund_etf_spot_em()
    # ... 列重命名、类型转换 ...
    return records

@staticmethod
@track_datasource("sina")
def _fetch_etfs_sina() -> List[Dict]:
    """从新浪获取 ETF 列表"""
    # ... 三个分类获取 + 去重 ...
    return deduped

@staticmethod
@track_datasource("ths")
def _fetch_etfs_ths() -> List[Dict]:
    """从同花顺获取 ETF 列表"""
    df = ak.fund_etf_spot_ths()
    # ... 列重命名 ...
    return records
```

重写 `fetch_all_etfs()` 调用这三个方法，保持原有的重试和降级逻辑：
- EastMoney: 2次重试，每次调用 `_fetch_etfs_eastmoney()`
- Sina: 调用 `_fetch_etfs_sina()`
- THS: 调用 `_fetch_etfs_ths()`
- DiskCache / Fallback JSON: 保持不变

同样改造 `fetch_history_raw()` 中的 EastMoney 调用：

```python
@staticmethod
@track_datasource("eastmoney_history")
def _fetch_history_eastmoney(code: str, period: str, adjust: str) -> pd.DataFrame:
    """从东方财富获取历史数据（单次尝试）"""
    df = ak.fund_etf_hist_em(symbol=code, period=period, adjust=adjust, ...)
    # ... 列重命名 ...
    return df
```

**关键**：装饰器只包裹单次调用，重试逻辑留在 `fetch_all_etfs()` / `fetch_history_raw()` 中。

**验证**: 启动后端，观察日志中出现 `[eastmoney]`、`[sina]` 等数据源标记和耗时

---

## Step 4: 增强健康端点

**改动** `backend/app/main.py`

新增端点：

```python
@app.get("/api/v1/health/datasources")
async def datasource_health():
    from app.core.metrics import datasource_metrics
    summary = datasource_metrics.get_summary()
    return {
        "status": datasource_metrics.get_overall_status(),
        "sources": summary,
    }
```

同时增强现有 `/api/v1/health`，加入 overall datasource status：

```python
@app.get("/api/v1/health")
async def health_check():
    from app.core.metrics import datasource_metrics
    return {
        "status": "ok",
        "version": settings.VERSION,
        "data_ready": etf_cache.is_initialized,
        "environment": settings.ENVIRONMENT,
        "datasource_status": datasource_metrics.get_overall_status(),
    }
```

**验证**: `curl localhost:8000/api/v1/health/datasources` 返回各数据源状态

---

## Step 5: 管理员告警广播

**新建** `backend/app/services/admin_alert_service.py`

```python
class AdminAlertService:
    _cooldowns: Dict[str, datetime]  # alert_type -> last_sent_at
    COOLDOWN_SECONDS = 300  # 5 分钟防抖

    async def send_admin_alert(self, alert_type: str, message: str) -> int:
        """
        向所有已配置 Telegram 的管理员发送告警
        Returns: 成功发送的管理员数量
        """
        # 1. 防抖检查
        # 2. 查询 is_admin=True 且 telegram.enabled+verified 的用户
        # 3. 解密 botToken，调用 TelegramNotificationService.send_message()
        # 4. 记录发送时间

    def _is_cooled_down(self, alert_type: str) -> bool: ...
    def _format_system_alert(self, alert_type: str, message: str) -> str: ...

admin_alert_service = AdminAlertService()
```

消息格式：
```
🚨 <b>系统告警</b>

<b>类型</b>: 所有数据源不可用
<b>时间</b>: 2026-02-16 15:30:01
<b>详情</b>: EastMoney、Sina、THS 均获取失败，当前使用磁盘缓存兜底

请检查网络连接和数据源状态。
```

恢复通知：
```
✅ <b>数据源恢复</b>

<b>时间</b>: 2026-02-16 15:35:02
<b>详情</b>: Sina 数据源已恢复正常，成功获取 1515 个 ETF
```

### 5b: 在 akshare_service.py 中触发告警

在 `fetch_all_etfs()` 中：
- 所有在线源失败（进入 DiskCache/Fallback 分支）时：调用 `admin_alert_service.send_admin_alert("all_sources_down", ...)`
- 需要在后台线程中调用 async 函数，使用 `asyncio.run()` 或获取 event loop

**注意**：`fetch_all_etfs()` 是同步方法，在后台线程中运行。调用 async 的 `send_admin_alert` 需要：
```python
import asyncio
try:
    loop = asyncio.get_event_loop()
    if loop.is_running():
        asyncio.ensure_future(admin_alert_service.send_admin_alert(...))
    else:
        asyncio.run(admin_alert_service.send_admin_alert(...))
except RuntimeError:
    asyncio.run(admin_alert_service.send_admin_alert(...))
```

或者更简单：将 `send_admin_alert` 改为同步方法，内部用 `asyncio.run()` 调用 Telegram API。考虑到告警是低频操作（最多几分钟一次），同步阻塞可接受。

**推荐**：`AdminAlertService` 提供同步接口 `send_admin_alert_sync()`，内部 `asyncio.run()` 调用 async Telegram API。

**验证**: 手动测试 — 临时让所有数据源抛异常，确认管理员收到 Telegram 通知

---

## Step 6: 单元测试

**新建** `backend/tests/test_metrics.py`

测试用例：
- `test_record_success`: 记录成功后 success_count 增加，latency 被记录
- `test_record_failure`: 记录失败后 failure_count 增加，last_error 被设置
- `test_success_rate`: 混合成功/失败后成功率计算正确
- `test_sliding_window`: 超过 100 次后旧数据被丢弃
- `test_overall_status_healthy`: 所有源 ok → healthy
- `test_overall_status_degraded`: 部分源 error → degraded
- `test_overall_status_critical`: 全部源 error → critical
- `test_thread_safety`: 多线程并发记录不崩溃
- `test_track_datasource_decorator`: 装饰器正确记录成功/失败

**新建** `backend/tests/test_admin_alert.py`

测试用例：
- `test_send_admin_alert_no_admins`: 无管理员时不报错，返回 0
- `test_send_admin_alert_cooldown`: 5 分钟内同类型告警不重复发送
- `test_send_admin_alert_different_types`: 不同类型告警不互相防抖
- `test_format_system_alert`: 消息格式正确

使用 `unittest.mock.patch` mock 掉：
- `TelegramNotificationService.send_message`（不实际发送）
- `Session` / 数据库查询（返回 mock 用户）

**验证**: `cd backend && pytest tests/test_metrics.py tests/test_admin_alert.py -v`

---

## Step 7: 文档更新

根据 AGENTS.md 4.7 节要求，更新以下文档：

- **`API_REFERENCE.md`**: 添加 `GET /api/v1/health/datasources` 端点说明
- **`CODE_NAVIGATION.md`**: 添加新文件路径（logging_config.py、metrics.py、admin_alert_service.py）
- **`docs/planning/data-source-optimization-plan.md`**: 勾选 1.1 和 1.2 的完成项

---

## 依赖关系

```
Step 1 (日志配置) ──┐
                     ├── Step 3 (装饰器 + 改造 akshare) ── Step 4 (健康端点)
Step 2 (指标收集器) ─┘                                          │
                                                                 ├── Step 7 (文档)
Step 5 (管理员告警) ── depends on Step 2, Step 3 ───────────────┘
Step 6 (测试) ── depends on Step 2, Step 5
```

可并行的步骤：
- Step 1 和 Step 2 可并行
- Step 4 和 Step 5 可并行（都依赖 Step 3 完成）
- Step 6 在 Step 2 + Step 5 完成后执行

---

## 风险和注意事项

1. **线程安全**：`DataSourceMetrics` 必须用 Lock 保护，因为 `fetch_all_etfs()` 在后台线程运行
2. **同步/异步桥接**：`AdminAlertService` 在同步上下文中调用 async Telegram API，推荐用同步包装
3. **不破坏现有告警**：`alert_scheduler.py` 完全不改动，用户级告警逻辑不受影响
4. **装饰器只包裹单次调用**：重试逻辑留在外层，避免装饰器内重复计数

---
**最后更新**: 2026-02-16
