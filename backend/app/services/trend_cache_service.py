"""
TrendCacheService - 趋势缓存服务

包装 trend_service，提供缓存和增量计算功能：
- 日趋势缓存：缓存均线值和位置关系
- 周趋势缓存：缓存周线数据和连续涨跌周数
- 盘中保护：盘中数据不写入缓存
- 强制刷新：支持跳过缓存重新计算
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Any

import pandas as pd

from app.services.akshare_service import disk_cache
from app.services.trend_service import trend_service

logger = logging.getLogger(__name__)


class TrendCacheService:
    """趋势缓存服务类"""

    # 缓存 key 前缀
    DAILY_TREND_PREFIX = "daily_trend"
    WEEKLY_TREND_PREFIX = "weekly_trend"

    def __init__(self):
        """初始化趋势缓存服务"""
        pass

    # ==================== 工具方法 ====================

    def _is_intraday(self, realtime_date: str, history_last_date: str) -> bool:
        """
        判断是否为盘中数据

        盘中判断逻辑：
        - 实时数据日期 == 历史最新日期 → 盘中（不写缓存）
        - 实时数据日期 > 历史最新日期 → 收盘后（写缓存）

        Args:
            realtime_date: 实时数据日期 (YYYY-MM-DD)
            history_last_date: 历史数据最新日期 (YYYY-MM-DD)

        Returns:
            True 表示盘中，False 表示收盘后
        """
        return realtime_date == history_last_date

    def _get_cache_key(self, code: str, trend_type: str) -> str:
        """
        生成缓存 key

        Args:
            code: ETF 代码
            trend_type: 趋势类型 ("daily" 或 "weekly")

        Returns:
            缓存 key，格式为 "{prefix}:{code}"
        """
        if trend_type == "daily":
            return f"{self.DAILY_TREND_PREFIX}:{code}"
        else:
            return f"{self.WEEKLY_TREND_PREFIX}:{code}"

    def _get_last_date(self, df: pd.DataFrame) -> Optional[str]:
        """
        获取 DataFrame 的最后日期

        Args:
            df: OHLCV DataFrame

        Returns:
            最后日期字符串，数据为空时返回 None
        """
        if df is None or df.empty:
            return None
        return str(df["date"].iloc[-1])

    # ==================== 日趋势缓存 ====================

    def _build_daily_cache_data(
        self, df: pd.DataFrame, result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        构建日趋势缓存数据结构

        Args:
            df: OHLCV DataFrame
            result: 计算结果

        Returns:
            缓存数据字典
        """
        last_date = self._get_last_date(df)

        # 获取昨日数据用于下次增量计算
        yesterday_close = None
        yesterday_ma = {}

        if len(df) >= 2:
            yesterday_close = float(df["close"].iloc[-2])

        # 从结果中提取均线值
        ma_values = result.get("ma_values", {})

        return {
            "last_date": last_date,
            "yesterday_close": yesterday_close,
            "yesterday_ma": ma_values,  # 当前均线值将成为下次的"昨日均线"
            "result": result,
        }

    def get_daily_trend(
        self,
        code: str,
        df: pd.DataFrame,
        realtime_price: Optional[float] = None,
        force_refresh: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        获取日趋势（带缓存）

        Args:
            code: ETF 代码
            df: 历史 OHLCV 数据
            realtime_price: 可选的实时价格（盘中使用）
            force_refresh: 强制刷新，跳过缓存

        Returns:
            日趋势分析结果
        """
        cache_key = self._get_cache_key(code, "daily")
        current_date = self._get_last_date(df)

        if current_date is None:
            logger.warning(f"[{code}] Empty DataFrame, cannot compute daily trend")
            return None

        # 强制刷新时跳过缓存读取
        if not force_refresh:
            cached = disk_cache.get(cache_key)

            if cached is not None:
                cached_date = cached.get("last_date")

                # 缓存命中：日期相同且没有实时价格
                if cached_date == current_date and realtime_price is None:
                    logger.debug(f"[{code}] Daily trend cache hit")
                    return cached.get("result")

                # 盘中模式：有实时价格且日期相同
                if realtime_price is not None and cached_date == current_date:
                    # 盘中计算，但不写入缓存
                    logger.debug(f"[{code}] Intraday mode, computing without cache write")
                    result = trend_service.get_daily_trend(df)
                    return result

        # 缓存未命中或强制刷新：重新计算
        logger.info(f"[{code}] Computing daily trend (cache miss or force refresh)")
        result = trend_service.get_daily_trend(df)

        if result is None:
            return None

        # 判断是否为盘中（有实时价格且日期相同表示盘中）
        is_intraday = realtime_price is not None

        # 非盘中时写入缓存
        if not is_intraday:
            cache_data = self._build_daily_cache_data(df, result)
            disk_cache.set(cache_key, cache_data)
            logger.debug(f"[{code}] Daily trend cached for date {current_date}")

        return result

    # ==================== 周趋势缓存 ====================

    def _build_weekly_cache_data(
        self, df: pd.DataFrame, result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        构建周趋势缓存数据结构

        Args:
            df: OHLCV DataFrame
            result: 计算结果

        Returns:
            缓存数据字典
        """
        last_date = self._get_last_date(df)

        return {
            "last_date": last_date,
            "result": result,
        }

    def get_weekly_trend(
        self,
        code: str,
        df: pd.DataFrame,
        force_refresh: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        获取周趋势（带缓存）

        Args:
            code: ETF 代码
            df: 历史 OHLCV 数据
            force_refresh: 强制刷新，跳过缓存

        Returns:
            周趋势分析结果
        """
        cache_key = self._get_cache_key(code, "weekly")
        current_date = self._get_last_date(df)

        if current_date is None:
            logger.warning(f"[{code}] Empty DataFrame, cannot compute weekly trend")
            return None

        # 强制刷新时跳过缓存读取
        if not force_refresh:
            cached = disk_cache.get(cache_key)

            if cached is not None:
                cached_date = cached.get("last_date")

                # 缓存命中：日期相同
                if cached_date == current_date:
                    logger.debug(f"[{code}] Weekly trend cache hit")
                    return cached.get("result")

        # 缓存未命中或强制刷新：重新计算
        logger.info(f"[{code}] Computing weekly trend (cache miss or force refresh)")
        result = trend_service.get_weekly_trend(df)

        if result is None:
            return None

        # 写入缓存
        cache_data = self._build_weekly_cache_data(df, result)
        disk_cache.set(cache_key, cache_data)
        logger.debug(f"[{code}] Weekly trend cached for date {current_date}")

        return result


# 全局单例
trend_cache_service = TrendCacheService()
