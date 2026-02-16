"""
数据源指标收集器

轻量级内存指标，追踪各数据源的成功率、延迟、状态。
线程安全（akshare_service 在后台线程中运行）。
"""

import functools
import logging
import threading
import time
from collections import deque
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

_CHINA_TZ = ZoneInfo("Asia/Shanghai")
_WINDOW_SIZE = 100  # 滑动窗口大小


class SourceStats:
    """单个数据源的统计数据"""

    __slots__ = (
        "success_count",
        "failure_count",
        "latencies",
        "results",
        "last_status",
        "last_success_at",
        "last_failure_at",
        "last_error",
        "circuit_open_until",
    )

    def __init__(self) -> None:
        self.success_count: int = 0
        self.failure_count: int = 0
        self.latencies: deque = deque(maxlen=_WINDOW_SIZE)
        self.results: deque = deque(maxlen=_WINDOW_SIZE)  # True=成功, False=失败
        self.last_status: str = "unknown"
        self.last_success_at: Optional[datetime] = None
        self.last_failure_at: Optional[datetime] = None
        self.last_error: Optional[str] = None
        self.circuit_open_until: Optional[float] = None


class DataSourceMetrics:
    """数据源指标收集器（单例）"""

    def __init__(self) -> None:
        self._sources: Dict[str, SourceStats] = {}
        self._lock = threading.Lock()

    def _get_or_create(self, source: str) -> SourceStats:
        if source not in self._sources:
            self._sources[source] = SourceStats()
        return self._sources[source]

    def record_success(self, source: str, latency_ms: float) -> bool:
        """记录成功调用。返回 True 表示从 error 恢复（可用于触发恢复告警）。"""
        now = datetime.now(_CHINA_TZ)
        with self._lock:
            stats = self._get_or_create(source)
            was_error = stats.last_status == "error"
            stats.success_count += 1
            stats.latencies.append(latency_ms)
            stats.results.append(True)
            stats.last_status = "ok"
            stats.last_success_at = now
            return was_error

    def record_failure(self, source: str, error: str, latency_ms: float) -> None:
        now = datetime.now(_CHINA_TZ)
        with self._lock:
            stats = self._get_or_create(source)
            stats.failure_count += 1
            stats.latencies.append(latency_ms)
            stats.results.append(False)
            stats.last_status = "error"
            stats.last_failure_at = now
            stats.last_error = error

    def get_success_rate(self, source: str) -> Optional[float]:
        """最近 N 次调用的成功率（0.0 ~ 1.0），无记录返回 None"""
        with self._lock:
            stats = self._sources.get(source)
            if not stats or not stats.results:
                return None
            return sum(stats.results) / len(stats.results)

    def get_avg_latency(self, source: str) -> Optional[float]:
        """平均延迟（ms），无记录返回 None"""
        with self._lock:
            stats = self._sources.get(source)
            if not stats or not stats.latencies:
                return None
            return sum(stats.latencies) / len(stats.latencies)

    def get_source_status(self, source: str) -> Dict[str, Any]:
        """单个数据源的完整状态"""
        with self._lock:
            stats = self._sources.get(source)
            if not stats:
                return {"status": "unknown"}
            return self._stats_to_dict(stats)

    def is_circuit_open(
        self,
        source: str,
        threshold: float = 0.1,
        window: int = 10,
        cooldown: int = 300,
    ) -> bool:
        """
        检查数据源是否被熔断。

        规则：
        - 最近 window 次调用成功率 < threshold → 开启熔断
        - 熔断持续 cooldown 秒
        - 到期后允许一次探测（半开状态）
        """
        with self._lock:
            stats = self._sources.get(source)
            if not stats:
                return False

            now = time.monotonic()

            # 在冷却期内 → 熔断开启
            if stats.circuit_open_until is not None:
                if now < stats.circuit_open_until:
                    return True
                # 冷却期过 → 半开，允许探测
                stats.circuit_open_until = None
                return False

            # 数据不足 → 不熔断
            recent = list(stats.results)[-window:]
            if len(recent) < window:
                return False

            # 成功率低于阈值 → 开启熔断
            rate = sum(recent) / len(recent)
            if rate < threshold:
                stats.circuit_open_until = now + cooldown
                return True

            return False

    def get_summary(self) -> Dict[str, Dict[str, Any]]:
        """所有数据源状态汇总"""
        with self._lock:
            return {
                source: self._stats_to_dict(stats)
                for source, stats in self._sources.items()
            }

    def get_overall_status(self) -> str:
        """
        整体状态：
        - "healthy": 所有源 ok（或无记录）
        - "degraded": 部分源 error
        - "critical": 全部源 error
        """
        with self._lock:
            if not self._sources:
                return "healthy"
            statuses = [s.last_status for s in self._sources.values()]
            if all(s == "ok" for s in statuses):
                return "healthy"
            if all(s == "error" for s in statuses):
                return "critical"
            return "degraded"

    @staticmethod
    def _stats_to_dict(stats: SourceStats) -> Dict[str, Any]:
        def _fmt_time(dt: Optional[datetime]) -> Optional[str]:
            return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None

        success_rate = (
            sum(stats.results) / len(stats.results) if stats.results else None
        )
        avg_latency = (
            round(sum(stats.latencies) / len(stats.latencies), 1)
            if stats.latencies
            else None
        )

        result: Dict[str, Any] = {
            "status": stats.last_status,
            "success_rate": round(success_rate, 3) if success_rate is not None else None,
            "avg_latency_ms": avg_latency,
            "success_count": stats.success_count,
            "failure_count": stats.failure_count,
        }
        if stats.last_success_at:
            result["last_success_at"] = _fmt_time(stats.last_success_at)
        if stats.last_failure_at:
            result["last_failure_at"] = _fmt_time(stats.last_failure_at)
        if stats.last_error:
            result["last_error"] = stats.last_error
        return result


# 模块级单例
datasource_metrics = DataSourceMetrics()


def track_datasource(source_name: str) -> Callable:
    """
    装饰器：自动追踪数据源调用的成功/失败/耗时。

    只包裹单次调用，重试逻辑应留在外层。

    用法:
        @track_datasource("eastmoney")
        def _fetch_etfs_eastmoney():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.monotonic()
            try:
                result = func(*args, **kwargs)
                latency = (time.monotonic() - start) * 1000
                recovered = datasource_metrics.record_success(source_name, latency)
                logger.info(
                    "[%s] %s succeeded (%.0fms)", source_name, func.__name__, latency
                )
                if recovered:
                    logger.info("[%s] source recovered from error state", source_name)
                    try:
                        from app.services.admin_alert_service import admin_alert_service
                        admin_alert_service.send_admin_alert_sync(
                            "source_recovered",
                            f"{source_name} 已恢复正常",
                        )
                    except Exception:
                        pass
                return result
            except Exception as e:
                latency = (time.monotonic() - start) * 1000
                datasource_metrics.record_failure(source_name, str(e), latency)
                logger.warning(
                    "[%s] %s failed (%.0fms): %s",
                    source_name,
                    func.__name__,
                    latency,
                    e,
                )
                raise

        return wrapper

    return decorator
