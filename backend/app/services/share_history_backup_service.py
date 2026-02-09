"""
份额历史数据备份服务

提供 CSV 导出和定期备份功能
"""

import os
import logging
import calendar
from typing import Optional, Dict, Any
from datetime import datetime

import pandas as pd
from sqlmodel import Session, select

from app.core.share_history_database import share_history_engine
from app.models.etf_share_history import ETFShareHistory

logger = logging.getLogger(__name__)


class ShareHistoryBackupService:
    """份额历史数据备份服务"""

    def __init__(self):
        # 备份目录相对于 backend/ 目录
        backend_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        self.backup_dir = os.path.join(backend_dir, "backups", "share_history")

    def _ensure_backup_dir(self):
        """确保备份目录存在"""
        os.makedirs(self.backup_dir, exist_ok=True)

    def export_to_csv_bytes(
        self,
        start_date: str,
        end_date: str,
        codes: Optional[list] = None
    ) -> bytes:
        """
        导出指定日期范围的数据为 CSV bytes

        Args:
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            codes: 可选的 ETF 代码列表，None 表示全部

        Returns:
            CSV 格式的 bytes
        """
        try:
            with Session(share_history_engine) as session:
                statement = select(ETFShareHistory).where(
                    ETFShareHistory.date >= start_date,
                    ETFShareHistory.date <= end_date
                )

                if codes:
                    statement = statement.where(ETFShareHistory.code.in_(codes))

                records = session.exec(statement).all()

                # 转换为 DataFrame
                data = [
                    {
                        "code": r.code,
                        "date": r.date,
                        "shares": r.shares,
                        "exchange": r.exchange,
                        "etf_type": r.etf_type,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in records
                ]

                if data:
                    df = pd.DataFrame(data)
                else:
                    df = pd.DataFrame(columns=["code", "date", "shares", "exchange", "etf_type", "created_at"])

                # 转为 CSV bytes
                csv_str = df.to_csv(index=False)
                return csv_str.encode("utf-8")

        except Exception as e:
            logger.error(f"Failed to export CSV: {e}", exc_info=True)
            # 返回空 CSV（仅表头）
            df = pd.DataFrame(columns=["code", "date", "shares", "exchange", "etf_type", "created_at"])
            return df.to_csv(index=False).encode("utf-8")

    def export_monthly_backup(self, year: int, month: int) -> Dict[str, Any]:
        """
        导出指定月份的数据到文件

        Args:
            year: 年份
            month: 月份

        Returns:
            备份结果字典
        """
        try:
            self._ensure_backup_dir()

            # 计算日期范围（使用 calendar.monthrange 简化逻辑）
            start_date = f"{year}-{month:02d}-01"
            last_day = calendar.monthrange(year, month)[1]
            end_date = f"{year}-{month:02d}-{last_day:02d}"

            # 导出数据
            csv_bytes = self.export_to_csv_bytes(start_date, end_date)

            # 保存到文件
            filename = f"etf_share_history_{year}-{month:02d}.csv"
            filepath = os.path.join(self.backup_dir, filename)

            with open(filepath, "wb") as f:
                f.write(csv_bytes)

            logger.info(f"Monthly backup saved: {filepath}")

            return {
                "success": True,
                "filepath": filepath,
                "size_bytes": len(csv_bytes),
                "year": year,
                "month": month,
            }

        except Exception as e:
            logger.error(f"Failed to export monthly backup: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "year": year,
                "month": month,
            }


# 全局单例
share_history_backup_service = ShareHistoryBackupService()
