"""
TemperatureService - 市场温度计算服务

基于 5 个因子加权计算市场温度：
| 因子 | 权重 | 计算方式 | 得分范围 |
|------|------|----------|----------|
| 回撤程度 | 30% | 当前回撤映射到 0-100（-30%回撤=0分，新高=100分） | 0-100 |
| RSI指标 | 20% | RSI(14) 直接作为得分（Wilder EMA 方式） | 0-100 |
| 历史分位 | 20% | 当前价格在近10年的分位数 × 100 | 0-100 |
| 波动水平 | 15% | 当前波动率在历史中的分位数 × 100 | 0-100 |
| 趋势强度 | 15% | 基于均线排列计算（多头=80，震荡=50，空头=20） | 0-100 |

温度等级：
- 0-30: `freezing` 冰点
- 31-50: `cool` 温和
- 51-70: `warm` 偏热
- 71-100: `hot` 过热
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Any

import pandas as pd
import numpy as np

from app.core.config_loader import metric_config

logger = logging.getLogger(__name__)

# 每年交易日数（约 252 天）
TRADING_DAYS_PER_YEAR = 252


class TemperatureService:
    """市场温度计算服务类"""

    def __init__(self):
        """初始化温度服务"""
        pass

    # ==================== RSI 计算 (Wilder EMA) ====================

    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> Optional[float]:
        """
        使用 Wilder 平滑方法计算 RSI

        Wilder 方法：
        1. 首先计算前 period 天的简单移动平均 (SMA) 作为初始值
        2. 然后使用递归公式：avg = (prev_avg * (period - 1) + current_value) / period

        Args:
            df: 包含 close 列的 OHLCV DataFrame
            period: RSI 周期，默认 14

        Returns:
            RSI 值 (0-100)，数据不足时返回 None
        """
        if df is None or df.empty or len(df) < period + 1:
            return None

        # 计算价格变动
        close = df["close"].dropna()
        if len(close) < period + 1:
            return None

        delta = close.diff()

        # 分离涨跌
        gains = delta.where(delta > 0, 0.0).fillna(0.0)
        losses = (-delta).where(delta < 0, 0.0).fillna(0.0)

        # Wilder 平滑方法：
        # 1. 首先计算前 period 天的 SMA 作为初始值
        # 2. 然后使用递归公式
        
        # 计算初始 SMA（从索引 1 开始，因为索引 0 是 NaN）
        first_avg_gain = gains.iloc[1:period + 1].mean()
        first_avg_loss = losses.iloc[1:period + 1].mean()

        # 如果数据刚好等于 period + 1，直接使用 SMA
        if len(close) == period + 1:
            if first_avg_loss == 0:
                return 100.0 if first_avg_gain > 0 else 50.0
            rs = first_avg_gain / first_avg_loss
            return float(100 - (100 / (1 + rs)))

        # 递归计算后续值
        avg_gain = first_avg_gain
        avg_loss = first_avg_loss

        for i in range(period + 1, len(close)):
            avg_gain = (avg_gain * (period - 1) + gains.iloc[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses.iloc[i]) / period

        # 处理边界情况
        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0

        if avg_gain == 0:
            return 0.0

        # 计算 RS 和 RSI
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return float(rsi)

    # ==================== 回撤得分计算 ====================

    def calculate_drawdown_score(self, df: pd.DataFrame) -> int:
        """
        计算回撤得分

        映射规则：
        - 新高 (0% 回撤) = 100 分
        - -30% 回撤 = 0 分
        - 线性映射

        Args:
            df: OHLCV DataFrame

        Returns:
            回撤得分 (0-100)
        """
        if df is None or df.empty:
            return 50  # 默认中间值

        close = df["close"].dropna()
        if len(close) == 0:
            return 50

        # 计算当前回撤
        current_price = close.iloc[-1]
        peak_price = close.max()

        if peak_price <= 0:
            return 50

        drawdown = (current_price - peak_price) / peak_price  # 负数或零

        # 映射: 0% -> 100, -30% -> 0
        # score = 100 + (drawdown / 0.30) * 100
        # 简化: score = 100 * (1 + drawdown / 0.30)
        score = 100 * (1 + drawdown / 0.30)

        # 限制在 0-100 范围内
        return int(max(0, min(100, score)))

    # ==================== 历史分位计算 ====================

    def calculate_percentile(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        计算当前价格在历史中的分位数

        Args:
            df: OHLCV DataFrame

        Returns:
            包含 percentile_value, percentile_score, percentile_years 的字典
            如果数据不足 10 年，还包含 percentile_note
        """
        target_years = metric_config.percentile_years  # 默认 10 年
        target_days = target_years * TRADING_DAYS_PER_YEAR

        if df is None or df.empty:
            return {
                "percentile_value": 0.5,
                "percentile_score": 50.0,
                "percentile_years": 0,
                "percentile_note": "无数据",
            }

        close = df["close"].dropna()
        if len(close) == 0:
            return {
                "percentile_value": 0.5,
                "percentile_score": 50.0,
                "percentile_years": 0,
                "percentile_note": "无数据",
            }

        # 计算实际数据覆盖年数
        actual_days = len(close)
        actual_years = round(actual_days / TRADING_DAYS_PER_YEAR, 1)

        # 取最近 N 年的数据
        if actual_days > target_days:
            close = close.iloc[-int(target_days):]

        # 计算当前价格的分位数
        current_price = close.iloc[-1]
        percentile_value = (close < current_price).sum() / len(close)

        result = {
            "percentile_value": float(percentile_value),
            "percentile_score": float(percentile_value * 100),
            "percentile_years": actual_years,
        }

        # 如果数据不足目标年数，添加提示
        if actual_years < target_years:
            result["percentile_note"] = f"数据仅覆盖 {actual_years} 年"

        return result

    # ==================== 波动率得分计算 ====================

    def calculate_volatility_score(self, df: pd.DataFrame, window: int = 20) -> float:
        """
        计算波动率得分

        当前波动率在历史波动率分布中的分位数 × 100

        Args:
            df: OHLCV DataFrame
            window: 波动率计算窗口，默认 20 天

        Returns:
            波动率得分 (0-100)
        """
        if df is None or df.empty or len(df) < window + 1:
            return 50.0  # 默认中间值

        close = df["close"].dropna()
        if len(close) < window + 1:
            return 50.0

        # 计算日收益率
        returns = close.pct_change().dropna()
        if len(returns) < window:
            return 50.0

        # 计算滚动波动率（标准差）
        rolling_vol = returns.rolling(window=window).std()
        rolling_vol = rolling_vol.dropna()

        if len(rolling_vol) == 0:
            return 50.0

        # 当前波动率
        current_vol = rolling_vol.iloc[-1]

        # 计算当前波动率在历史中的分位数
        percentile = (rolling_vol < current_vol).sum() / len(rolling_vol)

        return float(percentile * 100)

    # ==================== 趋势得分计算 ====================

    def calculate_trend_score(self, df: pd.DataFrame) -> int:
        """
        基于均线排列计算趋势得分

        - 多头排列 (MA5 > MA10 > MA20 > MA60): 80 分
        - 空头排列 (MA5 < MA10 < MA20 < MA60): 20 分
        - 震荡: 50 分

        Args:
            df: OHLCV DataFrame

        Returns:
            趋势得分 (20, 50, 或 80)
        """
        if df is None or df.empty:
            return 50

        close = df["close"].dropna()
        # 需要至少 60 天数据来计算 MA60
        if len(close) < 60:
            return 50

        # 计算均线
        ma5 = close.rolling(window=5, min_periods=5).mean().iloc[-1]
        ma10 = close.rolling(window=10, min_periods=10).mean().iloc[-1]
        ma20 = close.rolling(window=20, min_periods=20).mean().iloc[-1]
        ma60 = close.rolling(window=60, min_periods=60).mean().iloc[-1]

        # 检查是否有 NaN
        if any(pd.isna([ma5, ma10, ma20, ma60])):
            return 50

        # 判断排列
        # 多头排列: MA5 > MA10 > MA20 > MA60
        if ma5 > ma10 > ma20 > ma60:
            return 80

        # 空头排列: MA5 < MA10 < MA20 < MA60
        if ma5 < ma10 < ma20 < ma60:
            return 20

        # 震荡
        return 50

    # ==================== 温度等级判断 ====================

    def get_temperature_level(self, score: float) -> str:
        """
        根据温度得分判断等级

        - 0-30: freezing (冰点)
        - 31-50: cool (温和)
        - 51-70: warm (偏热)
        - 71-100: hot (过热)

        Args:
            score: 温度得分 (0-100)

        Returns:
            温度等级字符串
        """
        if score <= 30:
            return "freezing"
        elif score <= 50:
            return "cool"
        elif score <= 70:
            return "warm"
        else:
            return "hot"

    # ==================== 温度计算主函数 ====================

    def calculate_temperature(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        计算市场温度

        综合 5 个因子加权计算：
        - 回撤程度 (30%)
        - RSI 指标 (20%)
        - 历史分位 (20%)
        - 波动水平 (15%)
        - 趋势强度 (15%)

        Args:
            df: OHLCV DataFrame

        Returns:
            温度计算结果字典，包含:
            - score: 综合温度得分 (0-100)
            - level: 温度等级 (freezing/cool/warm/hot)
            - factors: 各因子得分
            - rsi_value: 原始 RSI 值
            - percentile_value: 分位数值 (0-1)
            - percentile_years: 数据覆盖年数
            - percentile_note: 数据不足时的提示（可选）

            数据不足时返回 None 或包含 error 的字典
        """
        # 数据验证
        if df is None or df.empty:
            return None

        if len(df) < 15:  # 至少需要 RSI 周期 + 1 天的数据
            return None

        # 获取权重配置
        weights = metric_config.temperature_weights
        rsi_period = metric_config.rsi_period

        # 计算各因子得分
        # 1. 回撤得分 (30%)
        drawdown_score = self.calculate_drawdown_score(df)

        # 2. RSI 得分 (20%)
        rsi_value = self.calculate_rsi(df, period=rsi_period)
        if rsi_value is None:
            rsi_value = 50.0  # 默认中间值
        rsi_score = rsi_value  # RSI 直接作为得分

        # 3. 历史分位得分 (20%)
        percentile_result = self.calculate_percentile(df)
        percentile_score = percentile_result["percentile_score"]

        # 4. 波动率得分 (15%)
        volatility_score = self.calculate_volatility_score(df)

        # 5. 趋势得分 (15%)
        trend_score = self.calculate_trend_score(df)

        # 加权计算综合得分
        weighted_score = (
            drawdown_score * weights.get("drawdown", 0.30) +
            rsi_score * weights.get("rsi", 0.20) +
            percentile_score * weights.get("percentile", 0.20) +
            volatility_score * weights.get("volatility", 0.15) +
            trend_score * weights.get("trend", 0.15)
        )

        # 四舍五入为整数
        final_score = int(round(weighted_score))

        # 确定温度等级
        level = self.get_temperature_level(final_score)

        # 构建结果
        result = {
            "score": final_score,
            "level": level,
            "factors": {
                "drawdown_score": drawdown_score,
                "rsi_score": rsi_score,
                "percentile_score": percentile_score,
                "volatility_score": volatility_score,
                "trend_score": trend_score,
            },
            "rsi_value": rsi_value,
            "percentile_value": percentile_result["percentile_value"],
            "percentile_years": percentile_result["percentile_years"],
        }

        # 如果数据不足，添加提示
        if "percentile_note" in percentile_result:
            result["percentile_note"] = percentile_result["percentile_note"]

        return result


# 全局单例
temperature_service = TemperatureService()
