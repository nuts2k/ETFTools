"""
告警调度器服务测试
"""

import pandas as pd
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.alert_scheduler import AlertScheduler


@pytest.mark.anyio
async def test_fetch_and_compute_etf_metrics_success():
    """测试成功获取数据并计算指标"""
    # 准备测试数据
    test_df = pd.DataFrame({
        'date': pd.date_range(start='2023-01-01', periods=100),
        'close': [3.0 + i * 0.01 for i in range(100)],
        'high': [3.0 + i * 0.01 + 0.05 for i in range(100)],
        'low': [3.0 + i * 0.01 - 0.05 for i in range(100)],
        'open': [3.0 + i * 0.01 for i in range(100)],
        'volume': [1000000 for _ in range(100)],
    })

    # Mock 依赖服务
    with patch('app.services.alert_scheduler.ak_service') as mock_ak_service, \
         patch('app.services.alert_scheduler.temperature_service') as mock_temp_service, \
         patch('app.services.alert_scheduler.trend_service') as mock_trend_service:

        # 配置 mock 返回值
        mock_ak_service.fetch_history_raw.return_value = test_df
        mock_temp_service.calculate_temperature.return_value = 65.5
        mock_trend_service.get_daily_trend.return_value = "上涨"
        mock_trend_service.get_weekly_trend.return_value = "震荡"

        # 创建调度器实例并调用方法
        scheduler = AlertScheduler()
        result = await scheduler._fetch_and_compute_etf_metrics("510300")

        # 验证结果
        assert result is not None
        assert "temperature" in result
        assert "daily_trend" in result
        assert "weekly_trend" in result
        assert result["temperature"] == 65.5
        assert result["daily_trend"] == "上涨"
        assert result["weekly_trend"] == "震荡"

        # 验证调用参数
        mock_ak_service.fetch_history_raw.assert_called_once_with("510300", "daily", "qfq")
        mock_temp_service.calculate_temperature.assert_called_once()
        mock_trend_service.get_daily_trend.assert_called_once()
        mock_trend_service.get_weekly_trend.assert_called_once()


@pytest.mark.anyio
async def test_fetch_and_compute_etf_metrics_empty_dataframe():
    """测试空 DataFrame 的处理"""
    # 准备空 DataFrame
    empty_df = pd.DataFrame()

    # Mock 依赖服务
    with patch('app.services.alert_scheduler.ak_service') as mock_ak_service:
        # 配置 mock 返回空 DataFrame
        mock_ak_service.fetch_history_raw.return_value = empty_df

        # 创建调度器实例并调用方法
        scheduler = AlertScheduler()
        result = await scheduler._fetch_and_compute_etf_metrics("510300")

        # 验证返回 None
        assert result is None

        # 验证调用参数
        mock_ak_service.fetch_history_raw.assert_called_once_with("510300", "daily", "qfq")


@pytest.mark.anyio
async def test_fetch_and_compute_etf_metrics_none_dataframe():
    """测试 None DataFrame 的处理"""
    # Mock 依赖服务
    with patch('app.services.alert_scheduler.ak_service') as mock_ak_service:
        # 配置 mock 返回 None
        mock_ak_service.fetch_history_raw.return_value = None

        # 创建调度器实例并调用方法
        scheduler = AlertScheduler()
        result = await scheduler._fetch_and_compute_etf_metrics("510300")

        # 验证返回 None
        assert result is None

        # 验证调用参数
        mock_ak_service.fetch_history_raw.assert_called_once_with("510300", "daily", "qfq")


# ---- _fetch_summary_etf_data 测试 ----

def _make_etf_info(code, change_pct):
    return {"code": code, "name": f"ETF{code}", "price": 1.0, "change_pct": change_pct, "volume": 0}


def _make_metrics():
    return {"temperature": 50.0, "daily_trend": "上涨", "weekly_trend": "震荡"}


@pytest.mark.anyio
async def test_fetch_summary_etf_data_happy_path():
    """新鲜数据全部命中，不走缓存 fallback"""
    fresh_list = [_make_etf_info("510300", -0.5), _make_etf_info("159201", -1.2)]

    with patch('app.services.alert_scheduler.ak_service') as mock_ak, \
         patch.object(AlertScheduler, '_fetch_and_compute_etf_metrics', new_callable=AsyncMock) as mock_metrics:
        mock_ak.fetch_all_etfs.return_value = fresh_list
        mock_metrics.return_value = _make_metrics()

        scheduler = AlertScheduler()
        result = await scheduler._fetch_summary_etf_data(["510300", "159201"])

        assert len(result) == 2
        assert result["510300"]["info"]["change_pct"] == -0.5
        assert result["159201"]["info"]["change_pct"] == -1.2
        # 不应调用 get_etf_info（无需 fallback）
        mock_ak.get_etf_info.assert_not_called()


