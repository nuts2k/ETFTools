"""AdminAlertService 单元测试"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zoneinfo import ZoneInfo

from app.services.admin_alert_service import AdminAlertService

_CHINA_TZ = ZoneInfo("Asia/Shanghai")


@pytest.fixture
def alert_service():
    return AdminAlertService()


def _make_mock_admin(user_id=1, bot_token="encrypted_token", chat_id="12345"):
    """创建 mock 管理员用户"""
    user = MagicMock()
    user.id = user_id
    user.is_admin = True
    user.is_active = True
    user.settings = {
        "telegram": {
            "enabled": True,
            "verified": True,
            "botToken": bot_token,
            "chatId": chat_id,
        }
    }
    return user


class TestCooldown:
    def test_first_alert_not_cooled(self, alert_service):
        assert alert_service._is_cooled_down("all_sources_down") is True

    def test_within_cooldown(self, alert_service):
        alert_service._cooldowns["all_sources_down"] = datetime.now(_CHINA_TZ)
        assert alert_service._is_cooled_down("all_sources_down") is False

    def test_after_cooldown(self, alert_service):
        alert_service._cooldowns["all_sources_down"] = (
            datetime.now(_CHINA_TZ) - timedelta(seconds=301)
        )
        assert alert_service._is_cooled_down("all_sources_down") is True

    def test_different_types_independent(self, alert_service):
        alert_service._cooldowns["all_sources_down"] = datetime.now(_CHINA_TZ)
        assert alert_service._is_cooled_down("all_sources_down") is False
        assert alert_service._is_cooled_down("source_recovered") is True


class TestFormatSystemAlert:
    def test_all_sources_down(self):
        msg = AdminAlertService._format_system_alert(
            "all_sources_down", "EastMoney、Sina、THS 均获取失败"
        )
        assert "系统告警" in msg
        assert "所有数据源不可用" in msg
        assert "EastMoney、Sina、THS 均获取失败" in msg

    def test_source_recovered(self):
        msg = AdminAlertService._format_system_alert(
            "source_recovered", "Sina 已恢复"
        )
        assert "数据源恢复" in msg
        assert "Sina 已恢复" in msg

    def test_unknown_type(self):
        msg = AdminAlertService._format_system_alert("custom_type", "some detail")
        assert "系统通知" in msg
        assert "custom_type" in msg


class TestSendAdminAlert:
    @patch.object(AdminAlertService, "_get_telegram_admins", return_value=[])
    def test_no_admins(self, mock_get, alert_service):
        result = alert_service.send_admin_alert_sync("all_sources_down", "test")
        assert result == 0

    @patch("app.services.admin_alert_service.asyncio.run")
    @patch("app.services.admin_alert_service.decrypt_token", return_value="real_token")
    @patch.object(
        AdminAlertService,
        "_get_telegram_admins",
        return_value=[
            {"user_id": 1, "bot_token_encrypted": "enc", "chat_id": "123"}
        ],
    )
    def test_sends_to_admin(self, mock_get, mock_decrypt, mock_run, alert_service):
        result = alert_service.send_admin_alert_sync("all_sources_down", "test detail")
        assert result == 1
        mock_run.assert_called_once()

    @patch("app.services.admin_alert_service.asyncio.run")
    @patch("app.services.admin_alert_service.decrypt_token", return_value="real_token")
    @patch.object(
        AdminAlertService,
        "_get_telegram_admins",
        return_value=[
            {"user_id": 1, "bot_token_encrypted": "enc", "chat_id": "123"}
        ],
    )
    def test_cooldown_prevents_resend(
        self, mock_get, mock_decrypt, mock_run, alert_service
    ):
        # 第一次发送
        result1 = alert_service.send_admin_alert_sync("all_sources_down", "test")
        assert result1 == 1
        # 第二次应被防抖
        result2 = alert_service.send_admin_alert_sync("all_sources_down", "test again")
        assert result2 == 0

    @patch("app.services.admin_alert_service.asyncio.run")
    @patch("app.services.admin_alert_service.decrypt_token", return_value="real_token")
    @patch.object(
        AdminAlertService,
        "_get_telegram_admins",
        return_value=[
            {"user_id": 1, "bot_token_encrypted": "enc", "chat_id": "123"},
            {"user_id": 2, "bot_token_encrypted": "enc2", "chat_id": "456"},
        ],
    )
    def test_sends_to_multiple_admins(
        self, mock_get, mock_decrypt, mock_run, alert_service
    ):
        result = alert_service.send_admin_alert_sync("all_sources_down", "test")
        assert result == 2
        assert mock_run.call_count == 2

    @patch(
        "app.services.admin_alert_service.asyncio.run",
        side_effect=Exception("send failed"),
    )
    @patch("app.services.admin_alert_service.decrypt_token", return_value="real_token")
    @patch.object(
        AdminAlertService,
        "_get_telegram_admins",
        return_value=[
            {"user_id": 1, "bot_token_encrypted": "enc", "chat_id": "123"}
        ],
    )
    def test_handles_send_failure(
        self, mock_get, mock_decrypt, mock_run, alert_service
    ):
        result = alert_service.send_admin_alert_sync("all_sources_down", "test")
        assert result == 0
