"""
每日摘要功能集成测试

测试完整的端到端流程：用户配置 → 数据获取 → 摘要生成 → 消息发送
"""

import pytest
import pandas as pd
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
from sqlmodel import Session

from app.models.user import User, Watchlist
from app.models.alert_config import SignalItem, SignalPriority
from app.services.alert_scheduler import AlertScheduler
from app.services.alert_state_service import AlertStateService
from app.core.encryption import encrypt_token
from app.core.config import settings


@pytest.fixture
def mock_etf_data():
    """Mock ETF 数据"""
    return {
        "510300": {
            "info": {
                "name": "沪深300ETF",
                "code": "510300",
                "change_pct": 1.25,
                "close": 4.123,
            },
            "metrics": {
                "temperature": {"score": 55, "level": "warm"},
                "daily_trend": "上涨",
                "weekly_trend": "震荡",
            },
        },
        "512480": {
            "info": {
                "name": "半导体ETF",
                "code": "512480",
                "change_pct": 2.35,
                "close": 1.234,
            },
            "metrics": {
                "temperature": {"score": 68, "level": "warm"},
                "daily_trend": "上涨",
                "weekly_trend": "上涨",
            },
        },
        "512010": {
            "info": {
                "name": "医药ETF",
                "code": "512010",
                "change_pct": -1.56,
                "close": 0.987,
            },
            "metrics": {
                "temperature": {"score": 28, "level": "cool"},
                "daily_trend": "下跌",
                "weekly_trend": "下跌",
            },
        },
    }


@pytest.fixture
def test_user_with_watchlist(test_session: Session):
    """创建带自选列表和 Telegram 配置的测试用户"""
    # 创建用户
    user = User(
        username="test_summary_user",
        hashed_password="hashed_password",
        is_active=True,
        settings={
            "telegram": {
                "enabled": True,
                "botToken": encrypt_token("test_bot_token", settings.SECRET_KEY),
                "chatId": "123456789",
                "verified": True,
            },
            "alerts": {
                "daily_summary": True,  # 启用每日摘要
            }
        },
    )
    test_session.add(user)
    test_session.commit()
    test_session.refresh(user)

    # 添加自选列表
    watchlist_items = [
        Watchlist(user_id=user.id, etf_code="510300", name="沪深300ETF", sort_order=0),
        Watchlist(user_id=user.id, etf_code="512480", name="半导体ETF", sort_order=1),
        Watchlist(user_id=user.id, etf_code="512010", name="医药ETF", sort_order=2),
    ]
    for item in watchlist_items:
        test_session.add(item)
    test_session.commit()

    return user


@pytest.fixture
def test_user_summary_disabled(test_session: Session):
    """创建禁用每日摘要的测试用户"""
    user = User(
        username="test_summary_disabled",
        hashed_password="hashed_password",
        is_active=True,
        settings={
            "telegram": {
                "enabled": True,
                "botToken": encrypt_token("test_bot_token", settings.SECRET_KEY),
                "chatId": "987654321",
                "verified": True,
            },
            "alerts": {
                "daily_summary": False,  # 禁用每日摘要
            }
        },
    )
    test_session.add(user)
    test_session.commit()
    test_session.refresh(user)

    # 添加自选列表
    watchlist_items = [
        Watchlist(user_id=user.id, etf_code="510300", name="沪深300ETF", sort_order=0),
    ]
    for item in watchlist_items:
        test_session.add(item)
    test_session.commit()

    return user


# ===== 集成测试 =====


@pytest.mark.asyncio
async def test_run_daily_summary_end_to_end(
    test_session: Session,
    test_user_with_watchlist: User,
    mock_etf_data: dict,
):
    """测试完整的每日摘要生成和发送流程"""

    # Mock 外部依赖
    with patch('app.services.alert_scheduler.ak_service') as mock_ak_service, \
         patch('app.services.alert_scheduler.temperature_service') as mock_temp_service, \
         patch('app.services.alert_scheduler.trend_service') as mock_trend_service, \
         patch('app.services.alert_scheduler.TelegramNotificationService.send_message') as mock_send, \
         patch('app.services.alert_scheduler.Session') as mock_session_cls, \
         patch('app.services.alert_scheduler.alert_state_service') as mock_state_service:

        # 配置 Session mock 返回测试会话
        mock_session_cls.return_value.__enter__.return_value = test_session

        # 配置 akshare mock
        def mock_get_etf_info(code):
            return mock_etf_data.get(code, {}).get("info")

        mock_ak_service.get_etf_info.side_effect = mock_get_etf_info

        # 配置历史数据 mock（用于温度计算）
        test_df = pd.DataFrame({
            'date': pd.date_range(start='2023-01-01', periods=100),
            'close': [3.0 + i * 0.01 for i in range(100)],
            'high': [3.0 + i * 0.01 + 0.05 for i in range(100)],
            'low': [3.0 + i * 0.01 - 0.05 for i in range(100)],
            'open': [3.0 + i * 0.01 for i in range(100)],
            'volume': [1000000 for _ in range(100)],
        })
        mock_ak_service.fetch_history_raw.return_value = test_df

        # 配置温度和趋势服务 mock
        def mock_calculate_temperature(df):
            return mock_etf_data.get("510300", {}).get("metrics", {}).get("temperature")

        mock_temp_service.calculate_temperature.side_effect = mock_calculate_temperature
        mock_trend_service.get_daily_trend.return_value = "上涨"
        mock_trend_service.get_weekly_trend.return_value = "震荡"

        # 配置状态服务 mock
        mock_state_service.is_summary_sent_today.return_value = False
        mock_state_service.get_today_signals.return_value = []

        # 配置 Telegram 发送 mock
        mock_send.return_value = None

        # 执行测试
        scheduler = AlertScheduler()
        await scheduler._run_daily_summary()

        # 验证：应该调用了 Telegram 发送
        assert mock_send.called, "应该调用 Telegram 发送消息"
        assert mock_send.call_count == 1, "应该只发送一次消息"

        # 验证：发送的消息内容
        call_args = mock_send.call_args
        bot_token = call_args[0][0]
        chat_id = call_args[0][1]
        message = call_args[0][2]

        assert bot_token == "test_bot_token"
        assert chat_id == "123456789"
        assert "自选日报" in message
        assert "510300" in message or "沪深300ETF" in message

        # 验证：标记摘要已发送
        mock_state_service.mark_summary_sent.assert_called_once_with(test_user_with_watchlist.id)


