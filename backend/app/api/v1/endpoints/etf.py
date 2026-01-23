from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Optional
import numpy as np
import pandas as pd
from datetime import datetime, time

from app.core.cache import etf_cache
from app.services.akshare_service import ak_service
from app.services.valuation_service import valuation_service

router = APIRouter()

def get_market_status() -> str:
    """
    判断当前是否为交易时间 (A股)
    交易时间: 周一至周五 9:15-11:30, 13:00-15:00
    """
    now = datetime.now()
    
    # 周末
    if now.weekday() >= 5:
        return "已收盘"
        
    current_time = now.time()
    
    # 9:15 - 11:30
    if time(9, 15) <= current_time <= time(11, 30):
        return "交易中"
        
    # 13:00 - 15:00
    if time(13, 0) <= current_time <= time(15, 0):
        return "交易中"
        
    return "已收盘"

@router.get("/search", response_model=List[Dict])
async def search_etf(q: str = Query(..., min_length=1, description="ETF代码或名称关键字")):
    """
    搜索 ETF
    """
    return etf_cache.search(q)

@router.get("/{code}/info")
async def get_etf_info(code: str):
    """
    获取 ETF 实时基础信息
    """
    info = ak_service.get_etf_info(code)
    if not info:
        raise HTTPException(status_code=404, detail="ETF not found")
    
    # Create a copy to avoid modifying the cache directly
    info = info.copy()
    
    # 补充 update_time (近似值，即缓存最后更新时间)
    info["update_time"] = datetime.fromtimestamp(etf_cache.last_updated).strftime("%Y-%m-%d %H:%M:%S")
    
    # 补充 market (交易状态)
    info["market"] = get_market_status()
    
    return info

@router.get("/{code}/history")
async def get_etf_history(code: str, period: str = "daily", adjust: str = "qfq"):
    """
    获取 ETF 历史行情 (包含实时点拼接)
    """
    data = ak_service.get_etf_history(code, period, adjust)
    if not data:
        raise HTTPException(status_code=404, detail="History data not found")
    return data

@router.get("/{code}/metrics")
async def get_etf_metrics(code: str, period: str = "5y"):
    """
    计算核心指标: CAGR, MaxDrawdown, Volatility
    默认基于 daily, qfq 数据
    """
    # 1. 获取全量历史数据
    history = ak_service.get_etf_history(code, period="daily", adjust="qfq")
    if not history:
        raise HTTPException(status_code=404, detail="Data not found for metrics")
    
    df = pd.DataFrame(history)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    
    # 2. 根据 period 筛选数据
    end_date = df.index[-1]
    
    if period == "1y":
        start_date = end_date - pd.DateOffset(years=1)
    elif period == "3y":
        start_date = end_date - pd.DateOffset(years=3)
    elif period == "5y":
        start_date = end_date - pd.DateOffset(years=5)
    else:
        # "all" or default fallback
        start_date = df.index[0]
    
    # 如果数据不足或者 start_date 早于数据起点，就用全部数据
    if start_date < df.index[0]:
        start_date = df.index[0]
        
    df_period = df.loc[start_date:end_date]
    
    # 边界情况处理：数据点不足
    if len(df_period) < 2:
        if df_period.empty:
            raise HTTPException(status_code=404, detail="Not enough data for metrics")
        
        # 如果只有1个数据点，返回零值指标，避免前端崩溃
        single_date = df_period.index[0].strftime("%Y-%m-%d")
        return {
            "period": f"{single_date} to {single_date}",
            "total_return": 0.0,
            "cagr": 0.0,
            "actual_years": 0.0,
            "max_drawdown": 0.0,
            "mdd_date": single_date,
            "mdd_start": single_date,
            "mdd_trough": single_date,
            "mdd_end": None,
            "volatility": 0.0,
            "risk_level": "Low"
        }

    # 3. 计算指标
    closes = df_period["close"]
    
    # CAGR
    # 使用实际数据范围计算年数，解决历史数据不足选定时间段的问题
    actual_start_date = df_period.index[0]
    actual_end_date = df_period.index[-1]
    actual_days = (actual_end_date - actual_start_date).days
    actual_years = actual_days / 365.25
    
    total_return = (closes.iloc[-1] / closes.iloc[0]) - 1
    
    cagr = 0.0
    if actual_years > 0 and closes.iloc[0] > 0:
        cagr = (closes.iloc[-1] / closes.iloc[0]) ** (1 / actual_years) - 1

    # Max Drawdown
    # 累计最大值
    rolling_max = closes.cummax()
    drawdown = (closes - rolling_max) / rolling_max
    max_drawdown = drawdown.min()
    
    # 1. Trough Date (mdd_trough): date of max drawdown
    trough_idx = drawdown.idxmin()
    mdd_trough = trough_idx.strftime("%Y-%m-%d")
    
    # 2. Peak Date (mdd_start): last time price was at rolling_max before trough
    # We look at data up to trough
    data_upto_trough = closes.loc[:trough_idx]
    rolling_max_upto_trough = rolling_max.loc[:trough_idx]
    
    # The peak price is the rolling_max at the trough date
    peak_price = rolling_max_upto_trough.iloc[-1]
    
    # Find the last date where price >= peak_price (before or on trough date)
    # Actually, strictly speaking, it's where price == peak_price
    # Because peak_price comes from rolling_max, there must be at least one point where close == peak_price
    peak_idx = data_upto_trough[data_upto_trough >= peak_price].index[-1]
    mdd_start = peak_idx.strftime("%Y-%m-%d")
    
    # 3. Recovery Date (mdd_end): first time price >= peak_price after trough
    data_after_trough = closes.loc[trough_idx:]
    # drop the first point (trough itself) to avoid matching if trough == peak (impossible for drawdown < 0)
    data_after_trough = data_after_trough.iloc[1:]
    
    mdd_end = None
    if not data_after_trough.empty:
        recovered = data_after_trough[data_after_trough >= peak_price]
        if not recovered.empty:
            mdd_end = recovered.index[0].strftime("%Y-%m-%d")
    
    # Volatility (Annualized)
    # 日收益率标准差 * sqrt(252)
    daily_returns = closes.pct_change().dropna()
    volatility = daily_returns.std() * np.sqrt(252)
    
    # 获取估值数据 (非阻塞或独立获取，不因估值失败影响指标)
    # 此功能暂时关闭，如需开启请参考 AGENT.md
    valuation_data = None
    # try:
    #     valuation_data = valuation_service.get_valuation(code)
    # except Exception as e:
    #     # log but don't fail
    #     pass

    return {
        "period": f"{actual_start_date.date()} to {actual_end_date.date()}",
        "total_return": round(total_return, 4),
        "cagr": round(cagr, 4),
        "actual_years": round(actual_years, 4),
        "max_drawdown": round(max_drawdown, 4),
        "mdd_date": mdd_trough, # Keep backward compatibility
        "mdd_start": mdd_start,
        "mdd_trough": mdd_trough,
        "mdd_end": mdd_end,
        "volatility": round(volatility, 4),
        "risk_level": "High" if volatility > 0.25 else ("Medium" if volatility > 0.15 else "Low"),
        "valuation": valuation_data
    }
