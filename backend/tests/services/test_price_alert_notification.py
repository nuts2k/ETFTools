"""到价提醒通知消息格式化测试"""
import pytest
from datetime import datetime

from app.models.price_alert import PriceAlert
from app.services.notification_service import TelegramNotificationService


class TestFormatPriceAlertMessage:
    """format_price_alert_message() 测试"""

    def _make_alert(self, **kwargs):
        defaults = dict(
            id=1, user_id=1, etf_code="510300", etf_name="沪深300ETF",
            target_price=3.50, direction="below", note=None,
            is_triggered=True, triggered_price=3.48,
            triggered_at=datetime(2026, 3, 5, 6, 30),  # UTC
        )
        defaults.update(kwargs)
        return PriceAlert(**defaults)

    def test_single_below_no_note(self):
        alert = self._make_alert()
        msg = TelegramNotificationService.format_price_alert_message(
            [alert], datetime(2026, 3, 5, 14, 30)
        )
        assert "到价提醒" in msg
        assert "沪深300ETF" in msg
        assert "510300" in msg
        assert "<b>3.48</b>" in msg
        assert "跌破" in msg
        assert "3.5" in msg
        assert "📝" not in msg  # 无备注，不显示

    def test_single_above_with_note(self):
        alert = self._make_alert(
            direction="above", target_price=6.10, triggered_price=6.12,
            note="到这个价加仓 2000 元",
        )
        msg = TelegramNotificationService.format_price_alert_message(
            [alert], datetime(2026, 3, 5, 14, 30)
        )
        assert "突破" in msg
        assert "6.1" in msg
        assert "📝" in msg
        assert "到这个价加仓 2000 元" in msg

    def test_multiple_alerts(self):
        a1 = self._make_alert()
        a2 = self._make_alert(
            id=2, etf_code="510500", etf_name="中证500ETF",
            target_price=6.10, direction="above", triggered_price=6.12,
        )
        msg = TelegramNotificationService.format_price_alert_message(
            [a1, a2], datetime(2026, 3, 5, 14, 30)
        )
        assert "2 个触发" in msg
        assert "沪深300ETF" in msg
        assert "中证500ETF" in msg

    def test_html_escape_etf_name(self):
        alert = self._make_alert(etf_name="Test<script>ETF")
        msg = TelegramNotificationService.format_price_alert_message(
            [alert], datetime(2026, 3, 5, 14, 30)
        )
        assert "<script>" not in msg
        assert "&lt;script&gt;" in msg

    def test_html_escape_note(self):
        alert = self._make_alert(note='<b>恶意</b> & "注入"')
        msg = TelegramNotificationService.format_price_alert_message(
            [alert], datetime(2026, 3, 5, 14, 30)
        )
        assert "<b>恶意</b>" not in msg  # 用户 note 中的 <b> 被转义
        assert "&lt;b&gt;" in msg
