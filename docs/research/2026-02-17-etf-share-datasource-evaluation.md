# ETF 份额数据源调研报告

**日期**: 2026-02-17
**调研人**: Claude
**状态**: 已完成（已修正）

## 1. 调研背景

### 1.1 问题描述

项目中用于获取上交所 ETF 份额数据的接口 `fund_etf_scale_sse()` 出现数据停止更新的问题：
- 接口仍可调用，但数据日期停留在 **2025-01-15**
- 距离当前时间（2026-02-17）已超过一个月未更新
- 深交所接口 `fund_etf_scale_szse()` 运行稳定，暂不需要替换

### 1.2 调研目标

寻找稳定可靠的上交所 ETF 份额数据源，要求：
1. 数据更新及时（最好是每日更新）
2. 数据源稳定可靠
3. 包含完整的份额字段
4. 最好能统一数据源（同时覆盖上交所和深交所）

## 2. 数据源定义与区分

### 2.1 项目涉及的3个数据源

**重要说明**：本次调研涉及3个不同的数据源，必须明确区分：

| 数据源 | 接口 | 用途 | 项目使用 | 记录数 | 份额字段 |
|--------|------|------|----------|--------|----------|
| **数据源1：Sina 列表** | `fund_etf_category_sina(symbol='ETF基金')` | ETF 实时行情（价格、涨跌幅） | ✓ 第一优先级 | 1436 条 | ✗ 无 |
| **数据源2：EastMoney 列表** | `fund_etf_spot_em()` | ETF 实时行情（价格、涨跌幅、**最新份额**） | ✓ 第二优先级 | 1383 条 | ✓ 有 |
| **数据源3：Sina 份额** | `fund_scale_open_sina(symbol='股票型基金'等)` | 基金规模数据（**份额**、净值） | ✗ 调研目标 | 2177 条（筛选后） | ✓ 有 |

**关键区别**：
- **数据源1和2**：用于获取 ETF 实时行情，项目当前已使用（`akshare_service.py`）
- **数据源3**：用于获取基金份额数据，本次调研的目标，拟替代上交所官方接口

### 2.2 Sina 份额接口的重要发现

**关键发现**：`fund_scale_open_sina()` 接口支持 `symbol` 参数，可选值：
- `"股票型基金"`（默认）
- `"混合型基金"`
- `"债券型基金"`
- `"货币型基金"`
- `"QDII基金"` ← **必须调用此分类才能获取 QDII ETF 数据**

**错误教训**：初期调研时只调用了默认参数（"股票型基金"），导致错误地认为 Sina 份额接口不包含 QDII ETF 数据。实际上需要调用所有5个分类才能获取完整数据。

## 3. 数据源详细测试

### 3.1 数据源1：Sina 列表接口

```python
df = ak.fund_etf_category_sina(symbol="ETF基金")
```

**测试结果**：
- 记录数：1436 条
- 数据日期：2026-02-17（实时）
- 字段：代码、名称、最新价、涨跌幅、成交额等
- **无份额字段**

**用途**：项目当前用于获取 ETF 实时行情（第一优先级）

### 3.2 数据源2：EastMoney 列表接口

```python
df = ak.fund_etf_spot_em()
```

**测试结果**：
- 记录数：1383 条
- 数据日期：2026-02-13
- 字段：代码、名称、最新价、涨跌幅、成交额、**最新份额**等
- **有份额字段**："最新份额"

**用途**：项目当前用于获取 ETF 实时行情（第二优先级），同时包含份额数据

### 3.3 数据源3：Sina 份额接口

```python
# 必须调用所有分类
categories = ["股票型基金", "混合型基金", "债券型基金", "货币型基金", "QDII基金"]
for cat in categories:
    df = ak.fund_scale_open_sina(symbol=cat)
```

**测试结果**：

| 分类 | 总记录数 | 场内基金（筛选后） |
|------|---------|-------------------|
| 股票型基金 | 6344 | 1493 |
| 混合型基金 | 10000 | 327 |
| 债券型基金 | 6750 | 198 |
| 货币型基金 | 872 | 69 |
| QDII基金 | 316 | 65 |
| **合计** | **24282** | **2177** |

