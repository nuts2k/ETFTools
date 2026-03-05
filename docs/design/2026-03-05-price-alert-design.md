# 到价提醒功能 - 设计文档

> 创建时间: 2026-03-05
> 状态: 待实现
> 关联路线图: FEATURE-ROADMAP.md #11

---

## 1. 功能定位

### 1.1 与现有告警系统的关系

到价提醒与现有信号告警是**互补关系**：

| | 信号告警（已有） | 到价提醒（本功能） |
|---|---------|---------|
| **触发方式** | 自动检测指标变化 | 用户主动设置目标价 |
| **触发条件** | 温度/RSI/均线等技术指标变化 | 价格穿越用户指定阈值 |
| **生命周期** | 持续监控，同类信号每日去重 | 一次性，触发后自动停用 |
| **用户心智** | "出了技术信号告诉我" | "到了我的目标价告诉我" |
| **配额关系** | 受 `max_alerts_per_day` 限制 | 独立，不受每日配额限制 |

### 1.2 核心价值

- 最直觉的提醒需求："沪深300 跌到 3.5 提醒我"
- 比技术指标告警更容易理解和使用，零学习成本
- 帮助用户执行投资计划，避免情绪化操作

---

## 2. 核心决策

| # | 决策项 | 选择 | 理由 |
|---|--------|------|------|
| 1 | 触发后行为 | 一次性，自动停用 | 符合"到价提醒"的语义直觉，避免重复打扰 |
| 2 | 检查频率 | 复用 30 分钟盘中检查 + 15:01 收盘补检 | 30 分钟对 ETF 足够；收盘补检确保日终价不漏 |
| 3 | 存储方案 | 独立数据库表 `price_alerts` | 需跨用户遍历活跃提醒，JSON 存储效率差 |
| 4 | 备注字段 | 有，可选 | 成本极低，触发时看到备注能想起操作计划 |
| 5 | 管理入口 | 详情页创建 + `/settings/alerts` 管理 | 集中管理，不增加导航入口 |
| 6 | 数量限制 | 每用户 20 个活跃提醒 | 防极端情况拖慢检查循环 |
| 7 | 配额关系 | 独立于每日告警配额 | 用户主动设置的提醒不应被信号告警吞掉 |
| 8 | 价格比较精度 | float + 0.0001 容差 | ETF 价格最多 3 位小数，容差到第 4 位避免浮点误判 |
| 9 | `updated_at` 更新 | service 层手动设置 | SQLModel `default_factory` 仅 INSERT 生效，UPDATE 需手动赋值 |
| 10 | 收盘补检时间 | 15:01（非 15:00） | 给数据源 API 返回收盘价留缓冲时间 |
| 11 | 已触发记录清理 | 30 天自动清理 | 挂在每日任务中，防止表无限增长 |
| 12 | ETF 代码校验 | 不校验 | 前端入口已保证有效性，YAGNI |
| 13 | 通知渠道 | 仅 Telegram | 与现有告警系统保持一致 |
| 14 | 创建弹窗组件 | PriceAlertButton 内专用实现 | 不做通用 BottomSheet 抽象，YAGNI |
| 15 | 批量操作 | 第一版不做 | 配合 30 天自动清理，逐条操作足够 |

---

## 3. 数据模型设计

### 3.1 PriceAlert 表

新增 SQLModel 表，使用 `create_db_and_tables()` 自动创建（项目未使用 Alembic）：

```python
class PriceAlertDirection(str, Enum):
    ABOVE = "above"  # 价格上穿目标价
    BELOW = "below"  # 价格下穿目标价

class PriceAlert(SQLModel, table=True):
    __tablename__ = "price_alerts"
    __table_args__ = (
        Index('idx_price_alerts_user_active', 'user_id', 'is_triggered'),
        Index('idx_price_alerts_active', 'is_triggered'),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    etf_code: str = Field(max_length=10, index=True)
    etf_name: str = Field(max_length=50)
    target_price: float
    direction: str = Field(max_length=10)  # "above" | "below"
    note: Optional[str] = Field(default=None, max_length=200)
    is_triggered: bool = Field(default=False)
    triggered_at: Optional[datetime] = Field(default=None)
    triggered_price: Optional[float] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    # 注意：updated_at 的 default_factory 仅在 INSERT 时生效
    # UPDATE 时需在 service 层手动设置 alert.updated_at = datetime.utcnow()
```

