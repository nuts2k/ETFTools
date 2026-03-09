# 到价提醒 (Price Alert) 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现到价提醒功能，让用户设置目标价格，当 ETF 价格到达目标价时通过 Telegram 发送通知。

**Architecture:** 新增 `price_alerts` SQLModel 表存储提醒数据，新增 `PriceAlertService` 处理业务逻辑，新增 3 个 REST API 端点（GET/POST/DELETE），复用现有 `AlertScheduler` 的盘中 30 分钟检查并新增 15:01 收盘补检任务。前端在 ETF 详情页添加铃铛按钮创建提醒，在 `/settings/alerts` 页添加管理列表。

**Tech Stack:** FastAPI + SQLModel + APScheduler（后端），Next.js + TypeScript + Tailwind CSS + Lucide Icons（前端），pytest（后端测试），vitest + @testing-library/react（前端测试）

**Design Doc:** `docs/design/2026-03-05-price-alert-design.md`

---

## Task 1: 数据模型 (PriceAlert Model)

**Files:**
- Create: `backend/app/models/price_alert.py`
- Test: `backend/tests/models/test_price_alert_model.py`

### Step 1: 编写模型校验测试

```python
# backend/tests/models/test_price_alert_model.py
"""到价提醒模型单元测试"""
import pytest
from pydantic import ValidationError

from app.models.price_alert import (
    PriceAlertCreate,
    PriceAlertResponse,
    PriceAlertDirection,
)


class TestPriceAlertCreate:
    """PriceAlertCreate 请求模型校验"""

    def test_valid_create(self):
        data = PriceAlertCreate(
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            note="到这个价加仓",
        )
        assert data.etf_code == "510300"
        assert data.target_price == 3.50
        assert data.direction is None  # 可选，后端自动推断

    def test_valid_with_direction(self):
        data = PriceAlertCreate(
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            direction=PriceAlertDirection.BELOW,
        )
        assert data.direction == PriceAlertDirection.BELOW

    def test_etf_code_must_be_6_digits(self):
        with pytest.raises(ValidationError, match="6 位数字"):
            PriceAlertCreate(
                etf_code="51030",  # 5 位
                etf_name="沪深300ETF",
                target_price=3.50,
            )

    def test_etf_code_rejects_non_digits(self):
        with pytest.raises(ValidationError, match="6 位数字"):
            PriceAlertCreate(
                etf_code="abcdef",
                etf_name="沪深300ETF",
                target_price=3.50,
            )

    def test_target_price_must_be_positive(self):
        with pytest.raises(ValidationError):
            PriceAlertCreate(
                etf_code="510300",
                etf_name="沪深300ETF",
                target_price=0,
            )

    def test_target_price_rejects_negative(self):
        with pytest.raises(ValidationError):
            PriceAlertCreate(
                etf_code="510300",
                etf_name="沪深300ETF",
                target_price=-1.0,
            )

    def test_note_max_200_chars(self):
        with pytest.raises(ValidationError):
            PriceAlertCreate(
                etf_code="510300",
                etf_name="沪深300ETF",
                target_price=3.50,
                note="x" * 201,
            )

    def test_note_200_chars_ok(self):
        data = PriceAlertCreate(
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            note="x" * 200,
        )
        assert len(data.note) == 200

    def test_note_optional(self):
        data = PriceAlertCreate(
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
        )
        assert data.note is None


class TestPriceAlertResponse:
    """PriceAlertResponse 模型测试"""

    def test_from_attributes(self):
        """确认 from_attributes=True 配置正确"""
        resp = PriceAlertResponse(
            id=1,
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            direction="below",
            note=None,
            is_triggered=False,
            triggered_at=None,
            triggered_price=None,
            created_at="2026-03-05T10:30:00",
        )
        assert resp.id == 1
        assert resp.direction == "below"
```

### Step 2: 运行测试，确认失败

```bash
cd backend && python -m pytest tests/models/test_price_alert_model.py -v
```

预期: FAIL — `ModuleNotFoundError: No module named 'app.models.price_alert'`

### Step 3: 实现 PriceAlert 模型

```python
# backend/app/models/price_alert.py
"""到价提醒模型"""
import re
from enum import Enum
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field as PydanticField, field_validator
from sqlmodel import SQLModel, Field, Index


class PriceAlertDirection(str, Enum):
    ABOVE = "above"
    BELOW = "below"


class PriceAlert(SQLModel, table=True):
    """到价提醒"""
    __tablename__ = "price_alerts"
    __table_args__ = (
        Index("idx_price_alerts_user_active", "user_id", "is_triggered"),
        Index("idx_price_alerts_active", "is_triggered"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    etf_code: str = Field(max_length=10, index=True)
    etf_name: str = Field(max_length=50)
    target_price: float
    direction: str = Field(max_length=10)  # "above" | "below"
    note: Optional[str] = Field(default=None, max_length=200)
    is_triggered: bool = Field(default=False)
    triggered_at: Optional[datetime] = Field(default=None)
    triggered_price: Optional[float] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# --- Pydantic 请求/响应模型 ---

class PriceAlertCreate(BaseModel):
    etf_code: str
    etf_name: str
    target_price: float = PydanticField(gt=0)
    direction: Optional[PriceAlertDirection] = None  # 可选，后端自动推断
    note: Optional[str] = PydanticField(default=None, max_length=200)

    @field_validator("etf_code")
    @classmethod
    def validate_etf_code(cls, v: str) -> str:
        if not re.match(r"^\d{6}$", v):
            raise ValueError("ETF 代码必须为 6 位数字")
        return v


class PriceAlertResponse(BaseModel):
    id: int
    etf_code: str
    etf_name: str
    target_price: float
    direction: str
    note: Optional[str]
    is_triggered: bool
    triggered_at: Optional[datetime]
    triggered_price: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True
```

### Step 4: 运行测试，确认通过

```bash
cd backend && python -m pytest tests/models/test_price_alert_model.py -v
```

预期: 全部 PASS

### Step 5: 追加数据库表测试

在 `test_price_alert_model.py` 末尾追加：

```python
class TestPriceAlertTable:
    """PriceAlert 数据库表测试"""

    def test_table_creation(self, test_engine):
        """确认 PriceAlert 表能被 create_all 创建"""
        from sqlalchemy import inspect
        inspector = inspect(test_engine)
        tables = inspector.get_table_names()
        assert "price_alerts" in tables

    def test_insert_and_query(self, test_session):
        """确认基本 CRUD 可用"""
        from app.models.price_alert import PriceAlert
        alert = PriceAlert(
            user_id=1,
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            direction="below",
        )
        test_session.add(alert)
        test_session.commit()
        test_session.refresh(alert)
        assert alert.id is not None
        assert alert.is_triggered is False
```

注意：这些测试使用 `conftest.py` 中已有的 `test_engine` 和 `test_session` fixture（基于 in-memory SQLite）。因为 `conftest.py:223` 调用 `SQLModel.metadata.create_all(engine)` 会自动创建所有已导入的 SQLModel 表，需要确保 `PriceAlert` 被导入。如果测试中已 `from app.models.price_alert import ...` 则自动注册到 metadata。

### Step 6: 运行全部模型测试

```bash
cd backend && python -m pytest tests/models/test_price_alert_model.py -v
```

预期: 全部 PASS

### Step 7: 提交

```bash
git add backend/app/models/price_alert.py backend/tests/models/test_price_alert_model.py
git commit -m "feat(price-alert): add PriceAlert model and validation tests"
```

---

## Task 2: 业务服务 (PriceAlertService)

**Files:**
- Create: `backend/app/services/price_alert_service.py`
- Test: `backend/tests/services/test_price_alert_service.py`

### Step 1: 编写核心业务逻辑测试

