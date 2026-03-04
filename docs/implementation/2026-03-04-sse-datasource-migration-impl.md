# ETF 份额数据源迁移实施计划：EastMoney → 上交所官方 API

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 用上交所官方 API 替代被 IP 封锁的 EastMoney 接口，恢复沪市 ETF 份额采集。

**Architecture:** 在 `FundFlowCollector` 中新增 `_fetch_sse_shares()` 方法，使用 `requests` 直接调用 SSE 官方 API（`query.sse.com.cn/commonQuery.do`），替代 `collect_daily_snapshot()` 中对 `_fetch_em_shares()` 的调用。保留 `_fetch_em_shares()` 方法代码但标记弃用。同步更新测试和文档。

**Tech Stack:** Python 3.9+, requests, pandas, SQLModel, pytest

**Reference:** `docs/planning/2026-03-04-sse-datasource-migration.md`

---

## Task 1: 新增 `_fetch_sse_shares()` 方法 — 测试

**Files:**
- Modify: `backend/tests/services/test_fund_flow_collector.py`

**Step 1: 添加 SSE 测试 fixture 和测试用例**

在 `test_fund_flow_collector.py` 末尾添加：

```python
from unittest.mock import MagicMock
import json


@pytest.fixture
def sample_sse_api_response():
    """模拟 SSE 官方 API 返回的 JSON 响应"""
    return {
        "result": [
            {"SEC_CODE": "510300", "TOT_VOL": "9106200.00", "STAT_DATE": "2026-03-03", "ETF_TYPE": "股票ETF"},
            {"SEC_CODE": "510500", "TOT_VOL": "4503000.00", "STAT_DATE": "2026-03-03", "ETF_TYPE": "股票ETF"},
            {"SEC_CODE": "159915", "TOT_VOL": "3204500.00", "STAT_DATE": "2026-03-03", "ETF_TYPE": "股票ETF"},
            {"SEC_CODE": "511260", "TOT_VOL": "500000.00", "STAT_DATE": "2026-03-03", "ETF_TYPE": "债券ETF"},
        ],
        "success": "true",
    }


def _mock_sse_response(json_data, status_code=200):
    """构造 mock 的 requests.Response 对象"""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


def test_fetch_sse_shares_success(sample_sse_api_response):
    """测试成功获取 SSE 份额数据"""
    collector = FundFlowCollector()
    whitelist = {"510300", "510500", "159915", "511260"}

    with patch("app.services.fund_flow_collector.requests.get",
               return_value=_mock_sse_response(sample_sse_api_response)):
        result = collector._fetch_sse_shares(whitelist)

    assert result is not None
    assert len(result) == 4
    assert "code" in result.columns
    assert "shares" in result.columns
    assert "date" in result.columns
    assert "etf_type" in result.columns


def test_fetch_sse_shares_unit_conversion(sample_sse_api_response):
    """测试万份 → 亿份转换：TOT_VOL 9106200 万份 = 910.62 亿份"""
    collector = FundFlowCollector()
    whitelist = {"510300", "510500", "159915", "511260"}

    with patch("app.services.fund_flow_collector.requests.get",
               return_value=_mock_sse_response(sample_sse_api_response)):
        result = collector._fetch_sse_shares(whitelist)

    row_510300 = result.loc[result["code"] == "510300", "shares"].iloc[0]
    assert row_510300 == pytest.approx(910.62, rel=0.01)


def test_fetch_sse_shares_uses_stat_date(sample_sse_api_response):
    """测试使用 API 返回的 STAT_DATE 而非 today"""
    collector = FundFlowCollector()
    whitelist = {"510300"}

    with patch("app.services.fund_flow_collector.requests.get",
               return_value=_mock_sse_response(sample_sse_api_response)):
        result = collector._fetch_sse_shares(whitelist)

    assert result.iloc[0]["date"] == "2026-03-03"


def test_fetch_sse_shares_whitelist_filter(sample_sse_api_response):
    """测试白名单过滤"""
    collector = FundFlowCollector()
    whitelist = {"510300", "510500"}  # 只保留 2 个

    with patch("app.services.fund_flow_collector.requests.get",
               return_value=_mock_sse_response(sample_sse_api_response)):
        result = collector._fetch_sse_shares(whitelist)

    assert result is not None
    assert len(result) == 2
    assert set(result["code"]) == {"510300", "510500"}


def test_fetch_sse_shares_date_fallback():
    """测试日期回溯：当日无数据时回溯到前一天"""
    collector = FundFlowCollector()
    whitelist = {"510300"}

    empty_response = {"result": [], "success": "true"}
    data_response = {
        "result": [
            {"SEC_CODE": "510300", "TOT_VOL": "9106200.00", "STAT_DATE": "2026-03-03", "ETF_TYPE": "股票ETF"},
        ],
        "success": "true",
    }

    # 第一次调用（今天）返回空，第二次（昨天）返回数据
    with patch("app.services.fund_flow_collector.requests.get",
               side_effect=[
                   _mock_sse_response(empty_response),
                   _mock_sse_response(data_response),
               ]):
        result = collector._fetch_sse_shares(whitelist)

    assert result is not None
    assert len(result) == 1
    assert result.iloc[0]["date"] == "2026-03-03"


def test_fetch_sse_shares_retry_on_failure():
    """测试网络异常时 3 次重试后返回 None"""
    collector = FundFlowCollector()
    whitelist = {"510300"}

    with patch("app.services.fund_flow_collector.requests.get",
               side_effect=Exception("Connection error")):
        result = collector._fetch_sse_shares(whitelist)

    assert result is None
```

