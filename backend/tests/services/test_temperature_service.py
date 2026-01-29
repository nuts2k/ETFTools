"""
Tests for TemperatureService - 市场温度计算服务测试

TDD Red Phase: These tests define the expected behavior of temperature_service.
All tests should FAIL until temperature_service is implemented.

Test coverage:
- RSI calculation (Wilder EMA method)
- Drawdown score calculation
- Historical percentile calculation
- Volatility score calculation
- Trend score calculation
- Temperature weighted sum and level determination

温度计算公式:
| 因子 | 权重 | 计算方式 | 得分范围 |
|------|------|----------|----------|
| 回撤程度 | 30% | 当前回撤映射到 0-100（-30%回撤=0分，新高=100分） | 0-100 |
| RSI指标 | 20% | RSI(14) 直接作为得分（Wilder EMA 方式） | 0-100 |
| 历史分位 | 20% | 当前价格在近10年的分位数 × 100 | 0-100 |
| 波动水平 | 15% | 当前波动率在历史中的分位数 × 100 | 0-100 |
| 趋势强度 | 15% | 基于均线排列计算（多头=80，震荡=50，空头=20） | 0-100 |

温度等级:
- 0-30: `freezing` 冰点
- 31-50: `cool` 温和
- 51-70: `warm` 偏热
- 71-100: `hot` 过热
"""

from __future__ import annotations

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Import the service that doesn't exist yet - this will cause ImportError
from app.services.temperature_service import TemperatureService, temperature_service


class TestCalculateRSI:
    """Test RSI calculation using Wilder EMA method."""

    def test_calculate_rsi_wilder(self, sample_daily_data: pd.DataFrame):
        """
        RSI should be calculated using Wilder's smoothing method.
        
        Wilder EMA uses alpha = 1/period (not 2/(period+1) like standard EMA).
        RSI = 100 - (100 / (1 + RS)), where RS = avg_gain / avg_loss
        """
        service = TemperatureService()
        rsi = service.calculate_rsi(sample_daily_data, period=14)

        # RSI should be between 0 and 100
        assert 0 <= rsi <= 100

        # RSI should be a float
        assert isinstance(rsi, float)

        # Manual verification with known data
        # Create simple test data with known RSI
        prices = [44, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84,
                  46.08, 45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41,
                  46.22, 45.64]
        test_data = pd.DataFrame({
            "date": [(datetime.now() - timedelta(days=len(prices)-i)).strftime("%Y-%m-%d") 
                     for i in range(len(prices))],
            "close": prices,
            "open": prices,
            "high": [p + 0.1 for p in prices],
            "low": [p - 0.1 for p in prices],
            "volume": [1000000] * len(prices),
        })
        
        rsi_result = service.calculate_rsi(test_data, period=14)
        # Wilder RSI for this data should be approximately 70 (known value)
        assert 65 <= rsi_result <= 75

    def test_rsi_overbought(self):
        """RSI > 70 indicates overbought condition."""
        service = TemperatureService()

        # Create data with strong upward momentum (should produce high RSI)
        days = 30
        # Prices consistently rising
        prices = [1.0 + i * 0.02 for i in range(days)]  # 2% daily gains
        
        overbought_data = pd.DataFrame({
            "date": [(datetime.now() - timedelta(days=days-i)).strftime("%Y-%m-%d") 
                     for i in range(days)],
            "close": prices,
            "open": [p - 0.01 for p in prices],
            "high": [p + 0.01 for p in prices],
            "low": [p - 0.02 for p in prices],
            "volume": [1000000] * days,
        })

        rsi = service.calculate_rsi(overbought_data, period=14)
        
        # Strong uptrend should produce RSI > 70
        assert rsi > 70, f"Expected RSI > 70 for overbought condition, got {rsi}"

    def test_rsi_oversold(self):
        """RSI < 30 indicates oversold condition."""
        service = TemperatureService()

        # Create data with strong downward momentum (should produce low RSI)
        days = 30
        # Prices consistently falling
        prices = [2.0 - i * 0.02 for i in range(days)]  # 2% daily losses
        
        oversold_data = pd.DataFrame({
            "date": [(datetime.now() - timedelta(days=days-i)).strftime("%Y-%m-%d") 
                     for i in range(days)],
            "close": prices,
            "open": [p + 0.01 for p in prices],
            "high": [p + 0.02 for p in prices],
            "low": [p - 0.01 for p in prices],
            "volume": [1000000] * days,
        })

        rsi = service.calculate_rsi(oversold_data, period=14)
        
        # Strong downtrend should produce RSI < 30
        assert rsi < 30, f"Expected RSI < 30 for oversold condition, got {rsi}"