```python
# backend/tests/services/test_price_alert_service.py
"""到价提醒业务逻辑测试"""
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from sqlmodel import Session

from app.models.price_alert import PriceAlert, PriceAlertCreate
from app.services.price_alert_service import PriceAlertService


class TestShouldTrigger:
    """_should_trigger() 触发条件判断测试"""

    def test_below_triggers_when_price_at_target(self):
        alert = PriceAlert(
            id=1, user_id=1, etf_code="510300", etf_name="沪深300ETF",
            target_price=3.50, direction="below",
        )
        assert PriceAlertService._should_trigger(alert, 3.50) is True

    def test_below_triggers_when_price_below_target(self):
        alert = PriceAlert(
            id=1, user_id=1, etf_code="510300", etf_name="沪深300ETF",
            target_price=3.50, direction="below",
        )
        assert PriceAlertService._should_trigger(alert, 3.48) is True

    def test_below_not_triggers_when_price_above_target(self):
        alert = PriceAlert(
            id=1, user_id=1, etf_code="510300", etf_name="沪深300ETF",
            target_price=3.50, direction="below",
        )
        assert PriceAlertService._should_trigger(alert, 3.52) is False

    def test_above_triggers_when_price_at_target(self):
        alert = PriceAlert(
            id=1, user_id=1, etf_code="510300", etf_name="沪深300ETF",
            target_price=6.10, direction="above",
        )
        assert PriceAlertService._should_trigger(alert, 6.10) is True

    def test_above_triggers_when_price_above_target(self):
        alert = PriceAlert(
            id=1, user_id=1, etf_code="510300", etf_name="沪深300ETF",
            target_price=6.10, direction="above",
        )
        assert PriceAlertService._should_trigger(alert, 6.12) is True

    def test_above_not_triggers_when_price_below_target(self):
        alert = PriceAlert(
            id=1, user_id=1, etf_code="510300", etf_name="沪深300ETF",
            target_price=6.10, direction="above",
        )
        assert PriceAlertService._should_trigger(alert, 6.08) is False

    def test_float_epsilon_below(self):
        """浮点容差: 3.5000001 应该触发 below 3.50"""
        alert = PriceAlert(
            id=1, user_id=1, etf_code="510300", etf_name="沪深300ETF",
            target_price=3.50, direction="below",
        )
        # 3.50 + EPSILON(0.0001) = 3.5001，价格 3.5000001 <= 3.5001
        assert PriceAlertService._should_trigger(alert, 3.5000001) is True

    def test_float_epsilon_above(self):
        """浮点容差: 6.0999999 应该触发 above 6.10"""
        alert = PriceAlert(
            id=1, user_id=1, etf_code="510300", etf_name="沪深300ETF",
            target_price=6.10, direction="above",
        )
        # 6.10 - EPSILON(0.0001) = 6.0999，价格 6.0999999 >= 6.0999
        assert PriceAlertService._should_trigger(alert, 6.0999999) is True


class TestInferDirection:
    """方向自动推断测试"""

    def test_target_below_current_infers_below(self):
        assert PriceAlertService._infer_direction(3.40, 3.52) == "below"

    def test_target_above_current_infers_above(self):
        assert PriceAlertService._infer_direction(6.20, 6.10) == "above"

    def test_target_equals_current_infers_below(self):
        """目标价=当前价时推断为 below（实际上创建时会被拒绝）"""
        # 只要有一个确定的返回值就行
        result = PriceAlertService._infer_direction(3.50, 3.50)
        assert result in ("above", "below")


class TestIsConditionAlreadyMet:
    """创建时条件已满足检查"""

    def test_below_already_met(self):
        """当前价 3.48 已经 <= 目标价 3.50，条件已满足"""
        assert PriceAlertService._is_condition_already_met("below", 3.50, 3.48) is True

    def test_below_not_met(self):
        """当前价 3.52 > 目标价 3.50，条件未满足"""
        assert PriceAlertService._is_condition_already_met("below", 3.50, 3.52) is False

    def test_above_already_met(self):
        """当前价 6.12 已经 >= 目标价 6.10，条件已满足"""
        assert PriceAlertService._is_condition_already_met("above", 6.10, 6.12) is True

    def test_above_not_met(self):
        """当前价 6.08 < 目标价 6.10，条件未满足"""
        assert PriceAlertService._is_condition_already_met("above", 6.10, 6.08) is False

    def test_equal_price_is_met(self):
        """当前价=目标价，条件已满足"""
        assert PriceAlertService._is_condition_already_met("below", 3.50, 3.50) is True
        assert PriceAlertService._is_condition_already_met("above", 3.50, 3.50) is True
```

### Step 2: 运行测试，确认失败

```bash
cd backend && python -m pytest tests/services/test_price_alert_service.py -v
```

预期: FAIL — `ModuleNotFoundError: No module named 'app.services.price_alert_service'`

### Step 3: 实现 PriceAlertService

```python
# backend/app/services/price_alert_service.py
"""到价提醒业务服务"""
import logging
from datetime import datetime
from typing import Dict, List, Optional

from sqlmodel import Session, select, col

from app.models.price_alert import PriceAlert, PriceAlertCreate

logger = logging.getLogger(__name__)

# 每用户最大活跃提醒数
MAX_ACTIVE_ALERTS = 20
# 浮点比较容差 (ETF 价格最多 3 位小数，第 4 位容差)
EPSILON = 0.0001


class PriceAlertService:
    """到价提醒业务逻辑"""

    @staticmethod
    def _should_trigger(alert: PriceAlert, current_price: float) -> bool:
        """判断提醒是否应该触发"""
        if alert.direction == "below":
            return current_price <= alert.target_price + EPSILON
        elif alert.direction == "above":
            return current_price >= alert.target_price - EPSILON
        return False

    @staticmethod
    def _infer_direction(target_price: float, current_price: float) -> str:
        """根据目标价和当前价自动推断方向"""
        if target_price < current_price:
            return "below"
        return "above"

    @staticmethod
    def _is_condition_already_met(
        direction: str, target_price: float, current_price: float
    ) -> bool:
        """检查创建时条件是否已满足"""
        if direction == "below":
            return current_price <= target_price + EPSILON
        elif direction == "above":
            return current_price >= target_price - EPSILON
        return False

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
        if PriceAlertService._is_condition_already_met(
            direction, data.target_price, current_price
        ):
            direction_text = "跌破" if direction == "below" else "突破"
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
        from sqlalchemy import text
        result = session.exec(
            text(
                "DELETE FROM price_alerts "
                "WHERE is_triggered = 1 "
                "AND triggered_at < datetime('now', :offset)"
            ),
            params={"offset": f"-{days} days"},
        )
        session.commit()
        return result.rowcount
```

### Step 4: 运行测试，确认通过

```bash
cd backend && python -m pytest tests/services/test_price_alert_service.py -v
```

预期: 全部 PASS

### Step 5: 追加数据库操作测试

在 `test_price_alert_service.py` 追加数据库操作测试（使用 conftest 中的 `test_session` fixture）：

