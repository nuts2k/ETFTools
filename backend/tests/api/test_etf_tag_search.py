"""
Tests for ETF tag filtering: filter_by_tag, /tags/popular, /search?tag=xxx
"""

from __future__ import annotations

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.core.cache import ETFCacheManager


# --- Unit tests for filter_by_tag ---

class TestFilterByTag:
    """Tests for ETFCacheManager.filter_by_tag method."""

    def setup_method(self):
        self.cache = ETFCacheManager()
        self.cache.set_etf_list([
            {"code": "510300", "name": "沪深300ETF", "tags": [
                {"label": "宽基", "group": "type"},
            ]},
            {"code": "159915", "name": "创业板ETF", "tags": [
                {"label": "宽基", "group": "type"},
            ]},
            {"code": "512480", "name": "半导体ETF", "tags": [
                {"label": "半导体", "group": "industry"},
            ]},
            {"code": "518880", "name": "黄金ETF", "tags": [
                {"label": "黄金", "group": "industry"},
                {"label": "商品", "group": "type"},
            ]},
            {"code": "510050", "name": "上证50ETF"},  # 无 tags 字段
        ])

    def test_match_single_tag(self):
        results = self.cache.filter_by_tag("半导体")
        assert len(results) == 1
        assert results[0]["code"] == "512480"

    def test_match_multiple_results(self):
        results = self.cache.filter_by_tag("宽基")
        assert len(results) == 2
        codes = {r["code"] for r in results}
        assert codes == {"510300", "159915"}

    def test_no_match(self):
        results = self.cache.filter_by_tag("不存在的标签")
        assert results == []

    def test_limit_parameter(self):
        results = self.cache.filter_by_tag("宽基", limit=1)
        assert len(results) == 1

    def test_empty_cache(self):
        empty_cache = ETFCacheManager()
        results = empty_cache.filter_by_tag("宽基")
        assert results == []

    def test_item_without_tags_field(self):
        """Items without tags field should be skipped."""
        results = self.cache.filter_by_tag("宽基")
        codes = {r["code"] for r in results}
        assert "510050" not in codes

    def test_multi_tag_item(self):
        """Item with multiple tags should match any of them."""
        results_gold = self.cache.filter_by_tag("黄金")
        assert len(results_gold) == 1
        assert results_gold[0]["code"] == "518880"

        results_commodity = self.cache.filter_by_tag("商品")
        assert len(results_commodity) == 1
        assert results_commodity[0]["code"] == "518880"


# --- API integration tests ---

class TestTagSearchAPI:
    """Integration tests for tag-related API endpoints."""

    def setup_method(self):
        from app.main import app
        from app.core.cache import etf_cache

        self.client = TestClient(app)
        # 预填充缓存数据
        etf_cache.set_etf_list([
            {"code": "510300", "name": "沪深300ETF", "price": 3.85, "change_pct": 1.0, "tags": [
                {"label": "宽基", "group": "type"},
            ]},
            {"code": "512480", "name": "半导体ETF", "price": 1.20, "change_pct": -0.5, "tags": [
                {"label": "半导体", "group": "industry"},
            ]},
        ])

    def test_get_popular_tags(self):
        resp = self.client.get("/api/v1/etf/tags/popular")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # 每个标签都有 label 和 group
        for tag in data:
            assert "label" in tag
            assert "group" in tag

    def test_search_by_tag(self):
        resp = self.client.get("/api/v1/etf/search?tag=宽基")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["code"] == "510300"

    def test_search_by_tag_no_match(self):
        resp = self.client.get("/api/v1/etf/search?tag=不存在")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_search_no_params_returns_empty(self):
        resp = self.client.get("/api/v1/etf/search")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_search_by_q_backward_compat(self):
        resp = self.client.get("/api/v1/etf/search?q=300")
        assert resp.status_code == 200
        data = resp.json()
        assert any(item["code"] == "510300" for item in data)

    def test_search_tag_takes_priority_over_q(self):
        resp = self.client.get("/api/v1/etf/search?tag=半导体&q=300")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["code"] == "512480"
