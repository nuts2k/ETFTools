"""
管理员用户管理端点集成测试

测试覆盖:
- 用户列表获取、分页、过滤
- 管理员权限切换
- 用户激活/停用
- 权限验证
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.models.user import User


class TestUserList:
    """用户列表端点测试"""

    def test_list_users_as_admin(self, admin_client: TestClient, admin_user: User, regular_user: User):
        """管理员可以获取用户列表"""
        response = admin_client.get("/api/v1/admin/users")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2  # 至少有 admin 和 regular_user

        # 验证返回的用户数据结构
        user_data = data[0]
        assert "id" in user_data
        assert "username" in user_data
        assert "is_admin" in user_data
        assert "is_active" in user_data
        assert "created_at" in user_data

    def test_list_users_as_regular_user(self, user_client: TestClient):
        """普通用户无权访问用户列表（403）"""
        response = user_client.get("/api/v1/admin/users")
        assert response.status_code == 403
        assert "Admin privileges required" in response.json()["detail"]

    def test_list_users_unauthenticated(self, client: TestClient):
        """未认证用户无权访问（401）"""
        response = client.get("/api/v1/admin/users")
        assert response.status_code == 401

    def test_list_users_pagination(self, admin_client: TestClient, test_session: Session):
        """分页参数正确工作"""
        # 创建额外的测试用户
        for i in range(5):
            user = User(
                username=f"testuser{i}",
                hashed_password="hash",
                is_admin=False,
                is_active=True,
            )
            test_session.add(user)
        test_session.commit()

        # 测试 limit 参数
        response = admin_client.get("/api/v1/admin/users?limit=3")
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 3

        # 测试 skip 参数
        response = admin_client.get("/api/v1/admin/users?skip=2&limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 2

    def test_list_users_filter_by_admin(self, admin_client: TestClient, admin_user: User, regular_user: User):
        """按 is_admin 过滤"""
        # 只获取管理员
        response = admin_client.get("/api/v1/admin/users?is_admin=true")
        assert response.status_code == 200
        data = response.json()
        assert all(user["is_admin"] for user in data)

        # 只获取非管理员
        response = admin_client.get("/api/v1/admin/users?is_admin=false")
        assert response.status_code == 200
        data = response.json()
        assert all(not user["is_admin"] for user in data)

    def test_list_users_filter_by_active(self, admin_client: TestClient, test_session: Session):
        """按 is_active 过滤"""
        # 创建一个停用用户
        inactive_user = User(
            username="inactive",
            hashed_password="hash",
            is_admin=False,
            is_active=False,
        )
        test_session.add(inactive_user)
        test_session.commit()

        # 只获取激活用户
        response = admin_client.get("/api/v1/admin/users?is_active=true")
        assert response.status_code == 200
        data = response.json()
        assert all(user["is_active"] for user in data)

        # 只获取停用用户
        response = admin_client.get("/api/v1/admin/users?is_active=false")
        assert response.status_code == 200
        data = response.json()
        assert all(not user["is_active"] for user in data)
        assert any(user["username"] == "inactive" for user in data)


class TestToggleAdmin:
    """管理员权限切换测试"""

    def test_toggle_admin_grant(self, admin_client: TestClient, regular_user: User, test_session: Session):
        """授予管理员权限"""
        response = admin_client.post(f"/api/v1/admin/users/{regular_user.id}/toggle-admin")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == regular_user.id
        assert data["is_admin"] is True

        # 验证数据库中的状态
        test_session.refresh(regular_user)
        assert regular_user.is_admin is True

    def test_toggle_admin_revoke(self, admin_client: TestClient, test_session: Session):
        """撤销管理员权限"""
        # 创建一个管理员用户
        another_admin = User(
            username="another_admin",
            hashed_password="hash",
            is_admin=True,
            is_active=True,
        )
        test_session.add(another_admin)
        test_session.commit()
        test_session.refresh(another_admin)

        response = admin_client.post(f"/api/v1/admin/users/{another_admin.id}/toggle-admin")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == another_admin.id
        assert data["is_admin"] is False

        # 验证数据库中的状态
        test_session.refresh(another_admin)
        assert another_admin.is_admin is False

    def test_toggle_admin_as_regular_user(self, user_client: TestClient, admin_user: User):
        """普通用户无权操作（403）"""
        response = user_client.post(f"/api/v1/admin/users/{admin_user.id}/toggle-admin")
        assert response.status_code == 403
        assert "Admin privileges required" in response.json()["detail"]

    def test_toggle_admin_nonexistent_user(self, admin_client: TestClient):
        """用户不存在（404）"""
        response = admin_client.post("/api/v1/admin/users/99999/toggle-admin")
        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

    def test_toggle_admin_self(self, admin_client: TestClient, admin_user: User):
        """不能修改自己的权限（400）"""
        response = admin_client.post(f"/api/v1/admin/users/{admin_user.id}/toggle-admin")
        assert response.status_code == 400
        assert "Cannot modify your own admin status" in response.json()["detail"]


class TestToggleActive:
    """用户激活/停用测试"""

    def test_toggle_active_deactivate(self, admin_client: TestClient, regular_user: User, test_session: Session):
        """停用用户"""
        response = admin_client.post(f"/api/v1/admin/users/{regular_user.id}/toggle-active")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == regular_user.id
        assert data["is_active"] is False

        # 验证数据库中的状态
        test_session.refresh(regular_user)
        assert regular_user.is_active is False

    def test_toggle_active_activate(self, admin_client: TestClient, test_session: Session):
        """激活用户"""
        # 创建一个停用用户
        inactive_user = User(
            username="inactive_test",
            hashed_password="hash",
            is_admin=False,
            is_active=False,
        )
        test_session.add(inactive_user)
        test_session.commit()
        test_session.refresh(inactive_user)

        response = admin_client.post(f"/api/v1/admin/users/{inactive_user.id}/toggle-active")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == inactive_user.id
        assert data["is_active"] is True

        # 验证数据库中的状态
        test_session.refresh(inactive_user)
        assert inactive_user.is_active is True

    def test_toggle_active_as_regular_user(self, user_client: TestClient, regular_user: User):
        """普通用户无权操作（403）"""
        response = user_client.post(f"/api/v1/admin/users/{regular_user.id}/toggle-active")
        assert response.status_code == 403
        assert "Admin privileges required" in response.json()["detail"]

    def test_toggle_active_self(self, admin_client: TestClient, admin_user: User):
        """不能停用自己（400）"""
        response = admin_client.post(f"/api/v1/admin/users/{admin_user.id}/toggle-active")
        assert response.status_code == 400
        assert "Cannot disable your own account" in response.json()["detail"]