**Step 2: 运行测试确认全部失败**

Run: `cd backend && python -m pytest tests/services/test_fund_flow_collector.py::test_fetch_sse_shares_success tests/services/test_fund_flow_collector.py::test_fetch_sse_shares_unit_conversion tests/services/test_fund_flow_collector.py::test_fetch_sse_shares_uses_stat_date tests/services/test_fund_flow_collector.py::test_fetch_sse_shares_whitelist_filter tests/services/test_fund_flow_collector.py::test_fetch_sse_shares_date_fallback tests/services/test_fund_flow_collector.py::test_fetch_sse_shares_retry_on_failure -v`

Expected: 全部 FAIL（`AttributeError: 'FundFlowCollector' object has no attribute '_fetch_sse_shares'`）

---

## Task 2: 新增 `_fetch_sse_shares()` 方法 — 实现

**Files:**
- Modify: `backend/app/services/fund_flow_collector.py`

**Step 1: 添加 `import requests` 到文件顶部**

在 `import pandas as pd` 之后添加：

```python
import requests
```

**Step 2: 在 `_fetch_em_shares()` 方法之前插入 `_fetch_sse_shares()` 方法**

在 `_build_etf_whitelist()` 方法之后、`_fetch_em_shares()` 方法之前插入：

```python
    def _fetch_sse_shares(self, whitelist: set) -> Optional[pd.DataFrame]:
        """
        从上交所官方 API 获取 ETF 份额数据

        自动向前回溯最近 5 个日期（跳过周末），找到第一个有数据的日期。
        每个日期请求最多重试 3 次。

        Args:
            whitelist: ETF 代码白名单

        Returns:
            标准化 DataFrame（columns: code, shares, date, etf_type），失败时返回 None
        """
        from datetime import timedelta

        SSE_API_URL = "https://query.sse.com.cn/commonQuery.do"
        SSE_HEADERS = {
            "Referer": "https://www.sse.com.cn/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

        today = datetime.now(ZoneInfo("Asia/Shanghai")).date()

        # 向前回溯最近 5 个日期（跳过周末）
        dates_to_try = []
        d = today
        while len(dates_to_try) < 5:
            if d.weekday() < 5:  # 周一到周五
                dates_to_try.append(d)
            d -= timedelta(days=1)

        for target_date in dates_to_try:
            date_str = target_date.strftime("%Y-%m-%d")

            for attempt in range(3):
                try:
                    logger.info(f"Fetching SSE shares for {date_str} (attempt {attempt + 1}/3)...")
                    resp = requests.get(
                        SSE_API_URL,
                        params={
                            "sqlId": "COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L",
                            "STAT_DATE": date_str,
                        },
                        headers=SSE_HEADERS,
                        timeout=30,
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    records = data.get("result", [])
                    if not records:
                        logger.info(f"SSE returned no data for {date_str}, trying earlier date...")
                        break  # 该日期无数据，尝试更早的日期

                    df = pd.DataFrame(records)

                    # 白名单过滤
                    df = df[df["SEC_CODE"].astype(str).isin(whitelist)]

                    if df.empty:
                        logger.info(f"SSE data for {date_str} has no whitelisted ETFs")
                        break

                    # 标准化列名和单位：TOT_VOL 单位为万份，转换为亿份（÷10000）
                    result = pd.DataFrame({
                        "code": df["SEC_CODE"].astype(str).values,
                        "shares": pd.to_numeric(df["TOT_VOL"], errors="coerce") / 1e4,
                        "date": df["STAT_DATE"].astype(str).values,
                        "etf_type": df["ETF_TYPE"].astype(str).values if "ETF_TYPE" in df.columns else None,
                    })

                    logger.info(f"Fetched {len(result)} ETF shares from SSE (date: {date_str})")
                    return result

                except Exception as e:
                    logger.warning(f"SSE fetch attempt {attempt + 1} for {date_str} failed: {e}")
                    if attempt < 2:
                        time.sleep(3)

        logger.error("Failed to fetch SSE shares after trying 5 dates")
        return None
```

