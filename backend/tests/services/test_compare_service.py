import pytest
import numpy as np
import pandas as pd
from contextlib import ExitStack
from unittest.mock import patch, MagicMock
from app.services.compare_service import CompareService
from app.services.metrics_service import calculate_period_metrics


def _make_df(dates, closes):
    """构造简单的历史数据记录列表"""
    return [{"date": d, "open": c, "close": c, "high": c, "low": c, "volume": 1000}
            for d, c in zip(dates, closes)]


def _biz_dates(start, n):
    """生成 n 个工作日日期字符串"""
    return [d.strftime("%Y-%m-%d") for d in pd.bdate_range(start, periods=n)]


class _patch_compare:
    """compare_service 所需的三个 mock 的 context manager"""
    def __enter__(self):
        self._stack = ExitStack()
        self._stack.__enter__()
        mock_ak = self._stack.enter_context(patch("app.services.compare_service.ak_service"))
        mock_cache = self._stack.enter_context(patch("app.services.compare_service.etf_cache"))
        mock_temp = self._stack.enter_context(patch("app.services.compare_service.temperature_cache_service"))
        return mock_ak, mock_cache, mock_temp

    def __exit__(self, *exc):
        return self._stack.__exit__(*exc)


class TestCalculatePeriodMetrics:

    def test_basic_metrics(self):
        """基本指标计算正确"""
        dates = pd.bdate_range("2024-01-02", periods=252)
        # 模拟一年内从 100 涨到 110
        prices = [100 + 10 * i / 251 for i in range(252)]
        closes = pd.Series(prices, index=dates)
        result = calculate_period_metrics(closes)

        assert result["total_return"] > 0
        assert result["cagr"] > 0
        assert result["max_drawdown"] <= 0
        assert result["volatility"] >= 0
        assert result["risk_level"] in ("Low", "Medium", "High")
        assert result["mdd_trough"] is not None
        assert result["mdd_start"] is not None

    def test_single_point_returns_zeros(self):
        """单个数据点返回零值"""
        closes = pd.Series([100.0], index=pd.DatetimeIndex(["2024-01-02"]))
        result = calculate_period_metrics(closes)
        assert result["cagr"] == 0.0
        assert result["max_drawdown"] == 0.0
        assert result["volatility"] == 0.0

    def test_drawdown_recovery(self):
        """回撤恢复日期正确"""
        dates = pd.bdate_range("2024-01-02", periods=60)
        # 先涨到 120，跌到 90，再涨回 125
        prices = ([100 + i for i in range(20)] +          # 100→119
                  [120 - i * 1.5 for i in range(20)] +    # 120→91
                  [90 + i * 1.75 for i in range(20)])      # 90→123.25
        closes = pd.Series(prices, index=dates)
        result = calculate_period_metrics(closes)

        assert result["max_drawdown"] < 0
        assert result["mdd_end"] is not None  # 已恢复


