"""
Tests for GET /etf/batch-price endpoint.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, PropertyMock
from fastapi.testclient import TestClient


class TestBatchPriceEndpoint:
    """Tests for /etf/batch-price endpoint."""

    def _make_etf_map(self):
        """Helper: mock etf_map data."""
        return {
            "510300": {
                "code": "510300",
                "name": "沪深300ETF",
                "price": 3.85,
                "change_pct": 0.52,
            },
            "510500": {
                "code": "510500",
                "name": "中证500ETF",
                "price": 5.12,
                "change_pct": -0.39,
            },
        }

    @patch("app.api.v1.endpoints.etf.get_market_status", return_value="交易中")
    @patch("app.api.v1.endpoints.etf.etf_cache")
    def test_batch_price_success(self, mock_cache, mock_status):
        """正常请求返回多个 ETF 价格。"""
        from app.main import app

        mock_cache.etf_map = self._make_etf_map()

        client = TestClient(app)
        response = client.get("/api/v1/etf/batch-price?codes=510300,510500")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "market_status" in data
        assert len(data["items"]) == 2
        assert data["items"][0]["code"] == "510300"
        assert data["items"][0]["price"] == 3.85
        assert data["market_status"] == "交易中"

    @patch("app.api.v1.endpoints.etf.get_market_status", return_value="已收盘")
    @patch("app.api.v1.endpoints.etf.etf_cache")
    def test_batch_price_market_closed(self, mock_cache, mock_status):
        """已收盘时 market_status 正确返回。"""
        from app.main import app

        mock_cache.etf_map = self._make_etf_map()

        client = TestClient(app)
        response = client.get("/api/v1/etf/batch-price?codes=510300")

        assert response.status_code == 200
        data = response.json()
        assert data["market_status"] == "已收盘"

    @patch("app.api.v1.endpoints.etf.etf_cache")
    def test_batch_price_unknown_code_skipped(self, mock_cache):
        """未知代码被静默跳过，不报错。"""
        from app.main import app

        mock_cache.etf_map = self._make_etf_map()

        client = TestClient(app)
        response = client.get("/api/v1/etf/batch-price?codes=999999")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 0

    def test_batch_price_empty_codes(self):
        """空 codes 参数返回 400。"""
        from app.main import app

        client = TestClient(app)
        response = client.get("/api/v1/etf/batch-price?codes=")

        assert response.status_code == 400

    def test_batch_price_too_many_codes(self):
        """超过 50 个代码返回 400。"""
        from app.main import app

        codes = ",".join([f"{i:06d}" for i in range(51)])
        client = TestClient(app)
        response = client.get(f"/api/v1/etf/batch-price?codes={codes}")

        assert response.status_code == 400

    @patch("app.api.v1.endpoints.etf.get_market_status", return_value="交易中")
    @patch("app.api.v1.endpoints.etf.etf_cache")
    def test_batch_price_codes_with_whitespace(self, mock_cache, mock_status):
        """代码间有多余空格时仍能正常解析。"""
        from app.main import app

        mock_cache.etf_map = self._make_etf_map()

        client = TestClient(app)
        response = client.get("/api/v1/etf/batch-price?codes= 510300 , 510500 ")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2

    @patch("app.api.v1.endpoints.etf.get_market_status", return_value="交易中")
    @patch("app.api.v1.endpoints.etf.etf_cache")
    def test_batch_price_duplicate_codes(self, mock_cache, mock_status):
        """重复代码返回重复条目（不去重）。"""
        from app.main import app

        mock_cache.etf_map = self._make_etf_map()

        client = TestClient(app)
        response = client.get("/api/v1/etf/batch-price?codes=510300,510300")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2

    def test_batch_price_invalid_format_codes(self):
        """非6位数字的代码被过滤，全部无效时返回 400。"""
        from app.main import app

        client = TestClient(app)
        response = client.get("/api/v1/etf/batch-price?codes=abc,<script>,12345")

        assert response.status_code == 400

    @patch("app.api.v1.endpoints.etf.get_market_status", return_value="交易中")
    @patch("app.api.v1.endpoints.etf.etf_cache")
    def test_batch_price_includes_tags(self, mock_cache, mock_status):
        """batch-price 响应应包含 tags 字段"""
        from app.main import app

        mock_cache.etf_map = {
            "510300": {
                "code": "510300", "name": "沪深300ETF",
                "price": 3.85, "change_pct": 1.2,
                "tags": [{"label": "宽基", "group": "type"}, {"label": "沪深300", "group": "type"}],
            },
        }
        mock_cache.last_updated = 1700000000.0

        client = TestClient(app)
        resp = client.get("/api/v1/etf/batch-price?codes=510300")
        assert resp.status_code == 200
        item = resp.json()["items"][0]
        assert "tags" in item
        assert item["tags"][0]["label"] == "宽基"

    @patch("app.api.v1.endpoints.etf.get_market_status", return_value="交易中")
    @patch("app.api.v1.endpoints.etf.etf_cache")
    def test_batch_price_missing_tags(self, mock_cache, mock_status):
        """ETF 无 tags 字段时应返回空列表"""
        from app.main import app

        mock_cache.etf_map = {
            "510300": {"code": "510300", "name": "沪深300ETF", "price": 3.85, "change_pct": 1.2},
        }
        mock_cache.last_updated = 1700000000.0

        client = TestClient(app)
        resp = client.get("/api/v1/etf/batch-price?codes=510300")
        item = resp.json()["items"][0]
        assert item["tags"] == []