**Step 3: 运行 Task 1 中的测试确认全部通过**

Run: `cd backend && python -m pytest tests/services/test_fund_flow_collector.py -k "test_fetch_sse" -v`

Expected: 6 passed

**Step 4: 运行全部测试确认无回归**

Run: `cd backend && python -m pytest tests/services/test_fund_flow_collector.py -v`

Expected: 全部通过（包括现有 EM 测试）

**Step 5: Commit**

```bash
git add backend/app/services/fund_flow_collector.py backend/tests/services/test_fund_flow_collector.py
git commit -m "feat: add _fetch_sse_shares() method with SSE official API

Implements SSE API client with date fallback (5 weekdays) and 3x retry.
Converts TOT_VOL from 万份 to 亿份. Uses STAT_DATE from API response.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 3: 切换 `collect_daily_snapshot()` 到 SSE 数据源

**Files:**
- Modify: `backend/app/services/fund_flow_collector.py`

**Step 1: 更新模块 docstring**

将文件顶部 docstring 从：
```python
"""
资金流向采集服务

通过 Sina 白名单 + EastMoney 份额 + 深交所补充 三步管线采集 ETF 份额数据，
使用 APScheduler 定时调度。
"""
```

改为：
```python
"""
资金流向采集服务

通过 Sina 白名单 + 上交所官方 + 深交所官方 三步管线采集 ETF 份额数据，
使用 APScheduler 定时调度。
"""
```

**Step 2: 在 `_fetch_em_shares()` 方法上方添加弃用注释**

```python
    # [DEPRECATED] 2026-03-04: EastMoney push2 服务器已封锁日本云服务器 IP 段，
    # 该方法不再被 collect_daily_snapshot() 调用。保留代码供参考。
    def _fetch_em_shares(self, whitelist: set) -> Optional[pd.DataFrame]:
```

**Step 3: 修改 `collect_daily_snapshot()` 方法**

将整个方法体替换为：

```python
    def collect_daily_snapshot(self) -> Dict[str, Any]:
        """
        执行每日份额数据采集

        流程：
        1. 从 Sina 列表构建 ETF 白名单
        2. 从上交所官方 API 获取沪市份额数据
        3. 从深交所官方获取深市数据
        4. 合并并保存到数据库

        Returns:
            采集结果字典
        """
        logger.info("Starting daily ETF share collection...")

        # 1. 构建白名单
        whitelist = self._build_etf_whitelist()
        if whitelist is None:
            logger.error("Failed to build ETF whitelist, aborting collection")
            return {
                "success": False,
                "collected": 0,
                "failed": 1,
                "message": "Failed to build ETF whitelist",
            }

        # 2. 获取上交所官方份额数据
        sse_df = self._fetch_sse_shares(whitelist)

        # 3. 获取深交所官方数据
        szse_df = self._fetch_szse_shares(whitelist)

        # 4. 合并数据：同一 (code, date) 以 SZSE 为准
        if sse_df is not None and szse_df is not None:
            szse_keys = set(zip(szse_df["code"], szse_df["date"]))
            sse_keep = [k not in szse_keys for k in zip(sse_df["code"], sse_df["date"])]
            merged_df = pd.concat(
                [sse_df[sse_keep], szse_df],
                ignore_index=True,
            )
        elif sse_df is not None:
            merged_df = sse_df
        elif szse_df is not None:
            merged_df = szse_df
        else:
            logger.error("All data sources failed")
            return {
                "success": False,
                "collected": 0,
                "failed": 1,
                "message": "All data sources failed",
            }

        # 5. 保存到数据库
        total_collected = self._save_to_database(merged_df)

        sources = []
        if sse_df is not None:
            sources.append(f"SSE: {len(sse_df)}")
        if szse_df is not None:
            sources.append(f"SZSE: {len(szse_df)}")

        message = f"Collected {total_collected} records ({', '.join(sources)})"
        logger.info(message)

        return {
            "success": True,
            "collected": total_collected,
            "failed": 0 if sse_df is not None else 1,
            "message": message,
        }
