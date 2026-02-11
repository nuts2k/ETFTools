"""
Tests for ETFCacheManager.update_etf_info merge semantics.
"""

import pytest
from app.core.cache import ETFCacheManager


class TestUpdateEtfInfoMerge:
    def setup_method(self):
        self.cache = ETFCacheManager()
        self.cache.set_etf_list([
            {
                "code": "510300", "name": "沪深300ETF",
                "price": 3.85, "change_pct": 1.2,
                "tags": [{"label": "宽基", "group": "type"}],
            },
        ])

    def test_merge_preserves_tags(self):
        """update 不含 tags 的 dict 时，已有 tags 应保留"""
        self.cache.update_etf_info({
            "code": "510300", "price": 3.90, "change_pct": 1.5,
        })
        info = self.cache.get_etf_info("510300")
        assert info["price"] == 3.90
        assert info["tags"] == [{"label": "宽基", "group": "type"}]

    def test_merge_updates_existing_fields(self):
        """update 应正确更新已有字段"""
        self.cache.update_etf_info({"code": "510300", "name": "新名称"})
        info = self.cache.get_etf_info("510300")
        assert info["name"] == "新名称"
        assert info["tags"] == [{"label": "宽基", "group": "type"}]

    def test_merge_syncs_list_and_map(self):
        """etf_list 和 etf_map 应同步更新"""
        self.cache.update_etf_info({"code": "510300", "price": 4.00})
        map_info = self.cache.etf_map["510300"]
        list_info = next(e for e in self.cache.etf_list if e["code"] == "510300")
        assert map_info["price"] == 4.00
        assert list_info["price"] == 4.00
        assert map_info["tags"] == list_info["tags"]

    def test_insert_new_etf(self):
        """update 不存在的 ETF 应新增记录"""
        self.cache.update_etf_info({
            "code": "512480", "name": "半导体ETF", "price": 1.20,
        })
        info = self.cache.get_etf_info("512480")
        assert info is not None
        assert info["name"] == "半导体ETF"

    def test_no_code_is_noop(self):
        """无 code 字段时应静默忽略"""
        original_len = len(self.cache.etf_list)
        self.cache.update_etf_info({"name": "无代码"})
        assert len(self.cache.etf_list) == original_len
