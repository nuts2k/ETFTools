"""到价提醒业务逻辑测试"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from sqlmodel import Session

from app.models.price_alert import PriceAlert, PriceAlertCreate, PriceAlertDirection
from app.services.price_alert_service import PriceAlertService


class TestShouldTrigger:
    """_should_trigger() 触发条件判断测试"""

    def test_below_triggers_when_price_at_target(self):
        alert = PriceAlert(
            id=1, user_id=1, etf_code="510300", etf_name="沪深300ETF",
            target_price=3.50, direction="below",
        )
        assert PriceAlertService._should_trigger(alert, 3.50) is True

    def test_below_triggers_when_price_below_target(self):
        alert = PriceAlert(
            id=1, user_id=1, etf_code="510300", etf_name="沪深300ETF",
            target_price=3.50, direction="below",
        )
        assert PriceAlertService._should_trigger(alert, 3.48) is True

    def test_below_not_triggers_when_price_above_target(self):
        alert = PriceAlert(
            id=1, user_id=1, etf_code="510300", etf_name="沪深300ETF",
            target_price=3.50, direction="below",
        )
        assert PriceAlertService._should_trigger(alert, 3.52) is False

    def test_above_triggers_when_price_at_target(self):
        alert = PriceAlert(
            id=1, user_id=1, etf_code="510300", etf_name="沪深300ETF",
            target_price=6.10, direction="above",
        )
        assert PriceAlertService._should_trigger(alert, 6.10) is True

    def test_above_triggers_when_price_above_target(self):
        alert = PriceAlert(
            id=1, user_id=1, etf_code="510300", etf_name="沪深300ETF",
            target_price=6.10, direction="above",
        )
        assert PriceAlertService._should_trigger(alert, 6.12) is True

    def test_above_not_triggers_when_price_below_target(self):
        alert = PriceAlert(
            id=1, user_id=1, etf_code="510300", etf_name="沪深300ETF",
            target_price=6.10, direction="above",
        )
        assert PriceAlertService._should_trigger(alert, 6.08) is False

    def test_float_epsilon_below(self):
        """浮点容差: 3.5000001 应该触发 below 3.50"""
        alert = PriceAlert(
            id=1, user_id=1, etf_code="510300", etf_name="沪深300ETF",
            target_price=3.50, direction="below",
        )
        assert PriceAlertService._should_trigger(alert, 3.5000001) is True

    def test_float_epsilon_above(self):
        """浮点容差: 6.0999999 应该触发 above 6.10"""
        alert = PriceAlert(
            id=1, user_id=1, etf_code="510300", etf_name="沪深300ETF",
            target_price=6.10, direction="above",
        )
        assert PriceAlertService._should_trigger(alert, 6.0999999) is True


class TestInferDirection:
    """方向自动推断测试"""

    def test_target_below_current_infers_below(self):
        assert PriceAlertService._infer_direction(3.40, 3.52) == PriceAlertDirection.BELOW

    def test_target_above_current_infers_above(self):
        assert PriceAlertService._infer_direction(6.20, 6.10) == PriceAlertDirection.ABOVE

    def test_target_equals_current_is_rejected(self):
        """目标价=当前价时，无论推断方向如何，创建时都会被拒绝"""
        result = PriceAlertService._infer_direction(3.50, 3.50)
        assert result in (PriceAlertDirection.ABOVE, PriceAlertDirection.BELOW)
        # 无论推断为哪个方向，_check_price_condition 都应返回 True
        assert PriceAlertService._check_price_condition(result, 3.50, 3.50) is True


class TestCheckPriceCondition:
    """创建时条件已满足检查"""

    def test_below_already_met(self):
        """当前价 3.48 已经 <= 目标价 3.50，条件已满足"""
        assert PriceAlertService._check_price_condition("below", 3.50, 3.48) is True

    def test_below_not_met(self):
        """当前价 3.52 > 目标价 3.50，条件未满足"""
        assert PriceAlertService._check_price_condition("below", 3.50, 3.52) is False

    def test_above_already_met(self):
        """当前价 6.12 已经 >= 目标价 6.10，条件已满足"""
        assert PriceAlertService._check_price_condition("above", 6.10, 6.12) is True

    def test_above_not_met(self):
        """当前价 6.08 < 目标价 6.10，条件未满足"""
        assert PriceAlertService._check_price_condition("above", 6.10, 6.08) is False

    def test_equal_price_is_met(self):
        """当前价=目标价，条件已满足"""
        assert PriceAlertService._check_price_condition("below", 3.50, 3.50) is True
        assert PriceAlertService._check_price_condition("above", 3.50, 3.50) is True


class TestCreateAlert:
    """创建提醒的数据库测试"""

    def test_create_success(self, test_session, regular_user):
        data = PriceAlertCreate(
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.40,
        )
        alert = PriceAlertService.create_alert(
            test_session, regular_user.id, data, current_price=3.52
        )
        assert alert.id is not None
        assert alert.direction == "below"  # 3.40 < 3.52 -> below
        assert alert.is_triggered is False

    def test_create_with_explicit_direction(self, test_session, regular_user):
        data = PriceAlertCreate(
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.40,
            direction=PriceAlertDirection.ABOVE,
        )
        # 3.52 >= 3.40 - EPSILON 为 True，所以条件已满足，应该被拒绝
        with pytest.raises(ValueError, match="已满足"):
            PriceAlertService.create_alert(
                test_session, regular_user.id, data, current_price=3.52
            )

    def test_create_rejects_already_met_below(self, test_session, regular_user):
        data = PriceAlertCreate(
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            direction=PriceAlertDirection.BELOW,
        )
        with pytest.raises(ValueError, match="已满足"):
            PriceAlertService.create_alert(
                test_session, regular_user.id, data, current_price=3.48
            )

    def test_create_rejects_already_met_above(self, test_session, regular_user):
        data = PriceAlertCreate(
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=6.10,
            direction=PriceAlertDirection.ABOVE,
        )
        with pytest.raises(ValueError, match="已满足"):
            PriceAlertService.create_alert(
                test_session, regular_user.id, data, current_price=6.12
            )

    def test_create_rejects_at_limit(self, test_session, regular_user):
        """创建第 21 个提醒应被拒绝"""
        for i in range(20):
            alert = PriceAlert(
                user_id=regular_user.id,
                etf_code=f"{510300 + i:06d}",
                etf_name=f"ETF-{i}",
                target_price=float(i + 1),
                direction="below",
            )
            test_session.add(alert)
        test_session.commit()

        data = PriceAlertCreate(
            etf_code="510399",
            etf_name="ETF-extra",
            target_price=1.0,
        )
        with pytest.raises(ValueError, match="上限"):
            PriceAlertService.create_alert(
                test_session, regular_user.id, data, current_price=2.0
            )


class TestDeleteAlert:
    """删除提醒测试"""

    def test_delete_own_alert(self, test_session, regular_user):
        alert = PriceAlert(
            user_id=regular_user.id,
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            direction="below",
        )
        test_session.add(alert)
        test_session.commit()
        test_session.refresh(alert)

        result = PriceAlertService.delete_alert(
            test_session, alert.id, regular_user.id
        )
        assert result is True

    def test_cannot_delete_others_alert(self, test_session, regular_user, admin_user):
        alert = PriceAlert(
            user_id=admin_user.id,  # 管理员创建的
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            direction="below",
        )
        test_session.add(alert)
        test_session.commit()
        test_session.refresh(alert)

        result = PriceAlertService.delete_alert(
            test_session, alert.id, regular_user.id  # 普通用户尝试删除
        )
        assert result is False

    def test_delete_nonexistent(self, test_session, regular_user):
        result = PriceAlertService.delete_alert(
            test_session, 99999, regular_user.id
        )
        assert result is False


class TestTriggerAlerts:
    """trigger_alerts() 批量触发测试"""

    def test_trigger_matching_alerts(self, test_session, regular_user):
        a1 = PriceAlert(
            user_id=regular_user.id,
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            direction="below",
        )
        a2 = PriceAlert(
            user_id=regular_user.id,
            etf_code="510500",
            etf_name="中证500ETF",
            target_price=6.10,
            direction="above",
        )
        test_session.add_all([a1, a2])
        test_session.commit()

        # 510300 当前 3.48 <= 3.50 (below 触发)
        # 510500 当前 6.08 < 6.10 (above 不触发)
        triggered = PriceAlertService.trigger_alerts(
            test_session,
            [a1, a2],
            {"510300": 3.48, "510500": 6.08},
        )
        assert len(triggered) == 1
        assert triggered[0].etf_code == "510300"
        assert triggered[0].is_triggered is True
        assert triggered[0].triggered_price == 3.48

    def test_skip_missing_price(self, test_session, regular_user):
        a = PriceAlert(
            user_id=regular_user.id,
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            direction="below",
        )
        test_session.add(a)
        test_session.commit()

        triggered = PriceAlertService.trigger_alerts(
            test_session, [a], {}  # 无价格数据
        )
        assert len(triggered) == 0
        assert a.is_triggered is False
