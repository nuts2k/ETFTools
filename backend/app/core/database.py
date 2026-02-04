import os
from sqlmodel import SQLModel, create_engine, Session
from app.core.config import settings


def get_database_url() -> str:
    """
    从配置获取数据库 URL，支持相对路径和绝对路径。
    对于 SQLite 相对路径，自动转换为绝对路径。

    支持的格式:
    - sqlite:///./filename.db (相对于 backend 目录)
    - sqlite:///filename.db (相对于 backend 目录，如果不是绝对路径)
    - sqlite:////absolute/path/to/file.db (绝对路径，四个斜杠)
    - postgresql://... (其他数据库直接使用)
    """
    db_url = settings.DATABASE_URL

    # 处理 SQLite 相对路径 (sqlite:///./filename.db)
    if db_url.startswith("sqlite:///./"):
        relative_path = db_url.replace("sqlite:///./", "")

        # 安全检查：防止路径遍历攻击
        if ".." in relative_path or relative_path.startswith("/"):
            raise ValueError(
                f"Invalid database path: {relative_path}. "
                "Path traversal (../) and absolute paths are not allowed in relative URLs."
            )

        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        absolute_path = os.path.join(backend_dir, relative_path)
        db_url = f"sqlite:///{absolute_path}"
    # 处理 SQLite 相对路径 (sqlite:///filename.db)
    elif db_url.startswith("sqlite:///") and not db_url.startswith("sqlite:////"):
        relative_path = db_url.replace("sqlite:///", "")
        # 检查是否为绝对路径
        if not os.path.isabs(relative_path):
            # 安全检查：防止路径遍历攻击
            if ".." in relative_path:
                raise ValueError(
                    f"Invalid database path: {relative_path}. "
                    "Path traversal (../) is not allowed."
                )

            backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            absolute_path = os.path.join(backend_dir, relative_path)
            db_url = f"sqlite:///{absolute_path}"

    return db_url


sqlite_url = get_database_url()
engine = create_engine(sqlite_url, echo=False, connect_args={"check_same_thread": False})

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
