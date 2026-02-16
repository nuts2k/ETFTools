# backend/tests/core/test_config_datasource.py
"""数据源配置项测试"""
import pytest


class TestDataSourceConfig:
    def test_default_history_sources(self):
        """默认历史数据源优先级列表"""
        from app.core.config import settings
        assert settings.HISTORY_DATA_SOURCES == ["eastmoney", "ths_history"]

    def test_baostock_disabled_default(self):
        """Baostock 默认关闭（不支持 ETF）"""
        from app.core.config import settings
        assert settings.BAOSTOCK_ENABLED is False

    def test_circuit_breaker_defaults(self):
        from app.core.config import settings
        assert settings.CIRCUIT_BREAKER_THRESHOLD == 0.1
        assert settings.CIRCUIT_BREAKER_WINDOW == 10
        assert settings.CIRCUIT_BREAKER_COOLDOWN == 300
