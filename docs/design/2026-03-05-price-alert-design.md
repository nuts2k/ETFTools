# 到价提醒功能 - 设计文档

> 创建时间: 2026-03-05
> 修订时间: 2026-03-09（基于设计评审结果全面修订）
> 状态: 已实现
> 关联路线图: FEATURE-ROADMAP.md #11
> 评审文档: docs/planning/2026-03-08-price-alert-design-review.md

---

## 1. 功能定位

### 1.1 与现有告警系统的关系

到价提醒与现有信号告警是**互补关系**：

| | 信号告警（已有） | 到价提醒（本功能） |
|---|---------|---------|
| **触发方式** | 自动检测指标变化 | 用户主动设置目标价 |
| **触发条件** | 温度/RSI/均线等技术指标变化 | 价格到达用户指定目标价 |
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
| 1 | 触发语义 | **到达目标价**（非"穿越"） | 符合"到价提醒"的日常表达，实现简单、语义稳定 |
| 2 | 已满足条件时创建 | **拒绝创建 + 提示原因** | 当前价已满足则无需"提醒"，避免创建后立即触发的困惑 |
| 3 | 触发后行为 | 一次性，自动停用 | 符合"到价提醒"的语义直觉，避免重复打扰 |
| 4 | 检查频率 | 复用 30 分钟盘中检查 + 15:01 收盘补检 | 30 分钟对 ETF 足够；收盘补检确保日终价不漏 |
| 5 | 存储方案 | 独立数据库表 `price_alerts` | 需跨用户遍历活跃提醒，JSON 存储效率差 |
| 6 | 备注字段 | 有，可选 | 成本极低，触发时看到备注能想起操作计划 |
| 7 | 管理入口 | 详情页创建 + `/settings/alerts` 管理 | 创建在详情页是自然场景（看着价格设目标），集中管理不增加导航入口 |
| 8 | 数量限制 | 每用户 20 个活跃提醒 | 防极端情况拖慢检查循环 |
| 9 | 配额关系 | 独立于每日告警配额 | 用户主动设置的提醒不应被信号告警吞掉 |
| 10 | 价格比较精度 | float + 0.0001 容差 | ETF 价格最多 3 位小数，容差到第 4 位避免浮点误判 |
| 11 | 收盘补检时间 | 15:01（非 15:00） | 给数据源 API 返回收盘价留缓冲时间 |
| 12 | 已触发记录清理 | 30 天自动清理 | 挂在每日任务中，防止表无限增长 |
| 13 | ETF 代码校验 | 6 位数字格式校验 | 防止垃圾数据拖慢检查循环，不做是否真实存在的校验 |
| 14 | 通知渠道 | 仅 Telegram | 与现有告警系统保持一致 |
| 15 | Telegram 未配置 | 禁止创建提醒 | 避免"设了但收不到"的困惑，引导用户先配置 |
| 16 | 创建弹窗组件 | PriceAlertButton 内专用实现 | 不做通用 BottomSheet 抽象，YAGNI |
| 17 | 批量操作 | V1 不做 | 配合 30 天自动清理，逐条操作足够 |
| 18 | 重新启用 | V1 不做 | 删了重建即可，减少 API 复杂度 |
| 19 | PUT 修改接口 | V1 不做 | 删了重建即可，少一套校验逻辑 |
| 20 | 并发保护 | 调度器层面互斥 | 盘中检查与收盘补检时间不重叠 + `max_instances=1` |
| 21 | 通知失败处理 | V1 不处理 | 概率低，设置页可查看已触发记录 |
| 22 | 通知消息安全 | HTML escape 用户字段 | `etf_name` 和 `note` 在拼入 Telegram HTML 消息前转义 |

---

## 3. V1 范围定义

### 3.1 V1 核心范围

