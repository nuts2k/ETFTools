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
15:30  告警检查 → 计算温度/趋势 → 写入缓存 → 发送告警信号
15:35  每日摘要 → 读取实时价格 + 读取缓存温度 → 格式化 → 发送摘要
```

摘要时间选择 15:35 的原因：
- 在告警检查（15:30）之后 5 分钟
- 可复用告警检查已计算好的缓存数据，避免重复请求 API
- 收盘后数据已稳定，不会再变动

### 3.4 数据依赖

| 数据 | 来源 | 是否需要新接口 |
|------|------|--------------|
| ETF 实时价格/涨跌幅 | `ak_service.get_etf_info()` | 否 |
| 温度分数/等级 | `temperature_cache_service` 或现场计算 | 否 |
| 当日告警信号 | `alert_state_service` 的当日记录 | 否 |
| 用户自选列表 | `_collect_etf_users()` | 否 |

**结论：不需要任何新的数据接口，全部复用现有服务。**

### 3.5 独立性设计

- 摘要和告警是**两个独立开关**，用户可以只开摘要不开告警，或反过来
- 每日摘要**不计入** `max_alerts_per_day` 的告警配额
- Telegram 配置共用（bot_token / chat_id），无需额外配置

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
    """格式化每日摘要消息"""
```

参数说明：
- `items`: 自选 ETF 列表，每项包含 `code`, `name`, `price`, `change_pct`, `temperature_score`, `temperature_level`
- `signals`: 当日已触发的告警信号（从 `alert_state_service` 读取）
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

#### 新增 `_collect_summary_users()` 方法

与 `_collect_etf_users()` 类似，但筛选条件不同：
- 不要求 `alerts.enabled` 为 True（摘要独立于告警）
- 要求 `daily_summary` 为 True
- 要求 Telegram 已配置且已验证

#### `trigger_check()` 扩展

新增 `summary` 参数支持手动触发摘要：

```python
async def trigger_check(self, user_id=None, summary=False):
    if summary:
        await self._run_user_summary(user_id)
    else:
        # 现有逻辑
```

### 4.4 `alerts.py` — API 字段扩展

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
| 用户关闭了告警但开了摘要 | 正常发送摘要（两者独立） |
| 用户开了告警但关了摘要 | 只发告警不发摘要 |
| Telegram 未配置/未验证 | 跳过该用户 |
| 自选只有 1-2 只 | 不分"涨幅前三/跌幅前三"，直接展示完整列表 |
| 全部上涨或全部下跌 | 只显示对应方向的排行 |

---

## 7. 实施步骤

按以下顺序实施，每步可独立验证：

```
Step 1: alert_config.py 新增 daily_summary 字段
Step 2: notification_service.py 新增 format_daily_summary()
Step 3: alert_scheduler.py 新增 _run_daily_summary() + 注册定时任务
Step 4: alerts.py API 新增 daily_summary 字段 + trigger summary 参数
Step 5: 前端告警设置页新增 Toggle
Step 6: 手动触发测试验证
```

预估总改动量：后端 ~150 行新增，前端 ~20 行新增。
