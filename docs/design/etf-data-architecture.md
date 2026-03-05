# ETF 数据架构文档

> 文档类型：设计与实现参考
> 最后更新：2026-03-05

---

## 1. 概览

本文梳理 ETFTool 后端所有 ETF 数据的种类、存储方式、缓存策略、数据源及刷新机制，供开发者维护和扩展数据层时参考。

---

## 2. 数据种类

### 2.1 ETF 实时行情列表

全市场 ETF 的基础行情快照，供搜索、列表展示、批量价格查询使用。

| 字段 | 类型 | 说明 |
|------|------|------|
| code | str | ETF 代码（如 "510300"） |
| name | str | ETF 名称 |
| price | float | 最新价 |
| change_pct | float | 涨跌幅（%） |
| volume | float | 成交额 |
| tags | List[Dict] | 自动分类标签（label + group） |

### 2.2 ETF 历史行情（OHLCV）

单只 ETF 的日线价格历史，**强制使用前复权（qfq）**，供收益计算、图表展示、技术指标分析使用。

| 字段 | 类型 | 说明 |
|------|------|------|
| date | str | 日期（YYYY-MM-DD） |
| open | float | 开盘价（前复权） |
| high | float | 最高价（前复权） |
| low | float | 最低价（前复权） |
| close | float | 收盘价（前复权） |
| volume | float | 成交量 |

> 注意：返回给前端时，历史最后一条记录会用实时价格覆盖 close，实现盘中实时拼接。

### 2.3 ETF 估值数据（PE/PE 分位数）

基于对应指数的 PE-TTM 历史分布计算分位数，反映当前估值水平。

| 字段 | 类型 | 说明 |
|------|------|------|
| pe | float | 当前 PE（TTM） |
| pe_percentile | float | PE 历史分位数（0-100） |
| dist_view | str | 估值判断（低估/适中/高估/参考(短期)） |
| index_code | str | 对应指数代码 |
| index_name | str | 对应指数名称 |
| data_date | str | 数据日期 |
| history_start | str | 历史数据起始日期 |
| history_years | float | 历史数据覆盖年数 |

> 依赖映射文件：`backend/app/data/etf_index_map.json`（ETF 代码 → 指数代码）。
> 仅覆盖 A 股指数，港股/美股指数暂不支持。

### 2.4 ETF 份额历史

记录每日基金份额（亿份），用于计算基金规模、排名及历史变化趋势。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| code | str | ETF 代码 |
| date | str | 统计日期（YYYY-MM-DD） |
| shares | float | 基金份额（亿份） |
| exchange | str | 交易所（SSE / SZSE） |
| etf_type | str | ETF 类型（如"股票型"） |
| created_at | datetime | 记录写入时间（UTC） |

### 2.5 ETF 分类标签

通过规则匹配 ETF 名称自动生成，无需外部 API。

| 字段 | 类型 | 说明 |
|------|------|------|
| label | str | 标签文字（如"宽基"、"半导体"） |
| group | str | 分组（type / industry / strategy / special） |

标签分组优先级：`type > industry > strategy > special`

大类（type）：宽基、跨境、商品、货币、债券、REITs
行业（industry）：半导体、医药、新能源、金融……（50+ 行业标签）
策略（strategy）：红利、高股息、价值、增强……

### 2.6 衍生指标（纯计算，无需独立存储）

基于历史行情数据在线计算，带 DiskCache 缓存。

**收益指标**（`/metrics` 接口）：
- CAGR（年化收益率）、总回报、最大回撤（MDD）、波动率、风险等级

**ATR 与当前回撤**：
- ATR（14日平均真实波幅）、当前相对历史峰值的回撤、距峰值天数

**趋势指标**（日线）：
- MA5 / MA20 / MA60 当前值、价格与各均线的位置关系（above/below/crossing_up/crossing_down）
- 均线排列状态（bullish / bearish / mixed）
- 最新突破信号（如 break_above_ma20）

**趋势指标**（周线）：
- 连续涨跌周数（正数=连涨，负数=连跌）
- 方向（up/down/flat）、周均线排列状态

