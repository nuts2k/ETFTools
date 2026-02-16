# Phase 2 数据源抽象与 Baostock 集成 - 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 通过抽象数据源接口统一管理历史数据获取，集成 Baostock 作为主数据源，优化降级策略。

**Architecture:** 定义 HistoryDataSource 协议，BaostockSource 和 EastMoneyHistorySource 各自实现。DataSourceManager 按配置优先级编排数据源，结合 Phase 1 已有的 DataSourceMetrics 实现熔断逻辑。akshare_service.py 的 fetch_history_raw() 委托给 manager，保留 DiskCache 兜底。

**Tech Stack:** Python 3.9+, FastAPI, baostock, pandas, pydantic-settings, pytest

**Design Doc:** `docs/design/2026-02-16-datasource-abstraction-design.md`

---

## Task 1: 添加配置项

**Files:**
- Modify: `backend/app/core/config.py:13-50`
- Test: `backend/tests/core/test_config_datasource.py` (create)

**Step 1: Write the failing test**

```python
# backend/tests/core/test_config_datasource.py
"""数据源配置项测试"""
import pytest


class TestDataSourceConfig:
    def test_default_history_sources(self):
        """默认历史数据源优先级列表"""
        from app.core.config import settings
        assert settings.HISTORY_DATA_SOURCES == ["baostock", "eastmoney"]

    def test_baostock_enabled_default(self):
        from app.core.config import settings
        assert settings.BAOSTOCK_ENABLED is True

    def test_circuit_breaker_defaults(self):
        from app.core.config import settings
        assert settings.CIRCUIT_BREAKER_THRESHOLD == 0.1
        assert settings.CIRCUIT_BREAKER_WINDOW == 10
        assert settings.CIRCUIT_BREAKER_COOLDOWN == 300
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/core/test_config_datasource.py -v`
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'HISTORY_DATA_SOURCES'`

**Step 3: Write minimal implementation**

在 `backend/app/core/config.py` 的 `Settings` 类中，`ENABLE_RATE_LIMIT` 之后添加：

```python
    # 数据源配置
    HISTORY_DATA_SOURCES: List[str] = ["baostock", "eastmoney"]
    BAOSTOCK_ENABLED: bool = True
    CIRCUIT_BREAKER_THRESHOLD: float = 0.1
    CIRCUIT_BREAKER_WINDOW: int = 10
    CIRCUIT_BREAKER_COOLDOWN: int = 300
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/core/test_config_datasource.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add backend/app/core/config.py backend/tests/core/test_config_datasource.py
git commit -m "feat: add datasource config items for Phase 2"
```

---

## Task 2: 熔断逻辑 — 扩展 DataSourceMetrics

**Files:**
- Modify: `backend/app/core/metrics.py:24-47` (SourceStats) 和 `49-165` (DataSourceMetrics)
- Test: `backend/tests/core/test_metrics.py` (append)

**Step 1: Write the failing tests**

在 `backend/tests/core/test_metrics.py` 末尾追加：

```python
class TestCircuitBreaker:
    def test_not_open_for_unknown_source(self, metrics):
        assert metrics.is_circuit_open("nonexistent") is False

    def test_not_open_with_insufficient_data(self, metrics):
        """数据不足 window 大小时不触发熔断"""
        for _ in range(5):
            metrics.record_failure("src", "err", 10.0)
        assert metrics.is_circuit_open("src", threshold=0.1, window=10) is False

    def test_opens_when_below_threshold(self, metrics):
        """成功率低于阈值时开启熔断"""
        for _ in range(10):
            metrics.record_failure("src", "err", 10.0)
        assert metrics.is_circuit_open("src", threshold=0.1, window=10) is True

    def test_stays_open_during_cooldown(self, metrics):
        """熔断冷却期内保持开启"""
        for _ in range(10):
            metrics.record_failure("src", "err", 10.0)
        metrics.is_circuit_open("src", threshold=0.1, window=10, cooldown=300)
        # 立即再次检查，仍然开启
        assert metrics.is_circuit_open("src", threshold=0.1, window=10, cooldown=300) is True

    def test_half_open_after_cooldown(self, metrics):
        """冷却期过后进入半开状态（允许探测）"""
        for _ in range(10):
            metrics.record_failure("src", "err", 10.0)
        metrics.is_circuit_open("src", threshold=0.1, window=10, cooldown=0)
        # cooldown=0 立即过期，应允许探测
        import time
        time.sleep(0.01)
        assert metrics.is_circuit_open("src", threshold=0.1, window=10, cooldown=0) is False

    def test_not_open_when_above_threshold(self, metrics):
        """成功率高于阈值时不触发"""
        for _ in range(8):
            metrics.record_success("src", 10.0)
        for _ in range(2):
            metrics.record_failure("src", "err", 10.0)
        assert metrics.is_circuit_open("src", threshold=0.1, window=10) is False
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/core/test_metrics.py::TestCircuitBreaker -v`
Expected: FAIL — `AttributeError: 'DataSourceMetrics' object has no attribute 'is_circuit_open'`

**Step 3: Write minimal implementation**

3a. 在 `SourceStats.__slots__` 中添加 `"circuit_open_until"`，在 `__init__` 中初始化：

```python
self.circuit_open_until: Optional[float] = None  # monotonic timestamp
```

3b. 在 `DataSourceMetrics` 类中添加方法：

```python
    def is_circuit_open(
        self,
        source: str,
        threshold: float = 0.1,
        window: int = 10,
        cooldown: int = 300,
    ) -> bool:
        """
        检查数据源是否被熔断。

        规则：
        - 最近 window 次调用成功率 < threshold → 开启熔断
        - 熔断持续 cooldown 秒
        - 到期后允许一次探测（半开状态）
        """
        import time as _time

        with self._lock:
            stats = self._sources.get(source)
            if not stats:
                return False

            now = _time.monotonic()

            # 在冷却期内 → 熔断开启
            if stats.circuit_open_until is not None:
                if now < stats.circuit_open_until:
                    return True
                # 冷却期过 → 半开，允许探测
                stats.circuit_open_until = None
                return False

            # 数据不足 → 不熔断
            recent = list(stats.results)[-window:]
            if len(recent) < window:
                return False

            # 成功率低于阈值 → 开启熔断
            rate = sum(recent) / len(recent)
            if rate < threshold:
                stats.circuit_open_until = now + cooldown
                return True

            return False
