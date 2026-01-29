"""
Tests for TrendCacheService.

Tests cover:
- Cache miss/hit behavior
- Intraday detection (no cache write during trading hours)
- Force refresh functionality
- Daily and weekly trend caching
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd


class TestIsIntraday:
    """Tests for intraday detection logic."""

    def test_is_intraday_same_date_returns_true(self):
        """When realtime date equals history last date, it's intraday."""
        from app.services.trend_cache_service import TrendCacheService
        
        service = TrendCacheService()
        result = service._is_intraday("2026-01-29", "2026-01-29")
        assert result is True

    def test_is_intraday_different_date_returns_false(self):
        """When realtime date is after history last date, it's not intraday."""
        from app.services.trend_cache_service import TrendCacheService
        
        service = TrendCacheService()
        result = service._is_intraday("2026-01-29", "2026-01-28")
        assert result is False


class TestDailyTrendCache:
    """Tests for daily trend caching."""

    @patch("app.services.trend_cache_service.disk_cache")
    def test_get_daily_trend_cache_miss_writes_cache(
        self, mock_cache, sample_daily_data
    ):
        """When cache misses, compute result and write to cache."""
        from app.services.trend_cache_service import TrendCacheService
        
        mock_cache.get.return_value = None
        
        service = TrendCacheService()
        result = service.get_daily_trend("510300", sample_daily_data)
        
        # Should have called cache.get
        mock_cache.get.assert_called_once()
        
        # Should have called cache.set (cache miss -> write)
        mock_cache.set.assert_called_once()
        
        # Result should contain expected keys
        assert result is not None
        assert "ma_alignment" in result

    @patch("app.services.trend_cache_service.disk_cache")
    def test_get_daily_trend_cache_hit_returns_cached(
        self, mock_cache, sample_daily_data
    ):
        """When cache hits with same date, return cached result directly."""
        from app.services.trend_cache_service import TrendCacheService
        
        # Get the last date from sample data
        last_date = sample_daily_data["date"].iloc[-1]
        
        cached_data = {
            "last_date": last_date,
            "result": {
                "ma_alignment": "bullish",
                "ma5_position": "above",
                "ma20_position": "above",
                "ma60_position": "above",
                "ma_values": {"ma5": 1.0, "ma20": 0.98, "ma60": 0.95},
                "latest_signal": None,
            },
        }
        mock_cache.get.return_value = cached_data
        
        service = TrendCacheService()
        result = service.get_daily_trend("510300", sample_daily_data)
        
        # Should have called cache.get
        mock_cache.get.assert_called_once()
        
        # Should NOT have called cache.set (cache hit)
        mock_cache.set.assert_not_called()
        
        # Result should be the cached result
        assert result == cached_data["result"]

    @patch("app.services.trend_cache_service.disk_cache")
    def test_get_daily_trend_intraday_no_cache_write(
        self, mock_cache, sample_daily_data
    ):
        """When in intraday mode, compute but don't write to cache."""
        from app.services.trend_cache_service import TrendCacheService
        
        # Simulate cache with yesterday's data
        last_date = sample_daily_data["date"].iloc[-1]
        cached_data = {
            "last_date": last_date,  # Same as data's last date = intraday
            "yesterday_close": 1.0,
            "yesterday_ma": {"ma5": 1.0, "ma20": 0.98, "ma60": 0.95},
            "result": {
                "ma_alignment": "bullish",
                "ma5_position": "above",
                "ma20_position": "above",
                "ma60_position": "above",
                "ma_values": {"ma5": 1.0, "ma20": 0.98, "ma60": 0.95},
                "latest_signal": None,
            },
        }
        mock_cache.get.return_value = cached_data
        
        service = TrendCacheService()
        # Pass realtime_price to trigger intraday calculation
        result = service.get_daily_trend(
            "510300", sample_daily_data, realtime_price=1.05
        )
        
        # Should NOT write to cache during intraday
        mock_cache.set.assert_not_called()
        
        # Should still return a result
        assert result is not None

    @patch("app.services.trend_cache_service.disk_cache")
    def test_get_daily_trend_force_refresh_bypasses_cache(
        self, mock_cache, sample_daily_data
    ):
        """When force_refresh=True, skip cache read and recompute."""
        from app.services.trend_cache_service import TrendCacheService
        
        cached_data = {
            "last_date": "2026-01-28",
            "result": {"ma_alignment": "bearish"},  # Old cached value
        }
        mock_cache.get.return_value = cached_data
        
        service = TrendCacheService()
        result = service.get_daily_trend(
            "510300", sample_daily_data, force_refresh=True
        )
        
        # Should NOT read from cache when force_refresh=True
        mock_cache.get.assert_not_called()
        
        # Should write new result to cache
        mock_cache.set.assert_called_once()
        
        # Result should be freshly computed (not the old cached value)
        assert result is not None
        assert result.get("ma_alignment") != "bearish" or "ma_values" in result


class TestWeeklyTrendCache:
    """Tests for weekly trend caching."""

    @patch("app.services.trend_cache_service.disk_cache")
    def test_get_weekly_trend_cache_miss_writes_cache(
        self, mock_cache, sample_daily_data
    ):
        """When cache misses, compute weekly trend and write to cache."""
        from app.services.trend_cache_service import TrendCacheService
        
        mock_cache.get.return_value = None
        
        service = TrendCacheService()
        result = service.get_weekly_trend("510300", sample_daily_data)
        
        # Should have called cache.get
        mock_cache.get.assert_called_once()
        
        # Should have called cache.set
        mock_cache.set.assert_called_once()
        
        # Result should contain expected keys
        assert result is not None
        assert "consecutive_weeks" in result
        assert "direction" in result

    @patch("app.services.trend_cache_service.disk_cache")
    def test_get_weekly_trend_cache_hit_returns_cached(
        self, mock_cache, sample_daily_data
    ):
        """When cache hits with same week, return cached result."""
        from app.services.trend_cache_service import TrendCacheService
        
        # Get the last date from sample data to determine current week
        last_date = sample_daily_data["date"].iloc[-1]
        
        cached_data = {
            "last_date": last_date,
            "result": {
                "consecutive_weeks": 3,
                "direction": "up",
                "ma_status": "bullish",
            },
        }
        mock_cache.get.return_value = cached_data
        
        service = TrendCacheService()
        result = service.get_weekly_trend("510300", sample_daily_data)
        
        # Should have called cache.get
        mock_cache.get.assert_called_once()
        
        # Should NOT have called cache.set (cache hit)
        mock_cache.set.assert_not_called()
        
        # Result should be the cached result
        assert result == cached_data["result"]