- 数据模型（`price_alerts` 表）
- API：GET 列表 / POST 创建 / DELETE 删除（3 个端点）
- 创建校验：目标价 > 0、etf_code 6 位数字、备注 <= 200 字、活跃数 <= 20、当前价未满足条件、Telegram 已配置
- 方向自动推断（后端根据当前价与目标价自动设置 direction）
- 调度检查（复用盘中 30 分钟检查 + 15:01 收盘补检）
- 触发通知（Telegram 消息，HTML escape 用户字段）
- 前端创建入口（详情页铃铛按钮 + 创建弹窗）
- 前端管理（`/settings/alerts` 页面展示活跃/已触发列表，支持删除）
- 自动清理（已触发 30 天后自动删除）

### 3.2 明确推后（V1 不做）

| 项目 | 原因 |
|------|------|
| 重新启用已触发提醒 | 删了重建即可 |
| PUT 修改接口 | 删了重建即可 |
| 设置页创建入口 | 详情页创建是自然场景 |
| 通知失败补偿/重试 | 概率低，设置页可查看状态 |
| 数据库级并发保护 | 调度器层面互斥已够用 |
| 收盘价有效性校验 | 数据源可靠性足够 |
| 交易日历 | mon-fri + 创建时校验兜底 |
| 每日摘要集成 | 非核心 |
| 批量操作 | 配合 30 天清理，逐条足够 |

---

## 4. 数据模型设计

### 4.1 PriceAlert 表

新增 SQLModel 表，使用 `create_db_and_tables()` 自动创建（项目未使用 Alembic）：

```python
class PriceAlertDirection(str, Enum):
    ABOVE = "above"  # 价格到达目标价上方
    BELOW = "below"  # 价格到达目标价下方

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
```

### 4.2 已触发记录清理

已触发超过 30 天的记录自动清理，挂在每日任务（如 15:30 daily_check）中：

```sql
DELETE FROM price_alerts WHERE is_triggered = true AND triggered_at < datetime('now', '-30 days');
```

### 4.3 索引设计

| 索引 | 字段 | 用途 |
|------|------|------|
| `idx_price_alerts_user_active` | `(user_id, is_triggered)` | 获取用户的活跃/已触发提醒列表 |
| `idx_price_alerts_active` | `(is_triggered)` | 调度器遍历所有活跃提醒 |

注：当前索引为初版设计，后续可根据查询慢日志调整。

### 4.4 查询模式

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

## 5. API 设计

### 5.1 接口清单

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/v1/price-alerts` | 获取当前用户的所有提醒 |
| POST | `/api/v1/price-alerts` | 创建到价提醒 |
| DELETE | `/api/v1/price-alerts/{id}` | 删除提醒 |

### 5.2 请求/响应模型

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

**成功响应：**

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

**已满足条件时的拒绝响应：**

```json
{
    "detail": "当前价格 3.48 已满足该提醒条件（跌破 3.50），无需设置提醒"
}
```
HTTP 400

**获取列表：**

```
GET /api/v1/price-alerts?active_only=false
```

返回按 `is_triggered ASC, created_at DESC` 排序（活跃的在前）。

**删除提醒：**

```
DELETE /api/v1/price-alerts/1
```

### 5.3 校验规则

| 规则 | 说明 |
|------|------|
| `target_price > 0` | 价格必须为正数 |
| `etf_code` 为 6 位数字 | 正则 `^\d{6}$`，防止垃圾数据 |
| `direction` in `["above", "below"]` | 仅支持两个方向 |
| `note` 最长 200 字符 | 防止滥用 |
| 活跃提醒数 <= 20 | 创建时检查，超限返回 400 |
| 当前价格未满足条件 | 创建时获取当前价格，已满足则拒绝并提示 |
| Telegram 已配置 | 未配置时返回 400，提示先配置 Telegram |
| 用户只能操作自己的提醒 | DELETE 时校验 `user_id` |

### 5.4 创建时的智能默认

创建提醒时，后端获取 ETF 当前价格，自动推断 `direction`：

- 若 `target_price` < 当前价格 → 默认 `direction = "below"`
- 若 `target_price` > 当前价格 → 默认 `direction = "above"`
- 用户仍可显式指定 `direction` 覆盖默认值

前端在用户输入目标价后，也应据此自动选中方向，并允许用户修改。

---

## 6. 检查逻辑设计

### 6.1 调度集成

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

### 6.2 收盘补检任务

```python
# 新增定时任务：15:01 收盘价格检查
self._scheduler.add_job(
    self._run_closing_price_check,
    CronTrigger(
        hour=15, minute=1,
        day_of_week="mon-fri",
        timezone=ZoneInfo("Asia/Shanghai")
    ),
    id="closing_price_check",
    replace_existing=True,
    max_instances=1,  # 防止重入
)
```

15:01 选择的原因：
- A 股 15:00 收盘，延迟 1 分钟确保数据源 API 已返回收盘价
- 早于 15:30 的每日告警检查，不冲突
- 确保收盘价不被 30 分钟检查遗漏（14:30 → 15:00 之间的变动）

注：依赖数据源（akshare/东方财富）在 15:01 返回有效收盘价。

### 6.3 检查逻辑

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

### 6.4 价格数据复用

盘中检查（`_run_intraday_check`）已经在获取 ETF 实时价格用于信号检测。到价提醒检查直接复用这些价格数据，**不额外请求 API**：

```
_run_intraday_check()
  ├── 获取所有用户自选 ETF 列表
  ├── 合并活跃提醒中的 ETF 代码（可能不在任何用户自选中）
  ├── 批量获取实时价格 → etf_prices dict
  ├── 执行信号检测（已有逻辑）
  └── _check_price_alerts(etf_prices)   ← 新增，复用 etf_prices