```

**Step 4: 运行全部测试确认无回归**

Run: `cd backend && python -m pytest tests/services/test_fund_flow_collector.py -v`

Expected: 现有 `_fetch_em_shares` 的 3 个单元测试仍通过，`collect_daily_snapshot` 的 4 个集成测试会失败（因为它们还在 mock `_fetch_em_shares`）。

---

## Task 4: 更新集成测试适配 SSE 数据源

**Files:**
- Modify: `backend/tests/services/test_fund_flow_collector.py`

**Step 1: 更新 `test_collect_daily_snapshot_new_flow`**

将 mock 从 `_fetch_em_shares` 改为 `_fetch_sse_shares`，变量名从 `em_df` 改为 `sse_df`：

```python
def test_collect_daily_snapshot_new_flow():
    """测试采集流程：同日期时 SZSE 覆盖 SSE 深市数据"""
    collector = FundFlowCollector()

    whitelist = {"510300", "510500", "159915", "159919"}

    sse_df = pd.DataFrame({
        "code": ["510300", "510500", "159915", "159919"],
        "shares": [910.62, 450.30, 320.45, 280.12],
        "date": ["2026-02-17"] * 4,
        "etf_type": [None] * 4,
    })

    szse_df = pd.DataFrame({
        "code": ["159915", "159919"],
        "shares": [321.00, 281.00],
        "date": ["2026-02-17"] * 2,
        "etf_type": ["ETF"] * 2,
    })

    with patch.object(collector, "_build_etf_whitelist", return_value=whitelist), \
         patch.object(collector, "_fetch_sse_shares", return_value=sse_df), \
         patch.object(collector, "_fetch_szse_shares", return_value=szse_df), \
         patch.object(collector, "_save_to_database", return_value=4) as mock_save:

        result = collector.collect_daily_snapshot()

        assert result["success"] is True
        assert result["collected"] == 4

        # 验证合并后只有 4 条（SZSE 覆盖了同日期的 SSE 深市数据）
        saved_df = mock_save.call_args[0][0]
        assert len(saved_df) == 4
        szse_159915 = saved_df.loc[saved_df["code"] == "159915", "shares"].iloc[0]
        assert szse_159915 == pytest.approx(321.00, rel=0.01)
```

**Step 2: 更新 `test_collect_daily_snapshot_different_dates_kept`**

```python
def test_collect_daily_snapshot_different_dates_kept():
    """测试不同日期的数据都保留（SSE 昨天 + SZSE 今天）"""
    collector = FundFlowCollector()

    whitelist = {"510300", "159915"}

    sse_df = pd.DataFrame({
        "code": ["510300", "159915"],
        "shares": [910.62, 320.45],
        "date": ["2026-02-14"] * 2,
        "etf_type": [None] * 2,
    })

    szse_df = pd.DataFrame({
        "code": ["159915"],
        "shares": [321.00],
        "date": ["2026-02-17"],
        "etf_type": ["ETF"],
    })

    with patch.object(collector, "_build_etf_whitelist", return_value=whitelist), \
         patch.object(collector, "_fetch_sse_shares", return_value=sse_df), \
         patch.object(collector, "_fetch_szse_shares", return_value=szse_df), \
         patch.object(collector, "_save_to_database", return_value=3) as mock_save:

        result = collector.collect_daily_snapshot()

        # SSE 的 159915(02-14) 和 SZSE 的 159915(02-17) 日期不同，都保留
        saved_df = mock_save.call_args[0][0]
        assert len(saved_df) == 3
        codes_159915 = saved_df[saved_df["code"] == "159915"]
        assert len(codes_159915) == 2
