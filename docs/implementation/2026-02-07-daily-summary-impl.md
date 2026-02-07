# 每日市场摘要推送 - 实现计划

> 设计文档: [docs/design/2026-02-07-daily-summary-design.md](../design/2026-02-07-daily-summary-design.md)
> 创建时间: 2026-02-07
> 状态: 待实施

---

## 改动文件总览

| # | 文件 | 改动类型 | 说明 |
|---|------|---------|------|
| 1 | `backend/app/models/alert_config.py` | 修改 | 新增 `daily_summary` 字段 |
| 2 | `backend/app/services/alert_state_service.py` | 修改 | 新增信号详情存储 + 摘要去重 |
| 3 | `backend/app/services/notification_service.py` | 修改 | 新增 `format_daily_summary()` |
| 4 | `backend/app/services/alert_scheduler.py` | 修改 | 扩展 `_collect_etf_users()` + 新增 `_run_daily_summary()` |
| 5 | `backend/app/api/v1/endpoints/alerts.py` | 修改 | API 新增 `daily_summary` 字段 + trigger summary 参数 |
| 6 | `frontend/lib/api.ts` | 修改 | `AlertConfig` 类型 + `triggerAlertCheck` 参数 |
| 7 | `frontend/app/settings/alerts/page.tsx` | 修改 | 新增每日摘要 Toggle |
| 8 | `backend/tests/services/test_daily_summary.py` | 新增 | 单元测试 |

---

## Step 1: `alert_config.py` — 新增 `daily_summary` 字段

**文件**: `backend/app/models/alert_config.py:68-81`

在 `UserAlertPreferences` 的 `weekly_signal` 和 `max_alerts_per_day` 之间插入：

```python
    # 每日摘要
    daily_summary: bool = True           # 每日市场摘要开关，默认开启
```

**验证**: 新字段有默认值，所有现有 `UserAlertPreferences(**alert_settings)` 调用不受影响。

---

## Step 2: `alert_state_service.py` — 信号详情存储 + 摘要去重

**文件**: `backend/app/services/alert_state_service.py`

### 2.1 新增 import

在文件顶部 `from app.models.alert_config import ETFAlertState` 后追加：

```python
from app.models.alert_config import ETFAlertState, SignalItem
```

### 2.2 新增缓存 key 生成方法

在 `_count_key()` 方法（第 36-39 行）之后新增：

```python
def _signal_detail_key(self, user_id: int) -> str:
    """生成当日信号详情缓存 key"""
    today = date.today().isoformat()
    return f"alert_signal_detail:{user_id}:{today}"

def _summary_sent_key(self, user_id: int) -> str:
    """生成摘要已发送缓存 key"""
    today = date.today().isoformat()
    return f"summary_sent:{user_id}:{today}"
```

### 2.3 修改 `mark_signal_sent()` — 同时存储信号详情

在现有 `mark_signal_sent()` 方法（第 73-92 行）的签名中新增 `signal_item` 参数，并在方法体末尾追加信号详情存储逻辑：

```python
def mark_signal_sent(
    self, user_id: int, etf_code: str, signal_type: str,
    signal_item: Optional["SignalItem"] = None
) -> None:
    """标记信号已发送（当天有效），同时存储信号详情供摘要使用"""
    try:
        key = self._sent_key(user_id, etf_code, signal_type)
        now = datetime.now()
        end_of_day = datetime(now.year, now.month, now.day, 23, 59, 59)
        ttl = int((end_of_day - now).total_seconds())

        if self._cache.get(key) is None:
            self._cache.set(key, True, expire=max(ttl, 1))
            count_key = self._count_key(user_id)
            current = self._cache.get(count_key, default=0)
            self._cache.set(count_key, current + 1, expire=max(ttl, 1))

        # 新增：存储信号详情供每日摘要使用
        if signal_item:
            detail_key = self._signal_detail_key(user_id)
            existing = self._cache.get(detail_key, default=[])
            existing.append(signal_item.model_dump())
            self._cache.set(detail_key, existing, expire=max(ttl, 1))
    except Exception as e:
        logger.error(f"Failed to mark signal sent: {e}")
```

**注意**: `signal_item` 参数可选且默认 `None`，现有调用方不受影响。

### 2.4 新增 `get_today_signals()`

在 `get_daily_sent_count()` 方法之后新增：

```python
def get_today_signals(self, user_id: int) -> list:
    """获取用户当日所有已触发的信号详情"""
    try:
        detail_key = self._signal_detail_key(user_id)
        data = self._cache.get(detail_key, default=[])
        return [SignalItem(**item) for item in data]
    except Exception as e:
        logger.error(f"Failed to get today signals: {e}")
        return []
```

