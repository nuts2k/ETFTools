"""
API integration tests for metrics caching.

Tests verify that the /metrics endpoint correctly uses cache services.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


class TestMetricsEndpointCache:
    """Tests for /metrics endpoint caching behavior."""

    @patch("app.services.trend_cache_service.disk_cache")
    @patch("app.services.temperature_cache_service.disk_cache")
    @patch("app.api.v1.endpoints.etf.ak_service")
    def test_metrics_endpoint_uses_cache(
        self,
        mock_ak_service,
        mock_temp_cache,
        mock_trend_cache,
        sample_daily_data,
    ):
        """Verify that /metrics endpoint uses cache services."""
        from app.main import app
        
        # Mock akshare service to return sample data
        mock_ak_service.get_etf_history.return_value = sample_daily_data.to_dict(
            orient="records"
        )
        
        # Mock cache to return None (cache miss)
        mock_trend_cache.get.return_value = None
        mock_temp_cache.get.return_value = None
        
        client = TestClient(app)
        response = client.get("/api/v1/etf/510300/metrics")
        
        # Should succeed
        assert response.status_code == 200
        
        # Response should contain trend and temperature data
        data = response.json()
        assert "daily_trend" in data
        assert "weekly_trend" in data
        assert "temperature" in data
        
        # Cache should have been written (cache miss -> write)
        assert mock_trend_cache.set.called
        assert mock_temp_cache.set.called

    @patch("app.services.trend_cache_service.disk_cache")
    @patch("app.services.temperature_cache_service.disk_cache")
    @patch("app.api.v1.endpoints.etf.ak_service")
    def test_metrics_endpoint_force_refresh(
        self,
        mock_ak_service,
        mock_temp_cache,
        mock_trend_cache,
        sample_daily_data,
    ):
        """Verify that force_refresh=true bypasses cache."""
        from app.main import app
        
        # Mock akshare service to return sample data
        mock_ak_service.get_etf_history.return_value = sample_daily_data.to_dict(
            orient="records"
        )
        
        # Mock cache with existing data
        last_date = sample_daily_data["date"].iloc[-1]
        mock_trend_cache.get.return_value = {
            "last_date": last_date,
            "result": {"ma_alignment": "cached_value"},
        }
        mock_temp_cache.get.return_value = {
            "last_date": last_date,
            "result": {"score": 50, "level": "cached"},
        }
        
        client = TestClient(app)
        
        # Request with force_refresh=true
        response = client.get("/api/v1/etf/510300/metrics?force_refresh=true")
        
        # Should succeed
        assert response.status_code == 200
        
        # Cache.get should NOT have been called (force_refresh bypasses read)
        # Note: The cache services skip cache.get when force_refresh=True
        mock_trend_cache.get.assert_not_called()
        mock_temp_cache.get.assert_not_called()
        
        # Cache should have been written with fresh data
        assert mock_trend_cache.set.called
        assert mock_temp_cache.set.called

    @patch("app.services.trend_cache_service.disk_cache")
    @patch("app.services.temperature_cache_service.disk_cache")
    @patch("app.api.v1.endpoints.etf.ak_service")
    def test_metrics_endpoint_cache_hit(
        self,
        mock_ak_service,
        mock_temp_cache,
        mock_trend_cache,
        sample_daily_data,
    ):
        """Verify that cache hit returns cached data without recomputation."""
        from app.main import app
        import pandas as pd
        
        # Mock akshare service to return sample data
        mock_ak_service.get_etf_history.return_value = sample_daily_data.to_dict(
            orient="records"
        )
        
        # Get the last date in the format that will be used after pd.to_datetime conversion
        # The etf.py code does: df["date"] = pd.to_datetime(df["date"]) then reset_index()
        # So the date becomes a datetime object, and str() will include time
        last_date_str = sample_daily_data["date"].iloc[-1]
        last_date_datetime = str(pd.to_datetime(last_date_str))
        
        cached_daily_trend = {
            "ma_alignment": "bullish",
            "ma5_position": "above",
            "ma20_position": "above",
            "ma60_position": "above",
            "ma_values": {"ma5": 1.0, "ma20": 0.98, "ma60": 0.95},
            "latest_signal": None,
        }
        cached_weekly_trend = {
            "consecutive_weeks": 3,
            "direction": "up",
            "ma_status": "bullish",
        }
        cached_temperature = {
            "score": 65,
            "level": "warm",
            "factors": {
                "drawdown_score": 80,
                "rsi_score": 55,
                "percentile_score": 60,
                "volatility_score": 50,
                "trend_score": 50,
            },
            "rsi_value": 55.0,
            "percentile_value": 0.6,
            "percentile_years": 0.5,
        }
        
        # Set up cache returns for trend cache service
        # Use the datetime string format that matches what the code produces
        def trend_cache_side_effect(key):
            if "daily_trend" in key:
                return {"last_date": last_date_datetime, "result": cached_daily_trend}
            elif "weekly_trend" in key:
                return {"last_date": last_date_datetime, "result": cached_weekly_trend}
            return None
        
        mock_trend_cache.get.side_effect = trend_cache_side_effect
        mock_temp_cache.get.return_value = {
            "last_date": last_date_datetime,
            "result": cached_temperature,
        }
        
        client = TestClient(app)
        response = client.get("/api/v1/etf/510300/metrics")
        
        # Should succeed
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify cache was checked (cache hit scenario)
        assert mock_trend_cache.get.called
        assert mock_temp_cache.get.called
        
        # Cache should NOT have been written (cache hit)
        mock_trend_cache.set.assert_not_called()
        mock_temp_cache.set.assert_not_called()
        
        # Response should contain the cached values
        assert data["daily_trend"] == cached_daily_trend
        assert data["weekly_trend"] == cached_weekly_trend
        assert data["temperature"] == cached_temperature
