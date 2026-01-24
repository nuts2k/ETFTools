import os
from sqlmodel import SQLModel, create_engine, Session

# 确保数据库路径始终指向 backend/etf_tool.db
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sqlite_file_name = os.path.join(BASE_DIR, "etf_tool.db")
sqlite_url = f"sqlite:///{sqlite_file_name}"

engine = create_engine(sqlite_url, echo=False, connect_args={"check_same_thread": False})

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
