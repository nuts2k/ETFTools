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
