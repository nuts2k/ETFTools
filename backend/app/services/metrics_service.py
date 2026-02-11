import numpy as np
import pandas as pd
import logging
import threading
from typing import Dict, Optional, Tuple
from datetime import datetime

from app.services.akshare_service import disk_cache, ak_service
from app.core.config_loader import metric_config

logger = logging.getLogger(__name__)


def calculate_period_metrics(closes: pd.Series) -> Dict:
    """基于对齐后的收盘价序列计算核心指标（纯函数，不含数据获取）

    Args:
        closes: 带 DatetimeIndex 的 close 价格 Series，至少 2 个数据点

    Returns:
        包含 cagr, total_return, actual_years, max_drawdown, mdd_date,
        mdd_start, mdd_trough, mdd_end, volatility, risk_level 的字典
    """
    if len(closes) < 2:
        first_date = closes.index[0].strftime("%Y-%m-%d") if len(closes) == 1 else ""
        return {
            "total_return": 0.0, "cagr": 0.0, "actual_years": 0.0,
            "max_drawdown": 0.0, "mdd_date": first_date,
            "mdd_start": first_date, "mdd_trough": first_date, "mdd_end": None,
            "volatility": 0.0, "risk_level": "Low",
        }

    # CAGR
    actual_days = (closes.index[-1] - closes.index[0]).days
    actual_years = actual_days / 365.25
    total_return = (closes.iloc[-1] / closes.iloc[0]) - 1

    cagr = 0.0
    if actual_years > 0 and closes.iloc[0] > 0:
        cagr = (closes.iloc[-1] / closes.iloc[0]) ** (1 / actual_years) - 1

    # Max Drawdown
    rolling_max = closes.cummax()
    drawdown = (closes - rolling_max) / rolling_max
    max_drawdown = drawdown.min()

    trough_idx = drawdown.idxmin()
    mdd_trough = trough_idx.strftime("%Y-%m-%d")

    data_upto_trough = closes.loc[:trough_idx]
    peak_price = rolling_max.loc[:trough_idx].iloc[-1]
    peak_idx = data_upto_trough[data_upto_trough >= peak_price].index[-1]
    mdd_start = peak_idx.strftime("%Y-%m-%d")

    data_after_trough = closes.loc[trough_idx:].iloc[1:]
    mdd_end = None
    if not data_after_trough.empty:
        recovered = data_after_trough[data_after_trough >= peak_price]
        if not recovered.empty:
            mdd_end = recovered.index[0].strftime("%Y-%m-%d")

    # Volatility (Annualized)
    daily_returns = closes.pct_change().dropna()
    volatility = float(daily_returns.std() * np.sqrt(252))

    return {
        "total_return": round(float(total_return), 4),
        "cagr": round(float(cagr), 4),
        "actual_years": round(actual_years, 4),
        "max_drawdown": round(float(max_drawdown), 4),
        "mdd_date": mdd_trough,
        "mdd_start": mdd_start,
        "mdd_trough": mdd_trough,
        "mdd_end": mdd_end,
        "volatility": round(volatility, 4),
        "risk_level": "High" if volatility > 0.25 else ("Medium" if volatility > 0.15 else "Low"),
    }


class MetricsService:
    def __init__(self):
        self._fetching_codes = set()
        self._lock = threading.Lock()

    def _async_fetch_history(self, code: str):
        """Background task to fetch and cache history metrics base data"""
        with self._lock:
            if code in self._fetching_codes:
                return
            self._fetching_codes.add(code)
        
        try:
            logger.info(f"Background fetching history base for {code}...")
            # This will populate the cache inside fetch_history_raw
            self._get_history_base_data(code, force_sync=True)
            logger.info(f"Background history fetch complete for {code}.")
        except Exception as e:
            logger.error(f"Error in async history fetch for {code}: {e}")
        finally:
            with self._lock:
                self._fetching_codes.remove(code)

    def _get_history_base_data(self, code: str, force_sync: bool = False) -> Optional[Dict]:
        """Get cached base data. If missing and not force_sync, trigger async fetch."""
        dd_days = metric_config.drawdown_days
        atr_period = metric_config.atr_period
        cache_key = f"metrics_base_{code}_{dd_days}_{atr_period}"
        
        cached = disk_cache.get(cache_key)
        if cached:
            return cached

        if not force_sync:
            # Trigger background fetch and return None immediately
            t = threading.Thread(target=self._async_fetch_history, args=(code,))
            t.daemon = True
            t.start()
            return None

        # Actual synchronous fetch (only for background threads or explicit calls)
        df = ak_service.fetch_history_raw(code, period="daily", adjust="qfq")
        if df.empty or len(df) < 2:
            return None

        # Drawdown History Window
        start_idx = -(dd_days) 
        if abs(start_idx) > len(df): start_idx = 0
        hist_window = df.iloc[start_idx:]
        hist_peak_price = float(hist_window["close"].max()) if not hist_window.empty else 0.0
        
        # ATR Calculation
        atr_val = None
        if len(df) > atr_period:
            prev_close = df["close"].shift(1)
            tr = pd.concat([df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()], axis=1).max(axis=1)
            atr_series = tr.rolling(window=atr_period).mean()
            if not pd.isna(atr_series.iloc[-1]):
                atr_val = float(atr_series.iloc[-1])

        result = {
            "hist_peak_price": hist_peak_price,
            "prev_atr": atr_val,
            "last_date": df.iloc[-1]["date"]
        }
        disk_cache.set(cache_key, result, expire=14400) # 4 hours
        return result

    def get_realtime_metrics_lite(self, code: str, current_price: float, current_change_pct: float) -> Dict:
        """Fast calculation using cached or async-fetched history base data"""
        base_data = self._get_history_base_data(code)
        
        atr = None
        drawdown = None
        
        if base_data:
            atr = base_data.get("prev_atr")
            hist_peak = base_data.get("hist_peak_price", 0.0)
            peak = max(hist_peak, current_price)
            drawdown = (current_price - peak) / peak if peak > 0 else 0.0
                
        return {
            "atr": round(atr, 4) if atr is not None else None,
            "current_drawdown": round(drawdown, 4) if drawdown is not None else None
        }

metrics_service = MetricsService()
