# ETF 对比功能 - 设计文档

> 创建时间: 2026-02-11
> 状态: 已实现
> 优先级: P0（高用户价值，中等开发投入）
> 关联: Feature Roadmap 功能 #1

---

## 1. 功能定位

### 1.1 为什么需要这个功能？

**核心痛点**：
- **选基困难**：用户在同类 ETF 之间难以做出选择（如沪深300 vs 中证500）
- **信息分散**：需要在多个详情页之间反复切换对比指标
- **缺乏直观对比**：无法在同一张图上看到不同 ETF 的走势差异
- **相关性盲区**：用户以为分散了投资，实际持仓高度相关

**用户价值**：
- 横向对比是选基金最直觉的决策方式
- 归一化走势消除绝对价格差异，聚焦相对表现
- 相关性系数帮助构建真正分散的投资组合

### 1.2 核心价值主张

**为投资者提供「一目了然」的 ETF 横向对比工具**

- 选择 2-3 只 ETF，走势图叠加对比
- 核心指标并排展示，优劣一目了然
- 相关性系数量化持仓分散度

---

## 2. 需求分析

### 2.1 用户场景

**场景1：同类选优**
```
用户："沪深300ETF 和中证500ETF，过去3年哪个表现更好？"
期望：归一化走势图直观对比，指标表格量化差异
```

**场景2：分散验证**
```
用户："我同时持有半导体ETF和芯片ETF，是不是太集中了？"
期望：相关性系数显示 0.95，提示高度相关
```

**场景3：风格对比**
```
用户："红利ETF vs 成长ETF，不同市场环境下谁更抗跌？"
期望：对比最大回撤和波动率，辅助风格配置决策
```

### 2.2 功能需求（MVP）

1. **ETF 选择**：页内搜索添加 2-3 只 ETF
2. **归一化走势图**：以起始日为基准 100%，多线叠加
3. **时间范围切换**：1Y / 3Y / 5Y / 全部
4. **指标对比表格**：CAGR、最大回撤、波动率、温度并排展示
5. **相关性系数**：Pearson 相关系数（基于日收益率）

### 2.3 非功能需求

- 对比计算响应时间 < 2s（3 只 ETF）
- 移动端优先，320px+ 适配
- 图表支持触摸交互（tooltip 防遮挡）

---

## 3. 技术方案

### 3.1 架构决策

**API 设计：混合策略（新端点 + 复用已有端点）**

| 数据 | 端点 | 理由 |
|------|------|------|
| 归一化价格 + 相关性 | `GET /etf/compare`（新） | 需要跨 ETF 日期对齐和联合计算 |
| 单只 ETF 指标 | `GET /etf/{code}/metrics`（已有） | 避免重复 100+ 行指标计算逻辑 |

前端并行请求 compare 端点和各 ETF 的 metrics 端点，减少后端改动量。

### 3.2 后端 API 设计

#### 3.2.1 新增端点：ETF 对比数据

```
GET /api/v1/etf/compare?codes=510300,159915,510500&period=3y

参数:
  codes (必选): 逗号分隔的 ETF 代码，2-3 个，每个 6 位数字
  period (可选): Literal["1y", "3y", "5y", "all"]，默认 "3y"
    （与现有 metrics 端点使用相同枚举值，前端可用同一 period 值并行调用两个端点）

响应:
{
  "etf_names": {
    "510300": "沪深300ETF",
    "159915": "创业板ETF",
    "510500": "中证500ETF"
  },
  "period_label": "2023-02-11 ~ 2026-02-11",
  "warnings": [],
  "normalized": {
    "dates": ["2023-02-13", "2023-02-14", ...],
    "series": {
      "510300": [100.0, 100.32, 99.87, ...],
      "159915": [100.0, 101.15, 100.44, ...]
    }
  },
  "correlation": {
    "510300_159915": 0.85,
    "510300_510500": 0.72,
    "159915_510500": 0.68
  }
}

字段说明:
  etf_names: ETF 代码到名称的映射，后端从 etf_cache.get_etf_info() 零成本获取
  warnings: 警告信息数组，默认空数组。重叠期 30-120 天时包含提示文案
  normalized.series: 归一化后的价格序列，经降采样处理（最多 500 点）

错误响应:
  400: codes 数量不在 2-3 范围，或格式不合法；period 不在 1y|3y|5y|all 范围
  404: 某个 ETF 代码不存在或无历史数据
  422: 无重叠交易日，或重叠交易日不足 30 天（相关性无统计意义）
```

