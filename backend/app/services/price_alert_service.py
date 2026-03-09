"""到价提醒业务服务"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlmodel import Session, select, col
from sqlalchemy import delete

from app.models.price_alert import PriceAlert, PriceAlertCreate, PriceAlertDirection

logger = logging.getLogger(__name__)

# 每用户最大活跃提醒数
MAX_ACTIVE_ALERTS = 20
# 浮点比较容差 (ETF 价格最多 3 位小数，第 4 位容差)
EPSILON = 0.0001


class PriceAlertService:
    """到价提醒业务逻辑"""

    @staticmethod
    def _check_price_condition(
        direction: str, target_price: float, current_price: float
    ) -> bool:
        """检查价格是否满足方向条件（触发判断 & 创建时前置校验共用）"""
        if direction == PriceAlertDirection.BELOW:
            return current_price <= target_price + EPSILON
        elif direction == PriceAlertDirection.ABOVE:
            return current_price >= target_price - EPSILON
        return False

    @staticmethod
    def _should_trigger(alert: PriceAlert, current_price: float) -> bool:
        """判断提醒是否应该触发"""
        return PriceAlertService._check_price_condition(
            alert.direction, alert.target_price, current_price
        )

    @staticmethod
    def _infer_direction(target_price: float, current_price: float) -> PriceAlertDirection:
        """根据目标价和当前价自动推断方向"""
        if target_price < current_price:
            return PriceAlertDirection.BELOW
        return PriceAlertDirection.ABOVE

    @staticmethod
    def get_active_count(session: Session, user_id: int) -> int:
        """获取用户活跃提醒数量"""
        from sqlalchemy import func
        count = session.exec(
            select(func.count()).where(
                PriceAlert.user_id == user_id,
                PriceAlert.is_triggered == False,  # noqa: E712
            )
        ).one()
        return count

    @staticmethod
    def get_user_alerts(
        session: Session, user_id: int, active_only: bool = False
    ) -> List[PriceAlert]:
        """获取用户的提醒列表"""
        query = select(PriceAlert).where(PriceAlert.user_id == user_id)
        if active_only:
            query = query.where(PriceAlert.is_triggered == False)  # noqa: E712
        query = query.order_by(
            col(PriceAlert.is_triggered).asc(),
            col(PriceAlert.created_at).desc(),
        )
        return list(session.exec(query).all())

    @staticmethod
    def create_alert(
        session: Session,
        user_id: int,
        data: PriceAlertCreate,
        current_price: float,
    ) -> PriceAlert:
        """创建到价提醒

        Raises:
            ValueError: 校验失败时抛出
        """
        # 1. 检查活跃提醒数量
        active_count = PriceAlertService.get_active_count(session, user_id)
        if active_count >= MAX_ACTIVE_ALERTS:
            raise ValueError(
                f"活跃提醒数量已达上限 ({MAX_ACTIVE_ALERTS} 个)，"
                "请删除不需要的提醒后再创建"
            )

        # 2. 确定方向
        direction = (
            data.direction.value if data.direction
            else PriceAlertService._infer_direction(data.target_price, current_price)
        )

        # 3. 检查条件是否已满足
        if PriceAlertService._check_price_condition(
            direction, data.target_price, current_price
        ):
            direction_text = "跌破" if direction == PriceAlertDirection.BELOW else "突破"
            raise ValueError(
                f"当前价格 {current_price} 已满足该提醒条件"
                f"（{direction_text} {data.target_price}），无需设置提醒"
            )

        # 4. 创建记录
        alert = PriceAlert(
            user_id=user_id,
            etf_code=data.etf_code,
            etf_name=data.etf_name,
            target_price=data.target_price,
            direction=direction,
            note=data.note,
        )
        session.add(alert)
        session.commit()
        session.refresh(alert)
        return alert

    @staticmethod
    def delete_alert(session: Session, alert_id: int, user_id: int) -> bool:
        """删除提醒（只能删自己的）

        Returns:
            True 删除成功, False 未找到
        """
        alert = session.get(PriceAlert, alert_id)
        if not alert or alert.user_id != user_id:
            return False
        session.delete(alert)
        session.commit()
        return True

    @staticmethod
    def get_all_active_alerts(session: Session) -> List[PriceAlert]:
        """获取所有用户的活跃提醒（调度器用）"""
        return list(
            session.exec(
                select(PriceAlert).where(
                    PriceAlert.is_triggered == False  # noqa: E712
                )
            ).all()
        )

    @staticmethod
    def trigger_alerts(
        session: Session,
        alerts: List[PriceAlert],
        etf_prices: Dict[str, float],
    ) -> List[PriceAlert]:
        """检查并触发到价提醒

        Returns:
            本次触发的提醒列表
        """
        triggered = []
        for alert in alerts:
            current_price = etf_prices.get(alert.etf_code)
            if current_price is None:
                continue
            if PriceAlertService._should_trigger(alert, current_price):
                alert.is_triggered = True
                alert.triggered_at = datetime.utcnow()
                alert.triggered_price = current_price
                triggered.append(alert)

        if triggered:
            session.commit()

        return triggered

    @staticmethod
    def cleanup_old_triggered(session: Session, days: int = 30) -> int:
        """清理已触发超过指定天数的记录

        Returns:
            删除的记录数
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        stmt = delete(PriceAlert).where(
            PriceAlert.is_triggered == True,  # noqa: E712
            PriceAlert.triggered_at < cutoff,
        )
        result = session.exec(stmt)
        session.commit()
        return result.rowcount
