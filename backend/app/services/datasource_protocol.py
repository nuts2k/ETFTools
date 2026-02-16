# backend/app/services/datasource_protocol.py
"""历史数据源统一协议"""
from typing import Optional, runtime_checkable

from typing import Protocol

import pandas as pd


@runtime_checkable
class HistoryDataSource(Protocol):
    """
    历史数据源接口。

    所有历史数据源必须实现此协议。
    返回的 DataFrame 至少包含列: date, open, high, low, close, volume
    """

    name: str

    def fetch_history(
        self,
        code: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> Optional[pd.DataFrame]: ...

    def is_available(self) -> bool: ...
