import os
from sqlmodel import SQLModel, create_engine, Session


def _get_share_history_db_url() -> str:
    """构建独立数据库 URL，数据库文件位于 backend/ 目录"""
    backend_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    db_path = os.path.join(backend_dir, "etf_share_history.db")
    return f"sqlite:///{db_path}"


share_history_engine = create_engine(
    _get_share_history_db_url(),
    echo=False,
    connect_args={"check_same_thread": False}
)


def create_share_history_tables():
    """创建份额历史表（仅在独立数据库上创建）"""
    from app.models.etf_share_history import ETFShareHistory
    SQLModel.metadata.create_all(
        share_history_engine,
        tables=[ETFShareHistory.__table__]
    )


def get_share_history_session():
    """获取份额历史数据库会话（FastAPI DI 用）"""
    with Session(share_history_engine) as session:
        yield session