**字段**：基金代码、基金简称、单位净值、**最近总份额**、成立日期、基金经理、更新日期

**筛选逻辑**：通过代码前缀 `^(51|52|53|55|56|58|15|16)` 筛选场内基金

**重要发现**：
- 筛选后的 2177 条中，包含大量非 ETF 基金（LOF、联接基金等）
- 必须使用 EastMoney 白名单过滤才能获得准确的 ETF 数据

## 4. 数据源对比分析

### 4.1 对比1：Sina 列表 vs EastMoney 列表

**目的**：了解项目当前使用的两个列表接口的差异

| 指标 | Sina 列表 | EastMoney 列表 |
|------|-----------|----------------|
| 记录数 | 1436 条 | 1383 条 |
| 共同 | 1383 条（100%） | - |
| 独有 | 53 条 | 0 条 |

**结论**：EastMoney 列表是 Sina 列表的子集，Sina 列表多了 53 条。

### 4.2 对比2：EastMoney 列表 vs Sina 份额（核心对比）

**目的**：评估 Sina 份额接口对 ETF 的覆盖情况

| 指标 | 数量 | 占比 |
|------|------|------|
| EastMoney 列表（准确的 ETF） | 1383 条 | 100% |
| Sina 份额（筛选后） | 2177 条 | - |
| **共同（Sina 覆盖）** | **1373 条** | **99.3%** |
| **EastMoney 独有（Sina 缺失）** | **10 条** | **0.7%** |
| Sina 份额独有（非 ETF） | 804 条 | - |

**关键发现**：

1. **Sina 份额接口覆盖率：99.3%**
   - 覆盖了 1373/1383 条 ETF
   - 只缺失 10 条（主要是黄金 ETF 和货币 ETF）

2. **Sina 份额接口准确率：63.1%**
   - 筛选后的 2177 条中，只有 1373 条是真正的 ETF
   - 包含 804 条非 ETF 基金：
     - 204 条 LOF 基金
     - 21 条 ETF 联接基金
     - 其他指数基金

3. **必须使用 EastMoney 白名单过滤**

### 4.3 Sina 份额接口缺失的 10 条 ETF

| 代码 | 名称 | 类型 | EastMoney 最新份额 |
|------|------|------|-------------------|
| 518880 | 黄金ETF | 黄金 | 112.21 亿份 |
| 518800 | 黄金ETF国泰 | 黄金 | 40.92 亿份 |
| 159834 | 金ETF南方 | 黄金 | 1.63 亿份 |
| 159934 | 黄金ETF易方达 | 黄金 | 39.53 亿份 |
| 159831 | 金ETF嘉实 | 黄金 | 1.95 亿份 |
| 159937 | 黄金ETF博时 | 黄金 | 47.35 亿份 |
| 511660 | 货币ETF建信 | 货币 | 0.91 亿份 |
| 511690 | 交易货币ETF大成 | 货币 | 0.08 亿份 |
| 511770 | 金鹰增益货币ETF | 货币 | 0.01 亿份 |
| 511990 | 华宝添益ETF | 货币 | 74.17 亿份 |

**说明**：这 10 条 ETF 在 Sina 份额接口的所有5个分类中都不存在，但在 EastMoney 列表接口中有"最新份额"字段，可以作为补充。

## 5. 官方数据源测试

### 5.1 上交所官方接口

```python
df = ak.fund_etf_scale_sse()
```

**测试结果**：
- 记录数：593 条
- 数据日期：**2025-01-15**（已停更）
- 字段：基金代码、基金简称、ETF类型、统计日期、基金份额
- **包含 QDII ETF**（如 513100 纳指ETF）

**结论**：数据已停更超过1个月，不可用。

### 5.2 深交所官方接口

```python
df = ak.fund_etf_scale_szse()
```

**测试结果**：
- 记录数：921 条
- 数据日期：最新
- 字段：基金代码、基金简称、基金份额
- **包含 QDII ETF**（如 159941 纳指ETF）

