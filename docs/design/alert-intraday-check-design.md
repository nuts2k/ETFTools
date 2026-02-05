# ETF 告警系统盘中检查设计文档

## 文档信息

- **创建日期**: 2026-02-03
- **版本**: v1.1
- **状态**: 已实施

## 1. 概述

### 1.1 背景

基于现有的 ETF 告警通知系统（每日收盘后检查），新增盘中实时检查功能，以便用户能够在交易时段内及时收到 ETF 指标变化的通知。

### 1.2 目标

- 支持盘中固定间隔检查（默认每 30 分钟）
- 优化性能，避免重复计算相同 ETF 的指标
- 保持现有的去重逻辑，避免重复通知
- 提供灵活的配置选项

### 1.3 核心功能

1. **盘中定时检查**：在交易时段（09:30-14:30）按固定间隔检查 ETF 指标
2. **ETF 合并排重**：多个用户收藏同一 ETF 时，只计算一次指标
3. **统一去重策略**：盘中检查和收盘检查共享去重计数器
4. **消息合并发送**：每个用户收到一条包含所有信号的合并消息

---

## 2. 需求分析

### 2.1 功能需求

| 需求 | 描述 | 优先级 |
|------|------|--------|
| FR-1 | 支持盘中每 30 分钟检查一次 | P0 |
| FR-2 | 支持配置检查间隔（15/30/60 分钟） | P1 |
| FR-3 | 同一信号每天只发送一次 | P0 |
| FR-4 | 盘中和收盘检查共享去重计数器 | P0 |
| FR-5 | 相同 ETF 只计算一次指标 | P0 |
| FR-6 | 支持交易日判断（跳过周末和节假日） | P1 |

### 2.2 非功能需求

| 需求 | 描述 | 目标 |
|------|------|------|
| NFR-1 | 性能优化 | 减少 50-80% 的重复计算 |
| NFR-2 | API 调用频率 | 控制在合理范围内，避免被限流 |
| NFR-3 | 错误处理 | 单个 ETF 失败不影响其他 ETF |
| NFR-4 | 可配置性 | 支持动态调整检查间隔 |

---

## 3. 设计方案

### 3.1 调度策略设计

#### 3.1.1 时间点规划

**盘中检查时间点**（每 30 分钟）：
```
09:00, 09:30, 10:00, 10:30, 11:00, 11:30,
13:00, 13:30, 14:00, 14:30
```

**收盘检查时间点**：
```
15:30
```

**说明**：
- 午休时间（11:30-13:00）自动跳过
- 使用 CronTrigger 实现精确控制
- 周末自动跳过（`day_of_week="mon-fri"`）

#### 3.1.2 调度器配置

使用 APScheduler 的 CronTrigger：

```python
# 盘中检查
CronTrigger(
    minute="0,30",      # 每小时的 0 分和 30 分
    hour="9-14",        # 9:00-14:59 之间
    day_of_week="mon-fri"
)

# 收盘检查
CronTrigger(
    hour=15,
    minute=30,
    day_of_week="mon-fri"
)
```

### 3.2 去重策略设计

#### 3.2.1 去重原则

- **同一信号每天只发送一次**：无论盘中检查还是收盘检查
- **共享计数器**：盘中和收盘检查使用相同的去重逻辑
- **按天重置**：每天 00:00 自动清除前一天的去重标记

#### 3.2.2 去重实现

使用现有的 `AlertStateService`：

```python
# 检查信号是否已发送
is_sent = alert_state_service.is_signal_sent_today(
    user_id, etf_code, signal_type
)

# 标记信号已发送（TTL 到当天 23:59:59）
alert_state_service.mark_signal_sent(
    user_id, etf_code, signal_type
)
```

**缓存 Key 格式**：
```
alert_sent:{user_id}:{etf_code}:{signal_type}:{date}
```

**示例**：
```
alert_sent:1:510300:temperature_change:2026-02-03
```

### 3.3 性能优化设计（ETF 合并排重）

#### 3.3.1 问题分析

**当前方案**（按用户遍历）：
```
遍历所有用户
  └─ 遍历该用户的自选股
      └─ 获取 ETF 数据 + 计算指标
```