```python
# 追加到 test_price_alert_service.py

class TestCreateAlert:
    """创建提醒的数据库测试"""

    def test_create_success(self, test_session, regular_user):
        data = PriceAlertCreate(
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.40,
        )
        alert = PriceAlertService.create_alert(
            test_session, regular_user.id, data, current_price=3.52
        )
        assert alert.id is not None
        assert alert.direction == "below"  # 3.40 < 3.52 -> below
        assert alert.is_triggered is False

    def test_create_with_explicit_direction(self, test_session, regular_user):
        from app.models.price_alert import PriceAlertDirection
        data = PriceAlertCreate(
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.40,
            direction=PriceAlertDirection.ABOVE,
        )
        # 虽然 target < current，但用户显式指定了 above
        # 这里 3.52 >= 3.40 - EPSILON 为 True，所以条件已满足
        # 应该被拒绝
        with pytest.raises(ValueError, match="已满足"):
            PriceAlertService.create_alert(
                test_session, regular_user.id, data, current_price=3.52
            )

    def test_create_rejects_already_met_below(self, test_session, regular_user):
        data = PriceAlertCreate(
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
        )
        with pytest.raises(ValueError, match="已满足"):
            PriceAlertService.create_alert(
                test_session, regular_user.id, data, current_price=3.48
            )

    def test_create_rejects_already_met_above(self, test_session, regular_user):
        data = PriceAlertCreate(
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=6.10,
        )
        with pytest.raises(ValueError, match="已满足"):
            PriceAlertService.create_alert(
                test_session, regular_user.id, data, current_price=6.12
            )

    def test_create_rejects_at_limit(self, test_session, regular_user):
        """创建第 21 个提醒应被拒绝"""
        for i in range(20):
            alert = PriceAlert(
                user_id=regular_user.id,
                etf_code=f"{510300 + i:06d}",
                etf_name=f"ETF-{i}",
                target_price=float(i + 1),
                direction="below",
            )
            test_session.add(alert)
        test_session.commit()

        data = PriceAlertCreate(
            etf_code="510399",
            etf_name="ETF-extra",
            target_price=1.0,
        )
        with pytest.raises(ValueError, match="上限"):
            PriceAlertService.create_alert(
                test_session, regular_user.id, data, current_price=2.0
            )


class TestDeleteAlert:
    """删除提醒测试"""

    def test_delete_own_alert(self, test_session, regular_user):
        alert = PriceAlert(
            user_id=regular_user.id,
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            direction="below",
        )
        test_session.add(alert)
        test_session.commit()
        test_session.refresh(alert)

        result = PriceAlertService.delete_alert(
            test_session, alert.id, regular_user.id
        )
        assert result is True

    def test_cannot_delete_others_alert(self, test_session, regular_user, admin_user):
        alert = PriceAlert(
            user_id=admin_user.id,  # 管理员创建的
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            direction="below",
        )
        test_session.add(alert)
        test_session.commit()
        test_session.refresh(alert)

        result = PriceAlertService.delete_alert(
            test_session, alert.id, regular_user.id  # 普通用户尝试删除
        )
        assert result is False

    def test_delete_nonexistent(self, test_session, regular_user):
        result = PriceAlertService.delete_alert(
            test_session, 99999, regular_user.id
        )
        assert result is False


class TestTriggerAlerts:
    """trigger_alerts() 批量触发测试"""

    def test_trigger_matching_alerts(self, test_session, regular_user):
        a1 = PriceAlert(
            user_id=regular_user.id,
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            direction="below",
        )
        a2 = PriceAlert(
            user_id=regular_user.id,
            etf_code="510500",
            etf_name="中证500ETF",
            target_price=6.10,
            direction="above",
        )
        test_session.add_all([a1, a2])
        test_session.commit()

        # 510300 当前 3.48 <= 3.50 (below 触发)
        # 510500 当前 6.08 < 6.10 (above 不触发)
        triggered = PriceAlertService.trigger_alerts(
            test_session,
            [a1, a2],
            {"510300": 3.48, "510500": 6.08},
        )
        assert len(triggered) == 1
        assert triggered[0].etf_code == "510300"
        assert triggered[0].is_triggered is True
        assert triggered[0].triggered_price == 3.48

    def test_skip_missing_price(self, test_session, regular_user):
        a = PriceAlert(
            user_id=regular_user.id,
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            direction="below",
        )
        test_session.add(a)
        test_session.commit()

        triggered = PriceAlertService.trigger_alerts(
            test_session, [a], {}  # 无价格数据
        )
        assert len(triggered) == 0
        assert a.is_triggered is False
```

### Step 6: 运行全部测试

```bash
cd backend && python -m pytest tests/services/test_price_alert_service.py -v
```

预期: 全部 PASS

### Step 7: 提交

```bash
git add backend/app/services/price_alert_service.py backend/tests/services/test_price_alert_service.py
git commit -m "feat(price-alert): add PriceAlertService with business logic and tests"
```

---

## Task 3: API 端点 (Price Alert Endpoints)

**Files:**
- Create: `backend/app/api/v1/endpoints/price_alerts.py`
- Modify: `backend/app/api/v1/api.py:2,12` — 新增 import 和路由注册
- Test: `backend/tests/api/test_price_alerts.py`

### Step 1: 编写 API 测试

```python
# backend/tests/api/test_price_alerts.py
"""到价提醒 API 端点测试"""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.models.price_alert import PriceAlert


class TestGetPriceAlerts:
    """GET /api/v1/price-alerts"""

    def test_empty_list(self, user_client: TestClient):
        resp = user_client.get("/api/v1/price-alerts")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_user_alerts(self, user_client, test_session, regular_user):
        alert = PriceAlert(
            user_id=regular_user.id,
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            direction="below",
        )
        test_session.add(alert)
        test_session.commit()

        resp = user_client.get("/api/v1/price-alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["etf_code"] == "510300"

    def test_active_only_filter(self, user_client, test_session, regular_user):
        active = PriceAlert(
            user_id=regular_user.id,
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            direction="below",
        )
        triggered = PriceAlert(
            user_id=regular_user.id,
            etf_code="510500",
            etf_name="中证500ETF",
            target_price=6.10,
            direction="above",
            is_triggered=True,
        )
        test_session.add_all([active, triggered])
        test_session.commit()

        resp = user_client.get("/api/v1/price-alerts?active_only=true")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["etf_code"] == "510300"

    def test_unauthenticated(self, client):
        resp = client.get("/api/v1/price-alerts")
        assert resp.status_code == 401


class TestCreatePriceAlert:
    """POST /api/v1/price-alerts"""

    @patch("app.api.v1.endpoints.price_alerts._get_current_etf_price")
    def test_create_success(self, mock_price, user_client, test_session, regular_user):
        mock_price.return_value = 3.52

        # 给用户配置 Telegram
        regular_user.settings = {
            "telegram": {"enabled": True, "verified": True, "botToken": "enc", "chatId": "123"}
        }
        test_session.commit()

        resp = user_client.post("/api/v1/price-alerts", json={
            "etf_code": "510300",
            "etf_name": "沪深300ETF",
            "target_price": 3.40,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["direction"] == "below"
        assert data["is_triggered"] is False

    @patch("app.api.v1.endpoints.price_alerts._get_current_etf_price")
    def test_create_rejects_already_met(self, mock_price, user_client, test_session, regular_user):
        mock_price.return_value = 3.48

        regular_user.settings = {
            "telegram": {"enabled": True, "verified": True, "botToken": "enc", "chatId": "123"}
        }
        test_session.commit()

        resp = user_client.post("/api/v1/price-alerts", json={
            "etf_code": "510300",
            "etf_name": "沪深300ETF",
            "target_price": 3.50,
        })
        assert resp.status_code == 400
        assert "已满足" in resp.json()["detail"]

    def test_create_rejects_without_telegram(self, user_client, test_session, regular_user):
        # 不配置 Telegram
        regular_user.settings = {}
        test_session.commit()

        resp = user_client.post("/api/v1/price-alerts", json={
            "etf_code": "510300",
            "etf_name": "沪深300ETF",
            "target_price": 3.40,
        })
        assert resp.status_code == 400
        assert "Telegram" in resp.json()["detail"]

    def test_create_validates_etf_code(self, user_client, test_session, regular_user):
        regular_user.settings = {
            "telegram": {"enabled": True, "verified": True, "botToken": "enc", "chatId": "123"}
        }
        test_session.commit()

        resp = user_client.post("/api/v1/price-alerts", json={
            "etf_code": "abc",
            "etf_name": "Bad",
            "target_price": 3.40,
        })
        assert resp.status_code == 422  # Pydantic validation


class TestDeletePriceAlert:
    """DELETE /api/v1/price-alerts/{id}"""

    def test_delete_own_alert(self, user_client, test_session, regular_user):
        alert = PriceAlert(
            user_id=regular_user.id,
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            direction="below",
        )
        test_session.add(alert)
        test_session.commit()
        test_session.refresh(alert)

        resp = user_client.delete(f"/api/v1/price-alerts/{alert.id}")
        assert resp.status_code == 200

    def test_delete_nonexistent(self, user_client):
        resp = user_client.delete("/api/v1/price-alerts/99999")
        assert resp.status_code == 404

    def test_delete_others_alert(self, user_client, test_session, admin_user):
        alert = PriceAlert(
            user_id=admin_user.id,
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            direction="below",
        )
        test_session.add(alert)
        test_session.commit()
        test_session.refresh(alert)

        resp = user_client.delete(f"/api/v1/price-alerts/{alert.id}")
        assert resp.status_code == 404
```

