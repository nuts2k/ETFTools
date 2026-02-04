# ETF 告警系统优化设计文档

## 文档信息

- **创建日期**: 2026-02-04
- **版本**: v1.0
- **状态**: 设计中

---

## 1. 现状分析

### 1.1 当前架构概述

当前告警系统已实现以下核心功能：
- 盘中检查（每 30 分钟，09:00-14:30）
- 收盘检查（15:30）
- ETF 去重优化（相同 ETF 只计算一次）
- 信号去重（同一信号每天只发送一次）
- Telegram 通知推送

### 1.2 已识别的问题和优化点

| 类别 | 问题描述 | 影响 | 优先级 |
|------|----------|------|--------|
| 可靠性 | 无交易日判断，周末/节假日仍会执行检查 | 资源浪费、可能产生无效数据 | P0 |
| 可靠性 | 消息发送失败后无重试机制 | 用户可能错过重要信号 | P1 |
| 性能 | ETF 数据串行获取，无并发控制 | 检查耗时长 | P1 |
| 可观测性 | 缺少监控指标和告警 | 问题难以发现和定位 | P1 |
| 用户体验 | 无静默时段配置 | 用户可能在非工作时间收到通知 | P2 |
| 扩展性 | DiskCache 不支持多实例部署 | 无法水平扩展 | P2 |
| 信号质量 | 缺少信号确认机制，可能产生误报 | 用户信任度下降 | P2 |
| 权限管理 | 无管理员角色，监控功能无法访问控制 | 监控数据暴露风险 | P1 |

---

## 2. 优化方案

### 2.1 P0: 交易日判断

#### 2.1.1 问题详述

当前系统使用 `day_of_week="mon-fri"` 跳过周末，但无法处理：
- 法定节假日（春节、国庆等）
- 调休工作日（周末补班）

#### 2.1.2 解决方案

**方案 A: 使用 AKShare 交易日历 API（推荐）**

```python
# 伪代码
async def _is_trading_day(self) -> bool:
    """判断今天是否为交易日"""
    today = date.today()

    # 1. 先检查缓存
    cache_key = f"trading_day:{today.isoformat()}"
    cached = self._cache.get(cache_key)
    if cached is not None:
        return cached

    # 2. 调用 AKShare API 获取交易日历
    try:
        calendar = await asyncio.to_thread(
            ak.tool_trade_date_hist_sina
        )
        is_trading = today in calendar['trade_date'].values

        # 缓存结果（24小时）
        self._cache.set(cache_key, is_trading, expire=86400)
        return is_trading
    except Exception as e:
        # 降级：仅判断周末
        return today.weekday() < 5
```

**方案 B: 本地维护节假日列表**

- 优点：无外部依赖
- 缺点：需要手动维护，容易遗漏

**推荐**: 方案 A，API 失败时降级到方案 B

#### 2.1.3 实现位置

- 文件: `backend/app/services/alert_scheduler.py`
- 方法: 新增 `_is_trading_day()`，在 `_run_daily_check()` 开头调用

---

### 2.2 P1: 消息发送重试机制

#### 2.2.1 问题详述

当前 `_send_alert_message()` 方法在发送失败时仅记录日志，不会重试：
- 网络抖动可能导致临时失败
- Telegram API 限流可能导致发送失败
- 用户可能错过重要的交易信号

#### 2.2.2 解决方案

**实现指数退避重试**

```python
async def _send_alert_message_with_retry(
    self,
    user: User,
    telegram_config: dict,
    signals: List[SignalItem],
    max_retries: int = 3,
) -> bool:
    """带重试的消息发送"""
    for attempt in range(max_retries):
        try:
            await self._send_alert_message(user, telegram_config, signals)
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                logger.warning(
                    f"Send failed (attempt {attempt + 1}), retrying in {wait_time}s: {e}"
                )
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"Send failed after {max_retries} attempts: {e}")
                # 可选：将失败消息存入队列，稍后重试
                return False
    return False
```

#### 2.2.3 扩展：失败消息队列

对于持续失败的消息，可以存入队列稍后重试：

```python
# 缓存 key: failed_messages:{user_id}:{date}
# 内容: List[SignalItem]
# 在下次检查时尝试重发
```

---

### 2.3 P1: ETF 数据并发获取

#### 2.3.1 问题详述

当前 ETF 数据是串行获取的：

```python
for etf_code, users_data in etf_users_map.items():
    metrics = await self._fetch_and_compute_etf_metrics(etf_code)  # 串行
```

假设有 50 只 ETF，每只获取耗时 1 秒，总耗时约 50 秒。

#### 2.3.2 解决方案

**使用 asyncio.gather 并发获取，带并发限制**