```

注意：需要在文件顶部 `import time` 已存在，但方法内用 `_time` 别名避免与参数冲突。实际实现中直接用模块级 `time.monotonic()` 即可。

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/core/test_metrics.py -v`
Expected: ALL passed（包括原有测试和新增的 6 个熔断测试）

**Step 5: Commit**

```bash
git add backend/app/core/metrics.py backend/tests/core/test_metrics.py
git commit -m "feat: add circuit breaker logic to DataSourceMetrics"
```

---

## Task 3: 定义 HistoryDataSource 协议

**Files:**
- Create: `backend/app/services/datasource_protocol.py`
- Test: `backend/tests/services/test_datasource_protocol.py` (create)

**Step 1: Write the failing test**

```python
# backend/tests/services/test_datasource_protocol.py
"""HistoryDataSource 协议合规性测试"""
from typing import Optional

import pandas as pd
import pytest

from app.services.datasource_protocol import HistoryDataSource


class _GoodSource:
    """符合协议的 mock 数据源"""
    name = "mock"

    def fetch_history(self, code: str, start_date: str, end_date: str, adjust: str = "qfq") -> Optional[pd.DataFrame]:
        return pd.DataFrame({"date": ["2024-01-01"], "close": [1.0]})

    def is_available(self) -> bool:
        return True


class _BadSource:
    """缺少 name 属性，不符合协议"""
    def fetch_history(self, code, start_date, end_date, adjust="qfq"):
        return None


class TestHistoryDataSourceProtocol:
    def test_good_source_is_instance(self):
        assert isinstance(_GoodSource(), HistoryDataSource)

    def test_bad_source_is_not_instance(self):
        assert not isinstance(_BadSource(), HistoryDataSource)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/services/test_datasource_protocol.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.datasource_protocol'`

**Step 3: Write minimal implementation**

