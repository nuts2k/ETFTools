import pandas as pd
import numpy as np
from typing import Dict, Any

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
    
    # 使用分位数计算上下界（简化版本，后续可用 ATR 优化）
    upper = recent_df['close'].quantile(0.95)
    lower = recent_df['close'].quantile(0.05)
    current_price = recent_df['close'].iloc[-1]
    
    # 网格间距百分比（简化为固定值）
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
    
    return {
        "upper": round(upper, 3),
        "lower": round(lower, 3),
        "spacing_pct": spacing_pct * 100,
        "grid_count": count,
        "range_start": recent_df['date'].iloc[0].strftime("%Y-%m-%d") if 'date' in recent_df.columns else "",
        "range_end": recent_df['date'].iloc[-1].strftime("%Y-%m-%d") if 'date' in recent_df.columns else "",
        "is_out_of_range": current_price > upper * 1.05 or current_price < lower * 0.95
    }
