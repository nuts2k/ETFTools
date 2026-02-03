"""
告警调度器服务

使用 APScheduler 管理定时任务
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session, select

from app.core.database import engine
from app.models.user import User, Watchlist
from app.models.alert_config import UserAlertPreferences, SignalItem
from app.services.alert_service import alert_service
from app.services.alert_state_service import alert_state_service
from app.services.notification_service import TelegramNotificationService
from app.services.akshare_service import ak_service
from app.services.temperature_service import temperature_service
from app.services.trend_service import trend_service
from app.core.encryption import decrypt_token
from app.core.config import settings

logger = logging.getLogger(__name__)


class AlertScheduler:
    """告警调度器"""

    def __init__(self):
        self._scheduler: Optional[AsyncIOScheduler] = None

    def start(self) -> None:
        """启动调度器（支持盘中和收盘检查）"""
        if self._scheduler is not None:
            return

        self._scheduler = AsyncIOScheduler()

        # 盘中检查 (每 30 分钟，09:00-14:30，周一到周五)
        self._scheduler.add_job(
            self._run_daily_check,
            CronTrigger(
                minute="0,30",      # 每小时的 0 分和 30 分
                hour="9-14",        # 9:00-14:59 之间
                day_of_week="mon-fri"
            ),
            id="intraday_alert_check",
            replace_existing=True,
        )
        logger.info("Intraday alert check scheduled: every 30 minutes (09:00-14:30)")

        # 收盘后检查 (每天 15:30)
        self._scheduler.add_job(
            self._run_daily_check,
            CronTrigger(hour=15, minute=30, day_of_week="mon-fri"),
            id="daily_alert_check",
            replace_existing=True,
        )
        logger.info("Daily alert check scheduled: 15:30")

        self._scheduler.start()
        logger.info("Alert scheduler started with intraday and daily checks")

    def stop(self) -> None:
        """停止调度器"""
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            logger.info("Alert scheduler stopped")

    async def _run_daily_check(self) -> None:
        """执行告警检查（优化版：按 ETF 去重）"""
        logger.info("Running alert check...")

        with Session(engine) as session:
            # 步骤 1: 收集所有需要检查的 ETF 及其关联用户
            etf_users_map = self._collect_etf_users(session)

            if not etf_users_map:
                logger.info("No ETFs to check")
                return

            logger.info(f"Checking {len(etf_users_map)} unique ETFs for alerts")

            # 步骤 2: 为每个用户收集信号
            user_signals_map: Dict[int, List[SignalItem]] = {}

            for etf_code, users_data in etf_users_map.items():
                try:
                    # 获取 ETF 数据并计算指标（每个 ETF 只计算一次）
                    df = await asyncio.to_thread(ak_service.fetch_etf_history, etf_code)
                    if df is None or df.empty:
                        logger.warning(f"No data for ETF {etf_code}")
                        continue

                    # 计算所有指标（只计算一次）
                    def compute_metrics():
                        return {
                            "temperature": temperature_service.calculate_temperature(df),
                            "daily_trend": trend_service.get_daily_trend(df),
                            "weekly_trend": trend_service.get_weekly_trend(df),
                        }
                    metrics = await asyncio.to_thread(compute_metrics)

                    # 为每个用户检测信号
                    for user_data in users_data:
                        user_id = user_data["user"].id
                        signals = alert_service.detect_signals(
                            user_id=user_id,
                            etf_code=etf_code,
                            etf_name=user_data["etf_name"],
                            current_metrics=metrics,
                            prefs=user_data["prefs"],
                        )

                        if signals:
                            # 更新状态
                            state = alert_service.build_current_state(etf_code, metrics)
                            alert_state_service.save_state(user_id, state)

                            # 标记信号已发送
                            for signal in signals:
                                alert_state_service.mark_signal_sent(
                                    user_id, etf_code, signal.signal_type
                                )

                            # 收集信号
                            if user_id not in user_signals_map:
                                user_signals_map[user_id] = []
                            user_signals_map[user_id].extend(signals)

                except Exception as e:
                    logger.error(f"Error processing ETF {etf_code}: {e}")
                    continue

            # 步骤 3: 为每个用户发送合并消息
            for user_id, signals in user_signals_map.items():
                try:
                    # 从 etf_users_map 中找到用户信息
                    user_info = self._find_user_info(etf_users_map, user_id)
                    if not user_info:
                        continue

                    # 检查每日告警数量限制
                    prefs = user_info["prefs"]
                    sent_count = alert_state_service.get_daily_sent_count(user_id)
                    remaining = prefs.max_alerts_per_day - sent_count

                    if remaining <= 0:
                        logger.info(f"User {user_id} reached daily alert limit ({sent_count} sent)")
                        continue

                    # 如果信号数量超过剩余配额，则截断
                    signals_to_send = signals[:remaining]
                    if len(signals) > remaining:
                        logger.info(f"User {user_id}: truncated {len(signals)} signals to {remaining}")

                    await self._send_alert_message(
                        user_info["user"],
                        user_info["telegram_config"],
                        signals_to_send,
                    )
                    logger.info(f"Sent {len(signals_to_send)} alerts to user {user_id}")
                except Exception as e:
                    logger.error(f"Error sending message to user {user_id}: {e}")

    def _collect_etf_users(self, session: Session) -> Dict[str, List[Dict]]:
        """
        收集所有需要检查的 ETF 及其关联用户

        Returns:
            {
                "510300": [
                    {"user": User对象, "etf_name": "沪深300ETF", "prefs": UserAlertPreferences对象, "telegram_config": dict},
                    ...
                ],
                "510500": [...]
            }
        """
        etf_users_map: Dict[str, List[Dict]] = {}

        # 获取所有用户
        users = session.exec(select(User)).all()

        for user in users:
            # 获取用户告警配置
            alert_settings = (user.settings or {}).get("alerts", {})
            prefs = UserAlertPreferences(**alert_settings)

            if not prefs.enabled:
                continue

            # 检查 Telegram 配置
            telegram_config = (user.settings or {}).get("telegram", {})
            if not telegram_config.get("enabled") or not telegram_config.get("verified"):
                continue

            # 获取用户自选股
            watchlist = session.exec(
                select(Watchlist).where(Watchlist.user_id == user.id)
            ).all()

            if not watchlist:
                continue

            for item in watchlist:
                etf_code = item.etf_code

                if etf_code not in etf_users_map:
                    etf_users_map[etf_code] = []

                etf_users_map[etf_code].append({
                    "user": user,
                    "etf_name": item.etf_name or etf_code,
                    "prefs": prefs,
                    "telegram_config": telegram_config,
                })

        return etf_users_map

    def _find_user_info(
        self,
        etf_users_map: Dict[str, List[Dict]],
        user_id: int
    ) -> Optional[Dict]:
        """从 ETF-用户映射中找到用户信息"""
        for users_data in etf_users_map.values():
            for user_data in users_data:
                if user_data["user"].id == user_id:
                    return user_data
        return None


    async def _send_alert_message(
        self,
        user: User,
        telegram_config: dict,
        signals: List[SignalItem],
    ) -> None:
        """发送告警消息"""
        bot_token = decrypt_token(telegram_config["botToken"], settings.SECRET_KEY)
        chat_id = telegram_config["chatId"]

        now = datetime.now().strftime("%H:%M")
        message = TelegramNotificationService.format_alert_message(signals, now)

        try:
            await TelegramNotificationService.send_message(bot_token, chat_id, message)
            logger.info(f"Sent {len(signals)} alerts to user {user.id}")
        except Exception as e:
            logger.error(f"Failed to send alert to user {user.id}: {e}")

    async def trigger_check(self) -> dict:
        """手动触发检查（用于测试）"""
        try:
            await self._run_daily_check()
            return {"success": True, "message": "检查完成"}
        except Exception as e:
            logger.error(f"Manual trigger failed: {e}")
            return {"success": False, "message": str(e)}


# 全局单例
alert_scheduler = AlertScheduler()