```python
# backend/app/services/datasource_protocol.py
"""历史数据源统一协议"""
from typing import Optional, runtime_checkable

from typing import Protocol

import pandas as pd


@runtime_checkable
class HistoryDataSource(Protocol):
    """
    历史数据源接口。

    所有历史数据源必须实现此协议。
    返回的 DataFrame 至少包含列: date, open, high, low, close, volume
    """

    name: str

    def fetch_history(
        self,
        code: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> Optional[pd.DataFrame]: ...

    def is_available(self) -> bool: ...
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/services/test_datasource_protocol.py -v`
Expected: 2 passed

**Step 5: Commit**

```bash
git add backend/app/services/datasource_protocol.py backend/tests/services/test_datasource_protocol.py
git commit -m "feat: define HistoryDataSource protocol"
```

---

## Task 4: 实现 BaostockSource

**Files:**
- Create: `backend/app/services/baostock_service.py`
- Test: `backend/tests/services/test_baostock_service.py` (create)
- Modify: `backend/pyproject.toml:7-24` (添加 baostock 依赖)

**Step 1: 添加依赖**

在 `backend/pyproject.toml` 的 `dependencies` 列表中添加 `"baostock>=0.8.8"`。

Run: `cd backend && pip install baostock`

**Step 2: Write the failing tests**

```python
# backend/tests/services/test_baostock_service.py
"""BaostockSource 单元测试（全部 mock，不依赖真实网络）"""
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.services.baostock_service import BaostockSource, _to_baostock_code
from app.services.datasource_protocol import HistoryDataSource


class TestToBaostockCode:
    """ETF 代码 → Baostock 格式转换"""

    def test_shanghai_5xx(self):
        assert _to_baostock_code("510300") == "sh.510300"

    def test_shanghai_58x(self):
        assert _to_baostock_code("588000") == "sh.588000"

    def test_shenzhen_1xx(self):
        assert _to_baostock_code("159915") == "sz.159915"

    def test_shenzhen_0xx(self):
        assert _to_baostock_code("009999") == "sz.009999"

    def test_unknown_defaults_to_sh(self):
        assert _to_baostock_code("888888") == "sh.888888"


class TestBaostockSourceProtocol:
    def test_implements_protocol(self):
        source = BaostockSource()
        assert isinstance(source, HistoryDataSource)

    def test_name(self):
        assert BaostockSource().name == "baostock"


class TestBaostockSourceFetchHistory:
    @patch("app.services.baostock_service.bs")
    def test_success(self, mock_bs):
        """正常返回数据"""
        mock_login = MagicMock()
        mock_login.error_code = "0"
        mock_bs.login.return_value = mock_login

        mock_rs = MagicMock()
        mock_rs.error_code = "0"
        mock_rs.fields = ["date", "open", "high", "low", "close", "volume", "amount", "pctChg"]
        mock_rs.next.side_effect = [True, True, False]
        mock_rs.get_row_data.side_effect = [
            ["2024-01-02", "1.00", "1.05", "0.98", "1.03", "10000", "10300", "3.00"],
            ["2024-01-03", "1.03", "1.10", "1.01", "1.08", "12000", "12960", "4.85"],
        ]
        mock_bs.query_history_k_data_plus.return_value = mock_rs

        source = BaostockSource()
        df = source.fetch_history("510300", "2024-01-02", "2024-01-03")

        assert df is not None
        assert len(df) == 2
        assert list(df.columns) == ["date", "open", "high", "low", "close", "volume", "amount", "pctChg"]
        assert df["close"].dtype == float

    @patch("app.services.baostock_service.bs")
    def test_login_failure(self, mock_bs):
        """登录失败返回 None"""
        mock_login = MagicMock()
        mock_login.error_code = "1"
        mock_login.error_msg = "login failed"
        mock_bs.login.return_value = mock_login

        source = BaostockSource()
        assert source.fetch_history("510300", "2024-01-01", "2024-12-31") is None

    @patch("app.services.baostock_service.bs")
    def test_empty_result(self, mock_bs):
        """查询返回空数据"""
        mock_login = MagicMock()
        mock_login.error_code = "0"
        mock_bs.login.return_value = mock_login

        mock_rs = MagicMock()
        mock_rs.error_code = "0"
        mock_rs.next.return_value = False
        mock_bs.query_history_k_data_plus.return_value = mock_rs

        source = BaostockSource()
        assert source.fetch_history("510300", "2024-01-01", "2024-12-31") is None

    @patch("app.services.baostock_service.bs")
    def test_adjust_qfq(self, mock_bs):
        """前复权参数正确传递"""
        mock_login = MagicMock()
        mock_login.error_code = "0"
        mock_bs.login.return_value = mock_login

        mock_rs = MagicMock()
        mock_rs.error_code = "0"
        mock_rs.next.return_value = False
        mock_bs.query_history_k_data_plus.return_value = mock_rs

        source = BaostockSource()
        source.fetch_history("510300", "2024-01-01", "2024-12-31", adjust="qfq")

        call_kwargs = mock_bs.query_history_k_data_plus.call_args
        assert call_kwargs[1]["adjustflag"] == "2"  # qfq → adjustflag="2"
```

**Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/services/test_baostock_service.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 4: Write implementation**

```python
# backend/app/services/baostock_service.py
"""
Baostock 历史数据源

单例连接管理，线程安全，自动重连。
官方数据源，稳定性高于 AkShare 爬虫方式。
"""
import logging
import threading
from typing import Optional

import baostock as bs
import pandas as pd

logger = logging.getLogger(__name__)

# 复权参数映射：项目格式 → Baostock 格式
_ADJUST_MAP = {"qfq": "2", "hfq": "1", "": "3"}


def _to_baostock_code(code: str) -> str:
    """ETF 代码转 Baostock 格式 (sh.XXXXXX / sz.XXXXXX)"""
    prefix = code[0]
    if prefix in ("0", "1", "3"):
        return f"sz.{code}"
    return f"sh.{code}"


class _BaostockConnection:
    """Baostock 单例连接管理器"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._logged_in = False

    def ensure_login(self) -> bool:
        with self._lock:
            if self._logged_in:
                return True
            lg = bs.login()
            if lg.error_code != "0":
                logger.error("Baostock login failed: %s", lg.error_msg)
                return False
            self._logged_in = True
            logger.info("Baostock login succeeded")
            return True

    def reconnect(self) -> bool:
        with self._lock:
            try:
                bs.logout()
            except Exception:
                pass
            self._logged_in = False
            lg = bs.login()
            if lg.error_code != "0":
                logger.error("Baostock reconnect failed: %s", lg.error_msg)
                return False
            self._logged_in = True
            logger.info("Baostock reconnected")
            return True

    def logout(self) -> None:
        with self._lock:
            if self._logged_in:
                try:
                    bs.logout()
                except Exception:
                    pass
                self._logged_in = False


_connection = _BaostockConnection()


class BaostockSource:
    """Baostock 历史数据源，实现 HistoryDataSource 协议"""

    name: str = "baostock"

    def fetch_history(
        self,
        code: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> Optional[pd.DataFrame]:
        if not _connection.ensure_login():
            return None

        bs_code = _to_baostock_code(code)
        adjustflag = _ADJUST_MAP.get(adjust, "2")
        fields = "date,open,high,low,close,volume,amount,pctChg"

        rs = bs.query_history_k_data_plus(
            bs_code,
            fields,
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag=adjustflag,
        )

        # 查询失败 → 尝试重连一次
        if rs.error_code != "0":
            logger.warning("Baostock query failed (%s), reconnecting...", rs.error_msg)
            if not _connection.reconnect():
                return None
            rs = bs.query_history_k_data_plus(
                bs_code, fields,
                start_date=start_date, end_date=end_date,
                frequency="d", adjustflag=adjustflag,
            )
            if rs.error_code != "0":
                logger.error("Baostock query failed after reconnect: %s", rs.error_msg)
                return None

        rows = []
        while rs.next():
            rows.append(rs.get_row_data())

        if not rows:
            logger.warning("Baostock returned empty data: %s", code)
            return None

        df = pd.DataFrame(rows, columns=rs.fields)
        # 数值类型转换
        for col in ["open", "high", "low", "close", "volume", "amount", "pctChg"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    def is_available(self) -> bool:
        return _connection.ensure_login()
```

**Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/services/test_baostock_service.py -v`
Expected: ALL passed

**Step 6: Commit**

```bash
git add backend/pyproject.toml backend/app/services/baostock_service.py backend/tests/services/test_baostock_service.py
git commit -m "feat: implement BaostockSource with singleton connection"
```

---

## Task 5: 抽取 EastMoneyHistorySource

**Files:**
- Create: `backend/app/services/eastmoney_history_source.py`
- Test: `backend/tests/services/test_eastmoney_history_source.py` (create)

**Step 1: Write the failing tests**

```python
# backend/tests/services/test_eastmoney_history_source.py
"""EastMoneyHistorySource 单元测试"""
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from app.services.eastmoney_history_source import EastMoneyHistorySource
from app.services.datasource_protocol import HistoryDataSource


class TestEastMoneyHistorySourceProtocol:
    def test_implements_protocol(self):
        assert isinstance(EastMoneyHistorySource(), HistoryDataSource)

    def test_name(self):
        assert EastMoneyHistorySource().name == "eastmoney"


class TestEastMoneyHistorySourceFetch:
    @patch("app.services.eastmoney_history_source.ak")
    def test_success(self, mock_ak):
        """正常返回数据，列名已转换"""
        mock_ak.fund_etf_hist_em.return_value = pd.DataFrame({
            "日期": ["2024-01-02"],
            "开盘": [1.0],
            "收盘": [1.03],
            "最高": [1.05],
            "最低": [0.98],
            "成交量": [10000],
        })
        source = EastMoneyHistorySource()
        df = source.fetch_history("510300", "2024-01-01", "2024-12-31")
        assert df is not None
        assert "date" in df.columns
        assert "close" in df.columns

    @patch("app.services.eastmoney_history_source.ak")
    def test_empty_returns_none(self, mock_ak):
        mock_ak.fund_etf_hist_em.return_value = pd.DataFrame()
        source = EastMoneyHistorySource()
        assert source.fetch_history("510300", "2024-01-01", "2024-12-31") is None

    @patch("app.services.eastmoney_history_source.ak")
    def test_exception_returns_none(self, mock_ak):
        mock_ak.fund_etf_hist_em.side_effect = Exception("connection refused")
        source = EastMoneyHistorySource()
        assert source.fetch_history("510300", "2024-01-01", "2024-12-31") is None
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/services/test_eastmoney_history_source.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write implementation**

```python
# backend/app/services/eastmoney_history_source.py
"""
东方财富历史数据源

从 akshare_service.py 抽取，实现 HistoryDataSource 协议。
单次尝试，无重试（重试由 DataSourceManager 控制）。
"""
import logging
import time
from typing import Optional

import akshare as ak
import pandas as pd

from app.core.metrics import datasource_metrics

logger = logging.getLogger(__name__)


class EastMoneyHistorySource:
    """东方财富历史数据源，实现 HistoryDataSource 协议"""

    name: str = "eastmoney"

    def fetch_history(
        self,
        code: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> Optional[pd.DataFrame]:
        start = time.monotonic()
        try:
            df = ak.fund_etf_hist_em(
                symbol=code,
                period="daily",
                adjust=adjust,
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
            )
            if df.empty:
                latency = (time.monotonic() - start) * 1000
                datasource_metrics.record_failure(self.name, f"empty result for {code}", latency)
                return None

            df = df.rename(columns={
                "日期": "date", "开盘": "open", "收盘": "close",
                "最高": "high", "最低": "low", "成交量": "volume",
            })
            latency = (time.monotonic() - start) * 1000
            datasource_metrics.record_success(self.name, latency)
            return df
        except Exception as e:
            latency = (time.monotonic() - start) * 1000
            datasource_metrics.record_failure(self.name, str(e), latency)
            logger.warning("[eastmoney] fetch_history failed for %s: %s", code, e)
            return None

    def is_available(self) -> bool:
        return True  # AkShare 无持久连接，始终"可用"
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/services/test_eastmoney_history_source.py -v`
Expected: ALL passed

