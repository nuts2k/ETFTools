"""
东方财富历史数据源

从 akshare_service.py 抽取，实现 HistoryDataSource 协议。
单次尝试，无重试（重试由 DataSourceManager 控制）。
"""
import logging
import time
from typing import Optional

import akshare as ak
import pandas as pd

from app.core.metrics import datasource_metrics

logger = logging.getLogger(__name__)


class EastMoneyHistorySource:
    """东方财富历史数据源，实现 HistoryDataSource 协议"""

    name: str = "eastmoney"

    def fetch_history(
        self,
        code: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> Optional[pd.DataFrame]:
        start = time.monotonic()
        try:
            df = ak.fund_etf_hist_em(
                symbol=code,
                period="daily",
                adjust=adjust,
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
            )
            if df.empty:
                latency = (time.monotonic() - start) * 1000
                datasource_metrics.record_failure(self.name, f"empty result for {code}", latency)
                return None

            df = df.rename(columns={
                "日期": "date", "开盘": "open", "收盘": "close",
                "最高": "high", "最低": "low", "成交量": "volume",
            })
            latency = (time.monotonic() - start) * 1000
            datasource_metrics.record_success(self.name, latency)
            return df
        except Exception as e:
            latency = (time.monotonic() - start) * 1000
            datasource_metrics.record_failure(self.name, str(e), latency)
            logger.warning("[eastmoney] fetch_history failed for %s: %s", code, e)
            return None

    def is_available(self) -> bool:
        return True  # AkShare 无持久连接，始终"可用"
