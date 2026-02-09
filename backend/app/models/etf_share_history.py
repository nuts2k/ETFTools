from typing import Optional
from datetime import datetime
from sqlmodel import Field, SQLModel, UniqueConstraint, Index


class ETFShareHistory(SQLModel, table=True):
    """ETF 份额历史记录表"""
    __tablename__ = "etf_share_history"
    __table_args__ = (
        UniqueConstraint('code', 'date', name='uq_code_date'),
        Index('idx_code_date', 'code', 'date'),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True)           # ETF代码，如 "510300"
    date: str = Field(index=True)           # 统计日期 YYYY-MM-DD
    shares: float                            # 基金份额（亿份）
    exchange: str                            # 交易所 "SSE" / "SZSE"
    etf_type: Optional[str] = None          # ETF类型，如 "股票型"
    created_at: datetime = Field(default_factory=datetime.utcnow)