```python
async def _fetch_all_etf_metrics(
    self,
    etf_codes: List[str],
    max_concurrent: int = 10
) -> Dict[str, Optional[Dict[str, Any]]]:
    """并发获取多个 ETF 的指标"""
    semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_with_limit(etf_code: str):
        async with semaphore:
            return etf_code, await self._fetch_and_compute_etf_metrics(etf_code)

    results = await asyncio.gather(
        *[fetch_with_limit(code) for code in etf_codes],
        return_exceptions=True
    )

    return {
        code: metrics
        for code, metrics in results
        if not isinstance(metrics, Exception) and metrics is not None
    }
```

#### 2.3.3 性能预估

| 场景 | 串行耗时 | 并发耗时 (10并发) | 提升 |
|------|----------|-------------------|------|
| 50 ETF | ~50s | ~5s | 90% |
| 100 ETF | ~100s | ~10s | 90% |

---

### 2.4 P1: 可观测性增强

#### 2.4.1 问题详述

当前系统缺少：
- 结构化的监控指标
- 检查执行状态的可视化
- 异常情况的主动告警

#### 2.4.2 解决方案

**A. 添加监控指标**

```python
# 新增 metrics 模块
class AlertMetrics:
    """告警系统监控指标"""

    def __init__(self):
        self.check_count = 0           # 检查执行次数
        self.check_duration_ms = []    # 检查耗时
        self.etf_fetch_errors = 0      # ETF 数据获取失败次数
        self.signal_count = 0          # 检测到的信号数
        self.send_success = 0          # 发送成功次数
        self.send_failed = 0           # 发送失败次数
        self.last_check_time = None    # 上次检查时间

    def to_dict(self) -> dict:
        return {
            "check_count": self.check_count,
            "avg_duration_ms": sum(self.check_duration_ms[-100:]) / max(len(self.check_duration_ms[-100:]), 1),
            "etf_fetch_errors": self.etf_fetch_errors,
            "signal_count": self.signal_count,
            "send_success_rate": self.send_success / max(self.send_success + self.send_failed, 1),
            "last_check_time": self.last_check_time,
        }
```

**B. 添加监控 API 端点**

```
GET /api/v1/alerts/metrics
Response: {
    "check_count": 150,
    "avg_duration_ms": 3500,
    "etf_fetch_errors": 2,
    "signal_count": 45,
    "send_success_rate": 0.98,
    "last_check_time": "2026-02-04T10:30:00"
}
```

**C. 添加健康检查**

```python
def health_check(self) -> dict:
    """检查告警系统健康状态"""
    issues = []

    # 检查调度器状态
    if not self._scheduler or not self._scheduler.running:
        issues.append("scheduler_not_running")

    # 检查上次执行时间
    if self._metrics.last_check_time:
        elapsed = datetime.now() - self._metrics.last_check_time
        if elapsed.total_seconds() > 3600:  # 超过1小时未执行
            issues.append("check_overdue")

    # 检查错误率
    if self._metrics.send_failed > self._metrics.send_success * 0.1:
        issues.append("high_send_failure_rate")

    return {
        "healthy": len(issues) == 0,
        "issues": issues
    }
```

#### 2.4.3 监控观测方案

监控指标需要有地方观测，这涉及到管理员角色的引入（见 2.8 节）。

**观测方式对比**：

| 方案 | 优点 | 缺点 | 推荐场景 |
|------|------|------|----------|
| API 端点 + curl/脚本 | 简单、无需前端 | 不直观 | 开发调试 |
| 前端管理页面 | 直观、可视化 | 需要开发前端 | 生产环境 |
| Telegram 异常通知 | 复用现有通道、主动推送 | 仅告警、无历史 | 异常监控 |
| Prometheus + Grafana | 功能强大、业界标准 | 部署复杂 | 大规模系统 |

**推荐方案（渐进式）**：

1. **Phase 1**: API 端点 + Telegram 异常通知（复用现有通道）
2. **Phase 2**: 前端管理页面（按需）

---

### 2.5 P1: 管理员角色与权限控制

#### 2.5.1 问题详述

当前系统缺少管理员角色：
- 监控 API 端点无法做访问控制
- 系统异常通知不知道发给谁
- 无法区分普通用户和管理员权限

#### 2.5.2 解决方案

**A. 扩展 User 模型**

```python
class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str
    role: str = Field(default="user")  # user | admin
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"
```

**B. 管理员权限装饰器**

```python
from functools import wraps
from fastapi import HTTPException, status

def require_admin(func):
    """要求管理员权限的装饰器"""
    @wraps(func)
    async def wrapper(*args, current_user: User, **kwargs):
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="需要管理员权限"
            )
        return await func(*args, current_user=current_user, **kwargs)
    return wrapper
```