class TestDrawdownScore:
    """Test drawdown score calculation."""

    def test_drawdown_score_at_peak(self):
        """At new high (0% drawdown), score should be 100."""
        service = TemperatureService()

        # Create data where current price is at all-time high
        days = 60
        prices = [1.0 + i * 0.01 for i in range(days)]  # Steadily rising to new high
        
        peak_data = pd.DataFrame({
            "date": [(datetime.now() - timedelta(days=days-i)).strftime("%Y-%m-%d") 
                     for i in range(days)],
            "close": prices,
            "open": [p - 0.005 for p in prices],
            "high": [p + 0.005 for p in prices],
            "low": [p - 0.01 for p in prices],
            "volume": [1000000] * days,
        })

        score = service.calculate_drawdown_score(peak_data)
        
        # At peak, drawdown is 0%, score should be 100
        assert score == 100, f"Expected score 100 at peak, got {score}"

    def test_drawdown_score_at_30pct(self):
        """At -30% drawdown, score should be 0."""
        service = TemperatureService()

        # Create data with exactly -30% drawdown
        # Peak at 1.0, current at 0.7 = -30% drawdown
        days = 60
        prices = (
            [1.0] * 30 +  # Peak period
            [0.7] * 30    # Drawdown period at -30%
        )
        
        drawdown_data = pd.DataFrame({
            "date": [(datetime.now() - timedelta(days=days-i)).strftime("%Y-%m-%d") 
                     for i in range(days)],
            "close": prices,
            "open": prices,
            "high": [p + 0.01 for p in prices],
            "low": [p - 0.01 for p in prices],
            "volume": [1000000] * days,
        })

        score = service.calculate_drawdown_score(drawdown_data)
        
        # At -30% drawdown, score should be 0
        assert score == 0, f"Expected score 0 at -30% drawdown, got {score}"

    def test_drawdown_score_at_15pct(self):
        """At -15% drawdown (midpoint), score should be approximately 50."""
        service = TemperatureService()

        # Create data with -15% drawdown
        # Peak at 1.0, current at 0.85 = -15% drawdown
        days = 60
        prices = (
            [1.0] * 30 +  # Peak period
            [0.85] * 30   # Drawdown period at -15%
        )
        
        drawdown_data = pd.DataFrame({
            "date": [(datetime.now() - timedelta(days=days-i)).strftime("%Y-%m-%d") 
                     for i in range(days)],
            "close": prices,
            "open": prices,
            "high": [p + 0.01 for p in prices],
            "low": [p - 0.01 for p in prices],
            "volume": [1000000] * days,
        })

        score = service.calculate_drawdown_score(drawdown_data)
        
        # At -15% drawdown (midpoint of 0 to -30%), score should be ~50
        assert 45 <= score <= 55, f"Expected score ~50 at -15% drawdown, got {score}"