@pytest.mark.asyncio
async def test_daily_summary_deduplication(
    test_session: Session,
    test_user_with_watchlist: User,
    mock_etf_data: dict,
):
    """测试每日摘要去重逻辑：同一天不会重复发送"""

    with patch('app.services.alert_scheduler.ak_service') as mock_ak_service, \
         patch('app.services.alert_scheduler.temperature_service') as mock_temp_service, \
         patch('app.services.alert_scheduler.trend_service') as mock_trend_service, \
         patch('app.services.alert_scheduler.TelegramNotificationService.send_message') as mock_send, \
         patch('app.services.alert_scheduler.Session') as mock_session_cls, \
         patch('app.services.alert_scheduler.alert_state_service') as mock_state_service:

        mock_session_cls.return_value.__enter__.return_value = test_session

        # 配置 mock：摘要今日已发送
        mock_state_service.is_summary_sent_today.return_value = True

        # 执行测试
        scheduler = AlertScheduler()
        await scheduler._run_daily_summary()

        # 验证：不应该调用 Telegram 发送
        assert not mock_send.called, "摘要已发送，不应该重复发送"

        # 验证：不应该标记摘要已发送（因为已经发送过了）
        assert not mock_state_service.mark_summary_sent.called


@pytest.mark.asyncio
async def test_daily_summary_retry_logic(
    test_session: Session,
    test_user_with_watchlist: User,
    mock_etf_data: dict,
):
    """测试发送失败时的重试逻辑"""

    with patch('app.services.alert_scheduler.ak_service') as mock_ak_service, \
         patch('app.services.alert_scheduler.temperature_service') as mock_temp_service, \
         patch('app.services.alert_scheduler.trend_service') as mock_trend_service, \
         patch('app.services.alert_scheduler.TelegramNotificationService.send_message') as mock_send, \
         patch('app.services.alert_scheduler.Session') as mock_session_cls, \
         patch('app.services.alert_scheduler.alert_state_service') as mock_state_service, \
         patch('app.services.alert_scheduler.asyncio.sleep') as mock_sleep:

        mock_session_cls.return_value.__enter__.return_value = test_session

        # 配置 akshare mock
        def mock_get_etf_info(code):
            return mock_etf_data.get(code, {}).get("info")

        mock_ak_service.get_etf_info.side_effect = mock_get_etf_info

        # 配置历史数据 mock
        test_df = pd.DataFrame({
            'date': pd.date_range(start='2023-01-01', periods=100),
            'close': [3.0 + i * 0.01 for i in range(100)],
            'high': [3.0 + i * 0.01 + 0.05 for i in range(100)],
            'low': [3.0 + i * 0.01 - 0.05 for i in range(100)],
            'open': [3.0 + i * 0.01 for i in range(100)],
            'volume': [1000000 for _ in range(100)],
        })
        mock_ak_service.fetch_history_raw.return_value = test_df

        mock_temp_service.calculate_temperature.return_value = {"score": 55, "level": "warm"}
        mock_trend_service.get_daily_trend.return_value = "上涨"
        mock_trend_service.get_weekly_trend.return_value = "震荡"

        mock_state_service.is_summary_sent_today.return_value = False
        mock_state_service.get_today_signals.return_value = []

        # 配置 Telegram 发送 mock：第一次失败，第二次成功
        mock_send.side_effect = [
            Exception("Network error"),  # 第一次失败
            None,  # 重试成功
        ]

        # 执行测试
        scheduler = AlertScheduler()
        await scheduler._run_daily_summary()

        # 验证：应该调用了两次 Telegram 发送（第一次失败，重试成功）
        assert mock_send.call_count == 2, "应该重试一次"

        # 验证：应该等待 30 秒后重试
        mock_sleep.assert_called_once_with(30)

        # 验证：重试成功后标记摘要已发送
        mock_state_service.mark_summary_sent.assert_called_once_with(test_user_with_watchlist.id)


@pytest.mark.asyncio
async def test_daily_summary_disabled_user_not_sent(
    test_session: Session,
    test_user_summary_disabled: User,
    mock_etf_data: dict,
):
    """测试禁用每日摘要的用户不会收到消息"""

    with patch('app.services.alert_scheduler.ak_service') as mock_ak_service, \
         patch('app.services.alert_scheduler.TelegramNotificationService.send_message') as mock_send, \
         patch('app.services.alert_scheduler.Session') as mock_session_cls, \
         patch('app.services.alert_scheduler.alert_state_service') as mock_state_service:

        mock_session_cls.return_value.__enter__.return_value = test_session

        # 执行测试
        scheduler = AlertScheduler()
        await scheduler._run_daily_summary()

        # 验证：不应该调用 Telegram 发送（用户禁用了摘要）
        assert not mock_send.called, "禁用摘要的用户不应该收到消息"

        # 验证：不应该标记摘要已发送
        assert not mock_state_service.mark_summary_sent.called