### Step 2: 运行测试，确认失败

```bash
cd backend && python -m pytest tests/api/test_price_alerts.py -v
```

预期: FAIL — `ModuleNotFoundError` 或 404

### Step 3: 实现 API 端点

```python
# backend/app/api/v1/endpoints/price_alerts.py
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
def list_price_alerts(
    active_only: bool = False,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的到价提醒列表"""
    return PriceAlertService.get_user_alerts(
        session, current_user.id, active_only=active_only
    )


@router.post("", response_model=PriceAlertResponse, status_code=status.HTTP_201_CREATED)
def create_price_alert(
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
def delete_price_alert(
    alert_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """删除到价提醒"""
    deleted = PriceAlertService.delete_alert(session, alert_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="提醒不存在")
    return {"message": "已删除"}
```

### Step 4: 注册路由

修改 `backend/app/api/v1/api.py`（第 2 行 import 和末尾追加一行）:

```python
# 第 2 行修改为:
from app.api.v1.endpoints import etf, auth, users, watchlist, notifications, alerts, admin, compare, price_alerts

# 末尾追加:
api_router.include_router(price_alerts.router, prefix="/price-alerts", tags=["price-alerts"])
```

### Step 5: 运行 API 测试

```bash
cd backend && python -m pytest tests/api/test_price_alerts.py -v
```

预期: 全部 PASS

### Step 6: 运行全部后端测试确保无回归

```bash
cd backend && python -m pytest -v
```

预期: 全部 PASS

### Step 7: 提交

```bash
git add backend/app/api/v1/endpoints/price_alerts.py backend/app/api/v1/api.py backend/tests/api/test_price_alerts.py
git commit -m "feat(price-alert): add GET/POST/DELETE API endpoints with tests"
```

---

## Task 4: 通知消息格式 (Telegram Message Formatting)

**Files:**
- Modify: `backend/app/services/notification_service.py:167` — 末尾追加方法
- Test: `backend/tests/services/test_price_alert_notification.py`

### Step 1: 编写消息格式化测试

```python
# backend/tests/services/test_price_alert_notification.py
"""到价提醒通知消息格式化测试"""
import pytest
from datetime import datetime

from app.models.price_alert import PriceAlert
from app.services.notification_service import TelegramNotificationService


class TestFormatPriceAlertMessage:
    """format_price_alert_message() 测试"""

    def _make_alert(self, **kwargs):
        defaults = dict(
            id=1, user_id=1, etf_code="510300", etf_name="沪深300ETF",
            target_price=3.50, direction="below", note=None,
            is_triggered=True, triggered_price=3.48,
            triggered_at=datetime(2026, 3, 5, 6, 30),  # UTC
        )
        defaults.update(kwargs)
        return PriceAlert(**defaults)

    def test_single_below_no_note(self):
        alert = self._make_alert()
        msg = TelegramNotificationService.format_price_alert_message(
            [alert], datetime(2026, 3, 5, 14, 30)
        )
        assert "到价提醒" in msg
        assert "沪深300ETF" in msg
        assert "510300" in msg
        assert "<b>3.48</b>" in msg
        assert "跌破" in msg
        assert "3.5" in msg
        assert "📝" not in msg  # 无备注，不显示

    def test_single_above_with_note(self):
        alert = self._make_alert(
            direction="above", target_price=6.10, triggered_price=6.12,
            note="到这个价加仓 2000 元",
        )
        msg = TelegramNotificationService.format_price_alert_message(
            [alert], datetime(2026, 3, 5, 14, 30)
        )
        assert "突破" in msg
        assert "6.1" in msg
        assert "📝" in msg
        assert "到这个价加仓 2000 元" in msg

    def test_multiple_alerts(self):
        a1 = self._make_alert()
        a2 = self._make_alert(
            id=2, etf_code="510500", etf_name="中证500ETF",
            target_price=6.10, direction="above", triggered_price=6.12,
        )
        msg = TelegramNotificationService.format_price_alert_message(
            [a1, a2], datetime(2026, 3, 5, 14, 30)
        )
        assert "2 个触发" in msg
        assert "沪深300ETF" in msg
        assert "中证500ETF" in msg

    def test_html_escape_etf_name(self):
        alert = self._make_alert(etf_name="Test<script>ETF")
        msg = TelegramNotificationService.format_price_alert_message(
            [alert], datetime(2026, 3, 5, 14, 30)
        )
        assert "<script>" not in msg
        assert "&lt;script&gt;" in msg

    def test_html_escape_note(self):
        alert = self._make_alert(note='<b>恶意</b> & "注入"')
        msg = TelegramNotificationService.format_price_alert_message(
            [alert], datetime(2026, 3, 5, 14, 30)
        )
        assert "<b>恶意</b>" not in msg  # 用户 note 中的 <b> 被转义
        assert "&lt;b&gt;" in msg
```

### Step 2: 运行测试，确认失败

```bash
cd backend && python -m pytest tests/services/test_price_alert_notification.py -v
```

预期: FAIL — `AttributeError: type object 'TelegramNotificationService' has no attribute 'format_price_alert_message'`

### Step 3: 实现消息格式化方法

在 `backend/app/services/notification_service.py` 文件末尾的 `TelegramNotificationService` 类中追加新方法：

```python
    @staticmethod
    def format_price_alert_message(
        alerts: list, check_time: "datetime"
    ) -> str:
        """格式化到价提醒消息（HTML 格式）

        Args:
            alerts: 已触发的 PriceAlert 列表
            check_time: 检查时间（datetime 对象，将格式化为北京时间）
        """
        from html import escape as html_escape
        from zoneinfo import ZoneInfo

        # 转换为北京时间
        if check_time.tzinfo is None:
            time_str = check_time.strftime("%Y-%m-%d %H:%M")
        else:
            bj_time = check_time.astimezone(ZoneInfo("Asia/Shanghai"))
            time_str = bj_time.strftime("%Y-%m-%d %H:%M")

        if len(alerts) == 1:
            a = alerts[0]
            direction_emoji = "⬇️" if a.direction == "below" else "⬆️"
            direction_text = "跌破" if a.direction == "below" else "突破"
            name = html_escape(a.etf_name)
            msg = "🔔 到价提醒\n\n"
            msg += f"{name} ({a.etf_code})\n"
            msg += f"当前价格: <b>{a.triggered_price}</b> {direction_emoji} {direction_text} {a.target_price}\n"
            if a.note:
                msg += f"\n📝 {html_escape(a.note)}\n"
            msg += f"\n⏰ {time_str}"
            return msg
        else:
            msg = f"🔔 到价提醒 ({len(alerts)} 个触发)\n"
            for a in alerts:
                direction_emoji = "⬇️" if a.direction == "below" else "⬆️"
                direction_text = "跌破" if a.direction == "below" else "突破"
                name = html_escape(a.etf_name)
                msg += f"\n📌 {name} ({a.etf_code})\n"
                msg += f"   当前: <b>{a.triggered_price}</b> {direction_emoji} {direction_text} {a.target_price}\n"
                if a.note:
                    msg += f"   📝 {html_escape(a.note)}\n"
            msg += f"\n⏰ {time_str}"
            return msg
```