```

**Step 3: 更新 `test_collect_daily_snapshot_em_failure_fallback`**

重命名并修改 mock 目标：

```python
def test_collect_daily_snapshot_sse_failure_fallback():
    """测试 SSE 失败时降级到仅 SZSE"""
    collector = FundFlowCollector()

    whitelist = {"510300", "159915"}

    szse_df = pd.DataFrame({
        "code": ["159915"],
        "shares": [321.00],
        "date": ["2026-02-17"],
        "etf_type": ["ETF"],
    })

    with patch.object(collector, "_build_etf_whitelist", return_value=whitelist), \
         patch.object(collector, "_fetch_sse_shares", return_value=None), \
         patch.object(collector, "_fetch_szse_shares", return_value=szse_df), \
         patch.object(collector, "_save_to_database", return_value=1):

        result = collector.collect_daily_snapshot()

        assert result["success"] is True
        assert result["collected"] == 1
```

**Step 4: 运行全部测试**

Run: `cd backend && python -m pytest tests/services/test_fund_flow_collector.py -v`

Expected: 全部通过

**Step 5: Commit**

```bash
git add backend/app/services/fund_flow_collector.py backend/tests/services/test_fund_flow_collector.py
git commit -m "feat: switch collect_daily_snapshot() from EastMoney to SSE API

- Replace _fetch_em_shares() call with _fetch_sse_shares()
- Rename em_df/em_keep variables to sse_df/sse_keep
- Update log messages from 'EastMoney' to 'SSE'
- Mark _fetch_em_shares() as deprecated (IP blocked)
- Update module docstring
- Update integration tests to mock _fetch_sse_shares

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 5: 文档同步更新

**Files:**
- Modify: `docs/design/2026-02-08-fund-flow-analysis-design.md`
- Modify: `docs/implementation/2026-02-09-fund-flow-analysis-impl.md`

**Step 1: 更新设计文档中的数据源描述**

在 `docs/design/2026-02-08-fund-flow-analysis-design.md` 中：

1. 第 37 行的数据源表格，将 `fund_etf_scale_sse` 行更新说明：

```
| `fund_etf_scale_sse` | 上交所 ETF 份额快照 | ❌ 无 | ⚠️ 已弃用（akshare 实现有缺陷） | 593只 |
```

2. 第 125-126 行的架构图，更新采集层描述：

```
│    ├── fetch_sse_shares() - 上交所数据（SSE 官方 API）  │
│    └── fetch_szse_shares() - 深交所数据                 │
```

3. 第 251 行，更新采集范围说明：

```
- **采集所有 ETF**：上交所通过 SSE 官方 API（`query.sse.com.cn`），深交所通过 `fund_etf_scale_szse` 获取数据
```

**Step 2: 更新实现文档中的采集器说明**

在 `docs/implementation/2026-02-09-fund-flow-analysis-impl.md` 中：

1. 第 175-177 行，更新 `_fetch_sse_shares` 方法说明：

```
2. `_fetch_sse_shares(whitelist: set) -> pd.DataFrame`
   - 使用 `requests` 直接调用 SSE 官方 API（`query.sse.com.cn/commonQuery.do`）
   - 需要 `Referer: https://www.sse.com.cn/` 请求头
   - 自动向前回溯 5 个工作日，找到有数据的日期
   - 返回标准化 DataFrame
```

2. 第 259 行，更新测试说明：

```
- `test_fetch_sse_shares_success` — Mock `requests.get`，验证 SSE API 返回 DataFrame
```

**Step 3: Commit**

```bash
git add docs/design/2026-02-08-fund-flow-analysis-design.md docs/implementation/2026-02-09-fund-flow-analysis-impl.md
git commit -m "docs: update design and impl docs for SSE datasource migration

Reflect the switch from akshare fund_etf_scale_sse() to direct SSE
official API calls in design and implementation documents.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## 端到端验证

完成所有 Task 后，按以下顺序验证：

```bash
# 1. 后端全量测试
cd backend && python -m pytest tests/services/test_fund_flow_collector.py -v

# 2. 确认 _fetch_em_shares 不再被调用
grep -n "_fetch_em_shares" backend/app/services/fund_flow_collector.py
# 预期：仅出现在方法定义处和弃用注释处，不出现在 collect_daily_snapshot() 中

# 3. 确认 import requests 已添加
grep -n "^import requests" backend/app/services/fund_flow_collector.py
# 预期：出现一行
```
