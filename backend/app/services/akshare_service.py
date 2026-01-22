import akshare as ak
import pandas as pd
from typing import List, Dict, Optional, Any
import logging
from cachetools import TTLCache, cached
from datetime import datetime

from app.core.cache import etf_cache

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 历史数据缓存 (5分钟)
history_cache = TTLCache(maxsize=100, ttl=300)

class AkShareService:
    @staticmethod
    def fetch_all_etfs() -> List[Dict]:
        """
        获取全市场 ETF 实时行情（用于构建基础列表）
        Source: ak.fund_etf_spot_em()
        """
        try:
            logger.info("Fetching all ETF spot data from AkShare...")
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
            return records
            
        except Exception as e:
            logger.error(f"Error fetching ETF list: {e}")
            return []

    @staticmethod
    def get_etf_info(code: str) -> Optional[Dict]:
        """
        获取单个 ETF 的实时信息。
        逻辑：优先查缓存，如果缓存过期(60s)，则重新拉取全量列表并更新缓存。
        """
        if etf_cache.is_stale:
            # 缓存过期，触发刷新 (可以是异步的，这里为了简化MVP先同步)
            # 在高并发下这里应该加锁，MVP 暂略
            logger.info("Cache stale, refreshing etf list...")
            data = AkShareService.fetch_all_etfs()
            if data:
                etf_cache.set_etf_list(data)
        
        return etf_cache.get_etf_info(code)

    @staticmethod
    @cached(history_cache)
    def fetch_history_raw(code: str, period: str, adjust: str) -> pd.DataFrame:
        """纯粹的历史数据获取 (带缓存)"""
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
