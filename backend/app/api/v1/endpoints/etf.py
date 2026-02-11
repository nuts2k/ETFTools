from fastapi import APIRouter, HTTPException, Query, Request
from typing import List, Dict, Optional
import numpy as np
import pandas as pd
from datetime import datetime, time
from zoneinfo import ZoneInfo
import logging
import re

from app.core.cache import etf_cache
from app.services.akshare_service import ak_service
from app.services.valuation_service import valuation_service
from app.services.etf_classifier import ETFClassifier
from app.services.trend_cache_service import trend_cache_service
from app.services.temperature_cache_service import temperature_cache_service
from app.services.grid_service import calculate_grid_params_cached
from app.services.fund_flow_cache_service import fund_flow_cache_service
from app.core.config_loader import metric_config
from app.middleware.rate_limit import limiter

router = APIRouter()
logger = logging.getLogger(__name__)

def get_market_status() -> str:
    """
    判断当前是否为交易时间 (A股)
    交易时间: 周一至周五 9:15-11:30, 13:00-15:00

    注意: 使用中国时区 (Asia/Shanghai) 判断，无论服务器部署在哪个时区
    """
    # 使用中国时区获取当前时间
    now = datetime.now(ZoneInfo("Asia/Shanghai"))

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
@limiter.limit("30/minute")  # 限制搜索频率
async def search_etf(
    request: Request,
    q: str = Query(..., min_length=1, description="ETF代码或名称关键字")
):
    """
    搜索 ETF
    """
    return etf_cache.search(q)