```

到价提醒可能涉及不在任何用户自选中的 ETF（用户删除自选但保留了提醒）。处理方式：将活跃提醒的 ETF 代码合并到价格获取列表中，确保用户删除自选后提醒仍有效。

### 6.5 收盘补检的价格获取

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

### 6.6 并发保护

盘中检查和收盘补检在时间上天然不重叠（盘中最后一次 14:30，收盘补检 15:01）。额外通过 `max_instances=1` 保证同一任务不会重入。

---

## 7. 通知消息设计

### 7.1 Telegram 消息模板

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

### 7.2 设计原则

1. **方向标识清晰** — ⬇️ 跌破 / ⬆️ 突破，一眼看出方向
2. **目标价突出** — 当前价格加粗，目标价紧跟其后
3. **备注跟随** — 有备注才显示，无备注省略 📝 行
4. **时间戳** — 标注触发检测时间，让用户知道是实时还是延迟
5. **HTML 格式** — 与现有告警消息保持一致（`parse_mode="HTML"`）
6. **安全转义** — `etf_name` 和 `note` 在拼入消息前必须 HTML escape，防止用户输入破坏消息格式

### 7.3 时间处理约定

- 数据库存储：UTC（`datetime.utcnow()`）
- 调度器 CronTrigger：`timezone=ZoneInfo("Asia/Shanghai")`
- Telegram 消息时间：转换为北京时间显示
- API 返回时间：与项目现有约定保持一致

---

## 8. 前端设计

### 8.1 Telegram 配置检查

点击铃铛按钮时，若用户未配置 Telegram，直接提示"请先配置 Telegram 通知"并引导跳转到设置页。不弹出创建弹窗。

### 8.2 ETF 详情页 — 创建入口

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

**创建弹窗（PriceAlertButton 内置）：**

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
- 后端返回"当前价格已满足条件"错误时，弹窗内显示错误提示，不关闭弹窗

### 8.3 告警设置页 — 管理区域

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
│  │ 触发于 03-03 14:30          [删除] │    │
│  └───────────────────────────────────┘    │
│                                           │
│  Telegram 未配置时:                        │
│  ┌───────────────────────────────────┐    │
│  │ 💡 请先配置 Telegram 通知才能      │    │
│  │    创建到价提醒 [去配置]           │    │
│  └───────────────────────────────────┘    │
│                                           │
└────────────────────────────────────────────┘
```

**交互细节：**
- 标题显示活跃数量和上限（3/20）
- 活跃提醒和已触发提醒均支持删除
- 已触发提醒显示触发时的实际价格和时间
- 设置页只管理（查看、删除），不提供创建入口
- Telegram 未配置时，显示引导提示