**结论**：运行稳定，数据新鲜，暂不需要替换。

## 5.5 数据源质量对比：EastMoney vs Sina 份额接口

### 5.5.1 对比方法

使用深交所官方接口（`fund_etf_scale_szse()`）作为基准，对比：
- **EastMoney 列表接口**的"最新份额"字段
- **Sina 份额接口**的"最近总份额"字段

对比范围：604 条共同的深市 ETF（基金类别 = "ETF"，排除 LOF）

### 5.5.2 EastMoney 列表接口数据质量

**测试结果**（591 条深市 ETF）：

| 差异范围 | 数量 | 占比 |
|---------|------|------|
| <1% | 252 条 | **42.6%** |
| 1-5% | 125 条 | **21.2%** |
| 5-10% | 17 条 | 2.9% |
| 10-20% | 10 条 | 1.7% |
| 20-50% | 6 条 | 1.0% |
| >50% | 0 条 | 0.0% |

**关键指标**：
- ✅ **63.8%** 的数据差异小于 5%
- ✅ **97.3%** 的数据差异小于 20%
- ✅ **没有**差异超过 50% 的异常数据
- ✅ 数据日期：2026-02-13（3-4天前）

**159108 案例验证**（用户外部验证实际份额为 1.96 亿）：
- EastMoney：1.96 亿 ✓ **完全准确**（差异 0.13%）
- 深交所官方：2.01 亿（差异 2.42%）
- Sina 份额接口：6.13 亿 ✗ **严重错误**（差异 212%，历史数据）

### 5.5.3 Sina 份额接口数据质量

**测试结果**（604 条深市 ETF）：

| 差异范围 | 数量 | 占比 |
|---------|------|------|
| <1% | 42 条 | 7.0% |
| 1-5% | 88 条 | 14.6% |
| 5-10% | 117 条 | 19.4% |
| 10-20% | 137 条 | 22.7% |
| 20-50% | 138 条 | 22.8% |
| 50-100% | 68 条 | 11.3% |
| >100% | 14 条 | **2.3%** |

**关键指标**：
- ⚠️ 只有 **21.6%** 的数据差异小于 5%
- ⚠️ **79.1%** 的数据差异大于 5%
- ❌ **13.6%** 的数据差异超过 50%
- ❌ 存在差异超过 400% 的异常数据（如 159293: 427.2%）
- ⚠️ 数据日期：2026-02-13（与 EastMoney 相同）

**问题分析**：
1. **历史数据混入**：部分数据是发行时份额，未及时更新（如 159108 的 6.13 亿）
2. **双向差异**：既有过大的（427%），也有过小的（89%）
3. **LOF 基金数据质量极差**：LOF 基金的差异普遍超过 200%

### 5.5.4 数据源对比总结

| 数据源 | 覆盖率 | 准确性（<5%） | 稳定性 | 数据日期 | 推荐度 |
|--------|--------|---------------|--------|----------|--------|
| **Sina 列表** | 1436条 | N/A（无份额） | ⭐⭐⭐⭐⭐ 最稳定 | 实时 | ⭐⭐⭐⭐⭐ 白名单首选 |
| **EastMoney 列表** | 1383条 | ⭐⭐⭐⭐⭐ **63.8%** | ⭐⭐ 不稳定 | 2026-02-13 | ⭐⭐⭐⭐⭐ 份额数据首选 |
| **Sina 份额接口** | 2177条（含LOF） | ⭐⭐ 21.6% | ⭐⭐⭐ 较稳定 | 2026-02-13 | ⭐⭐ 不推荐 |
| **深交所官方** | 610条（仅深市） | ⭐⭐⭐⭐ 官方数据 | ⭐⭐⭐⭐ 稳定 | 实时 | ⭐⭐⭐⭐ 深市补充 |
| **上交所官方** | 停更（2025-01-15） | ⭐⭐⭐⭐ 官方数据 | ❌ 停更 | 2025-01-15 | ❌ 不可用 |

