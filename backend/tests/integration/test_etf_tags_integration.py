"""
Integration tests: tags flow from enrich → cache → API endpoints.
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient


class TestTagsIntegration:
    """验证 tags 从 enrich → cache → API 的完整链路"""

    def teardown_method(self):
        """每个测试结束后重置全局 cache，避免状态泄漏"""
        from app.core.cache import etf_cache
        etf_cache.etf_list = []
        etf_cache.etf_map = {}
        etf_cache.last_updated = 0

    def _setup_cache_with_tags(self):
        """辅助：用带 tags 的数据初始化 cache"""
        from app.core.cache import etf_cache
        from app.services.akshare_service import _enrich_with_tags

        etf_list = [
            {"code": "510300", "name": "沪深300ETF", "price": 3.85, "change_pct": 1.2},
            {"code": "512480", "name": "半导体ETF", "price": 1.20, "change_pct": -0.5},
            {"code": "159915", "name": "创业板ETF", "price": 2.10, "change_pct": 0.8},
        ]
        _enrich_with_tags(etf_list)
        etf_cache.set_etf_list(etf_list)
        return etf_cache

    @patch("app.api.v1.endpoints.etf.get_market_status", return_value="交易中")
    def test_search_returns_tags(self, mock_status):
        """搜索接口应透传 cache 中的 tags"""
        self._setup_cache_with_tags()

        from app.main import app
        client = TestClient(app)
        resp = client.get("/api/v1/etf/search?q=半导体")
        assert resp.status_code == 200

        results = resp.json()
        semi_etf = next((r for r in results if r["code"] == "512480"), None)
        assert semi_etf is not None
        assert "tags" in semi_etf
        labels = [t["label"] for t in semi_etf["tags"]]
        assert "半导体" in labels

    @patch("app.api.v1.endpoints.etf.get_market_status", return_value="交易中")
    def test_batch_price_returns_tags(self, mock_status):
        """batch-price 接口应包含 tags"""
        self._setup_cache_with_tags()

        from app.main import app
        client = TestClient(app)
        resp = client.get("/api/v1/etf/batch-price?codes=510300,512480")
        assert resp.status_code == 200

        items = resp.json()["items"]
        assert len(items) == 2
        for item in items:
            assert "tags" in item
            assert isinstance(item["tags"], list)

    def test_update_etf_info_preserves_tags(self):
        """watchlist 同步更新价格后 tags 不丢失"""
        cache = self._setup_cache_with_tags()
        original_tags = cache.get_etf_info("510300")["tags"]

        # 模拟 watchlist 同步：只更新 price
        cache.update_etf_info({"code": "510300", "price": 4.00})

        info = cache.get_etf_info("510300")
        assert info["price"] == 4.00
        assert info["tags"] == original_tags