@router.get("/batch-price")
@limiter.limit("120/minute")
async def get_batch_price(
    request: Request,
    codes: str = Query(..., description="逗号分隔的 ETF 代码列表，如 510300,510500")
):
    """
    批量获取 ETF 实时价格（轻量级，仅从内存缓存读取）
    """
    ETF_CODE_RE = re.compile(r"^\d{6}$")
    code_list = [c.strip() for c in codes.split(",") if c.strip()]
    if not code_list or len(code_list) > 50:
        raise HTTPException(status_code=400, detail="codes 参数无效或超过 50 个")
    code_list = [c for c in code_list if ETF_CODE_RE.match(c)]
    if not code_list:
        raise HTTPException(status_code=400, detail="无有效的 ETF 代码（需为6位数字）")

    items = []
    for code in code_list:
        info = etf_cache.etf_map.get(code)
        if info:
            items.append({
                "code": info.get("code", code),
                "name": info.get("name", ""),
                "price": info.get("price", 0),
                "change_pct": info.get("change_pct", 0),
                "tags": info.get("tags", []),
            })

    # 添加更新时间（中国时区），确保前端显示一致
    update_time = datetime.fromtimestamp(
        etf_cache.last_updated,
        tz=ZoneInfo("Asia/Shanghai")
    ).strftime("%Y-%m-%d %H:%M:%S")

    return {
        "items": items,
        "market_status": get_market_status(),
        "update_time": update_time,
    }


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
    # 使用中国时区，确保无论服务器部署在哪里，都显示北京时间
    info["update_time"] = datetime.fromtimestamp(
        etf_cache.last_updated,
        tz=ZoneInfo("Asia/Shanghai")
    ).strftime("%Y-%m-%d %H:%M:%S")
    
    # 补充 market (交易状态)
    info["market"] = get_market_status()

    # 补充 tags（优先从缓存读取，缓存无则实时分类）
    info["tags"] = info.get("tags", [])
    if not info["tags"]:
        classifier = ETFClassifier()
        tags = classifier.classify(info.get("name", ""), code)
        info["tags"] = [t.to_dict() for t in tags]

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
async def get_etf_metrics(code: str, period: str = "5y", force_refresh: bool = False):
    """
    计算核心指标: CAGR, MaxDrawdown, Volatility
    默认基于 daily, qfq 数据
    
    Args:
        code: ETF 代码
        period: 计算周期 (1y, 3y, 5y, all)
        force_refresh: 强制刷新缓存
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
    # 此功能暂时关闭，如需开启请参考 AGENTS.md
    valuation_data = None
    # try:
    #     valuation_data = valuation_service.get_valuation(code)
    # except Exception as e:
    #     # log but don't fail
    #     pass

    # --- New Metrics Calculation (ATR & Current Drawdown) ---
    atr_val = None
    current_drawdown = None
    current_drawdown_peak_date = None
    days_since_peak = 0
    effective_drawdown_days = 0
    
    # ATR Calculation
    atr_period = metric_config.atr_period
    # Need enough data for rolling window
    if len(df) > atr_period + 1:
        # Calculate True Range (TR)
        # TR = Max(High-Low, |High-PrevClose|, |Low-PrevClose|)
        # We need to shift close to get PrevClose
        prev_close = df["close"].shift(1)
        high = df["high"]
        low = df["low"]
        close = df["close"]
        
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        # Simple Moving Average for ATR
        atr_series = tr.rolling(window=atr_period).mean()
        # Get the latest ATR (from the last row)
        if not pd.isna(atr_series.iloc[-1]):
             atr_val = float(atr_series.iloc[-1])

    # Drawdown from N-day Peak (Configurable)
    # 峰值计算：历史收盘价窗口 + 当天实时价
    dd_days = metric_config.drawdown_days

    if len(df) >= 2:
        current_price = float(df.iloc[-1]["close"])
        current_date = df.index[-1]
        
        # Determine actual history window size available
        # len(df) includes today. History pool is previous rows.
        # Max lookback is dd_days.
        # Available history length = len(df) - 1
        available_history_len = len(df) - 1
        
        if available_history_len <= dd_days:
            # Data is shorter than config window -> Use all available history
            # This is "since inception" effectively relative to the loaded data
            start_idx = 0 
            effective_drawdown_days = available_history_len
        else:
            # Data is sufficient -> Use config window
            start_idx = -(dd_days + 1)
            effective_drawdown_days = dd_days
            
        # The pool for history peak calculation (exclude last row which is current)
        history_window = df.iloc[start_idx:-1]
        
        peak_price = 0.0
        peak_date = None

        if not history_window.empty:
            hist_peak = float(history_window["close"].max())
            hist_peak_idx = history_window["close"].idxmax()
            
            # Compare history peak with current price
            if current_price >= hist_peak:
                # New High (Real-time)
                peak_price = current_price
                peak_date = current_date
            else:
                # History Peak is higher
                peak_price = hist_peak
                peak_date = hist_peak_idx
        else:
            # Not enough history (e.g. only current point if we logic-ed wrong, 
            # but len>=2 ensures at least 1 history point).
            # Fallback for safety.
            peak_price = current_price
            peak_date = current_date

        # Calculate metrics
        if peak_date:
            current_drawdown_peak_date = peak_date.strftime("%Y-%m-%d")
            days_since_peak = (current_date - peak_date).days

        if peak_price > 0:
            current_drawdown = (current_price - peak_price) / peak_price
        else:
            current_drawdown = 0.0

    # --- Trend and Temperature Analysis ---
    # 准备用于趋势分析的 DataFrame（需要 date 和 close 列）
    df_for_trend = df.reset_index()  # 将 date 从索引恢复为列
    
    # 日趋势分析（使用缓存服务）
    daily_trend = trend_cache_service.get_daily_trend(
        code, df_for_trend, realtime_price=None, force_refresh=force_refresh
    )
    
    # 周趋势分析（使用缓存服务）
    weekly_trend = trend_cache_service.get_weekly_trend(
        code, df_for_trend, force_refresh=force_refresh
    )
    
    # 市场温度计算（使用缓存服务）
    temperature = temperature_cache_service.calculate_temperature(
        code, df_for_trend, realtime_price=None, force_refresh=force_refresh
    )

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
        "valuation": valuation_data,
        "atr": round(atr_val, 4) if atr_val is not None else None,
        "current_drawdown": round(current_drawdown, 4) if current_drawdown is not None else None,
        "drawdown_days": dd_days,
        "effective_drawdown_days": effective_drawdown_days,
        "current_drawdown_peak_date": current_drawdown_peak_date,
        "days_since_peak": days_since_peak,
        "daily_trend": daily_trend,
        "weekly_trend": weekly_trend,
        "temperature": temperature
    }


@router.get("/{code}/grid-suggestion")
async def get_grid_suggestion(code: str, force_refresh: bool = False):
    """
    获取网格交易建议参数
    
    基于历史波动率（ATR）计算适合震荡行情的网格交易参数
    
    Args:
        code: ETF 代码
        force_refresh: 是否强制刷新缓存（默认 False）
        
    Returns:
        网格参数，包含上下界、间距、网格数量等
    """
    import time
    start_time = time.time()
    
    # 使用缓存版本的计算函数
    result = calculate_grid_params_cached(code, force_refresh=force_refresh)
    
    elapsed = time.time() - start_time
    is_cached = elapsed < 0.1  # 如果响应时间小于 100ms，认为是缓存命中
    
    logger.info(
        f"Grid suggestion for {code}: {elapsed:.3f}s "
        f"(cached: {is_cached}, force_refresh: {force_refresh})"
    )
    
    if not result:
        raise HTTPException(status_code=400, detail="Insufficient data for grid calculation")

    return result


@router.get("/{code}/fund-flow")
async def get_fund_flow(code: str, force_refresh: bool = False):
    """获取 ETF 资金流向数据（份额规模、排名）"""
    result = fund_flow_cache_service.get_fund_flow(code, force_refresh=force_refresh)
    if not result:
        raise HTTPException(
            status_code=404,
            detail="No fund flow data available for this ETF"
        )
    return result
