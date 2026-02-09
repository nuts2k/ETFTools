"""
资金流向业务逻辑服务

提供 ETF 份额规模查询和排名计算
"""

import logging
from typing import Optional, Dict, Any

from sqlmodel import Session, select, func
from app.core.share_history_database import share_history_engine
from app.models.etf_share_history import ETFShareHistory
from app.core.cache import etf_cache

logger = logging.getLogger(__name__)


class FundFlowService:
    """资金流向业务服务"""

    def get_current_scale(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取 ETF 当前规模

        Args:
            code: ETF 代码

        Returns:
            包含 shares, scale, update_date, exchange 的字典，无数据时返回 None
        """
        try:
            with Session(share_history_engine) as session:
                # 查询该 ETF 最新记录
                statement = (
                    select(ETFShareHistory)
                    .where(ETFShareHistory.code == code)
                    .order_by(ETFShareHistory.date.desc())
                    .limit(1)
                )
                record = session.exec(statement).first()

                if not record:
                    return None

                # 获取当前价格
                etf_info = etf_cache.get_etf_info(code)
                current_price = etf_info.get("price") if etf_info else None

                # 计算规模（亿元）
                scale = None
                if current_price is not None and current_price > 0:
                    scale = record.shares * current_price

                return {
                    "shares": record.shares,
                    "scale": scale,
                    "update_date": record.date,
                    "exchange": record.exchange,
                }

        except Exception as e:
            logger.error(f"Failed to get current scale for {code}: {e}", exc_info=True)
            return None

    def get_scale_rank(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取 ETF 规模排名

        Args:
            code: ETF 代码

        Returns:
            包含 rank, total_count, percentile, category 的字典，无数据时返回 None
        """
        try:
            with Session(share_history_engine) as session:
                # 先获取该 ETF 最新记录的日期
                statement = (
                    select(ETFShareHistory.date)
                    .where(ETFShareHistory.code == code)
                    .order_by(ETFShareHistory.date.desc())
                    .limit(1)
                )
                latest_date = session.exec(statement).first()

                if not latest_date:
                    return None

                # 使用 SQL 窗口函数计算排名（性能优化）
                from sqlalchemy import func as sql_func, literal_column
                from sqlalchemy.sql import text

                # 构建窗口函数查询
                rank_query = text("""
                    WITH ranked AS (
                        SELECT
                            code,
                            etf_type,
                            RANK() OVER (ORDER BY shares DESC) as rank,
                            COUNT(*) OVER () as total_count
                        FROM etf_share_history
                        WHERE date = :latest_date
                    )
                    SELECT rank, total_count, etf_type
                    FROM ranked
                    WHERE code = :code
                """)

                result = session.execute(
                    rank_query,
                    {"latest_date": latest_date, "code": code}
                ).first()

                if not result:
                    return None

                rank, total_count, etf_type = result
                percentile = (total_count - rank + 1) / total_count * 100

                return {
                    "rank": rank,
                    "total_count": total_count,
                    "percentile": round(percentile, 2),
                    "category": etf_type or "ETF",
                }

        except Exception as e:
            logger.error(f"Failed to get scale rank for {code}: {e}", exc_info=True)
            return None

    def get_fund_flow_data(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取完整的资金流向数据

        Args:
            code: ETF 代码

        Returns:
            完整的资金流向数据字典，无数据时返回 None
        """
        current_scale = self.get_current_scale(code)
        if not current_scale:
            return None

        rank_info = self.get_scale_rank(code)

        # 查询历史数据点数量
        try:
            with Session(share_history_engine) as session:
                statement = select(func.count()).where(ETFShareHistory.code == code)
                data_points = session.exec(statement).one()
        except Exception:
            data_points = 0

        return {
            "code": code,
            "name": code,  # 前端会从其他接口获取名称
            "current_scale": current_scale,
            "rank": rank_info,
            "historical_available": data_points > 1,
            "data_points": data_points,
        }


# 全局单例
fund_flow_service = FundFlowService()
