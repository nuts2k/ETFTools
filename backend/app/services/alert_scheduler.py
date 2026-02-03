"""
告警调度器服务

使用 APScheduler 管理定时任务
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Optional

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
        """启动调度器"""
        if self._scheduler is not None:
            return

        self._scheduler = AsyncIOScheduler()

        # 收盘后检查 (每天 15:30)
        self._scheduler.add_job(
            self._run_daily_check,
            CronTrigger(hour=15, minute=30, day_of_week="mon-fri"),
            id="daily_alert_check",
            replace_existing=True,
        )

        self._scheduler.start()
        logger.info("Alert scheduler started")

    def stop(self) -> None:
        """停止调度器"""
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            logger.info("Alert scheduler stopped")

    async def _run_daily_check(self) -> None:
        """执行每日告警检查"""
        logger.info("Running daily alert check...")

        with Session(engine) as session:
            # 获取所有用户，在内存中过滤启用告警的用户
            # 注：SQLite JSON 查询支持有限，使用内存过滤
            all_users = session.exec(select(User)).all()
            users = [
                u for u in all_users
                if (u.settings or {}).get("alerts", {}).get("enabled", True)
                and (u.settings or {}).get("telegram", {}).get("enabled")
                and (u.settings or {}).get("telegram", {}).get("verified")
            ]
            logger.info(f"Found {len(users)} users with alerts enabled")

            for user in users:
                try:
                    await self._check_user_alerts(session, user)
                except Exception as e:
                    logger.error(f"Error checking alerts for user {user.id}: {e}")

    async def _check_user_alerts(self, session: Session, user: User) -> None:
        """检查单个用户的告警"""
        # 获取用户告警配置
        alert_settings = (user.settings or {}).get("alerts", {})
        prefs = UserAlertPreferences(**alert_settings)

        if not prefs.enabled:
            return

        # 检查 Telegram 配置
        telegram_config = (user.settings or {}).get("telegram", {})
        if not telegram_config.get("enabled") or not telegram_config.get("verified"):
            return

        # 获取用户自选股
        watchlist = session.exec(
            select(Watchlist).where(Watchlist.user_id == user.id)
        ).all()

        if not watchlist:
            return

        all_signals: List[SignalItem] = []

        # 检查今日已发送数量
        sent_count = alert_state_service.get_daily_sent_count(user.id)
        remaining = prefs.max_alerts_per_day - sent_count
        if remaining <= 0:
            logger.info(f"User {user.id} reached daily alert limit")
            return

        for item in watchlist:
            try:
                signals = await self._check_etf_signals(
                    user.id, item.etf_code, item.etf_name or item.etf_code, prefs
                )
                all_signals.extend(signals)
            except Exception as e:
                logger.error(f"Error checking ETF {item.etf_code}: {e}")

        # 发送合并消息（限制数量）
        if all_signals:
            # 截断到剩余配额
            signals_to_send = all_signals[:remaining]
            if len(all_signals) > remaining:
                logger.info(
                    f"User {user.id}: truncated {len(all_signals)} signals to {remaining}"
                )
            await self._send_alert_message(user, telegram_config, signals_to_send)

    async def _check_etf_signals(
        self,
        user_id: int,
        etf_code: str,
        etf_name: str,
        prefs: UserAlertPreferences,
    ) -> List[SignalItem]:
        """检查单个 ETF 的信号"""
        # 获取历史数据（使用 asyncio.to_thread 避免阻塞事件循环）
        df = await asyncio.to_thread(ak_service.fetch_etf_history, etf_code)
        if df is None or df.empty:
            return []

        # 计算指标（同样使用线程池）
        def compute_metrics():
            return {
                "temperature": temperature_service.calculate_temperature(df),
                "daily_trend": trend_service.get_daily_trend(df),
                "weekly_trend": trend_service.get_weekly_trend(df),
            }
        metrics = await asyncio.to_thread(compute_metrics)

        # 检测信号
        signals = alert_service.detect_signals(
            user_id, etf_code, etf_name, metrics, prefs
        )

        # 无论是否有信号都更新状态（避免下次重复检测相同变化）
        state = alert_service.build_current_state(etf_code, metrics)
        alert_state_service.save_state(user_id, state)

        # 标记信号已发送
        for signal in signals:
            alert_state_service.mark_signal_sent(
                user_id, etf_code, signal.signal_type
            )

        return signals

    async def _send_alert_message(
        self,
        user: User,
        telegram_config: dict,
        signals: List[SignalItem],
    ) -> None:
        """发送告警消息"""
        bot_token = decrypt_token(telegram_config["botToken"], settings.SECRET_KEY)
        chat_id = telegram_config["chatId"]

        message = self._format_message(signals)

        try:
            await TelegramNotificationService.send_message(bot_token, chat_id, message)
            logger.info(f"Sent {len(signals)} alerts to user {user.id}")
        except Exception as e:
            logger.error(f"Failed to send alert to user {user.id}: {e}")

    def _format_message(self, signals: List[SignalItem]) -> str:
        """格式化告警消息"""
        now = datetime.now().strftime("%H:%M")

        high_priority = [s for s in signals if s.priority == "high"]
        medium_priority = [s for s in signals if s.priority == "medium"]

        lines = [f"📊 <b>ETF 信号提醒</b> ({now})", ""]

        if high_priority:
            lines.append("🔥 <b>高优先级:</b>")
            for s in high_priority:
                lines.append(f"• {s.etf_code} {s.etf_name}: {s.signal_detail}")
            lines.append("")

        if medium_priority:
            lines.append("📈 <b>中优先级:</b>")
            for s in medium_priority:
                lines.append(f"• {s.etf_code} {s.etf_name}: {s.signal_detail}")
            lines.append("")

        lines.append(f"共 {len(signals)} 个信号")

        return "\n".join(lines)

    async def trigger_check(self, user_id: int) -> dict:
        """手动触发检查（用于测试）"""
        with Session(engine) as session:
            user = session.get(User, user_id)
            if not user:
                return {"success": False, "message": "用户不存在"}

            try:
                await self._check_user_alerts(session, user)
                return {"success": True, "message": "检查完成"}
            except Exception as e:
                return {"success": False, "message": str(e)}


# 全局单例
alert_scheduler = AlertScheduler()
