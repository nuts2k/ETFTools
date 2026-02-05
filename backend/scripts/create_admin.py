"""
管理员创建脚本（交互式）

使用方式：cd backend && python scripts/create_admin.py
"""
import sys
import os
import getpass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select
from app.core.database import engine
from app.models.user import User, UserCreate
from app.services.auth_service import AuthService


def create_admin():
    print("=== ETFTool 管理员创建工具 ===\n")
    with Session(engine) as session:
        # 检查现有管理员
        existing = session.exec(select(User).where(User.is_admin == True)).all()
        if existing:
            print(f"⚠️  当前已有 {len(existing)} 个管理员:")
            for admin in existing:
                print(f"   - {admin.username} (ID: {admin.id})")
            confirm = input("\n是否继续创建? (yes/no): ")
            if confirm.lower() != 'yes':
                print("操作已取消")
                return

        username = input("\n用户名: ").strip()
        if not username:
            print("❌ 用户名不能为空")
            sys.exit(1)

        if AuthService.get_user_by_username(session, username):
            print(f"❌ 用户名 '{username}' 已存在")
            sys.exit(1)

        password = getpass.getpass("密码: ")
        password_confirm = getpass.getpass("确认密码: ")
        if password != password_confirm:
            print("❌ 密码不匹配")
            sys.exit(1)
        if len(password) < 6:
            print("❌ 密码长度至少 6 位")
            sys.exit(1)

        user_in = UserCreate(username=username, password=password)
        admin_user = AuthService.create_user(session, user_in)
        admin_user.is_admin = True
        session.add(admin_user)
        session.commit()
        print(f"\n✅ 管理员创建成功! 用户名: {username}, ID: {admin_user.id}")


if __name__ == "__main__":
    create_admin()
