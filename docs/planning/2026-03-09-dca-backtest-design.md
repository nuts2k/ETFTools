# 定投回测功能设计（修订稿）

> 创建时间: 2026-03-09
> 修订时间: 2026-03-09
> 对应路线图: FEATURE-ROADMAP.md #2 定投回测模拟

---

## 1. 功能概述

输入起始日期、截止日期、定投金额和频率，计算定投某只 ETF 的历史收益、两种年化回报、最大浮亏，并以累计投入线与持仓市值线可视化结果。

**用户价值**: 定投是散户最主流的 ETF 投资策略之一，"如果我从 X 年开始定投，现在赚了多少"是高频问题。

**本期目标**: 在 ETF 详情页提供零配置可用的默认回测结果，并允许用户在全屏面板中调整参数查看详细结果。

**本期不做**:
- 不展示逐笔交易明细表
- 不支持手续费、税费、滑点
- 不支持分红单独处理或红利再投参数
- 不支持盘中动态回测结果跳动
- 不展示 `total_shares`（避免在 QFQ 口径下误导用户）

---

## 2. 本次评审确认的产品口径

### 2.1 日期与定投规则

- 默认起点不是"上市日"，而是**历史数据第一天**
- 第一笔定投按**起始日当天或之后的第一个规则定投日**执行（`>=` 语义）
- 非交易日按**顺延到下一个交易日**处理
- `end_date` 为**硬截止日**
  - 若规则定投日顺延后的交易日超过 `end_date`，该期**不计入**
- `end_date` 晚于今天时，按今天处理
- `effective_params.end_date` 反映**历史数据实际覆盖到的最后一个交易日**，而非用户请求的 `end_date`
- 所有日期判定（"今天"、钳制逻辑）以 **`Asia/Shanghai` 时区**为准，与项目统一约定一致

### 2.2 收益与份额口径

- 历史价格继续使用项目统一规范：**前复权 QFQ 收盘价**
- 年化收益率同时展示两种口径：
  - **资金加权年化收益率（XIRR）**：主口径
  - **简单年化收益率**：辅助口径
- 不展示 `total_shares`
  - 内部仍可按 `amount / close_price` 计算持仓份额用于估值
  - 但前端不对用户暴露，避免与真实账户份额混淆

### 2.3 图表口径

- 详情图按**交易日级别**输出曲线
- 卡片中的 sparkline 可基于详情图数据做轻量抽样
- 最大浮亏按**交易日路径**计算，并与详情图口径保持一致

### 2.4 v1 价格来源口径

- 定投成交价格使用历史交易日收盘价
- 最终市值也使用同一套历史/收盘口径
- v1 **不引入盘中实时价拼接**，避免回测结果在交易时段动态跳动
- v1 不改变底层历史数据缓存策略（7 天 TTL），通过 `effective_params.end_date` 透明化实际数据截止日

---

## 3. 交互设计

### 3.1 入口：详情页卡片 + 全屏 Sheet

- 在 ETF 详情页（`/etf/[code]`）新增"定投回测"卡片
- 卡片默认展示基于默认参数的回测摘要，零配置即可使用
- 点击"查看详情"后展开为全屏 Sheet，支持参数调整和详细结果查看

### 3.2 卡片预览（折叠态）

**默认文案**:
- 标题示例：`从历史起点每月定投 ¥1,000`

**展示内容**:
- 2x2 指标网格：总投入、当前市值、总收益率、资金加权年化收益率（XIRR）
- 迷你收益曲线（sparkline 风格，不带坐标轴）
- "查看详情"入口

**说明**:
- 卡片只显示主指标，不展示简单年化收益率
- 卡片图表可对交易日曲线做抽样，优先保证轻量展示

**加载态**:
- 使用骨架屏（skeleton），与详情页其他卡片保持一致
- 2x2 指标区域和 sparkline 区域均显示灰色占位块

