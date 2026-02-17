"""
资金流向采集服务

通过 Sina 白名单 + EastMoney 份额 + 深交所补充 三步管线采集 ETF 份额数据，
使用 APScheduler 定时调度。
"""

import asyncio
import logging
import time
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

    def __init__(self):
        self._scheduler: Optional[AsyncIOScheduler] = None

    def _build_etf_whitelist(self) -> Optional[set]:
        """
        从 Sina 列表接口构建 ETF 白名单（过滤债券 ETF）

        Returns:
            ETF 代码集合（如 {"510300", "159915", ...}），失败时返回 None
        """
        import akshare as ak
        try:
            logger.info("Building ETF whitelist from Sina list...")
            df = ak.fund_etf_category_sina(symbol="ETF基金")
            if df is None or df.empty:
                logger.warning("Sina list is empty")
                return None

            # 清理代码：去掉 sh/sz 前缀
            df["代码"] = df["代码"].astype(str).str.replace(r"^(sh|sz)", "", regex=True)

            # 过滤债券 ETF：代码段 51/52/53/56/58 且名称含"债"
            mask_bond = (
                df["代码"].str.match(r"^(51|52|53|56|58)")
                & df["名称"].str.contains("债", na=False)
            )
            df_filtered = df[~mask_bond]

            whitelist = set(df_filtered["代码"].astype(str))
            logger.info(f"ETF whitelist built: {len(whitelist)} codes (filtered {mask_bond.sum()} bond ETFs)")
            return whitelist

        except Exception as e:
            logger.error(f"Failed to build ETF whitelist: {e}")
            return None

    def _fetch_em_shares(self, whitelist: set) -> Optional[pd.DataFrame]:
        """
        从 EastMoney 列表接口获取 ETF 份额数据（最多重试 3 次）

        Args:
            whitelist: ETF 代码白名单

        Returns:
            标准化 DataFrame（columns: code, shares, date, etf_type），失败时返回 None
        """
        import akshare as ak
        for attempt in range(3):
            try:
                logger.info(f"Fetching EastMoney shares (attempt {attempt + 1}/3)...")
                df = ak.fund_etf_spot_em()
                if df is None or df.empty:
                    logger.warning("EastMoney data is empty")
                    continue

                # 白名单过滤
                df["代码"] = df["代码"].astype(str)
                df = df[df["代码"].isin(whitelist)]

                # 标准化列名和单位
                result = pd.DataFrame({
                    "code": df["代码"].values,
                    "shares": pd.to_numeric(df["最新份额"], errors="coerce") / 1e8,
                    "date": df["数据日期"].astype(str).values,
                })
                result["etf_type"] = None

                logger.info(f"Fetched {len(result)} ETF shares from EastMoney")
                return result

            except Exception as e:
                logger.warning(f"EastMoney fetch attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    time.sleep(3)

        logger.error("Failed to fetch EastMoney shares after 3 attempts")
        return None

    def _fetch_szse_shares(self, whitelist: Optional[set] = None) -> Optional[pd.DataFrame]:
        """
        获取深交所 ETF 份额数据（最多重试 3 次，间隔 3 秒）

        Args:
            whitelist: ETF 代码白名单（可选，传入时过滤非白名单代码）

        Returns:
            标准化 DataFrame（columns: code, shares, date, etf_type），失败时返回 None
        """
        import akshare as ak
        for attempt in range(3):
            try:
                logger.info(f"Fetching SZSE shares (attempt {attempt + 1}/3)...")
                df = ak.fund_etf_scale_szse()
                if df is None or df.empty:
                    logger.warning("SZSE data is empty")
                    continue

                # 只保留 ETF（排除 LOF）
                df = df[df["基金类别"] == "ETF"].copy()

                # 清理代码
                df["基金代码"] = df["基金代码"].astype(str).str.replace(r"^(sh|sz)", "", regex=True)

                # 白名单过滤
                if whitelist:
                    df = df[df["基金代码"].isin(whitelist)]

                # 标准化列名和单位
                today = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d")
                result = pd.DataFrame({
                    "code": df["基金代码"].values,
                    "shares": pd.to_numeric(df["基金份额"], errors="coerce") / 1e8,
                    "date": today,
                    "etf_type": df["基金类别"].values if "基金类别" in df.columns else None,
                })

                logger.info(f"Fetched {len(result)} records from SZSE")
                return result

            except Exception as e:
                logger.warning(f"SZSE fetch attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    time.sleep(3)

        logger.error("Failed to fetch SZSE shares after 3 attempts")
        return None

    def _save_to_database(self, df: pd.DataFrame) -> int:
        """
        保存标准化数据到数据库

        Args:
            df: 标准化 DataFrame（columns: code, shares, date, etf_type）

        Returns:
            成功插入的行数
        """
        if df is None or df.empty:
            return 0

        success_count = 0
        with Session(share_history_engine) as session:
            for _, row in df.iterrows():
                try:
                    shares_val = float(row["shares"])
                    if pd.isna(shares_val) or shares_val <= 0:
                        continue

                    code = str(row["code"])
                    # 根据代码前缀判断交易所
                    exchange = "SZSE" if code.startswith(("15", "16", "12")) else "SSE"

                    record = ETFShareHistory(
                        code=code,
                        date=str(row["date"]),
                        shares=shares_val,
                        exchange=exchange,
                        etf_type=str(row.get("etf_type", "")) if pd.notna(row.get("etf_type")) else None,
                    )
                    nested = session.begin_nested()
                    session.add(record)
                    nested.commit()
                    success_count += 1
                except IntegrityError:
                    nested.rollback()
                    continue
                except Exception as e:
                    logger.error(f"Failed to insert record {row.get('code')}: {e}")
                    nested.rollback()
                    continue

            session.commit()

        logger.info(f"Saved {success_count} records to database")
        return success_count

    def collect_daily_snapshot(self) -> Dict[str, Any]:
        """
        执行每日份额数据采集

        流程：
        1. 从 Sina 列表构建 ETF 白名单
        2. 从 EastMoney 获取份额数据（主力）
        3. 从深交所官方获取深市数据（补充，覆盖 EastMoney 深市部分）
        4. 合并并保存到数据库

        Returns:
            采集结果字典
        """
        logger.info("Starting daily ETF share collection...")

        # 1. 构建白名单
        whitelist = self._build_etf_whitelist()
        if whitelist is None:
            logger.error("Failed to build ETF whitelist, aborting collection")
            return {
                "success": False,
                "collected": 0,
                "failed": 1,
                "message": "Failed to build ETF whitelist",
            }

        # 2. 获取 EastMoney 份额数据
        em_df = self._fetch_em_shares(whitelist)

        # 3. 获取深交所官方数据
        szse_df = self._fetch_szse_shares(whitelist)

        # 4. 合并数据：同一 (code, date) 以 SZSE 为准
        if em_df is not None and szse_df is not None:
            szse_keys = set(zip(szse_df["code"], szse_df["date"]))
            em_keep = [k not in szse_keys for k in zip(em_df["code"], em_df["date"])]
            merged_df = pd.concat(
                [em_df[em_keep], szse_df],
                ignore_index=True,
            )
        elif em_df is not None:
            merged_df = em_df
        elif szse_df is not None:
            merged_df = szse_df
        else:
            logger.error("All data sources failed")
            return {
                "success": False,
                "collected": 0,
                "failed": 1,
                "message": "All data sources failed",
            }

        # 5. 保存到数据库
        total_collected = self._save_to_database(merged_df)

        sources = []
        if em_df is not None:
            sources.append(f"EastMoney: {len(em_df)}")
        if szse_df is not None:
            sources.append(f"SZSE: {len(szse_df)}")

        message = f"Collected {total_collected} records ({', '.join(sources)})"
        logger.info(message)

        return {
            "success": total_collected > 0,
            "collected": total_collected,
            "failed": 0 if em_df is not None else 1,
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
