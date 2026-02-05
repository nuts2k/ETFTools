"""
Shared pytest fixtures for ETFTool backend tests.

Fixtures provide mock data that matches the format returned by akshare_service:
- DataFrame with columns: date, open, high, low, close, volume
- date column as string format 'YYYY-MM-DD'
"""

from __future__ import annotations

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_session
from app.models.user import User, UserCreate
from app.services.auth_service import AuthService


def _generate_ohlcv_data(
    days: int,
    start_price: float = 1.0,
    trend: str = "neutral",
    volatility: float = 0.02,
    start_date: Optional[datetime] = None,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate mock OHLCV data for testing.

    Args:
        days: Number of trading days to generate
        start_price: Starting price
        trend: "bullish", "bearish", or "neutral"
        volatility: Daily volatility (standard deviation of returns)
        start_date: Starting date (defaults to `days` ago from today)
        seed: Random seed for reproducibility

    Returns:
        DataFrame with columns: date, open, high, low, close, volume
    """
    if start_date is None:
        start_date = datetime.now() - timedelta(days=days)

    # Generate dates (skip weekends for realism)
    dates = []
    current_date = start_date
    while len(dates) < days:
        if current_date.weekday() < 5:  # Monday = 0, Friday = 4
            dates.append(current_date.strftime("%Y-%m-%d"))
        current_date += timedelta(days=1)

    # Generate price series with trend
    np.random.seed(seed)

    if trend == "bullish":
        # Strong upward drift that overcomes volatility
        drift = 0.003  # ~0.3% daily upward drift
    elif trend == "bearish":
        # Strong downward drift
        drift = -0.003  # ~0.3% daily downward drift
    else:
        drift = 0.0

    # Generate daily returns with controlled noise
    noise = np.random.normal(0, volatility, days)
    returns = drift + noise
    
    # Calculate close prices
    close_prices = [start_price]
    for r in returns[:-1]:
        close_prices.append(close_prices[-1] * (1 + r))
    close_prices = np.array(close_prices)

    # Generate OHLC from close prices
    # Open is close of previous day with small gap
    open_prices = np.roll(close_prices, 1)
    open_prices[0] = start_price * (1 + np.random.normal(0, volatility / 2))

    # High and low based on intraday volatility
    intraday_range = volatility * 1.5
    high_prices = np.maximum(open_prices, close_prices) * (
        1 + np.abs(np.random.normal(0, intraday_range, days))
    )
    low_prices = np.minimum(open_prices, close_prices) * (
        1 - np.abs(np.random.normal(0, intraday_range, days))
    )

    # Generate volume (random with some correlation to price movement)
    base_volume = 1_000_000
    volume = base_volume * (1 + np.abs(returns) * 10) * np.random.uniform(0.5, 1.5, days)
    volume = volume.astype(int)

    df = pd.DataFrame({
        "date": dates,
        "open": np.round(open_prices, 4),
        "high": np.round(high_prices, 4),
        "low": np.round(low_prices, 4),
        "close": np.round(close_prices, 4),
        "volume": volume,
    })

    return df


@pytest.fixture
def sample_daily_data() -> pd.DataFrame:
    """
    120 days of mock daily OHLCV data.
    
    Use for:
    - ATR calculation tests
    - Short-term trend analysis
    - Drawdown calculations
    """
    return _generate_ohlcv_data(
        days=120,
        start_price=1.0,
        trend="neutral",
        volatility=0.02,
    )


@pytest.fixture
def sample_long_history() -> pd.DataFrame:
    """
    10 years (~2520 trading days) of mock historical data.
    
    Use for:
    - Percentile/quantile calculations
    - Long-term CAGR calculations
    - Historical volatility analysis
    """
    return _generate_ohlcv_data(
        days=2520,  # ~10 years of trading days
        start_price=1.0,
        trend="bullish",  # Slight upward bias for realistic long-term data
        volatility=0.015,
    )


@pytest.fixture
def bullish_trend_data() -> pd.DataFrame:
    """
    90 days of bullish (uptrend) data.
    
    Characteristics:
    - Clear upward price movement
    - MA5 > MA10 > MA20 > MA60 (多头排列)
    - Suitable for testing trend detection
    
    使用更长的数据和更强的趋势来确保均线排列稳定。
    """
    return _generate_ohlcv_data(
        days=90,  # 增加到 90 天以确保均线排列稳定
        start_price=1.0,
        trend="bullish",
        volatility=0.005,  # 更低的波动率以获得更清晰的趋势
        seed=100,
    )


@pytest.fixture
def bearish_trend_data() -> pd.DataFrame:
    """
    90 days of bearish (downtrend) data.
    
    Characteristics:
    - Clear downward price movement
    - MA5 < MA10 < MA20 < MA60 (空头排列)
    - Suitable for testing trend detection
    
    使用更长的数据和更强的趋势来确保均线排列稳定。
    """
    return _generate_ohlcv_data(
        days=90,  # 增加到 90 天以确保均线排列稳定
        start_price=2.0,
        trend="bearish",
        volatility=0.005,  # 更低的波动率以获得更清晰的趋势
        seed=200,
    )


# Utility fixtures for common test scenarios

@pytest.fixture
def empty_dataframe() -> pd.DataFrame:
    """Empty DataFrame with correct schema for edge case testing."""
    return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])


@pytest.fixture
def single_day_data() -> pd.DataFrame:
    """Single day of data for edge case testing."""
    return pd.DataFrame({
        "date": ["2024-01-15"],
        "open": [1.0],
        "high": [1.02],
        "low": [0.98],
        "close": [1.01],
        "volume": [1000000],
    })


# ============================================================================
# Admin System Test Fixtures
# ============================================================================

@pytest.fixture(name="test_engine")
def test_engine_fixture():
    """创建 in-memory SQLite 测试引擎"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture(name="test_session")
def test_session_fixture(test_engine):
    """创建测试数据库会话"""
    with Session(test_engine) as session:
        yield session


@pytest.fixture(name="admin_user")
def admin_user_fixture(test_session: Session) -> User:
    """创建管理员用户"""
    user = User(
        username="admin",
        hashed_password=AuthService.get_password_hash("admin123"),
        is_admin=True,
        is_active=True,
    )
    test_session.add(user)
    test_session.commit()
    test_session.refresh(user)
    return user


@pytest.fixture(name="regular_user")
def regular_user_fixture(test_session: Session) -> User:
    """创建普通用户"""
    user = User(
        username="user",
        hashed_password=AuthService.get_password_hash("user123"),
        is_admin=False,
        is_active=True,
    )
    test_session.add(user)
    test_session.commit()
    test_session.refresh(user)
    return user


@pytest.fixture(name="admin_token")
def admin_token_fixture(admin_user: User) -> str:
    """生成管理员 JWT token"""
    return AuthService.create_access_token(data={"sub": admin_user.username})


@pytest.fixture(name="user_token")
def user_token_fixture(regular_user: User) -> str:
    """生成普通用户 JWT token"""
    return AuthService.create_access_token(data={"sub": regular_user.username})


@pytest.fixture(name="admin_client")
def admin_client_fixture(test_session: Session, admin_token: str):
    """创建带管理员认证的 TestClient"""
    def override_get_session():
        yield test_session

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    client.headers = {"Authorization": f"Bearer {admin_token}"}
    yield client
    app.dependency_overrides.clear()


@pytest.fixture(name="user_client")
def user_client_fixture(test_session: Session, user_token: str):
    """创建带普通用户认证的 TestClient"""
    def override_get_session():
        yield test_session

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    client.headers = {"Authorization": f"Bearer {user_token}"}
    yield client
    app.dependency_overrides.clear()


@pytest.fixture(name="client")
def client_fixture(test_session: Session):
    """创建未认证的 TestClient"""
    def override_get_session():
        yield test_session

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