**错误态**:
- 网络失败或服务端异常时，显示简要错误提示和"重试"按钮
- 不展开详细错误信息，保持卡片紧凑

### 3.3 展开面板（全屏 Sheet）

**已知限制（v1）**: 全屏 Sheet 不改变 URL，因此不支持分享/收藏特定回测参数，浏览器后退行为可能不符预期。后续版本可升级为独立路由页面。

#### 参数调整区

| 参数 | 控件 | 默认值 | 说明 |
|------|------|--------|------|
| 起始日期 | 日期选择器 | 历史数据第一天 | 最早不超过历史数据第一天 |
| 截止日期 | 日期选择器 | 今天 | 最晚到今天 |
| 定投金额 | 数字输入 | 1,000 元 | 每期固定金额，必须大于 0 |
| 定投频率 | 分段选择 | 月 | `weekly` / `monthly` |
| 定投日 | 条件控件 | 周一 / 1号 | 周：1-5；月：1-28 |

#### 参数触发方式

- 用户修改参数后，**不立即自动请求**
- 由用户点击明确按钮（如"更新回测结果"）后再重新请求
- 这样可以避免移动端输入过程中频繁触发 API 请求

#### 核心指标区

展示以下指标：
- 总投入
- 当前市值
- 总收益率
- 资金加权年化收益率（XIRR，主指标）
- 简单年化收益率（辅助指标，带 tooltip："简单年化仅作参考，未考虑资金分批投入的时间差异"）
- 最大浮亏
- 总定投期数

#### 收益曲线图

- 双线：累计市值线 + 累计投入阶梯线
- 两线之间的面积差直观表达盈亏
- 使用交易日级别数据绘制
- 带坐标轴和 tooltip
- tooltip 中展示日期、累计投入、持仓市值、当日盈亏率

#### 空态

当区间合法但没有任何有效定投时，显示：
- "该参数区间内没有可执行的定投日"
- 引导用户调整起始日期、截止日期或定投频率

#### 加载态

- 核心指标区和收益曲线图使用骨架屏，与卡片加载态风格一致
- 参数区保持可见但禁用交互，直到数据加载完成

#### 错误态

- 网络失败或服务端异常时，在结果区域显示错误提示和"重试"按钮
- 参数区保持可操作，允许用户修改后重试

---

## 4. 技术方案

### 4.1 整体架构

- 后端计算 + 前端展示，与现有 `metrics` / `grid-suggestion` 模式一致
- 后端复用 `akshare_service.fetch_history_raw()` 获取 QFQ 历史数据
- **DCA 回测直接使用原始历史数据，不走带实时拼接的 `get_etf_history()`**
- 使用 pandas 做时间序列与资金路径计算
- 使用 `pyxirr` 库计算 XIRR（Rust 实现，性能好且边界处理成熟）
- 使用 DiskCache 做 4 小时缓存，相同参数不重复计算
- 无需认证（公开历史数据的纯计算）
- 无需新数据库表（无状态计算）

### 4.2 API 设计

**端点**: `GET /api/v1/etf/{code}/backtest/dca`

#### 请求参数（Query Params）

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `start_date` | string | 否 | 历史数据第一天 | `YYYY-MM-DD` |
| `end_date` | string | 否 | 今天 | `YYYY-MM-DD` |
| `amount` | float | 否 | 1000 | 每期金额（元） |
| `interval` | string | 否 | `monthly` | `weekly` / `monthly` |
| `day` | int | 否 | 1 | 周：1-5；月：1-28 |

#### 参数校验与钳制规则

- `code` 必须为 6 位数字
- `amount` 必须大于 0
- `start_date <= end_date`
- `end_date > 今天` 时，自动钳制到今天
- `start_date < 历史数据第一天` 时，自动钳制到历史数据第一天
- `interval=weekly` 时，`day` 只能在 `1..5`
- `interval=monthly` 时，`day` 只能在 `1..28`

#### 响应结构