### 2.5 新增摘要去重方法

在 `get_today_signals()` 之后新增：

```python
def is_summary_sent_today(self, user_id: int) -> bool:
    """检查今天是否已发送摘要"""
    try:
        key = self._summary_sent_key(user_id)
        return self._cache.get(key) is not None
    except Exception as e:
        logger.error(f"Failed to check summary sent: {e}")
        return False

def mark_summary_sent(self, user_id: int) -> None:
    """标记今天已发送摘要"""
    try:
        key = self._summary_sent_key(user_id)
        now = datetime.now()
        end_of_day = datetime(now.year, now.month, now.day, 23, 59, 59)
        ttl = int((end_of_day - now).total_seconds())
        self._cache.set(key, True, expire=max(ttl, 1))
    except Exception as e:
        logger.error(f"Failed to mark summary sent: {e}")
```

### 2.6 更新调用方：`alert_scheduler.py` 传入 `signal_item`

`_process_user_signals()` 方法（第 128-133 行）中现有调用：

```python
for signal in signals:
    alert_state_service.mark_signal_sent(
        user_id, etf_code, signal.signal_type
    )
```

改为：

```python
for signal in signals:
    alert_state_service.mark_signal_sent(
        user_id, etf_code, signal.signal_type, signal_item=signal
    )
```

---

## Step 3: `notification_service.py` — 新增 `format_daily_summary()`

**文件**: `backend/app/services/notification_service.py`

### 3.1 更新 import

将现有的 TYPE_CHECKING import 改为直接 import：

```python
from app.models.alert_config import SignalPriority, SignalItem, TemperatureLevel
```

删除 `TYPE_CHECKING` 相关的条件导入块。

### 3.2 新增 `format_daily_summary()` 方法

在 `format_alert_message()` 方法之后新增：

```python
@staticmethod
def format_daily_summary(
    items: List[dict],
    signals: List[SignalItem],
    date_str: str
) -> str:
    """格式化每日摘要消息（HTML 格式）

    Args:
        items: ETF 数据列表，每项含 code, name, change_pct, temperature_score, temperature_level
        signals: 当日已触发的告警信号
        date_str: 日期字符串，如 "2026-02-07 (周五)"
    """
    lines = [f"📋 <b>自选日报</b> | {date_str}", ""]

    # 涨跌概览
    up = sum(1 for i in items if i["change_pct"] > 0)
    down = sum(1 for i in items if i["change_pct"] < 0)
    flat = len(items) - up - down
    lines.append(f"📊 涨: {up} | 跌: {down} | 平: {flat}")
    lines.append("")

    # 排序
    sorted_items = sorted(items, key=lambda x: x["change_pct"], reverse=True)

    def fmt_item(item: dict) -> str:
        pct = item["change_pct"]
        sign = "+" if pct > 0 else ""
        score = item.get("temperature_score")
        temp_str = f"  🌡️{score:.0f}" if score is not None else ""
        return f"• {item['name']} ({item['code']})  {sign}{pct:.2f}%{temp_str}"

    if len(items) <= 3:
        # 自选 ≤ 3 只：直接展示完整列表
        for item in sorted_items:
            lines.append(fmt_item(item))
        lines.append("")
    else:
        # 涨幅前三
        gainers = [i for i in sorted_items if i["change_pct"] > 0]
        if gainers:
            lines.append("🔴 <b>涨幅前三</b>")
            for item in gainers[:3]:
                lines.append(fmt_item(item))
            lines.append("")

        # 跌幅前三
        losers = [i for i in sorted_items if i["change_pct"] < 0]
        if losers:
            lines.append("🟢 <b>跌幅前三</b>")
            for item in reversed(losers[-3:]):
                lines.append(fmt_item(item))
            lines.append("")

    # 今日信号
    if signals:
        lines.append(f"⚡ <b>今日信号</b> ({len(signals)})")
        for s in signals:
            lines.append(f"• {s.etf_code} {s.etf_name}: {s.signal_detail}")
        lines.append("")

    # 温度分布
    level_counts = {"freezing": 0, "cool": 0, "warm": 0, "hot": 0}
    for item in items:
        level = item.get("temperature_level")
        if level and level in level_counts:
            level_counts[level] += 1
    level_icons = {"freezing": "🥶", "cool": "❄️", "warm": "☀️", "hot": "🔥"}
    dist_parts = [f"{level_icons[k]} {k}: {v}" for k, v in level_counts.items()]
    lines.append(f"🌡️ {' | '.join(dist_parts)}")

    return "\n".join(lines)
```