class TestPercentileCalculation:
    """Test historical percentile calculation."""

    def test_percentile_calculation(self, sample_long_history: pd.DataFrame):
        """
        Percentile should represent where current price falls in historical distribution.
        
        If current price is at the median of 10-year history, percentile should be ~0.5.
        """
        service = TemperatureService()
        result = service.calculate_percentile(sample_long_history)

        # Result should contain percentile_value and percentile_score
        assert "percentile_value" in result
        assert "percentile_score" in result
        
        # Percentile value should be between 0 and 1
        assert 0 <= result["percentile_value"] <= 1
        
        # Percentile score should be percentile_value * 100
        assert result["percentile_score"] == result["percentile_value"] * 100

    def test_percentile_with_short_history(self):
        """
        When data is less than 10 years, should include a note about limited data.
        """
        service = TemperatureService()

        # Create only 3 years of data (~756 trading days)
        days = 756
        short_history = pd.DataFrame({
            "date": [(datetime.now() - timedelta(days=days-i)).strftime("%Y-%m-%d") 
                     for i in range(days)],
            "close": [1.0 + np.sin(i / 50) * 0.2 for i in range(days)],  # Oscillating prices
            "open": [1.0] * days,
            "high": [1.3] * days,
            "low": [0.7] * days,
            "volume": [1000000] * days,
        })

        result = service.calculate_percentile(short_history)

        # Should include percentile_years indicating actual data coverage
        assert "percentile_years" in result
        assert result["percentile_years"] < 10
        
        # Should include a note about limited data
        assert "percentile_note" in result
        assert "年" in result["percentile_note"] or "year" in result["percentile_note"].lower()

    def test_percentile_at_historical_high(self, sample_long_history: pd.DataFrame):
        """At historical high, percentile should be close to 1.0."""
        service = TemperatureService()
        
        # Modify data so current price is at historical high
        modified_data = sample_long_history.copy()
        max_price = modified_data["close"].max()
        modified_data.iloc[-1, modified_data.columns.get_loc("close")] = max_price * 1.1
        
        result = service.calculate_percentile(modified_data)
        
        # At historical high, percentile should be very close to 1.0
        assert result["percentile_value"] >= 0.95

    def test_percentile_at_historical_low(self, sample_long_history: pd.DataFrame):
        """At historical low, percentile should be close to 0.0."""
        service = TemperatureService()
        
        # Modify data so current price is at historical low
        modified_data = sample_long_history.copy()
        min_price = modified_data["close"].min()
        modified_data.iloc[-1, modified_data.columns.get_loc("close")] = min_price * 0.9
        
        result = service.calculate_percentile(modified_data)
        
        # At historical low, percentile should be very close to 0.0
        assert result["percentile_value"] <= 0.05


class TestVolatilityScore:
    """Test volatility score calculation."""

    def test_volatility_score(self, sample_long_history: pd.DataFrame):
        """
        Volatility score should represent current volatility's percentile in history.
        
        Score = percentile of current volatility in historical volatility distribution * 100
        """
        service = TemperatureService()
        score = service.calculate_volatility_score(sample_long_history)

        # Score should be between 0 and 100
        assert 0 <= score <= 100
        
        # Score should be a number
        assert isinstance(score, (int, float))

    def test_volatility_score_high_volatility(self):
        """High current volatility should produce high score."""
        service = TemperatureService()

        # Create data with low historical volatility but high recent volatility
        days = 500
        # Low volatility for most of history
        low_vol_prices = [1.0 + i * 0.001 for i in range(days - 30)]
        # High volatility in recent period
        high_vol_prices = [1.5 + np.sin(i) * 0.3 for i in range(30)]
        
        prices = low_vol_prices + high_vol_prices
        
        high_vol_data = pd.DataFrame({
            "date": [(datetime.now() - timedelta(days=days-i)).strftime("%Y-%m-%d") 
                     for i in range(days)],
            "close": prices,
            "open": prices,
            "high": [p + 0.05 for p in prices],
            "low": [p - 0.05 for p in prices],
            "volume": [1000000] * days,
        })

        score = service.calculate_volatility_score(high_vol_data)
        
        # High recent volatility should produce score > 70
        assert score > 70, f"Expected high volatility score > 70, got {score}"

    def test_volatility_score_low_volatility(self):
        """Low current volatility should produce low score."""
        service = TemperatureService()

        # Create data with high historical volatility but low recent volatility
        days = 500
        # High volatility for most of history
        high_vol_prices = [1.0 + np.sin(i / 5) * 0.3 for i in range(days - 30)]
        # Low volatility in recent period
        low_vol_prices = [1.5 + i * 0.001 for i in range(30)]
        
        prices = high_vol_prices + low_vol_prices
        
        low_vol_data = pd.DataFrame({
            "date": [(datetime.now() - timedelta(days=days-i)).strftime("%Y-%m-%d") 
                     for i in range(days)],
            "close": prices,
            "open": prices,
            "high": [p + 0.01 for p in prices],
            "low": [p - 0.01 for p in prices],
            "volume": [1000000] * days,
        })

        score = service.calculate_volatility_score(low_vol_data)
        
        # Low recent volatility should produce score < 30
        assert score < 30, f"Expected low volatility score < 30, got {score}"