```json
{
  "etf_code": "510300",
  "requested_params": {
    "start_date": "2015-01-01",
    "end_date": "2026-03-31",
    "amount": 1000,
    "interval": "monthly",
    "day": 1
  },
  "effective_params": {
    "start_date": "2015-02-12",
    "end_date": "2026-03-07",
    "amount": 1000,
    "interval": "monthly",
    "day": 1,
    "first_invest_date": "2015-02-12"
  },
  "meta": {
    "data_start_date": "2015-02-12",
    "data_end_date": "2026-03-07",
    "price_basis": "qfq_close",
    "non_trading_day_policy": "roll_forward",
    "end_date_is_hard_limit": true,
    "annualized_return_primary": "xirr",
    "annualized_return_secondary": "simple",
    "final_value_price_source": "close",
    "timezone": "Asia/Shanghai"
  },
  "summary": {
    "total_invested": 133000.00,
    "final_value": 187650.32,
    "total_return_pct": 41.09,
    "annualized_return_xirr_pct": 7.96,
    "annualized_return_simple_pct": 8.23,
    "max_floating_loss_pct": -28.56,
    "total_periods": 133
  },
  "equity_curve": [
    {"date": "2015-02-12", "invested": 1000.00, "value": 1000.00},
    {"date": "2015-02-13", "invested": 1000.00, "value": 1004.20}
  ]
}
```

#### 字段说明

##### `requested_params`
保留用户原始请求参数，用于前端展示和排查结果争议。

##### `effective_params`
返回实际参与回测的参数，重点包括：
- 实际生效的起止日期（`end_date` 反映历史数据实际覆盖到的最后一个交易日，可能早于用户请求的日期）
- 钳制后的参数
- 第一笔实际定投日 `first_invest_date`

##### `meta`
返回回测口径说明，避免前后端或用户对结果解释不一致。

##### `summary`
保留以下字段：
- `total_invested`
- `final_value`
- `total_return_pct`
- `annualized_return_xirr_pct`
- `annualized_return_simple_pct`
- `max_floating_loss_pct`
- `total_periods`

**不返回**:
- `total_shares`

##### `equity_curve`
- 按交易日返回曲线点
- 字段仅包含：`date`、`invested`、`value`
- 用于详情图绘制，卡片图由前端自行抽样

### 4.3 缓存策略

- 缓存 key: `dca_backtest_v1_{code}_{start}_{end}_{amount:.2f}_{interval}_{day}`
  - `amount` 统一格式化为 2 位小数（如 `1000.00`），避免 `1000` / `1000.0` 产生不同 key
- TTL: 4 小时（与 metrics 一致）
- 使用 DiskCache
- `v1` 前缀用于后续口径调整时避免旧缓存污染新结果

### 4.4 状态码与错误处理

#### 400 / 422
用于参数非法，例如：
- `amount <= 0`
- `start_date > end_date`
- `interval` 非法
- `day` 越界

#### 404
用于数据不存在，例如：
- ETF 不存在
- 历史数据为空

#### 200 + 空结果
当参数合法，但区间内没有任何有效定投时，返回 200，例如：

```json
{
  "summary": {
    "total_invested": 0,
    "final_value": 0,
    "total_return_pct": 0,
    "annualized_return_xirr_pct": null,
    "annualized_return_simple_pct": null,
    "max_floating_loss_pct": 0,
    "total_periods": 0
  },
  "equity_curve": []
}
```

这样前端可以展示明确空态，而不是把结果误判为系统异常。

---

## 5. 文件清单