注意：需要在文件顶部添加 `from datetime import datetime` import（如果尚未导入）。

### Step 4: 运行测试

```bash
cd backend && python -m pytest tests/services/test_price_alert_notification.py -v
```

预期: 全部 PASS

### Step 5: 提交

```bash
git add backend/app/services/notification_service.py backend/tests/services/test_price_alert_notification.py
git commit -m "feat(price-alert): add Telegram notification message formatting"
```

---

## Task 5: 调度器集成 (Scheduler Integration)

**Files:**
- Modify: `backend/app/services/alert_scheduler.py` — 多处修改
- Test: `backend/tests/services/test_price_alert_scheduler.py`

### Step 1: 编写调度器集成测试

```python
# backend/tests/services/test_price_alert_scheduler.py
"""到价提醒调度器集成测试"""
import pytest
from datetime import datetime, timedelta
from sqlmodel import Session

from app.models.price_alert import PriceAlert
from app.services.price_alert_service import PriceAlertService


class TestPriceAlertSchedulerIntegration:
    """测试到价提醒在调度器中的检查和触发"""

    def test_trigger_alerts_updates_db(self, test_session, regular_user):
        """验证 trigger_alerts 正确更新数据库"""
        alert = PriceAlert(
            user_id=regular_user.id,
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            direction="below",
        )
        test_session.add(alert)
        test_session.commit()

        triggered = PriceAlertService.trigger_alerts(
            test_session,
            [alert],
            {"510300": 3.48},
        )
        assert len(triggered) == 1
        assert triggered[0].is_triggered is True
        assert triggered[0].triggered_price == 3.48
        assert triggered[0].triggered_at is not None

        # 再次查询确认已持久化
        refreshed = test_session.get(PriceAlert, alert.id)
        assert refreshed.is_triggered is True

    def test_triggered_alert_not_in_active_list(self, test_session, regular_user):
        """已触发的提醒不再出现在活跃列表中"""
        alert = PriceAlert(
            user_id=regular_user.id,
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            direction="below",
            is_triggered=True,
        )
        test_session.add(alert)
        test_session.commit()

        active = PriceAlertService.get_all_active_alerts(test_session)
        assert len(active) == 0

    def test_cleanup_old_triggered(self, test_session, regular_user):
        """30 天自动清理已触发的记录"""
        old = PriceAlert(
            user_id=regular_user.id,
            etf_code="510300",
            etf_name="沪深300ETF",
            target_price=3.50,
            direction="below",
            is_triggered=True,
            triggered_at=datetime.utcnow() - timedelta(days=31),
            triggered_price=3.48,
        )
        recent = PriceAlert(
            user_id=regular_user.id,
            etf_code="510500",
            etf_name="中证500ETF",
            target_price=6.10,
            direction="above",
            is_triggered=True,
            triggered_at=datetime.utcnow() - timedelta(days=5),
            triggered_price=6.12,
        )
        test_session.add_all([old, recent])
        test_session.commit()

        deleted_count = PriceAlertService.cleanup_old_triggered(test_session)
        assert deleted_count == 1

        # 近期记录应保留
        remaining = test_session.get(PriceAlert, recent.id)
        assert remaining is not None
```

### Step 2: 运行测试

```bash
cd backend && python -m pytest tests/services/test_price_alert_scheduler.py -v
```

预期: PASS（这些测试使用已实现的 PriceAlertService 方法）

### Step 3: 修改 alert_scheduler.py — 新增 15:01 收盘补检任务

在 `start()` 方法中（`alert_scheduler.py:90` 之前，即 `self._scheduler.start()` 之前），新增收盘价格提醒补检任务：

```python
        # 15:01 收盘价格提醒补检（到价提醒专用）
        self._scheduler.add_job(
            self._run_closing_price_check,
            CronTrigger(
                hour=15, minute=1,
                day_of_week="mon-fri",
                timezone=ZoneInfo("Asia/Shanghai")
            ),
            id="closing_price_check",
            replace_existing=True,
            max_instances=1,
        )
        logger.info("Closing price check scheduled: 15:01 Beijing Time")
```

### Step 4: 修改 _run_daily_check() — 在盘中检查末尾集成到价提醒

在 `_run_daily_check()` 方法的步骤 3（发送消息循环）之后追加到价提醒检查：

```python
            # 步骤 4: 检查到价提醒
            await self._check_price_alerts()
```

### Step 5: 在 _run_daily_check() 末尾添加清理逻辑

在 `_run_daily_check()` 的最后追加清理已触发超过 30 天的记录：

```python
            # 步骤 5: 清理过期的已触发到价提醒（30 天）
            try:
                from app.services.price_alert_service import PriceAlertService
                with Session(engine) as cleanup_session:
                    deleted = PriceAlertService.cleanup_old_triggered(cleanup_session)
                    if deleted > 0:
                        logger.info(f"Cleaned up {deleted} old triggered price alerts")
            except Exception as e:
                logger.error(f"Failed to cleanup old price alerts: {e}")
```

### Step 6: 新增 _check_price_alerts()、_send_price_alert_notification()、_run_closing_price_check()

在 AlertScheduler 类中新增三个方法：

```python
    async def _check_price_alerts(self) -> None:
        """检查所有活跃的到价提醒并触发通知"""
        from app.services.price_alert_service import PriceAlertService

        with Session(engine) as session:
            active_alerts = PriceAlertService.get_all_active_alerts(session)
            if not active_alerts:
                return

            # 获取涉及的 ETF 代码
            etf_codes = set(a.etf_code for a in active_alerts)
            logger.info(f"Checking {len(active_alerts)} active price alerts for {len(etf_codes)} ETFs")

            # 获取实时价格
            etf_prices: Dict[str, float] = {}
            for code in etf_codes:
                try:
                    info = await asyncio.to_thread(ak_service.get_etf_info, code)
                    if info and "price" in info:
                        etf_prices[code] = info["price"]
                except Exception as e:
                    logger.error(f"Failed to get price for {code}: {e}")

            if not etf_prices:
                logger.warning("No prices fetched for price alert check")
                return

            # 触发匹配的提醒
            triggered = PriceAlertService.trigger_alerts(
                session, active_alerts, etf_prices
            )

            if not triggered:
                return

            logger.info(f"Triggered {len(triggered)} price alerts")

            # 按用户分组发送通知
            user_alerts: Dict[int, list] = {}
            for alert in triggered:
                user_alerts.setdefault(alert.user_id, []).append(alert)

            for user_id, alerts in user_alerts.items():
                await self._send_price_alert_notification(session, user_id, alerts)

    async def _send_price_alert_notification(
        self, session: Session, user_id: int, alerts: list
    ) -> None:
        """发送到价提醒的 Telegram 通知"""
        user = session.get(User, user_id)
        if not user:
            return

        telegram_config = (user.settings or {}).get("telegram", {})
        if not telegram_config.get("enabled") or not telegram_config.get("verified"):
            logger.warning(f"User {user_id}: Telegram not configured, skipping price alert notification")
            return

        bot_token = decrypt_token(telegram_config["botToken"], settings.SECRET_KEY)
        chat_id = telegram_config["chatId"]

        check_time = datetime.now(ZoneInfo("Asia/Shanghai"))
        message = TelegramNotificationService.format_price_alert_message(alerts, check_time)

        try:
            await TelegramNotificationService.send_message(bot_token, chat_id, message)
            logger.info(f"Sent price alert notification to user {user_id} ({len(alerts)} alerts)")
        except Exception as e:
            logger.error(f"Failed to send price alert to user {user_id}: {e}")

    async def _run_closing_price_check(self) -> None:
        """15:01 收盘补检 - 仅检查到价提醒"""
        logger.info("Running closing price check for price alerts...")
        await self._check_price_alerts()
```

