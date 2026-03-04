# ETF 份额数据源迁移：EastMoney → 上交所官方 API

**日期**: 2026-03-04
**状态**: 已完成

---

## 一、问题描述

`fund_flow_collector.py` 每日 16:00 执行份额采集时，`_fetch_em_shares()` 调用 EastMoney 的
`88.push2.eastmoney.com/api/qt/clist/get` 持续失败。

### 错误现象（服务器日志）

```
EastMoney fetch attempt 1 failed: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
EastMoney fetch attempt 2 failed: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
EastMoney fetch attempt 3 failed: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
Failed to fetch EastMoney shares after 3 attempts
```

最早出现时间：2026-02-27（容器内最早留存日志），推测更早已开始失败。

### 根因分析

经过逐步排查：

1. **不是频率限制**：近一周系统无用户，告警调度器提前返回（无自选列表），唯一的 EastMoney 调用来源是 16:00 的 `fund_flow_collector`。

2. **不是 TLS 指纹问题**：用 `curl_cffi` 模拟 Chrome TLS 指纹后仍然失败（`curl: (56) Connection closed abruptly`）。

3. **是 IP 封锁**：直接从服务器执行 `curl` 也返回 HTTP 000（空响应），确认为纯 IP 层面封锁。日本云服务器 IP 段被 EastMoney `push2` 服务器屏蔽。

### 当前影响

- 深市 ETF (159xxx)：由 SZSE 官方接口兜底，**正常采集 610 条**
- 沪市 ETF (510xxx-589xxx)：完全缺失，**808 条数据每日丢失**
- 总覆盖率从 ~100% 降至约 43%

---

## 二、解决方案

### 方案选择

| 方案 | 描述 | 结论 |
|------|------|------|
| curl_cffi TLS 伪装 | 模拟浏览器 TLS 指纹绕过检测 | ❌ 无效，是 IP 封锁不是 TLS 检测 |
| 上交所官方 API（SSE） | `query.sse.com.cn/commonQuery.do` | ✅ 可用，不封 IP，官方数据 |

### 采用方案：接入上交所官方 API

**接口信息**：
- URL: `https://query.sse.com.cn/commonQuery.do`
- 参数: `sqlId=COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L`，`STAT_DATE=YYYY-MM-DD`
- 需要 `Referer: https://www.sse.com.cn/` 请求头
- 数据字段: `SEC_CODE`（代码）、`TOT_VOL`（份额，单位万份）、`STAT_DATE`（统计日期）、`ETF_TYPE`（类型）

**HTTP 客户端**：使用 `requests`（已作为 akshare 的传递依赖存在，不引入新包）。

**数据时效**：当日数据通常在 22:00 后发布，16:00 采集时取最近一个有数据的交易日（通常为 T-1）。

**实施前验证**：需先手动调用一次 SSE API，确认实际响应 JSON 结构与文档描述一致。

---

## 三、实施计划

### 改动范围

- **主要修改**：`backend/app/services/fund_flow_collector.py`
- **测试更新**：`backend/tests/services/test_fund_flow_collector.py`
- **文档同步**：见步骤 5

### 具体步骤

**步骤 1：新增 `_fetch_sse_shares()` 方法**

在 `fund_flow_collector.py` 中新增方法，实现逻辑：
- 使用 `requests` 直接调用 SSE 官方 API（不通过 akshare，akshare 的 `fund_etf_scale_sse()` 日期硬编码且不处理空结果）
- 请求头需包含 `Referer: https://www.sse.com.cn/`
- 自动向前回溯最近 5 个日期（跳过周末），找到第一个有数据的日期
- 将 `TOT_VOL`（万份）除以 10000 转换为亿份
- 用 API 返回的 `STAT_DATE` 作为数据日期（而非 `today`）
- 保留白名单过滤逻辑
- 保留 3 次重试机制（每次间隔 3 秒）

**步骤 2：修改 `collect_daily_snapshot()` 方法**

除了将调用 `_fetch_em_shares()` 改为 `_fetch_sse_shares()` 外，还需同步修改以下引用：

| 位置 | 当前代码 | 改为 |
|------|---------|------|
| 变量名 | `em_df = self._fetch_em_shares(whitelist)` | `sse_df = self._fetch_sse_shares(whitelist)` |
| 合并逻辑 | `em_df`、`em_keep` 等变量 | 全部改为 `sse_df`、`sse_keep` |
| 日志输出 | `sources.append(f"EastMoney: {len(em_df)}")` | `sources.append(f"SSE: {len(sse_df)}")` |
| 返回值 | `"failed": 0 if em_df is not None else 1` | `"failed": 0 if sse_df is not None else 1` |
| 模块 docstring | "Sina 白名单 + EastMoney 份额 + 深交所补充" | "Sina 白名单 + 上交所官方 + 深交所官方" |

