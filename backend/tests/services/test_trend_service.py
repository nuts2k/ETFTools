"""
Tests for TrendService - 趋势分析服务测试

TDD Red Phase: These tests define the expected behavior of trend_service.
All tests should FAIL until trend_service is implemented.

Test coverage:
- MA calculation (MA5, MA20, MA60)
- Price position relative to MAs (above, below, crossing)
- MA alignment detection (bullish, bearish, mixed)
- Weekly resampling and consecutive week counting
"""

from __future__ import annotations

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Import the service that doesn't exist yet - this will cause ImportError
from app.services.trend_service import TrendService, trend_service


class TestCalculateMAValues:
    """Test MA (Moving Average) calculation correctness."""

    def test_calculate_ma_values_basic(self, sample_daily_data: pd.DataFrame):
        """MA5, MA20, MA60 should be calculated correctly from close prices."""
        service = TrendService()
        result = service.calculate_ma_values(sample_daily_data)

        # Should return dict with ma5, ma20, ma60
        assert "ma5" in result
        assert "ma20" in result
        assert "ma60" in result

        # Values should be floats
        assert isinstance(result["ma5"], float)
        assert isinstance(result["ma20"], float)
        assert isinstance(result["ma60"], float)

        # Manual verification: MA5 should be average of last 5 closes
        expected_ma5 = sample_daily_data["close"].tail(5).mean()
        assert abs(result["ma5"] - expected_ma5) < 0.0001

    def test_calculate_ma_values_with_insufficient_data(self):
        """Should handle data with fewer rows than MA period gracefully."""
        service = TrendService()
        # Only 10 days of data - not enough for MA60
        short_data = pd.DataFrame({
            "date": [(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(10, 0, -1)],
            "close": [1.0 + i * 0.01 for i in range(10)],
            "open": [1.0] * 10,
            "high": [1.1] * 10,
            "low": [0.9] * 10,
            "volume": [1000000] * 10,
        })

        result = service.calculate_ma_values(short_data)

        # MA5 should be calculated
        assert result["ma5"] is not None
        # MA60 should be None (insufficient data)
        assert result["ma60"] is None


class TestDeterminePosition:
    """Test price position relative to MA determination."""

    def test_determine_position_above(self):
        """Price clearly above MA should return 'above'."""
        service = TrendService()

        # Create data where current price is clearly above MA
        data = pd.DataFrame({
            "date": [(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(10, 0, -1)],
            "close": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.5],  # Last price jumps up
            "open": [1.0] * 10,
            "high": [1.1] * 10,
            "low": [0.9] * 10,
            "volume": [1000000] * 10,
        })

        position = service.determine_position(data, ma_period=5)
        assert position == "above"

    def test_determine_position_below(self):
        """Price clearly below MA should return 'below'."""
        service = TrendService()

        # Create data where current price is clearly below MA
        data = pd.DataFrame({
            "date": [(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(10, 0, -1)],
            "close": [1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.0],  # Last price drops
            "open": [1.5] * 10,
            "high": [1.6] * 10,
            "low": [1.4] * 10,
            "volume": [1000000] * 10,
        })

        position = service.determine_position(data, ma_period=5)
        assert position == "below"

    def test_determine_position_crossing_up(self):
        """
        Crossing up detection:
        - Yesterday: close < MA
        - Today: close >= MA
        """
        service = TrendService()

        # Create data where price crosses above MA
        # MA5 of [0.9, 0.9, 0.9, 0.9, 0.95] = 0.91
        # Yesterday close (0.9) < yesterday MA, today close (1.0) > today MA
        data = pd.DataFrame({
            "date": [(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, 0, -1)],
            "close": [0.85, 0.9, 0.9, 0.9, 0.9, 1.0],  # Crosses up on last day
            "open": [0.9] * 6,
            "high": [1.0] * 6,
            "low": [0.8] * 6,
            "volume": [1000000] * 6,
        })

        position = service.determine_position(data, ma_period=5)
        assert position == "crossing_up"

    def test_determine_position_crossing_down(self):
        """
        Crossing down detection:
        - Yesterday: close > MA
        - Today: close <= MA
        """
        service = TrendService()

        # Create data where price crosses below MA
        data = pd.DataFrame({
            "date": [(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, 0, -1)],
            "close": [1.1, 1.0, 1.0, 1.0, 1.0, 0.9],  # Crosses down on last day
            "open": [1.0] * 6,
            "high": [1.1] * 6,
            "low": [0.9] * 6,
            "volume": [1000000] * 6,
        })

        position = service.determine_position(data, ma_period=5)
        assert position == "crossing_down"


class TestMAAlignment:
    """Test MA alignment detection (bullish/bearish/mixed)."""

    def test_ma_alignment_bullish(self, bullish_trend_data: pd.DataFrame):
        """
        Bullish alignment: MA5 > MA20 > MA60
        多头排列
        """
        service = TrendService()
        alignment = service.get_ma_alignment(bullish_trend_data)

        assert alignment == "bullish"

    def test_ma_alignment_bearish(self, bearish_trend_data: pd.DataFrame):
        """
        Bearish alignment: MA5 < MA20 < MA60
        空头排列
        """
        service = TrendService()
        alignment = service.get_ma_alignment(bearish_trend_data)

        assert alignment == "bearish"

    def test_ma_alignment_mixed(self, sample_daily_data: pd.DataFrame):
        """
        Mixed alignment: Neither bullish nor bearish pattern
        震荡
        """
        service = TrendService()

        # Create data with mixed MA alignment (MA5 > MA20 but MA20 < MA60)
        mixed_data = pd.DataFrame({
            "date": [(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(70, 0, -1)],
            "close": (
                [2.0] * 30 +  # High prices early (affects MA60)
                [1.0] * 30 +  # Drop (affects MA20)
                [1.2] * 10    # Recent uptick (affects MA5)
            ),
            "open": [1.5] * 70,
            "high": [2.1] * 70,
            "low": [0.9] * 70,
            "volume": [1000000] * 70,
        })

        alignment = service.get_ma_alignment(mixed_data)
        assert alignment == "mixed"


class TestWeeklyResample:
    """Test weekly data resampling from daily data."""

    def test_weekly_resample_correctness(self, sample_daily_data: pd.DataFrame):
        """
        Weekly resample should:
        - Use Monday's open as weekly open
        - Use Friday's close as weekly close
        - Use max of week as high
        - Use min of week as low
        - Sum volume for the week
        """
        service = TrendService()
        weekly_df = service.resample_to_weekly(sample_daily_data)

        # Should have fewer rows than daily
        assert len(weekly_df) < len(sample_daily_data)

        # Should have OHLCV columns
        assert "open" in weekly_df.columns
        assert "high" in weekly_df.columns
        assert "low" in weekly_df.columns
        assert "close" in weekly_df.columns
        assert "volume" in weekly_df.columns

        # Weekly high should be >= weekly close and open
        for _, row in weekly_df.iterrows():
            assert row["high"] >= row["close"]
            assert row["high"] >= row["open"]
            assert row["low"] <= row["close"]
            assert row["low"] <= row["open"]

    def test_weekly_resample_handles_partial_week(self):
        """Should handle weeks with fewer than 5 trading days."""
        service = TrendService()

        # Create data with partial week (only 3 days)
        partial_week_data = pd.DataFrame({
            "date": ["2024-01-15", "2024-01-16", "2024-01-17"],  # Mon, Tue, Wed
            "open": [1.0, 1.01, 1.02],
            "high": [1.05, 1.06, 1.07],
            "low": [0.95, 0.96, 0.97],
            "close": [1.01, 1.02, 1.03],
            "volume": [1000000, 1100000, 1200000],
        })

        weekly_df = service.resample_to_weekly(partial_week_data)

        # Should produce 1 week of data
        assert len(weekly_df) == 1
        # Open should be Monday's open
        assert weekly_df.iloc[0]["open"] == 1.0
        # Close should be Wednesday's close (last day of partial week)
        assert weekly_df.iloc[0]["close"] == 1.03


class TestConsecutiveWeeks:
    """Test consecutive up/down week counting."""

    def test_consecutive_weeks_up(self):
        """Count consecutive weeks with positive returns."""
        service = TrendService()

        # Create 4 weeks of data, all up
        weekly_data = pd.DataFrame({
            "date": ["2024-01-05", "2024-01-12", "2024-01-19", "2024-01-26"],
            "open": [1.0, 1.05, 1.10, 1.15],
            "high": [1.06, 1.11, 1.16, 1.21],
            "low": [0.99, 1.04, 1.09, 1.14],
            "close": [1.05, 1.10, 1.15, 1.20],  # Each week closes higher than open
            "volume": [5000000] * 4,
        })

        result = service.count_consecutive_weeks(weekly_data)

        # Should return positive number for consecutive up weeks
        assert result["consecutive_weeks"] == 4
        assert result["direction"] == "up"

    def test_consecutive_weeks_down(self):
        """Count consecutive weeks with negative returns."""
        service = TrendService()

        # Create 3 weeks of data, all down
        weekly_data = pd.DataFrame({
            "date": ["2024-01-05", "2024-01-12", "2024-01-19"],
            "open": [1.20, 1.15, 1.10],
            "high": [1.21, 1.16, 1.11],
            "low": [1.14, 1.09, 1.04],
            "close": [1.15, 1.10, 1.05],  # Each week closes lower than open
            "volume": [5000000] * 3,
        })

        result = service.count_consecutive_weeks(weekly_data)

        # Should return negative number for consecutive down weeks
        assert result["consecutive_weeks"] == -3
        assert result["direction"] == "down"

    def test_consecutive_weeks_mixed(self):
        """Mixed weeks should only count the most recent streak."""
        service = TrendService()

        # Create data: up, up, down, up, up (most recent streak is 2 up)
        weekly_data = pd.DataFrame({
            "date": ["2024-01-05", "2024-01-12", "2024-01-19", "2024-01-26", "2024-02-02"],
            "open": [1.0, 1.05, 1.10, 1.08, 1.10],
            "high": [1.06, 1.11, 1.11, 1.11, 1.16],
            "low": [0.99, 1.04, 1.07, 1.07, 1.09],
            "close": [1.05, 1.10, 1.08, 1.10, 1.15],  # up, up, down, up, up
            "volume": [5000000] * 5,
        })

        result = service.count_consecutive_weeks(weekly_data)

        # Most recent streak is 2 up weeks
        assert result["consecutive_weeks"] == 2
        assert result["direction"] == "up"

    def test_consecutive_weeks_flat(self):
        """Flat week (open == close) should break the streak."""
        service = TrendService()

        # Create data: up, flat, up
        weekly_data = pd.DataFrame({
            "date": ["2024-01-05", "2024-01-12", "2024-01-19"],
            "open": [1.0, 1.05, 1.05],
            "high": [1.06, 1.06, 1.11],
            "low": [0.99, 1.04, 1.04],
            "close": [1.05, 1.05, 1.10],  # up, flat, up
            "volume": [5000000] * 3,
        })

        result = service.count_consecutive_weeks(weekly_data)

        # Most recent streak is 1 up week (flat breaks the streak)
        assert result["consecutive_weeks"] == 1
        assert result["direction"] == "up"


class TestGetDailyTrend:
    """Integration test for daily trend analysis."""

    def test_get_daily_trend_returns_complete_structure(self, sample_daily_data: pd.DataFrame):
        """Daily trend should return all expected fields."""
        service = TrendService()
        result = service.get_daily_trend(sample_daily_data)

        # Check all required fields exist
        assert "ma5_position" in result
        assert "ma20_position" in result
        assert "ma60_position" in result
        assert "ma_alignment" in result
        assert "ma_values" in result

        # ma_values should contain all MAs
        assert "ma5" in result["ma_values"]
        assert "ma20" in result["ma_values"]
        assert "ma60" in result["ma_values"]

        # Positions should be valid values
        valid_positions = {"above", "below", "crossing_up", "crossing_down"}
        assert result["ma5_position"] in valid_positions
        assert result["ma20_position"] in valid_positions
        # ma60_position could be None if insufficient data
        assert result["ma60_position"] in valid_positions or result["ma60_position"] is None

        # Alignment should be valid
        valid_alignments = {"bullish", "bearish", "mixed"}
        assert result["ma_alignment"] in valid_alignments


class TestGetWeeklyTrend:
    """Integration test for weekly trend analysis."""

    def test_get_weekly_trend_returns_complete_structure(self, sample_daily_data: pd.DataFrame):
        """Weekly trend should return all expected fields."""
        service = TrendService()
        result = service.get_weekly_trend(sample_daily_data)

        # Check all required fields exist
        assert "consecutive_weeks" in result
        assert "direction" in result
        assert "ma_status" in result

        # consecutive_weeks should be an integer
        assert isinstance(result["consecutive_weeks"], int)

        # direction should be valid
        valid_directions = {"up", "down", "flat"}
        assert result["direction"] in valid_directions

        # ma_status should be valid
        valid_statuses = {"bullish", "bearish", "mixed"}
        assert result["ma_status"] in valid_statuses


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_dataframe(self, empty_dataframe: pd.DataFrame):
        """Should handle empty DataFrame gracefully."""
        service = TrendService()

        # Should not raise exception
        result = service.get_daily_trend(empty_dataframe)

        # Should return None or empty result
        assert result is None or result.get("ma_values") is None

    def test_single_day_data(self, single_day_data: pd.DataFrame):
        """Should handle single day of data gracefully."""
        service = TrendService()

        result = service.get_daily_trend(single_day_data)

        # Should return None or indicate insufficient data
        assert result is None or result.get("ma5_position") is None

    def test_data_with_nan_values(self):
        """Should handle data with NaN values."""
        service = TrendService()

        data_with_nan = pd.DataFrame({
            "date": [(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(10, 0, -1)],
            "close": [1.0, np.nan, 1.02, 1.03, np.nan, 1.05, 1.06, 1.07, 1.08, 1.09],
            "open": [1.0] * 10,
            "high": [1.1] * 10,
            "low": [0.9] * 10,
            "volume": [1000000] * 10,
        })

        # Should not raise exception
        result = service.get_daily_trend(data_with_nan)

        # Result should be valid (implementation decides how to handle NaN)
        assert result is not None or result is None  # Either is acceptable