#### 3.2.2 复用端点：单只 ETF 指标

```
GET /api/v1/etf/{code}/metrics?period=3y

已有端点，返回 CAGR、最大回撤、波动率、温度等。
前端对 2-3 只 ETF 并行调用。
```

### 3.3 核心算法

#### 3.3.0 数据获取（含实时拼接）

⚠️ **【强制】** 对比功能必须包含当日实时价格，与详情页行为保持一致。

```python
# compare_service.py 中获取历史数据
# 必须使用含实时拼接的方法，而非 fetch_history_raw()
records = AkShareService.get_etf_history(code, period="daily", adjust="qfq")
df = pd.DataFrame(records)  # 包含当日实时价格（如有）
```

**关键点**：
- `get_etf_history()` 会将当日实时价格追加到历史数据末尾（来自 `etf_cache` 内存缓存）
- 冷启动时内存缓存可能未初始化，实时点可能缺失，compare_service 应容忍此情况（不报错，仅缺少当日数据）
- 禁止直接调用 `fetch_history_raw()`，否则对比页会比详情页少一天数据

#### 3.3.1 日期对齐

不同 ETF 可能上市时间不同，使用 pandas inner merge 取交集：

```python
# 合并多只 ETF 的历史数据，只保留共同交易日
merged = df_list[0][['date', 'close']].rename(columns={'close': code_list[0]})
for i in range(1, len(df_list)):
    right = df_list[i][['date', 'close']].rename(columns={'close': code_list[i]})
    merged = merged.merge(right, on='date', how='inner')
```

#### 3.3.2 价格归一化

以对齐后的第一个交易日为基准 100：

```python
for code in code_list:
    base_price = merged[code].iloc[0]
    merged[f'{code}_norm'] = merged[code] / base_price * 100
```

#### 3.3.3 相关性计算

基于日收益率的 Pearson 相关系数：

```python
returns = merged[code_list].pct_change().dropna()
for i, j in combinations(code_list, 2):
    corr = returns[i].corr(returns[j])
    result[f"{i}_{j}"] = round(corr, 4)
```

**相关性解读参考**：
- 0.8 ~ 1.0：高度正相关（如半导体ETF vs 芯片ETF）
- 0.4 ~ 0.8：中度正相关
- -0.2 ~ 0.4：低相关（分散效果好）
- < -0.2：负相关（对冲效果）

#### 3.3.4 降采样

5y/all 期间数据量可达 2500+ 点，3 条 SVG 线在低端移动设备上渲染卡顿。归一化后进行等间隔降采样：

```python
MAX_POINTS = 500  # 320px 屏幕已超像素分辨率，视觉无损

if len(merged) > MAX_POINTS:
    step = len(merged) / MAX_POINTS
    indices = [int(i * step) for i in range(MAX_POINTS)]
    indices[0] = 0
    indices[-1] = len(merged) - 1  # 确保包含首尾
    merged = merged.iloc[indices].reset_index(drop=True)
```

**注意**：降采样在归一化之后进行，确保首尾值正确。

### 3.4 后端代码结构

**新增文件**：
```
backend/app/services/compare_service.py   # 归一化 + 相关性计算
backend/app/api/v1/endpoints/compare.py   # API 端点
backend/tests/api/test_compare.py         # 测试
backend/tests/services/test_compare_service.py  # 单元测试
```

**修改文件**：
```
backend/app/api/v1/api.py                 # 注册 compare router
```

---

## 4. 前端 UI 设计

### 4.1 入口：底部导航

在现有 3 个 tab（自选、搜索、设置）基础上新增第 4 个 tab：

```
[⭐ 自选] [🔍 搜索] [⇄ 对比] [⚙ 设置]
```

图标使用 lucide-react 的 `ArrowLeftRight`。

### 4.2 页面布局（移动端优先）

