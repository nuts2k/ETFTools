# 每日市场摘要推送 - 设计文档

> 创建时间: 2026-02-07
> 状态: 待实现

---

## 1. 功能定位

### 1.1 与现有告警系统的关系

每日摘要与现有告警是**互补关系**，不是替代关系：

| | 现有告警 | 每日摘要 |
|---|---------|---------|
| **触发方式** | 事件驱动（指标变化才触发） | 时间驱动（每天固定发送） |
| **内容** | 单个信号（RSI 超买、均线突破等） | 全局概览（所有自选的当日表现） |
| **频率** | 不确定，可能一天多条或零条 | 每天固定一条 |
| **用户心智** | "出事了告诉我" | "每天给我一份日报" |

### 1.2 核心价值

- 用户无需打开 APP 即可掌握当日自选全貌
- 复用现有 Telegram 通道，零额外配置成本
- 30 秒内读完，信息密度高

---

## 2. 消息模板设计

### 2.1 模板示例

```
📋 自选日报 | 2026-02-07 (周五)

📊 今日概览
涨: 5 | 跌: 3 | 平: 1

🔴 涨幅前三
• 半导体ETF (512480)  +2.35%  🌡️68
• 沪深300ETF (510300) +1.12%  🌡️52
• 中证500ETF (510500) +0.87%  🌡️45

🟢 跌幅前三
• 医药ETF (512010)    -1.56%  🌡️28
• 消费ETF (159928)    -0.93%  🌡️35
• 新能源ETF (516160)  -0.41%  🌡️41

⚡ 今日信号 (3)
• 512480 半导体ETF: 温度 cool→warm
• 510300 沪深300ETF: 上穿MA20
• 512010 医药ETF: RSI<30 超卖

🌡️ 温度分布
🥶 freezing: 0 | ❄️ cool: 3 | ☀️ warm: 4 | 🔥 hot: 2
```

### 2.2 设计原则

1. **涨跌概览先行** — 一眼看出今天市场整体情绪
2. **涨跌幅排行** — 最多各展示 3 只，避免消息过长
3. **温度跟随价格** — 每只 ETF 后面附温度分数，不用单独查
4. **信号复用** — 如果当天告警系统已检测到信号，直接复用，不重复计算
5. **温度分布** — 一行总结自选列表的冷热分布

### 2.3 边界情况下的模板

**自选只有 1-2 只时**：不显示"涨幅前三/跌幅前三"分区，改为完整列表

**全部上涨/全部下跌时**：只显示对应方向的排行，另一方向不显示

**无信号时**：省略"今日信号"区块

---

## 3. 架构设计

### 3.1 核心原则

**最大化复用，最小化新增代码。**

### 3.2 调度架构

```
AlertScheduler (已有)
  ├── _run_daily_check()        ← 15:30 告警检查（已有）
  └── _run_daily_summary()      ← 15:35 每日摘要（新增）
        │
        ├── 复用 _collect_etf_users()    获取用户+自选
        ├── 复用 ak_service              获取实时价格
        ├── 复用 temperature_service     获取温度（可从缓存读）
        └── 复用 TelegramNotificationService.send_message()
```

### 3.3 时序设计

```
15:30  告警检查 → fetch_history_raw(写入4h DiskCache) → 计算温度/趋势 → 发送告警信号
15:35  每日摘要 → fetch_history_raw(命中缓存) + get_etf_info() → 现场计算温度 → 格式化 → 发送摘要
```

摘要时间选择 15:35 的原因：
- 在告警检查（15:30）之后 5 分钟
- `fetch_history_raw` 有 4 小时 DiskCache，15:35 调用时命中 15:30 的缓存，不会重复请求 API
- 温度计算是纯 CPU 操作（毫秒级），不需要独立缓存层，现场计算即可
- 收盘后数据已稳定，不会再变动

### 3.4 数据获取策略

| 数据 | 来源 | 说明 |
|------|------|------|
| ETF 涨跌幅/价格 | `ak_service.get_etf_info()` | 收盘后实时行情即收盘价，数据最准确 |
| 温度分数/等级 | `fetch_history_raw()` → `temperature_service.calculate_temperature()` | 复用历史数据缓存，现场计算温度 |
| 当日告警信号 | `alert_state_service.get_today_signals()` | **新增方法**，从缓存读取当日信号详情 |
| 用户自选列表 | `_collect_etf_users(for_summary=True)` | 复用现有方法，通过参数切换筛选条件 |

**关键决策：不新增温度缓存层。** `fetch_history_raw` 的 DiskCache 已解决重复 API 请求问题，温度计算开销可忽略。

### 3.5 容错：告警检查未执行时的摘要行为

如果 15:30 告警检查因服务器宕机/重启等原因未执行，15:35 摘要仍能正常工作：

