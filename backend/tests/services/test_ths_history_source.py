"""ThsHistorySource 单元测试"""
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from app.services.ths_history_source import ThsHistorySource, _parse_ths_response
from app.services.datasource_protocol import HistoryDataSource

_SAMPLE_RESPONSE = (
    'quotebridge_v6_line_hs_510300_01_last36000({"num":2,"year":{"2024":2},'
    '"total":2,"data":"20240102,3.809,3.850,3.780,3.830,100000000,383000000.000,1.84,,,0;'
    '20240103,3.830,3.860,3.810,3.850,120000000,462000000.000,1.31,,,0","name":"\\u6caa\\u6df1300ETF"})'
)


class TestThsHistorySourceProtocol:
    def test_implements_protocol(self):
        assert isinstance(ThsHistorySource(), HistoryDataSource)

    def test_name(self):
        assert ThsHistorySource().name == "ths_history"


class TestParseThsResponse:
    def test_normal(self):
        df = _parse_ths_response(_SAMPLE_RESPONSE)
        assert df is not None
        assert len(df) == 2
        assert list(df.columns) == ["date", "open", "high", "low", "close", "volume", "amount"]
        assert df["close"].dtype == float
        assert df.iloc[0]["date"] == "2024-01-02"

    def test_empty_data(self):
        text = 'quotebridge_v6_line_hs_510300_01_last36000({"num":0,"total":0,"data":""})'
        assert _parse_ths_response(text) is None

    def test_invalid_response(self):
        assert _parse_ths_response("error page") is None


class TestThsHistorySourceFetch:
    @patch("app.services.ths_history_source.requests.get")
    def test_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = _SAMPLE_RESPONSE
        mock_get.return_value = mock_resp

        source = ThsHistorySource()
        df = source.fetch_history("510300", "2024-01-01", "2024-12-31")
        assert df is not None
        assert len(df) == 2

    @patch("app.services.ths_history_source.requests.get")
    def test_http_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.text = "Forbidden"
        mock_get.return_value = mock_resp

        source = ThsHistorySource()
        assert source.fetch_history("510300", "2024-01-01", "2024-12-31") is None

    @patch("app.services.ths_history_source.requests.get")
    def test_network_exception_propagates(self, mock_get):
        """网络异常向上抛出，由 DataSourceManager 统一处理"""
        mock_get.side_effect = Exception("connection refused")

        source = ThsHistorySource()
        with pytest.raises(Exception, match="connection refused"):
            source.fetch_history("510300", "2024-01-01", "2024-12-31")

    @patch("app.services.ths_history_source.requests.get")
    def test_date_filtering(self, mock_get):
        """只返回 start_date ~ end_date 范围内的数据"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = _SAMPLE_RESPONSE
        mock_get.return_value = mock_resp

        source = ThsHistorySource()
        df = source.fetch_history("510300", "2024-01-03", "2024-12-31")
        assert df is not None
        assert len(df) == 1
        assert df.iloc[0]["date"] == "2024-01-03"