**市场温度**（综合评分 0-100）：

| 因子 | 权重 | 计算方式 |
|------|------|----------|
| 回撤程度 | 30% | 当前回撤线性映射（-30%回撤=0分，新高=100分） |
| RSI(14) | 20% | Wilder EMA 方法，直接作为得分 |
| 历史分位 | 20% | 当前价格在近 10 年中的分位数 × 100 |
| 波动水平 | 15% | 当前 20 日波动率在历史中的分位数 × 100 |
| 趋势强度 | 15% | 多头排列=80，空头排列=20，震荡=50 |

温度等级：freezing（0-30）/ cool（31-50）/ warm（51-70）/ hot（71-100）

**网格参数**：
- 基于近 60 日 ATR 和价格分位数计算上下界、网格间距、网格数量

---

## 3. 存储层

### 3.1 内存缓存（ETFCacheManager）

- **文件**：`backend/app/core/cache.py`，全局单例 `etf_cache`
- **存储内容**：全量 ETF 列表（含 tags）+ code→info 哈希映射
- **TTL**：60 秒
- **失效行为**：TTL 过期后触发后台线程异步刷新，当前请求仍返回旧数据（非阻塞）

```
etf_cache.etf_list  # List[Dict]  全量列表
etf_cache.etf_map   # Dict[code, info]  O(1) 查找
```

### 3.2 DiskCache（diskcache.Cache）

- **文件**：`backend/app/services/akshare_service.py`，单例 `disk_cache`
- **目录**：`settings.CACHE_DIR`（默认 `./cache`，可通过环境变量 `CACHE_DIR` 覆盖）
- **所有缓存 Key 和 TTL**：

| 用途 | Key 格式 | TTL |
|------|----------|-----|
| ETF 列表 | `etf_list_all` | 24h（86400s） |
| 历史行情（主） | `hist_{code}_{period}_{adjust}` | 7天（604800s） |
| 历史行情（兜底） | `hist_fallback_{code}_{period}_{adjust}` | 永不过期 |
| 估值数据（成功） | `valuation_{index_code}` | 12h（43200s） |
| 估值数据（空） | `valuation_{index_code}` | 5min（300s） |
| 日趋势 | `daily_trend:{code}` | 无固定 TTL，按日期判断 |
| 周趋势 | `weekly_trend:{code}` | 无固定 TTL，按日期判断 |
| 市场温度 | `temperature:{code}` | 无固定 TTL，按日期判断 |
| 资金流向 | `fund_flow:{code}` | 4h（14400s） |
| 网格参数 | `grid:{code}` | DiskCache 默认 TTL |

> 趋势和温度缓存的"按日期判断"含义：缓存中记录了数据对应的最新日期，若历史数据的最新日期与缓存中的日期一致且无实时价格，则直接命中；否则重新计算。**盘中数据不写入缓存**（保护盘中实时性）。

### 3.3 SQLite 主库（etftool.db）

- **文件**：`backend/app/core/database.py`
- **路径配置**：`settings.DATABASE_URL`（默认 `sqlite:///./etftool.db`）
- **表**：

| 表名 | 内容 |
|------|------|
| users | 用户账户、密码哈希、权限 |
| watchlists | 用户自选列表（ETF 代码列表） |
| alert_configs | 价格预警配置 |
| system_configs | 系统级配置项 |

### 3.4 SQLite 份额历史库（etf_share_history.db）

- **文件**：`backend/app/core/share_history_database.py`
- **路径**：`backend/etf_share_history.db`（固定位置，独立于主库）
- **表**：`etf_share_history`
  - 唯一约束：`(code, date)`
  - 索引：`idx_code_date`

### 3.5 本地文件（静态数据）

| 文件 | 用途 |
|------|------|
| `backend/app/data/etf_fallback.json` | ETF 列表兜底 JSON，所有在线源失败时使用 |
| `backend/app/data/etf_index_map.json` | ETF 代码 → 指数代码映射，估值服务依赖 |

---

## 4. 数据源