| 数据 | 行为 | 影响 |
|------|------|------|
| `fetch_history_raw` | 缓存未命中 → 直接调 AkShare API 拉取 → 写入缓存 | 多几秒请求时间，无功能影响 |
| `get_etf_info()` | 直接调 API | 无影响 |
| 当日信号 | 缓存为空 → "今日信号"区块省略 | 符合预期：告警没跑就没有信号记录 |

**结论：摘要不依赖告警检查必须先执行，具备独立运行能力。**

### 3.6 信号复用机制

现有 `alert_state_service` 的 `mark_signal_sent()` 只记录"是否已发送"，不保存信号内容。需要扩展：

- 在 `mark_signal_sent()` 时同时存储 `SignalItem` 的序列化数据
- 新增 `get_today_signals(user_id) -> List[SignalItem]`，一次读取当日所有信号
- 缓存键：`alert_signal_detail:{user_id}:{date}` → `List[SignalItem]`

**告警关闭时的行为：** 用户关闭告警但开启摘要时，不会产生信号记录，"今日信号"区块自动省略。这符合用户意图——关闭告警即表示不关注信号。

### 3.7 独立性设计

- 摘要和告警是**两个独立开关**，用户可以只开摘要不开告警，或反过来
- 每日摘要**不计入** `max_alerts_per_day` 的告警配额
- Telegram 配置共用（bot_token / chat_id），无需额外配置

### 3.8 可靠性设计

**发送失败重试：** 告警信号是事件驱动，错过了下次还会触发；但摘要每天一次，错过就没了。因此摘要发送失败时重试 1 次，间隔 30 秒。不需要复杂的重试队列。

**去重保护：** 防止定时任务因服务重启等原因重复执行导致用户收到多条摘要。在 `alert_state_service` 中新增缓存键 `summary_sent:{user_id}:{date}`，发送前检查、发送后标记。

### 3.9 消息格式

统一使用 **HTML 格式**（`parse_mode="HTML"`），与现有告警消息保持一致。模板中的 emoji 在 HTML 模式下正常显示，同时可用 `<b>` 加粗关键数字提升可读性。

---

## 4. 后端改动清单

### 4.1 `alert_config.py` — 新增字段

在 `UserAlertPreferences` 中新增：

```python
daily_summary: bool = True   # 每日摘要开关，默认开启
```

只加一个字段，保持简洁。默认开启，因为这是低打扰、高价值的功能。

### 4.2 `notification_service.py` — 新增格式化方法

```python
@staticmethod
def format_daily_summary(
    items: List[dict],
    signals: List[SignalItem],
    date_str: str
) -> str:
    """格式化每日摘要消息（HTML 格式，与现有告警一致）"""
```

参数说明：
- `items`: 自选 ETF 列表，每项包含 `code`, `name`, `price`, `change_pct`, `temperature_score`, `temperature_level`
- `signals`: 当日已触发的告警信号（从 `alert_state_service.get_today_signals()` 读取）
- `date_str`: 日期字符串，如 "2026-02-07 (周五)"

格式化逻辑：
1. 统计涨/跌/平数量
2. 按涨跌幅排序，取前 3 / 后 3
3. 附加当日信号（如有）
4. 统计温度分布

### 4.3 `alert_scheduler.py` — 新增摘要任务

#### 注册定时任务

在 `start()` 中新增：

```python
# 每日摘要 (15:35，在告警检查之后)
self._scheduler.add_job(
    self._run_daily_summary,
    CronTrigger(hour=15, minute=35, day_of_week="mon-fri"),
    id="daily_summary",
    replace_existing=True,
)
```

#### 新增 `_run_daily_summary()` 方法

核心逻辑：

1. 遍历所有用户，筛选条件：
   - `daily_summary` 开关为 True
   - Telegram 已配置且已验证
   - 自选列表不为空
2. 按 ETF 去重获取实时价格和温度（复用 `_collect_etf_users()` 的模式）
3. 为每个用户组装其自选列表的数据
4. 调用 `format_daily_summary()` 格式化消息
5. 通过 `TelegramNotificationService.send_message()` 发送

#### 扩展 `_collect_etf_users()` 方法

不新增独立方法，而是给现有方法加 `for_summary=False` 参数，内部切换筛选条件：
- `for_summary=False`（默认）：要求 `alerts.enabled == True`（现有行为不变）
- `for_summary=True`：要求 `daily_summary == True`，不要求 `alerts.enabled`
- 两者共同要求：Telegram 已配置且已验证、自选列表不为空

#### `trigger_check()` 扩展

新增 `summary` 参数支持手动触发摘要：

```python
async def trigger_check(self, user_id=None, summary=False):
    if summary:
        await self._run_user_summary(user_id)
    else:
        # 现有逻辑
```

