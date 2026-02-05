import pytest
from datetime import datetime
from app.models.user import User

def test_user_has_admin_fields():
    """验证 User 模型包含管理员相关字段"""
    user = User(
        username="testuser",
        hashed_password="hashed",
        is_admin=True,
        is_active=False
    )
    assert user.is_admin is True
    assert user.is_active is False

def test_user_admin_defaults():
    """验证 User 模型默认值"""
    user = User(
        username="testuser",
        hashed_password="hashed"
    )
    assert user.is_admin is False
    assert user.is_active is True
    assert user.updated_at is not None
