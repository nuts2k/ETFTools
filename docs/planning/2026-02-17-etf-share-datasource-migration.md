# ETF 份额数据源迁移实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 替换已停更的上交所 `fund_etf_scale_sse()` 接口，改用 Sina 列表白名单 + EastMoney 份额 + 深交所官方补充的统一方案。

**Architecture:** 当前 `FundFlowCollector` 分别调用上交所和深交所官方接口采集份额数据。上交所接口已停更（2025-01-15），需要替换为：(1) Sina 列表接口构建 ETF 白名单（最稳定），(2) EastMoney 列表接口获取份额数据（最准确，63.8% <5%），(3) 深交所官方接口补充深市数据（最权威）。深交所数据覆盖 EastMoney 的深市部分。

**Tech Stack:** Python 3.9+, akshare, pandas, SQLModel, pytest

**Reference:** `docs/research/2026-02-17-etf-share-datasource-evaluation.md`

---

## Task 1: 添加 `_build_etf_whitelist()` 方法

**Files:**
- Modify: `backend/app/services/fund_flow_collector.py`
- Modify: `backend/tests/services/test_fund_flow_collector.py`

**Step 1: 写失败测试**

在 `backend/tests/services/test_fund_flow_collector.py` 末尾添加：

```python
@pytest.fixture
def sample_sina_list_data():
    """模拟 Sina 列表接口返回的数据（含债券 ETF）"""
    return pd.DataFrame({
        "代码": ["sh510300", "sh510500", "sz159915", "sh511260", "sh511270"],
        "名称": ["沪深300ETF", "中证500ETF", "创业板ETF", "国泰上证10年期国债ETF", "国债ETF"],
    })


def test_build_etf_whitelist_filters_bond_etfs(sample_sina_list_data):
    """测试白名单构建：过滤债券 ETF"""
    collector = FundFlowCollector()

    with patch("akshare.fund_etf_category_sina", return_value=sample_sina_list_data):
        whitelist = collector._build_etf_whitelist()

    # 应该过滤掉 2 条债券 ETF（511260、511270 名称含"债"）
    assert "510300" in whitelist
    assert "510500" in whitelist
    assert "159915" in whitelist
    assert "511260" not in whitelist
    assert "511270" not in whitelist
    assert len(whitelist) == 3


def test_build_etf_whitelist_returns_none_on_failure():
    """测试 Sina 列表接口失败时返回 None"""
    collector = FundFlowCollector()

    with patch("akshare.fund_etf_category_sina", side_effect=Exception("API error")):
        whitelist = collector._build_etf_whitelist()

    assert whitelist is None
```

**Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/services/test_fund_flow_collector.py::test_build_etf_whitelist_filters_bond_etfs -v`
Expected: FAIL with `AttributeError: 'FundFlowCollector' object has no attribute '_build_etf_whitelist'`

**Step 3: 实现 `_build_etf_whitelist()`**

在 `backend/app/services/fund_flow_collector.py` 的 `FundFlowCollector` 类中，在 `__init__` 之后添加：

```python
def _build_etf_whitelist(self) -> Optional[set]:
    """
    从 Sina 列表接口构建 ETF 白名单（过滤债券 ETF）

    Returns:
        ETF 代码集合（如 {"510300", "159915", ...}），失败时返回 None
    """
    import akshare as ak
    try:
        logger.info("Building ETF whitelist from Sina list...")
        df = ak.fund_etf_category_sina(symbol="ETF基金")
        if df is None or df.empty:
            logger.warning("Sina list is empty")
            return None

        # 清理代码：去掉 sh/sz 前缀
        df["代码"] = df["代码"].astype(str).str.replace("sh", "").str.replace("sz", "")

        # 过滤债券 ETF：代码段 51/52/53/56/58 且名称含"债"
        mask_bond = (
            df["代码"].str.match(r"^(51|52|53|56|58)")
            & df["名称"].str.contains("债", na=False)
        )
        df_filtered = df[~mask_bond]

        whitelist = set(df_filtered["代码"].astype(str))
        logger.info(f"ETF whitelist built: {len(whitelist)} codes (filtered {mask_bond.sum()} bond ETFs)")
        return whitelist

    except Exception as e:
        logger.error(f"Failed to build ETF whitelist: {e}")
        return None