| 位置 | 文件 | 职责 |
|------|------|------|
| 后端 | `backend/app/services/dca_backtest_service.py` | 核心计算逻辑 |
| 后端 | `backend/app/api/v1/endpoints/etf.py` | 新增 API 路由 |
| 前端 | `frontend/components/DCABacktestCard.tsx` | 卡片预览组件 |
| 前端 | `frontend/components/DCABacktestSheet.tsx` | 全屏展开面板 |
| 前端 | `frontend/app/etf/[code]/page.tsx` | 详情页接入 |
| 前端 | `frontend/lib/api.ts` | 新增类型和请求函数 |
| 后端测试 | `backend/tests/services/test_dca_backtest_service.py` | 后端单元测试 |
| 后端测试 | `backend/tests/api/test_dca_backtest_api.py` | API 测试 |
| 前端测试 | `frontend/__tests__/DCABacktestCard.test.tsx` | 卡片组件测试 |
| 前端测试 | `frontend/__tests__/DCABacktestSheet.test.tsx` | Sheet 组件测试 |

---

## 6. 核心计算逻辑

### 6.1 定投日确定

1. 根据 `interval` 和 `day` 生成规则定投日序列
2. 保留 **`effective_start_date` 当天及之后**的规则日（`>=` 语义）
3. 对每个规则日，在历史交易日中查找最近的下一个交易日
4. 若顺延后的交易日 `> effective_end_date`，则该期跳过
5. 在该交易日以收盘价买入 `amount / close_price` 份额

### 6.2 收益路径构建

- 每次买入后累加内部持仓份额
- 从第一笔定投日起，按交易日遍历历史价格序列
- 每个交易日记录：
  - `date`: 交易日
  - `invested`: 截止当日的累计投入金额
  - `value`: 截止当日的持仓市值（内部累计份额 × 当日收盘价）

### 6.3 指标计算

#### 总投入
`total_invested = amount * total_periods`

#### 当前市值
`final_value = 最后一个交易日的持仓市值`

#### 总收益率
`total_return_pct = (final_value - total_invested) / total_invested * 100`

#### 简单年化收益率

使用当前结果对总投入做近似年化：

`annualized_return_simple = (final_value / total_invested) ^ (1 / years) - 1`

其中 `years` 基于首笔定投日至回测结束日的实际天数计算。

**注意**: 此公式将所有投入等价为一次性投入，对定投场景会系统性低估实际回报，仅作辅助参考。

#### 资金加权年化收益率（XIRR）

现金流定义：
- 每笔定投：负现金流 `-amount`
- 回测结束日：正现金流 `+final_value`

使用 `pyxirr` 库计算。XIRR 作为主口径展示。
若现金流不足以求解或结果不稳定，则返回 `null`，不抛异常。

#### 年化收益率短期保护规则

当满足以下任一条件时，**两种年化收益率均返回 `null`**：
- `total_periods = 1`（仅 1 期定投）
- 首笔定投日至回测结束日不足 30 天

此时仅展示总收益率，避免极短区间导致年化结果失真。

#### 最大浮亏

按交易日路径遍历：

`(当日市值 - 累计投入) / 累计投入`

取最小值作为 `max_floating_loss_pct`。

**注意**:
- 仅在累计投入大于 0 后参与计算
- 与详情图的交易日口径保持一致
- 该字段始终 `<= 0`，从未亏损时返回 `0`

### 6.4 数值输出规则

- 内部计算尽量保留高精度
- API 输出时统一 round 到 **2 位小数**：
  - 金额字段：`total_invested`、`final_value`、`equity_curve[].invested`、`equity_curve[].value`
  - 百分比字段：`total_return_pct`、`annualized_return_xirr_pct`、`annualized_return_simple_pct`、`max_floating_loss_pct`
- 避免前后端分别舍入导致结果不一致

---

## 7. 测试方案

### 7.1 后端单元测试

文件：`backend/tests/services/test_dca_backtest_service.py`

#### 基础 happy path
- 月投正常回测
- 周投正常回测
- `equity_curve` 日期升序
- `total_invested = amount * total_periods`

#### 日期边界
- 起始日期早于历史数据第一天时自动钳制
- 起始日当天恰好是规则定投日时，该日纳入（`>=` 语义）
- `end_date` 为硬截止，顺延超过截止日时该期跳过
- `end_date` 晚于今天时自动钳制到今天

