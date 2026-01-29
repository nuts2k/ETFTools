"""
Tests for TemperatureCacheService.

Tests cover:
- Cache miss/hit behavior
- Intraday detection (no cache write during trading hours)
- Force refresh functionality
- RSI state preservation in cache
- Historical peak updates
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd


class TestTemperatureCache:
    """Tests for temperature caching."""

    @patch("app.services.temperature_cache_service.disk_cache")
    def test_calculate_temperature_cache_miss_writes_cache(
        self, mock_cache, sample_daily_data
    ):
        """When cache misses, compute result and write to cache."""
        from app.services.temperature_cache_service import TemperatureCacheService
        
        mock_cache.get.return_value = None
        
        service = TemperatureCacheService()
        result = service.calculate_temperature("510300", sample_daily_data)
        
        # Should have called cache.get
        mock_cache.get.assert_called_once()
        
        # Should have called cache.set (cache miss -> write)
        mock_cache.set.assert_called_once()
        
        # Result should contain expected keys
        assert result is not None
        assert "score" in result
        assert "level" in result
        assert "factors" in result

    @patch("app.services.temperature_cache_service.disk_cache")
    def test_calculate_temperature_cache_hit_returns_cached(
        self, mock_cache, sample_daily_data
    ):
        """When cache hits with same date, return cached result directly."""
        from app.services.temperature_cache_service import TemperatureCacheService
        
        # Get the last date from sample data
        last_date = sample_daily_data["date"].iloc[-1]
        
        cached_data = {
            "last_date": last_date,
            "result": {
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
            },
        }
        mock_cache.get.return_value = cached_data
        
        service = TemperatureCacheService()
        result = service.calculate_temperature("510300", sample_daily_data)
        
        # Should have called cache.get
        mock_cache.get.assert_called_once()
        
        # Should NOT have called cache.set (cache hit)
        mock_cache.set.assert_not_called()
        
        # Result should be the cached result
        assert result == cached_data["result"]

    @patch("app.services.temperature_cache_service.disk_cache")
    def test_calculate_temperature_intraday_no_cache_write(
        self, mock_cache, sample_daily_data
    ):
        """When in intraday mode, compute but don't write to cache."""
        from app.services.temperature_cache_service import TemperatureCacheService
        
        # Simulate cache with same date (intraday scenario)
        last_date = sample_daily_data["date"].iloc[-1]
        cached_data = {
            "last_date": last_date,
            "result": {
                "score": 65,
                "level": "warm",
                "factors": {},
                "rsi_value": 55.0,
                "percentile_value": 0.6,
                "percentile_years": 0.5,
            },
        }
        mock_cache.get.return_value = cached_data
        
        service = TemperatureCacheService()
        # Pass realtime_price to trigger intraday calculation
        result = service.calculate_temperature(
            "510300", sample_daily_data, realtime_price=1.05
        )
        
        # Should NOT write to cache during intraday
        mock_cache.set.assert_not_called()
        
        # Should still return a result
        assert result is not None

    @patch("app.services.temperature_cache_service.disk_cache")
    def test_calculate_temperature_force_refresh_bypasses_cache(
        self, mock_cache, sample_daily_data
    ):
        """When force_refresh=True, skip cache read and recompute."""
        from app.services.temperature_cache_service import TemperatureCacheService
        
        cached_data = {
            "last_date": "2026-01-28",
            "result": {"score": 30, "level": "freezing"},  # Old cached value
        }
        mock_cache.get.return_value = cached_data
        
        service = TemperatureCacheService()
        result = service.calculate_temperature(
            "510300", sample_daily_data, force_refresh=True
        )
        
        # Should NOT read from cache when force_refresh=True
        mock_cache.get.assert_not_called()
        
        # Should write new result to cache
        mock_cache.set.assert_called_once()
        
        # Result should be freshly computed (contains all expected keys)
        assert result is not None
        assert "score" in result
        assert "level" in result
        assert "factors" in result

    @patch("app.services.temperature_cache_service.disk_cache")
    def test_rsi_state_preserved_in_cache(self, mock_cache, sample_daily_data):
        """RSI intermediate state should be preserved in cache."""
        from app.services.temperature_cache_service import TemperatureCacheService
        
        mock_cache.get.return_value = None
        
        service = TemperatureCacheService()
        result = service.calculate_temperature("510300", sample_daily_data)
        
        # Verify cache.set was called
        mock_cache.set.assert_called_once()
        
        # Get the cached data that was written
        call_args = mock_cache.set.call_args
        cache_key, cache_data = call_args[0]
        
        # Cache should contain RSI-related data
        assert "last_date" in cache_data
        assert "result" in cache_data
        # The result should have rsi_value
        assert "rsi_value" in cache_data["result"]

    @patch("app.services.temperature_cache_service.disk_cache")
    def test_historical_peak_updated_on_new_high(self, mock_cache, bullish_trend_data):
        """Historical peak should be updated when price makes new high."""
        from app.services.temperature_cache_service import TemperatureCacheService
        
        mock_cache.get.return_value = None
        
        service = TemperatureCacheService()
        result = service.calculate_temperature("510300", bullish_trend_data)
        
        # In bullish data, drawdown should be minimal (close to new high)
        # So drawdown_score should be high
        assert result is not None
        factors = result.get("factors", {})
        drawdown_score = factors.get("drawdown_score", 0)
        
        # In a bullish trend, we expect high drawdown score (close to peak)
        assert drawdown_score >= 50  # Should be reasonably high
