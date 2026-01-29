"""
TemperatureCacheService - 温度缓存服务

包装 temperature_service，提供缓存和增量计算功能：
- 温度缓存：缓存各因子得分和综合温度
- 盘中保护：盘中数据不写入缓存
- 强制刷新：支持跳过缓存重新计算
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Any

import pandas as pd

from app.services.akshare_service import disk_cache
from app.services.temperature_service import temperature_service

logger = logging.getLogger(__name__)


class TemperatureCacheService:
    """温度缓存服务类"""

    # 缓存 key 前缀
    TEMPERATURE_PREFIX = "temperature"

    def __init__(self):
        """初始化温度缓存服务"""
        pass

    # ==================== 工具方法 ====================

    def _get_cache_key(self, code: str) -> str:
        """
        生成缓存 key

        Args:
            code: ETF 代码

        Returns:
            缓存 key，格式为 "temperature:{code}"
        """
        return f"{self.TEMPERATURE_PREFIX}:{code}"

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

    # ==================== 缓存数据构建 ====================

    def _build_cache_data(
        self, df: pd.DataFrame, result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        构建温度缓存数据结构

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

    # ==================== 温度计算主函数 ====================

    def calculate_temperature(
        self,
        code: str,
        df: pd.DataFrame,
        realtime_price: Optional[float] = None,
        force_refresh: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        计算市场温度（带缓存）

        Args:
            code: ETF 代码
            df: 历史 OHLCV 数据
            realtime_price: 可选的实时价格（盘中使用）
            force_refresh: 强制刷新，跳过缓存

        Returns:
            温度计算结果
        """
        cache_key = self._get_cache_key(code)
        current_date = self._get_last_date(df)

        if current_date is None:
            logger.warning(f"[{code}] Empty DataFrame, cannot compute temperature")
            return None

        # 强制刷新时跳过缓存读取
        if not force_refresh:
            cached = disk_cache.get(cache_key)

            if cached is not None:
                cached_date = cached.get("last_date")

                # 缓存命中：日期相同且没有实时价格
                if cached_date == current_date and realtime_price is None:
                    logger.debug(f"[{code}] Temperature cache hit")
                    return cached.get("result")

                # 盘中模式：有实时价格且日期相同
                if realtime_price is not None and cached_date == current_date:
                    # 盘中计算，但不写入缓存
                    logger.debug(
                        f"[{code}] Intraday mode, computing without cache write"
                    )
                    result = temperature_service.calculate_temperature(df)
                    return result

        # 缓存未命中或强制刷新：重新计算
        logger.info(f"[{code}] Computing temperature (cache miss or force refresh)")
        result = temperature_service.calculate_temperature(df)

        if result is None:
            return None

        # 判断是否为盘中（有实时价格表示盘中）
        is_intraday = realtime_price is not None

        # 非盘中时写入缓存
        if not is_intraday:
            cache_data = self._build_cache_data(df, result)
            disk_cache.set(cache_key, cache_data)
            logger.debug(f"[{code}] Temperature cached for date {current_date}")

        return result


# 全局单例
temperature_cache_service = TemperatureCacheService()
