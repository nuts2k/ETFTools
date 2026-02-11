import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

class TestCompareAPI:

    @patch("app.api.v1.endpoints.compare.compare_service")
    def test_success_two_etfs(self, mock_svc):
        mock_svc.compute.return_value = {
            "etf_names": {"510300": "沪深300ETF", "510500": "中证500ETF"},
            "period_label": "2023-01-01 ~ 2024-01-01",
            "warnings": [],
            "normalized": {"dates": ["2023-01-01"], "series": {"510300": [100.0], "510500": [100.0]}},
            "correlation": {"510300_510500": 0.85},
            "metrics": {
                "510300": {"cagr": 0.08, "total_return": 0.08, "actual_years": 1.0, "max_drawdown": -0.1, "volatility": 0.15, "risk_level": "Medium", "mdd_date": "2023-06-01", "mdd_start": "2023-05-01", "mdd_trough": "2023-06-01", "mdd_end": "2023-08-01"},
                "510500": {"cagr": 0.05, "total_return": 0.05, "actual_years": 1.0, "max_drawdown": -0.12, "volatility": 0.18, "risk_level": "Medium", "mdd_date": "2023-06-01", "mdd_start": "2023-05-01", "mdd_trough": "2023-06-01", "mdd_end": "2023-08-01"},
            },
            "temperatures": {"510300": {"score": 55, "level": "warm"}, "510500": None},
        }
        resp = client.get("/api/v1/etf/compare?codes=510300,510500&period=3y")
        assert resp.status_code == 200
        data = resp.json()
        assert "etf_names" in data
        assert "510300" in data["etf_names"]
        assert data["warnings"] == []
        assert "metrics" in data
        assert "temperatures" in data
        mock_svc.compute.assert_called_once_with(["510300", "510500"], "3y")

    def test_codes_less_than_2(self):
        resp = client.get("/api/v1/etf/compare?codes=510300")
        assert resp.status_code == 400

    def test_codes_more_than_3(self):
        resp = client.get("/api/v1/etf/compare?codes=510300,510500,159915,159919")
        assert resp.status_code == 400

    def test_codes_invalid_format(self):
        resp = client.get("/api/v1/etf/compare?codes=abc,510500")
        assert resp.status_code == 400

    def test_invalid_period(self):
        resp = client.get("/api/v1/etf/compare?codes=510300,510500&period=2y")
        assert resp.status_code == 400

    @patch("app.api.v1.endpoints.compare.compare_service")
    def test_no_data_returns_404(self, mock_svc):
        mock_svc.compute.side_effect = ValueError("ETF ABC 无历史数据")
        resp = client.get("/api/v1/etf/compare?codes=510300,510500")
        assert resp.status_code == 404

    @patch("app.api.v1.endpoints.compare.compare_service")
    def test_overlap_too_short_returns_422(self, mock_svc):
        mock_svc.compute.side_effect = ValueError("不足 30 天")
        resp = client.get("/api/v1/etf/compare?codes=510300,510500")
        assert resp.status_code == 422

    @patch("app.api.v1.endpoints.compare.compare_service")
    def test_warnings_returned(self, mock_svc):
        mock_svc.compute.return_value = {
            "etf_names": {"A": "X", "B": "Y"},
            "period_label": "x", "warnings": ["重叠交易日仅 45 天"],
            "normalized": {"dates": [], "series": {}}, "correlation": {},
            "metrics": {}, "temperatures": {},
        }
        resp = client.get("/api/v1/etf/compare?codes=510300,510500")
        assert resp.status_code == 200
        assert len(resp.json()["warnings"]) == 1

    def test_default_period_is_3y(self):
        """不传 period 时默认 3y"""
        with patch("app.api.v1.endpoints.compare.compare_service") as mock_svc:
            mock_svc.compute.return_value = {
                "etf_names": {}, "period_label": "", "warnings": [],
                "normalized": {"dates": [], "series": {}}, "correlation": {},
                "metrics": {}, "temperatures": {},
            }
            client.get("/api/v1/etf/compare?codes=510300,510500")
            mock_svc.compute.assert_called_once_with(["510300", "510500"], "3y")