**步骤 3：保留 `_fetch_em_shares()` 方法（不调用）**

- 保留方法代码作为参考，但确保 `collect_daily_snapshot()` 中不再调用
- 方法上方添加注释说明已弃用及原因（IP 封锁）

**步骤 4：更新测试**

现有 6 个测试依赖 `_fetch_em_shares`，需要对应更新：

| 现有测试 | 处理方式 |
|---------|---------|
| `test_fetch_em_shares_success` | 保留（测试仍存在的方法） |
| `test_fetch_em_shares_filters_by_whitelist` | 保留 |
| `test_fetch_em_shares_returns_none_on_failure` | 保留 |
| `test_collect_daily_snapshot_new_flow` | mock 目标从 `_fetch_em_shares` 改为 `_fetch_sse_shares` |
| `test_collect_daily_snapshot_different_dates_kept` | 同上 |
| `test_collect_daily_snapshot_em_failure_fallback` | 同上，重命名为 `_sse_failure_fallback` |

新增测试：

| 测试 | 验证内容 |
|------|---------|
| `test_fetch_sse_shares_success` | mock `requests.get`，验证正常返回 DataFrame |
| `test_fetch_sse_shares_whitelist_filter` | 验证白名单过滤逻辑 |
| `test_fetch_sse_shares_retry_on_failure` | 验证 3 次重试机制 |
| `test_fetch_sse_shares_date_fallback` | 验证日期回溯逻辑（当日无数据时回溯到 T-1） |
| `test_fetch_sse_shares_unit_conversion` | 验证万份 → 亿份转换 |

**步骤 5：文档同步更新**

按 AGENTS.md 4.7 规范，代码变更须与文档更新在同一 commit 中提交：

| 文档 | 更新内容 |
|------|---------|
| `docs/design/2026-02-08-fund-flow-analysis-design.md` | 数据源说明从 EastMoney 改为 SSE 官方 API |
| `docs/implementation/2026-02-09-fund-flow-analysis-impl.md` | 采集流程描述更新 |

### 不需要改动的部分

- `_build_etf_whitelist()`：Sina 白名单逻辑不变
- `_fetch_szse_shares()`：深市逻辑不变
- `_save_to_database()`：入库逻辑不变
- 合并逻辑：SSE 和 SZSE 按 `(code, date)` 去重，以 SZSE 为准的逻辑不变（两者代码段不重叠，实际不会发生覆盖）

---

## 四、数据覆盖分析

| 数据源 | 原始返回数量 | 代码范围 | 说明 |
|--------|------------|---------|------|
| SSE（上交所） | 808 | 510xxx–589xxx | 含部分债券 ETF（会被白名单过滤） |
| SZSE（深交所） | 611 | 159xxx、16xxxx | — |
| 原始合计 | 1419 | — | 白名单过滤前的总数 |
| Sina 白名单 | 1423 | — | 已过滤债券 ETF |

### 白名单匹配后的缺失分析

Sina 白名单中有 25 个 ETF 不在 SSE+SZSE 返回范围内：

| 类型 | 数量 | 代码段 | 处理方式 |
|------|------|--------|---------|
| 货币 ETF | 24 | 511600–511990 | **不处理**，货币 ETF 不在系统关注范围 |
| 普通 ETF（560390 电网设备ETF易方达） | 1 | 560xxx | 新上市暂未进入 SSE 统计，后续自动补全 |

迁移后实际覆盖率：**(1423 - 25) / 1423 ≈ 98.2%**，较现状 43% 大幅提升。25 个缺失均为货币 ETF 或极新上市 ETF，不影响系统核心功能。

---

## 五、风险评估

| 风险 | 可能性 | 影响 | 对策 |
|------|--------|------|------|
| SSE API 结构变更 | 低 | 高 | 日志中记录异常，SZSE 仍可兜底深市数据 |
| SSE API 当日数据延迟发布 | 高（每天） | 低 | 已处理：自动回溯 T-1 数据，用实际 STAT_DATE 入库 |
| SSE 偶发网络抖动 | 中（类似 SZSE） | 低 | 已处理：3 次重试机制 |
| SSE Referer 校验策略变更 | 低 | 高 | 监控日志，必要时更新请求头 |