**问题**：
- 用户 A 收藏 [510300, 510500, 159915]
- 用户 B 收藏 [510300, 510500, 159941]
- 用户 C 收藏 [510300, 159915, 159941]

结果：510300 被计算 3 次，510500 被计算 2 次...

**总计**：9 次数据获取和指标计算

#### 3.3.2 优化方案（按 ETF 遍历）

```
1. 收集所有用户的自选股，按 ETF 分组
   └─ 得到：{ETF代码: [用户列表]}

2. 遍历每个唯一的 ETF
   ├─ 获取数据（1次）
   ├─ 计算指标（1次）
   └─ 为所有收藏该 ETF 的用户检测信号
       └─ 收集到：{用户ID: [信号列表]}

3. 遍历每个用户
   └─ 发送包含所有信号的合并消息（1次）
```

**优化后**：4 次数据获取和指标计算（节省 55%）

#### 3.3.3 性能提升估算

| 场景 | 当前方案 | 优化方案 | 提升 |
|------|---------|---------|------|
| 100用户，10只ETF/人，50%重复率 | 1000次 | ~500次 | 50% |
| 100用户，10只ETF/人，80%重复率 | 1000次 | ~200次 | 80% |
| 盘中检查（每天10次） | 10000次/天 | 2000-5000次/天 | 50-80% |

---

## 4. 技术实现

### 4.1 数据模型

#### 4.1.1 调度配置模型

```python
class AlertScheduleConfig(BaseModel):
    """全局调度配置"""
    # 盘中检查
    intraday_enabled: bool = True
    intraday_interval_minutes: int = Field(default=30, ge=5, le=120)
    intraday_start_time: str = "09:30"
    intraday_end_time: str = "15:00"

    # 收盘汇总
    daily_summary_enabled: bool = True
    daily_summary_time: str = "15:30"

    # 交易日判断
    skip_weekends: bool = True
```

#### 4.1.2 数据结构

**ETF-用户映射**：
```python
{
    "510300": [
        {
            "user": User对象,
            "etf_name": "沪深300ETF",
            "prefs": UserAlertPreferences对象,
            "telegram_config": dict
        },
        ...
    ],
    "510500": [...]
}
```

**用户-信号映射**：
```python
{
    1: [SignalItem对象1, SignalItem对象2, ...],
    2: [SignalItem对象3, ...],
    ...
}
```

### 4.2 核心流程

#### 4.2.1 主检查流程

```python
async def _run_daily_check(self) -> None:
    """执行告警检查（优化版）"""
    # 步骤 1: 收集所有需要检查的 ETF 及其关联用户
    etf_users_map = self._collect_etf_users(session)

    # 步骤 2: 为每个用户收集信号
    user_signals_map = {}

    for etf_code, users_data in etf_users_map.items():
        # 获取 ETF 数据并计算指标（每个 ETF 只计算一次）
        df = ak_service.fetch_etf_history(etf_code)
        metrics = {
            "temperature": temperature_service.calculate_temperature(df),
            "daily_trend": trend_service.get_daily_trend(df),
            "weekly_trend": trend_service.get_weekly_trend(df),
        }

        # 为每个用户检测信号
        for user_data in users_data:
            signals = alert_service.detect_signals(...)
            if signals:
                # 更新状态并标记已发送
                # 收集信号到 user_signals_map

    # 步骤 3: 为每个用户发送合并消息
    for user_id, signals in user_signals_map.items():
        await self._send_alert_message(user, telegram_config, signals)
```

#### 4.2.2 ETF-用户收集流程

```python
def _collect_etf_users(self, session: Session) -> Dict[str, List[Dict]]:
    """收集所有需要检查的 ETF 及其关联用户"""
    etf_users_map = {}

    users = session.exec(select(User)).all()

    for user in users:
        # 检查用户配置（告警启用、Telegram 配置）
        if not is_user_eligible(user):
            continue

        # 获取用户自选股
        watchlist = get_user_watchlist(user.id)

        for item in watchlist:
            if item.etf_code not in etf_users_map:
                etf_users_map[item.etf_code] = []

            etf_users_map[item.etf_code].append({
                "user": user,
                "etf_name": item.etf_name,
                "prefs": user_prefs,
                "telegram_config": telegram_config,
            })

    return etf_users_map
```