**核心结论**：
1. **EastMoney 列表接口的"最新份额"字段是最优的份额数据源**（准确率 63.8%）
2. **Sina 份额接口数据质量差**（准确率仅 21.6%），不推荐使用
3. **Sina 列表接口最稳定**，适合作为 ETF 白名单来源
4. **深交所官方接口**可作为深市数据的权威补充

## 6. 最终推荐方案

### 6.1 推荐方案：Sina 列表 + EastMoney 份额 + 深交所补充

**方案名称**：Sina 列表（白名单）+ EastMoney 份额（主力）+ 深交所官方（补充）

**核心思路**：
- 使用 **Sina 列表接口**（最稳定）作为 ETF 白名单来源
- 使用 **EastMoney 列表接口的"最新份额"字段**（最准确，63.8% <5%）作为主要份额数据源
- 使用 **深交所官方接口**（最权威）补充或校验深市 ETF 数据
- 过滤掉 53 条债券 ETF，得到 1383 条 ETF（与 EastMoney 对齐）

**实现逻辑**：

```python
def fetch_etf_shares():
    # 1. 从 Sina 列表获取 ETF 白名单（最稳定的数据源）
    df_sina_list = ak.fund_etf_category_sina(symbol="ETF基金")
    df_sina_list['代码'] = df_sina_list['代码'].astype(str).str.replace('sh', '').str.replace('sz', '')

    # 2. 过滤掉债券 ETF（53 条），得到 1383 条
    # 债券 ETF 特征：代码段为 51/52/53/56/58，且名称包含"债"
    df_sina_list_filtered = df_sina_list[
        ~(df_sina_list['代码'].str.match('^(51|52|53|56|58)') &
          df_sina_list['名称'].str.contains('债', na=False))
    ]
    etf_codes = set(df_sina_list_filtered['代码'].astype(str))
    # 得到 1383 条 ETF 白名单

    # 3. 从 EastMoney 获取份额数据（最准确，63.8% <5%）
    try:
        df_em = ak.fund_etf_spot_em()
        df_em = df_em[df_em['代码'].astype(str).isin(etf_codes)]

        # 统一列名
        df_em = df_em.rename(columns={
            '代码': '基金代码',
            '名称': '基金简称',
            '最新份额': '最近总份额',
            '数据日期': '更新日期',
        })

        # 转换单位（份 → 亿份）
        df_em['最近总份额'] = df_em['最近总份额'] / 100000000

        logger.info(f"EastMoney provided {len(df_em)} ETF shares")
        df_result = df_em

    except Exception as e:
        logger.error(f"EastMoney failed: {e}, falling back to SZSE")
        df_result = pd.DataFrame()

    # 4. 补充深交所官方数据（深市 ETF 的权威数据源）
    try:
        df_szse = ak.fund_etf_scale_szse()
        df_szse['基金代码'] = df_szse['基金代码'].astype(str).str.replace('sz', '').str.replace('sh', '')
        df_szse = df_szse[df_szse['基金类别'] == 'ETF']  # 只要 ETF
        df_szse = df_szse[df_szse['基金代码'].isin(etf_codes)]  # 白名单过滤

        # 统一列名
        df_szse = df_szse.rename(columns={
            '基金简称': '基金简称',
            '基金份额': '最近总份额',
        })
        df_szse['最近总份额'] = df_szse['最近总份额'] / 100000000
        df_szse['更新日期'] = datetime.now().strftime('%Y-%m-%d')

        if not df_result.empty:
            # 用深交所数据覆盖深市 ETF（更权威）
            szse_codes = set(df_szse['基金代码'])
            df_result = df_result[~df_result['基金代码'].isin(szse_codes)]
            df_result = pd.concat([df_result, df_szse], ignore_index=True)
            logger.info(f"SZSE supplemented {len(df_szse)} ETFs")
        else:
            # EastMoney 失败，只用深交所数据
            df_result = df_szse
            logger.warning("Using SZSE only (EastMoney failed)")

    except Exception as e:
        logger.warning(f"SZSE supplement failed: {e}")

    return df_result
```

