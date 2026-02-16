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