---

## 9. 后端改动清单

### 9.1 新增文件

| 文件 | 说明 |
|------|------|
| `backend/app/models/price_alert.py` | PriceAlert 模型 + Pydantic 请求/响应模型 |
| `backend/app/api/v1/endpoints/price_alerts.py` | GET / POST / DELETE 端点 |
| `backend/app/services/price_alert_service.py` | 业务逻辑（创建/查询/检查/触发） |

### 9.2 修改文件

| 文件 | 改动 |
|------|------|
| `backend/app/main.py` | 注册 price_alerts 路由 |
| `backend/app/api/v1/router.py` | 挂载 price_alerts 端点 |
| `backend/app/services/alert_scheduler.py` | 盘中检查集成 + 新增 15:01 收盘补检任务 |
| `backend/app/services/notification_service.py` | 新增 `format_price_alert_message()` |

### 9.3 模型文件详情

`backend/app/models/price_alert.py`:

```python
import re
from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field as PydanticField, field_validator
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


# --- Pydantic 请求/响应模型 ---

class PriceAlertCreate(BaseModel):
    etf_code: str
    etf_name: str
    target_price: float = PydanticField(gt=0)
    direction: Optional[PriceAlertDirection] = None  # 可选，后端可自动推断
    note: Optional[str] = PydanticField(default=None, max_length=200)

    @field_validator('etf_code')
    @classmethod
    def validate_etf_code(cls, v: str) -> str:
        if not re.match(r'^\d{6}$', v):
            raise ValueError('ETF 代码必须为 6 位数字')
        return v


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

### 9.4 alert_scheduler.py 改动

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
        max_instances=1,
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

### 9.5 notification_service.py 改动

新增 `format_price_alert_message()` 静态方法：

```python
from html import escape as html_escape

@staticmethod
def format_price_alert_message(alerts: list, check_time: datetime) -> str:
    """格式化到价提醒消息（HTML 格式）"""
    if len(alerts) == 1:
        a = alerts[0]
        direction_emoji = "⬇️" if a.direction == "below" else "⬆️"
        direction_text = "跌破" if a.direction == "below" else "突破"
        name = html_escape(a.etf_name)
        msg = f"🔔 到价提醒\n\n"
        msg += f"{name} ({a.etf_code})\n"
        msg += f"当前价格: <b>{a.triggered_price}</b> {direction_emoji} {direction_text} {a.target_price}\n"
        if a.note:
            msg += f"\n📝 {html_escape(a.note)}\n"
        msg += f"\n⏰ {check_time.strftime('%Y-%m-%d %H:%M')}"
        return msg
    else:
        msg = f"🔔 到价提醒 ({len(alerts)} 个触发)\n"
        for a in alerts:
            direction_emoji = "⬇️" if a.direction == "below" else "⬆️"
            direction_text = "跌破" if a.direction == "below" else "突破"
            name = html_escape(a.etf_name)
            msg += f"\n📌 {name} ({a.etf_code})\n"
            msg += f"   当前: <b>{a.triggered_price}</b> {direction_emoji} {direction_text} {a.target_price}\n"
            if a.note:
                msg += f"   📝 {html_escape(a.note)}\n"
        msg += f"\n⏰ {check_time.strftime('%Y-%m-%d %H:%M')}"
        return msg
```

---

## 10. 前端改动清单

### 10.1 新增文件

| 文件 | 说明 |
|------|------|
| `frontend/components/PriceAlertButton.tsx` | 详情页铃铛图标 + 创建弹窗 |
| `frontend/components/PriceAlertList.tsx` | 提醒管理列表（用于 settings 页） |

### 10.2 修改文件

| 文件 | 改动 |
|------|------|
| `frontend/lib/api.ts` | 新增 price-alerts API 调用函数 |
| `frontend/app/settings/alerts/page.tsx` | 底部新增到价提醒管理区域 |
| ETF 详情页组件 | 价格旁添加 `<PriceAlertButton>` |

### 10.3 api.ts 新增函数

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

export async function deletePriceAlert(
  token: string,
  id: number
): Promise<{ message: string }>;
```