**C. 管理员专属 API 端点**

```python
# backend/app/api/v1/endpoints/admin.py

@router.get("/alerts/metrics")
@require_admin
async def get_alert_metrics(current_user: User = Depends(get_current_user)):
    """获取告警系统监控指标（仅管理员）"""
    return alert_scheduler.get_metrics()

@router.get("/alerts/health")
@require_admin
async def get_alert_health(current_user: User = Depends(get_current_user)):
    """获取告警系统健康状态（仅管理员）"""
    return alert_scheduler.health_check()
```

**D. 管理员异常通知**

```python
class AdminNotificationService:
    """管理员通知服务"""

    @staticmethod
    async def notify_admins(message: str) -> None:
        """向所有管理员发送通知"""
        with Session(engine) as session:
            admins = session.exec(
                select(User).where(User.role == "admin")
            ).all()

            for admin in admins:
                telegram_config = admin.settings.get("telegram", {})
                if telegram_config.get("enabled") and telegram_config.get("verified"):
                    await TelegramNotificationService.send_message(
                        bot_token=decrypt_token(telegram_config["botToken"]),
                        chat_id=telegram_config["chatId"],
                        message=f"⚠️ 系统告警\n\n{message}"
                    )
```

**E. 管理员账号创建**

方案选择：

| 方案 | 说明 | 适用场景 |
|------|------|----------|
| 环境变量初始化 | 首次启动时从环境变量创建 | 简单部署 |
| CLI 命令 | `python -m app.cli create-admin` | 灵活管理 |
| 首个注册用户 | 第一个注册的用户自动成为管理员 | 个人使用 |

**推荐**: 环境变量 + CLI 命令结合

```python
# 启动时检查
async def init_admin():
    admin_username = os.getenv("ADMIN_USERNAME")
    admin_password = os.getenv("ADMIN_PASSWORD")

    if admin_username and admin_password:
        with Session(engine) as session:
            existing = session.exec(
                select(User).where(User.username == admin_username)
            ).first()

            if not existing:
                admin = User(
                    username=admin_username,
                    hashed_password=hash_password(admin_password),
                    role="admin"
                )
                session.add(admin)
                session.commit()
                logger.info(f"Admin user '{admin_username}' created")
```

---

### 2.6 P2: 用户静默时段配置

#### 2.5.1 问题详述

用户可能不希望在某些时段收到通知（如午休时间）。

#### 2.5.2 解决方案

**扩展用户告警配置**

```python
class UserAlertPreferences(BaseModel):
    # ... 现有字段 ...

    # 新增：静默时段
    quiet_hours_enabled: bool = False
    quiet_hours_start: str = "12:00"  # HH:MM
    quiet_hours_end: str = "13:00"

    def is_quiet_time(self) -> bool:
        """判断当前是否在静默时段"""
        if not self.quiet_hours_enabled:
            return False

        now = datetime.now().time()
        start = datetime.strptime(self.quiet_hours_start, "%H:%M").time()
        end = datetime.strptime(self.quiet_hours_end, "%H:%M").time()

        return start <= now <= end
```

**在发送前检查**

```python
if prefs.is_quiet_time():
    # 将消息存入延迟队列，静默时段结束后发送
    self._queue_delayed_message(user_id, signals)
    return
```

---

### 2.7 P2: Redis 缓存支持（多实例部署）

#### 2.6.1 问题详述

当前使用 DiskCache 存储状态：
- 仅支持单实例部署
- 无法在多个服务实例间共享状态
- 可能导致重复发送通知

#### 2.6.2 解决方案

**抽象缓存接口，支持多种后端**

```python
from abc import ABC, abstractmethod

class AlertCacheBackend(ABC):
    """告警缓存后端抽象接口"""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]: ...

    @abstractmethod
    def set(self, key: str, value: Any, expire: int = None): ...

    @abstractmethod
    def delete(self, key: str): ...


class DiskCacheBackend(AlertCacheBackend):
    """DiskCache 实现（单实例）"""
    def __init__(self):
        self._cache = Cache(CACHE_DIR)
    # ... 实现方法


class RedisCacheBackend(AlertCacheBackend):
    """Redis 实现（多实例）"""
    def __init__(self, redis_url: str):
        self._redis = redis.from_url(redis_url)
    # ... 实现方法
```

**配置选择**

```python
# config.py
ALERT_CACHE_BACKEND = os.getenv("ALERT_CACHE_BACKEND", "disk")  # disk | redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
```

---

### 2.8 P2: 信号质量优化

#### 2.7.1 问题详述

