"""
通知服务模块

提供 Telegram 通知功能
"""

from telegram import Bot
from telegram.error import TelegramError
from typing import Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.alert_config import SignalItem


class TelegramNotificationService:
    """Telegram 通知服务"""

    @staticmethod
    async def send_message(bot_token: str, chat_id: str, message: str) -> bool:
        """
        发送 Telegram 消息

        Args:
            bot_token: Telegram Bot Token
            chat_id: 目标 Chat ID
            message: 消息内容（支持 HTML 格式）

        Returns:
            bool: 发送成功返回 True

        Raises:
            ValueError: Telegram API 调用失败时抛出
        """
        try:
            async with Bot(token=bot_token) as bot:
                await bot.send_message(chat_id=chat_id, text=message, parse_mode='HTML')
            return True
        except TelegramError as e:
            raise ValueError(f"Telegram API 错误: {str(e)}")

    @staticmethod
    async def test_connection(bot_token: str, chat_id: str) -> Dict[str, Any]:
        """
        测试 Telegram 连接

        发送测试消息以验证 Bot Token 和 Chat ID 是否正确配置

        Args:
            bot_token: Telegram Bot Token
            chat_id: 目标 Chat ID

        Returns:
            dict: 包含 success (bool) 和 message (str) 的字典
        """
        test_message = "🎉 <b>ETFTool 通知测试成功！</b>\n\n您的 Telegram Bot 已正确配置。"
        try:
            await TelegramNotificationService.send_message(
                bot_token, chat_id, test_message
            )
            return {"success": True, "message": "测试消息已发送"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @staticmethod
    def format_alert_message(signals: List["SignalItem"], check_time: str) -> str:
        """
        格式化告警消息

        Args:
            signals: SignalItem 列表
            check_time: 检查时间字符串 (HH:MM)

        Returns:
            格式化的 HTML 消息
        """
        high_priority = [s for s in signals if s.priority == "high"]
        medium_priority = [s for s in signals if s.priority == "medium"]

        lines = [f"📊 <b>ETF 信号提醒</b> ({check_time})", ""]

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