#### 非交易日顺延
- 月投遇周末顺延到下一个交易日
- 周投遇缺失交易日顺延到下一个交易日
- 顺延后超出历史数据末尾时安全跳过
- 连续节假日导致两笔投资间隔极短时行为正确（如连续两周周一为假期，各自顺延到周二，间隔仅 6 天）

#### 指标计算
- 总收益率计算正确
- 简单年化收益率计算正确
- XIRR 计算在误差范围内正确
- XIRR 不可解时返回 `null`
- 仅 1 期或不足 30 天时，两种年化均返回 `null`
- 最大浮亏按交易日路径计算，而不是只看定投日
- 最大浮亏始终 `<= 0`，全程盈利时返回 `0`

#### 空结果与边界结果
- 合法参数但 0 笔定投时返回空结果
- 历史数据极短时不崩溃
- 金额为小数时结果稳定

#### 数据口径
- 不返回 `total_shares`
- 使用 QFQ 历史数据计算

### 7.2 API 测试

文件：`backend/tests/api/test_dca_backtest_api.py`

- 成功返回 200，并包含 `requested_params`、`effective_params`、`meta`、`summary`、`equity_curve`
- 非法 ETF 代码返回 400/422
- `amount <= 0` 返回 400/422
- `start_date > end_date` 返回 400/422
- 非法 `interval` 返回 400/422
- `day` 越界返回 400/422
- ETF 不存在或历史数据为空返回 404
- 请求日期被钳制时，`requested_params` 与 `effective_params` 能正确体现差异
- `effective_params.end_date` 反映实际数据截止日而非请求日期
- 合法但无有效定投时返回 200 + 空结果

### 7.3 前端测试

#### 卡片组件测试
文件：`frontend/__tests__/DCABacktestCard.test.tsx`

- loading 态（骨架屏）
- 错误态（错误提示 + 重试按钮）
- 无数据态
- 正常展示 2x2 指标
- 收益正负配色符合项目规范（红涨绿跌）

#### Sheet 组件测试
文件：`frontend/__tests__/DCABacktestSheet.test.tsx`

- 默认参数展示正确
- 修改参数后不立即自动请求
- 点击"更新回测结果"后再触发请求
- 加载态（骨架屏 + 参数区禁用）
- 错误态（错误提示 + 重试，参数区可操作）
- 空结果时展示明确空态
- 两种年化口径文案不混淆
- 简单年化有 tooltip 说明

#### 详情页集成验证
- ETF 详情页能显示 DCA 卡片
- 点击后能打开全屏 Sheet
- 请求成功后能显示摘要和图表

---

## 8. 已明确不纳入 v1 的扩展项

以下内容本次设计不纳入，避免范围膨胀：

- 手续费、税费、滑点
- 红利处理方式（现金分红 / 红利再投）
- 月末、最后一个交易日等更复杂的定投规则
- 导出交易明细
- 策略对比（一次性买入 vs 定投）
- 盘中动态估值回测
- equity_curve API 层抽样（v1 由前端自行处理）
- 全屏 Sheet 升级为独立路由页面（URL 分享/深链接）

---

## 9. 结论

本次修订后，定投回测功能的关键口径已明确：
- 默认起点按历史数据第一天处理
- 第一笔按起始日当天或之后的首个规则定投日执行（`>=` 语义）
- 非交易日顺延，但 `end_date` 为硬截止
- `effective_params.end_date` 反映实际数据截止日，透明化数据新鲜度
- 年化收益率同时展示 XIRR 与简单年化，主展示 XIRR；不足 30 天或仅 1 期时返回 null
- XIRR 使用 `pyxirr` 库计算
- 详情图按交易日级别输出，最大浮亏与图表路径一致，始终 <= 0
- 所有数值输出统一 2 位小数
- 不展示 `total_shares`
- 所有日期判定以 `Asia/Shanghai` 时区为准

该设计已具备进入实施规划前的完整度，但**当前仅保存修订稿，暂不生成实施计划**。
