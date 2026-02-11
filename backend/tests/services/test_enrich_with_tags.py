"""
Tests for _enrich_with_tags helper function.
"""

import pytest
from app.services.akshare_service import _enrich_with_tags


class TestEnrichWithTags:
    def test_basic_enrichment(self):
        """ETF 列表经 enrich 后每个 dict 应包含 tags 字段"""
        etf_list = [
            {"code": "510300", "name": "沪深300ETF", "price": 3.85},
            {"code": "512480", "name": "半导体ETF", "price": 1.20},
        ]
        result = _enrich_with_tags(etf_list)

        assert result is etf_list  # 原地修改，返回同一引用
        for etf in result:
            assert "tags" in etf
            assert isinstance(etf["tags"], list)

    def test_tags_format(self):
        """tags 应为 [{"label": str, "group": str}] 格式"""
        etf_list = [{"code": "510300", "name": "沪深300ETF"}]
        _enrich_with_tags(etf_list)

        for tag in etf_list[0]["tags"]:
            assert "label" in tag
            assert "group" in tag
            assert isinstance(tag["label"], str)
            assert tag["group"] in ("type", "industry", "strategy", "special")

    def test_known_classification(self):
        """已知 ETF 应返回预期标签"""
        etf_list = [{"code": "510300", "name": "沪深300ETF"}]
        _enrich_with_tags(etf_list)
        labels = [t["label"] for t in etf_list[0]["tags"]]
        assert "宽基" in labels
        assert "沪深300" in labels

    def test_empty_name(self):
        """name 为空字符串时 tags 应为空列表"""
        etf_list = [{"code": "000000", "name": ""}]
        _enrich_with_tags(etf_list)
        assert etf_list[0]["tags"] == []

    def test_missing_name_key(self):
        """dict 中无 name 键时不报错，tags 为空列表"""
        etf_list = [{"code": "000000"}]
        _enrich_with_tags(etf_list)
        assert etf_list[0]["tags"] == []

    def test_empty_list(self):
        """空列表不报错"""
        result = _enrich_with_tags([])
        assert result == []

    def test_large_batch(self):
        """500 个 ETF 批量 enrich 应在 1 秒内完成"""
        import time
        etf_list = [{"code": f"{i:06d}", "name": f"测试ETF{i}"} for i in range(500)]
        start = time.perf_counter()
        _enrich_with_tags(etf_list)
        duration = time.perf_counter() - start
        assert duration < 1.0
