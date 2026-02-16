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
    def test_exception_propagates(self, mock_ak):
        """异常向上抛出，由 DataSourceManager 统一处理"""
        mock_ak.fund_etf_hist_em.side_effect = Exception("connection refused")
        source = EastMoneyHistorySource()
        with pytest.raises(Exception, match="connection refused"):
            source.fetch_history("510300", "2024-01-01", "2024-12-31")