**手动触发的时间处理：** 手动触发不限制时间（可在盘中使用），但消息模板中标注实际生成时间而非固定写"收盘"，让用户知道这是盘中快照还是收盘数据。

### 4.4 `alert_state_service.py` — 信号详情存储

扩展现有服务以支持摘要读取当日信号：

**修改 `mark_signal_sent()`：** 在标记信号已发送的同时，将 `SignalItem` 追加到当日信号列表缓存中。

```python
# 新增缓存键：alert_signal_detail:{user_id}:{date} → List[SignalItem]
def mark_signal_sent(self, user_id, etf_code, signal_type, signal_item=None):
    # ... 现有逻辑 ...
    if signal_item:
        # 追加到当日信号详情列表
```

**新增 `get_today_signals()`：**

```python
def get_today_signals(self, user_id: int) -> List[SignalItem]:
    """获取用户当日所有已触发的信号详情"""
```

**新增 `is_summary_sent_today()`** 和 **`mark_summary_sent()`：**

```python
def is_summary_sent_today(self, user_id: int) -> bool:
    """检查今天是否已发送摘要（去重保护）"""

def mark_summary_sent(self, user_id: int) -> None:
    """标记今天已发送摘要"""
    # 缓存键：summary_sent:{user_id}:{date}，当天有效
```

### 4.5 `alerts.py` — API 字段扩展

`AlertConfigRequest` 和 `AlertConfigResponse` 新增：

```python
daily_summary: bool = True
```

同时 `trigger` 端点新增 `summary` 查询参数：

```python
@router.post("/trigger")
async def trigger_alert_check(
    summary: bool = False,
    current_user: User = Depends(get_current_user)
):
    result = await alert_scheduler.trigger_check(current_user.id, summary=summary)
```

---

## 5. 前端改动清单

### 5.1 告警设置页 (`frontend/app/settings/alerts/page.tsx`)

在"启用信号通知"主开关下方新增一行独立 Toggle：

```
[现有] 启用信号通知        ← 控制告警信号
[新增] 每日市场摘要        ← 控制每日摘要（独立开关）
[现有] 监控信号类型...
```

UI 结构：与现有主开关样式一致，使用日历图标 (`Calendar`)。

**禁用态：** Telegram 未配置/未验证时，摘要开关置灰并提示"请先配置 Telegram"，复用现有告警开关的禁用逻辑。

### 5.2 `lib/api.ts` — AlertConfig 类型扩展

```typescript
export interface AlertConfig {
  // ... 现有字段 ...
  daily_summary: boolean;  // 新增
}
```

### 5.3 改动量估算

前端约 20 行新增（一个 Toggle + 类型字段）。

---

## 6. 边界情况处理

| 场景 | 处理方式 |
|------|---------|
| 自选列表为空 | 不发送摘要 |
| 所有 ETF 数据获取失败 | 不发送，记录日志 |
| 部分 ETF 失败 | 只展示成功的，底部注明"N 只获取失败" |
| 非交易日（周末） | 不发送（`day_of_week="mon-fri"` 已处理） |
| 节假日（周一到周五但休市） | 第一版不处理，后续可接入交易日历 |
| 用户关闭了告警但开了摘要 | 正常发送摘要，但"今日信号"区块为空（自动省略） |
| 用户开了告警但关了摘要 | 只发告警不发摘要 |
| Telegram 未配置/未验证 | 跳过该用户，前端开关置灰 |
| 自选只有 1-2 只 | 不分"涨幅前三/跌幅前三"，直接展示完整列表 |
| 全部上涨或全部下跌 | 只显示对应方向的排行 |
| 发送失败 | 重试 1 次（间隔 30 秒），仍失败则记录日志 |
| 定时任务重复执行 | `summary_sent:{user_id}:{date}` 缓存键去重，同一天不会重复发送 |
| 15:30 告警检查未执行 | 摘要独立运行：`fetch_history_raw` 直接调 API，信号区块省略 |
| 手动触发（盘中） | 正常发送，消息标注实际生成时间 |

---

## 7. 实施步骤

按以下顺序实施，每步可独立验证：

```
Step 1: alert_config.py 新增 daily_summary 字段
Step 2: alert_state_service.py 扩展信号详情存储 + 摘要去重
Step 3: notification_service.py 新增 format_daily_summary()（HTML 格式）
Step 4: alert_scheduler.py 扩展 _collect_etf_users() + 新增 _run_daily_summary() + 注册定时任务
Step 5: alerts.py API 新增 daily_summary 字段 + trigger summary 参数
Step 6: 前端告警设置页新增 Toggle（含禁用态）
Step 7: 手动触发测试验证
```

预估总改动量：后端 ~180 行新增，前端 ~20 行新增。