---

## Step 4: `alert_scheduler.py` — 扩展用户收集 + 新增摘要任务

**文件**: `backend/app/services/alert_scheduler.py`

### 4.1 注册定时任务

在 `start()` 方法中，收盘后检查任务（第 58-64 行）之后、`self._scheduler.start()` 之前新增：

```python
# 每日摘要 (15:35，在告警检查之后)
self._scheduler.add_job(
    self._run_daily_summary,
    CronTrigger(hour=15, minute=35, day_of_week="mon-fri"),
    id="daily_summary",
    replace_existing=True,
)
logger.info("Daily summary scheduled: 15:35")
```

### 4.2 扩展 `_collect_etf_users()` — 新增 `for_summary` 参数

修改方法签名（第 294 行）：

```python
def _collect_etf_users(
    self, session: Session, user_id: Optional[int] = None,
    for_summary: bool = False
) -> Dict[str, List[Dict]]:
```

修改筛选逻辑（第 324 行附近），将：

```python
if not prefs.enabled:
```

改为：

```python
if for_summary:
    if not prefs.daily_summary:
        if user_id is not None:
            logger.info(f"User {user.id}: daily_summary not enabled")
        continue
else:
    if not prefs.enabled:
        if user_id is not None:
            logger.info(f"User {user.id}: alert not enabled")
        continue
```

其余逻辑（Telegram 检查、自选列表获取）不变。

### 4.3 新增 `_run_daily_summary()` 方法

在 `_run_daily_check()` 方法之后新增：

```python
async def _run_daily_summary(self) -> None:
    """执行每日摘要推送"""
    logger.info("Running daily summary...")

    with Session(engine) as session:
        etf_users_map = self._collect_etf_users(session, for_summary=True)

        if not etf_users_map:
            logger.info("No users for daily summary")
            return

        # 收集所有需要的 ETF 代码
        all_etf_codes = list(etf_users_map.keys())
        logger.info(f"Fetching data for {len(all_etf_codes)} ETFs")

        # 按 ETF 去重获取数据
        etf_data: Dict[str, Dict[str, Any]] = {}
        for etf_code in all_etf_codes:
            try:
                # 获取实时行情（涨跌幅）
                info = await asyncio.to_thread(
                    ak_service.get_etf_info, etf_code
                )
                # 获取历史数据并计算温度
                metrics = await self._fetch_and_compute_etf_metrics(etf_code)

                etf_data[etf_code] = {
                    "info": info,
                    "metrics": metrics,
                }
            except Exception as e:
                logger.error(f"Failed to fetch data for {etf_code}: {e}")

        # 按用户去重
        user_map: Dict[int, Dict] = {}
        for etf_code, users_data in etf_users_map.items():
            for ud in users_data:
                uid = ud["user"].id
                if uid not in user_map:
                    user_map[uid] = {
                        "user": ud["user"],
                        "telegram_config": ud["telegram_config"],
                        "etf_list": [],
                    }
                user_map[uid]["etf_list"].append({
                    "etf_code": etf_code,
                    "etf_name": ud["etf_name"],
                })

        # 为每个用户生成并发送摘要
        for uid, udata in user_map.items():
            await self._send_user_summary(uid, udata, etf_data)
```

### 4.4 新增 `_send_user_summary()` 方法

```python
async def _send_user_summary(
    self, user_id: int, udata: Dict, etf_data: Dict[str, Dict]
) -> None:
    """为单个用户生成并发送摘要"""
    # 去重保护
    if alert_state_service.is_summary_sent_today(user_id):
        logger.info(f"User {user_id}: summary already sent today")
        return

    # 组装 items
    items = []
    failed_count = 0
    for etf_item in udata["etf_list"]:
        code = etf_item["etf_code"]
        data = etf_data.get(code)
        if not data or not data.get("info"):
            failed_count += 1
            continue

        info = data["info"]
        metrics = data.get("metrics")
        temp = metrics.get("temperature") if metrics else None

        items.append({
            "code": code,
            "name": etf_item["etf_name"],
            "change_pct": info.get("change_pct", 0),
            "temperature_score": temp.get("score") if temp else None,
            "temperature_level": temp.get("level") if temp else None,
        })

    if not items:
        logger.info(f"User {user_id}: no valid ETF data for summary")
        return

    # 获取当日信号
    signals = alert_state_service.get_today_signals(user_id)

    # 格式化日期
    now = datetime.now()
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    date_str = f"{now.strftime('%Y-%m-%d')} ({weekdays[now.weekday()]})"

    message = TelegramNotificationService.format_daily_summary(
        items, signals, date_str
    )

    # 部分失败提示
    if failed_count > 0:
        message += f"\n\n⚠️ {failed_count} 只 ETF 数据获取失败"

    # 发送（含重试）
    bot_token = decrypt_token(
        udata["telegram_config"]["botToken"], settings.SECRET_KEY
    )
    chat_id = udata["telegram_config"]["chatId"]

    try:
        await TelegramNotificationService.send_message(
            bot_token, chat_id, message
        )
        alert_state_service.mark_summary_sent(user_id)
        logger.info(f"Daily summary sent to user {user_id}")
    except Exception as e:
        logger.warning(f"Summary send failed for user {user_id}, retrying: {e}")
        await asyncio.sleep(30)
        try:
            await TelegramNotificationService.send_message(
                bot_token, chat_id, message
            )
            alert_state_service.mark_summary_sent(user_id)
            logger.info(f"Daily summary sent to user {user_id} (retry)")
        except Exception as e2:
            logger.error(f"Summary retry failed for user {user_id}: {e2}")
```