```
┌──────────────────────────────┐
│ ETF 对比                      │  ← 页面标题
├──────────────────────────────┤
│ [沪深300ETF ×] [创业板ETF ×] [+] │  ← ETF 选择器
├──────────────────────────────┤
│ [🔍 搜索 ETF...]              │  ← 点击 [+] 展开
│ [宽基] [红利] [半导体] [医药] ▸ │  ← 标签横向滚动（输入文字时隐藏）
│ ┌────────────────────────┐   │
│ │ 510300 沪深300ETF       │   │  ← 搜索/标签筛选结果
│ │ 510500 中证500ETF       │   │
│ └────────────────────────┘   │
├──────────────────────────────┤
│ [1Y] [3Y] [5Y] [全部]        │  ← 时间切换
├──────────────────────────────┤
│                               │
│   归一化走势图                 │  ← Recharts LineChart
│   (多线叠加，不同颜色)         │
│                               │
├──────────────────────────────┤
│ 相关性系数                     │
│ 510300 vs 159915: 0.85        │
├──────────────────────────────┤
│ 指标对比                       │
│ ┌────────┬────────┬────────┐ │
│ │        │ 沪深300 │ 创业板  │ │
│ ├────────┼────────┼────────┤ │
│ │ CAGR   │ +8.2%  │ +12.1% │ │
│ │ 最大回撤│ -15.3% │ -22.1% │ │
│ │ 波动率  │ 18.5%  │ 25.3% │ │
│ │ 温度    │ 45     │ 72    │ │
│ └────────┴────────┴────────┘ │
└──────────────────────────────┘
```

### 4.3 交互设计

**ETF 选择器**：
- 已选 ETF 显示为可移除的 chip（名称 + × 按钮），chip 颜色对应走势图线条颜色（蓝/紫/橙）
- [+] 按钮展开内联搜索输入框
- 搜索使用 `useDebounce(300ms)` + AbortController（复用搜索页技术模式）
- 输入框下方显示标签横向滚动行，复用搜索页的 `TAG_COLORS`（`frontend/lib/tag-colors.ts`）和 `/etf/tags/popular` API
- 标签与文本搜索互斥：输入文字时标签行隐藏，点击标签时清空输入框（与搜索页行为一致）
- 搜索结果以简洁下拉列表展示（code + name），不使用完整 StockCard 卡片
- 点击结果项添加到选择器，前端同时保存 `{code, name}` 用于 chip 显示
- 已满 3 只时隐藏 [+] 按钮
- 防止添加重复 ETF

**走势图**：
- 使用 Recharts `LineChart`（非 AreaChart，多线叠加更清晰）
- 每只 ETF 使用不同颜色：蓝色 `#3b82f6`、紫色 `#a855f7`、橙色 `#f97316`
- Y 轴显示百分比（100 = 起始基准），标签简化为整数（"123" 而非 "123.45"）
- 自定义 Tooltip 固定在图表顶部（而非跟随手指），避免触摸时被遮挡
- 不使用 Recharts 内置图例，ETF 选择器 chip 的颜色即为图例（合二为一，节省 320px 下的纵向空间）
- `isAnimationActive={false}` 关闭动画，提升渲染性能

**指标表格**：
- CAGR 正值红色、负值绿色（中国惯例）
- 最大回撤始终绿色（负值）
- 温度按等级着色（freezing/cool/warm/hot）

**状态管理**：
- `selectedETFs` 类型为 `{code: string, name: string}[]`（而非 `string[]`），搜索添加时同时保存名称
- `selectedETFs.length < 2` 时显示引导文案「请添加至少 2 只 ETF 开始对比」
- `selectedETFs.length >= 2` 时自动触发数据加载
- 加载中显示骨架屏
- `warnings` 非空时在图表上方显示淡黄色提示条

**URL 状态同步**：
- 使用 `useSearchParams` 将 codes 和 period 双向同步到 URL query string
- URL 格式：`/compare?codes=510300,159915&period=3y`
- 页面加载时从 URL 读取初始状态（支持分享链接和书签）
- 用户操作时使用 `router.replace()` 更新 URL（避免产生过多浏览器历史记录）
- 注意：Next.js App Router 中 `useSearchParams` 需要 `Suspense` 边界包裹
- 从 URL 加载时，ETF 名称从 compare API 的 `etf_names` 字段获取（无需额外请求）

### 4.4 前端代码结构

**新增文件**：
```
frontend/app/compare/page.tsx              # 对比页面
frontend/__tests__/compare-page.test.tsx   # 页面测试
```

**修改文件**：
```
frontend/lib/api.ts                        # 新增 CompareData 类型
frontend/components/BottomNav.tsx           # 新增「对比」tab
```

### 4.5 新增类型

