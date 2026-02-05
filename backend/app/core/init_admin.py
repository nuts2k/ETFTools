"""从环境变量初始化管理员账户"""
import os
import logging
from sqlmodel import Session
from app.core.database import engine
from app.models.user import UserCreate
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)


def init_admin_from_env():
    admin_username = os.getenv("ADMIN_USERNAME")
    admin_password = os.getenv("ADMIN_PASSWORD")
    if not admin_username or not admin_password:
        logger.info("未设置 ADMIN_USERNAME/ADMIN_PASSWORD，跳过管理员初始化")
        return

    with Session(engine) as session:
        existing = AuthService.get_user_by_username(session, admin_username)
        if existing:
            if not existing.is_admin:
                existing.is_admin = True
                session.add(existing)
                session.commit()
                logger.info(f"用户 '{admin_username}' 已升级为管理员")
            else:
                logger.info(f"管理员 '{admin_username}' 已存在")
            return

        user_in = UserCreate(username=admin_username, password=admin_password)
        admin_user = AuthService.create_user(session, user_in)
        admin_user.is_admin = True
        session.add(admin_user)
        session.commit()
        logger.info(f"管理员 '{admin_username}' 创建成功")
