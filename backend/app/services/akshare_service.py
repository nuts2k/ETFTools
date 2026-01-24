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

# 强制禁用代理，防止本地环境代理干扰
urllib.request.getproxies = lambda: {}

# 补丁 requests 增加默认 User-Agent 并彻底禁用代理
import requests
_original_session_init = requests.Session.__init__
def _patched_session_init(self, *args, **kwargs):
    _original_session_init(self, *args, **kwargs)
    self.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    # 强制禁用系统代理环境变量，防止 transparent proxy 干扰
    self.trust_env = False
    self.proxies = {"http": None, "https": None}
requests.Session.__init__ = _patched_session_init

from app.core.cache import etf_cache

import json

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
        """
        获取全市场 ETF 实时行情（用于构建基础列表）
        策略：优先使用东方财富(EM)，失败则尝试新浪(Sina)
        """
        # --- Attempt 1: EastMoney ---
        retries = 2
        for i in range(retries):
            try:
                logger.info(f"Fetching ETF spot data from EastMoney (Attempt {i+1}/{retries})...")
                df = ak.fund_etf_spot_em()
                if not df.empty:
                    # 字段映射
                    df = df.rename(columns={
                        "代码": "code",
                        "名称": "name",
                        "最新价": "price",
                        "涨跌幅": "change_pct",
                        "成交额": "volume", 
                    })
                    df["price"] = pd.to_numeric(df["price"], errors="coerce")
                    df["change_pct"] = pd.to_numeric(df["change_pct"], errors="coerce")
                    records = cast(List[Dict[str, Any]], df[["code", "name", "price", "change_pct", "volume"]].to_dict(orient="records"))  # type: ignore
                    
                    logger.info(f"Successfully loaded {len(records)} ETFs from EastMoney.")
                    disk_cache.set(ETF_LIST_CACHE_KEY, records, expire=86400)
                    return records
            except Exception as e:
                logger.error(f"EastMoney fetch failed: {e}")
                time.sleep(2)

        # --- Attempt 2: Sina Fallback ---
        logger.warning("EastMoney failed, trying Sina fallback...")
        try:
            # Sina category map: symbol -> record filter/mapper
            sina_categories = ["ETF基金", "QDII基金", "封闭式基金"]
            all_sina_records = []
            for cat in sina_categories:
                try:
                    logger.info(f"Fetching {cat} from Sina...")
                    df = ak.fund_etf_category_sina(symbol=cat)
                    if df is not None and not df.empty:
                        # Normalize columns
                        col_map = {"代码": "code", "名称": "name", "最新价": "price", "涨跌幅": "change_pct", "成交额": "volume"}
                        # Only rename columns that exist
                        actual_map = {k: v for k, v in col_map.items() if k in df.columns}
                        df = df.rename(columns=actual_map)
                        
                        if "code" in df.columns:
                            df["code"] = df["code"].astype(str).str.replace("sh", "").str.replace("sz", "")
                            # Fill missing required columns with defaults if necessary
                            for col in ["price", "change_pct", "volume"]:
                                if col not in df.columns:
                                    df[col] = 0.0
                            
                            subset = cast(List[Dict[str, Any]], df[["code", "name", "price", "change_pct", "volume"]].to_dict(orient="records"))  # type: ignore
                            all_sina_records.extend(subset)
                except Exception as cat_e:
                    logger.warning(f"Sina category {cat} failed: {cat_e}")
            
            if all_sina_records:
                # Dedup by code
                seen = set()
                deduped = []
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
                # 字段映射
                # 序号, 基金代码, 基金名称, 当前-单位净值, 最新-单位净值, 最新-累计净值, 基金类型, 查询日期
                df = df.rename(columns={
                    "基金代码": "code",
                    "基金名称": "name",
                    "当前-单位净值": "price"
                })
                # 填充缺失字段
                df["change_pct"] = 0.0
                df["volume"] = 0.0
                
                # 数据清洗
                df["price"] = pd.to_numeric(df["price"], errors="coerce")
                
                records = cast(List[Dict[str, Any]], df[["code", "name", "price", "change_pct", "volume"]].to_dict(orient="records"))  # type: ignore
                
                logger.info(f"Successfully loaded {len(records)} ETFs from THS.")
                disk_cache.set(ETF_LIST_CACHE_KEY, records, expire=86400)
                return records
        except Exception as e:
            logger.error(f"THS fetch failed: {e}")

        # --- Attempt 4: Disk Cache ---
        logger.warning("All online fetches failed. Attempting to load from disk cache...")
        cached_list = cast(List[Dict[str, Any]], disk_cache.get(ETF_LIST_CACHE_KEY))
        if cached_list and len(cached_list) > 20:
            return cached_list
        
        # --- Attempt 4: Fallback JSON ---
        logger.warning("Disk cache empty. Loading fallback JSON...")
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
            else:
                logger.warning("Background refresh failed to get data.")

        except Exception as e:
            logger.error(f"Error in background refresh: {e}")
        finally:
            with AkShareService._refresh_lock:
                AkShareService._is_refreshing = False

    @staticmethod
    def get_etf_info(code: str) -> Optional[Dict]:
        """
        获取单个 ETF 的实时信息。
        逻辑：
        1. 如果缓存过期但已初始化：启动后台刷新，立即返回旧数据（非阻塞）。
        2. 如果缓存未初始化：必须同步阻塞刷新（否则没数据）。
        """
        if not etf_cache.is_initialized:
            # 必须同步加载 (Cold start)
            logger.info("Cache empty (cold start), syncing etf list...")
            data = AkShareService.fetch_all_etfs()
            if data:
                etf_cache.set_etf_list(data)
            
            # Try disk cache fallback if network failed
            if not etf_cache.is_initialized:
                 cached_list = disk_cache.get(ETF_LIST_CACHE_KEY)
                 if cached_list:
                     etf_cache.set_etf_list(cast(List[Dict[str, Any]], cached_list))

        elif etf_cache.is_stale:
            # 缓存过期但有数据，触发后台刷新 (Stale-While-Revalidate)
            should_start = False
            with AkShareService._refresh_lock:
                if not AkShareService._is_refreshing:
                    should_start = True
            
            if should_start:
                logger.info("Cache stale, triggering background refresh...")
                t = threading.Thread(target=AkShareService._refresh_task)
                t.daemon = True
                t.start()

        return etf_cache.get_etf_info(code)

    @staticmethod
    def fetch_history_raw(code: str, period: str, adjust: str) -> pd.DataFrame:
        """纯粹的历史数据获取 (带 DiskCache)"""
        cache_key = f"hist_{code}_{period}_{adjust}"
        
        # Try to get from disk cache first (valid for 1 hour)
        cached_data = disk_cache.get(cache_key)
        if cached_data is not None:
             # logger.info(f"Cache hit for {code}")
             return cast(pd.DataFrame, cached_data)

        try:
            logger.info(f"Fetching history for {code} adjust={adjust} from AkShare")
            df = ak.fund_etf_hist_em(symbol=code, period=period, adjust=adjust, start_date="20000101", end_date="20500101")
            
            if df.empty:
                return pd.DataFrame()

            df = df.rename(columns={
                "日期": "date",
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交量": "volume"
            })
            
            # Store in disk cache for 1 hour (3600 seconds)
            disk_cache.set(cache_key, df, expire=3600)
            
            return df
        except Exception as e:
            logger.error(f"Error fetching history raw for {code}: {e}")
            return pd.DataFrame()

    @staticmethod
    def get_etf_history(code: str, period: str = "daily", adjust: str = "qfq") -> List[Dict]:
        """
        获取拼接了实时数据的历史行情
        """
        # 1. 获取历史数据
        df_hist = AkShareService.fetch_history_raw(code, period, adjust)
        
        if df_hist.empty:
            return []

        # 2. 获取实时数据
        realtime_info = AkShareService.get_etf_info(code)
        
        records = df_hist.to_dict(orient="records")

        # 3. 拼接逻辑
        # 如果实时数据存在，且历史数据最后一条的日期不是今天，则追加（或更新）今天的数据
        if realtime_info and realtime_info.get("price"):
            today_str = datetime.now().strftime("%Y-%m-%d")
            
            if records:
                last_record = records[-1]
                last_date = last_record["date"]
                
                current_price = realtime_info["price"]
                
                # 如果历史数据最后一天就是今天（收盘后可能出现），则覆盖
                if last_date == today_str:
                    last_record["close"] = current_price
                    # 注意: 这里的 open/high/low 可能不准，暂时仅更新 close 用于画图
                else:
                    # 历史数据还没包含今天，追加一条
                    # 为了画图连续，open/high/low 暂时设为 current_price (MVP简化)
                    records.append({
                        "date": today_str,
                        "open": current_price,
                        "close": current_price,
                        "high": current_price,
                        "low": current_price,
                        "volume": 0
                    })
        
        return records

ak_service = AkShareService()
