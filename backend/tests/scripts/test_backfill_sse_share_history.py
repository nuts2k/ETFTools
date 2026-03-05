"""
Tests for scripts/backfill_sse_share_history.py
"""

import pytest
import pandas as pd
from datetime import date
from unittest.mock import patch, MagicMock
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

from app.models.etf_share_history import ETFShareHistory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


# ---------------------------------------------------------------------------
# generate_weekdays
# ---------------------------------------------------------------------------

class TestGenerateWeekdays:
    def setup_method(self):
        from scripts.backfill_sse_share_history import generate_weekdays
        self.generate_weekdays = generate_weekdays

    def test_single_weekday(self):
        result = self.generate_weekdays(date(2025, 1, 2), date(2025, 1, 2))  # Thursday
        assert result == [date(2025, 1, 2)]

    def test_skips_weekend(self):
        # 2025-01-03 Fri, 2025-01-04 Sat, 2025-01-05 Sun, 2025-01-06 Mon
        result = self.generate_weekdays(date(2025, 1, 3), date(2025, 1, 6))
        assert result == [date(2025, 1, 3), date(2025, 1, 6)]

    def test_full_week(self):
        # 2025-01-06 Mon ~ 2025-01-12 Sun → 5 weekdays
        result = self.generate_weekdays(date(2025, 1, 6), date(2025, 1, 12))
        assert len(result) == 5
        assert all(d.weekday() < 5 for d in result)

    def test_start_equals_end_weekend(self):
        result = self.generate_weekdays(date(2025, 1, 4), date(2025, 1, 4))  # Saturday
        assert result == []

    def test_start_after_end_returns_empty(self):
        result = self.generate_weekdays(date(2025, 1, 10), date(2025, 1, 5))
        assert result == []


# ---------------------------------------------------------------------------
# get_existing_dates
# ---------------------------------------------------------------------------

class TestGetExistingDates:
    def setup_method(self):
        self.engine = _make_engine()

    def _insert(self, code, date_str, exchange="SSE"):
        with Session(self.engine) as session:
            record = ETFShareHistory(
                code=code, date=date_str, shares=100.0, exchange=exchange
            )
            session.add(record)
            session.commit()

    def test_returns_empty_when_no_data(self):
        from scripts.backfill_sse_share_history import get_existing_dates
        with patch("scripts.backfill_sse_share_history.share_history_engine", self.engine):
            result = get_existing_dates("2025-01-01", "2025-01-31")
        assert result == set()

    def test_returns_existing_sse_dates(self):
        from scripts.backfill_sse_share_history import get_existing_dates
        self._insert("510300", "2025-01-02")
        self._insert("510500", "2025-01-03")
        with patch("scripts.backfill_sse_share_history.share_history_engine", self.engine):
            result = get_existing_dates("2025-01-01", "2025-01-31")
        assert result == {"2025-01-02", "2025-01-03"}

    def test_excludes_szse_dates(self):
        from scripts.backfill_sse_share_history import get_existing_dates
        self._insert("510300", "2025-01-02", exchange="SSE")
        self._insert("159915", "2025-01-02", exchange="SZSE")
        with patch("scripts.backfill_sse_share_history.share_history_engine", self.engine):
            result = get_existing_dates("2025-01-01", "2025-01-31")
        assert result == {"2025-01-02"}

    def test_respects_date_range(self):
        from scripts.backfill_sse_share_history import get_existing_dates
        self._insert("510300", "2024-12-31")
        self._insert("510300", "2025-01-02")
        self._insert("510300", "2025-02-01")
        with patch("scripts.backfill_sse_share_history.share_history_engine", self.engine):
            result = get_existing_dates("2025-01-01", "2025-01-31")
        assert result == {"2025-01-02"}


# ---------------------------------------------------------------------------
# save_to_database
# ---------------------------------------------------------------------------

class TestSaveToDatabase:
    def setup_method(self):
        self.engine = _make_engine()

    def _count(self):
        with Session(self.engine) as session:
            return len(session.exec(select(ETFShareHistory)).all())

    def test_inserts_new_records(self):
        from scripts.backfill_sse_share_history import save_to_database
        df = pd.DataFrame({
            "code": ["510300", "510500"],
            "shares": [910.62, 320.45],
            "date": ["2025-01-02", "2025-01-02"],
            "etf_type": ["股票型", "股票型"],
        })
        with patch("scripts.backfill_sse_share_history.share_history_engine", self.engine):
            inserted, skipped = save_to_database(df)
        assert inserted == 2
        assert skipped == 0
        assert self._count() == 2

    def test_skips_duplicate_records(self):
        from scripts.backfill_sse_share_history import save_to_database
        df = pd.DataFrame({
            "code": ["510300"],
            "shares": [910.62],
            "date": ["2025-01-02"],
            "etf_type": [None],
        })
        with patch("scripts.backfill_sse_share_history.share_history_engine", self.engine):
            save_to_database(df)
            inserted, skipped = save_to_database(df)
        assert inserted == 0
        assert skipped == 1
        assert self._count() == 1

    def test_assigns_exchange_by_code_prefix(self):
        from scripts.backfill_sse_share_history import save_to_database
        df = pd.DataFrame({
            "code": ["510300", "159915"],
            "shares": [100.0, 200.0],
            "date": ["2025-01-02", "2025-01-02"],
            "etf_type": [None, None],
        })
        with patch("scripts.backfill_sse_share_history.share_history_engine", self.engine):
            save_to_database(df)
        with Session(self.engine) as session:
            records = {r.code: r.exchange for r in session.exec(select(ETFShareHistory)).all()}
        assert records["510300"] == "SSE"
        assert records["159915"] == "SZSE"

    def test_skips_invalid_shares(self):
        from scripts.backfill_sse_share_history import save_to_database
        df = pd.DataFrame({
            "code": ["510300", "510500"],
            "shares": [float("nan"), -1.0],
            "date": ["2025-01-02", "2025-01-02"],
            "etf_type": [None, None],
        })
        with patch("scripts.backfill_sse_share_history.share_history_engine", self.engine):
            inserted, skipped = save_to_database(df)
        assert inserted == 0
        assert self._count() == 0

    def test_empty_dataframe_returns_zero(self):
        from scripts.backfill_sse_share_history import save_to_database
        with patch("scripts.backfill_sse_share_history.share_history_engine", self.engine):
            inserted, skipped = save_to_database(pd.DataFrame())
        assert inserted == 0
        assert skipped == 0