### 4.1 ETF 实时行情（5 级降级链）

```
Sina (fund_etf_category_sina × 3类)
    ↓ 失败
EastMoney (fund_etf_spot_em)
    ↓ 失败
THS (fund_etf_spot_ths)
    ↓ 失败 + 发送管理员告警
DiskCache (etf_list_all)
    ↓ 空或过期
本地 etf_fallback.json
```

Sina 覆盖类别：ETF基金、QDII基金、封闭式基金，去重后合并。

### 4.2 ETF 历史行情（DataSourceManager）

通过 `DataSourceManager` 按配置优先级编排，内置熔断器：

```
EastMoney (ak.fund_etf_hist_em, adjust=qfq)
    ↓ 失败或熔断
THS History (https://d.10jqka.com.cn/v6/line/hs_{code}/{fq}/last36000.js)
    ↓ 全部失败
DiskCache (hist_fallback_{code}_{period}_{adjust}, 永不过期)
```

配置项（`backend/.env` 或环境变量）：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `HISTORY_DATA_SOURCES` | `["eastmoney", "ths_history"]` | 数据源顺序 |
| `CIRCUIT_BREAKER_THRESHOLD` | 0.1 | 熔断错误率阈值（10%） |
| `CIRCUIT_BREAKER_WINDOW` | 10 | 熔断统计窗口（最近 N 次请求） |
| `CIRCUIT_BREAKER_COOLDOWN` | 300 | 熔断冷却时间（秒） |

**复权模式**：
- THS 映射：`qfq → "01"`（前复权），`hfq → "02"`（后复权），`"" → "00"`（不复权）
- EastMoney：直接传 `adjust` 参数（qfq/hfq/""）

### 4.3 ETF 估值数据

`AkShare.stock_zh_index_value_csindex(symbol=index_code)` → 中证指数官网。

ETF 代码通过 `etf_index_map.json` 映射到指数代码后查询，仅支持 A 股指数（排除含 "HK"/"US" 的代码）。

### 4.4 ETF 份额历史

```
Sina (fund_etf_category_sina)  ← 构建 ETF 白名单（过滤债券 ETF）
上交所官方 API (query.sse.com.cn)  ← 沪市份额，单位万份→亿份
AkShare (fund_etf_scale_szse)   ← 深市份额，单位份→亿份
```

合并规则：同一 `(code, date)` 以深交所数据为准（SZSE 优先覆盖 SSE）。
交易所判断：代码前缀 `15x/16x/12x` → SZSE，其余 → SSE。

> EastMoney push2 接口已废弃（2026-03-04），因日本云服务器 IP 被封锁，代码保留但不再调用。

---

## 5. 刷新机制

### 5.1 实时行情（内存缓存刷新）

- **触发条件**：内存缓存 TTL 过期（60s）或未初始化时，任意请求（`/etf/{code}/info`、`/etf/batch-price`、`/etf/search` 等）均可触发
- **执行方式**：后台 `threading.Thread`（daemon=True），非阻塞，不影响当前请求响应
- **并发保护**：`_refresh_lock` + `_is_refreshing` 标志，同时只有一个刷新任务运行
- **冷启动**：进程启动后首次请求时，优先从 DiskCache 恢复内存缓存，再触发异步刷新

### 5.2 历史行情

- **触发条件**：DiskCache 未命中（TTL 7天到期或首次请求）
- **执行方式**：同步请求，在 API 调用链中直接拉取
- **兜底机制**：在线源全部失败时，使用永不过期的 `hist_fallback_*` 兜底

### 5.3 估值数据

- **触发条件**：DiskCache 未命中（成功缓存 12h，无数据缓存 5min）
- **执行方式**：同步请求，在 `/metrics` 接口中按需获取
- **注意**：当前 `/metrics` 接口中估值查询已被注释禁用，不影响接口响应

### 5.4 趋势与温度（盘中保护）

