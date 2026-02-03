# ETF 指标变化 Telegram 通知系统设计文档

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 ETFTool 新增基于指标变化的自动 Telegram 通知功能，监控用户自选股的温度计、均线信号等关键指标变化

**Architecture:** 新增调度器服务（APScheduler）+ 信号检测服务 + 状态缓存，复用现有的 temperature_service 和 trend_service

**Tech Stack:** Python 3.9+, FastAPI, APScheduler, DiskCache

---

## 1. 背景与目标

### 1.1 问题背景
- 现有 Telegram 通知系统仅支持手动测试，缺乏自动触发机制
- 用户需要主动查看 ETF 指标变化，无法及时获知关键信号

### 1.2 目标用户
**主动型投资者** - 希望在 ETF 出现关键信号时及时收到通知，辅助投资决策

### 1.3 设计目标
- 自动监控用户自选股的指标变化
- 支持灵活配置通知时间和频率
- 避免重复通知，减少信息干扰

---

## 2. 监控指标设计

### 2.1 温度计相关信号

| 信号类型 | 触发条件 | 通知优先级 |
|---------|---------|-----------|
| 温度等级变化 | 等级跨越（如 cool → warm） | 高 |
| 极端温度 | 进入 freezing（<30）或 hot（>70） | 高 |
| RSI 超买超卖 | RSI > 70 或 RSI < 30 | 中 |

### 2.2 均线信号（日线）

| 信号类型 | 触发条件 | 通知优先级 |
|---------|---------|-----------|
| 上穿 MA60 | 价格从下方突破 60 日均线 | 高 |
| 下穿 MA60 | 价格从上方跌破 60 日均线 | 高 |
| 上穿 MA20 | 价格从下方突破 20 日均线 | 中 |
| 下穿 MA20 | 价格从上方跌破 20 日均线 | 中 |
| 均线多头排列 | MA5 > MA20 > MA60 形成 | 中 |
| 均线空头排列 | MA5 < MA20 < MA60 形成 | 中 |

### 2.3 周线信号

| 信号类型 | 触发条件 | 通知优先级 |
|---------|---------|-----------|
| 周线趋势转换 | 周线均线排列从空头转多头（或反之） | 高 |
| 周线关键位突破 | 周线收盘价突破 MA20 | 中 |

---

## 3. 技术架构设计

### 3.1 定时任务框架

**选择: APScheduler**

理由：
- 轻量级，无需额外依赖（如 Redis/RabbitMQ）
- 原生支持 asyncio，与 FastAPI 完美集成
- 支持 cron 表达式，配置灵活
- 支持任务持久化（可选）

### 3.2 系统架构图

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Application                   │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────────────────┐ │
│  │  APScheduler    │    │  Alert Service              │ │
│  │  ─────────────  │───▶│  ─────────────────────────  │ │
│  │  - 盘中检查     │    │  - 指标计算                 │ │
│  │  - 收盘汇总     │    │  - 信号检测                 │ │
│  │  - 自定义时间   │    │  - 状态对比                 │ │
│  └─────────────────┘    └──────────────┬──────────────┘ │
│                                        │                 │
│  ┌─────────────────┐    ┌──────────────▼──────────────┐ │
│  │  Alert Config   │    │  Notification Service       │ │
│  │  ─────────────  │    │  ─────────────────────────  │ │
│  │  - 全局配置     │    │  - Telegram 发送            │ │
│  │  - 用户偏好     │    │  - 消息格式化               │ │
│  └─────────────────┘    └─────────────────────────────┘ │
│                                                          │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  Alert State Cache (DiskCache)                      │ │
│  │  - 上次指标快照                                      │ │
│  │  - 已发送信号记录（防重复）                          │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### 3.3 核心模块

1. **AlertScheduler** - 调度器管理
2. **AlertService** - 信号检测逻辑
3. **AlertConfigService** - 配置管理
4. **AlertStateCache** - 状态缓存（防重复通知）

---

## 4. 数据模型设计

### 4.1 全局调度配置

