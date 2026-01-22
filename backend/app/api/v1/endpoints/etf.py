from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Optional
import numpy as np
import pandas as pd
from datetime import datetime

from app.core.cache import etf_cache
from app.services.akshare_service import ak_service

router = APIRouter()

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
    
    # 补充 update_time (近似值，即缓存最后更新时间)
    info["update_time"] = datetime.fromtimestamp(etf_cache.last_updated).strftime("%Y-%m-%d %H:%M:%S")
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
    # 5y = 最近5年
    end_date = df.index[-1]
    start_date = end_date - pd.DateOffset(years=5)
    
    # 如果数据不足5年，就用全部数据
    if start_date < df.index[0]:
        start_date = df.index[0]
        
    df_period = df.loc[start_date:end_date]
    
    if df_period.empty:
         raise HTTPException(status_code=404, detail="Not enough data for metrics")

    # 3. 计算指标
    closes = df_period["close"]
    
    # CAGR
    # 年数 = (end - start).days / 365.25
    days = (end_date - start_date).days
    years = days / 365.25
    total_return = (closes.iloc[-1] / closes.iloc[0]) - 1
    
    cagr = 0.0
    if years > 0 and closes.iloc[0] > 0:
        cagr = (closes.iloc[-1] / closes.iloc[0]) ** (1 / years) - 1

    # Max Drawdown
    # 累计最大值
    rolling_max = closes.cummax()
    drawdown = (closes - rolling_max) / rolling_max
    max_drawdown = drawdown.min()
    
    # Max Drawdown Date
    mdd_date = drawdown.idxmin().strftime("%Y-%m-%d")
    
    # Volatility (Annualized)
    # 日收益率标准差 * sqrt(252)
    daily_returns = closes.pct_change().dropna()
    volatility = daily_returns.std() * np.sqrt(252)
    
    return {
        "period": f"{start_date.date()} to {end_date.date()}",
        "total_return": round(total_return, 4),
        "cagr": round(cagr, 4),
        "max_drawdown": round(max_drawdown, 4),
        "mdd_date": mdd_date,
        "volatility": round(volatility, 4),
        "risk_level": "High" if volatility > 0.25 else ("Medium" if volatility > 0.15 else "Low")
    }