### 4.5 扩展 `trigger_check()` — 支持手动触发摘要

修改 `trigger_check()` 方法（第 396-410 行）：

```python
async def trigger_check(
    self, user_id: Optional[int] = None, summary: bool = False
) -> dict:
    """手动触发检查（用于测试）"""
    try:
        if summary:
            if user_id is not None:
                await self._run_user_summary_manual(user_id)
            else:
                await self._run_daily_summary()
        else:
            if user_id is not None:
                await self._run_user_check(user_id)
            else:
                await self._run_daily_check()
        return {"success": True, "message": "检查完成"}
    except Exception as e:
        logger.error(f"Manual trigger failed: {e}")
        return {"success": False, "message": str(e)}
```

### 4.6 新增 `_run_user_summary_manual()` — 手动触发单用户摘要

```python
async def _run_user_summary_manual(self, user_id: int) -> None:
    """手动触发单用户摘要（不检查去重，不限时间）"""
    with Session(engine) as session:
        etf_users_map = self._collect_etf_users(
            session, user_id=user_id, for_summary=True
        )
        if not etf_users_map:
            logger.info(f"No ETFs for user {user_id} summary")
            return

        etf_data: Dict[str, Dict[str, Any]] = {}
        for etf_code in etf_users_map.keys():
            try:
                info = await asyncio.to_thread(
                    ak_service.get_etf_info, etf_code
                )
                metrics = await self._fetch_and_compute_etf_metrics(etf_code)
                etf_data[etf_code] = {"info": info, "metrics": metrics}
            except Exception as e:
                logger.error(f"Failed to fetch {etf_code}: {e}")

        # 组装用户数据
        first_data = list(etf_users_map.values())[0][0]
        udata = {
            "user": first_data["user"],
            "telegram_config": first_data["telegram_config"],
            "etf_list": [
                {"etf_code": code, "etf_name": uds[0]["etf_name"]}
                for code, uds in etf_users_map.items()
            ],
        }
        await self._send_user_summary(user_id, udata, etf_data)
```

**注意**: 手动触发不跳过去重检查（`is_summary_sent_today`），因为 `_send_user_summary` 内部已有去重。如需强制重发，可在手动触发前清除缓存，但第一版不做此功能。

---

## Step 5: `alerts.py` — API 字段扩展

**文件**: `backend/app/api/v1/endpoints/alerts.py`

### 5.1 `AlertConfigRequest` 和 `AlertConfigResponse` 新增字段

在两个类的 `weekly_signal` 之后、`max_alerts_per_day` 之前各新增：

```python
daily_summary: bool = True
```

### 5.2 `trigger` 端点新增 `summary` 参数

将现有 `trigger_alert_check`（第 70-76 行）改为：

```python
@router.post("/trigger")
async def trigger_alert_check(
    summary: bool = False,
    current_user: User = Depends(get_current_user),
):
    """手动触发告警检查或每日摘要"""
    result = await alert_scheduler.trigger_check(
        current_user.id, summary=summary
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result
```

---

## Step 6: 前端 — 类型扩展 + Toggle

### 6.1 `frontend/lib/api.ts` — `AlertConfig` 类型

在 `AlertConfig` 接口（第 161-170 行）的 `weekly_signal` 之后新增：

```typescript
export interface AlertConfig {
  enabled: boolean;
  temperature_change: boolean;
  extreme_temperature: boolean;
  rsi_signal: boolean;
  ma_crossover: boolean;
  ma_alignment: boolean;
  weekly_signal: boolean;
  daily_summary: boolean;    // 新增
  max_alerts_per_day: number;
}
```