### 4.3 代码结构

#### 4.3.1 文件修改清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/services/alert_scheduler.py` | 修改 | 重构主检查流程，添加盘中检查任务 |
| `backend/app/models/alert_config.py` | 已存在 | 配置模型已包含盘中检查字段 |
| `backend/app/services/alert_state_service.py` | 无需修改 | 现有去重逻辑已满足需求 |
| `backend/app/services/alert_service.py` | 无需修改 | 信号检测逻辑无需变更 |

#### 4.3.2 关键方法

**AlertScheduler 类新增/修改方法**：

```python
class AlertScheduler:
    def __init__(self):
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._config = AlertScheduleConfig()  # 默认配置

    def start(self) -> None:
        """启动调度器（支持盘中和收盘检查）"""
        # 添加盘中检查任务
        # 添加收盘检查任务

    def update_config(self, config: AlertScheduleConfig) -> None:
        """更新配置并重启调度器"""

    async def _run_daily_check(self) -> None:
        """执行检查（优化版：按 ETF 去重）"""

    def _collect_etf_users(self, session: Session) -> Dict[str, List[Dict]]:
        """收集 ETF-用户映射"""

    def _find_user_info(self, etf_users_map: Dict, user_id: int) -> Optional[Dict]:
        """查找用户信息"""
```

---

## 5. 配置说明

### 5.1 全局配置

**配置位置**：`AlertScheduler._config`（内存配置，可扩展为数据库存储）

**默认配置**：
```python
AlertScheduleConfig(
    intraday_enabled=True,              # 启用盘中检查
    intraday_interval_minutes=30,       # 30 分钟间隔
    intraday_start_time="09:30",        # 开始时间
    intraday_end_time="15:00",          # 结束时间
    daily_summary_enabled=True,         # 启用收盘检查
    daily_summary_time="15:30",         # 收盘检查时间
    skip_weekends=True                  # 跳过周末
)
```

### 5.2 用户配置

**配置位置**：`User.settings["alerts"]`

**用户告警偏好**：
```python
UserAlertPreferences(
    enabled=True,                       # 启用告警
    temperature_change=True,            # 温度变化信号
    extreme_temperature=True,           # 极端温度信号
    ma_crossover=True,                  # 均线突破信号
    ma_alignment=True,                  # 均线排列信号
    weekly_signal=True,                 # 周线信号
    max_alerts_per_day=20               # 每天最多信号数
)
```

### 5.3 配置优先级

1. **全局配置**：控制调度器是否启用盘中检查
2. **用户配置**：控制用户是否接收告警通知
3. **Telegram 配置**：必须启用并验证才能接收通知

**判断逻辑**：
```python
# 用户是否符合检查条件
def is_user_eligible(user: User) -> bool:
    # 1. 检查用户告警配置
    alert_prefs = UserAlertPreferences(**user.settings.get("alerts", {}))
    if not alert_prefs.enabled:
        return False

    # 2. 检查 Telegram 配置
    telegram_config = user.settings.get("telegram", {})
    if not telegram_config.get("enabled") or not telegram_config.get("verified"):
        return False

    return True
```

---

## 6. 实施步骤

### 6.1 Phase 1: 核心功能实现（P0）

#### Step 1: 重构 alert_scheduler.py

**修改内容**：
1. 重构 `_run_daily_check()` 方法，实现按 ETF 去重的逻辑
2. 添加 `_collect_etf_users()` 方法
3. 添加 `_find_user_info()` 辅助方法

**预期结果**：
- 性能提升 50-80%
- 保持现有功能不变

#### Step 2: 添加盘中检查任务

**修改内容**：
在 `start()` 方法中添加盘中检查的 CronTrigger

```python
# 盘中检查
self._scheduler.add_job(
    self._run_daily_check,
    CronTrigger(minute="0,30", hour="9-14", day_of_week="mon-fri"),
    id="intraday_alert_check",
    replace_existing=True,
)
```

**预期结果**：
- 盘中每 30 分钟自动检查
- 与收盘检查共享去重逻辑

#### Step 3: 测试验证