### 3.2 已触发记录清理

已触发超过 30 天的记录自动清理，挂在每日任务（如 15:30 daily_check）中：

```sql
DELETE FROM price_alerts WHERE is_triggered = true AND triggered_at < datetime('now', '-30 days');
```

### 3.3 索引设计

| 索引 | 字段 | 用途 |
|------|------|------|
| `idx_price_alerts_user_active` | `(user_id, is_triggered)` | 获取用户的活跃/已触发提醒列表 |
| `idx_price_alerts_active` | `(is_triggered)` | 调度器遍历所有活跃提醒 |

### 3.4 查询模式

```sql
-- 调度器检查：获取所有活跃提醒
SELECT * FROM price_alerts WHERE is_triggered = false;

-- 用户查询：获取我的所有提醒
SELECT * FROM price_alerts WHERE user_id = ? ORDER BY is_triggered, created_at DESC;

-- 用户查询：仅活跃提醒
SELECT * FROM price_alerts WHERE user_id = ? AND is_triggered = false;

-- 活跃提醒计数（限制检查）
SELECT COUNT(*) FROM price_alerts WHERE user_id = ? AND is_triggered = false;
```

---

## 4. API 设计

### 4.1 接口清单

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/v1/price-alerts` | 获取当前用户的所有提醒 |
| POST | `/api/v1/price-alerts` | 创建到价提醒 |
| PUT | `/api/v1/price-alerts/{id}` | 修改提醒（改价格/备注/重新启用） |
| DELETE | `/api/v1/price-alerts/{id}` | 删除提醒 |

### 4.2 请求/响应模型

**创建提醒：**

```
POST /api/v1/price-alerts
{
    "etf_code": "510300",
    "etf_name": "沪深300ETF",
    "target_price": 3.50,
    "direction": "below",
    "note": "到这个价加仓 2000 元"
}
```

**响应：**

```json
{
    "id": 1,
    "etf_code": "510300",
    "etf_name": "沪深300ETF",
    "target_price": 3.50,
    "direction": "below",
    "note": "到这个价加仓 2000 元",
    "is_triggered": false,
    "triggered_at": null,
    "triggered_price": null,
    "created_at": "2026-03-05T10:30:00Z"
}
```

**获取列表：**

```
GET /api/v1/price-alerts?active_only=false
```

返回按 `is_triggered ASC, created_at DESC` 排序（活跃的在前）。

**修改提醒（含重新启用）：**

```
PUT /api/v1/price-alerts/1
{
    "target_price": 3.40,
    "note": "调低目标价",
    "is_triggered": false      // 设为 false 即重新启用
}
```

所有字段均为可选，只更新传入的字段。将 `is_triggered` 改为 `false` 时自动清空 `triggered_at` 和 `triggered_price`。

### 4.3 校验规则

| 规则 | 说明 |
|------|------|
| `target_price > 0` | 价格必须为正数 |
| `direction` in `["above", "below"]` | 仅支持两个方向 |
| `note` 最长 200 字符 | 防止滥用 |
| 活跃提醒数 <= 20 | 创建时检查，超限返回 400 |
| 用户只能操作自己的提醒 | PUT/DELETE 时校验 `user_id` |

### 4.4 创建时的智能默认

创建提醒时，后端应获取 ETF 当前价格，自动推断 `direction`：

- 若 `target_price` < 当前价格 → 默认 `direction = "below"`
- 若 `target_price` > 当前价格 → 默认 `direction = "above"`
- 用户仍可显式指定 `direction` 覆盖默认值

前端在用户输入目标价后，也应据此自动选中方向，并允许用户修改。

---

## 5. 检查逻辑设计

### 5.1 调度集成

在现有 `AlertScheduler` 中新增价格提醒检查：

```
AlertScheduler (已有)
  ├── _run_intraday_check()     ← 09:00-14:59 每 30 分钟（已有）
  │     └── + _check_price_alerts()  ← 新增：顺带检查到价提醒
  ├── _run_daily_check()        ← 15:30 告警检查（已有）
  ├── _run_daily_summary()      ← 15:35 每日摘要（已有）
  └── _run_closing_price_check() ← 15:01 收盘补检（新增）
        └── 仅检查到价提醒，不做信号检测