**Step 5: Commit**

```bash
git add backend/app/services/eastmoney_history_source.py backend/tests/services/test_eastmoney_history_source.py
git commit -m "feat: extract EastMoneyHistorySource from akshare_service"
```

---

## Task 6: 实现 DataSourceManager

**Files:**
- Create: `backend/app/services/datasource_manager.py`
- Test: `backend/tests/services/test_datasource_manager.py` (create)

**Step 1: Write the failing tests**

```python
# backend/tests/services/test_datasource_manager.py
"""DataSourceManager 单元测试"""
from typing import Optional
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from app.core.metrics import DataSourceMetrics
from app.services.datasource_manager import DataSourceManager


class _MockSource:
    """可控的 mock 数据源"""
    def __init__(self, name: str, data: Optional[pd.DataFrame] = None, fail: bool = False):
        self.name = name
        self._data = data
        self._fail = fail
        self.call_count = 0

    def fetch_history(self, code, start_date, end_date, adjust="qfq"):
        self.call_count += 1
        if self._fail:
            raise Exception(f"{self.name} failed")
        return self._data

    def is_available(self):
        return True


_SAMPLE_DF = pd.DataFrame({
    "date": ["2024-01-02", "2024-01-03"],
    "open": [1.0, 1.03],
    "high": [1.05, 1.10],
    "low": [0.98, 1.01],
    "close": [1.03, 1.08],
    "volume": [10000, 12000],
})


class TestDataSourceManagerFetchHistory:
    def test_first_source_success(self):
        """第一个源成功，不调用第二个"""
        src1 = _MockSource("src1", data=_SAMPLE_DF)
        src2 = _MockSource("src2", data=_SAMPLE_DF)
        mgr = DataSourceManager(sources=[src1, src2], metrics=DataSourceMetrics())

        df = mgr.fetch_history("510300", "2024-01-01", "2024-12-31")
        assert df is not None
        assert len(df) == 2
        assert src1.call_count == 1
        assert src2.call_count == 0

    def test_fallback_to_second(self):
        """第一个源失败，降级到第二个"""
        src1 = _MockSource("src1", fail=True)
        src2 = _MockSource("src2", data=_SAMPLE_DF)
        mgr = DataSourceManager(sources=[src1, src2], metrics=DataSourceMetrics())

        df = mgr.fetch_history("510300", "2024-01-01", "2024-12-31")
        assert df is not None
        assert src1.call_count == 1
        assert src2.call_count == 1

    def test_all_fail_returns_none(self):
        """所有源失败返回 None"""
        src1 = _MockSource("src1", fail=True)
        src2 = _MockSource("src2", fail=True)
        mgr = DataSourceManager(sources=[src1, src2], metrics=DataSourceMetrics())

        assert mgr.fetch_history("510300", "2024-01-01", "2024-12-31") is None

    def test_returns_none_skipped(self):
        """源返回 None（空数据）也降级"""
        src1 = _MockSource("src1", data=None)
        src2 = _MockSource("src2", data=_SAMPLE_DF)
        mgr = DataSourceManager(sources=[src1, src2], metrics=DataSourceMetrics())

        df = mgr.fetch_history("510300", "2024-01-01", "2024-12-31")
        assert df is not None
        assert src2.call_count == 1

    def test_empty_sources(self):
        """无数据源返回 None"""
        mgr = DataSourceManager(sources=[], metrics=DataSourceMetrics())
        assert mgr.fetch_history("510300", "2024-01-01", "2024-12-31") is None


class TestDataSourceManagerCircuitBreaker:
    def test_skips_circuit_broken_source(self):
        """被熔断的源直接跳过"""
        metrics = DataSourceMetrics()
        # 制造 src1 熔断：连续 10 次失败
        for _ in range(10):
            metrics.record_failure("src1", "err", 10.0)

        src1 = _MockSource("src1", data=_SAMPLE_DF)
        src2 = _MockSource("src2", data=_SAMPLE_DF)
        mgr = DataSourceManager(
            sources=[src1, src2], metrics=metrics,
            cb_threshold=0.1, cb_window=10, cb_cooldown=300,
        )

        df = mgr.fetch_history("510300", "2024-01-01", "2024-12-31")
        assert df is not None
        assert src1.call_count == 0  # 被跳过
        assert src2.call_count == 1
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/services/test_datasource_manager.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write implementation**

```python
# backend/app/services/datasource_manager.py
"""
数据源管理器

按配置优先级编排历史数据源，集成熔断逻辑。
所有在线源失败后返回 None，由调用方走缓存兜底。
"""
import logging
import time
from typing import List, Optional

