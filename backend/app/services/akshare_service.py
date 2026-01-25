import akshare as ak
import pandas as pd
from typing import List, Dict, Optional, Any, cast
import logging
from diskcache import Cache
from datetime import datetime
import os
import time
import threading
import urllib.request
import requests
import json

# 强制禁用代理，防止本地环境代理干扰
urllib.request.getproxies = lambda: {}

# 补丁 requests 增加默认 User-Agent 并彻底禁用代理
_original_session_init = requests.Session.__init__
def _patched_session_init(self, *args, **kwargs):
    _original_session_init(self, *args, **kwargs)
    self.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    self.trust_env = False
    self.proxies = {"http": None, "https": None}
requests.Session.__init__ = _patched_session_init

from app.core.cache import etf_cache

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# DiskCache setup
CACHE_DIR = os.path.join(os.getcwd(), ".cache")
disk_cache = Cache(CACHE_DIR)
ETF_LIST_CACHE_KEY = "etf_list_all"

class AkShareService:
    _refresh_lock = threading.Lock()
    _is_refreshing = False

    @staticmethod
    def load_fallback_data() -> List[Dict]:
        """Load ETF list from local JSON fallback"""
        try:
            json_path = os.path.join(os.getcwd(), "app/data/etf_fallback.json")
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"Loaded {len(data)} ETFs from fallback JSON.")
                    return data
        except Exception as e:
            logger.error(f"Failed to load fallback data: {e}")
        return []

    @staticmethod
    def fetch_all_etfs() -> List[Dict]:
        """获取全市场 ETF 实时行情"""
        # --- Attempt 1: EastMoney ---
        retries = 2
        for i in range(retries):
            try:
                logger.info(f"Fetching ETF spot data from EastMoney (Attempt {i+1}/{retries})...")
                df = ak.fund_etf_spot_em()
                if not df.empty:
                    df = df.rename(columns={
                        "代码": "code",
                        "名称": "name",
                        "最新价": "price",
                        "涨跌幅": "change_pct",
                        "成交额": "volume", 
                    })
                    df["price"] = pd.to_numeric(df["price"], errors="coerce")
                    df["change_pct"] = pd.to_numeric(df["change_pct"], errors="coerce")
                    records = cast(List[Dict[str, Any]], df[["code", "name", "price", "change_pct", "volume"]].to_dict(orient="records"))
                    
                    logger.info(f"Successfully loaded {len(records)} ETFs from EastMoney.")
                    disk_cache.set(ETF_LIST_CACHE_KEY, records, expire=86400)
                    return records
            except Exception as e:
                logger.error(f"EastMoney fetch failed: {e}")
                time.sleep(2)

        # --- Attempt 2: Sina Fallback ---
        logger.warning("EastMoney failed, trying Sina fallback...")
        try:
            sina_categories = ["ETF基金", "QDII基金", "封闭式基金"]
            all_sina_records: List[Dict[str, Any]] = []
            for cat in sina_categories:
                try:
                    logger.info(f"Fetching {cat} from Sina...")
                    df = ak.fund_etf_category_sina(symbol=cat)
                    if df is not None and not df.empty:
                        col_map = {"代码": "code", "名称": "name", "最新价": "price", "涨跌幅": "change_pct", "成交额": "volume"}
                        actual_map = {k: v for k, v in col_map.items() if k in df.columns}
                        df = df.rename(columns=actual_map)
                        
                        if "code" in df.columns:
                            df["code"] = df["code"].astype(str).str.replace("sh", "").str.replace("sz", "")
                            for col in ["price", "change_pct", "volume"]:
                                if col not in df.columns:
                                    df[col] = 0.0
                            
                            subset = cast(List[Dict[str, Any]], df[["code", "name", "price", "change_pct", "volume"]].to_dict(orient="records"))
                            all_sina_records.extend(subset)
                except Exception as cat_e:
                    logger.warning(f"Sina category {cat} failed: {cat_e}")
            
            if all_sina_records:
                seen: set[str] = set()
                deduped: List[Dict[str, Any]] = []
                for r in all_sina_records:
                    if r['code'] not in seen:
                        deduped.append(r)
                        seen.add(r['code'])
                
                logger.info(f"Successfully loaded {len(deduped)} ETFs from Sina.")
                disk_cache.set(ETF_LIST_CACHE_KEY, deduped, expire=86400)
                return deduped
        except Exception as e:
            logger.error(f"Sina fetch failed: {e}")

        # --- Attempt 3: THS Fallback ---
        logger.warning("Sina failed, trying THS fallback...")
        try:
            logger.info("Fetching ETF spot data from THS...")
            df = ak.fund_etf_spot_ths()
            if not df.empty:
                df = df.rename(columns={
                    "基金代码": "code",
                    "基金名称": "name",
                    "当前-单位净值": "price"
                })
                df["change_pct"] = 0.0
                df["volume"] = 0.0
                df["price"] = pd.to_numeric(df["price"], errors="coerce")
                
                records = cast(List[Dict[str, Any]], df[["code", "name", "price", "change_pct", "volume"]].to_dict(orient="records"))
                
                logger.info(f"Successfully loaded {len(records)} ETFs from THS.")
                disk_cache.set(ETF_LIST_CACHE_KEY, records, expire=86400)
                return records
        except Exception as e:
            logger.error(f"THS fetch failed: {e}")

        # --- Attempt 4: Disk Cache ---
        logger.warning("All online fetches failed. Attempting to load from disk cache...")
        cached_list = cast(List[Dict[str, Any]], disk_cache.get(ETF_LIST_CACHE_KEY))
        if cached_list and len(cached_list) > 20:
            logger.info(f"Restored {len(cached_list)} ETFs from disk cache.")
            return cached_list
        
        # --- Attempt 5: Fallback JSON ---
        logger.warning("Disk cache empty or stale. Loading fallback JSON...")
        return AkShareService.load_fallback_data()

    @staticmethod
    def _refresh_task():
        """Background task to refresh ETF list"""
        try:
            with AkShareService._refresh_lock:
                if AkShareService._is_refreshing:
                    return
                AkShareService._is_refreshing = True

            logger.info("Starting background refresh of ETF list...")
            data = AkShareService.fetch_all_etfs()
            if data:
                etf_cache.set_etf_list(data)
                logger.info("Background refresh complete.")
        except Exception as e:
            logger.error(f"Error in background refresh: {e}")
        finally:
            with AkShareService._refresh_lock:
                AkShareService._is_refreshing = False

    @staticmethod
    def get_etf_info(code: str) -> Optional[Dict]:
        """获取单个 ETF 的实时信息（非阻塞）"""
        info = etf_cache.get_etf_info(code)
        
        # Cold start: try loading from disk cache into memory
        if not info and not etf_cache.is_initialized:
            cached_list = disk_cache.get(ETF_LIST_CACHE_KEY)
            if cached_list:
                logger.info("Cold start: Restoring cache from disk.")
                etf_cache.set_etf_list(cast(List[Dict[str, Any]], cached_list))
                info = etf_cache.get_etf_info(code)

        # Trigger refresh if empty or stale
        if not etf_cache.is_initialized or etf_cache.is_stale:
            should_start = False
            with AkShareService._refresh_lock:
                if not AkShareService._is_refreshing:
                    should_start = True
            
            if should_start:
                logger.info("Triggering non-blocking background refresh...")
                t = threading.Thread(target=AkShareService._refresh_task)
                t.daemon = True
                t.start()

        return info

    @staticmethod
    def fetch_history_raw(code: str, period: str, adjust: str) -> pd.DataFrame:
        """历史数据获取 (带 DiskCache)"""
        cache_key = f"hist_{code}_{period}_{adjust}"
        cached_data = disk_cache.get(cache_key)
        if cached_data is not None:
             return cast(pd.DataFrame, cached_data)

        try:
            logger.info(f"Fetching history for {code} adjust={adjust} from AkShare")
            df = ak.fund_etf_hist_em(symbol=code, period=period, adjust=adjust, start_date="20000101", end_date="20500101")
            if df.empty: return pd.DataFrame()

            df = df.rename(columns={"日期": "date", "开盘": "open", "收盘": "close", "最高": "high", "最低": "low", "成交量": "volume"})
            disk_cache.set(cache_key, df, expire=3600)
            return df
        except Exception as e:
            logger.error(f"Error fetching history raw for {code}: {e}")
            return pd.DataFrame()

    @staticmethod
    def get_etf_history(code: str, period: str = "daily", adjust: str = "qfq") -> List[Dict]:
        df_hist = AkShareService.fetch_history_raw(code, period, adjust)
        if df_hist.empty: return []
        realtime_info = AkShareService.get_etf_info(code)
        records = df_hist.to_dict(orient="records")
        if realtime_info and realtime_info.get("price"):
            today_str = datetime.now().strftime("%Y-%m-%d")
            if records:
                last_record = records[-1]
                if last_record["date"] == today_str:
                    last_record["close"] = realtime_info["price"]
                else:
                    records.append({"date": today_str, "open": realtime_info["price"], "close": realtime_info["price"], "high": realtime_info["price"], "low": realtime_info["price"], "volume": 0})
        return records

ak_service = AkShareService()