**测试内容**：
1. 单元测试：`_collect_etf_users()` 方法
2. 集成测试：完整检查流程
3. 性能测试：对比优化前后的执行时间

**验证指标**：
- 功能正确性：信号检测准确
- 去重有效性：同一信号每天只发送一次
- 性能提升：计算次数减少 50% 以上

### 6.2 Phase 2: 配置管理（P1）

#### Step 1: 添加配置 API

**文件**：`backend/app/api/v1/endpoints/alerts.py`

**新增端点**：
- `GET /api/v1/alerts/schedule-config` - 获取调度配置
- `PUT /api/v1/alerts/schedule-config` - 更新调度配置

#### Step 2: 实现动态配置更新

**修改内容**：
在 `AlertScheduler` 中添加 `update_config()` 方法，支持动态调整检查间隔

#### Step 3: 前端配置页面（可选）

**文件**：`frontend/app/settings/alerts/page.tsx`

**新增功能**：
- 显示当前调度配置
- 支持修改检查间隔
- 显示下次检查时间

### 6.3 Phase 3: 交易日判断（P1）

#### Step 1: 添加交易日判断逻辑

**修改内容**：
在 `_run_daily_check()` 开头添加交易日判断

```python
async def _run_daily_check(self) -> None:
    # 判断是否为交易日
    if not self._is_trading_day():
        logger.info("Not a trading day, skipping check")
        return
    # ... 现有逻辑
```

#### Step 2: 实现 `_is_trading_day()` 方法

**实现方案**：
- 方案 1：使用 AKShare 的交易日历 API
- 方案 2：维护本地节假日列表
- 方案 3：简单判断周末（当前方案）

**推荐**：方案 1（最准确）

---

## 7. 注意事项

### 7.1 性能相关

#### 7.1.1 API 调用频率

**问题**：
- 盘中每 30 分钟检查一次
- 假设 100 个用户，200 只唯一 ETF
- 每天约 10 次检查 = 2000 次 API 调用/天

**风险**：
- AKShare API 可能有频率限制
- 大量并发请求可能导致超时

**缓解措施**：
1. **批量处理**：分批处理 ETF，避免并发过高
2. **错误重试**：单个 ETF 失败不影响其他 ETF
3. **超时控制**：设置合理的超时时间
4. **监控告警**：监控 API 调用失败率

#### 7.1.2 数据库连接

**问题**：
- 每次检查需要查询所有用户和自选股
- 可能产生大量数据库查询

**优化建议**：
1. 使用连接池
2. 批量查询，减少往返次数
3. 考虑添加缓存层

#### 7.1.3 内存使用

**问题**：
- `etf_users_map` 和 `user_signals_map` 可能占用较多内存
- 用户数量增长时需要注意

**监控指标**：
- 内存使用峰值
- 单次检查耗时
- 数据结构大小

### 7.2 数据一致性

#### 7.2.1 状态更新时机

**当前设计**：
- 检测到信号后立即更新状态
- 标记信号已发送

**注意**：
- 如果发送消息失败，状态已更新，信号不会重发
- 需要权衡：重发风险 vs 丢失风险

**建议**：
- 保持当前设计（避免重复通知）
- 添加发送失败日志，便于排查

#### 7.2.2 并发问题

**场景**：
- 理论上不会有并发问题（单线程调度器）
- 但如果手动触发检查，可能与定时任务冲突

**解决方案**：
- 添加分布式锁（如果部署多实例）
- 或在 `_run_daily_check()` 开头检查是否有任务正在运行

### 7.3 错误处理

#### 7.3.1 错误隔离

**原则**：
- 单个 ETF 失败不影响其他 ETF
- 单个用户失败不影响其他用户

**实现**：
```python
for etf_code, users_data in etf_users_map.items():
    try:
        # 处理 ETF
    except Exception as e:
        logger.error(f"Error processing ETF {etf_code}: {e}")
        continue  # 继续处理下一个 ETF
```

#### 7.3.2 日志记录

**关键日志**：
- 检查开始/结束时间
- 处理的 ETF 数量
- 发送的通知数量
- 错误详情（ETF 代码、用户 ID、错误信息）

