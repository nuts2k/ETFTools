"""
通知服务模块

提供 Telegram 通知功能
"""

from telegram import Bot
from telegram.error import TelegramError
from typing import Dict, Any, List

from app.models.alert_config import SignalPriority, SignalItem


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
        high_priority = [s for s in signals if s.priority == SignalPriority.HIGH]
        medium_priority = [s for s in signals if s.priority == SignalPriority.MEDIUM]

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

    @staticmethod
    def format_daily_summary(
        items: List[dict],
        signals: List[SignalItem],
        date_str: str
    ) -> str:
        """格式化每日摘要消息（HTML 格式）

        Args:
            items: ETF 数据列表，每项含 code, name, change_pct, temperature_score, temperature_level
            signals: 当日已触发的告警信号
            date_str: 日期字符串，如 "2026-02-07 (周五)"
        """
        lines = [f"📋 <b>自选日报</b> | {date_str}", ""]

        # 涨跌概览
        up = sum(1 for i in items if i["change_pct"] > 0)
        down = sum(1 for i in items if i["change_pct"] < 0)
        flat = len(items) - up - down
        lines.append(f"📊 涨: {up} | 跌: {down} | 平: {flat}")
        lines.append("")

        # 排序
        sorted_items = sorted(items, key=lambda x: x["change_pct"], reverse=True)

        def fmt_item(item: dict) -> str:
            pct = item["change_pct"]
            sign = "+" if pct > 0 else ""
            score = item.get("temperature_score")
            temp_str = f"  🌡️{score:.0f}" if score is not None else ""
            return f"• {item['name']} ({item['code']})  {sign}{pct:.2f}%{temp_str}"

        if len(items) <= 3:
            for item in sorted_items:
                lines.append(fmt_item(item))
            lines.append("")
        else:
            # 涨幅前三
            gainers = [i for i in sorted_items if i["change_pct"] > 0]
            if gainers:
                lines.append("🔴 <b>涨幅前三</b>")
                for item in gainers[:3]:
                    lines.append(fmt_item(item))
                lines.append("")

            # 跌幅前三
            losers = [i for i in sorted_items if i["change_pct"] < 0]
            if losers:
                lines.append("🟢 <b>跌幅前三</b>")
                for item in reversed(losers[-3:]):
                    lines.append(fmt_item(item))
                lines.append("")

        # 今日信号
        if signals:
            lines.append(f"⚡ <b>今日信号</b> ({len(signals)})")
            for s in signals:
                lines.append(f"• {s.etf_code} {s.etf_name}: {s.signal_detail}")
            lines.append("")

        # 温度分布
        level_counts = {"freezing": 0, "cool": 0, "warm": 0, "hot": 0}
        for item in items:
            level = item.get("temperature_level")
            if level and level in level_counts:
                level_counts[level] += 1
        level_icons = {"freezing": "🥶", "cool": "❄️", "warm": "☀️", "hot": "🔥"}
        dist_parts = [f"{level_icons[k]} {k}: {v}" for k, v in level_counts.items()]
        lines.append(f"🌡️ {' | '.join(dist_parts)}")

        return "\n".join(lines)