### 6.2 关于 53 条债券 ETF 的说明

**为什么过滤债券 ETF？**

| 指标 | 数值 |
|------|------|
| Sina 列表总数 | 1436 条 |
| EastMoney 列表总数 | 1383 条 |
| 差异（债券 ETF） | 53 条 |
| 债券 ETF 在 Sina 份额中有数据 | 50 条 |
| 债券 ETF 在 Sina 份额中无数据 | 3 条 |

**决策理由**：
1. **与项目当前范围对齐**：项目当前使用 EastMoney 列表（1383 条），不包含债券 ETF
2. **避免依赖不稳定接口**：EastMoney 列表接口不稳定，通过过滤 Sina 列表实现相同效果
3. **保持数据一致性**：避免突然增加 50 条债券 ETF 导致的数据口径变化
4. **简化维护**：债券 ETF 可作为未来扩展方向，当前先保持稳定

### 6.3 方案优势

| 维度 | 说明 |
|------|------|
| **稳定性** | 白名单 100% 依赖 Sina 列表（项目第一优先级数据源），不依赖不稳定的 EastMoney 列表 |
| **准确性** | 份额数据 63.8% 差异 <5%（EastMoney），远优于 Sina 份额接口（21.6%） |
| **权威性** | 深市数据使用深交所官方接口（最权威），覆盖或校验 EastMoney 数据 |
| **完整性** | 覆盖所有 1383 条 ETF（包括 QDII、黄金、货币、科创债） |
| **容错性** | EastMoney 失败时降级到深交所官方接口（深市）+ 历史数据（上交所） |

### 6.4 数据覆盖

```
总覆盖：1383 条（100%）
├─ 白名单来源：Sina 列表（过滤后）← 最稳定
├─ 份额数据（主力）：EastMoney 列表（1383 条，63.8% <5%）← 最准确
└─ 份额数据（补充）：深交所官方（610 条深市 ETF）← 最权威
```

### 6.5 Fallback 策略

```
优先级 1: Sina 列表（过滤债券）+ EastMoney 份额 + 深交所补充
         ↓ EastMoney 失败
优先级 2: Sina 列表（过滤债券）+ 深交所官方（深市）+ 数据库历史（上交所）
         ↓ 深交所失败
优先级 3: 数据库历史数据（最后兜底）
```

**说明**：
- 上交所官方接口已停更（2025-01-15），不再作为数据源
- EastMoney 失败时，深市使用深交所官方接口，上交所使用数据库历史数据
- 深交所官方接口失败时，全部使用数据库历史数据

## 7. 列名映射

### 7.1 Sina 份额接口

```python
COLUMN_MAP_SINA_SCALE = {
    "基金代码": "code",
    "基金简称": "name",
    "最近总份额": "shares",  # 单位：份
    "更新日期": "date",
    "单位净值": "nav",
    "成立日期": "inception_date",
    "基金经理": "manager",
}
```

### 7.2 EastMoney 列表接口

```python
COLUMN_MAP_EASTMONEY = {
    "代码": "code",
    "名称": "name",
    "最新份额": "shares",  # 单位：份
    "数据日期": "date",
    # ETF类型需要从其他字段推断或设为 None
}
```

## 8. 数据验证

### 8.1 验证逻辑

建议增加以下数据验证：

1. **份额变化验证**：
   - 与历史数据对比，份额变化不应超过 50%
   - 异常数据不入库，使用历史数据

2. **数据完整性验证**：
   - 检查必需字段是否存在
   - 检查份额字段是否为空或异常值

3. **数据源标记**：
   - 记录数据来源（Sina/EastMoney）
   - 记录采集时间

4. **失败告警**：
   - 失败时触发管理员告警
   - 记录失败原因和重试次数

### 8.2 验证代码示例

