from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select
from app.models.user import User, UserRead
from app.core.database import get_session
from app.api.v1.endpoints.auth import get_current_admin_user

router = APIRouter()


@router.get("/users", response_model=List[UserRead])
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    is_admin: Optional[bool] = Query(None),
    is_active: Optional[bool] = Query(None),
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin_user)
):
    """获取用户列表（仅管理员）"""
    statement = select(User)
    if is_admin is not None:
        statement = statement.where(User.is_admin == is_admin)
    if is_active is not None:
        statement = statement.where(User.is_active == is_active)
    return session.exec(statement.offset(skip).limit(limit)).all()


@router.get("/users/{user_id}", response_model=UserRead)
def get_user(
    user_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin_user)
):
    """获取用户详情（仅管理员）"""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
