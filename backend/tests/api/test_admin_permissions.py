"""
管理员权限验证链集成测试

测试覆盖:
- 完整的权限验证链
- 停用管理员无法访问
- 过期/无效 token 场景
"""

import pytest
from datetime import timedelta
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.models.user import User
from app.services.auth_service import AuthService


class TestPermissionChain:
    """权限验证链测试"""

    def test_admin_permission_chain(self, admin_client: TestClient):
        """验证完整的权限链: 认证 -> 激活 -> 管理员"""
        # 管理员应该能访问所有管理端点
        response = admin_client.get("/api/v1/admin/users")
        assert response.status_code == 200

        response = admin_client.get("/api/v1/admin/system/config")
        assert response.status_code == 200

    def test_inactive_admin_blocked(self, test_session: Session, test_engine):
        """停用的管理员无法访问"""
        # 创建一个停用的管理员
        inactive_admin = User(
            username="inactive_admin",
            hashed_password=AuthService.get_password_hash("password123"),
            is_admin=True,
            is_active=False,
        )
        test_session.add(inactive_admin)
        test_session.commit()
        test_session.refresh(inactive_admin)

        # 生成 token
        token = AuthService.create_access_token(data={"sub": inactive_admin.username})

        # 创建 client
        from app.main import app
        from app.core.database import get_session
        from fastapi.testclient import TestClient

        def override_get_session():
            yield test_session

        app.dependency_overrides[get_session] = override_get_session
        client = TestClient(app)
        client.headers = {"Authorization": f"Bearer {token}"}

        # 尝试访问管理端点
        response = client.get("/api/v1/admin/users")
        assert response.status_code == 403
        assert "User account is disabled" in response.json()["detail"]

        app.dependency_overrides.clear()

    def test_expired_token_blocked(self, test_session: Session, admin_user: User):
        """过期 token 无法访问"""
        # 生成一个已过期的 token（过期时间为 -1 分钟）
        expired_token = AuthService.create_access_token(
            data={"sub": admin_user.username},
            expires_delta=timedelta(minutes=-1)
        )

        # 创建 client
        from app.main import app
        from app.core.database import get_session
        from fastapi.testclient import TestClient

        def override_get_session():
            yield test_session

        app.dependency_overrides[get_session] = override_get_session
        client = TestClient(app)
        client.headers = {"Authorization": f"Bearer {expired_token}"}

        # 尝试访问管理端点
        response = client.get("/api/v1/admin/users")
        assert response.status_code == 401
        assert "Could not validate credentials" in response.json()["detail"]

        app.dependency_overrides.clear()

    def test_invalid_token_blocked(self, test_session: Session):
        """无效 token 无法访问"""
        # 使用一个无效的 token
        invalid_token = "invalid.token.here"

        # 创建 client
        from app.main import app
        from app.core.database import get_session
        from fastapi.testclient import TestClient

        def override_get_session():
            yield test_session

        app.dependency_overrides[get_session] = override_get_session
        client = TestClient(app)
        client.headers = {"Authorization": f"Bearer {invalid_token}"}

        # 尝试访问管理端点
        response = client.get("/api/v1/admin/users")
        assert response.status_code == 401
        assert "Could not validate credentials" in response.json()["detail"]

        app.dependency_overrides.clear()

    def test_regular_user_blocked_from_admin_endpoints(self, user_client: TestClient):
        """普通用户无法访问管理端点"""
        # 尝试访问各个管理端点
        endpoints = [
            "/api/v1/admin/users",
            "/api/v1/admin/system/config",
        ]

        for endpoint in endpoints:
            response = user_client.get(endpoint)
            assert response.status_code == 403
            assert "Admin privileges required" in response.json()["detail"]
