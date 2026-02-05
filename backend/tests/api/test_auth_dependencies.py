import pytest
from fastapi import HTTPException
from app.models.user import User


def test_get_current_active_user_disabled():
    """验证禁用用户被拒绝"""
    from app.api.v1.endpoints.auth import get_current_active_user
    user = User(username="test", hashed_password="hash", is_active=False)
    with pytest.raises(HTTPException) as exc_info:
        import asyncio
        asyncio.get_event_loop().run_until_complete(get_current_active_user(user))
    assert exc_info.value.status_code == 403


def test_get_current_admin_user_not_admin():
    """验证非管理员被拒绝"""
    from app.api.v1.endpoints.auth import get_current_admin_user
    user = User(username="test", hashed_password="hash", is_admin=False, is_active=True)
    with pytest.raises(HTTPException) as exc_info:
        import asyncio
        asyncio.get_event_loop().run_until_complete(get_current_admin_user(user))
    assert exc_info.value.status_code == 403