```python
# 存储在配置文件或数据库中
class AlertScheduleConfig:
    # 盘中检查
    intraday_enabled: bool = True
    intraday_interval_minutes: int = 30  # 每30分钟
    intraday_start_time: str = "09:30"   # 开盘时间
    intraday_end_time: str = "15:00"     # 收盘时间

    # 收盘汇总
    daily_summary_enabled: bool = True
    daily_summary_time: str = "15:30"    # 收盘后30分钟

    # 交易日判断
    skip_weekends: bool = True           # 仅跳过周末
```

### 4.2 用户通知偏好

```python
# 扩展 User.settings["alerts"]
class UserAlertPreferences:
    enabled: bool = True

    # 信号类型开关
    temperature_change: bool = True      # 温度等级变化
    extreme_temperature: bool = True     # 极端温度
    ma_crossover: bool = True            # 均线上穿/下穿
    ma_alignment: bool = True            # 均线排列变化
    weekly_signal: bool = True           # 周线信号

    # 通知频率控制
    max_alerts_per_day: int = 20         # 每日最大通知数
    signal_cooldown: str = "daily"       # 同一 ETF 同类信号冷却: daily（当天一次）
```

### 4.3 信号状态缓存

```python
# 存储在 DiskCache 中，key: f"alert_state:{user_id}:{etf_code}"
class ETFAlertState:
    etf_code: str
    last_check_time: datetime

    # 温度计状态
    temperature_level: str       # freezing/cool/warm/hot
    temperature_score: float
    rsi_value: float

    # 均线状态
    ma5_position: str            # above/below/crossing_up/crossing_down
    ma20_position: str
    ma60_position: str
    ma_alignment: str            # bullish/bearish/mixed

    # 周线状态
    weekly_alignment: str
```

### 4.4 消息发送策略

**合并消息模式**：同一时间点检测到的所有信号合并为一条消息发送

```python
class AlertMessage:
    check_time: datetime
    signals: List[SignalItem]  # 多个信号合并

class SignalItem:
    etf_code: str
    etf_name: str
    signal_type: str           # temperature_change, ma_crossover 等
    signal_detail: str         # 具体描述
    priority: str              # high, medium, low
```

**消息格式示例**：
```
📊 ETF 信号提醒 (15:30)

🔥 高优先级:
• 510300 沪深300ETF: 上穿 MA60
• 159915 创业板ETF: 温度 cool → warm

📈 中优先级:
• 510500 中证500ETF: 均线多头排列形成
• 512880 证券ETF: 上穿 MA20

共 4 个信号 | 监控 8 只自选股
```

### 4.5 信号去重策略

**当天一次**：同一 ETF 的同类信号在当天只发送一次

```python
# 缓存 key: f"alert_sent:{user_id}:{etf_code}:{signal_type}:{date}"
# 缓存 value: True
# TTL: 到当天 23:59:59
```

---

## 5. API 设计

### 5.1 配置管理

**获取配置**
```
GET /api/v1/alerts/config
```

**更新配置**
```
PUT /api/v1/alerts/config
Content-Type: application/json

{
  "enabled": true,
  "temperature_change": true,
  "ma_crossover": true,
  "ma_alignment": true,
  "weekly_signal": true,
  "max_alerts_per_day": 20
}
```

### 5.2 手动触发

```
POST /api/v1/alerts/trigger
```

立即执行一次信号检测并发送通知（用于测试）

### 5.3 历史查询

```
GET /api/v1/alerts/history?limit=20&offset=0
```

查询最近发送的通知记录

---

## 6. 前端界面设计

### 6.1 通知配置页面

路径: `/settings/alerts`

```
┌─ 信号通知设置 ─────────────────────────┐
│                                        │
│ 启用信号通知  [开关]                    │
│                                        │
│ ────────────────────────────────────── │
│                                        │
│ 监控信号类型                            │
│ ☑ 温度等级变化（如 cool → warm）        │
│ ☑ 极端温度（freezing 或 hot）           │
│ ☑ 均线上穿/下穿（MA20、MA60）           │
│ ☑ 均线排列变化（多头/空头形成）          │
│ ☑ 周线趋势信号                          │
│                                        │
│ ────────────────────────────────────── │
│                                        │
│ 通知时间                                │
│ ☑ 盘中检查  每 [30] 分钟                │
│ ☑ 收盘汇总  [15:30]                     │
│                                        │
│ ────────────────────────────────────── │
│                                        │
│ [测试通知]  [保存设置]                   │
│                                        │
└────────────────────────────────────────┘
```