```

**Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/services/test_fund_flow_collector.py::test_build_etf_whitelist_filters_bond_etfs tests/services/test_fund_flow_collector.py::test_build_etf_whitelist_returns_none_on_failure -v`
Expected: 2 passed

**Step 5: 提交**

```bash
cd backend
git add app/services/fund_flow_collector.py tests/services/test_fund_flow_collector.py
git commit -m "feat: add _build_etf_whitelist() for Sina-based ETF filtering"
```

---

## Task 2: 添加 `_fetch_em_shares()` 方法

**Files:**
- Modify: `backend/app/services/fund_flow_collector.py`
- Modify: `backend/tests/services/test_fund_flow_collector.py`

**Step 1: 写失败测试**

在测试文件末尾添加：

```python
@pytest.fixture
def sample_em_data():
    """模拟 EastMoney 列表接口返回的数据"""
    return pd.DataFrame({
        "代码": ["510300", "510500", "159915", "159919"],
        "名称": ["沪深300ETF", "中证500ETF", "创业板ETF", "沪深300ETF"],
        "最新份额": [91062000000.0, 45030000000.0, 32045000000.0, 28012000000.0],
        "数据日期": ["2026-02-13", "2026-02-13", "2026-02-13", "2026-02-13"],
    })


def test_fetch_em_shares_success(sample_em_data):
    """测试成功获取 EastMoney 份额数据"""
    collector = FundFlowCollector()
    whitelist = {"510300", "510500", "159915", "159919"}

    with patch("akshare.fund_etf_spot_em", return_value=sample_em_data):
        result = collector._fetch_em_shares(whitelist)

    assert result is not None
    assert len(result) == 4
    assert "code" in result.columns
    assert "shares" in result.columns
    assert "date" in result.columns
    # 验证份额单位已转换为亿份
    assert result.loc[result["code"] == "510300", "shares"].iloc[0] == pytest.approx(910.62, rel=0.01)


def test_fetch_em_shares_filters_by_whitelist(sample_em_data):
    """测试白名单过滤"""
    collector = FundFlowCollector()
    whitelist = {"510300", "159915"}  # 只要 2 条

    with patch("akshare.fund_etf_spot_em", return_value=sample_em_data):
        result = collector._fetch_em_shares(whitelist)

    assert result is not None
    assert len(result) == 2
    assert set(result["code"]) == {"510300", "159915"}


def test_fetch_em_shares_returns_none_on_failure():
    """测试 EastMoney 接口失败时返回 None"""
    collector = FundFlowCollector()

    with patch("akshare.fund_etf_spot_em", side_effect=Exception("API error")):
        result = collector._fetch_em_shares({"510300"})

    assert result is None
```

**Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/services/test_fund_flow_collector.py::test_fetch_em_shares_success -v`
Expected: FAIL with `AttributeError`

**Step 3: 实现 `_fetch_em_shares()`**

在 `_build_etf_whitelist()` 之后添加：

```python
def _fetch_em_shares(self, whitelist: set) -> Optional[pd.DataFrame]:
    """
    从 EastMoney 列表接口获取 ETF 份额数据（最多重试 3 次）

    Args:
        whitelist: ETF 代码白名单

    Returns:
        标准化 DataFrame（columns: code, shares, date, etf_type），失败时返回 None
    """
    import akshare as ak
    for attempt in range(3):
        try:
            logger.info(f"Fetching EastMoney shares (attempt {attempt + 1}/3)...")
            df = ak.fund_etf_spot_em()
            if df is None or df.empty:
                logger.warning("EastMoney data is empty")
                return None

            # 白名单过滤
            df["代码"] = df["代码"].astype(str)
            df = df[df["代码"].isin(whitelist)]

            # 标准化列名和单位
            result = pd.DataFrame({
                "code": df["代码"].values,
                "shares": pd.to_numeric(df["最新份额"], errors="coerce") / 1e8,
                "date": df["数据日期"].astype(str).values,
            })
            result["etf_type"] = None

            logger.info(f"Fetched {len(result)} ETF shares from EastMoney")
            return result

        except Exception as e:
            logger.warning(f"EastMoney fetch attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                time.sleep(3)

    logger.error("Failed to fetch EastMoney shares after 3 attempts")
    return None
```

**Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/services/test_fund_flow_collector.py::test_fetch_em_shares_success tests/services/test_fund_flow_collector.py::test_fetch_em_shares_filters_by_whitelist tests/services/test_fund_flow_collector.py::test_fetch_em_shares_returns_none_on_failure -v`
Expected: 3 passed

**Step 5: 提交**

```bash
cd backend
git add app/services/fund_flow_collector.py tests/services/test_fund_flow_collector.py
git commit -m "feat: add _fetch_em_shares() for EastMoney share data"
```

---

## Task 3: 更新 `_fetch_szse_shares()` 支持白名单过滤

**Files:**
- Modify: `backend/app/services/fund_flow_collector.py`
- Modify: `backend/tests/services/test_fund_flow_collector.py`

**Step 1: 写失败测试**

在测试文件末尾添加：

```python
@pytest.fixture
def sample_szse_data_with_lof():
    """模拟深交所返回的数据（含 LOF 和 ETF）"""
    return pd.DataFrame({
        "基金代码": ["159915", "159919", "160219", "169106"],
        "基金简称": ["创业板ETF", "沪深300ETF", "医药LOF", "东方红创优定开"],
        "基金类别": ["ETF", "ETF", "LOF", "LOF"],
        "基金份额": [32045000000.0, 28012000000.0, 157574115.0, 54000000.0],
    })


def test_fetch_szse_shares_filters_etf_only(sample_szse_data_with_lof):
    """测试深交所数据只保留 ETF，过滤 LOF"""
    collector = FundFlowCollector()
    whitelist = {"159915", "159919", "160219", "169106"}

    with patch("akshare.fund_etf_scale_szse", return_value=sample_szse_data_with_lof):
        result = collector._fetch_szse_shares(whitelist)

    assert result is not None
    assert len(result) == 2  # 只有 2 条 ETF
    assert set(result["code"]) == {"159915", "159919"}


def test_fetch_szse_shares_filters_by_whitelist(sample_szse_data_with_lof):
    """测试深交所数据按白名单过滤"""
    collector = FundFlowCollector()
    whitelist = {"159915"}  # 只要 1 条

    with patch("akshare.fund_etf_scale_szse", return_value=sample_szse_data_with_lof):
        result = collector._fetch_szse_shares(whitelist)

    assert result is not None
    assert len(result) == 1
    assert result.iloc[0]["code"] == "159915"
    # 验证份额单位已转换为亿份
    assert result.iloc[0]["shares"] == pytest.approx(320.45, rel=0.01)
```

**Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/services/test_fund_flow_collector.py::test_fetch_szse_shares_filters_etf_only -v`
Expected: FAIL（旧签名不接受 whitelist 参数）

**Step 3: 重写 `_fetch_szse_shares()`**

替换 `backend/app/services/fund_flow_collector.py` 中的 `_fetch_szse_shares` 方法：

```python
def _fetch_szse_shares(self, whitelist: Optional[set] = None) -> Optional[pd.DataFrame]:
    """
    获取深交所 ETF 份额数据（最多重试 3 次，间隔 3 秒）

    Args:
        whitelist: ETF 代码白名单（可选，传入时过滤非白名单代码）

    Returns:
        标准化 DataFrame（columns: code, shares, date, etf_type），失败时返回 None
    """
    import akshare as ak
    for attempt in range(3):
        try:
            logger.info(f"Fetching SZSE shares (attempt {attempt + 1}/3)...")
            df = ak.fund_etf_scale_szse()
            if df is None or df.empty:
                logger.warning("SZSE data is empty")
                return None

            # 只保留 ETF（排除 LOF）
            df = df[df["基金类别"] == "ETF"]

            # 清理代码
            df["基金代码"] = df["基金代码"].astype(str).str.replace("sz", "").str.replace("sh", "")

            # 白名单过滤
            if whitelist:
                df = df[df["基金代码"].isin(whitelist)]

            # 标准化列名和单位
            today = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d")
            result = pd.DataFrame({
                "code": df["基金代码"].values,
                "shares": pd.to_numeric(df["基金份额"], errors="coerce") / 1e8,
                "date": today,
                "etf_type": df["基金类别"].values if "基金类别" in df.columns else None,
            })

            logger.info(f"Fetched {len(result)} records from SZSE")
            return result

        except Exception as e:
            logger.warning(f"SZSE fetch attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                time.sleep(3)

    logger.error("Failed to fetch SZSE shares after 3 attempts")
    return None
```

**Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/services/test_fund_flow_collector.py::test_fetch_szse_shares_filters_etf_only tests/services/test_fund_flow_collector.py::test_fetch_szse_shares_filters_by_whitelist -v`
Expected: 2 passed

**Step 5: 提交**

```bash
cd backend
git add app/services/fund_flow_collector.py tests/services/test_fund_flow_collector.py
git commit -m "feat: update _fetch_szse_shares() with whitelist filter and ETF-only"
```

---

## Task 4: 重写 `collect_daily_snapshot()` 和 `_save_to_database()`

**Files:**
- Modify: `backend/app/services/fund_flow_collector.py`
- Modify: `backend/tests/services/test_fund_flow_collector.py`

**Step 1: 写失败测试**

在测试文件末尾添加：

```python
def test_collect_daily_snapshot_new_flow():
    """测试新的采集流程：白名单 → EastMoney → SZSE 补充"""
    collector = FundFlowCollector()

    whitelist = {"510300", "510500", "159915", "159919"}

    em_df = pd.DataFrame({
        "code": ["510300", "510500", "159915", "159919"],
        "shares": [910.62, 450.30, 320.45, 280.12],
        "date": ["2026-02-13"] * 4,
        "etf_type": [None] * 4,
    })

    szse_df = pd.DataFrame({
        "code": ["159915", "159919"],
        "shares": [321.00, 281.00],  # 深交所数据略有不同
        "date": ["2026-02-17"] * 2,
        "etf_type": ["ETF"] * 2,
    })

    with patch.object(collector, "_build_etf_whitelist", return_value=whitelist), \
         patch.object(collector, "_fetch_em_shares", return_value=em_df), \
         patch.object(collector, "_fetch_szse_shares", return_value=szse_df), \
         patch.object(collector, "_save_to_database", return_value=4) as mock_save:

        result = collector.collect_daily_snapshot()

        assert result["success"] is True
        assert result["collected"] == 4

        # 验证 _save_to_database 被调用，且深市数据被 SZSE 覆盖
        saved_df = mock_save.call_args[0][0]
        szse_159915 = saved_df.loc[saved_df["code"] == "159915", "shares"].iloc[0]
        assert szse_159915 == pytest.approx(321.00, rel=0.01)  # SZSE 覆盖了 EastMoney


def test_collect_daily_snapshot_em_failure_fallback():
    """测试 EastMoney 失败时降级到 SZSE"""
    collector = FundFlowCollector()

    whitelist = {"510300", "159915"}

    szse_df = pd.DataFrame({
        "code": ["159915"],
        "shares": [321.00],
        "date": ["2026-02-17"],
        "etf_type": ["ETF"],
    })

    with patch.object(collector, "_build_etf_whitelist", return_value=whitelist), \
         patch.object(collector, "_fetch_em_shares", return_value=None), \
         patch.object(collector, "_fetch_szse_shares", return_value=szse_df), \
         patch.object(collector, "_save_to_database", return_value=1):

        result = collector.collect_daily_snapshot()

        # 只有深市数据，但仍算成功
        assert result["success"] is True
        assert result["collected"] == 1


def test_collect_daily_snapshot_whitelist_failure():
    """测试白名单构建失败时的处理"""
    collector = FundFlowCollector()

    with patch.object(collector, "_build_etf_whitelist", return_value=None), \
         patch.object(collector, "_save_to_database", return_value=0):

        result = collector.collect_daily_snapshot()

        assert result["success"] is False
        assert result["collected"] == 0
```

**Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/services/test_fund_flow_collector.py::test_collect_daily_snapshot_new_flow -v`
Expected: FAIL（旧的 `collect_daily_snapshot` 不调用 `_build_etf_whitelist`）

**Step 3: 重写 `collect_daily_snapshot()` 和 `_save_to_database()`**

替换 `backend/app/services/fund_flow_collector.py` 中的两个方法：

```python
def _save_to_database(self, df: pd.DataFrame) -> int:
    """
    保存标准化数据到数据库

    Args:
        df: 标准化 DataFrame（columns: code, shares, date, etf_type）

    Returns:
        成功插入的行数
    """
    if df is None or df.empty:
        return 0

    success_count = 0
    with Session(share_history_engine) as session:
        for _, row in df.iterrows():
            try:
                shares_val = float(row["shares"])
                if pd.isna(shares_val) or shares_val <= 0:
                    continue

                code = str(row["code"])
                # 根据代码前缀判断交易所
                exchange = "SZSE" if code.startswith(("15", "16")) else "SSE"

                record = ETFShareHistory(
                    code=code,
                    date=str(row["date"]),
                    shares=shares_val,
                    exchange=exchange,
                    etf_type=str(row.get("etf_type", "")) if pd.notna(row.get("etf_type")) else None,
                )
                session.add(record)
                session.commit()
                success_count += 1
            except IntegrityError:
                session.rollback()
                continue
            except Exception as e:
                logger.error(f"Failed to insert record {row.get('code')}: {e}")
                session.rollback()
                continue

    logger.info(f"Saved {success_count} records to database")
    return success_count

def collect_daily_snapshot(self) -> Dict[str, Any]:
    """
    执行每日份额数据采集

    流程：
    1. 从 Sina 列表构建 ETF 白名单
    2. 从 EastMoney 获取份额数据（主力）
    3. 从深交所官方获取深市数据（补充，覆盖 EastMoney 深市部分）
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

    # 2. 获取 EastMoney 份额数据
    em_df = self._fetch_em_shares(whitelist)

    # 3. 获取深交所官方数据
    szse_df = self._fetch_szse_shares(whitelist)

    # 4. 合并数据：SZSE 覆盖 EastMoney 的深市部分
    if em_df is not None and szse_df is not None:
        szse_codes = set(szse_df["code"])
        merged_df = pd.concat(
            [em_df[~em_df["code"].isin(szse_codes)], szse_df],
            ignore_index=True,
        )
    elif em_df is not None:
        merged_df = em_df
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
    if em_df is not None:
        sources.append(f"EastMoney: {len(em_df)}")
    if szse_df is not None:
        sources.append(f"SZSE: {len(szse_df)}")

    message = f"Collected {total_collected} records ({', '.join(sources)})"
    logger.info(message)

    return {
        "success": total_collected > 0,
        "collected": total_collected,
        "failed": 0 if em_df is not None else 1,
        "message": message,
    }
```

**Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/services/test_fund_flow_collector.py::test_collect_daily_snapshot_new_flow tests/services/test_fund_flow_collector.py::test_collect_daily_snapshot_em_failure_fallback tests/services/test_fund_flow_collector.py::test_collect_daily_snapshot_whitelist_failure -v`
Expected: 3 passed

**Step 5: 提交**

```bash
cd backend
git add app/services/fund_flow_collector.py tests/services/test_fund_flow_collector.py
git commit -m "feat: rewrite collect_daily_snapshot() with unified data source approach"
```

---

## Task 5: 清理旧代码 + 更新旧测试 + 全量验证

**Files:**
- Modify: `backend/app/services/fund_flow_collector.py`
- Modify: `backend/tests/services/test_fund_flow_collector.py`

**Step 1: 删除旧代码**

从 `backend/app/services/fund_flow_collector.py` 中删除：
- `COLUMN_MAP_SSE` 类变量
- `COLUMN_MAP_SZSE` 类变量
- `_fetch_sse_shares()` 方法

**Step 2: 更新旧测试**

旧测试中有 5 个测试需要更新或删除：

1. **删除** `test_fetch_sse_shares_success` — SSE 接口已移除
2. **更新** `test_fetch_szse_shares_success` — 新签名返回标准化 DataFrame
3. **更新** `test_save_to_database` — 新签名不需要 column_map
4. **更新** `test_save_to_database_dedup` — 同上
5. **删除** `test_collect_daily_snapshot_partial_failure` — 旧流程测试
6. **删除** `test_collect_daily_snapshot_all_success` — 旧流程测试
7. **删除** `sample_sse_data` fixture — 不再需要
8. **更新** `sample_szse_data` fixture — 新格式

更新后的旧测试：

```python
@pytest.fixture
def sample_szse_data():
    """模拟深交所返回的数据（实际 akshare 列名，份额单位为份，无日期列）"""
    return pd.DataFrame({
        "基金代码": ["159915", "159919"],
        "基金简称": ["创业板ETF", "沪深300ETF"],
        "基金类别": ["ETF", "ETF"],
        "基金份额": [32045000000.0, 28012000000.0],
    })


def test_fetch_szse_shares_success(sample_szse_data):
    """测试成功获取深交所数据"""
    collector = FundFlowCollector()

    with patch("akshare.fund_etf_scale_szse", return_value=sample_szse_data):
        result = collector._fetch_szse_shares()

    assert result is not None
    assert len(result) == 2
    assert "code" in result.columns
    assert "shares" in result.columns


def test_save_to_database(test_share_engine):
    """测试保存标准化数据到数据库"""
    collector = FundFlowCollector()

    df = pd.DataFrame({
        "code": ["510300", "159915"],
        "shares": [910.62, 320.45],
        "date": ["2026-02-13", "2026-02-13"],
        "etf_type": ["股票型", "股票型"],
    })

    with patch("app.services.fund_flow_collector.share_history_engine", test_share_engine):
        count = collector._save_to_database(df)

    assert count == 2

    with Session(test_share_engine) as session:
        records = session.query(ETFShareHistory).all()
        assert len(records) == 2
        # 验证交易所根据代码前缀自动判断
        sse_record = [r for r in records if r.code == "510300"][0]
        szse_record = [r for r in records if r.code == "159915"][0]
        assert sse_record.exchange == "SSE"
        assert szse_record.exchange == "SZSE"


def test_save_to_database_dedup(test_share_engine):
    """测试重复数据去重"""
    collector = FundFlowCollector()

    df = pd.DataFrame({
        "code": ["510300", "159915"],
        "shares": [910.62, 320.45],
        "date": ["2026-02-13", "2026-02-13"],
        "etf_type": [None, None],
    })

    with patch("app.services.fund_flow_collector.share_history_engine", test_share_engine):
        count1 = collector._save_to_database(df)
        assert count1 == 2

        count2 = collector._save_to_database(df)
        assert count2 == 0

        with Session(test_share_engine) as session:
            records = session.query(ETFShareHistory).all()
            assert len(records) == 2
```

**Step 3: 运行全量测试**

Run: `cd backend && python -m pytest tests/services/test_fund_flow_collector.py -v`
Expected: ALL passed（新旧测试全部通过）

**Step 4: 运行项目全量测试确认无回归**

Run: `cd backend && python -m pytest tests/ -v --timeout=30`
Expected: ALL passed

**Step 5: 提交**

```bash
cd backend
git add app/services/fund_flow_collector.py tests/services/test_fund_flow_collector.py
git commit -m "refactor: remove deprecated SSE fetch, update tests for new data flow"
```

---

## Task 6: 更新文档

**Files:**
- Modify: `docs/research/2026-02-17-etf-share-datasource-evaluation.md`

**Step 1: 更新实施计划状态**

在 `docs/research/2026-02-17-etf-share-datasource-evaluation.md` 的第 10 节中，将已完成的项目标记为 `[x]`：

```markdown
### 10.1 立即行动

- [x] 完成数据源调研和对比分析
- [x] 修改 `fund_flow_collector.py` 实现新方案
- [x] 更新列名映射和数据处理逻辑
- [x] 增加数据验证和容错机制
- [x] 编写单元测试
```

**Step 2: 提交**

```bash
git add docs/research/2026-02-17-etf-share-datasource-evaluation.md
git commit -m "docs: update implementation status in research document"
```
