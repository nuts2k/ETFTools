"""到价提醒调度器集成测试"""
import pytest
from datetime import datetime, timedelta
from sqlmodel import Session

from app.models.price_alert import PriceAlert
from app.services.price_alert_service import PriceAlertService


class TestPriceAlertSchedulerIntegration:
    """测试到价提醒在调度器中的检查和触发"""

    def test_trigger_alerts_updates_db(self, test_session, regular_user):
        """验证 trigger_alerts 正确更新数据库"""
        alert = PriceAlert(
            user_id=regular_user.id,
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            direction="below",
        )
        test_session.add(alert)
        test_session.commit()

        triggered = PriceAlertService.trigger_alerts(
            test_session,
            [alert],
            {"510300": 3.48},
        )
        assert len(triggered) == 1
        assert triggered[0].is_triggered is True
        assert triggered[0].triggered_price == 3.48
        assert triggered[0].triggered_at is not None

        # 再次查询确认已持久化
        refreshed = test_session.get(PriceAlert, alert.id)
        assert refreshed.is_triggered is True

    def test_triggered_alert_not_in_active_list(self, test_session, regular_user):
        """已触发的提醒不再出现在活跃列表中"""
        alert = PriceAlert(
            user_id=regular_user.id,
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            direction="below",
            is_triggered=True,
        )
        test_session.add(alert)
        test_session.commit()

        active = PriceAlertService.get_all_active_alerts(test_session)
        assert len(active) == 0

    def test_cleanup_old_triggered(self, test_session, regular_user):
        """30 天自动清理已触发的记录"""
        old = PriceAlert(
            user_id=regular_user.id,
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            direction="below",
            is_triggered=True,
            triggered_at=datetime.utcnow() - timedelta(days=31),
            triggered_price=3.48,
        )
        recent = PriceAlert(
            user_id=regular_user.id,
            etf_code="510500",
            etf_name="中证500ETF",
            target_price=6.10,
            direction="above",
            is_triggered=True,
            triggered_at=datetime.utcnow() - timedelta(days=5),
            triggered_price=6.12,
        )
        test_session.add_all([old, recent])
        test_session.commit()

        deleted_count = PriceAlertService.cleanup_old_triggered(test_session)
        assert deleted_count == 1

        # 近期记录应保留
        remaining = test_session.get(PriceAlert, recent.id)
        assert remaining is not None