---

## 7. 实施步骤

### 第一阶段：基础设施

1. **安装 APScheduler**
   - 添加依赖到 `requirements.txt`: `apscheduler>=3.10.0`

2. **创建调度器模块**
   - 文件: `backend/app/services/alert_scheduler.py`
   - 使用 `AsyncIOScheduler` 与 FastAPI 集成
   - 在 `main.py` 的 `lifespan` 中启动/停止调度器

3. **创建配置模型**
   - 文件: `backend/app/models/alert_config.py`
   - 定义 `AlertScheduleConfig` 和 `UserAlertPreferences`

### 第二阶段：信号检测服务

4. **创建信号检测服务**
   - 文件: `backend/app/services/alert_service.py`
   - 复用现有的 `temperature_service` 和 `trend_service`
   - 实现信号对比逻辑（当前状态 vs 上次状态）

5. **创建状态缓存服务**
   - 文件: `backend/app/services/alert_state_service.py`
   - 使用现有的 DiskCache 基础设施
   - 实现信号去重（当天一次）

### 第三阶段：通知集成

6. **扩展通知服务**
   - 修改: `backend/app/services/notification_service.py`
   - 添加 `format_alert_message()` 方法
   - 支持合并多个信号为一条消息

7. **创建 API 端点**
   - 文件: `backend/app/api/v1/endpoints/alerts.py`
   - `GET /alerts/config` - 获取配置
   - `PUT /alerts/config` - 更新配置
   - `POST /alerts/trigger` - 手动触发检查
   - `GET /alerts/history` - 查询历史信号

### 第四阶段：前端界面

8. **创建通知配置页面**
   - 文件: `frontend/app/settings/alerts/page.tsx`
   - 信号类型开关（温度变化、均线信号等）
   - 调度时间配置（盘中频率、收盘时间）

---

## 8. 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/requirements.txt` | 修改 | 添加 apscheduler 依赖 |
| `backend/app/main.py` | 修改 | 集成调度器生命周期 |
| `backend/app/services/alert_scheduler.py` | **新建** | 调度器核心 |
| `backend/app/services/alert_service.py` | **新建** | 信号检测逻辑 |
| `backend/app/services/alert_state_service.py` | **新建** | 状态缓存管理 |
| `backend/app/models/alert_config.py` | **新建** | 配置数据模型 |
| `backend/app/api/v1/endpoints/alerts.py` | **新建** | API 端点 |
| `backend/app/services/notification_service.py` | 修改 | 添加消息格式化 |
| `frontend/app/settings/alerts/page.tsx` | **新建** | 前端配置页 |
| `frontend/lib/api.ts` | 修改 | 添加 alerts API 调用 |

---

## 9. 技术决策记录

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 定时任务框架 | APScheduler | 轻量级，原生 asyncio 支持，无需额外基础设施 |
| 消息发送模式 | 合并消息 | 减少通知数量，降低用户干扰 |
| 信号冷却策略 | 当天一次 | 平衡及时性和避免重复 |
| 节假日处理 | 仅跳过周末 | 简单实现，避免维护节假日数据 |
| 状态存储 | DiskCache | 复用现有基础设施，持久化存储 |

---

## 10. 验证方案

### 10.1 单元测试
- 信号检测逻辑测试（温度变化、均线突破）
- 状态对比测试（新旧状态比较）
- 去重逻辑测试

### 10.2 集成测试
- 手动触发 API 测试
- 模拟定时任务执行
- 消息格式化验证

### 10.3 端到端测试
1. 配置 Telegram Bot Token 和 Chat ID
2. 添加 ETF 到自选股
3. 调用手动触发 API
4. 验证 Telegram 收到格式正确的通知消息

---

## 11. 后续迭代（暂不实现）

- 支持更多通知渠道（邮件、微信）
- 自定义信号阈值（如 RSI > 80 才通知）
- 信号历史统计和分析
- 智能节假日识别（接入节假日 API）
