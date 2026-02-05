"""
管理员系统配置端点集成测试

测试覆盖:
- 获取系统配置
- 更新系统配置
- 注册开关集成测试
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.models.user import User


class TestGetSystemConfig:
    """获取系统配置测试"""

    def test_get_config_as_admin(self, admin_client: TestClient):
        """管理员可以获取配置"""
        response = admin_client.get("/api/v1/admin/system/config")
        assert response.status_code == 200
        data = response.json()
        assert "registration_enabled" in data
        assert "max_watchlist_items" in data
        assert isinstance(data["registration_enabled"], bool)
        assert isinstance(data["max_watchlist_items"], int)

    def test_get_config_as_regular_user(self, user_client: TestClient):
        """普通用户无权访问（403）"""
        response = user_client.get("/api/v1/admin/system/config")
        assert response.status_code == 403
        assert "Admin privileges required" in response.json()["detail"]

    def test_get_config_registration_enabled(self, admin_client: TestClient, test_session: Session):
        """注册开启时返回正确状态"""
        # 确保注册开启
        from app.services.system_config_service import SystemConfigService
        from app.models.system_config import SystemConfigKeys
        SystemConfigService.set_config(test_session, SystemConfigKeys.REGISTRATION_ENABLED, True, 1)

        response = admin_client.get("/api/v1/admin/system/config")
        assert response.status_code == 200
        data = response.json()
        assert data["registration_enabled"] is True

    def test_get_config_registration_disabled(self, admin_client: TestClient, test_session: Session):
        """注册关闭时返回正确状态"""
        # 关闭注册
        from app.services.system_config_service import SystemConfigService
        from app.models.system_config import SystemConfigKeys
        SystemConfigService.set_config(test_session, SystemConfigKeys.REGISTRATION_ENABLED, False, 1)

        response = admin_client.get("/api/v1/admin/system/config")
        assert response.status_code == 200
        data = response.json()
        assert data["registration_enabled"] is False


class TestUpdateSystemConfig:
    """更新系统配置测试"""

    def test_update_config_enable_registration(self, admin_client: TestClient, test_session: Session):
        """开启注册"""
        response = admin_client.post("/api/v1/admin/system/config/registration?enabled=true")
        assert response.status_code == 200
        data = response.json()
        assert data["registration_enabled"] is True

        # 验证数据库中的状态
        from app.services.system_config_service import SystemConfigService
        assert SystemConfigService.is_registration_enabled(test_session) is True

    def test_update_config_disable_registration(self, admin_client: TestClient, test_session: Session):
        """关闭注册"""
        response = admin_client.post("/api/v1/admin/system/config/registration?enabled=false")
        assert response.status_code == 200
        data = response.json()
        assert data["registration_enabled"] is False

        # 验证数据库中的状态
        from app.services.system_config_service import SystemConfigService
        assert SystemConfigService.is_registration_enabled(test_session) is False

    def test_update_config_as_regular_user(self, user_client: TestClient):
        """普通用户无权操作（403）"""
        response = user_client.post("/api/v1/admin/system/config/registration?enabled=false")
        assert response.status_code == 403
        assert "Admin privileges required" in response.json()["detail"]

    def test_update_max_watchlist(self, admin_client: TestClient, test_session: Session):
        """设置自选列表最大数量"""
        response = admin_client.post("/api/v1/admin/system/config/max-watchlist?max_items=200")
        assert response.status_code == 200
        data = response.json()
        assert data["max_watchlist_items"] == 200

        # 验证数据库中的状态
        from app.services.system_config_service import SystemConfigService
        assert SystemConfigService.get_max_watchlist_items(test_session) == 200


class TestRegistrationIntegration:
    """注册开关集成测试"""

    def test_registration_when_enabled(self, admin_client: TestClient, client: TestClient, test_session: Session):
        """注册开启时可以注册"""
        # 开启注册
        admin_client.post("/api/v1/admin/system/config/registration?enabled=true")

        # 尝试注册
        response = client.post(
            "/api/v1/auth/register",
            json={"username": "newuser", "password": "password123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "newuser"

    def test_registration_when_disabled(self, admin_client: TestClient, client: TestClient):
        """注册关闭时无法注册（403）"""
        # 关闭注册
        admin_client.post("/api/v1/admin/system/config/registration?enabled=false")

        # 尝试注册
        response = client.post(
            "/api/v1/auth/register",
            json={"username": "newuser2", "password": "password123"}
        )
        assert response.status_code == 403
        assert "User registration is currently disabled" in response.json()["detail"]

    def test_registration_toggle_flow(self, admin_client: TestClient, client: TestClient):
        """完整的开启/关闭/开启流程"""
        # 1. 开启注册
        response = admin_client.post("/api/v1/admin/system/config/registration?enabled=true")
        assert response.status_code == 200

        # 2. 验证可以注册
        response = client.post(
            "/api/v1/auth/register",
            json={"username": "user1", "password": "password123"}
        )
        assert response.status_code == 200

        # 3. 关闭注册
        response = admin_client.post("/api/v1/admin/system/config/registration?enabled=false")
        assert response.status_code == 200

        # 4. 验证无法注册
        response = client.post(
            "/api/v1/auth/register",
            json={"username": "user2", "password": "password123"}
        )
        assert response.status_code == 403

        # 5. 再次开启注册
        response = admin_client.post("/api/v1/admin/system/config/registration?enabled=true")
        assert response.status_code == 200

        # 6. 验证可以注册
        response = client.post(
            "/api/v1/auth/register",
            json={"username": "user3", "password": "password123"}
        )
        assert response.status_code == 200
