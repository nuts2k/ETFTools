from typing import Optional, Any
from datetime import datetime
from sqlmodel import Field, SQLModel, JSON


class SystemConfig(SQLModel, table=True):
    """系统配置表 - 存储全局设置"""
    __tablename__ = "system_config"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True, max_length=100)
    value: Any = Field(sa_type=JSON)
    description: Optional[str] = Field(default=None, max_length=500)
    updated_by: Optional[int] = Field(default=None, foreign_key="user.id")
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SystemConfigKeys:
    """预定义配置键常量"""
    REGISTRATION_ENABLED = "registration_enabled"
    MAX_WATCHLIST_ITEMS = "max_watchlist_items"
    MAINTENANCE_MODE = "maintenance_mode"
    ALERT_CHECK_ENABLED = "alert_check_enabled"
