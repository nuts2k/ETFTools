from typing import List, Optional
from datetime import datetime
import asyncio
import io
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from app.models.user import User, UserRead
from app.models.system_config import SystemConfigKeys
from app.core.database import get_session
from app.api.v1.endpoints.auth import get_current_admin_user
from app.services.system_config_service import SystemConfigService
from app.services.fund_flow_collector import fund_flow_collector
from app.services.share_history_backup_service import share_history_backup_service

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


@router.post("/users/{user_id}/toggle-admin")
def toggle_admin_status(
    user_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin_user)
):
    """切换用户管理员权限"""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot modify your own admin status")
    user.is_admin = not user.is_admin
    user.updated_at = datetime.utcnow()
    session.add(user)
    session.commit()
    return {"user_id": user.id, "is_admin": user.is_admin}


@router.post("/users/{user_id}/toggle-active")
def toggle_user_active(
    user_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin_user)
):
    """启用/禁用用户账户"""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot disable your own account")
    user.is_active = not user.is_active
    user.updated_at = datetime.utcnow()
    session.add(user)
    session.commit()
    return {"user_id": user.id, "is_active": user.is_active}


@router.get("/system/config")
def get_system_config(
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin_user)
):
    """获取系统配置（仅管理员）"""
    return {
        "registration_enabled": SystemConfigService.is_registration_enabled(session),
        "max_watchlist_items": SystemConfigService.get_max_watchlist_items(session),
    }


@router.post("/system/config/registration")
def toggle_registration(
    enabled: bool,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin_user)
):
    """开启/关闭用户注册"""
    SystemConfigService.set_config(
        session, SystemConfigKeys.REGISTRATION_ENABLED, enabled, admin.id
    )
    return {"registration_enabled": enabled}


@router.post("/system/config/max-watchlist")
def set_max_watchlist(
    max_items: int = Query(..., ge=1, le=1000),
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin_user)
):
    """设置自选列表最大数量"""
    SystemConfigService.set_config(
        session, SystemConfigKeys.MAX_WATCHLIST_ITEMS, max_items, admin.id
    )
    return {"max_watchlist_items": max_items}


@router.post("/fund-flow/collect")
async def trigger_fund_flow_collection(
    admin: User = Depends(get_current_admin_user)
):
    """手动触发 ETF 份额数据采集（管理员）"""
    result = await asyncio.to_thread(fund_flow_collector.collect_daily_snapshot)
    return result


@router.post("/fund-flow/export")
async def export_share_history(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    admin: User = Depends(get_current_admin_user)
):
    """导出份额历史数据为 CSV（管理员）"""
    csv_bytes = share_history_backup_service.export_to_csv_bytes(
        start_date, end_date
    )
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={
            "Content-Disposition":
                f"attachment; filename=etf_share_history_{start_date}_{end_date}.csv"
        }
    )
