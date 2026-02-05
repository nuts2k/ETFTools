import pytest
from sqlmodel import Session, SQLModel, create_engine
from app.models.system_config import SystemConfig, SystemConfigKeys
from app.models.user import User  # Required for foreign key
from app.services.system_config_service import SystemConfigService


@pytest.fixture
def test_session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_get_config_default(test_session):
    """测试获取不存在的配置返回默认值"""
    result = SystemConfigService.get_config(test_session, "nonexistent", default="default")
    assert result == "default"


def test_set_and_get_config(test_session):
    """测试设置和获取配置"""
    SystemConfigService.set_config(test_session, "test_key", {"enabled": True}, user_id=1)
    result = SystemConfigService.get_config(test_session, "test_key")
    assert result == {"enabled": True}


def test_is_registration_enabled_default(test_session):
    """测试注册开关默认值"""
    assert SystemConfigService.is_registration_enabled(test_session) is True
