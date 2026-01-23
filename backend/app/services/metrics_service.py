import pandas as pd
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime

from app.services.akshare_service import disk_cache, ak_service
from app.core.config_loader import metric_config

logger = logging.getLogger(__name__)

class MetricsService:
    def __init__(self):
        # Cache for "Heavy" history calculations (Peak Price, TR sum)
        # Key: "metrics_base_{code}_{days}"
        pass

    def _get_history_base_data(self, code: str) -> Optional[Dict]:
        """
        Get cached base data for metrics calculation.
        Base data includes:
        - 120-day historical peak (excluding today)
        - ATR components (TR history)
        
        This data is cached for a longer duration (e.g. 1 hour or until EOD)
        because historical daily data (OHLC) doesn't change during the day 
        (except for the current forming bar which we handle in real-time).
        """
        # Configs
        dd_days = metric_config.drawdown_days
        atr_period = metric_config.atr_period
        
        cache_key = f"metrics_base_{code}_{dd_days}_{atr_period}"
        cached = disk_cache.get(cache_key)
        
        if cached:
            return cached

        # Fetch history (reuse service logic which has its own cache)
        # We need enough history for 120 days + ATR
        # Fetching 'daily' period
        df = ak_service.fetch_history_raw(code, period="daily", adjust="qfq")
        
        if df.empty or len(df) < 2:
            return None

        # --- Calculate 120-day Peak (History Only) ---
        # Exclude today/latest if it's potentially incomplete?
        # fetch_history_raw returns historical closed candles usually. 
        # But if it includes today's partial candle, we should be careful.
        # For simplicity, we treat the entire DF as "history context".
        
        # Drawdown History Window
        start_idx = -(dd_days) 
        if abs(start_idx) > len(df):
            start_idx = 0
            
        hist_window = df.iloc[start_idx:]
        hist_peak_price = float(hist_window["close"].max()) if not hist_window.empty else 0.0
        
        # --- Calculate ATR Base (Last N days TR) ---
        # To calculate real-time ATR, we need the rolling mean of TR.
        # Real-time ATR ~ ((Prior ATR * (n-1)) + Current TR) / n
        # Or simpler: just get the TR series and we'll append today's TR in real-time.
        
        atr_val = None
        if len(df) > atr_period:
            prev_close = df["close"].shift(1)
            high = df["high"]
            low = df["low"]
            
            tr1 = high - low
            tr2 = (high - prev_close).abs()
            tr3 = (low - prev_close).abs()
            
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            # We store the last ATR value from history to help smooth today's value
            # OR we just pre-calculate ATR from history and return it as "Yesterday's ATR"
            # For list view, Yesterday's ATR is often close enough, or we refine it slightly.
            # Let's simple use the latest full-day ATR.
            atr_series = tr.rolling(window=atr_period).mean()
            if not pd.isna(atr_series.iloc[-1]):
                atr_val = float(atr_series.iloc[-1])

        result = {
            "hist_peak_price": hist_peak_price,
            "prev_atr": atr_val,
            "last_date": df.iloc[-1]["date"] # To check if we need to merge today
        }
        
        # Cache for 4 hours (during trading day, history doesn't change, only today's bar)
        disk_cache.set(cache_key, result, expire=14400)
        return result

    def get_realtime_metrics_lite(self, code: str, current_price: float, current_change_pct: float) -> Dict:
        """
        Fast, lightweight calculation for lists.
        Combines cached history base data with real-time price.
        """
        base_data = self._get_history_base_data(code)
        
        atr = None
        drawdown = None
        
        if base_data:
            # 1. ATR (Use cached value for list view performance)
            # In a detailed view we might recalculate with today's High/Low.
            # For watchlist, the previous close ATR is sufficient proxy.
            atr = base_data.get("prev_atr")

            # 2. Drawdown (Real-time synthesis)
            # Compare current price with history peak
            hist_peak = base_data.get("hist_peak_price", 0.0)
            
            peak = max(hist_peak, current_price)
            
            if peak > 0:
                drawdown = (current_price - peak) / peak
            else:
                drawdown = 0.0
                
        return {
            "atr": round(atr, 4) if atr is not None else None,
            "current_drawdown": round(drawdown, 4) if drawdown is not None else None
        }

metrics_service = MetricsService()