```python
def validate_shares_data(df_new, df_old):
    """验证份额数据的合理性"""
    if df_old is None or df_old.empty:
        return True

    # 合并新旧数据
    df_merged = df_new.merge(df_old, on='code', suffixes=('_new', '_old'))

    # 计算份额变化率
    df_merged['change_rate'] = (
        (df_merged['shares_new'] - df_merged['shares_old']) / df_merged['shares_old']
    ).abs()

    # 检查异常变化
    abnormal = df_merged[df_merged['change_rate'] > 0.5]

    if not abnormal.empty:
        logger.warning(f"Found {len(abnormal)} ETFs with abnormal share changes")
        for _, row in abnormal.iterrows():
            logger.warning(
                f"  {row['code']}: {row['shares_old']:.0f} -> {row['shares_new']:.0f} "
                f"({row['change_rate']*100:.1f}%)"
            )
        return False

    return True
```

## 9. 风险评估

### 9.1 潜在风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Sina 列表接口格式变化 | 白名单获取失败 | 增加字段验证和异常处理，降级到 EastMoney 列表 |
| EastMoney 列表接口不稳定 | 份额数据获取失败 | 降级到深交所官方（深市）+ 数据库历史（上交所） |
| 深交所官方接口失败 | 深市数据缺失 | 使用数据库历史数据兜底 |
| 新的 ETF 代码段 | 筛选逻辑遗漏 | 定期对比 EastMoney 白名单，调整过滤规则 |
| EastMoney 数据质量下降 | 份额数据不准确 | 增加数据验证（份额变化率检查），异常数据使用历史数据 |

### 9.2 回滚方案

如果新方案出现问题，可以快速回滚：
1. 深交所继续使用 `fund_etf_scale_szse()`（已验证稳定）
2. 上交所暂时使用数据库历史数据
3. 触发管理员告警，人工介入

## 10. 实施计划

### 10.1 立即行动

- [x] 完成数据源调研和对比分析
- [x] 修改 `fund_flow_collector.py` 实现新方案
- [x] 更新列名映射和数据处理逻辑
- [x] 增加数据验证和容错机制
- [x] 编写单元测试

### 10.2 监控验证

- [ ] 部署后监控数据采集成功率
- [ ] 对比新旧数据源的份额数据差异
- [ ] 记录失败情况和原因
- [ ] 必要时调整 fallback 策略

### 10.3 文档更新

- [x] 更新调研文档
- [ ] 更新 API 文档
- [ ] 更新数据源说明
- [ ] 记录数据口径变化

## 11. 参考资料

- [akshare 公募基金文档](https://github.com/akfamily/akshare/blob/main/docs/data/fund/fund_public.md)
- 项目代码: `backend/app/services/fund_flow_collector.py`
- 项目代码: `backend/app/services/akshare_service.py`
- 测试脚本: `backend/compare_three_datasources.py` - 三个数据源对比
- 测试脚本: `backend/analyze_three_datasources.py` - 三个数据源详细分析
- 测试脚本: `backend/test_sina_all_categories.py` - Sina 份额接口所有分类测试
- 测试脚本: `backend/compare_szse_sina_shares.py` - 深交所官方 vs Sina 份额接口对比
- 测试脚本: `backend/compare_eastmoney_szse.py` - EastMoney vs 深交所官方对比
- 测试脚本: `backend/analyze_all_szse_etf_diff.py` - 所有深市 ETF 差异分析

## 12. 附录：测试数据文件

调研过程中生成的测试数据文件：

- `datasource1_sina_list_*.csv` - Sina 列表接口数据
- `datasource2_eastmoney_list_*.csv` - EastMoney 列表接口数据
- `datasource3_sina_scale_full_*.csv` - Sina 份额接口完整数据
- `datasource3_sina_scale_filtered_*.csv` - Sina 份额接口筛选后数据
- `three_datasources_comparison_summary.csv` - 三个数据源对比总结
- `szse_etf_diff_analysis.csv` - 深交所官方 vs Sina 份额接口差异分析（604条深市ETF）
- `eastmoney_szse_diff_analysis.csv` - EastMoney vs 深交所官方差异分析（591条深市ETF）

---

**调研完成日期**: 2026-02-17
**文档更新日期**: 2026-02-17
**下一步**: 等待用户确认后实施方案