```

### 5.2 收盘补检任务

```python
# 新增定时任务：15:01 收盘价格检查
self._scheduler.add_job(
    self._run_closing_price_check,
    CronTrigger(hour=15, minute=1, day_of_week="mon-fri"),
    id="closing_price_check",
    replace_existing=True,
)
```

15:01 选择的原因：
- A 股 15:00 收盘，延迟 1 分钟确保数据源 API 已返回收盘价
- 早于 15:30 的每日告警检查，不冲突
- 确保收盘价不被 30 分钟检查遗漏（14:30 → 15:00 之间的变动）

### 5.3 检查逻辑

```python
async def _check_price_alerts(self, etf_prices: Dict[str, float]):
    """
    检查所有活跃的到价提醒。

    参数:
        etf_prices: {etf_code: current_price} 映射，复用已获取的价格数据
    """
    # 1. 查询所有 is_triggered=false 的提醒
    active_alerts = session.exec(
        select(PriceAlert).where(PriceAlert.is_triggered == false())
    ).all()

    # 2. 逐个检查是否满足触发条件
    triggered = []
    for alert in active_alerts:
        current_price = etf_prices.get(alert.etf_code)
        if current_price is None:
            continue  # 该 ETF 价格获取失败，跳过

        if _should_trigger(alert, current_price):
            alert.is_triggered = True
            alert.triggered_at = datetime.utcnow()
            alert.triggered_price = current_price
            triggered.append(alert)

    # 3. 批量更新数据库
    session.commit()

    # 4. 按用户分组发送通知
    by_user = group_by(triggered, key=lambda a: a.user_id)
    for user_id, alerts in by_user.items():
        await _send_price_alert_notification(user_id, alerts)


def _should_trigger(alert: PriceAlert, current_price: float) -> bool:
    EPSILON = 0.0001  # 容差：ETF 价格最多 3 位小数，第 4 位容差避免浮点误判
    if alert.direction == "below":
        return current_price <= alert.target_price + EPSILON
    elif alert.direction == "above":
        return current_price >= alert.target_price - EPSILON
    return False
```

### 5.4 价格数据复用

盘中检查（`_run_intraday_check`）已经在获取 ETF 实时价格用于信号检测。到价提醒检查直接复用这些价格数据，**不额外请求 API**：

```
_run_intraday_check()
  ├── 获取所有用户自选 ETF 列表
  ├── 批量获取实时价格 → etf_prices dict
  ├── 执行信号检测（已有逻辑）
  └── _check_price_alerts(etf_prices)   ← 新增，复用 etf_prices
```

**注意事项：** 到价提醒可能涉及不在任何用户自选中的 ETF（用户删除自选但保留了提醒）。需要：
1. 先收集活跃提醒中的 ETF 代码
2. 与自选 ETF 合并后一起获取价格
3. 或者：创建提醒时要求 ETF 必须在自选中（更简单，推荐）

**推荐方案：** 创建提醒时不限制必须在自选中，但检查时将活跃提醒的 ETF 代码合并到价格获取列表中。这样用户删除自选后提醒仍有效。

### 5.5 收盘补检的价格获取

15:01 收盘补检是独立任务，需要单独获取价格：

```python
async def _run_closing_price_check(self):
    """15:01 收盘价格检查 - 仅检查到价提醒"""
    # 1. 获取所有活跃提醒涉及的 ETF 代码
    active_alerts = _get_active_alerts()
    if not active_alerts:
        return

    etf_codes = set(a.etf_code for a in active_alerts)

    # 2. 获取这些 ETF 的当前价格
    etf_prices = await _fetch_prices(etf_codes)

    # 3. 检查并触发
    await _check_price_alerts(etf_prices)