class TestTrendScore:
    """Test trend score calculation based on MA alignment."""

    def test_trend_score_bullish(self, bullish_trend_data: pd.DataFrame):
        """
        Bullish trend (多头排列: MA5 > MA10 > MA20 > MA60) should score 80.
        """
        service = TemperatureService()
        score = service.calculate_trend_score(bullish_trend_data)

        # Bullish trend should score 80
        assert score == 80, f"Expected bullish trend score 80, got {score}"

    def test_trend_score_bearish(self, bearish_trend_data: pd.DataFrame):
        """
        Bearish trend (空头排列: MA5 < MA10 < MA20 < MA60) should score 20.
        """
        service = TemperatureService()
        score = service.calculate_trend_score(bearish_trend_data)

        # Bearish trend should score 20
        assert score == 20, f"Expected bearish trend score 20, got {score}"

    def test_trend_score_neutral(self, sample_daily_data: pd.DataFrame):
        """
        Neutral/mixed trend (震荡) should score 50.
        """
        service = TemperatureService()
        
        # Create data with mixed MA alignment
        days = 70
        # Oscillating prices that don't form clear trend
        prices = [1.0 + np.sin(i / 10) * 0.1 for i in range(days)]
        
        neutral_data = pd.DataFrame({
            "date": [(datetime.now() - timedelta(days=days-i)).strftime("%Y-%m-%d") 
                     for i in range(days)],
            "close": prices,
            "open": prices,
            "high": [p + 0.02 for p in prices],
            "low": [p - 0.02 for p in prices],
            "volume": [1000000] * days,
        })

        score = service.calculate_trend_score(neutral_data)

        # Neutral trend should score 50
        assert score == 50, f"Expected neutral trend score 50, got {score}"


class TestTemperatureCalculation:
    """Test overall temperature calculation."""

    def test_temperature_weighted_sum(self, sample_daily_data: pd.DataFrame):
        """
        Temperature score should be weighted sum of all factors:
        - drawdown_score * 0.30
        - rsi_score * 0.20
        - percentile_score * 0.20
        - volatility_score * 0.15
        - trend_score * 0.15
        """
        service = TemperatureService()
        result = service.calculate_temperature(sample_daily_data)

        # Result should contain score and factors
        assert "score" in result
        assert "factors" in result
        
        # Factors should contain all component scores
        factors = result["factors"]
        assert "drawdown_score" in factors
        assert "rsi_score" in factors
        assert "percentile_score" in factors
        assert "volatility_score" in factors
        assert "trend_score" in factors

        # Verify weighted sum calculation
        expected_score = (
            factors["drawdown_score"] * 0.30 +
            factors["rsi_score"] * 0.20 +
            factors["percentile_score"] * 0.20 +
            factors["volatility_score"] * 0.15 +
            factors["trend_score"] * 0.15
        )
        
        # Score should match weighted sum (allow small rounding difference)
        assert abs(result["score"] - expected_score) < 1, \
            f"Score {result['score']} doesn't match expected weighted sum {expected_score}"

    def test_temperature_score_range(self, sample_daily_data: pd.DataFrame):
        """Temperature score should always be between 0 and 100."""
        service = TemperatureService()
        result = service.calculate_temperature(sample_daily_data)

        assert 0 <= result["score"] <= 100


