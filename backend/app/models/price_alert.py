"""到价提醒模型"""
import re
from enum import Enum
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field as PydanticField, field_validator
from sqlmodel import SQLModel, Field, Index


class PriceAlertDirection(str, Enum):
    ABOVE = "above"
    BELOW = "below"


class PriceAlert(SQLModel, table=True):
    """到价提醒"""
    __tablename__ = "price_alerts"
    __table_args__ = (
        Index("idx_price_alerts_user_active", "user_id", "is_triggered"),
        Index("idx_price_alerts_active", "is_triggered"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    etf_code: str = Field(max_length=10, index=True)
    etf_name: str = Field(max_length=50)
    target_price: float
    direction: str = Field(max_length=10)  # "above" | "below"
    note: Optional[str] = Field(default=None, max_length=200)
    is_triggered: bool = Field(default=False)
    triggered_at: Optional[datetime] = Field(default=None)
    triggered_price: Optional[float] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# --- Pydantic 请求/响应模型 ---

class PriceAlertCreate(BaseModel):
    etf_code: str
    etf_name: str = PydanticField(max_length=50)
    target_price: float = PydanticField(gt=0)
    direction: Optional[PriceAlertDirection] = None  # 可选，后端自动推断
    note: Optional[str] = PydanticField(default=None, max_length=200)

    @field_validator("etf_code")
    @classmethod
    def validate_etf_code(cls, v: str) -> str:
        if not re.match(r"^\d{6}$", v):
            raise ValueError("ETF 代码必须为 6 位数字")
        return v


class PriceAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    etf_code: str
    etf_name: str
    target_price: float
    direction: PriceAlertDirection
    note: Optional[str]
    is_triggered: bool
    triggered_at: Optional[datetime]
    triggered_price: Optional[float]
    created_at: datetime
