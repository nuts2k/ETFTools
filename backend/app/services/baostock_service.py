"""
Baostock 历史数据源

单例连接管理，线程安全，自动重连。
官方数据源，稳定性高于 AkShare 爬虫方式。
"""
import logging
import threading
from typing import Optional

import baostock as bs
import pandas as pd

logger = logging.getLogger(__name__)

# 复权参数映射：项目格式 → Baostock 格式
_ADJUST_MAP = {"qfq": "2", "hfq": "1", "": "3"}


def _to_baostock_code(code: str) -> str:
    """ETF 代码转 Baostock 格式 (sh.XXXXXX / sz.XXXXXX)"""
    prefix = code[0]
    if prefix in ("0", "1", "3"):
        return f"sz.{code}"
    return f"sh.{code}"


class _BaostockConnection:
    """Baostock 单例连接管理器"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._logged_in = False

    def ensure_login(self) -> bool:
        with self._lock:
            if self._logged_in:
                return True
            lg = bs.login()
            if lg.error_code != "0":
                logger.error("Baostock login failed: %s", lg.error_msg)
                return False
            self._logged_in = True
            logger.info("Baostock login succeeded")
            return True

    def reconnect(self) -> bool:
        with self._lock:
            try:
                bs.logout()
            except Exception:
                pass
            self._logged_in = False
            lg = bs.login()
            if lg.error_code != "0":
                logger.error("Baostock reconnect failed: %s", lg.error_msg)
                return False
            self._logged_in = True
            logger.info("Baostock reconnected")
            return True

    def logout(self) -> None:
        with self._lock:
            if self._logged_in:
                try:
                    bs.logout()
                except Exception:
                    pass
                self._logged_in = False


_connection = _BaostockConnection()


class BaostockSource:
    """Baostock 历史数据源，实现 HistoryDataSource 协议"""

    name: str = "baostock"

    def fetch_history(
        self,
        code: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> Optional[pd.DataFrame]:
        if not _connection.ensure_login():
            return None

        bs_code = _to_baostock_code(code)
        adjustflag = _ADJUST_MAP.get(adjust, "2")
        fields = "date,open,high,low,close,volume,amount,pctChg"

        rs = bs.query_history_k_data_plus(
            bs_code,
            fields,
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag=adjustflag,
        )

        # 查询失败 → 尝试重连一次
        if rs.error_code != "0":
            logger.warning("Baostock query failed (%s), reconnecting...", rs.error_msg)
            if not _connection.reconnect():
                return None
            rs = bs.query_history_k_data_plus(
                bs_code, fields,
                start_date=start_date, end_date=end_date,
                frequency="d", adjustflag=adjustflag,
            )
            if rs.error_code != "0":
                logger.error("Baostock query failed after reconnect: %s", rs.error_msg)
                return None

        rows = []
        while rs.next():
            rows.append(rs.get_row_data())

        if not rows:
            logger.warning("Baostock returned empty data: %s", code)
            return None

        df = pd.DataFrame(rows, columns=rs.fields)
        # 数值类型转换
        for col in ["open", "high", "low", "close", "volume", "amount", "pctChg"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    def is_available(self) -> bool:
        return _connection.ensure_login()