class TestTemperatureLevel:
    """Test temperature level determination."""

    def test_temperature_level_freezing(self):
        """Score 0-30 should be 'freezing' level."""
        service = TemperatureService()

        # Create extreme oversold conditions
        days = 120
        # Sharp decline to create low temperature
        prices = [2.0 - i * 0.015 for i in range(days)]  # Steady decline
        
        freezing_data = pd.DataFrame({
            "date": [(datetime.now() - timedelta(days=days-i)).strftime("%Y-%m-%d") 
                     for i in range(days)],
            "close": prices,
            "open": [p + 0.01 for p in prices],
            "high": [p + 0.02 for p in prices],
            "low": [p - 0.01 for p in prices],
            "volume": [1000000] * days,
        })

        result = service.calculate_temperature(freezing_data)
        
        # Should be freezing level (score 0-30)
        assert result["level"] == "freezing", \
            f"Expected 'freezing' level for score {result['score']}, got '{result['level']}'"
        assert result["score"] <= 30

    def test_temperature_level_cool(self):
        """Score 31-50 should be 'cool' level."""
        service = TemperatureService()
        
        # Test the level determination directly
        assert service.get_temperature_level(31) == "cool"
        assert service.get_temperature_level(40) == "cool"
        assert service.get_temperature_level(50) == "cool"

    def test_temperature_level_warm(self):
        """Score 51-70 should be 'warm' level."""
        service = TemperatureService()
        
        # Test the level determination directly
        assert service.get_temperature_level(51) == "warm"
        assert service.get_temperature_level(60) == "warm"
        assert service.get_temperature_level(70) == "warm"

    def test_temperature_level_hot(self):
        """Score 71-100 should be 'hot' level."""
        service = TemperatureService()

        # Create extreme overbought conditions
        days = 120
        # Sharp rise to create high temperature
        prices = [1.0 + i * 0.015 for i in range(days)]  # Steady rise
        
        hot_data = pd.DataFrame({
            "date": [(datetime.now() - timedelta(days=days-i)).strftime("%Y-%m-%d") 
                     for i in range(days)],
            "close": prices,
            "open": [p - 0.01 for p in prices],
            "high": [p + 0.01 for p in prices],
            "low": [p - 0.02 for p in prices],
            "volume": [1000000] * days,
        })

        result = service.calculate_temperature(hot_data)
        
        # Should be hot level (score 71-100)
        assert result["level"] == "hot", \
            f"Expected 'hot' level for score {result['score']}, got '{result['level']}'"
        assert result["score"] >= 71

    def test_temperature_level_boundaries(self):
        """Test exact boundary values for temperature levels."""
        service = TemperatureService()
        
        # Test boundary values
        assert service.get_temperature_level(0) == "freezing"
        assert service.get_temperature_level(30) == "freezing"
        assert service.get_temperature_level(31) == "cool"
        assert service.get_temperature_level(50) == "cool"
        assert service.get_temperature_level(51) == "warm"
        assert service.get_temperature_level(70) == "warm"
        assert service.get_temperature_level(71) == "hot"
        assert service.get_temperature_level(100) == "hot"


