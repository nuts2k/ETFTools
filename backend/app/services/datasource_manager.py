"""
数据源管理器

按配置优先级编排历史数据源，集成熔断逻辑。
所有在线源失败后返回 None，由调用方走缓存兜底。
"""
import logging
import time
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from app.services.datasource_protocol import HistoryDataSource

import pandas as pd

from app.core.metrics import DataSourceMetrics, datasource_metrics

logger = logging.getLogger(__name__)


class DataSourceManager:
    """历史数据源编排器"""

    def __init__(
        self,
        sources: "List[HistoryDataSource]",
        metrics: Optional[DataSourceMetrics] = None,
        cb_threshold: float = 0.1,
        cb_window: int = 10,
        cb_cooldown: int = 300,
    ) -> None:
        self._sources = sources
        self._metrics = metrics or datasource_metrics
        self._cb_threshold = cb_threshold
        self._cb_window = cb_window
        self._cb_cooldown = cb_cooldown

    def fetch_history(
        self,
        code: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> Optional[pd.DataFrame]:
        for source in self._sources:
            # 可用性检查
            if not source.is_available():
                logger.info("[%s] not available, skipping", source.name)
                continue

            # 熔断检查
            if self._metrics.is_circuit_open(
                source.name,
                threshold=self._cb_threshold,
                window=self._cb_window,
                cooldown=self._cb_cooldown,
            ):
                logger.info("[%s] circuit open, skipping", source.name)
                continue

            start = time.monotonic()
            try:
                df = source.fetch_history(code, start_date, end_date, adjust)
                if df is not None and not df.empty:
                    latency = (time.monotonic() - start) * 1000
                    self._metrics.record_success(source.name, latency)
                    logger.info("[%s] fetch_history succeeded for %s (%.0fms)", source.name, code, latency)
                    return df
                # 返回 None 或空 → 视为失败
                latency = (time.monotonic() - start) * 1000
                self._metrics.record_failure(source.name, f"empty result for {code}", latency)
                logger.warning("[%s] returned empty for %s", source.name, code)
            except Exception as e:
                latency = (time.monotonic() - start) * 1000
                self._metrics.record_failure(source.name, str(e), latency)
                logger.warning("[%s] failed for %s: %s", source.name, code, e)

        logger.error("All history sources failed for %s", code)
        return None
