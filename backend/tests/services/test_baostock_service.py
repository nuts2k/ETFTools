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
