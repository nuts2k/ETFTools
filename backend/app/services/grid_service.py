import pandas as pd
import numpy as np
from typing import Dict, Any
import logging

from app.services.akshare_service import disk_cache, ak_service

logger = logging.getLogger(__name__)

def _calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """
    计算 ATR (Average True Range)
    
    Args:
        df: 包含 high, low, close 列的数据
        period: ATR 计算周期
        
    Returns:
        ATR 值
    """
    if len(df) < period + 1:
        return 0.0
    
    prev_close = df['close'].shift(1)
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - prev_close).abs(),
        (df['low'] - prev_close).abs()
    ], axis=1).max(axis=1)
    
    atr_series = tr.rolling(window=period).mean()
    if pd.isna(atr_series.iloc[-1]):
        return 0.0
    
    return float(atr_series.iloc[-1])


def calculate_grid_params(df: pd.DataFrame) -> Dict[str, Any]:
    """
    计算网格交易参数
    
    Args:
        df: 包含 date, close, high, low 列的历史数据
        
    Returns:
        网格参数字典，包含 upper, lower, spacing_pct, grid_count 等
    """
    if df.empty or len(df) < 30:
        return {}
        
    # 使用最近 60 天数据
    recent_df = df.tail(60).copy()
    
    # 使用分位数计算上下界
    upper = recent_df['close'].quantile(0.95)
    lower = recent_df['close'].quantile(0.05)
    current_price = recent_df['close'].iloc[-1]
    
    # 使用 ATR 动态计算网格间距
    atr = _calculate_atr(recent_df, period=14)
    avg_price = (upper + lower) / 2
    
    if avg_price > 0 and atr > 0:
        # ATR 占均价的百分比作为基础间距
        atr_pct = (atr / avg_price)
        # 间距范围：1% - 3%，根据 ATR 动态调整
        spacing_pct = max(0.01, min(0.03, atr_pct * 1.5))
    else:
        # 降级为固定间距
        spacing_pct = 0.015
    
    # 计算网格数量
    price_range = upper - lower
    avg_price = (upper + lower) / 2
    step = avg_price * spacing_pct
    
    if step == 0:
        count = 0
    else:
        count = int(price_range / step)
    
    # 限制网格数量在 5-20 之间
    count = max(5, min(count, 20))
    
    # 确保所有值都是标准 Python 类型（避免 numpy 类型序列化问题）
    return {
        "upper": round(float(upper), 3),
        "lower": round(float(lower), 3),
        "spacing_pct": round(float(spacing_pct * 100), 2),
        "grid_count": int(count),
        "range_start": str(recent_df['date'].iloc[0])[:10] if 'date' in recent_df.columns else "",
        "range_end": str(recent_df['date'].iloc[-1])[:10] if 'date' in recent_df.columns else "",
        "is_out_of_range": bool(current_price > upper * 1.05 or current_price < lower * 0.95)
    }


def calculate_grid_params_cached(code: str, force_refresh: bool = False) -> Dict[str, Any]:
    """
    带缓存的网格参数计算
    
    Args:
        code: ETF 代码
        force_refresh: 是否强制刷新缓存
        
    Returns:
        网格参数字典，包含 upper, lower, spacing_pct, grid_count 等
    """
    cache_key = f"grid_params_{code}"
    
    # 如果不强制刷新，先尝试从缓存读取
    if not force_refresh:
        cached = disk_cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Grid params cache hit for {code}")
            return cached
    
    # 缓存未命中或强制刷新，重新计算
    logger.info(f"Calculating grid params for {code} (force_refresh={force_refresh})")
    
    # 获取历史数据
    df = ak_service.fetch_history_raw(code, period="daily", adjust="qfq")
    
    if df.empty:
        logger.warning(f"No history data found for {code}")
        return {}
    
    # 计算网格参数
    result = calculate_grid_params(df)
    
    # 如果计算成功，写入缓存（4 小时过期）
    if result:
        disk_cache.set(cache_key, result, expire=14400)
        logger.debug(f"Grid params cached for {code}")
    
    return result
