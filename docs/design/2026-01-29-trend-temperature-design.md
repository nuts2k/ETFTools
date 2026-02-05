# ETF 趋势与投资温度指标设计文档

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 ETFTool 新增三个核心指标：周趋势、日趋势（均线突破）、综合投资温度

**Architecture:** 新增两个独立服务（trend_service, temperature_service），通过配置文件控制参数，扩展现有 `/etf/{code}/metrics` API 返回新字段

**Tech Stack:** Python 3.9+, FastAPI, Pandas, NumPy

---

## 1. 背景与目标

### 1.1 问题背景
- 市盈率百分位指标因数据源限制难以实现
- 现有指标（CAGR、最大回撤、波动率）偏向长期分析，缺乏趋势判断工具

### 1.2 目标用户
**混合型投资者** - 既需要趋势判断，又需要风险控制，寻找合适的进出场点

### 1.3 设计目标
- 提供多周期趋势判断（日/周）
- 提供综合投资温度指标，辅助买卖决策
- 首页简洁展示 + 详情页完整数据

---

## 2. 指标定义

### 2.1 周趋势 (Weekly Trend)

**目的：** 判断中期趋势方向和持续性

**计算逻辑：**
1. 将日线数据重采样为周线（周一开盘 → 周五收盘）
2. 统计连续收阳周/收阴周的数量
3. 计算周均线（MA5/MA10/MA20）排列状态

**输出字段：**
```json
{
  "weekly_trend": {
    "consecutive_weeks": 3,      // 正数=连涨周数，负数=连跌周数
    "direction": "up",           // "up" / "down" / "flat"
    "ma_status": "bullish"       // "bullish" / "bearish" / "mixed"
  }
}
```

**展示方式：**
- 首页：`↗️ 连涨3周` 或 `↘️ 连跌2周`
- 详情页：周数 + 周均线排列状态

---

### 2.2 日趋势 (Daily Trend)

**目的：** 判断短期趋势和关键均线突破信号

**计算逻辑：**
1. 计算三条均线：MA5（短期）、MA20（中期）、MA60（长期）
2. 判断当前价格与每条均线的位置关系
3. 检测是否发生向上突破或向下破位
4. 判断整体均线排列状态

**位置判断规则：**
- `crossing_up`: 昨日收盘 < 昨日均线，今日收盘 >= 今日均线（向上突破）
- `crossing_down`: 昨日收盘 > 昨日均线，今日收盘 <= 今日均线（向下破位）
- `above`: 价格在均线上方
- `below`: 价格在均线下方

**排列判断规则：**
- `bullish`: MA5 > MA20 > MA60（多头排列）
- `bearish`: MA5 < MA20 < MA60（空头排列）
- `mixed`: 其他情况（震荡）

**输出字段：**
```json
{
  "daily_trend": {
    "ma5_position": "above",
    "ma20_position": "crossing_up",
    "ma60_position": "below",
    "ma_alignment": "mixed",
    "latest_signal": "break_above_ma20",  // 最近的突破信号
    "ma_values": {
      "ma5": 3.82,
      "ma20": 3.75,
      "ma60": 3.90
    }
  }
}
```

**展示方式：**
- 首页：最重要的信号，如 `🔺突破MA20` 或 `🔻跌破MA60`
- 详情页：三线位置 + 排列状态 + 均线数值

---

### 2.3 综合投资温度 (Temperature)

**目的：** 综合多维度因子，给出 0-100 的投资热度评分

**计算逻辑：**

5 个因子加权计算：

| 因子 | 权重 | 计算方式 | 得分范围 |
|------|------|----------|----------|
| 回撤程度 | 30% | 当前回撤映射到 0-100（-30%回撤=0分，新高=100分） | 0-100 |
| RSI指标 | 20% | RSI(14) 直接作为得分（Wilder EMA 方式） | 0-100 |
| 历史分位 | 20% | 当前价格在近10年的分位数 × 100 | 0-100 |
| 波动水平 | 15% | 当前波动率在历史中的分位数 × 100 | 0-100 |
| 趋势强度 | 15% | 基于均线排列计算（多头=80，震荡=50，空头=20） | 0-100 |

**温度等级：**
- 0-30: `freezing` ❄️ 冰点（超跌区，可考虑分批买入）
- 31-50: `cool` 🌤️ 温和（正常区间）
- 51-70: `warm` 🌡️ 偏热（谨慎追高）
- 71-100: `hot` 🔥 过热（高风险区，考虑减仓）

**历史分位特殊处理：**
- 默认使用 10 年数据计算分位
- 如 ETF 上市不足 10 年，使用全部历史数据并在 `percentile_note` 中标注

**输出字段：**
```json
{
  "temperature": {
    "score": 42,
    "level": "cool",
    "factors": {
      "drawdown_score": 25,
      "rsi_score": 40,
      "percentile_score": 30,
      "volatility_score": 45,
      "trend_score": 35
    },
    "rsi_value": 45.2,
    "percentile_value": 0.30,
    "percentile_years": 3.5,
    "percentile_note": "数据仅覆盖 3.5 年"  // 不足10年时显示
  }
}
```

**展示方式：**
- 首页：图标 + 数值，如 `🌤️ 42`
- 详情页：温度计可视化 + 各因子明细