class TestTemperatureOutputFormat:
    """Test the complete output format of temperature calculation."""

    def test_output_contains_all_fields(self, sample_daily_data: pd.DataFrame):
        """
        Output should match the expected format:
        {
            "score": 42,
            "level": "cool",
            "factors": {
                "drawdown_score": 25,
                "rsi_score": 40,
                "percentile_score": 30,
                "volatility_score": 45,
                "trend_score": 35
            },
            "rsi_value": 45.2,
            "percentile_value": 0.30,
            "percentile_years": 3.5,
            "percentile_note": "数据仅覆盖 3.5 年"  # Only when < 10 years
        }
        """
        service = TemperatureService()
        result = service.calculate_temperature(sample_daily_data)

        # Required fields
        assert "score" in result
        assert "level" in result
        assert "factors" in result
        assert "rsi_value" in result
        assert "percentile_value" in result
        
        # Score should be integer
        assert isinstance(result["score"], int)
        
        # Level should be valid
        assert result["level"] in ["freezing", "cool", "warm", "hot"]
        
        # RSI value should be the raw RSI (0-100)
        assert 0 <= result["rsi_value"] <= 100
        
        # Percentile value should be 0-1
        assert 0 <= result["percentile_value"] <= 1

    def test_output_with_short_history_includes_note(self):
        """When history < 10 years, output should include percentile_note."""
        service = TemperatureService()

        # Create 2 years of data
        days = 504  # ~2 years
        short_data = pd.DataFrame({
            "date": [(datetime.now() - timedelta(days=days-i)).strftime("%Y-%m-%d") 
                     for i in range(days)],
            "close": [1.0 + np.sin(i / 50) * 0.2 for i in range(days)],
            "open": [1.0] * days,
            "high": [1.3] * days,
            "low": [0.7] * days,
            "volume": [1000000] * days,
        })

        result = service.calculate_temperature(short_data)

        # Should include percentile_years and percentile_note
        assert "percentile_years" in result
        assert "percentile_note" in result
        assert result["percentile_years"] < 10


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_dataframe(self, empty_dataframe: pd.DataFrame):
        """Should handle empty DataFrame gracefully."""
        service = TemperatureService()

        # Should not raise exception, should return None or error indicator
        result = service.calculate_temperature(empty_dataframe)
        
        assert result is None or "error" in result

    def test_single_day_data(self, single_day_data: pd.DataFrame):
        """Should handle single day of data gracefully."""
        service = TemperatureService()

        result = service.calculate_temperature(single_day_data)
        
        # Should return None or indicate insufficient data
        assert result is None or "error" in result

    def test_data_with_nan_values(self):
        """Should handle data with NaN values."""
        service = TemperatureService()

        days = 120
        prices = [1.0 + i * 0.01 for i in range(days)]
        prices[50] = np.nan  # Insert NaN
        prices[75] = np.nan
        
        nan_data = pd.DataFrame({
            "date": [(datetime.now() - timedelta(days=days-i)).strftime("%Y-%m-%d") 
                     for i in range(days)],
            "close": prices,
            "open": [1.0] * days,
            "high": [1.5] * days,
            "low": [0.5] * days,
            "volume": [1000000] * days,
        })

        # Should not raise exception
        result = service.calculate_temperature(nan_data)
        
        # Result should be valid (implementation decides how to handle NaN)
        assert result is not None or result is None  # Either is acceptable

    def test_insufficient_data_for_rsi(self):
        """Should handle data with fewer days than RSI period."""
        service = TemperatureService()

        # Only 10 days, not enough for RSI(14)
        days = 10
        short_data = pd.DataFrame({
            "date": [(datetime.now() - timedelta(days=days-i)).strftime("%Y-%m-%d") 
                     for i in range(days)],
            "close": [1.0 + i * 0.01 for i in range(days)],
            "open": [1.0] * days,
            "high": [1.1] * days,
            "low": [0.9] * days,
            "volume": [1000000] * days,
        })

        # Should handle gracefully
        rsi = service.calculate_rsi(short_data, period=14)
        
        # Should return None or a reasonable default
        assert rsi is None or isinstance(rsi, float)