- **触发条件**：DiskCache 中无该代码的缓存，或缓存中记录的日期落后于当前历史数据最新日期
- **盘中模式**：当传入 `realtime_price` 时，计算结果**不写入 DiskCache**，避免用盘中不完整数据污染收盘后缓存
- **强制刷新**：接口支持 `force_refresh=true` 参数，跳过所有缓存重新计算

### 5.5 份额历史（定时调度）

使用 `APScheduler（AsyncIOScheduler）` 管理，均以北京时间（Asia/Shanghai）为准：

| 任务 | 调度时间 | 说明 |
|------|----------|------|
| 每日份额采集 | 周一至周五 16:00 | 采集沪深两市 ETF 份额并写入数据库 |
| 每月数据备份 | 每月 1 日 02:00 | 导出上个月份额历史数据为备份文件 |

- 容错：`misfire_grace_time=300`，允许延迟 5 分钟内仍执行
- 并发保护：`max_instances=1`，防止重复执行
- 上交所 API 回溯：自动向前回溯最近 5 个工作日，找到第一个有数据的日期（每次重试 3 次，间隔 3 秒）

---

## 6. 数据流向图

```
外部数据源
│
├── Sina / EastMoney / THS        → ETF 实时行情 → 内存缓存 (60s TTL)
│                                                  ↓ 同步写
│                                              DiskCache (24h)
│
├── EastMoney / THS History       → ETF 历史行情 → DiskCache (7天)
│                                               ↓ 永久兜底
│                                            hist_fallback_*
│
├── 中证指数 (AkShare)             → 估值数据 → DiskCache (12h)
│
├── 上交所 API + AkShare(深交所)   → 份额历史 → SQLite (etf_share_history.db)
│
└── 静态文件 (etf_index_map.json) → 估值映射（内存）
    静态文件 (etf_fallback.json)  → 列表兜底（文件读取）

计算层（读取历史行情，结果写入 DiskCache）
├── metrics_service     → CAGR / 最大回撤 / 波动率
├── trend_service       → 均线 / 趋势分析（盘中不缓存）
├── temperature_service → 市场温度（盘中不缓存）
└── grid_service        → 网格参数（ATR + 分位数）
```

---

## 7. 关键文件索引

| 文件 | 职责 |
|------|------|
| `app/core/cache.py` | 内存缓存 ETFCacheManager 定义 |
| `app/services/akshare_service.py` | ETF 实时行情、历史行情入口；DiskCache 实例 |
| `app/services/datasource_manager.py` | 历史数据源编排器（熔断逻辑） |
| `app/services/datasource_protocol.py` | 历史数据源统一接口协议 |
| `app/services/eastmoney_history_source.py` | 东方财富历史数据源实现 |
| `app/services/ths_history_source.py` | 同花顺历史数据源实现 |
| `app/services/valuation_service.py` | 估值数据获取（PE/分位数） |
| `app/services/etf_classifier.py` | ETF 自动分类标签生成 |
| `app/services/trend_service.py` | 趋势分析（均线、排列、突破） |
| `app/services/trend_cache_service.py` | 趋势分析缓存包装层 |
| `app/services/temperature_service.py` | 市场温度计算（5因子加权） |
| `app/services/temperature_cache_service.py` | 温度缓存包装层 |
| `app/services/grid_service.py` | 网格交易参数计算 |
| `app/services/fund_flow_service.py` | 资金流向查询（份额规模、排名） |
| `app/services/fund_flow_cache_service.py` | 资金流向缓存包装层（4h TTL） |
| `app/services/fund_flow_collector.py` | 份额历史定时采集器（APScheduler） |
| `app/services/metrics_service.py` | 收益指标计算（CAGR/MDD/波动率） |
| `app/core/share_history_database.py` | 份额历史 SQLite 引擎 |
| `app/models/etf_share_history.py` | 份额历史 SQLModel 表定义 |
| `app/core/database.py` | 主库 SQLite 引擎 |
| `app/core/config.py` | 配置管理（含数据源和缓存配置项） |
| `app/data/etf_fallback.json` | ETF 列表兜底数据 |
| `app/data/etf_index_map.json` | ETF → 指数代码映射 |
