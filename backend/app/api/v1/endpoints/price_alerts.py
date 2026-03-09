"""到价提醒 API 端点"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.database import get_session
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.price_alert import PriceAlertCreate, PriceAlertResponse
from app.services.price_alert_service import PriceAlertService

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_current_etf_price(etf_code: str) -> float:
    """获取 ETF 当前价格（同步，供端点调用）"""
    from app.services.akshare_service import ak_service
    info = ak_service.get_etf_info(etf_code)
    if info is None or "price" not in info:
        raise HTTPException(
            status_code=400,
            detail=f"无法获取 ETF {etf_code} 的当前价格，请稍后重试",
        )
    return info["price"]


@router.get("", response_model=List[PriceAlertResponse])
async def list_price_alerts(
    active_only: bool = False,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的到价提醒列表"""
    return PriceAlertService.get_user_alerts(
        session, current_user.id, active_only=active_only
    )


@router.post("", response_model=PriceAlertResponse, status_code=status.HTTP_201_CREATED)
async def create_price_alert(
    data: PriceAlertCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """创建到价提醒"""
    # 1. 检查 Telegram 配置
    telegram_config = (current_user.settings or {}).get("telegram", {})
    if not telegram_config.get("enabled") or not telegram_config.get("verified"):
        raise HTTPException(
            status_code=400,
            detail="请先配置并验证 Telegram 通知，才能创建到价提醒",
        )

    # 2. 获取当前价格
    current_price = _get_current_etf_price(data.etf_code)

    # 3. 创建提醒
    try:
        alert = PriceAlertService.create_alert(
            session, current_user.id, data, current_price
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return alert


@router.delete("/{alert_id}")
async def delete_price_alert(
    alert_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """删除到价提醒"""
    deleted = PriceAlertService.delete_alert(session, alert_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="提醒不存在")
    return {"message": "已删除"}
