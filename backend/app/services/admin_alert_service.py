"""
管理员告警广播服务

向所有已配置 Telegram 的管理员发送系统级告警（如数据源全部不可用）。
复用现有 TelegramNotificationService，带防抖机制。
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict

from zoneinfo import ZoneInfo

from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import engine
from app.core.encryption import decrypt_token
from app.models.user import User
from app.services.notification_service import TelegramNotificationService

logger = logging.getLogger(__name__)

_CHINA_TZ = ZoneInfo("Asia/Shanghai")


class AdminAlertService:
    """管理员告警广播服务"""

    COOLDOWN_SECONDS = 300  # 5 分钟防抖

    def __init__(self) -> None:
        self._cooldowns: Dict[str, datetime] = {}

    def _is_cooled_down(self, alert_type: str) -> bool:
        """检查是否在冷却期内"""
        last_sent = self._cooldowns.get(alert_type)
        if not last_sent:
            return True
        elapsed = (datetime.now(_CHINA_TZ) - last_sent).total_seconds()
        return elapsed >= self.COOLDOWN_SECONDS

    @staticmethod
    def _format_system_alert(alert_type: str, detail: str) -> str:
        """格式化系统告警消息（HTML）"""
        now_str = datetime.now(_CHINA_TZ).strftime("%Y-%m-%d %H:%M:%S")

        if alert_type == "all_sources_down":
            return (
                "🚨 <b>系统告警</b>\n\n"
                f"<b>类型</b>: 所有数据源不可用\n"
                f"<b>时间</b>: {now_str}\n"
                f"<b>详情</b>: {detail}\n\n"
                "请检查网络连接和数据源状态。"
            )
        elif alert_type == "source_recovered":
            return (
                "✅ <b>数据源恢复</b>\n\n"
                f"<b>时间</b>: {now_str}\n"
                f"<b>详情</b>: {detail}"
            )
        else:
            return (
                f"⚠️ <b>系统通知</b>\n\n"
                f"<b>类型</b>: {alert_type}\n"
                f"<b>时间</b>: {now_str}\n"
                f"<b>详情</b>: {detail}"
            )

    def send_admin_alert_sync(self, alert_type: str, detail: str) -> int:
        """
        同步发送管理员告警（适用于后台线程调用）。

        Args:
            alert_type: 告警类型，如 "all_sources_down", "source_recovered"
            detail: 告警详情

        Returns:
            成功发送的管理员数量
        """
        if not self._is_cooled_down(alert_type):
            logger.debug("Admin alert '%s' is in cooldown, skipping", alert_type)
            return 0

        message = self._format_system_alert(alert_type, detail)
        admins = self._get_telegram_admins()

        if not admins:
            logger.info("No admin users with verified Telegram config, skipping alert")
            return 0

        sent_count = 0
        for admin in admins:
            try:
                bot_token = decrypt_token(
                    admin["bot_token_encrypted"], settings.SECRET_KEY
                )
                coro = TelegramNotificationService.send_message(
                    bot_token, admin["chat_id"], message
                )
                try:
                    loop = asyncio.get_running_loop()
                    # 已在异步上下文中，调度为 task
                    loop.create_task(coro)
                except RuntimeError:
                    # 无事件循环（后台线程），安全使用 asyncio.run
                    asyncio.run(coro)
                sent_count += 1
                logger.info(
                    "Admin alert '%s' sent to user %d", alert_type, admin["user_id"]
                )
            except Exception as e:
                logger.error(
                    "Failed to send admin alert to user %d: %s",
                    admin["user_id"],
                    e,
                )

        if sent_count > 0:
            self._cooldowns[alert_type] = datetime.now(_CHINA_TZ)

        return sent_count

    @staticmethod
    def _get_telegram_admins() -> list:
        """查询所有已配置且验证 Telegram 的管理员用户"""
        admins = []
        try:
            with Session(engine) as session:
                users = session.exec(
                    select(User).where(User.is_admin == True, User.is_active == True)
                ).all()
                for user in users:
                    telegram_config = (user.settings or {}).get("telegram", {})
                    if (
                        telegram_config.get("enabled")
                        and telegram_config.get("verified")
                        and telegram_config.get("botToken")
                        and telegram_config.get("chatId")
                    ):
                        admins.append(
                            {
                                "user_id": user.id,
                                "bot_token_encrypted": telegram_config["botToken"],
                                "chat_id": telegram_config["chatId"],
                            }
                        )
        except Exception as e:
            logger.error("Failed to query admin users: %s", e)
        return admins


# 模块级单例
admin_alert_service = AdminAlertService()
