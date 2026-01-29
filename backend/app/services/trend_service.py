"""
TrendService - 趋势分析服务

提供日线和周线趋势分析功能：
- 均线计算 (MA5, MA20, MA60)
- 价格与均线位置关系判断 (above, below, crossing_up, crossing_down)
- 均线排列判断 (bullish, bearish, mixed)
- 周线重采样和连续涨跌周统计
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Any, List

import pandas as pd
import numpy as np

from app.core.config_loader import metric_config

logger = logging.getLogger(__name__)


class TrendService:
    """趋势分析服务类"""

    def __init__(self):
        """初始化趋势服务"""
        pass

    # ==================== 均线计算 ====================

    def _calculate_ma(self, df: pd.DataFrame, period: int) -> Optional[pd.Series]:
        """
        计算单条均线

        Args:
            df: 包含 close 列的 DataFrame
            period: 均线周期

        Returns:
            均线 Series，如果数据不足则返回 None
        """
        if df is None or df.empty or len(df) < period:
            return None

        return df["close"].rolling(window=period).mean()

    def calculate_ma_values(self, df: pd.DataFrame) -> Dict[str, Optional[float]]:
        """
        计算所有均线的当前值

        Args:
            df: OHLCV DataFrame

        Returns:
            包含 ma5, ma20, ma60 当前值的字典
        """
        periods = metric_config.daily_ma_periods  # [5, 20, 60]
        result = {}

        for period in periods:
            ma_series = self._calculate_ma(df, period)
            key = f"ma{period}"
            if ma_series is not None and len(ma_series) > 0 and not pd.isna(ma_series.iloc[-1]):
                result[key] = float(ma_series.iloc[-1])
            else:
                result[key] = None

        return result

    # ==================== 位置判断 ====================

    def _determine_position(
        self,
        price_today: float,
        ma_today: float,
        price_yesterday: float,
        ma_yesterday: float,
    ) -> str:
        """
        判断价格与均线的位置关系

        Args:
            price_today: 今日收盘价
            ma_today: 今日均线值
            price_yesterday: 昨日收盘价
            ma_yesterday: 昨日均线值

        Returns:
            位置关系: "crossing_up", "crossing_down", "above", "below"
        """
        # 向上突破: 昨日收盘 < 昨日均线，今日收盘 >= 今日均线
        if price_yesterday < ma_yesterday and price_today >= ma_today:
            return "crossing_up"

        # 向下破位: 昨日收盘 > 昨日均线，今日收盘 <= 今日均线
        if price_yesterday > ma_yesterday and price_today <= ma_today:
            return "crossing_down"

        # 在均线上方
        if price_today > ma_today:
            return "above"

        # 在均线下方
        return "below"

    def determine_position(self, df: pd.DataFrame, ma_period: int) -> Optional[str]:
        """
        判断当前价格与指定均线的位置关系

        Args:
            df: OHLCV DataFrame
            ma_period: 均线周期

        Returns:
            位置关系字符串，数据不足时返回 None
        """
        if df is None or df.empty or len(df) < ma_period + 1:
            return None

        ma_series = self._calculate_ma(df, ma_period)
        if ma_series is None:
            return None

        # 获取今日和昨日数据
        price_today = df["close"].iloc[-1]
        price_yesterday = df["close"].iloc[-2]
        ma_today = ma_series.iloc[-1]
        ma_yesterday = ma_series.iloc[-2]

        if pd.isna(ma_today) or pd.isna(ma_yesterday):
            return None

        return self._determine_position(price_today, ma_today, price_yesterday, ma_yesterday)

    # ==================== 均线排列 ====================

    def _determine_alignment(self, ma_values: Dict[str, Optional[float]]) -> str:
        """
        判断均线排列状态

        Args:
            ma_values: 包含 ma5, ma20, ma60 的字典

        Returns:
            排列状态: "bullish", "bearish", "mixed"
        """
        ma5 = ma_values.get("ma5")
        ma20 = ma_values.get("ma20")
        ma60 = ma_values.get("ma60")

        # 如果任何均线为 None，返回 mixed
        if ma5 is None or ma20 is None or ma60 is None:
            return "mixed"

        # 多头排列: MA5 > MA20 > MA60
        if ma5 > ma20 > ma60:
            return "bullish"

        # 空头排列: MA5 < MA20 < MA60
        if ma5 < ma20 < ma60:
            return "bearish"

        # 其他情况: 震荡
        return "mixed"

    def get_ma_alignment(self, df: pd.DataFrame) -> str:
        """
        获取均线排列状态

        Args:
            df: OHLCV DataFrame

        Returns:
            排列状态: "bullish", "bearish", "mixed"
        """
        ma_values = self.calculate_ma_values(df)
        return self._determine_alignment(ma_values)

    # ==================== 信号提取 ====================

    def _find_latest_signal(self, daily_trend: Dict[str, Any]) -> Optional[str]:
        """
        提取最重要的突破信号

        优先级: MA60 > MA20 > MA5

        Args:
            daily_trend: 日趋势分析结果

        Returns:
            最新信号字符串，如 "break_above_ma20"，无信号时返回 None
        """
        # 按优先级检查均线突破
        for ma_key in ["ma60", "ma20", "ma5"]:
            position_key = f"{ma_key}_position"
            position = daily_trend.get(position_key)

            if position == "crossing_up":
                return f"break_above_{ma_key}"
            elif position == "crossing_down":
                return f"break_below_{ma_key}"

        return None

    # ==================== 日趋势主函数 ====================

    def get_daily_trend(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        日趋势分析主函数

        Args:
            df: OHLCV DataFrame

        Returns:
            日趋势分析结果字典，包含:
            - ma5_position: MA5 位置关系
            - ma20_position: MA20 位置关系
            - ma60_position: MA60 位置关系
            - ma_alignment: 均线排列状态
            - latest_signal: 最新突破信号
            - ma_values: 均线当前值
        """
        if df is None or df.empty:
            return None

        # 数据量不足以计算任何有意义的指标
        if len(df) < 5:
            return None

        # 计算均线值
        ma_values = self.calculate_ma_values(df)

        # 如果连 MA5 都无法计算，返回 None
        if ma_values.get("ma5") is None:
            return None

        # 计算各均线位置
        periods = metric_config.daily_ma_periods  # [5, 20, 60]
        positions = {}
        for period in periods:
            position = self.determine_position(df, period)
            positions[f"ma{period}_position"] = position

        # 判断均线排列
        alignment = self._determine_alignment(ma_values)

        # 构建结果
        result = {
            "ma5_position": positions.get("ma5_position"),
            "ma20_position": positions.get("ma20_position"),
            "ma60_position": positions.get("ma60_position"),
            "ma_alignment": alignment,
            "ma_values": ma_values,
        }

        # 提取最新信号
        result["latest_signal"] = self._find_latest_signal(result)

        return result

    # ==================== 周线处理 ====================

    def _resample_to_weekly(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        日线转周线

        Args:
            df: 日线 OHLCV DataFrame

        Returns:
            周线 OHLCV DataFrame
        """
        if df is None or df.empty:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

        # 确保 date 列是 datetime 类型
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])

        # 设置 date 为索引
        df.set_index("date", inplace=True)

        # 按周重采样 (W-FRI 表示周五为周结束)
        weekly = df.resample("W-FRI").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        })

        # 移除空行 (没有交易数据的周)
        weekly = weekly.dropna()

        # 重置索引
        weekly = weekly.reset_index()
        weekly["date"] = weekly["date"].dt.strftime("%Y-%m-%d")

        return weekly

    def resample_to_weekly(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        公开的周线重采样方法

        Args:
            df: 日线 OHLCV DataFrame

        Returns:
            周线 OHLCV DataFrame
        """
        return self._resample_to_weekly(df)

    def _count_consecutive_weeks(self, weekly_df: pd.DataFrame) -> Dict[str, Any]:
        """
        统计连续涨跌周数

        Args:
            weekly_df: 周线 OHLCV DataFrame

        Returns:
            包含 consecutive_weeks 和 direction 的字典
        """
        if weekly_df is None or weekly_df.empty:
            return {"consecutive_weeks": 0, "direction": "flat"}

        # 计算每周涨跌 (close vs open)
        weekly_df = weekly_df.copy()
        weekly_df["change"] = weekly_df["close"] - weekly_df["open"]

        # 从最近一周开始向前统计
        consecutive = 0
        direction = "flat"

        for i in range(len(weekly_df) - 1, -1, -1):
            change = weekly_df.iloc[i]["change"]

            if change > 0:
                current_dir = "up"
            elif change < 0:
                current_dir = "down"
            else:
                current_dir = "flat"

            # 第一周确定方向
            if consecutive == 0:
                if current_dir == "flat":
                    # 平盘不计入连续
                    continue
                direction = current_dir
                consecutive = 1
            elif current_dir == direction:
                consecutive += 1
            else:
                # 方向改变，停止计数
                break

        # 负数表示连跌
        if direction == "down":
            consecutive = -consecutive

        return {"consecutive_weeks": consecutive, "direction": direction}

    def count_consecutive_weeks(self, weekly_df: pd.DataFrame) -> Dict[str, Any]:
        """
        公开的连续周数统计方法

        Args:
            weekly_df: 周线 OHLCV DataFrame

        Returns:
            包含 consecutive_weeks 和 direction 的字典
        """
        return self._count_consecutive_weeks(weekly_df)

    def _get_weekly_ma_status(self, weekly_df: pd.DataFrame) -> str:
        """
        获取周均线排列状态

        Args:
            weekly_df: 周线 OHLCV DataFrame

        Returns:
            排列状态: "bullish", "bearish", "mixed"
        """
        if weekly_df is None or weekly_df.empty:
            return "mixed"

        periods = metric_config.weekly_ma_periods  # [5, 10, 20]
        ma_values = {}

        for period in periods:
            ma_series = self._calculate_ma(weekly_df, period)
            key = f"ma{period}"
            if ma_series is not None and len(ma_series) > 0 and not pd.isna(ma_series.iloc[-1]):
                ma_values[key] = float(ma_series.iloc[-1])
            else:
                ma_values[key] = None

        # 获取周均线值
        ma5 = ma_values.get("ma5")
        ma10 = ma_values.get("ma10")
        ma20 = ma_values.get("ma20")

        if ma5 is None or ma10 is None or ma20 is None:
            return "mixed"

        # 多头排列: MA5 > MA10 > MA20
        if ma5 > ma10 > ma20:
            return "bullish"

        # 空头排列: MA5 < MA10 < MA20
        if ma5 < ma10 < ma20:
            return "bearish"

        return "mixed"

    # ==================== 周趋势主函数 ====================

    def get_weekly_trend(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        周趋势分析主函数

        Args:
            df: 日线 OHLCV DataFrame

        Returns:
            周趋势分析结果字典，包含:
            - consecutive_weeks: 连续涨跌周数 (正数=连涨，负数=连跌)
            - direction: 方向 ("up", "down", "flat")
            - ma_status: 周均线排列状态 ("bullish", "bearish", "mixed")
        """
        if df is None or df.empty:
            return None

        # 转换为周线数据
        weekly_df = self._resample_to_weekly(df)

        if weekly_df.empty:
            return None

        # 统计连续周数
        consecutive_result = self._count_consecutive_weeks(weekly_df)

        # 获取周均线状态
        ma_status = self._get_weekly_ma_status(weekly_df)

        return {
            "consecutive_weeks": consecutive_result["consecutive_weeks"],
            "direction": consecutive_result["direction"],
            "ma_status": ma_status,
        }


# 全局单例
trend_service = TrendService()