class TestCompareService:

    def test_normalize_two_etfs(self):
        """归一化：起始值为 100，后续按比例"""
        dates = _biz_dates("2024-01-02", 35)
        closes_a = [10.0 + i * 1.0 for i in range(35)]
        closes_b = [50.0 + (i % 2) * 5.0 for i in range(35)]
        data_a = _make_df(dates, closes_a)
        data_b = _make_df(dates, closes_b)

        with _patch_compare() as (mock_ak, mock_cache, mock_temp):
            mock_ak.get_etf_history.side_effect = [data_a, data_b]
            mock_cache.get_etf_info.side_effect = [
                {"name": "ETF_A"}, {"name": "ETF_B"}
            ]
            mock_temp.calculate_temperature.return_value = None
            result = CompareService().compute(["000001", "000002"], "all")

        # 第一个点一定是 100
        assert result["normalized"]["series"]["000001"][0] == 100.0
        assert result["normalized"]["series"]["000002"][0] == 100.0
        # 第二个点 = 11/10*100 = 110
        assert result["normalized"]["series"]["000001"][1] == 110.0
        assert result["normalized"]["dates"] == dates

    def test_etf_names_in_response(self):
        """响应包含 etf_names 映射"""
        dates = _biz_dates("2024-01-02", 35)
        data = _make_df(dates, [10.0 + i for i in range(35)])

        with _patch_compare() as (mock_ak, mock_cache, mock_temp):
            mock_ak.get_etf_history.return_value = data
            mock_cache.get_etf_info.side_effect = [
                {"name": "沪深300ETF"}, {"name": "中证500ETF"}
            ]
            mock_temp.calculate_temperature.return_value = None
            result = CompareService().compute(["510300", "510500"], "all")

        assert result["etf_names"] == {"510300": "沪深300ETF", "510500": "中证500ETF"}

    def test_date_alignment_inner_join(self):
        """日期对齐：不同上市日期取交集"""
        dates_all = _biz_dates("2024-01-02", 40)
        dates_a = dates_all[:35]       # 前 35 天
        dates_b = dates_all[5:]        # 后 35 天，交集 = 30 天
        data_a = _make_df(dates_a, [10 + i for i in range(35)])
        data_b = _make_df(dates_b, [50 + i for i in range(35)])

        with _patch_compare() as (mock_ak, mock_cache, mock_temp):
            mock_ak.get_etf_history.side_effect = [data_a, data_b]
            mock_cache.get_etf_info.return_value = {"name": "X"}
            mock_temp.calculate_temperature.return_value = None
            result = CompareService().compute(["A", "B"], "all")

        expected_dates = dates_all[5:35]
        assert result["normalized"]["dates"] == expected_dates

    def test_correlation_perfect(self):
        """完全正相关返回 1.0"""
        dates = _biz_dates("2024-01-02", 40)
        prices = [100 + i * 0.5 for i in range(40)]
        data = _make_df(dates, prices)

        with _patch_compare() as (mock_ak, mock_cache, mock_temp):
            mock_ak.get_etf_history.side_effect = [data, data]
            mock_cache.get_etf_info.return_value = {"name": "X"}
            mock_temp.calculate_temperature.return_value = None
            result = CompareService().compute(["A", "B"], "all")

        assert result["correlation"]["A_B"] == 1.0

    def test_correlation_three_etfs_three_pairs(self):
        """3 只 ETF 产生 3 对相关性"""
        dates = _biz_dates("2024-01-02", 40)
        data = _make_df(dates, [100 + i for i in range(40)])

        with _patch_compare() as (mock_ak, mock_cache, mock_temp):
            mock_ak.get_etf_history.return_value = data
            mock_cache.get_etf_info.return_value = {"name": "X"}
            mock_temp.calculate_temperature.return_value = None
            result = CompareService().compute(["A", "B", "C"], "all")

        assert len(result["correlation"]) == 3

    def test_downsample_over_500(self):
        """超过 500 点时降采样至 500 点，首尾保留"""
        dates = _biz_dates("2018-01-02", 600)
        prices = [100 + i * 0.01 for i in range(600)]
        data = _make_df(dates, prices)

        with _patch_compare() as (mock_ak, mock_cache, mock_temp):
            mock_ak.get_etf_history.return_value = data
            mock_cache.get_etf_info.return_value = {"name": "X"}
            mock_temp.calculate_temperature.return_value = None
            result = CompareService().compute(["A", "B"], "all")

        assert len(result["normalized"]["dates"]) == 500
        assert result["normalized"]["dates"][0] == dates[0]
        assert result["normalized"]["dates"][-1] == dates[-1]

    def test_downsample_under_500_no_change(self):
        """不足 500 点时不采样"""
        dates = _biz_dates("2024-01-02", 35)
        data = _make_df(dates, [100 + i for i in range(35)])

        with _patch_compare() as (mock_ak, mock_cache, mock_temp):
            mock_ak.get_etf_history.return_value = data
            mock_cache.get_etf_info.return_value = {"name": "X"}
            mock_temp.calculate_temperature.return_value = None
            result = CompareService().compute(["A", "B"], "all")

        assert len(result["normalized"]["dates"]) == 35

    def test_overlap_less_than_30_days_raises(self):
        """重叠交易日 < 30 天抛出 ValueError"""
        dates_a = _biz_dates("2024-01-02", 20)
        dates_b = _biz_dates("2024-01-15", 20)
        data_a = _make_df(dates_a, [100] * 20)
        data_b = _make_df(dates_b, [100] * 20)

        with _patch_compare() as (mock_ak, mock_cache, mock_temp):
            mock_ak.get_etf_history.side_effect = [data_a, data_b]
            mock_cache.get_etf_info.return_value = {"name": "X"}
            mock_temp.calculate_temperature.return_value = None
            with pytest.raises(ValueError, match="不足 30"):
                CompareService().compute(["A", "B"], "all")

    def test_overlap_30_to_120_days_warning(self):
        """重叠交易日 30-120 天返回 warning"""
        dates = _biz_dates("2024-01-02", 50)
        data = _make_df(dates, [100 + i * 0.1 for i in range(50)])

        with _patch_compare() as (mock_ak, mock_cache, mock_temp):
            mock_ak.get_etf_history.return_value = data
            mock_cache.get_etf_info.return_value = {"name": "X"}
            mock_temp.calculate_temperature.return_value = None
            result = CompareService().compute(["A", "B"], "all")

        assert len(result["warnings"]) > 0

    def test_no_data_raises(self):
        """ETF 无历史数据抛出 ValueError"""
        with _patch_compare() as (mock_ak, mock_cache, mock_temp):
            mock_ak.get_etf_history.return_value = []
            mock_cache.get_etf_info.return_value = {"name": "X"}
            mock_temp.calculate_temperature.return_value = None
            with pytest.raises(ValueError, match="无历史数据"):
                CompareService().compute(["A", "B"], "all")

    def test_period_filter_1y(self):
        """period=1y 只保留最近 1 年数据"""
        from datetime import datetime, timedelta
        base = datetime.now()
        dates = [(base - timedelta(days=1100-i)).strftime("%Y-%m-%d")
                 for i in range(1100) if (base - timedelta(days=1100-i)).weekday() < 5]
        prices = [100 + i * 0.01 for i in range(len(dates))]
        data = _make_df(dates, prices)

        with _patch_compare() as (mock_ak, mock_cache, mock_temp):
            mock_ak.get_etf_history.return_value = data
            mock_cache.get_etf_info.return_value = {"name": "X"}
            mock_temp.calculate_temperature.return_value = None
            result = CompareService().compute(["A", "B"], "1y")

        assert 200 < len(result["normalized"]["dates"]) < 280

    def test_metrics_in_response(self):
        """响应包含基于对齐数据计算的 metrics"""
        dates = _biz_dates("2024-01-02", 35)
        closes_a = [10.0 + i * 0.5 for i in range(35)]
        closes_b = [50.0 + i * 0.3 for i in range(35)]
        data_a = _make_df(dates, closes_a)
        data_b = _make_df(dates, closes_b)

        with _patch_compare() as (mock_ak, mock_cache, mock_temp):
            mock_ak.get_etf_history.side_effect = [data_a, data_b]
            mock_cache.get_etf_info.side_effect = [{"name": "A"}, {"name": "B"}]
            mock_temp.calculate_temperature.return_value = {"score": 55}
            result = CompareService().compute(["000001", "000002"], "all")

        assert "metrics" in result
        assert "000001" in result["metrics"]
        assert "000002" in result["metrics"]
        for code in ["000001", "000002"]:
            m = result["metrics"][code]
            assert "cagr" in m
            assert "max_drawdown" in m
            assert "volatility" in m
            assert "total_return" in m
            assert "actual_years" in m

    def test_temperatures_in_response(self):
        """响应包含 temperatures 字段"""
        dates = _biz_dates("2024-01-02", 35)
        data = _make_df(dates, [100 + i for i in range(35)])
        mock_temp_data = {"score": 42, "level": "cool"}

        with _patch_compare() as (mock_ak, mock_cache, mock_temp):
            mock_ak.get_etf_history.return_value = data
            mock_cache.get_etf_info.return_value = {"name": "X"}
            mock_temp.calculate_temperature.return_value = mock_temp_data
            result = CompareService().compute(["A", "B"], "all")

        assert "temperatures" in result
        assert result["temperatures"]["A"] == mock_temp_data
        assert result["temperatures"]["B"] == mock_temp_data

    def test_temperature_failure_returns_none(self):
        """temperature 计算失败时返回 None，不影响整体"""
        dates = _biz_dates("2024-01-02", 35)
        data = _make_df(dates, [100 + i for i in range(35)])

        with _patch_compare() as (mock_ak, mock_cache, mock_temp):
            mock_ak.get_etf_history.return_value = data
            mock_cache.get_etf_info.return_value = {"name": "X"}
            mock_temp.calculate_temperature.side_effect = Exception("计算失败")
            result = CompareService().compute(["A", "B"], "all")

        assert result["temperatures"]["A"] is None
        assert result["temperatures"]["B"] is None
