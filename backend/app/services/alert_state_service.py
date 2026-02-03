"""
告警状态缓存服务

管理 ETF 告警状态的存储和去重逻辑
"""

import os
import logging
from datetime import datetime, date
from typing import Optional, Dict, Any

from diskcache import Cache

from app.models.alert_config import ETFAlertState

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.getcwd(), ".cache", "alerts")


class AlertStateService:
    """告警状态缓存服务"""

    def __init__(self):
        self._cache = Cache(CACHE_DIR)

    def _state_key(self, user_id: int, etf_code: str) -> str:
        """生成状态缓存 key"""
        return f"alert_state:{user_id}:{etf_code}"

    def _sent_key(self, user_id: int, etf_code: str, signal_type: str) -> str:
        """生成已发送信号缓存 key（当天去重）"""
        today = date.today().isoformat()
        return f"alert_sent:{user_id}:{etf_code}:{signal_type}:{today}"

    def get_state(self, user_id: int, etf_code: str) -> Optional[ETFAlertState]:
        """获取 ETF 的上次状态快照"""
        key = self._state_key(user_id, etf_code)
        data = self._cache.get(key)
        if data:
            return ETFAlertState(**data)
        return None

    def save_state(self, user_id: int, state: ETFAlertState) -> None:
        """保存 ETF 状态快照"""
        key = self._state_key(user_id, state.etf_code)
        # 状态保存 7 天
        self._cache.set(key, state.model_dump(), expire=7 * 24 * 3600)

    def is_signal_sent_today(
        self, user_id: int, etf_code: str, signal_type: str
    ) -> bool:
        """检查信号今天是否已发送"""
        key = self._sent_key(user_id, etf_code, signal_type)
        return self._cache.get(key) is not None

    def mark_signal_sent(
        self, user_id: int, etf_code: str, signal_type: str
    ) -> None:
        """标记信号已发送（当天有效）"""
        key = self._sent_key(user_id, etf_code, signal_type)
        # 计算到今天 23:59:59 的秒数
        now = datetime.now()
        end_of_day = datetime(now.year, now.month, now.day, 23, 59, 59)
        ttl = int((end_of_day - now).total_seconds())
        self._cache.set(key, True, expire=max(ttl, 1))

    def get_daily_sent_count(self, user_id: int) -> int:
        """获取用户今天已发送的信号数量"""
        today = date.today().isoformat()
        prefix = f"alert_sent:{user_id}:"
        count = 0
        for key in self._cache.iterkeys():
            if key.startswith(prefix) and key.endswith(today):
                count += 1
        return count

    def clear_user_state(self, user_id: int) -> None:
        """清除用户的所有状态缓存"""
        prefix = f"alert_state:{user_id}:"
        keys_to_delete = [k for k in self._cache.iterkeys() if k.startswith(prefix)]
        for key in keys_to_delete:
            self._cache.delete(key)


# 全局单例
alert_state_service = AlertStateService()
