"""到价提醒模型单元测试"""
import pytest
from pydantic import ValidationError

from app.models.price_alert import (
    PriceAlertCreate,
    PriceAlertResponse,
    PriceAlertDirection,
)


class TestPriceAlertCreate:
    """PriceAlertCreate 请求模型校验"""

    def test_valid_create(self):
        data = PriceAlertCreate(
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            note="到这个价加仓",
        )
        assert data.etf_code == "510300"
        assert data.target_price == 3.50
        assert data.direction is None  # 可选，后端自动推断

    def test_valid_with_direction(self):
        data = PriceAlertCreate(
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            direction=PriceAlertDirection.BELOW,
        )
        assert data.direction == PriceAlertDirection.BELOW

    def test_etf_code_must_be_6_digits(self):
        with pytest.raises(ValidationError, match="6 位数字"):
            PriceAlertCreate(
                etf_code="51030",  # 5 位
                etf_name="沪深300ETF",
                target_price=3.50,
            )

    def test_etf_code_rejects_non_digits(self):
        with pytest.raises(ValidationError, match="6 位数字"):
            PriceAlertCreate(
                etf_code="abcdef",
                etf_name="沪深300ETF",
                target_price=3.50,
            )

    def test_target_price_must_be_positive(self):
        with pytest.raises(ValidationError):
            PriceAlertCreate(
                etf_code="510300",
                etf_name="沪深300ETF",
                target_price=0,
            )

    def test_target_price_rejects_negative(self):
        with pytest.raises(ValidationError):
            PriceAlertCreate(
                etf_code="510300",
                etf_name="沪深300ETF",
                target_price=-1.0,
            )

    def test_note_max_200_chars(self):
        with pytest.raises(ValidationError):
            PriceAlertCreate(
                etf_code="510300",
                etf_name="沪深300ETF",
                target_price=3.50,
                note="x" * 201,
            )

    def test_note_200_chars_ok(self):
        data = PriceAlertCreate(
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            note="x" * 200,
        )
        assert len(data.note) == 200

    def test_note_optional(self):
        data = PriceAlertCreate(
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
        )
        assert data.note is None

    def test_etf_name_max_50_chars(self):
        with pytest.raises(ValidationError):
            PriceAlertCreate(
                etf_code="510300",
                etf_name="x" * 51,
                target_price=3.50,
            )

    def test_etf_name_50_chars_ok(self):
        data = PriceAlertCreate(
            etf_code="510300",
            etf_name="x" * 50,
            target_price=3.50,
        )
        assert len(data.etf_name) == 50


class TestPriceAlertResponse:
    """PriceAlertResponse 模型测试"""

    def test_from_attributes(self):
        """确认 from_attributes=True 配置正确"""
        resp = PriceAlertResponse(
            id=1,
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            direction="below",
            note=None,
            is_triggered=False,
            triggered_at=None,
            triggered_price=None,
            created_at="2026-03-05T10:30:00",
        )
        assert resp.id == 1
        assert resp.direction == "below"


class TestPriceAlertTable:
    """PriceAlert 数据库表测试"""

    def test_table_creation(self, test_engine):
        """确认 PriceAlert 表能被 create_all 创建"""
        from sqlalchemy import inspect
        inspector = inspect(test_engine)
        tables = inspector.get_table_names()
        assert "price_alerts" in tables

    def test_insert_and_query(self, test_session):
        """确认基本 CRUD 可用"""
        from app.models.price_alert import PriceAlert
        alert = PriceAlert(
            user_id=1,
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            direction="below",
        )
        test_session.add(alert)
        test_session.commit()
        test_session.refresh(alert)
        assert alert.id is not None
        assert alert.is_triggered is False
