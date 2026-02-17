"""
Tests for fund_flow_collector.py
"""

import pytest
import pandas as pd
from unittest.mock import patch
from sqlmodel import Session, SQLModel, create_engine, select
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
def sample_szse_data():
    """模拟深交所返回的数据（实际 akshare 列名，份额单位为份，无日期列）"""
    return pd.DataFrame({
        "基金代码": ["159915", "159919"],
        "基金简称": ["创业板ETF", "沪深300ETF"],
        "基金类别": ["ETF", "ETF"],
        "基金份额": [32045000000.0, 28012000000.0],
    })


def test_fetch_szse_shares_success(sample_szse_data):
    """测试成功获取深交所数据"""
    collector = FundFlowCollector()

    with patch("akshare.fund_etf_scale_szse", return_value=sample_szse_data):
        result = collector._fetch_szse_shares()

    assert result is not None
    assert len(result) == 2
    assert "code" in result.columns
    assert "shares" in result.columns


def test_save_to_database(test_share_engine):
    """测试保存标准化数据到数据库"""
    collector = FundFlowCollector()

    df = pd.DataFrame({
        "code": ["510300", "159915"],
        "shares": [910.62, 320.45],
        "date": ["2026-02-13", "2026-02-13"],
        "etf_type": ["股票型", "股票型"],
    })

    with patch("app.services.fund_flow_collector.share_history_engine", test_share_engine):
        count = collector._save_to_database(df)

    assert count == 2

    with Session(test_share_engine) as session:
        records = session.exec(select(ETFShareHistory)).all()
        assert len(records) == 2
        sse_record = [r for r in records if r.code == "510300"][0]
        szse_record = [r for r in records if r.code == "159915"][0]
        assert sse_record.exchange == "SSE"
        assert szse_record.exchange == "SZSE"


def test_save_to_database_dedup(test_share_engine):
    """测试重复数据去重"""
    collector = FundFlowCollector()

    df = pd.DataFrame({
        "code": ["510300", "159915"],
        "shares": [910.62, 320.45],
        "date": ["2026-02-13", "2026-02-13"],
        "etf_type": [None, None],
    })

    with patch("app.services.fund_flow_collector.share_history_engine", test_share_engine):
        count1 = collector._save_to_database(df)
        assert count1 == 2

        count2 = collector._save_to_database(df)
        assert count2 == 0

        with Session(test_share_engine) as session:
            records = session.exec(select(ETFShareHistory)).all()
            assert len(records) == 2


@pytest.fixture
def sample_sina_list_data():
    """模拟 Sina 列表接口返回的数据（含债券 ETF）"""
    return pd.DataFrame({
        "代码": ["sh510300", "sh510500", "sz159915", "sh511260", "sh511270"],
        "名称": ["沪深300ETF", "中证500ETF", "创业板ETF", "国泰上证10年期国债ETF", "国债ETF"],
    })


def test_build_etf_whitelist_filters_bond_etfs(sample_sina_list_data):
    """测试白名单构建：过滤债券 ETF"""
    collector = FundFlowCollector()

    with patch("akshare.fund_etf_category_sina", return_value=sample_sina_list_data):
        whitelist = collector._build_etf_whitelist()

    assert "510300" in whitelist
    assert "510500" in whitelist
    assert "159915" in whitelist
    assert "511260" not in whitelist
    assert "511270" not in whitelist
    assert len(whitelist) == 3


def test_build_etf_whitelist_returns_none_on_failure():
    """测试 Sina 列表接口失败时返回 None"""
    collector = FundFlowCollector()

    with patch("akshare.fund_etf_category_sina", side_effect=Exception("API error")):
        whitelist = collector._build_etf_whitelist()

    assert whitelist is None


@pytest.fixture
def sample_em_data():
    """模拟 EastMoney 列表接口返回的数据"""
    return pd.DataFrame({
        "代码": ["510300", "510500", "159915", "159919"],
        "名称": ["沪深300ETF", "中证500ETF", "创业板ETF", "沪深300ETF"],
        "最新份额": [91062000000.0, 45030000000.0, 32045000000.0, 28012000000.0],
        "数据日期": ["2026-02-13", "2026-02-13", "2026-02-13", "2026-02-13"],
    })


def test_fetch_em_shares_success(sample_em_data):
    """测试成功获取 EastMoney 份额数据"""
    collector = FundFlowCollector()
    whitelist = {"510300", "510500", "159915", "159919"}

    with patch("akshare.fund_etf_spot_em", return_value=sample_em_data):
        result = collector._fetch_em_shares(whitelist)

    assert result is not None
    assert len(result) == 4
    assert "code" in result.columns
    assert "shares" in result.columns
    assert "date" in result.columns
    # 验证份额单位已转换为亿份
    assert result.loc[result["code"] == "510300", "shares"].iloc[0] == pytest.approx(910.62, rel=0.01)


def test_fetch_em_shares_filters_by_whitelist(sample_em_data):
    """测试白名单过滤"""
    collector = FundFlowCollector()
    whitelist = {"510300", "159915"}

    with patch("akshare.fund_etf_spot_em", return_value=sample_em_data):
        result = collector._fetch_em_shares(whitelist)

    assert result is not None
    assert len(result) == 2
    assert set(result["code"]) == {"510300", "159915"}


def test_fetch_em_shares_returns_none_on_failure():
    """测试 EastMoney 接口失败时返回 None"""
    collector = FundFlowCollector()

    with patch("akshare.fund_etf_spot_em", side_effect=Exception("API error")):
        result = collector._fetch_em_shares({"510300"})

    assert result is None