### Step 7: 运行全部后端测试

```bash
cd backend && python -m pytest -v
```

预期: 全部 PASS

### Step 8: 提交

```bash
git add backend/app/services/alert_scheduler.py backend/tests/services/test_price_alert_scheduler.py
git commit -m "feat(price-alert): integrate scheduler with intraday check and 15:01 closing check"
```

---

## Task 6: 前端 API 层 (Frontend API Functions)

**Files:**
- Modify: `frontend/lib/api.ts` — 末尾追加类型和函数

### Step 1: 在 api.ts 末尾追加到价提醒相关代码

在 `frontend/lib/api.ts` 文件末尾追加：

```typescript
// --- 到价提醒 ---

export interface PriceAlertItem {
  id: number
  etf_code: string
  etf_name: string
  target_price: number
  direction: "above" | "below"
  note: string | null
  is_triggered: boolean
  triggered_at: string | null
  triggered_price: number | null
  created_at: string
}

export async function getPriceAlerts(
  token: string,
  activeOnly?: boolean,
): Promise<PriceAlertItem[]> {
  const params = activeOnly ? "?active_only=true" : ""
  const response = await fetch(`${API_BASE_URL}/price-alerts${params}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "获取提醒列表失败" }))
    throw new Error(error.detail || "获取提醒列表失败")
  }
  return response.json()
}

export async function createPriceAlert(
  token: string,
  data: {
    etf_code: string
    etf_name: string
    target_price: number
    direction?: "above" | "below"
    note?: string
  },
): Promise<PriceAlertItem> {
  const response = await fetch(`${API_BASE_URL}/price-alerts`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "创建提醒失败" }))
    throw new Error(error.detail || "创建提醒失败")
  }
  return response.json()
}

export async function deletePriceAlert(
  token: string,
  id: number,
): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE_URL}/price-alerts/${id}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "删除提醒失败" }))
    throw new Error(error.detail || "删除提醒失败")
  }
  return response.json()
}
```

### Step 2: 验证 TypeScript 编译

```bash
cd frontend && npx tsc --noEmit
```

预期: 无错误

### Step 3: 提交

```bash
git add frontend/lib/api.ts
git commit -m "feat(price-alert): add frontend API functions for price alerts"
```

---

## Task 7: 前端创建入口 (PriceAlertButton Component)

**Files:**
- Create: `frontend/components/PriceAlertButton.tsx`
- Modify: `frontend/app/etf/[code]/page.tsx:197-207` — 在 header 中添加铃铛按钮

### Step 1: 实现 PriceAlertButton 组件

```tsx
// frontend/components/PriceAlertButton.tsx
"use client"

import { useState, useEffect } from "react"
import { Bell, X, Loader2 } from "lucide-react"
import { useAuth } from "@/hooks/use-auth"
import { getTelegramConfig, createPriceAlert, getPriceAlerts } from "@/lib/api"
import { cn } from "@/lib/utils"
import { useRouter } from "next/navigation"

interface PriceAlertButtonProps {
  etfCode: string
  etfName: string
  currentPrice: number
}