```

---

## 6. 通知消息设计

### 6.1 Telegram 消息模板

**单个提醒触发：**

```
🔔 到价提醒

沪深300ETF (510300)
当前价格: <b>3.48</b> ⬇️ 跌破 3.50

📝 到这个价加仓 2000 元

⏰ 2026-03-05 14:30
```

**多个提醒同时触发：**

```
🔔 到价提醒 (2 个触发)

📌 沪深300ETF (510300)
   当前: <b>3.48</b> ⬇️ 跌破 3.50
   📝 到这个价加仓 2000 元

📌 中证500ETF (510500)
   当前: <b>6.12</b> ⬆️ 突破 6.10

⏰ 2026-03-05 14:30
```

### 6.2 设计原则

1. **方向标识清晰** — ⬇️ 跌破 / ⬆️ 突破，一眼看出方向
2. **目标价突出** — 当前价格加粗，目标价紧跟其后
3. **备注跟随** — 有备注才显示，无备注省略 📝 行
4. **时间戳** — 标注触发检测时间，让用户知道是实时还是延迟
5. **HTML 格式** — 与现有告警消息保持一致（`parse_mode="HTML"`）

### 6.3 每日摘要中的集成

在已有的每日市场摘要消息中，可增加一行到价提醒状态：

```
📋 自选日报 | 2026-03-05 (周三)

... 现有内容 ...

🔔 到价提醒: 2 个待触发
```

仅作为提示，不展开详情。此集成为可选优化，第一版可不做。

---

## 7. 前端设计

### 7.1 ETF 详情页 — 创建入口

在价格区域添加铃铛图标按钮，点击后弹出创建弹窗：

```
┌─ ETF 详情 ───────────────────────────────┐
│                                           │
│  沪深300ETF (510300)                       │
│  3.52  +0.28%  🔔                         │
│         价格旁的铃铛图标 ↗                 │
│                                           │
└───────────────────────────────────────────┘
```

**创建弹窗（PriceAlertButton 内置，不做通用 BottomSheet 抽象）：**

```
┌─ 设置到价提醒 ────────────────────────────┐
│                                           │
│  沪深300ETF (510300)                       │
│  当前价格: 3.52                            │
│                                           │
│  目标价格  [ 3.40        ]                │
│                                           │
│  提醒方向                                  │
│  [⬇️ 跌破]  [⬆️ 突破]                     │
│  (根据目标价自动选中，可手动切换)          │
│                                           │
│  备注（可选）                              │
│  [ 到这个价加仓 2000 元   ]               │
│                                           │
│  [取消]           [确认设置]              │
│                                           │
└───────────────────────────────────────────┘
```

**交互细节：**
- 输入目标价后，自动根据与当前价的关系选中方向
- 方向按钮可手动切换
- 确认后 Toast 提示"提醒设置成功"
- 如果该 ETF 已有活跃提醒，铃铛图标高亮显示

### 7.2 告警设置页 — 管理区域

在 `/settings/alerts` 页面现有内容下方新增"到价提醒"区域：

```
┌─ 信号通知设置 ─────────────────────────────┐
│  ... 现有信号开关 ...                      │
│  ... 每日摘要开关 ...                      │
└────────────────────────────────────────────┘

