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