### 6.2 `triggerAlertCheck` 新增 `summary` 参数

修改 `triggerAlertCheck` 函数（第 258-270 行）：

```typescript
export async function triggerAlertCheck(
  token: string,
  summary: boolean = false
): Promise<{ success: boolean; message: string }> {
  const url = summary
    ? `${API_BASE_URL}/alerts/trigger?summary=true`
    : `${API_BASE_URL}/alerts/trigger`;
  const response = await fetch(url, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: '触发检查失败' }));
    throw new Error(error.detail || '触发检查失败');
  }
  return response.json();
}
```

### 6.3 `frontend/app/settings/alerts/page.tsx` — 新增每日摘要 Toggle

**6.3.1 初始状态新增字段**

在 `useState<AlertConfig>` 的初始值（第 36-45 行）中新增：

```typescript
const [config, setConfig] = useState<AlertConfig>({
  enabled: true,
  temperature_change: true,
  extreme_temperature: true,
  rsi_signal: true,
  ma_crossover: true,
  ma_alignment: true,
  weekly_signal: true,
  daily_summary: true,       // 新增
  max_alerts_per_day: 20,
});
```

**6.3.2 新增每日摘要 Toggle**

在"主开关"section（第 148-161 行）的 `</section>` 之后、"信号类型"section 之前插入：

```tsx
{/* 每日摘要 */}
<section>
  <div className="bg-card rounded-xl overflow-hidden shadow-sm ring-1 ring-border/50">
    <div className="p-4 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <Calendar className="h-5 w-5 text-muted-foreground" />
        <div>
          <span className="text-base font-medium">每日市场摘要</span>
          <p className="text-xs text-muted-foreground">
            收盘后推送自选日报
          </p>
        </div>
      </div>
      <Toggle
        checked={config.daily_summary}
        onChange={(v) => setConfig({ ...config, daily_summary: v })}
      />
    </div>
  </div>
</section>
```

`Calendar` 图标已在现有 import 中（第 11 行），无需新增 import。

---

## Step 7: 单元测试

**文件**: `backend/tests/services/test_daily_summary.py`（新建）

### 7.1 测试用例清单

| 测试 | 说明 |
|------|------|
| `test_format_daily_summary_basic` | 基本格式化：涨跌概览、涨跌幅排行、温度分布 |
| `test_format_daily_summary_few_items` | 自选 ≤ 3 只时展示完整列表 |
| `test_format_daily_summary_all_up` | 全部上涨：只显示涨幅排行 |
| `test_format_daily_summary_all_down` | 全部下跌：只显示跌幅排行 |
| `test_format_daily_summary_no_signals` | 无信号时省略信号区块 |
| `test_format_daily_summary_with_signals` | 有信号时展示信号区块 |
| `test_mark_signal_sent_stores_detail` | `mark_signal_sent` 同时存储信号详情 |
| `test_get_today_signals` | `get_today_signals` 返回当日所有信号 |
| `test_summary_dedup` | `is_summary_sent_today` + `mark_summary_sent` 去重 |
| `test_collect_etf_users_for_summary` | `for_summary=True` 筛选逻辑正确 |

---

## Step 8: 文档更新（AGENTS.md）

根据 AGENTS.md 第 4.6 节规范，代码变更必须同步更新文档。

### 8.1 API 接口速查表（第 6 节）

新增一行：

```
| `/alerts/trigger?summary=true` | POST | 手动触发每日摘要 |
```

### 8.2 说明文档更新

在 `docs/README.md` 的实现文档索引中新增本文档链接。

---

## 验证清单

```
[ ] Step 1: UserAlertPreferences 新增 daily_summary 字段，默认值 True
[ ] Step 2: alert_state_service 新增信号详情存储 + 摘要去重方法
[ ] Step 3: format_daily_summary() 输出 HTML 格式正确
[ ] Step 4: _collect_etf_users(for_summary=True) 筛选逻辑正确
[ ] Step 4: _run_daily_summary() 定时任务注册成功
[ ] Step 4: 发送失败重试 1 次
[ ] Step 5: API 新增 daily_summary 字段 + trigger summary 参数
[ ] Step 6: 前端 Toggle 正常工作，初始值从后端加载
[ ] Step 7: 所有单元测试通过
[ ] Step 8: AGENTS.md API 表更新
[ ] 手动触发测试：POST /alerts/trigger?summary=true 收到 Telegram 摘要
```