┌─ 到价提醒 (3/20) ─────────────────────────┐
│                                           │
│  [活跃]  [已触发]              ← 标签筛选  │
│                                           │
│  ┌───────────────────────────────────┐    │
│  │ 沪深300ETF (510300)               │    │
│  │ ⬇️ 跌破 3.50                      │    │
│  │ 📝 到这个价加仓 2000 元           │    │
│  │ 设置于 03-05                [删除] │    │
│  └───────────────────────────────────┘    │
│                                           │
│  ┌───────────────────────────────────┐    │
│  │ 中证500ETF (510500)               │    │
│  │ ⬆️ 突破 6.10                      │    │
│  │ 设置于 03-04                [删除] │    │
│  └───────────────────────────────────┘    │
│                                           │
│  [已触发] 标签下:                          │
│  ┌───────────────────────────────────┐    │
│  │ ✅ 创业板ETF (159915)             │    │
│  │ ⬇️ 跌破 2.00 → 实际 1.98         │    │
│  │ 触发于 03-03 14:30                │    │
│  │               [重新启用]  [删除]  │    │
│  └───────────────────────────────────┘    │
│                                           │
└────────────────────────────────────────────┘
```

**交互细节：**
- 标题显示活跃数量和上限（3/20）
- 活跃提醒支持删除
- 已触发提醒显示触发时的实际价格和时间
- 已触发提醒支持"重新启用"（调 PUT 接口将 `is_triggered` 设为 false）
- 已触发提醒支持删除
- Telegram 未配置时，整个区域显示提示"请先配置 Telegram"

---

## 8. 后端改动清单

### 8.1 新增文件

| 文件 | 说明 |
|------|------|
| `backend/app/models/price_alert.py` | PriceAlert 模型 + Pydantic 请求/响应模型 |
| `backend/app/api/v1/endpoints/price_alerts.py` | CRUD API 端点 |
| `backend/app/services/price_alert_service.py` | 业务逻辑（创建/查询/检查/触发） |

### 8.2 修改文件

| 文件 | 改动 |
|------|------|
| `backend/app/main.py` | 注册 price_alerts 路由 |
| `backend/app/api/v1/router.py` | 挂载 price_alerts 端点 |
| `backend/app/services/alert_scheduler.py` | 盘中检查集成 + 新增 15:01 收盘补检任务 |
| `backend/app/services/notification_service.py` | 新增 `format_price_alert_message()` |

### 8.3 模型文件详情

`backend/app/models/price_alert.py`:

```python
from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import SQLModel, Field, Index


class PriceAlertDirection(str, Enum):
    ABOVE = "above"
    BELOW = "below"


