"""
Tests for fund_flow_service.py and fund_flow_cache_service.py
"""

import pytest
from unittest.mock import Mock, patch
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from app.services.fund_flow_service import FundFlowService
from app.services.fund_flow_cache_service import FundFlowCacheService
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
def sample_records(test_share_engine):
    """插入测试数据"""
    with Session(test_share_engine) as session:
        records = [
            ETFShareHistory(
                code="510300",
                date="2025-01-15",
                shares=910.62,
                exchange="SSE",
                etf_type="股票型"
            ),
            ETFShareHistory(
                code="510500",
                date="2025-01-15",
                shares=450.30,
                exchange="SSE",
                etf_type="股票型"
            ),
            ETFShareHistory(
                code="159915",
                date="2025-01-15",
                shares=320.45,
                exchange="SZSE",
                etf_type="股票型"
            ),
        ]
        for record in records:
            session.add(record)
        session.commit()
    return records


def test_get_current_scale_with_data(test_share_engine, sample_records):
    """测试有数据时获取当前规模"""
    service = FundFlowService()

    with patch("app.services.fund_flow_service.share_history_engine", test_share_engine), \
         patch("app.services.fund_flow_service.etf_cache.get_etf_info", return_value={"price": 3.93}):

        result = service.get_current_scale("510300")

        assert result is not None
        assert result["shares"] == 910.62
        assert result["scale"] is not None
        assert abs(result["scale"] - 910.62 * 3.93) < 0.01
        assert result["update_date"] == "2025-01-15"
        assert result["exchange"] == "SSE"


def test_get_current_scale_no_data(test_share_engine):
    """测试无数据时返回 None"""
    service = FundFlowService()

    with patch("app.services.fund_flow_service.share_history_engine", test_share_engine):
        result = service.get_current_scale("999999")

        assert result is None


def test_get_current_scale_no_price(test_share_engine, sample_records):
    """测试无法获取价格时，scale 为 None"""
    service = FundFlowService()

    with patch("app.services.fund_flow_service.share_history_engine", test_share_engine), \
         patch("app.services.fund_flow_service.etf_cache.get_etf_info", return_value=None):

        result = service.get_current_scale("510300")

        assert result is not None
        assert result["shares"] == 910.62
        assert result["scale"] is None


def test_get_scale_rank(test_share_engine, sample_records):
    """测试排名计算"""
    service = FundFlowService()

    with patch("app.services.fund_flow_service.share_history_engine", test_share_engine):
        result = service.get_scale_rank("510300")

        assert result is not None
        assert result["rank"] == 1  # 份额最大
        assert result["total_count"] == 3
        assert result["percentile"] == 100.0
        assert result["category"] == "股票型"


def test_get_scale_rank_single_etf(test_share_engine):
    """测试只有一只 ETF 时的排名"""
    with Session(test_share_engine) as session:
        record = ETFShareHistory(
            code="510300",
            date="2025-01-15",
            shares=910.62,
            exchange="SSE",
            etf_type="股票型"
        )
        session.add(record)
        session.commit()

    service = FundFlowService()

    with patch("app.services.fund_flow_service.share_history_engine", test_share_engine):
        result = service.get_scale_rank("510300")

        assert result is not None
        assert result["rank"] == 1
        assert result["total_count"] == 1
        assert result["percentile"] == 100.0


def test_cache_hit():
    """测试缓存命中"""
    cache_service = FundFlowCacheService()
    mock_data = {"code": "510300", "current_scale": {"shares": 910.62}}

    with patch("app.services.fund_flow_cache_service.disk_cache.get", return_value=mock_data), \
         patch("app.services.fund_flow_cache_service.fund_flow_service.get_fund_flow_data") as mock_service:

        result = cache_service.get_fund_flow("510300")

        assert result == mock_data
        mock_service.assert_not_called()  # 缓存命中，不调用 service


def test_cache_miss():
    """测试缓存未命中"""
    cache_service = FundFlowCacheService()
    mock_data = {"code": "510300", "current_scale": {"shares": 910.62}}

    with patch("app.services.fund_flow_cache_service.disk_cache.get", return_value=None), \
         patch("app.services.fund_flow_cache_service.disk_cache.set") as mock_set, \
         patch("app.services.fund_flow_cache_service.fund_flow_service.get_fund_flow_data", return_value=mock_data):

        result = cache_service.get_fund_flow("510300")

        assert result == mock_data
        mock_set.assert_called_once()  # 缓存未命中，写入缓存


def test_force_refresh():
    """测试强制刷新"""
    cache_service = FundFlowCacheService()
    mock_data = {"code": "510300", "current_scale": {"shares": 910.62}}

    with patch("app.services.fund_flow_cache_service.disk_cache.get") as mock_get, \
         patch("app.services.fund_flow_cache_service.disk_cache.set"), \
         patch("app.services.fund_flow_cache_service.fund_flow_service.get_fund_flow_data", return_value=mock_data):

        result = cache_service.get_fund_flow("510300", force_refresh=True)

        assert result == mock_data
        mock_get.assert_not_called()  # force_refresh=True，跳过缓存读取
