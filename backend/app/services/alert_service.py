"""
告警信号检测服务

检测 ETF 指标变化并生成告警信号
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from app.models.alert_config import (
    ETFAlertState,
    SignalItem,
    UserAlertPreferences,
)
from app.services.temperature_service import temperature_service
from app.services.trend_service import trend_service
from app.services.alert_state_service import alert_state_service

logger = logging.getLogger(__name__)


class AlertService:
    """告警信号检测服务"""

    def __init__(self):
        pass

    def _detect_temperature_signals(
        self,
        etf_code: str,
        etf_name: str,
        current: Dict[str, Any],
        previous: Optional[ETFAlertState],
        prefs: UserAlertPreferences,
    ) -> List[SignalItem]:
        """检测温度计相关信号"""
        signals = []

        if not current.get("temperature"):
            return signals

        temp = current["temperature"]
        curr_level = temp.get("level")
        curr_score = temp.get("score")
        rsi = temp.get("rsi_value")

        # 温度等级变化
        if prefs.temperature_change and previous and previous.temperature_level:
            if curr_level != previous.temperature_level:
                signals.append(SignalItem(
                    etf_code=etf_code,
                    etf_name=etf_name,
                    signal_type="temperature_change",
                    signal_detail=f"温度 {previous.temperature_level} → {curr_level}",
                    priority="high",
                ))

        # 极端温度
        if prefs.extreme_temperature:
            if curr_level == "freezing" and (not previous or previous.temperature_level != "freezing"):
                signals.append(SignalItem(
                    etf_code=etf_code,
                    etf_name=etf_name,
                    signal_type="extreme_temperature",
                    signal_detail=f"进入冰点区域 (温度={curr_score})",
                    priority="high",
                ))
            elif curr_level == "hot" and (not previous or previous.temperature_level != "hot"):
                signals.append(SignalItem(
                    etf_code=etf_code,
                    etf_name=etf_name,
                    signal_type="extreme_temperature",
                    signal_detail=f"进入过热区域 (温度={curr_score})",
                    priority="high",
                ))

        # RSI 超买超卖
        if rsi is not None:
            prev_rsi = previous.rsi_value if previous else None
            if rsi > 70 and (prev_rsi is None or prev_rsi <= 70):
                signals.append(SignalItem(
                    etf_code=etf_code,
                    etf_name=etf_name,
                    signal_type="rsi_overbought",
                    signal_detail=f"RSI 超买 ({rsi:.1f})",
                    priority="medium",
                ))
            elif rsi < 30 and (prev_rsi is None or prev_rsi >= 30):
                signals.append(SignalItem(
                    etf_code=etf_code,
                    etf_name=etf_name,
                    signal_type="rsi_oversold",
                    signal_detail=f"RSI 超卖 ({rsi:.1f})",
                    priority="medium",
                ))

        return signals

    def _detect_ma_signals(
        self,
        etf_code: str,
        etf_name: str,
        current: Dict[str, Any],
        previous: Optional[ETFAlertState],
        prefs: UserAlertPreferences,
    ) -> List[SignalItem]:
        """检测均线相关信号"""
        signals = []

        daily = current.get("daily_trend")
        if not daily:
            return signals

        # 均线突破信号
        if prefs.ma_crossover:
            for ma_key, ma_label in [("ma60", "MA60"), ("ma20", "MA20")]:
                position = daily.get(f"{ma_key}_position")
                if position == "crossing_up":
                    signals.append(SignalItem(
                        etf_code=etf_code,
                        etf_name=etf_name,
                        signal_type=f"ma_cross_up_{ma_key}",
                        signal_detail=f"上穿 {ma_label}",
                        priority="high" if ma_key == "ma60" else "medium",
                    ))
                elif position == "crossing_down":
                    signals.append(SignalItem(
                        etf_code=etf_code,
                        etf_name=etf_name,
                        signal_type=f"ma_cross_down_{ma_key}",
                        signal_detail=f"下穿 {ma_label}",
                        priority="high" if ma_key == "ma60" else "medium",
                    ))

        # 均线排列变化
        if prefs.ma_alignment and previous and previous.ma_alignment:
            curr_align = daily.get("ma_alignment")
            if curr_align and curr_align != previous.ma_alignment:
                if curr_align == "bullish":
                    signals.append(SignalItem(
                        etf_code=etf_code,
                        etf_name=etf_name,
                        signal_type="ma_alignment_bullish",
                        signal_detail="均线多头排列形成",
                        priority="medium",
                    ))
                elif curr_align == "bearish":
                    signals.append(SignalItem(
                        etf_code=etf_code,
                        etf_name=etf_name,
                        signal_type="ma_alignment_bearish",
                        signal_detail="均线空头排列形成",
                        priority="medium",
                    ))

        return signals

    def _detect_weekly_signals(
        self,
        etf_code: str,
        etf_name: str,
        current: Dict[str, Any],
        previous: Optional[ETFAlertState],
        prefs: UserAlertPreferences,
    ) -> List[SignalItem]:
        """检测周线相关信号"""
        signals = []

        if not prefs.weekly_signal:
            return signals

        weekly = current.get("weekly_trend")
        if not weekly:
            return signals

        curr_status = weekly.get("ma_status")

        # 周线趋势转换
        if previous and previous.weekly_alignment and curr_status:
            if curr_status != previous.weekly_alignment:
                if curr_status == "bullish" and previous.weekly_alignment == "bearish":
                    signals.append(SignalItem(
                        etf_code=etf_code,
                        etf_name=etf_name,
                        signal_type="weekly_trend_bullish",
                        signal_detail="周线空转多",
                        priority="high",
                    ))
                elif curr_status == "bearish" and previous.weekly_alignment == "bullish":
                    signals.append(SignalItem(
                        etf_code=etf_code,
                        etf_name=etf_name,
                        signal_type="weekly_trend_bearish",
                        signal_detail="周线多转空",
                        priority="high",
                    ))

        return signals

    def detect_signals(
        self,
        user_id: int,
        etf_code: str,
        etf_name: str,
        current_metrics: Dict[str, Any],
        prefs: UserAlertPreferences,
    ) -> List[SignalItem]:
        """
        检测单个 ETF 的所有信号

        Args:
            user_id: 用户 ID
            etf_code: ETF 代码
            etf_name: ETF 名称
            current_metrics: 当前指标数据 (temperature, daily_trend, weekly_trend)
            prefs: 用户告警偏好

        Returns:
            检测到的信号列表
        """
        # 获取上次状态
        previous = alert_state_service.get_state(user_id, etf_code)

        all_signals = []

        # 检测各类信号
        all_signals.extend(self._detect_temperature_signals(
            etf_code, etf_name, current_metrics, previous, prefs
        ))
        all_signals.extend(self._detect_ma_signals(
            etf_code, etf_name, current_metrics, previous, prefs
        ))
        all_signals.extend(self._detect_weekly_signals(
            etf_code, etf_name, current_metrics, previous, prefs
        ))

        # 过滤已发送的信号（当天去重）
        filtered_signals = []
        for signal in all_signals:
            if not alert_state_service.is_signal_sent_today(
                user_id, etf_code, signal.signal_type
            ):
                filtered_signals.append(signal)

        return filtered_signals

    def build_current_state(
        self, etf_code: str, metrics: Dict[str, Any]
    ) -> ETFAlertState:
        """根据当前指标构建状态快照"""
        temp = metrics.get("temperature") or {}
        daily = metrics.get("daily_trend") or {}
        weekly = metrics.get("weekly_trend") or {}

        return ETFAlertState(
            etf_code=etf_code,
            last_check_time=datetime.now(),
            temperature_level=temp.get("level"),
            temperature_score=temp.get("score"),
            rsi_value=temp.get("rsi_value"),
            ma5_position=daily.get("ma5_position"),
            ma20_position=daily.get("ma20_position"),
            ma60_position=daily.get("ma60_position"),
            ma_alignment=daily.get("ma_alignment"),
            weekly_alignment=weekly.get("ma_status"),
        )


# 全局单例
alert_service = AlertService()
