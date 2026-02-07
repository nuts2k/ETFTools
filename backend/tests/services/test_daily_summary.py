"""
每日摘要功能测试
"""

import pytest
import tempfile
import shutil
from unittest.mock import patch
from datetime import date

from diskcache import Cache

from app.models.alert_config import SignalItem, SignalPriority
from app.services.notification_service import TelegramNotificationService
from app.services.alert_state_service import AlertStateService


# ===== format_daily_summary 测试 =====


def _make_items(data: list[tuple]) -> list[dict]:
    """辅助：生成 items 列表 (name, code, change_pct, score, level)"""
    return [
        {
            "name": d[0], "code": d[1], "change_pct": d[2],
            "temperature_score": d[3], "temperature_level": d[4],
        }
        for d in data
    ]


def _make_signal(code, name, detail, priority=SignalPriority.MEDIUM) -> SignalItem:
    return SignalItem(
        etf_code=code, etf_name=name,
        signal_type="test", signal_detail=detail, priority=priority,
    )


def test_format_daily_summary_basic():
    """基本格式化：涨跌概览、涨跌幅排行、温度分布"""
    items = _make_items([
        ("半导体ETF", "512480", 2.35, 68, "warm"),
        ("沪深300ETF", "510300", 1.12, 52, "warm"),
        ("中证500ETF", "510500", 0.87, 45, "cool"),
        ("医药ETF", "512010", -1.56, 28, "cool"),
        ("消费ETF", "159928", -0.93, 35, "cool"),
        ("新能源ETF", "516160", -0.41, 41, "warm"),
    ])
    result = TelegramNotificationService.format_daily_summary(
        items, [], "2026-02-07 (周五)"
    )
    assert "自选日报" in result
    assert "2026-02-07" in result
    assert "涨: 3" in result
    assert "跌: 3" in result
    assert "涨幅前三" in result
    assert "跌幅前三" in result
    assert "512480" in result
    assert "512010" in result
    # 温度分布
    assert "cool: 3" in result
    assert "warm: 3" in result


def test_format_daily_summary_few_items():
    """自选 ≤ 3 只时展示完整列表，不分涨跌排行"""
    items = _make_items([
        ("沪深300ETF", "510300", 1.12, 52, "warm"),
        ("医药ETF", "512010", -1.56, 28, "cool"),
    ])
    result = TelegramNotificationService.format_daily_summary(
        items, [], "2026-02-07 (周五)"
    )
    assert "涨幅前三" not in result
    assert "跌幅前三" not in result
    assert "510300" in result
    assert "512010" in result


def test_format_daily_summary_all_up():
    """全部上涨：只显示涨幅排行"""
    items = _make_items([
        ("A", "001", 2.0, 60, "warm"),
        ("B", "002", 1.0, 50, "warm"),
        ("C", "003", 0.5, 40, "cool"),
        ("D", "004", 0.3, 35, "cool"),
    ])
    result = TelegramNotificationService.format_daily_summary(items, [], "2026-02-07 (周五)")
    assert "涨幅前三" in result
    assert "跌幅前三" not in result


def test_format_daily_summary_all_down():
    """全部下跌：只显示跌幅排行"""
    items = _make_items([
        ("A", "001", -2.0, 20, "freezing"),
        ("B", "002", -1.0, 30, "cool"),
        ("C", "003", -0.5, 35, "cool"),
        ("D", "004", -0.3, 38, "cool"),
    ])
    result = TelegramNotificationService.format_daily_summary(items, [], "2026-02-07 (周五)")
    assert "涨幅前三" not in result
    assert "跌幅前三" in result


def test_format_daily_summary_no_signals():
    """无信号时省略信号区块"""
    items = _make_items([("A", "001", 1.0, 50, "warm")])
    result = TelegramNotificationService.format_daily_summary(
        items, [], "2026-02-07 (周五)"
    )
    assert "今日信号" not in result


def test_format_daily_summary_with_signals():
    """有信号时展示信号区块"""
    items = _make_items([("A", "001", 1.0, 50, "warm")])
    signals = [
        _make_signal("001", "A", "温度 cool→warm"),
        _make_signal("002", "B", "RSI<30 超卖"),
    ]
    result = TelegramNotificationService.format_daily_summary(
        items, signals, "2026-02-07 (周五)"
    )
    assert "今日信号" in result
    assert "(2)" in result
    assert "cool→warm" in result
    assert "RSI<30" in result


# ===== alert_state_service 测试 =====


@pytest.fixture
def state_service(tmp_path):
    """使用临时目录创建 AlertStateService 实例"""
    svc = AlertStateService()
    svc._cache = Cache(str(tmp_path / "test_cache"))
    yield svc
    svc._cache.close()


def test_mark_signal_sent_stores_detail(state_service):
    """mark_signal_sent 同时存储信号详情"""
    signal = _make_signal("510300", "沪深300ETF", "温度 cool→warm")
    state_service.mark_signal_sent(1, "510300", "test", signal_item=signal)

    signals = state_service.get_today_signals(1)
    assert len(signals) == 1
    assert signals[0].etf_code == "510300"
    assert signals[0].signal_detail == "温度 cool→warm"


def test_get_today_signals_multiple(state_service):
    """get_today_signals 返回当日所有信号"""
    s1 = _make_signal("510300", "沪深300ETF", "信号1")
    s2 = _make_signal("512480", "半导体ETF", "信号2")
    state_service.mark_signal_sent(1, "510300", "t1", signal_item=s1)
    state_service.mark_signal_sent(1, "512480", "t2", signal_item=s2)

    signals = state_service.get_today_signals(1)
    assert len(signals) == 2


def test_get_today_signals_empty(state_service):
    """无信号时返回空列表"""
    signals = state_service.get_today_signals(999)
    assert signals == []


def test_summary_dedup(state_service):
    """is_summary_sent_today + mark_summary_sent 去重"""
    assert state_service.is_summary_sent_today(1) is False
    state_service.mark_summary_sent(1)
    assert state_service.is_summary_sent_today(1) is True