export default function PriceAlertButton({
  etfCode,
  etfName,
  currentPrice,
}: PriceAlertButtonProps) {
  const { token } = useAuth()
  const router = useRouter()
  const [showDialog, setShowDialog] = useState(false)
  const [hasActiveAlert, setHasActiveAlert] = useState(false)
  const [targetPrice, setTargetPrice] = useState("")
  const [direction, setDirection] = useState<"above" | "below">("below")
  const [note, setNote] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState("")
  const [successMsg, setSuccessMsg] = useState("")

  // 检查该 ETF 是否有活跃提醒
  useEffect(() => {
    if (!token) return
    getPriceAlerts(token, true)
      .then((alerts) => {
        const has = alerts.some((a) => a.etf_code === etfCode)
        setHasActiveAlert(has)
      })
      .catch(() => {})
  }, [token, etfCode])

  const handleBellClick = async () => {
    if (!token) {
      router.push("/login")
      return
    }

    // 检查 Telegram 配置
    try {
      const config = await getTelegramConfig(token)
      if (!config?.enabled || !config?.verified) {
        setError("请先配置并验证 Telegram 通知")
        setShowDialog(true)
        return
      }
    } catch {
      setError("请先配置并验证 Telegram 通知")
      setShowDialog(true)
      return
    }

    setError("")
    setSuccessMsg("")
    setTargetPrice("")
    setNote("")
    setShowDialog(true)
  }

  // 目标价变化时自动推断方向
  useEffect(() => {
    const price = parseFloat(targetPrice)
    if (!isNaN(price) && price > 0 && currentPrice > 0) {
      setDirection(price < currentPrice ? "below" : "above")
    }
  }, [targetPrice, currentPrice])

  const handleSubmit = async () => {
    const price = parseFloat(targetPrice)
    if (isNaN(price) || price <= 0) {
      setError("请输入有效的目标价格")
      return
    }

    setIsSubmitting(true)
    setError("")
    try {
      await createPriceAlert(token!, {
        etf_code: etfCode,
        etf_name: etfName,
        target_price: price,
        direction,
        note: note.trim() || undefined,
      })
      setSuccessMsg("提醒设置成功")
      setHasActiveAlert(true)
      setTimeout(() => setShowDialog(false), 1200)
    } catch (err: any) {
      setError(err.message || "创建失败")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <>
      <button
        onClick={handleBellClick}
        className="flex w-10 h-10 items-center justify-center rounded-full text-foreground hover:bg-secondary transition-colors active:scale-90"
      >
        <Bell
          className={cn(
            "h-5 w-5 transition-all",
            hasActiveAlert
              ? "fill-primary text-primary"
              : "text-muted-foreground"
          )}
        />
      </button>

      {/* 创建弹窗 */}
      {showDialog && (
        <div className="fixed inset-0 z-[100] flex items-end sm:items-center justify-center">
          {/* 遮罩 */}
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => !isSubmitting && setShowDialog(false)}
          />

          {/* 弹窗内容 */}
          <div className="relative w-full max-w-md bg-background rounded-t-2xl sm:rounded-2xl p-6 pb-safe animate-in slide-in-from-bottom duration-200">
            {/* 标题栏 */}
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold">设置到价提醒</h3>
              <button
                onClick={() => !isSubmitting && setShowDialog(false)}
                className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-secondary"
              >
                <X className="h-5 w-5 text-muted-foreground" />
              </button>
            </div>

            {/* ETF 信息 */}
            <div className="mb-4 text-sm text-muted-foreground">
              <span className="font-medium text-foreground">{etfName}</span>
              <span className="ml-2">({etfCode})</span>
              <span className="ml-2">当前价格: {currentPrice.toFixed(3)}</span>
            </div>

            {/* Telegram 未配置时的提示 */}
            {error && error.includes("Telegram") ? (
              <div className="mb-4 p-3 bg-amber-500/10 text-amber-600 dark:text-amber-400 rounded-lg text-sm">
                <p>{error}</p>
                <button
                  onClick={() => router.push("/settings/notifications")}
                  className="mt-2 text-primary font-medium underline"
                >
                  去配置
                </button>
              </div>
            ) : (
              <>
                {/* 目标价格 */}
                <div className="mb-4">
                  <label className="block text-sm font-medium mb-1.5">
                    目标价格
                  </label>
                  <input
                    type="number"
                    step="0.001"
                    min="0"
                    value={targetPrice}
                    onChange={(e) => setTargetPrice(e.target.value)}
                    placeholder="输入目标价格"
                    className="w-full px-3 py-2.5 bg-secondary rounded-lg text-foreground outline-none focus:ring-2 focus:ring-primary/50"
                    autoFocus
                  />
                </div>

                {/* 提醒方向 */}
                <div className="mb-4">
                  <label className="block text-sm font-medium mb-1.5">
                    提醒方向
                  </label>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setDirection("below")}
                      className={cn(
                        "flex-1 py-2 rounded-lg text-sm font-medium transition-colors",
                        direction === "below"
                          ? "bg-down/15 text-down border border-down/30"
                          : "bg-secondary text-muted-foreground"
                      )}
                    >
                      ⬇️ 跌破
                    </button>
                    <button
                      onClick={() => setDirection("above")}
                      className={cn(
                        "flex-1 py-2 rounded-lg text-sm font-medium transition-colors",
                        direction === "above"
                          ? "bg-up/15 text-up border border-up/30"
                          : "bg-secondary text-muted-foreground"
                      )}
                    >
                      ⬆️ 突破
                    </button>
                  </div>
                </div>

                {/* 备注 */}
                <div className="mb-4">
                  <label className="block text-sm font-medium mb-1.5">
                    备注（可选）
                  </label>
                  <input
                    type="text"
                    maxLength={200}
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    placeholder="到这个价我要..."
                    className="w-full px-3 py-2.5 bg-secondary rounded-lg text-foreground outline-none focus:ring-2 focus:ring-primary/50"
                  />
                </div>

                {/* 错误/成功提示 */}
                {error && !error.includes("Telegram") && (
                  <div className="mb-4 p-3 bg-destructive/10 text-destructive rounded-lg text-sm">
                    {error}
                  </div>
                )}
                {successMsg && (
                  <div className="mb-4 p-3 bg-green-500/10 text-green-600 dark:text-green-400 rounded-lg text-sm">
                    {successMsg}
                  </div>
                )}

                {/* 按钮 */}
                <div className="flex gap-3">
                  <button
                    onClick={() => setShowDialog(false)}
                    disabled={isSubmitting}
                    className="flex-1 py-2.5 rounded-lg bg-secondary text-muted-foreground font-medium"
                  >
                    取消
                  </button>
                  <button
                    onClick={handleSubmit}
                    disabled={isSubmitting || !targetPrice}
                    className="flex-1 py-2.5 rounded-lg bg-primary text-primary-foreground font-medium disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
                    确认设置
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  )
}
```

**重要实现注意事项:**
- `useAuth` hook 的实际路径需要确认：可能是 `@/hooks/use-auth` 或 `@/lib/auth-context`，请在实现时检查项目中的实际路径。
- `text-up`/`text-down`/`bg-up`/`bg-down` 是项目自定义的 Tailwind 颜色（红涨绿跌），确认在 `tailwind.config` 中已定义。
- `pb-safe` 和 `animate-in` 是项目已有的自定义样式类。
- 弹窗使用 `fixed inset-0` 模式，与项目已有的 ConfirmationDialog 保持一致。

### Step 2: 集成到 ETF 详情页

修改 `frontend/app/etf/[code]/page.tsx`:

1. 在文件顶部 import 区域添加:
```tsx
import PriceAlertButton from "@/components/PriceAlertButton"
```

2. 修改 header 区域（约 line 197-207），将原来的单个 Star 按钮替换为包含 PriceAlertButton 和 Star 的容器:

**替换前** (line 197-207):
```tsx
          <button
            onClick={toggleWatchlist}
            className="absolute right-4 flex w-10 h-10 items-center justify-center rounded-full text-foreground hover:bg-secondary transition-colors -mr-2 active:scale-90"
          >
            <Star
              className={cn(
                "h-6 w-6 transition-all",
                watched ? "fill-yellow-400 text-yellow-400" : "text-muted-foreground"
              )}
            />
          </button>
```

**替换后**:
```tsx
          <div className="absolute right-4 flex items-center gap-0 -mr-2">
            {info && (
              <PriceAlertButton
                etfCode={code}
                etfName={info.name}
                currentPrice={info.price}
              />
            )}
            <button
              onClick={toggleWatchlist}
              className="flex w-10 h-10 items-center justify-center rounded-full text-foreground hover:bg-secondary transition-colors active:scale-90"
            >
              <Star
                className={cn(
                  "h-6 w-6 transition-all",
                  watched ? "fill-yellow-400 text-yellow-400" : "text-muted-foreground"
                )}
              />
            </button>
          </div>
```

### Step 3: 验证 TypeScript 编译

```bash
cd frontend && npx tsc --noEmit
```

预期: 无错误

### Step 4: 验证构建

```bash
cd frontend && npm run build
```

预期: 构建成功

### Step 5: 提交

```bash
git add frontend/components/PriceAlertButton.tsx frontend/app/etf/\[code\]/page.tsx
git commit -m "feat(price-alert): add PriceAlertButton component in ETF detail page"
```

---

## Task 8: 前端管理列表 (Settings Page Integration)

**Files:**
- Create: `frontend/components/PriceAlertList.tsx`
- Modify: `frontend/app/settings/alerts/page.tsx` — 添加到价提醒管理区域

### Step 1: 实现 PriceAlertList 组件

```tsx
// frontend/components/PriceAlertList.tsx
"use client"

import { useState, useEffect, useCallback } from "react"
import { Loader2, Trash2, Bell } from "lucide-react"
import { useAuth } from "@/hooks/use-auth"
import {
  getPriceAlerts,
  deletePriceAlert,
  getTelegramConfig,
  type PriceAlertItem,
} from "@/lib/api"
import { cn } from "@/lib/utils"
import { useRouter } from "next/navigation"

export default function PriceAlertList() {
  const { token } = useAuth()
  const router = useRouter()
  const [alerts, setAlerts] = useState<PriceAlertItem[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<"active" | "triggered">("active")
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [telegramConfigured, setTelegramConfigured] = useState<boolean | null>(null)

  const fetchAlerts = useCallback(async () => {
    if (!token) return
    try {
      setLoading(true)
      const [alertsData, telegramData] = await Promise.all([
        getPriceAlerts(token),
        getTelegramConfig(token).catch(() => null),
      ])
      setAlerts(alertsData)
      setTelegramConfigured(
        !!telegramData?.enabled && !!telegramData?.verified
      )
    } catch {
      // 静默失败
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    fetchAlerts()
  }, [fetchAlerts])

  const handleDelete = async (id: number) => {
    if (!token) return
    setDeletingId(id)
    try {
      await deletePriceAlert(token, id)
      setAlerts((prev) => prev.filter((a) => a.id !== id))
    } catch {
      // 静默失败
    } finally {
      setDeletingId(null)
    }
  }

  const activeAlerts = alerts.filter((a) => !a.is_triggered)
  const triggeredAlerts = alerts.filter((a) => a.is_triggered)
  const displayed = filter === "active" ? activeAlerts : triggeredAlerts

  if (!token) return null

  return (
    <section className="mt-6">
      {/* 标题 */}
      <div className="flex items-center gap-2 mb-3">
        <Bell className="h-5 w-5 text-primary" />
        <h3 className="text-base font-bold">
          到价提醒
          <span className="ml-1.5 text-sm font-normal text-muted-foreground">
            ({activeAlerts.length}/20)
          </span>
        </h3>
      </div>

      {/* Telegram 未配置提示 */}
      {telegramConfigured === false && (
        <div className="p-3 bg-amber-500/10 rounded-lg text-sm mb-3">
          <p className="text-amber-600 dark:text-amber-400">
            请先配置 Telegram 通知才能创建到价提醒
          </p>
          <button
            onClick={() => router.push("/settings/notifications")}
            className="mt-1 text-primary font-medium text-sm underline"
          >
            去配置
          </button>
        </div>
      )}

      {/* 筛选标签 */}
      <div className="flex gap-2 mb-3">
        <button
          onClick={() => setFilter("active")}
          className={cn(
            "px-3 py-1 rounded-full text-sm font-medium transition-colors",
            filter === "active"
              ? "bg-primary text-primary-foreground"
              : "bg-secondary text-muted-foreground"
          )}
        >
          活跃 ({activeAlerts.length})
        </button>
        <button
          onClick={() => setFilter("triggered")}
          className={cn(
            "px-3 py-1 rounded-full text-sm font-medium transition-colors",
            filter === "triggered"
              ? "bg-primary text-primary-foreground"
              : "bg-secondary text-muted-foreground"
          )}
        >
          已触发 ({triggeredAlerts.length})
        </button>
      </div>

      {/* 列表 */}
      {loading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : displayed.length === 0 ? (
        <div className="text-center py-8 text-sm text-muted-foreground">
          {filter === "active" ? "暂无活跃提醒" : "暂无已触发提醒"}
        </div>
      ) : (
        <div className="space-y-2">
          {displayed.map((alert) => (
            <div
              key={alert.id}
              className="p-3 bg-card rounded-lg border border-border/50"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    {alert.is_triggered && (
                      <span className="text-green-500 text-xs font-medium">
                        ✅
                      </span>
                    )}
                    <span className="font-medium text-sm truncate">
                      {alert.etf_name}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      ({alert.etf_code})
                    </span>
                  </div>

                  <div className="mt-1 text-sm">
                    <span>
                      {alert.direction === "below" ? "⬇️ 跌破" : "⬆️ 突破"}{" "}
                      {alert.target_price}
                    </span>
                    {alert.is_triggered && alert.triggered_price && (
                      <span className="ml-2 text-muted-foreground">
                        → 实际 {alert.triggered_price}
                      </span>
                    )}
                  </div>

                  {alert.note && (
                    <div className="mt-1 text-xs text-muted-foreground truncate">
                      📝 {alert.note}
                    </div>
                  )}

                  <div className="mt-1 text-xs text-muted-foreground/60">
                    {alert.is_triggered && alert.triggered_at
                      ? `触发于 ${new Date(alert.triggered_at).toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" })} ${new Date(alert.triggered_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`
                      : `设置于 ${new Date(alert.created_at).toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" })}`}
                  </div>
                </div>

                <button
                  onClick={() => handleDelete(alert.id)}
                  disabled={deletingId === alert.id}
                  className="ml-2 p-2 rounded-lg hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
                >
                  {deletingId === alert.id ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
```

**重要实现注意事项:**
- `useAuth` hook 路径需要与 Task 7 保持一致。
- 日期格式化使用 `toLocaleDateString("zh-CN")` 确保中文环境下的正确显示。

### Step 2: 集成到 Settings Alerts 页面

修改 `frontend/app/settings/alerts/page.tsx`:

1. 在文件顶部 import 区域添加:
```tsx
import PriceAlertList from "@/components/PriceAlertList"
```

2. 在信号类型开关区域的 `</section>` 之后、操作按钮（Test Check / Save Config）之前，添加:
```tsx
            {/* 到价提醒管理 */}
            <PriceAlertList />
```

具体位置需要阅读 `alerts/page.tsx` 源码确定，预期在 line 307 附近的 `</section>` 之后。

### Step 3: 验证 TypeScript 编译

```bash
cd frontend && npx tsc --noEmit
```

预期: 无错误

### Step 4: 验证构建

```bash
cd frontend && npm run build
```

预期: 构建成功

### Step 5: 提交

```bash
git add frontend/components/PriceAlertList.tsx frontend/app/settings/alerts/page.tsx
git commit -m "feat(price-alert): add PriceAlertList component in settings page"
```

---

## Task 9: 更新文档

**Files:**
- Modify: `API_REFERENCE.md` — 添加到价提醒 API 端点
- Modify: `CODE_NAVIGATION.md` — 添加新增文件路径
- Modify: `docs/design/2026-03-05-price-alert-design.md:5` — 状态改为"已实现"

### Step 1: 更新 API_REFERENCE.md

在现有 API 端点表格中添加到价提醒部分:

```markdown
### 到价提醒 (Price Alerts)

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/api/v1/price-alerts` | 获取当前用户的所有提醒（支持 `?active_only=true`） | 需要 |
| POST | `/api/v1/price-alerts` | 创建到价提醒 | 需要 |
| DELETE | `/api/v1/price-alerts/{id}` | 删除提醒 | 需要 |
```

### Step 2: 更新 CODE_NAVIGATION.md

在后端和前端文件列表中添加新文件:

后端新增:
- `backend/app/models/price_alert.py` — 到价提醒数据模型
- `backend/app/services/price_alert_service.py` — 到价提醒业务逻辑
- `backend/app/api/v1/endpoints/price_alerts.py` — 到价提醒 API 端点

前端新增:
- `frontend/components/PriceAlertButton.tsx` — 详情页铃铛按钮 + 创建弹窗
- `frontend/components/PriceAlertList.tsx` — 设置页提醒管理列表

### Step 3: 更新设计文档状态

修改 `docs/design/2026-03-05-price-alert-design.md` 第 5 行:

**修改前**: `> 状态: 待实现`
**修改后**: `> 状态: 已实现`

### Step 4: 提交

```bash
git add API_REFERENCE.md CODE_NAVIGATION.md docs/design/2026-03-05-price-alert-design.md
git commit -m "docs: update API reference and code navigation for price alerts"
```

---

## Task 10: 全量验证

### Step 1: 运行全部后端测试

```bash
cd backend && python -m pytest -v
```

预期: 全部 PASS

### Step 2: 运行前端构建

```bash
cd frontend && npm run build
```

预期: 构建成功，无 TypeScript 错误

### Step 3: 运行前端测试

```bash
cd frontend && npx vitest run
```

预期: 全部 PASS

### Step 4: 手动端到端验证（可选）

启动开发服务器：
```bash
./manage.sh start
```

验证流程：
1. 登录 → 进入 ETF 详情页 → 点击铃铛图标
2. 输入目标价 → 确认创建 → 看到成功提示
3. 进入 `/settings/alerts` → 看到新创建的提醒
4. 删除提醒 → 确认已删除

---

## 实现注意事项

### 后端
1. **`PriceAlert` 模型必须被导入才能被 `create_db_and_tables()` 创建**: 通过路由注册 (`api.py` import `price_alerts`) 自动完成。
2. **`cleanup_old_triggered()` 使用原生 SQL**: SQLModel ORM 不支持 SQLite 特定函数的批量删除。如日后迁移 PostgreSQL 需调整。
3. **float 比较容差 EPSILON = 0.0001**: ETF 价格最多 3 位小数，容差在第 4 位。
4. **`_get_current_etf_price()` 依赖内存缓存**: 服务器刚启动且缓存未就绪时可能返回 None，端点已做 400 错误处理。
5. **`_check_price_alerts()` 中的价格获取**: 逐个 ETF 调用 `ak_service.get_etf_info()`，如果活跃提醒涉及大量不同 ETF，考虑批量获取优化（V1 先不做）。

### 前端
1. **`useAuth` hook 路径**: 需确认项目中是 `@/hooks/use-auth` 还是 `@/lib/auth-context`，实现时需匹配实际路径。
2. **颜色类名**: `text-up`/`text-down`/`bg-up`/`bg-down` 是项目自定义 Tailwind 颜色（红涨绿跌），确认 `tailwind.config` 中已定义。
3. **`pb-safe` 和 `animate-in`**: 项目已有自定义样式类。
4. **弹窗使用 `fixed inset-0`**: 与 ConfirmationDialog 的简单实现模式保持一致。
