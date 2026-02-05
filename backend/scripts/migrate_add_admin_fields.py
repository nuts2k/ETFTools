"""
数据库迁移脚本：添加管理员相关字段到 User 表

使用方式：cd backend && python scripts/migrate_add_admin_fields.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, text
from app.core.database import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_column_exists(session: Session, table: str, column: str) -> bool:
    """检查列是否已存在"""
    result = session.exec(text(f"PRAGMA table_info({table})"))
    columns = [row[1] for row in result]
    return column in columns


def migrate():
    """添加管理员相关字段到 User 表"""
    logger.info("开始数据库迁移...")
    with Session(engine) as session:
        try:
            if not check_column_exists(session, "user", "is_admin"):
                session.exec(text("ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0"))
                logger.info("✅ 添加 is_admin 字段")
            else:
                logger.info("⏭️  is_admin 字段已存在")

            if not check_column_exists(session, "user", "is_active"):
                session.exec(text("ALTER TABLE user ADD COLUMN is_active BOOLEAN DEFAULT 1"))
                logger.info("✅ 添加 is_active 字段")
            else:
                logger.info("⏭️  is_active 字段已存在")

            if not check_column_exists(session, "user", "updated_at"):
                # SQLite 不支持非常量默认值，先添加列再更新现有行
                session.exec(text("ALTER TABLE user ADD COLUMN updated_at TIMESTAMP"))
                session.exec(text("UPDATE user SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL"))
                logger.info("✅ 添加 updated_at 字段")
            else:
                logger.info("⏭️  updated_at 字段已存在")

            session.commit()
            logger.info("✅ 数据库迁移完成")
        except Exception as e:
            session.rollback()
            logger.error(f"❌ 迁移失败: {e}")
            raise


if __name__ == "__main__":
    migrate()