当前信号检测可能产生误报：
- 盘中数据波动可能触发假信号
- 均线突破后快速回落（假突破）
- 用户对信号质量的信任度下降

#### 2.7.2 解决方案

**A. 信号确认机制**

```python
class SignalConfirmation:
    """信号确认机制"""

    def __init__(self, cache: AlertCacheBackend):
        self._cache = cache

    def should_send_signal(
        self,
        user_id: int,
        etf_code: str,
        signal_type: str,
        confirmation_count: int = 2
    ) -> bool:
        """
        检查信号是否应该发送

        需要连续 N 次检查都检测到相同信号才发送
        """
        key = f"signal_confirm:{user_id}:{etf_code}:{signal_type}"
        count = self._cache.get(key, default=0)

        if count >= confirmation_count - 1:
            # 达到确认次数，可以发送
            self._cache.delete(key)
            return True
        else:
            # 增加计数，等待下次确认
            self._cache.set(key, count + 1, expire=3600)  # 1小时内有效
            return False
```

**B. 信号优先级过滤**

允许用户只接收高优先级信号：

```python
class UserAlertPreferences(BaseModel):
    # ... 现有字段 ...
    min_priority: str = "LOW"  # LOW | MEDIUM | HIGH

    def should_send_priority(self, priority: SignalPriority) -> bool:
        priority_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
        return priority_order[priority.value] >= priority_order[self.min_priority]
```

---

## 3. 实施计划

### 3.1 Phase 1: 核心可靠性 (P0)

| 任务 | 预估工作量 | 依赖 |
|------|-----------|------|
| 实现交易日判断 | 小 | 无 |
| 添加单元测试 | 小 | 交易日判断 |

### 3.2 Phase 2: 性能与可靠性 (P1)

| 任务 | 预估工作量 | 依赖 |
|------|-----------|------|
| 消息发送重试机制 | 小 | 无 |
| ETF 数据并发获取 | 中 | 无 |
| User 模型添加 role 字段 | 小 | 无 |
| 管理员权限装饰器 | 小 | role 字段 |
| 管理员初始化逻辑 | 小 | role 字段 |
| 监控指标收集 | 中 | 无 |
| 监控 API 端点 | 小 | 监控指标 + 管理员权限 |
| 健康检查接口 | 小 | 监控指标 + 管理员权限 |
| 管理员异常通知 | 小 | 管理员权限 |

### 3.3 Phase 3: 用户体验 (P2)

| 任务 | 预估工作量 | 依赖 |
|------|-----------|------|
| 静默时段配置 | 中 | 无 |
| 信号确认机制 | 中 | 无 |
| 信号优先级过滤 | 小 | 无 |
| 前端配置页面 | 中 | 后端 API |

### 3.4 Phase 4: 扩展性 (P2)

| 任务 | 预估工作量 | 依赖 |
|------|-----------|------|
| 缓存接口抽象 | 中 | 无 |
| Redis 后端实现 | 中 | 缓存接口 |
| 配置切换支持 | 小 | Redis 后端 |

---

## 4. 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| AKShare 交易日历 API 不稳定 | 交易日判断失败 | 降级到周末判断 + 本地节假日列表 |
| 并发获取导致 API 限流 | 数据获取失败 | 控制并发数、添加重试 |
| Redis 连接失败 | 状态丢失 | 降级到 DiskCache |
| 信号确认延迟发送 | 用户错过时机 | 可配置确认次数，默认关闭 |

---

## 5. 总结

### 5.1 优化收益预估

| 优化项 | 预期收益 |
|--------|----------|
| 交易日判断 | 避免节假日无效检查，节省资源 |
| 消息重试 | 发送成功率从 ~95% 提升到 ~99% |
| 并发获取 | 检查耗时减少 80-90% |
| 监控指标 | 问题发现时间从小时级降到分钟级 |
| 静默时段 | 提升用户体验，减少打扰 |
| 信号确认 | 减少误报，提升信号质量 |

### 5.2 建议实施顺序

1. **立即实施**: 交易日判断（P0）- 避免节假日资源浪费
2. **短期实施**: 消息重试 + 并发获取 + 监控（P1）
3. **中期实施**: 用户体验优化（P2）
4. **长期规划**: Redis 支持（按需）

---

## 附录

### A. 相关文件

| 文件 | 说明 |
|------|------|
| `backend/app/services/alert_scheduler.py` | 告警调度器 |
| `backend/app/services/alert_service.py` | 信号检测服务 |
| `backend/app/services/alert_state_service.py` | 状态缓存服务 |
| `docs/alert-intraday-check-design.md` | 盘中检查设计文档 |

### B. 变更历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-02-04 | 初始版本 |

---

**文档结束**
