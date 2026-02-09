"""
Tests for share_history_backup_service.py
"""

import pytest
import os
import tempfile
from unittest.mock import patch
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from app.services.share_history_backup_service import ShareHistoryBackupService
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
                date="2025-01-16",
                shares=450.30,
                exchange="SSE",
                etf_type="股票型"
            ),
        ]
        for record in records:
            session.add(record)
        session.commit()
    return records


def test_export_to_csv_bytes_with_data(test_share_engine, sample_records):
    """测试有数据时导出 CSV"""
    service = ShareHistoryBackupService()

    with patch("app.services.share_history_backup_service.share_history_engine", test_share_engine):
        csv_bytes = service.export_to_csv_bytes("2025-01-01", "2025-01-31")

        assert csv_bytes is not None
        csv_str = csv_bytes.decode("utf-8")
        assert "510300" in csv_str
        assert "510500" in csv_str
        assert "code,date,shares" in csv_str


def test_export_to_csv_bytes_empty(test_share_engine):
    """测试无数据时返回空 CSV"""
    service = ShareHistoryBackupService()

    with patch("app.services.share_history_backup_service.share_history_engine", test_share_engine):
        csv_bytes = service.export_to_csv_bytes("2024-01-01", "2024-01-31")

        assert csv_bytes is not None
        csv_str = csv_bytes.decode("utf-8")
        assert "code,date,shares" in csv_str  # 仅表头


def test_export_monthly_backup_creates_file(test_share_engine, sample_records):
    """测试月度备份创建文件"""
    service = ShareHistoryBackupService()

    with tempfile.TemporaryDirectory() as tmpdir:
        service.backup_dir = tmpdir

        with patch("app.services.share_history_backup_service.share_history_engine", test_share_engine):
            result = service.export_monthly_backup(2025, 1)

            assert result["success"] is True
            assert os.path.exists(result["filepath"])
            assert "2025-01" in result["filepath"]


def test_backup_directory_auto_creation(test_share_engine):
    """测试备份目录自动创建"""
    service = ShareHistoryBackupService()

    with tempfile.TemporaryDirectory() as tmpdir:
        backup_path = os.path.join(tmpdir, "new_backup_dir")
        service.backup_dir = backup_path

        with patch("app.services.share_history_backup_service.share_history_engine", test_share_engine):
            service.export_monthly_backup(2025, 1)

            assert os.path.exists(backup_path)