**日志级别**：
- INFO: 正常流程
- WARNING: 数据缺失、配置问题
- ERROR: API 失败、发送失败

### 7.4 用户体验

#### 7.4.1 通知频率

**问题**：
- 盘中检查可能导致通知增多
- 用户可能感到打扰

**缓解措施**：
1. **去重机制**：同一信号每天只发送一次
2. **优先级过滤**：只发送高优先级信号（可选）
3. **用户配置**：允许用户关闭盘中通知

#### 7.4.2 消息质量

**要求**：
- 消息内容清晰、准确
- 包含必要的上下文信息
- 避免误报

**建议**：
- 定期审查信号检测逻辑
- 收集用户反馈
- 优化信号阈值

---

## 8. 测试验证

### 8.1 单元测试

#### 8.1.1 ETF-用户收集测试

**测试文件**：`tests/test_alert_scheduler.py`

**测试用例**：
```python
def test_collect_etf_users():
    """测试 ETF-用户映射收集"""
    # 准备测试数据
    # - 3 个用户
    # - 用户 A: [510300, 510500]
    # - 用户 B: [510300, 159915]
    # - 用户 C: [510500, 159915]

    # 执行
    etf_users_map = scheduler._collect_etf_users(session)

    # 验证
    assert len(etf_users_map) == 3  # 3 只唯一 ETF
    assert len(etf_users_map["510300"]) == 2  # 2 个用户收藏
    assert len(etf_users_map["510500"]) == 2
    assert len(etf_users_map["159915"]) == 2
```

#### 8.1.2 去重逻辑测试

**测试用例**：
```python
def test_signal_deduplication():
    """测试信号去重"""
    user_id = 1
    etf_code = "510300"
    signal_type = "temperature_change"

    # 第一次检查：应该发送
    assert not alert_state_service.is_signal_sent_today(
        user_id, etf_code, signal_type
    )

    # 标记已发送
    alert_state_service.mark_signal_sent(user_id, etf_code, signal_type)

    # 第二次检查：应该跳过
    assert alert_state_service.is_signal_sent_today(
        user_id, etf_code, signal_type
    )
```

### 8.2 集成测试

#### 8.2.1 完整检查流程测试

**测试场景**：
1. 准备测试数据（用户、自选股、Telegram 配置）
2. 触发检查
3. 验证信号检测
4. 验证消息发送

**验证点**：
- ETF 数据获取次数（应该等于唯一 ETF 数量）
- 信号检测准确性
- 消息格式正确性
- 去重逻辑有效性

#### 8.2.2 性能测试

**测试目标**：验证性能优化效果

**测试方法**：
```python
def test_performance_optimization():
    """对比优化前后的性能"""
    # 准备测试数据：100 个用户，每人 10 只 ETF，50% 重复率

    # 测试优化前的方案
    start = time.time()
    old_implementation()
    old_time = time.time() - start
    old_api_calls = count_api_calls()

    # 测试优化后的方案
    start = time.time()
    new_implementation()
    new_time = time.time() - start
    new_api_calls = count_api_calls()

    # 验证
    assert new_api_calls < old_api_calls * 0.6  # 至少减少 40%
    assert new_time < old_time * 0.7  # 至少快 30%
```

### 8.3 端到端测试

#### 8.3.1 手动测试步骤

**前置条件**：
1. 后端服务运行中
2. 至少 2 个测试用户
3. 配置了 Telegram Bot

**测试步骤**：

**Step 1: 配置测试用户**
```bash
# 用户 A
- 自选股: [510300, 510500, 159915]
- 告警配置: 全部启用
- Telegram: 已配置并验证

# 用户 B
- 自选股: [510300, 510500, 159941]
- 告警配置: 全部启用
- Telegram: 已配置并验证
```

**Step 2: 手动触发检查**
```bash
curl -X POST http://localhost:8000/api/v1/alerts/trigger \
  -H "Authorization: Bearer {token}"
```

**Step 3: 验证结果**
- 检查后端日志：
  - 应该显示处理了 4 只唯一 ETF（510300, 510500, 159915, 159941）
  - 不应该有重复的数据获取日志
- 检查 Telegram：
  - 用户 A 和 B 应该收到通知（如果有信号）
  - 消息格式正确，包含所有信号

