"""
告警配置数据模型

定义全局调度配置和用户告警偏好
"""

import re
from enum import Enum
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class TemperatureLevel(str, Enum):
    """温度等级"""
    FREEZING = "freezing"
    COOL = "cool"
    WARM = "warm"
    HOT = "hot"


class MAAlignment(str, Enum):
    """均线排列状态"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    MIXED = "mixed"


class MAPosition(str, Enum):
    """均线位置状态"""
    ABOVE = "above"
    BELOW = "below"
    CROSSING_UP = "crossing_up"
    CROSSING_DOWN = "crossing_down"


class SignalPriority(str, Enum):
    """信号优先级"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AlertScheduleConfig(BaseModel):
    """全局调度配置"""
    # 盘中检查
    intraday_enabled: bool = True
    intraday_interval_minutes: int = Field(default=30, ge=5, le=120)
    intraday_start_time: str = "09:30"
    intraday_end_time: str = "15:00"

    # 收盘汇总
    daily_summary_enabled: bool = True
    daily_summary_time: str = "15:30"

    # 交易日判断
    skip_weekends: bool = True

    @field_validator('intraday_start_time', 'intraday_end_time', 'daily_summary_time')
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        """验证时间格式 HH:MM"""
        if not re.match(r'^([01]\d|2[0-3]):[0-5]\d$', v):
            raise ValueError(f'时间格式错误，应为 HH:MM: {v}')
        return v


class UserAlertPreferences(BaseModel):
    """用户告警偏好（存储在 User.settings["alerts"]）"""
    enabled: bool = True

    # 信号类型开关
    temperature_change: bool = True      # 温度等级变化
    extreme_temperature: bool = True     # 极端温度
    rsi_signal: bool = True              # RSI 超买超卖
    ma_crossover: bool = True            # 均线上穿/下穿
    ma_alignment: bool = True            # 均线排列变化
    weekly_signal: bool = True           # 周线信号

    # 通知频率控制
    max_alerts_per_day: int = Field(default=100, ge=1, le=100)


class ETFAlertState(BaseModel):
    """ETF 告警状态快照（存储在 DiskCache）"""
    etf_code: str
    last_check_time: datetime

    # 温度计状态
    temperature_level: Optional[TemperatureLevel] = None
    temperature_score: Optional[float] = None
    rsi_value: Optional[float] = None

    # 日线均线状态
    ma5_position: Optional[MAPosition] = None
    ma20_position: Optional[MAPosition] = None
    ma60_position: Optional[MAPosition] = None
    ma_alignment: Optional[MAAlignment] = None

    # 周线状态
    weekly_alignment: Optional[MAAlignment] = None


class SignalItem(BaseModel):
    """单个信号项"""
    etf_code: str
    etf_name: str
    signal_type: str       # temperature_change, ma_crossover, etc.
    signal_detail: str     # 具体描述
    priority: SignalPriority


class AlertMessage(BaseModel):
    """告警消息（合并多个信号）"""
    check_time: datetime
    signals: list[SignalItem] = []
