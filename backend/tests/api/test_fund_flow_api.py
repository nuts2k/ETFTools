"""
Tests for fund flow API endpoints
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient


def test_get_fund_flow_success(client):
    """测试成功获取资金流向数据"""
    mock_data = {
        "code": "510300",
        "name": "510300",
        "current_scale": {
            "shares": 910.62,
            "scale": 3578.54,
            "update_date": "2025-01-15",
            "exchange": "SSE"
        },
        "rank": {
            "rank": 3,
            "total_count": 593,
            "percentile": 99.5,
            "category": "股票型"
        },
        "historical_available": True,
        "data_points": 30
    }

    with patch("app.services.fund_flow_cache_service.fund_flow_cache_service.get_fund_flow", return_value=mock_data):
        response = client.get("/api/v1/etf/510300/fund-flow")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == "510300"
        assert data["current_scale"]["shares"] == 910.62


def test_get_fund_flow_not_found(client):
    """测试无数据时返回 404"""
    with patch("app.services.fund_flow_cache_service.fund_flow_cache_service.get_fund_flow", return_value=None):
        response = client.get("/api/v1/etf/999999/fund-flow")

        assert response.status_code == 404


def test_get_fund_flow_force_refresh(client):
    """测试 force_refresh 参数"""
    mock_data = {"code": "510300", "current_scale": {"shares": 910.62}}

    with patch("app.services.fund_flow_cache_service.fund_flow_cache_service.get_fund_flow", return_value=mock_data) as mock_get:
        response = client.get("/api/v1/etf/510300/fund-flow?force_refresh=true")

        assert response.status_code == 200
        mock_get.assert_called_once_with("510300", force_refresh=True)


def test_admin_collect_requires_auth(client):
    """测试未认证时返回 401"""
    response = client.post("/api/v1/admin/fund-flow/collect")
    assert response.status_code == 401


def test_admin_collect_requires_admin(user_client):
    """测试普通用户返回 403"""
    response = user_client.post("/api/v1/admin/fund-flow/collect")
    assert response.status_code == 403


def test_admin_collect_success(admin_client):
    """测试管理员触发采集成功"""
    mock_result = {"success": True, "collected": 100, "failed": 0, "message": "Success"}

    with patch("app.services.fund_flow_collector.fund_flow_collector.collect_daily_snapshot", return_value=mock_result):
        response = admin_client.post("/api/v1/admin/fund-flow/collect")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["collected"] == 100


def test_admin_export_csv(admin_client):
    """测试管理员导出 CSV"""
    mock_csv = b"code,date,shares\n510300,2025-01-15,910.62\n"

    with patch("app.services.share_history_backup_service.share_history_backup_service.export_to_csv_bytes", return_value=mock_csv):
        response = admin_client.post("/api/v1/admin/fund-flow/export?start_date=2025-01-01&end_date=2025-01-31")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment" in response.headers["content-disposition"]