import pandas as pd

from app.core.metrics import DataSourceMetrics, datasource_metrics

logger = logging.getLogger(__name__)


class DataSourceManager:
    """历史数据源编排器"""

    def __init__(
        self,
        sources: List,
        metrics: Optional[DataSourceMetrics] = None,
        cb_threshold: float = 0.1,
        cb_window: int = 10,
        cb_cooldown: int = 300,
    ) -> None:
        self._sources = sources
        self._metrics = metrics or datasource_metrics
        self._cb_threshold = cb_threshold
        self._cb_window = cb_window
        self._cb_cooldown = cb_cooldown

    def fetch_history(
        self,
        code: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> Optional[pd.DataFrame]:
        for source in self._sources:
            # 熔断检查
            if self._metrics.is_circuit_open(
                source.name,
                threshold=self._cb_threshold,
                window=self._cb_window,
                cooldown=self._cb_cooldown,
            ):
                logger.info("[%s] circuit open, skipping", source.name)
                continue

            start = time.monotonic()
            try:
                df = source.fetch_history(code, start_date, end_date, adjust)
                if df is not None and not df.empty:
                    latency = (time.monotonic() - start) * 1000
                    self._metrics.record_success(source.name, latency)
                    logger.info("[%s] fetch_history succeeded for %s (%.0fms)", source.name, code, latency)
                    return df
                # 返回 None 或空 → 视为失败
                latency = (time.monotonic() - start) * 1000
                self._metrics.record_failure(source.name, f"empty result for {code}", latency)
                logger.warning("[%s] returned empty for %s", source.name, code)
            except Exception as e:
                latency = (time.monotonic() - start) * 1000
                self._metrics.record_failure(source.name, str(e), latency)
                logger.warning("[%s] failed for %s: %s", source.name, code, e)

        logger.error("All history sources failed for %s", code)
        return None
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/services/test_datasource_manager.py -v`
Expected: ALL passed (6 tests)

**Step 5: Commit**

```bash
git add backend/app/services/datasource_manager.py backend/tests/services/test_datasource_manager.py
git commit -m "feat: implement DataSourceManager with circuit breaker"
```

---

## Task 7: 集成 — 修改 fetch_history_raw()

**Files:**
- Modify: `backend/app/services/akshare_service.py:268-296`

**Step 1: 确认现有测试通过**

Run: `cd backend && python -m pytest tests/ -v --tb=short`
Expected: ALL passed（确认基线）

**Step 2: 修改 fetch_history_raw()**

将 `akshare_service.py` 中的 `fetch_history_raw` 方法替换为委托给 DataSourceManager 的版本。

在文件顶部 import 区域添加：

```python
from app.services.datasource_manager import DataSourceManager
from app.core.config import settings
```

在 `AkShareService` 类之前（模块级），添加 manager 初始化：

```python
def _build_history_manager() -> DataSourceManager:
    """构建历史数据源管理器（延迟初始化，避免循环导入）"""
    sources = []
    for name in settings.HISTORY_DATA_SOURCES:
        if name == "baostock" and settings.BAOSTOCK_ENABLED:
            from app.services.baostock_service import BaostockSource
            sources.append(BaostockSource())
        elif name == "eastmoney":
            from app.services.eastmoney_history_source import EastMoneyHistorySource
            sources.append(EastMoneyHistorySource())
    return DataSourceManager(
        sources=sources,
        cb_threshold=settings.CIRCUIT_BREAKER_THRESHOLD,
        cb_window=settings.CIRCUIT_BREAKER_WINDOW,
        cb_cooldown=settings.CIRCUIT_BREAKER_COOLDOWN,
    )

_history_manager: Optional[DataSourceManager] = None

def _get_history_manager() -> DataSourceManager:
    global _history_manager
    if _history_manager is None:
        _history_manager = _build_history_manager()
    return _history_manager
```

替换 `fetch_history_raw` 方法体：

```python
    @staticmethod
    def fetch_history_raw(code: str, period: str, adjust: str) -> pd.DataFrame:
        """历史数据获取（DataSourceManager + DiskCache 兜底）"""
        cache_key = f"hist_{code}_{period}_{adjust}"
        fallback_key = f"hist_fallback_{code}_{period}_{adjust}"

        # 1. DiskCache 命中 → 直接返回
        cached_data = disk_cache.get(cache_key)
        if cached_data is not None:
            return cast(pd.DataFrame, cached_data)

        # 2. DataSourceManager 按优先级尝试各在线源
        manager = _get_history_manager()
        df = manager.fetch_history(code, "20000101", "20500101", adjust)
        if df is not None and not df.empty:
            disk_cache.set(cache_key, df, expire=604800)  # 7 天缓存
            disk_cache.set(fallback_key, df)  # 永不过期兜底
            return df

        # 3. 所有在线源失败 → 过期缓存兜底
        fallback_data = disk_cache.get(fallback_key)
        if fallback_data is not None:
            logger.warning("Using stale fallback cache for %s", code)
            return cast(pd.DataFrame, fallback_data)

        return pd.DataFrame()
```

同时删除 `_fetch_history_eastmoney` 静态方法（已迁移到 `EastMoneyHistorySource`），以及对应的 `@track_datasource("eastmoney_history")` 装饰器。

**Step 3: Run all tests**

Run: `cd backend && python -m pytest tests/ -v --tb=short`
Expected: ALL passed

注意：如果有测试直接 mock `AkShareService._fetch_history_eastmoney`，需要更新为 mock `_get_history_manager` 或 `DataSourceManager.fetch_history`。检查方法：

Run: `cd backend && grep -r "_fetch_history_eastmoney" tests/`

如果有匹配，更新对应测试的 mock 路径。

**Step 4: Commit**

```bash
git add backend/app/services/akshare_service.py
git commit -m "feat: delegate fetch_history_raw to DataSourceManager"
```

---

## Task 8: 文档更新

**Files:**
- Modify: `docs/design/2026-02-16-datasource-abstraction-design.md` (状态改为"已实施")
- Modify: `docs/planning/data-source-optimization-plan.md` (勾选 2.1 和 2.2)
- Modify: `AGENTS.md` (更新数据源说明，如有必要)

**Step 1: 更新设计文档状态**

`docs/design/2026-02-16-datasource-abstraction-design.md` 第 4 行：
```
**状态**: 待实施  →  **状态**: 已实施
```

**Step 2: 更新优化规划 checklist**

`docs/planning/data-source-optimization-plan.md` 第 42-55 行，将 2.1 和 2.2 的 `[ ]` 改为 `[x]`。

**Step 3: 检查 AGENTS.md 是否需要更新**

如果 AGENTS.md 第 2 节技术栈中未提及 baostock，添加一行：

| **数据源** | akshare, baostock | 东方财富 + Baostock 混合策略 |

**Step 4: Commit**

```bash
git add docs/ AGENTS.md
git commit -m "docs: update Phase 2 status and datasource documentation"
```

---

## 验证清单

完成所有 Task 后，执行以下验证：

1. **全量测试**: `cd backend && python -m pytest tests/ -v`
2. **类型检查**: `cd backend && python -c "from app.services.datasource_manager import DataSourceManager; print('OK')"`
3. **配置验证**: `cd backend && python -c "from app.core.config import settings; print(settings.HISTORY_DATA_SOURCES)"`
4. **熔断验证**: `cd backend && python -c "from app.core.metrics import DataSourceMetrics; m = DataSourceMetrics(); [m.record_failure('test', 'err', 10.0) for _ in range(10)]; print('circuit open:', m.is_circuit_open('test'))"`

---

**最后更新**: 2026-02-16