---

## 3. 配置文件设计

**文件：** `backend/app/data/metrics_config.json`

```json
{
  "drawdown_days": 120,
  "atr_period": 14,
  
  "trend": {
    "daily_ma_periods": [5, 20, 60],
    "weekly_ma_periods": [5, 10, 20]
  },
  
  "temperature": {
    "percentile_years": 10,
    "rsi_period": 14,
    "weights": {
      "drawdown": 0.30,
      "rsi": 0.20,
      "percentile": 0.20,
      "volatility": 0.15,
      "trend": 0.15
    }
  }
}
```

---

## 4. API 响应格式

**端点：** `GET /api/v1/etf/{code}/metrics`

**扩展后的响应：**
```json
{
  // === 现有字段（保持不变）===
  "period": "2021-01-29 to 2026-01-29",
  "total_return": 0.2345,
  "cagr": 0.0432,
  "actual_years": 5.0,
  "max_drawdown": -0.2156,
  "mdd_date": "2024-02-05",
  "mdd_start": "2024-01-15",
  "mdd_trough": "2024-02-05",
  "mdd_end": "2024-06-20",
  "volatility": 0.1823,
  "risk_level": "Medium",
  "valuation": null,
  "atr": 0.0523,
  "current_drawdown": -0.0856,
  "drawdown_days": 120,
  "effective_drawdown_days": 120,
  "current_drawdown_peak_date": "2026-01-10",
  "days_since_peak": 19,
  
  // === 新增字段 ===
  "weekly_trend": {
    "consecutive_weeks": 3,
    "direction": "up",
    "ma_status": "bullish"
  },
  
  "daily_trend": {
    "ma5_position": "above",
    "ma20_position": "crossing_up",
    "ma60_position": "below",
    "ma_alignment": "mixed",
    "latest_signal": "break_above_ma20",
    "ma_values": {
      "ma5": 3.82,
      "ma20": 3.75,
      "ma60": 3.90
    }
  },
  
  "temperature": {
    "score": 42,
    "level": "cool",
    "factors": {
      "drawdown_score": 25,
      "rsi_score": 40,
      "percentile_score": 30,
      "volatility_score": 45,
      "trend_score": 35
    },
    "rsi_value": 45.2,
    "percentile_value": 0.30,
    "percentile_years": 3.5,
    "percentile_note": "数据仅覆盖 3.5 年"
  }
}
```

---

## 5. 前端展示设计

### 5.1 首页（自选列表）

每个 ETF 卡片新增一行指标摘要：

```
┌─────────────────────────────────────┐
│ 沪深300ETF (510300)                 │
│ 3.856  +1.25%                       │
│ ─────────────────────────────────── │
│ ↗️ 连涨3周  🔺突破MA20  🌤️ 温度42   │
└─────────────────────────────────────┘
```

### 5.2 详情页

新增"趋势分析"卡片：

```
┌─ 趋势分析 ──────────────────────────┐
│                                     │
│ 周趋势        ↗️ 连续上涨 3 周       │
│ 周均线        多头排列 (MA5>10>20)  │
│                                     │
│ ─────────────────────────────────── │
│                                     │
│ 日均线状态                          │
│ MA5 (3.82)   ● 价格在上方           │
│ MA20 (3.75)  🔺 今日向上突破         │
│ MA60 (3.90)  ○ 价格在下方           │
│ 整体排列      震荡整理               │
│                                     │
│ ─────────────────────────────────── │
│                                     │
│ 投资温度      🌤️ 42 / 100           │
│ ████████░░░░░░░░░░░░ 温和区间       │
│                                     │
│ 构成因子：                          │
│ · 回撤程度  25  (当前回撤 -8.5%)    │
│ · RSI指标   40  (RSI = 45)         │
│ · 历史分位  30  (近10年30%分位)     │
│ · 波动水平  45  (中等波动)          │
│ · 趋势强度  35  (震荡)              │
│                                     │
└─────────────────────────────────────┘
```

---

## 6. 技术决策记录

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 日均线周期 | MA5/MA20/MA60 | 经典三线，市场认可度高，覆盖短中长期 |
| 周均线周期 | MA5/MA10/MA20 | 周线级别的标准配置 |
| RSI 算法 | Wilder EMA | 业界标准，对近期变化更敏感 |
| 历史分位周期 | 10 年 | 覆盖完整牛熊周期，不足则用全部数据并标注 |
| 温度权重 | 可配置 | 放入 metrics_config.json，支持热加载调整 |
| 实现顺序 | 后端先行 | 先完成计算逻辑，再做前端展示 |

---

## 7. 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/data/metrics_config.json` | 修改 | 新增 trend 和 temperature 配置块 |
| `backend/app/core/config_loader.py` | 修改 | 新增配置属性访问器 |
| `backend/app/services/trend_service.py` | **新建** | 趋势计算服务 |
| `backend/app/services/temperature_service.py` | **新建** | 温度计算服务 |
| `backend/app/api/v1/endpoints/etf.py` | 修改 | 集成新服务，扩展返回字段 |

---

## 8. 后续迭代（暂不实现）

- 趋势强度量化（ADX 指标）
- 成交量异动检测
- 多 ETF 横向对比排名
- 温度历史走势图
