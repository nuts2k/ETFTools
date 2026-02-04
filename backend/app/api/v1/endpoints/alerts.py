"""
告警相关 API 端点
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from sqlalchemy.orm.attributes import flag_modified
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_session
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.alert_config import UserAlertPreferences
from app.services.alert_scheduler import alert_scheduler

router = APIRouter()


class AlertConfigRequest(BaseModel):
    """告警配置请求"""
    enabled: bool = True
    temperature_change: bool = True
    extreme_temperature: bool = True
    rsi_signal: bool = True
    ma_crossover: bool = True
    ma_alignment: bool = True
    weekly_signal: bool = True
    max_alerts_per_day: int = 100


class AlertConfigResponse(BaseModel):
    """告警配置响应"""
    enabled: bool
    temperature_change: bool
    extreme_temperature: bool
    rsi_signal: bool
    ma_crossover: bool
    ma_alignment: bool
    weekly_signal: bool
    max_alerts_per_day: int


@router.get("/config", response_model=AlertConfigResponse)
def get_alert_config(current_user: User = Depends(get_current_user)):
    """获取告警配置"""
    alert_settings = (current_user.settings or {}).get("alerts", {})
    prefs = UserAlertPreferences(**alert_settings)
    return AlertConfigResponse(**prefs.model_dump())


@router.put("/config")
def update_alert_config(
    config: AlertConfigRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """更新告警配置"""
    current_settings = current_user.settings or {}
    current_settings["alerts"] = config.model_dump()

    current_user.settings = current_settings
    flag_modified(current_user, "settings")
    session.add(current_user)
    session.commit()

    return {"message": "配置已保存"}


@router.post("/trigger")
async def trigger_alert_check(current_user: User = Depends(get_current_user)):
    """手动触发告警检查"""
    result = await alert_scheduler.trigger_check(current_user.id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result
