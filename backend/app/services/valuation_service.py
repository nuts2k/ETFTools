import akshare as ak
import pandas as pd
import logging
import json
import os
import re
from typing import Optional, Dict
import urllib.request

# 强制禁用代理
urllib.request.getproxies = lambda: {}

# Reuse the cache instance from akshare_service to avoid lock contention
from app.services.akshare_service import disk_cache as valuation_cache

logger = logging.getLogger(__name__)

# CACHE_DIR = os.path.join(os.getcwd(), ".cache")
# valuation_cache = Cache(CACHE_DIR)

class ValuationService:
    def __init__(self):
        # Resolve absolute path to data file
        # __file__ is .../backend/app/services/valuation_service.py
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.map_file = os.path.join(base_dir, "data", "etf_index_map.json")
        self.mapping = self._load_mapping()

    def _load_mapping(self) -> Dict[str, str]:
        # Robust path handling
        paths_to_try = [
            self.map_file,
            os.path.join(os.getcwd(), "backend/app/data/etf_index_map.json"),
            os.path.join(os.getcwd(), "app/data/etf_index_map.json")
        ]
        
        final_path = None
        for p in paths_to_try:
            if os.path.exists(p):
                final_path = p
                break
        
        if not final_path:
            logger.warning(f"ETF-Index mapping file not found. Tried: {paths_to_try}")
            return {}
            
        try:
            with open(final_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"Loaded {len(data)} ETF-Index mappings from {final_path}")
                return data
        except Exception as e:
            logger.error(f"Failed to load ETF-Index mapping: {e}")
            return {}

    def get_valuation(self, etf_code: str) -> Optional[Dict]:
        """
        Get valuation data for an ETF.
        """
        # Lazy reload if empty (e.g. init failed)
        if not self.mapping:
            logger.info("Mapping empty, attempting lazy reload...")
            self.mapping = self._load_mapping()

        index_code_full = self.mapping.get(etf_code)
        if not index_code_full:
            logger.info(f"No mapping found for ETF {etf_code}")
            return None
        
        # Skip HK/US indices for now as CSIndex only covers China A-share indices
        if "HK" in index_code_full or "US" in index_code_full:
            return None
            
        clean_code = re.sub(r"[^0-9]", "", index_code_full)
        if not clean_code:
            return None

        # Try cache
        cache_key = f"valuation_{clean_code}"
        cached = valuation_cache.get(cache_key)
        if cached:
            logger.info(f"Valuation cache hit for {clean_code}")
            return cached
            
        # Fetch from AkShare
        try:
            logger.info(f"Fetching valuation for {clean_code} from CSIndex...")
            df = ak.stock_zh_index_value_csindex(symbol=clean_code)
            
            if df.empty:
                logger.warning(f"No valuation data for {clean_code} (Empty DataFrame)")
                valuation_cache.set(cache_key, None, expire=300) 
                return None
                
            # Process Data
            # Expected columns: '日期', '指数代码', '指数中文全称', '指数中文简称', '市盈率1', '市盈率2', '股息率1', '股息率2'
            if '市盈率1' not in df.columns:
                 logger.warning(f"Missing PE column for {clean_code}. Columns: {df.columns}")
                 return None

            df['date'] = pd.to_datetime(df['日期'])
            df = df.sort_values('date')
            
            # Use '市盈率1' (PE-TTM)
            df['pe'] = pd.to_numeric(df['市盈率1'], errors='coerce')
            df = df.dropna(subset=['pe'])
            
            if df.empty:
                logger.warning(f"No valid PE data for {clean_code}")
                return None
                
            # Calculate Metrics
            current_record = df.iloc[-1]
            current_pe = current_record['pe']
            current_date = current_record['date'].strftime("%Y-%m-%d")
            index_name = current_record.get('指数中文简称', clean_code)
            
            # History Stats
            start_date = df['date'].iloc[0].strftime("%Y-%m-%d")
            duration_days = (df['date'].iloc[-1] - df['date'].iloc[0]).days
            duration_years = round(duration_days / 365.25, 2)

            # Percentile Calculation
            total_count = len(df)
            if total_count > 0:
                below_count = (df['pe'] < current_pe).sum()
                percentile = (below_count / total_count) * 100
            else:
                percentile = 0.0
            
            # Valuation Label
            if duration_years < 1.0:
                 view = "参考(短期)"
            elif percentile < 30:
                view = "低估"
            elif percentile > 70:
                view = "高估"
            else:
                view = "适中"
                
            result = {
                "pe": round(float(current_pe), 2),
                "pe_percentile": round(float(percentile), 2),
                "dist_view": view,
                "index_code": clean_code,
                "index_name": str(index_name),
                "data_date": current_date,
                "history_start": start_date,
                "history_years": duration_years
            }
            
            logger.info(f"Valuation success for {clean_code}: PE={current_pe}, Percentile={percentile}")
            
            # Cache success
            valuation_cache.set(cache_key, result, expire=43200)
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching valuation for {clean_code}: {e}")
            valuation_cache.set(cache_key, None, expire=300)
            return None

valuation_service = ValuationService()