```typescript
// frontend/lib/api.ts
export interface CompareData {
  etf_names: Record<string, string>;   // {"510300": "沪深300ETF", ...}
  period_label: string;                 // "2023-02-11 ~ 2026-02-11"
  warnings: string[];                   // 重叠期过短等警告，默认空数组
  normalized: {
    dates: string[];                    // 降采样后最多 500 点
    series: Record<string, number[]>;   // 归一化值，基准 100
  };
  correlation: Record<string, number>;  // {"510300_159915": 0.85, ...}
}
```

---

## 5. 实施路线图

### Phase 0: 设计文档 ← 当前

- [x] 需求分析和方案设计
- [x] 编写设计文档

### Phase 1: 后端

- [x] 创建 `compare_service.py`（归一化 + 相关性计算）
- [x] 创建 `compare.py` API 端点
- [x] 注册路由
- [x] 编写后端测试

### Phase 2: 前端基础

- [x] 新增 `CompareData` 类型
- [x] BottomNav 新增「对比」tab
- [x] 创建对比页面骨架

### Phase 3: 前端组件

- [x] ETF 选择器（chips + 内联搜索）
- [x] 归一化走势图（LineChart 多线）
- [x] 相关性展示
- [x] 指标对比表格

### Phase 4: 集成与测试

- [x] 数据获取逻辑串联
- [x] 前端测试
- [x] 更新文档（AGENTS.md）

---

## 6. 测试策略

### 6.1 后端测试

**API 集成测试** (`backend/tests/api/test_compare.py`)：
- 输入校验：少于 2 个 / 超过 3 个 / 格式错误 / 无效 period
- 正常对比：2 只 ETF、3 只 ETF
- 响应包含 `etf_names` 且名称正确
- ETF 不存在返回 404
- 无重叠日期返回 422
- 重叠日期不足 30 天返回 422
- 重叠日期 30-120 天返回 200 + `warnings` 非空

**服务单元测试** (`backend/tests/services/test_compare_service.py`)：
- 归一化：起始值为 100、价格不变返回全 100
- 日期对齐：不同上市日期取交集
- 相关性：完全相关返回 1.0、返回值在 [-1, 1] 范围
- pair 数量：2 只=1 对，3 只=3 对
- 降采样：超过 500 点时采样至 500 点，首尾值保留
- 降采样：不足 500 点时不采样，数据完整返回

### 6.2 前端测试

**对比页测试** (`frontend/__tests__/compare-page.test.tsx`)：
- 选择器：添加/移除 ETF、最多 3 只限制、防重复
- 选择器 chip 颜色与图表线条颜色一致
- 引导文案：少于 2 只时显示
- 图表：正确渲染多条线
- 指标表格：正确展示、涨跌配色
- URL 同步：从 URL query string 恢复选中状态
- 警告提示：`warnings` 非空时显示淡黄色提示条

---

## 7. 风险与缓解

### 7.1 性能

**风险**：3 只 ETF 的历史数据量较大（每只 ~2000 条 × 3）
**缓解**：
- 后端 pandas 处理效率高，预计 < 500ms
- 后端归一化后降采样至最多 500 点，大幅减少前端 SVG 渲染开销
- 前端图表使用 Recharts 的 `isAnimationActive={false}` 关闭动画
- 底层历史数据已有 DiskCache 缓存（4h TTL），compare 计算的输入数据大概率命中缓存
- MVP 阶段不缓存 compare 计算结果；如后续需要，缓存键必须对 codes 排序：`compare_{sorted(codes)}_{period}`

### 7.2 日期对齐

**风险**：两只 ETF 上市时间差距大，重叠期很短
**缓解**：
- 返回 `period_label` 告知实际对比区间
- 重叠交易日 < 30 天：返回 422 错误，拒绝计算（相关性在极短窗口下无统计意义）
- 重叠交易日 30-120 天：正常返回数据，`warnings` 字段包含提示文案（如"重叠交易日仅 45 天，对比结果可能不够稳定"）
- 前端 `warnings` 非空时在图表上方显示淡黄色提示条

---

## 8. 相关文档

- [Feature Roadmap](../planning/FEATURE-ROADMAP.md) — 功能 #1
- [ETF 分类设计](2026-02-10-etf-auto-classification-design.md) — 阶段 3 同类推荐（推迟）
- [AGENTS.md](../../AGENTS.md) — 开发规范

---

**最后更新**: 2026-02-11（架构审查更新：增加 ETF 名称映射、实时数据拼接、降采样、警告格式、URL 状态同步、移动端图例优化、内联标签筛选）