class PriceAlert(SQLModel, table=True):
    """到价提醒"""
    __tablename__ = "price_alerts"
    __table_args__ = (
        Index('idx_price_alerts_user_active', 'user_id', 'is_triggered'),
        Index('idx_price_alerts_active', 'is_triggered'),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    etf_code: str = Field(max_length=10, index=True)
    etf_name: str = Field(max_length=50)
    target_price: float
    direction: str = Field(max_length=10)
    note: Optional[str] = Field(default=None, max_length=200)
    is_triggered: bool = Field(default=False)
    triggered_at: Optional[datetime] = Field(default=None)
    triggered_price: Optional[float] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    # 注意：updated_at 仅 INSERT 时自动设置，UPDATE 需 service 层手动赋值


# --- Pydantic 请求/响应模型 ---

class PriceAlertCreate(BaseModel):
    etf_code: str
    etf_name: str
    target_price: float = PydanticField(gt=0)
    direction: Optional[PriceAlertDirection] = None  # 可选，后端可自动推断
    note: Optional[str] = PydanticField(default=None, max_length=200)


class PriceAlertUpdate(BaseModel):
    target_price: Optional[float] = PydanticField(default=None, gt=0)
    direction: Optional[PriceAlertDirection] = None
    note: Optional[str] = PydanticField(default=None, max_length=200)
    is_triggered: Optional[bool] = None  # 设为 false 即重新启用


class PriceAlertResponse(BaseModel):
    id: int
    etf_code: str
    etf_name: str
    target_price: float
    direction: str
    note: Optional[str]
    is_triggered: bool
    triggered_at: Optional[datetime]
    triggered_price: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True
```

### 8.4 alert_scheduler.py 改动

```python
# --- 新增定时任务注册 ---

def start(self):
    # ... 现有任务 ...

    # 15:01 收盘价格提醒补检
    self._scheduler.add_job(
        self._run_closing_price_check,
        CronTrigger(
            hour=15, minute=1,
            day_of_week="mon-fri",
            timezone=ZoneInfo("Asia/Shanghai")
        ),
        id="closing_price_check",
        replace_existing=True,
    )


# --- 盘中检查扩展 ---

async def _run_intraday_check(self):
    # ... 现有信号检测逻辑 ...

    # 复用已获取的价格数据检查到价提醒
    await self._check_price_alerts(etf_prices)


# --- 新增方法 ---

async def _run_closing_price_check(self):
    """15:01 收盘补检 - 仅检查到价提醒"""
    from app.services.price_alert_service import PriceAlertService
    await PriceAlertService.check_and_trigger()


async def _check_price_alerts(self, etf_prices: dict):
    """在盘中检查中顺带检查到价提醒"""
    from app.services.price_alert_service import PriceAlertService
    await PriceAlertService.check_and_trigger(etf_prices)
```

### 8.5 notification_service.py 改动

新增 `format_price_alert_message()` 静态方法：

```python
@staticmethod
def format_price_alert_message(alerts: list, check_time: datetime) -> str:
    """格式化到价提醒消息（HTML 格式）"""
    if len(alerts) == 1:
        a = alerts[0]
        direction_emoji = "⬇️" if a.direction == "below" else "⬆️"
        direction_text = "跌破" if a.direction == "below" else "突破"
        msg = f"🔔 到价提醒\n\n"
        msg += f"{a.etf_name} ({a.etf_code})\n"
        msg += f"当前价格: <b>{a.triggered_price}</b> {direction_emoji} {direction_text} {a.target_price}\n"
        if a.note:
            msg += f"\n📝 {a.note}\n"
        msg += f"\n⏰ {check_time.strftime('%Y-%m-%d %H:%M')}"
        return msg
    else:
        msg = f"🔔 到价提醒 ({len(alerts)} 个触发)\n"
        for a in alerts:
            direction_emoji = "⬇️" if a.direction == "below" else "⬆️"
            direction_text = "跌破" if a.direction == "below" else "突破"
            msg += f"\n📌 {a.etf_name} ({a.etf_code})\n"
            msg += f"   当前: <b>{a.triggered_price}</b> {direction_emoji} {direction_text} {a.target_price}\n"
            if a.note:
                msg += f"   📝 {a.note}\n"
        msg += f"\n⏰ {check_time.strftime('%Y-%m-%d %H:%M')}"
        return msg
```

---

## 9. 前端改动清单

### 9.1 新增文件

| 文件 | 说明 |
|------|------|
| `frontend/components/PriceAlertButton.tsx` | 详情页铃铛图标 + 创建弹窗 |
| `frontend/components/PriceAlertList.tsx` | 提醒管理列表（用于 settings 页） |

### 9.2 修改文件

| 文件 | 改动 |
|------|------|
| `frontend/lib/api.ts` | 新增 price-alerts CRUD API 调用函数 |
| `frontend/app/settings/alerts/page.tsx` | 底部新增到价提醒管理区域 |
| ETF 详情页组件 | 价格旁添加 `<PriceAlertButton>` |

### 9.3 api.ts 新增函数

```typescript
// --- 到价提醒 ---

export interface PriceAlertItem {
  id: number;
  etf_code: string;
  etf_name: string;
  target_price: number;
  direction: "above" | "below";
  note: string | null;
  is_triggered: boolean;
  triggered_at: string | null;
  triggered_price: number | null;
  created_at: string;
}

export async function getPriceAlerts(
  token: string,
  activeOnly?: boolean
): Promise<PriceAlertItem[]>;

export async function createPriceAlert(
  token: string,
  data: {
    etf_code: string;
    etf_name: string;
    target_price: number;
    direction?: "above" | "below";
    note?: string;
  }
): Promise<PriceAlertItem>;

export async function updatePriceAlert(
  token: string,
  id: number,
  data: Partial<{
    target_price: number;
    direction: "above" | "below";
    note: string;
    is_triggered: boolean;
  }>
): Promise<PriceAlertItem>;

export async function deletePriceAlert(
  token: string,
  id: number
): Promise<{ message: string }>;
```

---

## 10. 边界情况处理

| 场景 | 处理方式 |
|------|---------|
| 活跃提醒达到 20 个上限 | 创建时返回 400，提示用户删除旧提醒或等待触发 |
| ETF 退市或停牌（价格获取失败） | 跳过该提醒，不触发也不报错；下次检查继续尝试 |
| 价格在两次检查间快速穿越又回来 | 会漏掉。30 分钟检查频率的已知限制，文档中说明 |
| 目标价 = 当前价 | 允许创建，下次检查时会立即触发 |
| 用户创建提醒后删除自选 | 提醒仍然有效，检查时合并 ETF 到价格获取列表 |
| 用户 Telegram 未配置 | 提醒正常检查和触发（数据库状态更新），但通知发送跳过 |
| 同一 ETF 同方向重复创建 | 允许。用户可能想设多个目标价位（如 3.5、3.3、3.0） |
| 非交易日 | 不检查（cron `day_of_week="mon-fri"` + 15:01 收盘检查） |
| 节假日（工作日但休市） | 第一版不处理；检查时价格不变，不会误触发 |
| 并发触发（盘中 + 收盘补检同时触发同一提醒） | `is_triggered` 字段保证幂等，第二次检查时已跳过 |

---

## 11. 实施步骤

按以下顺序实施，每步可独立验证：

```
Step 1: 数据模型
  - 新增 price_alert.py（SQLModel 表 + Pydantic 模型）
  - 确保 create_db_and_tables() 能自动创建表

Step 2: 业务服务
  - 新增 price_alert_service.py
  - 实现 CRUD + check_and_trigger() 核心检查逻辑

Step 3: API 端点
  - 新增 price_alerts.py 端点
  - 注册路由，手动测试 CRUD

Step 4: 通知格式
  - notification_service.py 新增 format_price_alert_message()

Step 5: 调度器集成
  - alert_scheduler.py 盘中检查末尾调用 _check_price_alerts()
  - 新增 15:01 收盘补检任务
  - 新增已触发记录 30 天自动清理（挂在 daily_check 中）

Step 6: 前端 — API 层
  - api.ts 新增 price-alerts 相关函数

Step 7: 前端 — 创建入口
  - PriceAlertButton 组件（铃铛图标 + 弹窗）
  - 集成到 ETF 详情页

Step 8: 前端 — 管理列表
  - PriceAlertList 组件
  - 集成到 /settings/alerts 页面

Step 9: 端到端测试
  - 创建提醒 → 手动触发检查 → 验证 Telegram 收到通知
```

预估总改动量：后端 ~250 行新增，前端 ~350 行新增。

---

## 12. 验证方案

### 12.1 单元测试

- `_should_trigger()` 方向判断逻辑
- 活跃提醒数量限制校验
- 创建时方向自动推断
- 重新启用时字段清空

### 12.2 API 测试

- CRUD 全流程
- 权限校验（只能操作自己的提醒）
- 数量限制边界（第 20 个通过，第 21 个拒绝）
- 参数校验（负数价格、超长备注）

### 12.3 集成测试

- 模拟价格数据 → 调用 check_and_trigger() → 验证触发结果
- 盘中检查中到价提醒的集成
- Telegram 消息格式验证

### 12.4 端到端验证

1. 创建到价提醒
2. 通过 `/alerts/trigger` 手动触发检查
3. 验证 Telegram 收到格式正确的消息
4. 验证提醒状态变为已触发
5. 重新启用 → 再次触发 → 再次收到通知
