"""到价提醒 API 端点测试"""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.models.price_alert import PriceAlert


class TestGetPriceAlerts:
    """GET /api/v1/price-alerts"""

    def test_empty_list(self, user_client: TestClient):
        resp = user_client.get("/api/v1/price-alerts")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_user_alerts(self, user_client, test_session, regular_user):
        alert = PriceAlert(
            user_id=regular_user.id,
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            direction="below",
        )
        test_session.add(alert)
        test_session.commit()

        resp = user_client.get("/api/v1/price-alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["etf_code"] == "510300"

    def test_active_only_filter(self, user_client, test_session, regular_user):
        active = PriceAlert(
            user_id=regular_user.id,
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            direction="below",
        )
        triggered = PriceAlert(
            user_id=regular_user.id,
            etf_code="510500",
            etf_name="中证500ETF",
            target_price=6.10,
            direction="above",
            is_triggered=True,
        )
        test_session.add_all([active, triggered])
        test_session.commit()

        resp = user_client.get("/api/v1/price-alerts?active_only=true")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["etf_code"] == "510300"

    def test_unauthenticated(self, client):
        resp = client.get("/api/v1/price-alerts")
        assert resp.status_code == 401


class TestCreatePriceAlert:
    """POST /api/v1/price-alerts"""

    @patch("app.api.v1.endpoints.price_alerts._get_current_etf_price")
    def test_create_success(self, mock_price, user_client, test_session, regular_user):
        mock_price.return_value = 3.52

        # 给用户配置 Telegram
        regular_user.settings = {
            "telegram": {"enabled": True, "verified": True, "botToken": "enc", "chatId": "123"}
        }
        test_session.commit()

        resp = user_client.post("/api/v1/price-alerts", json={
            "etf_code": "510300",
            "etf_name": "沪深300ETF",
            "target_price": 3.40,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["direction"] == "below"
        assert data["is_triggered"] is False

    @patch("app.api.v1.endpoints.price_alerts._get_current_etf_price")
    def test_create_rejects_already_met(self, mock_price, user_client, test_session, regular_user):
        mock_price.return_value = 3.48

        regular_user.settings = {
            "telegram": {"enabled": True, "verified": True, "botToken": "enc", "chatId": "123"}
        }
        test_session.commit()

        resp = user_client.post("/api/v1/price-alerts", json={
            "etf_code": "510300",
            "etf_name": "沪深300ETF",
            "target_price": 3.50,
            "direction": "below",
        })
        assert resp.status_code == 400
        assert "已满足" in resp.json()["detail"]

    def test_create_rejects_without_telegram(self, user_client, test_session, regular_user):
        # 不配置 Telegram
        regular_user.settings = {}
        test_session.commit()

        resp = user_client.post("/api/v1/price-alerts", json={
            "etf_code": "510300",
            "etf_name": "沪深300ETF",
            "target_price": 3.40,
        })
        assert resp.status_code == 400
        assert "Telegram" in resp.json()["detail"]

    def test_create_validates_etf_code(self, user_client, test_session, regular_user):
        regular_user.settings = {
            "telegram": {"enabled": True, "verified": True, "botToken": "enc", "chatId": "123"}
        }
        test_session.commit()

        resp = user_client.post("/api/v1/price-alerts", json={
            "etf_code": "abc",
            "etf_name": "Bad",
            "target_price": 3.40,
        })
        assert resp.status_code == 422  # Pydantic validation

    @patch("app.api.v1.endpoints.price_alerts._get_current_etf_price")
    def test_create_rejects_at_quota_limit(self, mock_price, user_client, test_session, regular_user):
        """API 层验证：第 21 个提醒被拒绝（HTTP 400）"""
        mock_price.return_value = 100.0

        regular_user.settings = {
            "telegram": {"enabled": True, "verified": True, "botToken": "enc", "chatId": "123"}
        }
        test_session.commit()

        # 预填 20 条活跃提醒
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

        resp = user_client.post("/api/v1/price-alerts", json={
            "etf_code": "510399",
            "etf_name": "ETF-extra",
            "target_price": 1.0,
        })
        assert resp.status_code == 400
        assert "上限" in resp.json()["detail"]


class TestDeletePriceAlert:
    """DELETE /api/v1/price-alerts/{id}"""

    def test_delete_own_alert(self, user_client, test_session, regular_user):
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

        resp = user_client.delete(f"/api/v1/price-alerts/{alert.id}")
        assert resp.status_code == 200

    def test_delete_nonexistent(self, user_client):
        resp = user_client.delete("/api/v1/price-alerts/99999")
        assert resp.status_code == 404

    def test_delete_others_alert(self, user_client, test_session, admin_user):
        alert = PriceAlert(
            user_id=admin_user.id,
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            direction="below",
        )
        test_session.add(alert)
        test_session.commit()
        test_session.refresh(alert)

        resp = user_client.delete(f"/api/v1/price-alerts/{alert.id}")
        assert resp.status_code == 404
