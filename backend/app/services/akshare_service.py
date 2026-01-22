import akshare as ak
import pandas as pd
from typing import List, Dict, Optional, Any
import logging
from diskcache import Cache
from datetime import datetime
import os
import time

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
        Source: ak.fund_etf_spot_em()
        """
        retries = 3
        for i in range(retries):
            try:
                logger.info(f"Fetching all ETF spot data from AkShare (Attempt {i+1}/{retries})...")
                df = ak.fund_etf_spot_em()
                
                # 字段映射
                df = df.rename(columns={
                    "代码": "code",
                    "名称": "name",
                    "最新价": "price",
                    "涨跌幅": "change_pct",
                    "成交额": "volume", 
                })
                
                # 清洗数据，确保 price 是数字
                df["price"] = pd.to_numeric(df["price"], errors="coerce")
                df["change_pct"] = pd.to_numeric(df["change_pct"], errors="coerce")
                
                records = df[["code", "name", "price", "change_pct", "volume"]].to_dict(orient="records")
                
                logger.info(f"Successfully loaded {len(records)} ETFs.")
                
                # Save to disk cache for persistence across restarts
                disk_cache.set(ETF_LIST_CACHE_KEY, records, expire=86400) # Valid for 24 hours in disk
                
                return records
            except Exception as e:
                logger.error(f"Error fetching ETF list: {e}")
                time.sleep(1) # Wait before retry
        
        # If all retries fail, try to load from disk cache
        logger.warning("All retries failed. Attempting to load from disk cache...")
        cached_list = disk_cache.get(ETF_LIST_CACHE_KEY)
        if cached_list and len(cached_list) > 20: # Ensure we have a decent amount of data
            logger.info(f"Loaded {len(cached_list)} ETFs from disk cache.")
            return cached_list
        
        # If disk cache is empty or too small (e.g. only Seed data), load fallback
        logger.warning("Disk cache empty or insufficient. Loading fallback data...")
        fallback_data = AkShareService.load_fallback_data()
        if fallback_data:
            # Merge with existing cache if any (e.g. Seed data)
            if cached_list:
                # Simple merge: prefer fallback for broader coverage
                # In real world, we might want to dedup
                return fallback_data 
            return fallback_data
            
        return []

    @staticmethod
    def get_etf_info(code: str) -> Optional[Dict]:
        """
        获取单个 ETF 的实时信息。
        逻辑：优先查缓存，如果缓存过期(60s)，则重新拉取全量列表并更新缓存。
        """
        if etf_cache.is_stale or not etf_cache.is_initialized:
            # 缓存过期，触发刷新 (可以是异步的，这里为了简化MVP先同步)
            # 在高并发下这里应该加锁，MVP 暂略
            logger.info("Cache stale or empty, refreshing etf list...")
            data = AkShareService.fetch_all_etfs()
            if data:
                etf_cache.set_etf_list(data)
            
            # If still not initialized (e.g. network failure and no disk cache), try fallback
            if not etf_cache.is_initialized:
                # Try to load from disk cache directly if we haven't already
                cached_list = disk_cache.get(ETF_LIST_CACHE_KEY)
                if cached_list:
                    etf_cache.set_etf_list(cached_list)

        return etf_cache.get_etf_info(code)

    @staticmethod
    def fetch_history_raw(code: str, period: str, adjust: str) -> pd.DataFrame:
        """纯粹的历史数据获取 (带 DiskCache)"""
        cache_key = f"hist_{code}_{period}_{adjust}"
        
        # Try to get from disk cache first (valid for 1 hour)
        cached_data = disk_cache.get(cache_key)
        if cached_data is not None:
             # logger.info(f"Cache hit for {code}")
             return cached_data

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