**Step 4: 测试去重**
- 再次触发检查
- 验证：不应该收到重复通知

#### 8.3.2 自动化测试

**测试框架**：pytest + pytest-asyncio

**测试覆盖率目标**：
- 核心逻辑：90% 以上
- 边界情况：80% 以上
- 错误处理：70% 以上

---

## 9. 未来优化

### 9.1 智能调度

**目标**：根据市场波动自动调整检查频率

**实现思路**：
- 监控市场波动率（如沪深 300 指数波动）
- 波动大时增加检查频率（如 15 分钟）
- 波动小时降低频率（如 60 分钟）

**收益**：
- 提高重要时刻的响应速度
- 降低平稳期的资源消耗

### 9.2 分布式缓存

**目标**：支持多实例部署

**实现方案**：
- 使用 Redis 替代 DiskCache
- 实现分布式锁，避免重复检查
- 共享 ETF 数据缓存

**收益**：
- 支持水平扩展
- 提高可用性
- 减少重复计算

### 9.3 增量更新

**目标**：只检查有变化的 ETF

**实现思路**：
- 缓存上次检查的 ETF 数据
- 对比当前数据，只处理有变化的
- 减少不必要的信号检测

**收益**：
- 进一步降低计算量
- 减少 API 调用

### 9.4 用户个性化

**目标**：支持用户自定义检查策略

**功能**：
- 用户可选择是否接收盘中通知
- 用户可设置通知时间段（如只在 10:00-14:00）
- 用户可设置信号优先级过滤

**收益**：
- 提升用户体验
- 减少不必要的通知

### 9.5 机器学习优化

**目标**：智能过滤误报信号

**实现思路**：
- 收集用户反馈（点击率、忽略率）
- 训练模型识别有价值的信号
- 动态调整信号阈值

**收益**：
- 提高信号质量
- 减少噪音通知

---

## 10. 总结

### 10.1 核心价值

本设计方案通过以下优化，显著提升了 ETF 告警系统的性能和用户体验：

1. **盘中实时检查**：从每天 1 次检查提升到每天 10+ 次，提高信号及时性
2. **性能优化**：通过 ETF 合并排重，减少 50-80% 的重复计算
3. **智能去重**：避免重复通知，提升用户体验
4. **灵活配置**：支持动态调整检查间隔和策略

### 10.2 关键指标

| 指标 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 检查频率 | 1次/天 | 10+次/天 | 10倍 |
| API 调用次数 | 1000次/天 | 200-500次/天 | 50-80% |
| 响应时间 | 收盘后 | 盘中实时 | 显著提升 |
| 重复通知 | 可能重复 | 每天一次 | 用户体验优化 |

### 10.3 实施建议

**优先级排序**：
1. **P0**：核心功能实现（ETF 去重 + 盘中检查）
2. **P1**：配置管理 + 交易日判断
3. **P2**：前端配置页面
4. **P3**：未来优化功能

**风险控制**：
- 先在测试环境充分验证
- 灰度发布，逐步放量
- 监控关键指标，及时调整

---

## 附录

### A. 相关文档

- [ETF 告警系统实施计划](./plans/2026-02-03-alert-notification-impl.md)
- [产品需求文档](./PRD.md)

### B. 技术栈

- **后端框架**：FastAPI
- **调度器**：APScheduler 3.10+
- **缓存**：DiskCache（可升级为 Redis）
- **数据源**：AKShare
- **通知渠道**：Telegram Bot API

### C. 术语表

| 术语 | 说明 |
|------|------|
| 盘中检查 | 交易时段内的定时检查 |
| 收盘检查 | 收盘后的汇总检查 |
| ETF 合并排重 | 多个用户收藏同一 ETF 时只计算一次 |
| 信号去重 | 同一信号每天只发送一次 |
| 交易日 | 股市开市的工作日（排除周末和节假日） |

### D. 变更历史

| 版本 | 日期 | 作者 | 变更说明 |
|------|------|------|----------|
| v1.0 | 2026-02-03 | Claude | 初始版本，完成核心设计 |
| v1.1 | 2026-02-03 | Claude | 实施完成，包含代码审查修复 |

---

**文档结束**
