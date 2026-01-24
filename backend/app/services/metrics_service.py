import pandas as pd
import logging
import threading
from typing import Dict, Optional, Tuple
from datetime import datetime

from app.services.akshare_service import disk_cache, ak_service
from app.core.config_loader import metric_config

logger = logging.getLogger(__name__)

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
