"""
告警配置数据模型

定义全局调度配置和用户告警偏好
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


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


class UserAlertPreferences(BaseModel):
    """用户告警偏好（存储在 User.settings["alerts"]）"""
    enabled: bool = True

    # 信号类型开关
    temperature_change: bool = True      # 温度等级变化
    extreme_temperature: bool = True     # 极端温度
    ma_crossover: bool = True            # 均线上穿/下穿
    ma_alignment: bool = True            # 均线排列变化
    weekly_signal: bool = True           # 周线信号

    # 通知频率控制
    max_alerts_per_day: int = Field(default=20, ge=1, le=100)


class ETFAlertState(BaseModel):
    """ETF 告警状态快照（存储在 DiskCache）"""
    etf_code: str
    last_check_time: datetime

    # 温度计状态
    temperature_level: Optional[str] = None  # freezing/cool/warm/hot
    temperature_score: Optional[float] = None
    rsi_value: Optional[float] = None

    # 日线均线状态
    ma5_position: Optional[str] = None   # above/below/crossing_up/crossing_down
    ma20_position: Optional[str] = None
    ma60_position: Optional[str] = None
    ma_alignment: Optional[str] = None   # bullish/bearish/mixed

    # 周线状态
    weekly_alignment: Optional[str] = None  # bullish/bearish/mixed


class SignalItem(BaseModel):
    """单个信号项"""
    etf_code: str
    etf_name: str
    signal_type: str       # temperature_change, ma_crossover, etc.
    signal_detail: str     # 具体描述
    priority: str          # high, medium, low


class AlertMessage(BaseModel):
    """告警消息（合并多个信号）"""
    check_time: datetime
    signals: list[SignalItem] = []
