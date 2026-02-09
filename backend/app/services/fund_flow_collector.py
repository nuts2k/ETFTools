"""
资金流向采集服务

使用 APScheduler 定时采集上交所和深交所的 ETF 份额数据
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from zoneinfo import ZoneInfo

import pandas as pd
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session
from sqlalchemy.exc import IntegrityError

from app.core.share_history_database import share_history_engine
from app.models.etf_share_history import ETFShareHistory

logger = logging.getLogger(__name__)


class FundFlowCollector:
    """ETF 份额数据采集器"""

    # 列名映射（akshare 返回的列名 -> 数据库字段名）
    COLUMN_MAP_SSE = {
        "基金代码": "code",
        "基金份额": "shares",
        "统计日期": "date",
        "ETF类型": "etf_type",
    }

    COLUMN_MAP_SZSE = {
        "基金代码": "code",
        "基金份额": "shares",
        "基金类别": "etf_type",
    }

    def __init__(self):
        self._scheduler: Optional[AsyncIOScheduler] = None

    def _fetch_sse_shares(self) -> Optional[pd.DataFrame]:
        """
        获取上交所 ETF 份额数据

        Returns:
            DataFrame 或 None（失败时）
        """
        try:
            import akshare as ak
            df = ak.fund_etf_scale_sse()
            if df is None or df.empty:
                logger.warning("SSE data is empty")
                return None
            logger.info(f"Fetched {len(df)} records from SSE")
            return df
        except Exception as e:
            logger.error(f"Failed to fetch SSE shares: {e}", exc_info=True)
            return None

    def _fetch_szse_shares(self) -> Optional[pd.DataFrame]:
        """
        获取深交所 ETF 份额数据

        Returns:
            DataFrame 或 None（失败时）
        """
        try:
            import akshare as ak
            df = ak.fund_etf_scale_szse()
            if df is None or df.empty:
                logger.warning("SZSE data is empty")
                return None
            logger.info(f"Fetched {len(df)} records from SZSE")
            return df
        except Exception as e:
            logger.error(f"Failed to fetch SZSE shares: {e}", exc_info=True)
            return None

    def _save_to_database(
        self, df: pd.DataFrame, exchange: str, column_map: Dict[str, str]
    ) -> int:
        """
        保存数据到数据库

        Args:
            df: 原始 DataFrame
            exchange: 交易所代码 "SSE" 或 "SZSE"
            column_map: 列名映射字典

        Returns:
            成功插入的行数
        """
        if df is None or df.empty:
            return 0

        # 标准化列名
        df_renamed = df.rename(columns=column_map)

        # 检查必需列（date 可选，SZSE 无此列）
        required_cols = ["code", "shares"]
        if not all(col in df_renamed.columns for col in required_cols):
            logger.error(f"Missing required columns in {exchange} data, got: {list(df_renamed.columns)}")
            return 0

        # SZSE 无日期列，使用当天日期
        if "date" not in df_renamed.columns:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d")
            df_renamed["date"] = today

        # 份额单位转换：份 -> 亿份
        # 注意：akshare 返回的单位是"份"，需要除以 1e8 转换为"亿份"
        df_renamed["shares"] = pd.to_numeric(df_renamed["shares"], errors="coerce") / 1e8

        # 数据验证：检查无效的份额数据
        invalid_shares = df_renamed[df_renamed["shares"].isna()]
        if not invalid_shares.empty:
            invalid_codes = invalid_shares["code"].tolist()
            logger.warning(
                f"[{exchange}] Invalid shares data for {len(invalid_codes)} ETFs: {invalid_codes[:10]}"
                + (f" (and {len(invalid_codes) - 10} more)" if len(invalid_codes) > 10 else "")
            )

        success_count = 0
        with Session(share_history_engine) as session:
            for _, row in df_renamed.iterrows():
                try:
                    shares_val = float(row["shares"])
                    if pd.isna(shares_val) or shares_val <= 0:
                        continue
                    record = ETFShareHistory(
                        code=str(row["code"]),
                        date=str(row["date"]),
                        shares=shares_val,
                        exchange=exchange,
                        etf_type=str(row.get("etf_type", "")) if pd.notna(row.get("etf_type")) else None,
                    )
                    session.add(record)
                    session.commit()
                    success_count += 1
                except IntegrityError:
                    # UniqueConstraint 冲突，跳过重复数据
                    session.rollback()
                    continue
                except Exception as e:
                    logger.error(f"Failed to insert record {row.get('code')}: {e}")
                    session.rollback()
                    continue

        logger.info(f"Saved {success_count} records from {exchange}")
        return success_count

    def collect_daily_snapshot(self) -> Dict[str, Any]:
        """
        执行每日份额数据采集

        Returns:
            采集结果字典
        """
        logger.info("Starting daily ETF share collection...")

        sse_df = self._fetch_sse_shares()
        szse_df = self._fetch_szse_shares()

        sse_count = self._save_to_database(sse_df, "SSE", self.COLUMN_MAP_SSE) if sse_df is not None else 0
        szse_count = self._save_to_database(szse_df, "SZSE", self.COLUMN_MAP_SZSE) if szse_df is not None else 0

        total_collected = sse_count + szse_count
        total_failed = 0

        if sse_df is None:
            total_failed += 1
        if szse_df is None:
            total_failed += 1

        success = total_collected > 0
        message = f"Collected {total_collected} records (SSE: {sse_count}, SZSE: {szse_count})"

        if total_failed > 0:
            message += f", {total_failed} exchange(s) failed"

        logger.info(message)

        return {
            "success": success,
            "collected": total_collected,
            "failed": total_failed,
            "message": message,
        }

    async def _run_daily_collection(self):
        """定时任务：每日采集"""
        await asyncio.to_thread(self.collect_daily_snapshot)

    async def _run_monthly_backup(self):
        """定时任务：每月备份"""
        try:
            from app.services.share_history_backup_service import share_history_backup_service
            from datetime import datetime
            from dateutil.relativedelta import relativedelta

            # 导出上个月数据
            now = datetime.now(ZoneInfo("Asia/Shanghai"))
            last_month = now - relativedelta(months=1)
            year = last_month.year
            month = last_month.month

            result = await asyncio.to_thread(
                share_history_backup_service.export_monthly_backup, year, month
            )
            logger.info(f"Monthly backup completed: {result}")
        except Exception as e:
            logger.error(f"Monthly backup failed: {e}", exc_info=True)

    def start(self) -> None:
        """启动调度器"""
        if self._scheduler is not None:
            return

        self._scheduler = AsyncIOScheduler()

        # 每日采集 16:00 北京时间（周一至周五）
        # 失败重试：misfire_grace_time=300 允许延迟5分钟内仍执行
        # max_instances=1 防止重复执行
        self._scheduler.add_job(
            self._run_daily_collection,
            CronTrigger(
                hour=16,
                minute=0,
                day_of_week="mon-fri",
                timezone=ZoneInfo("Asia/Shanghai")
            ),
            id="fund_flow_daily_collection",
            replace_existing=True,
            misfire_grace_time=300,  # 5分钟容错时间
            max_instances=1,
        )
        logger.info("Daily ETF share collection scheduled: 16:00 Beijing Time (Mon-Fri) with 5min grace time")

        # 每月备份 每月1号 02:00
        self._scheduler.add_job(
            self._run_monthly_backup,
            CronTrigger(
                hour=2,
                minute=0,
                day=1,
                timezone=ZoneInfo("Asia/Shanghai")
            ),
            id="fund_flow_monthly_backup",
            replace_existing=True,
        )
        logger.info("Monthly backup scheduled: 02:00 on 1st of each month")

        self._scheduler.start()
        logger.info("Fund flow collector scheduler started")

    def stop(self) -> None:
        """停止调度器"""
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            logger.info("Fund flow collector scheduler stopped")


# 全局单例
fund_flow_collector = FundFlowCollector()
