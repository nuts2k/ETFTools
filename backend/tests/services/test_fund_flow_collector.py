"""
Tests for fund_flow_collector.py
"""

import pytest
import pandas as pd
from unittest.mock import Mock, patch
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from app.services.fund_flow_collector import FundFlowCollector
from app.models.etf_share_history import ETFShareHistory


@pytest.fixture
def test_share_engine():
    """创建测试用的内存数据库引擎"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def sample_sse_data():
    """模拟上交所返回的数据（实际 akshare 列名，份额单位为份）"""
    return pd.DataFrame({
        "基金代码": ["510300", "510500"],
        "基金份额": [91062000000.0, 45030000000.0],
        "统计日期": ["2025-01-15", "2025-01-15"],
        "ETF类型": ["股票型", "股票型"],
    })


@pytest.fixture
def sample_szse_data():
    """模拟深交所返回的数据（实际 akshare 列名，份额单位为份，无日期列）"""
    return pd.DataFrame({
        "基金代码": ["159915", "159919"],
        "基金份额": [32045000000.0, 28012000000.0],
        "基金类别": ["股票型", "股票型"],
    })


def test_fetch_sse_shares_success(sample_sse_data):
    """测试成功获取上交所数据"""
    collector = FundFlowCollector()

    with patch("akshare.fund_etf_scale_sse", return_value=sample_sse_data):
        result = collector._fetch_sse_shares()

        assert result is not None
        assert len(result) == 2
        assert "基金代码" in result.columns


def test_fetch_szse_shares_success(sample_szse_data):
    """测试成功获取深交所数据"""
    collector = FundFlowCollector()

    with patch("akshare.fund_etf_scale_szse", return_value=sample_szse_data):
        result = collector._fetch_szse_shares()

        assert result is not None
        assert len(result) == 2
        assert "基金代码" in result.columns


def test_save_to_database(test_share_engine, sample_sse_data):
    """测试保存数据到数据库"""
    collector = FundFlowCollector()

    with patch("app.services.fund_flow_collector.share_history_engine", test_share_engine):
        count = collector._save_to_database(
            sample_sse_data, "SSE", collector.COLUMN_MAP_SSE
        )

        assert count == 2

        # 验证数据已保存
        with Session(test_share_engine) as session:
            records = session.query(ETFShareHistory).all()
            assert len(records) == 2
            assert records[0].code == "510300"
            assert records[0].exchange == "SSE"


def test_save_to_database_dedup(test_share_engine, sample_sse_data):
    """测试重复数据去重"""
    collector = FundFlowCollector()

    with patch("app.services.fund_flow_collector.share_history_engine", test_share_engine):
        # 第一次插入
        count1 = collector._save_to_database(
            sample_sse_data, "SSE", collector.COLUMN_MAP_SSE
        )
        assert count1 == 2

        # 第二次插入相同数据（应该被去重）
        count2 = collector._save_to_database(
            sample_sse_data, "SSE", collector.COLUMN_MAP_SSE
        )
        assert count2 == 0

        # 验证数据库中只有2条记录
        with Session(test_share_engine) as session:
            records = session.query(ETFShareHistory).all()
            assert len(records) == 2


def test_collect_daily_snapshot_partial_failure(sample_sse_data):
    """测试部分失败的情况（一个交易所失败）"""
    collector = FundFlowCollector()

    with patch.object(collector, "_fetch_sse_shares", return_value=sample_sse_data), \
         patch.object(collector, "_fetch_szse_shares", return_value=None), \
         patch.object(collector, "_save_to_database", return_value=2):

        result = collector.collect_daily_snapshot()

        assert result["success"] is True
        assert result["collected"] == 2
        assert result["failed"] == 1


def test_collect_daily_snapshot_all_success(sample_sse_data, sample_szse_data):
    """测试全部成功的情况"""
    collector = FundFlowCollector()

    with patch.object(collector, "_fetch_sse_shares", return_value=sample_sse_data), \
         patch.object(collector, "_fetch_szse_shares", return_value=sample_szse_data), \
         patch.object(collector, "_save_to_database", side_effect=[2, 2]):

        result = collector.collect_daily_snapshot()

        assert result["success"] is True
        assert result["collected"] == 4
        assert result["failed"] == 0