@pytest.mark.anyio
async def test_fetch_summary_etf_data_partial_miss_fallback():
    """部分 ETF 不在新鲜数据中，单独 fallback 到缓存"""
    fresh_list = [_make_etf_info("510300", -0.5)]
    cached_info = _make_etf_info("159201", -1.0)

    with patch('app.services.alert_scheduler.ak_service') as mock_ak, \
         patch.object(AlertScheduler, '_fetch_and_compute_etf_metrics', new_callable=AsyncMock) as mock_metrics:
        mock_ak.fetch_all_etfs.return_value = fresh_list
        mock_ak.get_etf_info.return_value = cached_info
        mock_metrics.return_value = _make_metrics()

        scheduler = AlertScheduler()
        result = await scheduler._fetch_summary_etf_data(["510300", "159201"])

        assert len(result) == 2
        assert result["510300"]["info"]["change_pct"] == -0.5
        assert result["159201"]["info"]["change_pct"] == -1.0
        # 只对缺失的 ETF 调用 get_etf_info
        mock_ak.get_etf_info.assert_called_once_with("159201")


@pytest.mark.anyio
async def test_fetch_summary_etf_data_total_failure_fallback():
    """数据源完全失败（返回空），所有 ETF fallback 到缓存"""
    cached_info = _make_etf_info("510300", -0.8)

    with patch('app.services.alert_scheduler.ak_service') as mock_ak, \
         patch.object(AlertScheduler, '_fetch_and_compute_etf_metrics', new_callable=AsyncMock) as mock_metrics:
        mock_ak.fetch_all_etfs.return_value = []
        mock_ak.get_etf_info.return_value = cached_info
        mock_metrics.return_value = _make_metrics()

        scheduler = AlertScheduler()
        result = await scheduler._fetch_summary_etf_data(["510300"])

        assert result["510300"]["info"]["change_pct"] == -0.8
        mock_ak.get_etf_info.assert_called_once_with("510300")


@pytest.mark.anyio
async def test_fetch_summary_etf_data_fetch_all_raises():
    """fetch_all_etfs 抛异常，降级到缓存"""
    cached_info = _make_etf_info("510300", -0.3)

    with patch('app.services.alert_scheduler.ak_service') as mock_ak, \
         patch.object(AlertScheduler, '_fetch_and_compute_etf_metrics', new_callable=AsyncMock) as mock_metrics:
        mock_ak.fetch_all_etfs.side_effect = RuntimeError("network error")
        mock_ak.get_etf_info.return_value = cached_info
        mock_metrics.return_value = _make_metrics()

        scheduler = AlertScheduler()
        result = await scheduler._fetch_summary_etf_data(["510300"])

        assert result["510300"]["info"]["change_pct"] == -0.3
        mock_ak.get_etf_info.assert_called_once_with("510300")


@pytest.mark.anyio
async def test_fetch_summary_etf_data_etf_unavailable_from_all():
    """ETF 从所有来源都获取失败，info 为 None"""
    with patch('app.services.alert_scheduler.ak_service') as mock_ak, \
         patch.object(AlertScheduler, '_fetch_and_compute_etf_metrics', new_callable=AsyncMock) as mock_metrics:
        mock_ak.fetch_all_etfs.return_value = []
        mock_ak.get_etf_info.return_value = None
        mock_metrics.return_value = _make_metrics()

        scheduler = AlertScheduler()
        result = await scheduler._fetch_summary_etf_data(["999999"])

        assert result["999999"]["info"] is None
        assert result["999999"]["metrics"] is not None


@pytest.mark.anyio
async def test_fetch_summary_etf_data_individual_exception():
    """单个 ETF 处理异常不影响其他 ETF"""
    fresh_list = [_make_etf_info("510300", -0.5)]

    with patch('app.services.alert_scheduler.ak_service') as mock_ak, \
         patch.object(AlertScheduler, '_fetch_and_compute_etf_metrics', new_callable=AsyncMock) as mock_metrics:
        mock_ak.fetch_all_etfs.return_value = fresh_list
        # 第一个 ETF 的 metrics 抛异常，第二个正常
        mock_metrics.side_effect = [RuntimeError("compute failed"), _make_metrics()]
        mock_ak.get_etf_info.return_value = _make_etf_info("159201", -1.0)

        scheduler = AlertScheduler()
        result = await scheduler._fetch_summary_etf_data(["510300", "159201"])

        # 510300 因异常被跳过，159201 正常
        assert "510300" not in result
        assert "159201" in result