---

## 11. 边界情况处理

| 场景 | 处理方式 |
|------|---------|
| 活跃提醒达到 20 个上限 | 创建时返回 400，提示用户删除旧提醒或等待触发 |
| 当前价格已满足条件 | 拒绝创建，返回 400 并提示"当前价格已满足该提醒条件" |
| ETF 退市或停牌（价格获取失败） | 跳过该提醒，不触发也不报错；下次检查继续尝试 |
| 价格在两次检查间快速穿越又回来 | 会漏掉。30 分钟检查频率的已知限制 |
| 目标价 = 当前价 | 满足"已达到"条件，拒绝创建 |
| 用户创建提醒后删除自选 | 提醒仍然有效，检查时合并 ETF 到价格获取列表 |
| 用户 Telegram 未配置 | 禁止创建提醒，引导去设置页配置 |
| 同一 ETF 同方向重复创建 | 允许。用户可能想设多个目标价位（如 3.5、3.3、3.0） |
| 非交易日 | 不检查（cron `day_of_week="mon-fri"`） |
| 节假日（工作日但休市） | 检查时价格不变，不会产生新触发（创建时已校验"已满足条件"） |
| Telegram 通知发送失败 | V1 不做补偿，提醒仍标记为已触发，用户可在设置页查看 |

---

## 12. 实施步骤

按以下顺序实施，每步可独立验证：

```
Step 1: 数据模型
  - 新增 price_alert.py（SQLModel 表 + Pydantic 模型）
  - 确保 create_db_and_tables() 能自动创建表

Step 2: 业务服务
  - 新增 price_alert_service.py
  - 实现创建（含校验）/ 查询 / 删除 / check_and_trigger() 核心检查逻辑

Step 3: API 端点
  - 新增 price_alerts.py 端点（GET / POST / DELETE）
  - 注册路由，手动测试 CRUD

Step 4: 通知格式
  - notification_service.py 新增 format_price_alert_message()
  - 含 HTML escape 处理

Step 5: 调度器集成
  - alert_scheduler.py 盘中检查末尾调用 _check_price_alerts()
  - 新增 15:01 收盘补检任务（max_instances=1）
  - 新增已触发记录 30 天自动清理（挂在 daily_check 中）

Step 6: 前端 — API 层
  - api.ts 新增 price-alerts 相关函数

Step 7: 前端 — 创建入口
  - PriceAlertButton 组件（铃铛图标 + 弹窗 + Telegram 配置检查）
  - 集成到 ETF 详情页

Step 8: 前端 — 管理列表
  - PriceAlertList 组件
  - 集成到 /settings/alerts 页面

Step 9: 端到端测试
  - 创建提醒 → 手动触发检查 → 验证 Telegram 收到通知
```

预估总改动量：后端 ~200 行新增，前端 ~300 行新增。

---

## 13. 验证方案

### 13.1 单元测试

- `_should_trigger()` 方向判断逻辑
- 活跃提醒数量限制校验
- 创建时方向自动推断
- 创建时当前价已满足条件的拒绝逻辑
- ETF 代码格式校验

### 13.2 API 测试

- GET / POST / DELETE 全流程
- 权限校验（只能操作自己的提醒）
- 数量限制边界（第 20 个通过，第 21 个拒绝）
- 参数校验（负数价格、超长备注、非法 ETF 代码）
- 当前价已满足条件时拒绝创建
- Telegram 未配置时拒绝创建

### 13.3 集成测试

- 模拟价格数据 → 调用 check_and_trigger() → 验证触发结果
- 盘中检查中到价提醒的集成
- Telegram 消息格式验证（含 HTML 特殊字符转义）

### 13.4 端到端验证

1. 创建到价提醒
2. 通过手动触发检查
3. 验证 Telegram 收到格式正确的消息
4. 验证提醒状态变为已触发
5. 删除已触发提醒