@pytest.fixture
def sample_szse_data_with_lof():
    """模拟深交所返回的数据（含 LOF 和 ETF）"""
    return pd.DataFrame({
        "基金代码": ["159915", "159919", "160219", "169106"],
        "基金简称": ["创业板ETF", "沪深300ETF", "医药LOF", "东方红创优定开"],
        "基金类别": ["ETF", "ETF", "LOF", "LOF"],
        "基金份额": [32045000000.0, 28012000000.0, 157574115.0, 54000000.0],
    })


def test_fetch_szse_shares_filters_etf_only(sample_szse_data_with_lof):
    """测试深交所数据只保留 ETF，过滤 LOF"""
    collector = FundFlowCollector()
    whitelist = {"159915", "159919", "160219", "169106"}

    with patch("akshare.fund_etf_scale_szse", return_value=sample_szse_data_with_lof):
        result = collector._fetch_szse_shares(whitelist)

    assert result is not None
    assert len(result) == 2
    assert set(result["code"]) == {"159915", "159919"}


def test_fetch_szse_shares_filters_by_whitelist(sample_szse_data_with_lof):
    """测试深交所数据按白名单过滤"""
    collector = FundFlowCollector()
    whitelist = {"159915"}

    with patch("akshare.fund_etf_scale_szse", return_value=sample_szse_data_with_lof):
        result = collector._fetch_szse_shares(whitelist)

    assert result is not None
    assert len(result) == 1
    assert result.iloc[0]["code"] == "159915"
    assert result.iloc[0]["shares"] == pytest.approx(320.45, rel=0.01)


def test_collect_daily_snapshot_new_flow():
    """测试新的采集流程：同日期时 SZSE 覆盖 EastMoney 深市数据"""
    collector = FundFlowCollector()

    whitelist = {"510300", "510500", "159915", "159919"}

    em_df = pd.DataFrame({
        "code": ["510300", "510500", "159915", "159919"],
        "shares": [910.62, 450.30, 320.45, 280.12],
        "date": ["2026-02-17"] * 4,
        "etf_type": [None] * 4,
    })

    szse_df = pd.DataFrame({
        "code": ["159915", "159919"],
        "shares": [321.00, 281.00],
        "date": ["2026-02-17"] * 2,
        "etf_type": ["ETF"] * 2,
    })

    with patch.object(collector, "_build_etf_whitelist", return_value=whitelist), \
         patch.object(collector, "_fetch_em_shares", return_value=em_df), \
         patch.object(collector, "_fetch_szse_shares", return_value=szse_df), \
         patch.object(collector, "_save_to_database", return_value=4) as mock_save:

        result = collector.collect_daily_snapshot()

        assert result["success"] is True
        assert result["collected"] == 4

        # 验证合并后只有 4 条（SZSE 覆盖了同日期的 EM 深市数据）
        saved_df = mock_save.call_args[0][0]
        assert len(saved_df) == 4
        szse_159915 = saved_df.loc[saved_df["code"] == "159915", "shares"].iloc[0]
        assert szse_159915 == pytest.approx(321.00, rel=0.01)


def test_collect_daily_snapshot_different_dates_kept():
    """测试不同日期的数据都保留（EM 昨天 + SZSE 今天）"""
    collector = FundFlowCollector()

    whitelist = {"510300", "159915"}

    em_df = pd.DataFrame({
        "code": ["510300", "159915"],
        "shares": [910.62, 320.45],
        "date": ["2026-02-14"] * 2,
        "etf_type": [None] * 2,
    })

    szse_df = pd.DataFrame({
        "code": ["159915"],
        "shares": [321.00],
        "date": ["2026-02-17"],
        "etf_type": ["ETF"],
    })

    with patch.object(collector, "_build_etf_whitelist", return_value=whitelist), \
         patch.object(collector, "_fetch_em_shares", return_value=em_df), \
         patch.object(collector, "_fetch_szse_shares", return_value=szse_df), \
         patch.object(collector, "_save_to_database", return_value=3) as mock_save:

        result = collector.collect_daily_snapshot()

        # EM 的 159915(02-14) 和 SZSE 的 159915(02-17) 日期不同，都保留
        saved_df = mock_save.call_args[0][0]
        assert len(saved_df) == 3
        codes_159915 = saved_df[saved_df["code"] == "159915"]
        assert len(codes_159915) == 2


def test_collect_daily_snapshot_em_failure_fallback():
    """测试 EastMoney 失败时降级到 SZSE"""
    collector = FundFlowCollector()

    whitelist = {"510300", "159915"}

    szse_df = pd.DataFrame({
        "code": ["159915"],
        "shares": [321.00],
        "date": ["2026-02-17"],
        "etf_type": ["ETF"],
    })

    with patch.object(collector, "_build_etf_whitelist", return_value=whitelist), \
         patch.object(collector, "_fetch_em_shares", return_value=None), \
         patch.object(collector, "_fetch_szse_shares", return_value=szse_df), \
         patch.object(collector, "_save_to_database", return_value=1):

        result = collector.collect_daily_snapshot()

        assert result["success"] is True
        assert result["collected"] == 1


def test_collect_daily_snapshot_whitelist_failure():
    """测试白名单构建失败时的处理"""
    collector = FundFlowCollector()

    with patch.object(collector, "_build_etf_whitelist", return_value=None):

        result = collector.collect_daily_snapshot()

        assert result["success"] is False
        assert result["collected"] == 0
