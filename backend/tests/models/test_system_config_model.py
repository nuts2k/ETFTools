import pytest
from app.models.system_config import SystemConfig, SystemConfigKeys

def test_system_config_model():
    """验证 SystemConfig 模型结构"""
    config = SystemConfig(
        key="test_key",
        value={"enabled": True},
        description="Test config"
    )
    assert config.key == "test_key"
    assert config.value == {"enabled": True}

def test_system_config_keys():
    """验证预定义配置键常量"""
    assert SystemConfigKeys.REGISTRATION_ENABLED == "registration_enabled"
    assert SystemConfigKeys.MAX_WATCHLIST_ITEMS == "max_watchlist_items"
