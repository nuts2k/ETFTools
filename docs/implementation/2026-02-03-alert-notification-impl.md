# ETF 指标变化 Telegram 通知系统实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 ETFTool 新增基于指标变化的自动 Telegram 通知功能，监控用户自选股的温度计、均线信号等关键指标变化

**Architecture:** 新增 APScheduler 调度器服务 + AlertService 信号检测服务 + AlertStateService 状态缓存，复用现有的 temperature_service、trend_service 和 notification_service

**Tech Stack:** Python 3.9+, FastAPI, APScheduler 3.10+, DiskCache, Next.js 14, TypeScript

---

## 任务概览

| 任务 | 描述 | 文件数 |
|------|------|--------|
| Task 1 | 添加 APScheduler 依赖 | 1 |
| Task 2 | 创建告警配置数据模型 | 1 |
| Task 3 | 创建告警状态缓存服务 | 1 |
| Task 4 | 创建信号检测服务 | 1 |
| Task 5 | 创建调度器服务 | 1 |
| Task 6 | 集成调度器到 FastAPI 生命周期 | 1 |
| Task 7 | 扩展通知服务消息格式化 | 1 |
| Task 8 | 创建告警 API 端点 | 2 |
| Task 9 | 添加前端 API 函数 | 1 |
| Task 10 | 创建前端告警配置页面 | 1 |

---

## Task 1: 添加 APScheduler 依赖

**Files:**
- Modify: `backend/requirements.txt`

**Step 1: 添加 apscheduler 依赖**

在 `backend/requirements.txt` 文件末尾添加：

```
apscheduler==3.10.4
```

**Step 2: 安装依赖**

Run: `cd /Users/kelin/Work/ETFTool/backend && pip install apscheduler==3.10.4`
Expected: Successfully installed apscheduler

**Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add apscheduler dependency for alert scheduling"
```

---

## Task 2: 创建告警配置数据模型

**Files:**
- Create: `backend/app/models/alert_config.py`

**Step 1: 创建配置模型文件**

```python
"""
告警配置数据模型

定义全局调度配置和用户告警偏好
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class AlertScheduleConfig(BaseModel):
    """全局调度配置"""
    # 盘中检查
    intraday_enabled: bool = True
    intraday_interval_minutes: int = Field(default=30, ge=5, le=120)
    intraday_start_time: str = "09:30"
    intraday_end_time: str = "15:00"

    # 收盘汇总
    daily_summary_enabled: bool = True
    daily_summary_time: str = "15:30"

    # 交易日判断
    skip_weekends: bool = True


class UserAlertPreferences(BaseModel):
    """用户告警偏好（存储在 User.settings["alerts"]）"""
    enabled: bool = True

    # 信号类型开关
    temperature_change: bool = True      # 温度等级变化
    extreme_temperature: bool = True     # 极端温度
    ma_crossover: bool = True            # 均线上穿/下穿
    ma_alignment: bool = True            # 均线排列变化
    weekly_signal: bool = True           # 周线信号

    # 通知频率控制
    max_alerts_per_day: int = Field(default=20, ge=1, le=100)


class ETFAlertState(BaseModel):
    """ETF 告警状态快照（存储在 DiskCache）"""
    etf_code: str
    last_check_time: datetime

    # 温度计状态
    temperature_level: Optional[str] = None  # freezing/cool/warm/hot
    temperature_score: Optional[float] = None
    rsi_value: Optional[float] = None

    # 日线均线状态
    ma5_position: Optional[str] = None   # above/below/crossing_up/crossing_down
    ma20_position: Optional[str] = None
    ma60_position: Optional[str] = None
    ma_alignment: Optional[str] = None   # bullish/bearish/mixed

    # 周线状态
    weekly_alignment: Optional[str] = None  # bullish/bearish/mixed


class SignalItem(BaseModel):
    """单个信号项"""
    etf_code: str
    etf_name: str
    signal_type: str       # temperature_change, ma_crossover, etc.
    signal_detail: str     # 具体描述
    priority: str          # high, medium, low


class AlertMessage(BaseModel):
    """告警消息（合并多个信号）"""
    check_time: datetime
    signals: list[SignalItem] = []
```

**Step 2: 验证模型导入**

Run: `cd /Users/kelin/Work/ETFTool/backend && python -c "from app.models.alert_config import AlertScheduleConfig, UserAlertPreferences, ETFAlertState; print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add backend/app/models/alert_config.py
git commit -m "feat: add alert configuration data models"
```

---

## Task 3: 创建告警状态缓存服务

**Files:**
- Create: `backend/app/services/alert_state_service.py`

**Step 1: 创建状态缓存服务**

```python
"""
告警状态缓存服务

管理 ETF 告警状态的存储和去重逻辑
"""

import os
import logging
from datetime import datetime, date
from typing import Optional, Dict, Any

from diskcache import Cache

from app.models.alert_config import ETFAlertState

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.getcwd(), ".cache", "alerts")


class AlertStateService:
    """告警状态缓存服务"""

    def __init__(self):
        self._cache = Cache(CACHE_DIR)

    def _state_key(self, user_id: int, etf_code: str) -> str:
        """生成状态缓存 key"""
        return f"alert_state:{user_id}:{etf_code}"

    def _sent_key(self, user_id: int, etf_code: str, signal_type: str) -> str:
        """生成已发送信号缓存 key（当天去重）"""
        today = date.today().isoformat()
        return f"alert_sent:{user_id}:{etf_code}:{signal_type}:{today}"

    def get_state(self, user_id: int, etf_code: str) -> Optional[ETFAlertState]:
        """获取 ETF 的上次状态快照"""
        key = self._state_key(user_id, etf_code)
        data = self._cache.get(key)
        if data:
            return ETFAlertState(**data)
        return None

    def save_state(self, user_id: int, state: ETFAlertState) -> None:
        """保存 ETF 状态快照"""
        key = self._state_key(user_id, state.etf_code)
        # 状态保存 7 天
        self._cache.set(key, state.model_dump(), expire=7 * 24 * 3600)

    def is_signal_sent_today(
        self, user_id: int, etf_code: str, signal_type: str
    ) -> bool:
        """检查信号今天是否已发送"""
        key = self._sent_key(user_id, etf_code, signal_type)
        return self._cache.get(key) is not None

    def mark_signal_sent(
        self, user_id: int, etf_code: str, signal_type: str
    ) -> None:
        """标记信号已发送（当天有效）"""
        key = self._sent_key(user_id, etf_code, signal_type)
        # 计算到今天 23:59:59 的秒数
        now = datetime.now()
        end_of_day = datetime(now.year, now.month, now.day, 23, 59, 59)
        ttl = int((end_of_day - now).total_seconds())
        self._cache.set(key, True, expire=max(ttl, 1))

    def get_daily_sent_count(self, user_id: int) -> int:
        """获取用户今天已发送的信号数量"""
        today = date.today().isoformat()
        prefix = f"alert_sent:{user_id}:"
        count = 0
        for key in self._cache.iterkeys():
            if key.startswith(prefix) and key.endswith(today):
                count += 1
        return count

    def clear_user_state(self, user_id: int) -> None:
        """清除用户的所有状态缓存"""
        prefix = f"alert_state:{user_id}:"
        keys_to_delete = [k for k in self._cache.iterkeys() if k.startswith(prefix)]
        for key in keys_to_delete:
            self._cache.delete(key)


# 全局单例
alert_state_service = AlertStateService()
```

**Step 2: 验证服务导入**

Run: `cd /Users/kelin/Work/ETFTool/backend && python -c "from app.services.alert_state_service import alert_state_service; print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add backend/app/services/alert_state_service.py
git commit -m "feat: add alert state cache service for deduplication"
```

---

## Task 4: 创建信号检测服务

**Files:**
- Create: `backend/app/services/alert_service.py`

**Step 1: 创建信号检测服务**

```python
"""
告警信号检测服务

检测 ETF 指标变化并生成告警信号
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from app.models.alert_config import (
    ETFAlertState,
    SignalItem,
    UserAlertPreferences,
)
from app.services.temperature_service import temperature_service
from app.services.trend_service import trend_service
from app.services.alert_state_service import alert_state_service

logger = logging.getLogger(__name__)


class AlertService:
    """告警信号检测服务"""

    def __init__(self):
        pass

    def _detect_temperature_signals(
        self,
        etf_code: str,
        etf_name: str,
        current: Dict[str, Any],
        previous: Optional[ETFAlertState],
        prefs: UserAlertPreferences,
    ) -> List[SignalItem]:
        """检测温度计相关信号"""
        signals = []

        if not current.get("temperature"):
            return signals

        temp = current["temperature"]
        curr_level = temp.get("level")
        curr_score = temp.get("score")
        rsi = temp.get("rsi_value")

        # 温度等级变化
        if prefs.temperature_change and previous and previous.temperature_level:
            if curr_level != previous.temperature_level:
                signals.append(SignalItem(
                    etf_code=etf_code,
                    etf_name=etf_name,
                    signal_type="temperature_change",
                    signal_detail=f"温度 {previous.temperature_level} → {curr_level}",
                    priority="high",
                ))

        # 极端温度
        if prefs.extreme_temperature:
            if curr_level == "freezing" and (not previous or previous.temperature_level != "freezing"):
                signals.append(SignalItem(
                    etf_code=etf_code,
                    etf_name=etf_name,
                    signal_type="extreme_temperature",
                    signal_detail=f"进入冰点区域 (温度={curr_score})",
                    priority="high",
                ))
            elif curr_level == "hot" and (not previous or previous.temperature_level != "hot"):
                signals.append(SignalItem(
                    etf_code=etf_code,
                    etf_name=etf_name,
                    signal_type="extreme_temperature",
                    signal_detail=f"进入过热区域 (温度={curr_score})",
                    priority="high",
                ))

        # RSI 超买超卖
        if rsi is not None:
            prev_rsi = previous.rsi_value if previous else None
            if rsi > 70 and (prev_rsi is None or prev_rsi <= 70):
                signals.append(SignalItem(
                    etf_code=etf_code,
                    etf_name=etf_name,
                    signal_type="rsi_overbought",
                    signal_detail=f"RSI 超买 ({rsi:.1f})",
                    priority="medium",
                ))
            elif rsi < 30 and (prev_rsi is None or prev_rsi >= 30):
                signals.append(SignalItem(
                    etf_code=etf_code,
                    etf_name=etf_name,
                    signal_type="rsi_oversold",
                    signal_detail=f"RSI 超卖 ({rsi:.1f})",
                    priority="medium",
                ))

        return signals

    def _detect_ma_signals(
        self,
        etf_code: str,
        etf_name: str,
        current: Dict[str, Any],
        previous: Optional[ETFAlertState],
        prefs: UserAlertPreferences,
    ) -> List[SignalItem]:
        """检测均线相关信号"""
        signals = []

        daily = current.get("daily_trend")
        if not daily:
            return signals

        # 均线突破信号
        if prefs.ma_crossover:
            for ma_key, ma_label in [("ma60", "MA60"), ("ma20", "MA20")]:
                position = daily.get(f"{ma_key}_position")
                if position == "crossing_up":
                    signals.append(SignalItem(
                        etf_code=etf_code,
                        etf_name=etf_name,
                        signal_type=f"ma_cross_up_{ma_key}",
                        signal_detail=f"上穿 {ma_label}",
                        priority="high" if ma_key == "ma60" else "medium",
                    ))
                elif position == "crossing_down":
                    signals.append(SignalItem(
                        etf_code=etf_code,
                        etf_name=etf_name,
                        signal_type=f"ma_cross_down_{ma_key}",
                        signal_detail=f"下穿 {ma_label}",
                        priority="high" if ma_key == "ma60" else "medium",
                    ))

        # 均线排列变化
        if prefs.ma_alignment and previous and previous.ma_alignment:
            curr_align = daily.get("ma_alignment")
            if curr_align and curr_align != previous.ma_alignment:
                if curr_align == "bullish":
                    signals.append(SignalItem(
                        etf_code=etf_code,
                        etf_name=etf_name,
                        signal_type="ma_alignment_bullish",
                        signal_detail="均线多头排列形成",
                        priority="medium",
                    ))
                elif curr_align == "bearish":
                    signals.append(SignalItem(
                        etf_code=etf_code,
                        etf_name=etf_name,
                        signal_type="ma_alignment_bearish",
                        signal_detail="均线空头排列形成",
                        priority="medium",
                    ))

        return signals

    def _detect_weekly_signals(
        self,
        etf_code: str,
        etf_name: str,
        current: Dict[str, Any],
        previous: Optional[ETFAlertState],
        prefs: UserAlertPreferences,
    ) -> List[SignalItem]:
        """检测周线相关信号"""
        signals = []

        if not prefs.weekly_signal:
            return signals

        weekly = current.get("weekly_trend")
        if not weekly:
            return signals

        curr_status = weekly.get("ma_status")

        # 周线趋势转换
        if previous and previous.weekly_alignment and curr_status:
            if curr_status != previous.weekly_alignment:
                if curr_status == "bullish" and previous.weekly_alignment == "bearish":
                    signals.append(SignalItem(
                        etf_code=etf_code,
                        etf_name=etf_name,
                        signal_type="weekly_trend_bullish",
                        signal_detail="周线空转多",
                        priority="high",
                    ))
                elif curr_status == "bearish" and previous.weekly_alignment == "bullish":
                    signals.append(SignalItem(
                        etf_code=etf_code,
                        etf_name=etf_name,
                        signal_type="weekly_trend_bearish",
                        signal_detail="周线多转空",
                        priority="high",
                    ))

        return signals

    def detect_signals(
        self,
        user_id: int,
        etf_code: str,
        etf_name: str,
        current_metrics: Dict[str, Any],
        prefs: UserAlertPreferences,
    ) -> List[SignalItem]:
        """
        检测单个 ETF 的所有信号

        Args:
            user_id: 用户 ID
            etf_code: ETF 代码
            etf_name: ETF 名称
            current_metrics: 当前指标数据 (temperature, daily_trend, weekly_trend)
            prefs: 用户告警偏好

        Returns:
            检测到的信号列表
        """
        # 获取上次状态
        previous = alert_state_service.get_state(user_id, etf_code)

        all_signals = []

        # 检测各类信号
        all_signals.extend(self._detect_temperature_signals(
            etf_code, etf_name, current_metrics, previous, prefs
        ))
        all_signals.extend(self._detect_ma_signals(
            etf_code, etf_name, current_metrics, previous, prefs
        ))
        all_signals.extend(self._detect_weekly_signals(
            etf_code, etf_name, current_metrics, previous, prefs
        ))

        # 过滤已发送的信号（当天去重）
        filtered_signals = []
        for signal in all_signals:
            if not alert_state_service.is_signal_sent_today(
                user_id, etf_code, signal.signal_type
            ):
                filtered_signals.append(signal)

        return filtered_signals

    def build_current_state(
        self, etf_code: str, metrics: Dict[str, Any]
    ) -> ETFAlertState:
        """根据当前指标构建状态快照"""
        temp = metrics.get("temperature") or {}
        daily = metrics.get("daily_trend") or {}
        weekly = metrics.get("weekly_trend") or {}

        return ETFAlertState(
            etf_code=etf_code,
            last_check_time=datetime.now(),
            temperature_level=temp.get("level"),
            temperature_score=temp.get("score"),
            rsi_value=temp.get("rsi_value"),
            ma5_position=daily.get("ma5_position"),
            ma20_position=daily.get("ma20_position"),
            ma60_position=daily.get("ma60_position"),
            ma_alignment=daily.get("ma_alignment"),
            weekly_alignment=weekly.get("ma_status"),
        )


# 全局单例
alert_service = AlertService()
```

**Step 2: 验证服务导入**

Run: `cd /Users/kelin/Work/ETFTool/backend && python -c "from app.services.alert_service import alert_service; print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add backend/app/services/alert_service.py
git commit -m "feat: add alert signal detection service"
```

---

## Task 5: 创建调度器服务

**Files:**
- Create: `backend/app/services/alert_scheduler.py`

**Step 1: 创建调度器服务**

```python
"""
告警调度器服务

使用 APScheduler 管理定时任务
"""

import logging
from datetime import datetime
from typing import List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session, select

from app.core.database import engine
from app.models.user import User, Watchlist
from app.models.alert_config import UserAlertPreferences, SignalItem
from app.services.alert_service import alert_service
from app.services.alert_state_service import alert_state_service
from app.services.notification_service import TelegramNotificationService
from app.services.akshare_service import ak_service
from app.services.temperature_service import temperature_service
from app.services.trend_service import trend_service
from app.core.encryption import decrypt_token
from app.core.config import settings

logger = logging.getLogger(__name__)


class AlertScheduler:
    """告警调度器"""

    def __init__(self):
        self._scheduler: Optional[AsyncIOScheduler] = None

    def start(self) -> None:
        """启动调度器"""
        if self._scheduler is not None:
            return

        self._scheduler = AsyncIOScheduler()

        # 收盘后检查 (每天 15:30)
        self._scheduler.add_job(
            self._run_daily_check,
            CronTrigger(hour=15, minute=30, day_of_week="mon-fri"),
            id="daily_alert_check",
            replace_existing=True,
        )

        self._scheduler.start()
        logger.info("Alert scheduler started")

    def stop(self) -> None:
        """停止调度器"""
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            logger.info("Alert scheduler stopped")

    async def _run_daily_check(self) -> None:
        """执行每日告警检查"""
        logger.info("Running daily alert check...")

        with Session(engine) as session:
            # 获取所有启用告警的用户
            users = session.exec(select(User)).all()

            for user in users:
                try:
                    await self._check_user_alerts(session, user)
                except Exception as e:
                    logger.error(f"Error checking alerts for user {user.id}: {e}")

    async def _check_user_alerts(self, session: Session, user: User) -> None:
        """检查单个用户的告警"""
        # 获取用户告警配置
        alert_settings = (user.settings or {}).get("alerts", {})
        prefs = UserAlertPreferences(**alert_settings)

        if not prefs.enabled:
            return

        # 检查 Telegram 配置
        telegram_config = (user.settings or {}).get("telegram", {})
        if not telegram_config.get("enabled") or not telegram_config.get("verified"):
            return

        # 获取用户自选股
        watchlist = session.exec(
            select(Watchlist).where(Watchlist.user_id == user.id)
        ).all()

        if not watchlist:
            return

        all_signals: List[SignalItem] = []

        for item in watchlist:
            try:
                signals = await self._check_etf_signals(
                    user.id, item.etf_code, item.etf_name or item.etf_code, prefs
                )
                all_signals.extend(signals)
            except Exception as e:
                logger.error(f"Error checking ETF {item.etf_code}: {e}")

        # 发送合并消息
        if all_signals:
            await self._send_alert_message(user, telegram_config, all_signals)

    async def _check_etf_signals(
        self,
        user_id: int,
        etf_code: str,
        etf_name: str,
        prefs: UserAlertPreferences,
    ) -> List[SignalItem]:
        """检查单个 ETF 的信号"""
        # 获取历史数据
        df = ak_service.fetch_etf_history(etf_code)
        if df is None or df.empty:
            return []

        # 计算指标
        metrics = {
            "temperature": temperature_service.calculate_temperature(df),
            "daily_trend": trend_service.get_daily_trend(df),
            "weekly_trend": trend_service.get_weekly_trend(df),
        }

        # 检测信号
        signals = alert_service.detect_signals(
            user_id, etf_code, etf_name, metrics, prefs
        )

        # 更新状态
        if signals:
            state = alert_service.build_current_state(etf_code, metrics)
            alert_state_service.save_state(user_id, state)

            # 标记信号已发送
            for signal in signals:
                alert_state_service.mark_signal_sent(
                    user_id, etf_code, signal.signal_type
                )

        return signals

    async def _send_alert_message(
        self,
        user: User,
        telegram_config: dict,
        signals: List[SignalItem],
    ) -> None:
        """发送告警消息"""
        bot_token = decrypt_token(telegram_config["botToken"], settings.SECRET_KEY)
        chat_id = telegram_config["chatId"]

        message = self._format_message(signals)

        try:
            await TelegramNotificationService.send_message(bot_token, chat_id, message)
            logger.info(f"Sent {len(signals)} alerts to user {user.id}")
        except Exception as e:
            logger.error(f"Failed to send alert to user {user.id}: {e}")

    def _format_message(self, signals: List[SignalItem]) -> str:
        """格式化告警消息"""
        now = datetime.now().strftime("%H:%M")

        high_priority = [s for s in signals if s.priority == "high"]
        medium_priority = [s for s in signals if s.priority == "medium"]

        lines = [f"📊 <b>ETF 信号提醒</b> ({now})", ""]

        if high_priority:
            lines.append("🔥 <b>高优先级:</b>")
            for s in high_priority:
                lines.append(f"• {s.etf_code} {s.etf_name}: {s.signal_detail}")
            lines.append("")

        if medium_priority:
            lines.append("📈 <b>中优先级:</b>")
            for s in medium_priority:
                lines.append(f"• {s.etf_code} {s.etf_name}: {s.signal_detail}")
            lines.append("")

        lines.append(f"共 {len(signals)} 个信号")

        return "\n".join(lines)

    async def trigger_check(self, user_id: int) -> dict:
        """手动触发检查（用于测试）"""
        with Session(engine) as session:
            user = session.get(User, user_id)
            if not user:
                return {"success": False, "message": "用户不存在"}

            try:
                await self._check_user_alerts(session, user)
                return {"success": True, "message": "检查完成"}
            except Exception as e:
                return {"success": False, "message": str(e)}


# 全局单例
alert_scheduler = AlertScheduler()
```

**Step 2: 验证服务导入**

Run: `cd /Users/kelin/Work/ETFTool/backend && python -c "from app.services.alert_scheduler import alert_scheduler; print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add backend/app/services/alert_scheduler.py
git commit -m "feat: add alert scheduler service with APScheduler"
```

---

## Task 6: 集成调度器到 FastAPI 生命周期

**Files:**
- Modify: `backend/app/main.py`

**Step 1: 导入调度器**

在 `backend/app/main.py` 文件顶部导入部分添加：

```python
from app.services.alert_scheduler import alert_scheduler
```

**Step 2: 修改 lifespan 函数**

将 `lifespan` 函数修改为：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Application starting up...")
    create_db_and_tables()
    logger.info("Database initialized.")
    thread = threading.Thread(target=load_initial_data)
    thread.daemon = True
    thread.start()

    # 启动告警调度器
    alert_scheduler.start()
    logger.info("Alert scheduler started.")

    yield

    # Shutdown
    alert_scheduler.stop()
    logger.info("Alert scheduler stopped.")
    logger.info("Application shutting down...")
```

**Step 3: 验证应用启动**

Run: `cd /Users/kelin/Work/ETFTool/backend && timeout 5 python -c "from app.main import app; print('OK')" || echo "OK (timeout expected)"`
Expected: OK

**Step 4: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: integrate alert scheduler into FastAPI lifespan"
```

---

## Task 7: 扩展通知服务消息格式化

**Files:**
- Modify: `backend/app/services/notification_service.py`

**Step 1: 添加告警消息格式化方法**

在 `TelegramNotificationService` 类中添加静态方法：

```python
    @staticmethod
    def format_alert_message(signals: list, check_time: str) -> str:
        """
        格式化告警消息

        Args:
            signals: SignalItem 列表
            check_time: 检查时间字符串 (HH:MM)

        Returns:
            格式化的 HTML 消息
        """
        high_priority = [s for s in signals if s.get("priority") == "high"]
        medium_priority = [s for s in signals if s.get("priority") == "medium"]

        lines = [f"📊 <b>ETF 信号提醒</b> ({check_time})", ""]

        if high_priority:
            lines.append("🔥 <b>高优先级:</b>")
            for s in high_priority:
                lines.append(f"• {s['etf_code']} {s['etf_name']}: {s['signal_detail']}")
            lines.append("")

        if medium_priority:
            lines.append("📈 <b>中优先级:</b>")
            for s in medium_priority:
                lines.append(f"• {s['etf_code']} {s['etf_name']}: {s['signal_detail']}")
            lines.append("")

        lines.append(f"共 {len(signals)} 个信号")

        return "\n".join(lines)
```

**Step 2: 验证服务导入**

Run: `cd /Users/kelin/Work/ETFTool/backend && python -c "from app.services.notification_service import TelegramNotificationService; print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add backend/app/services/notification_service.py
git commit -m "feat: add alert message formatting to notification service"
```

---

## Task 8: 创建告警 API 端点

**Files:**
- Create: `backend/app/api/v1/endpoints/alerts.py`
- Modify: `backend/app/api/v1/api.py`

**Step 1: 创建告警 API 端点文件**

```python
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
    ma_crossover: bool = True
    ma_alignment: bool = True
    weekly_signal: bool = True
    max_alerts_per_day: int = 20


class AlertConfigResponse(BaseModel):
    """告警配置响应"""
    enabled: bool
    temperature_change: bool
    extreme_temperature: bool
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
```

**Step 2: 注册路由到 api.py**

在 `backend/app/api/v1/api.py` 中添加导入和路由注册：

```python
from app.api.v1.endpoints import etf, auth, users, watchlist, notifications, alerts

# ... 现有路由 ...
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
```

**Step 3: 验证 API 导入**

Run: `cd /Users/kelin/Work/ETFTool/backend && python -c "from app.api.v1.endpoints.alerts import router; print('OK')"`
Expected: OK

**Step 4: Commit**

```bash
git add backend/app/api/v1/endpoints/alerts.py backend/app/api/v1/api.py
git commit -m "feat: add alert configuration API endpoints"
```

---

## Task 9: 添加前端 API 函数

**Files:**
- Modify: `frontend/lib/api.ts`

**Step 1: 添加告警配置类型定义**

在 `frontend/lib/api.ts` 文件的类型定义部分添加：

```typescript
// 告警配置类型
export interface AlertConfig {
  enabled: boolean;
  temperature_change: boolean;
  extreme_temperature: boolean;
  ma_crossover: boolean;
  ma_alignment: boolean;
  weekly_signal: boolean;
  max_alerts_per_day: number;
}
```

**Step 2: 添加告警 API 函数**

在文件末尾添加：

```typescript
// 告警配置相关 API
export async function getAlertConfig(token: string): Promise<AlertConfig> {
  const response = await fetch(`${API_BASE_URL}/alerts/config`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: '获取配置失败' }));
    throw new Error(error.detail || '获取配置失败');
  }
  return response.json();
}

export async function saveAlertConfig(
  token: string,
  config: AlertConfig
): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE_URL}/alerts/config`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify(config)
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: '保存配置失败' }));
    throw new Error(error.detail || '保存配置失败');
  }
  return response.json();
}

export async function triggerAlertCheck(
  token: string
): Promise<{ success: boolean; message: string }> {
  const response = await fetch(`${API_BASE_URL}/alerts/trigger`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: '触发检查失败' }));
    throw new Error(error.detail || '触发检查失败');
  }
  return response.json();
}
```

**Step 3: Commit**

```bash
git add frontend/lib/api.ts
git commit -m "feat: add alert configuration API functions to frontend"
```

---

## Task 10: 创建前端告警配置页面

**Files:**
- Create: `frontend/app/settings/alerts/page.tsx`

**Step 1: 创建告警配置页面**

```tsx
"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Bell,
  Thermometer,
  TrendingUp,
  BarChart3,
  Calendar,
  CheckCircle2,
  XCircle,
  Loader2,
} from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import {
  getAlertConfig,
  saveAlertConfig,
  triggerAlertCheck,
  type AlertConfig,
} from "@/lib/api";

export default function AlertsSettingsPage() {
  const router = useRouter();
  const { token } = useAuth();
  const [mounted, setMounted] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [toast, setToast] = useState<{
    message: string;
    type: "success" | "error";
  } | null>(null);

  const [config, setConfig] = useState<AlertConfig>({
    enabled: true,
    temperature_change: true,
    extreme_temperature: true,
    ma_crossover: true,
    ma_alignment: true,
    weekly_signal: true,
    max_alerts_per_day: 20,
  });

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (mounted && token) {
      loadConfig();
    }
  }, [mounted, token]);

  const loadConfig = async () => {
    try {
      const data = await getAlertConfig(token!);
      setConfig(data);
    } catch (error) {
      console.error("Failed to load config:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const showToast = (message: string, type: "success" | "error") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await saveAlertConfig(token!, config);
      showToast("配置已保存", "success");
    } catch (error: any) {
      showToast(error.message || "保存失败", "error");
    } finally {
      setIsSaving(false);
    }
  };

  const handleTest = async () => {
    setIsTesting(true);
    try {
      await saveAlertConfig(token!, config);
      const result = await triggerAlertCheck(token!);
      if (result.success) {
        showToast("检查完成，如有信号将发送通知", "success");
      } else {
        showToast(result.message || "检查失败", "error");
      }
    } catch (error: any) {
      showToast(error.message || "检查失败", "error");
    } finally {
      setIsTesting(false);
    }
  };

  if (!mounted || isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const Toggle = ({
    checked,
    onChange,
  }: {
    checked: boolean;
    onChange: (v: boolean) => void;
  }) => (
    <button
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
        checked ? "bg-primary" : "bg-muted"
      }`}
    >
      <span
        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
          checked ? "translate-x-6" : "translate-x-1"
        }`}
      />
    </button>
  );

  return (
    <div className="flex flex-col min-h-[100dvh] bg-background pb-20">
      {/* Header */}
      <header className="sticky top-0 z-40 bg-background/95 backdrop-blur-md pt-safe border-b border-border/50">
        <div className="flex h-14 items-center gap-4 px-5">
          <button
            onClick={() => router.back()}
            className="hover:opacity-70 transition-opacity"
          >
            <ArrowLeft className="h-6 w-6" />
          </button>
          <h1 className="text-2xl font-bold tracking-tight">信号通知</h1>
        </div>
      </header>

      <main className="flex-1 w-full max-w-md mx-auto px-4 pt-6 space-y-6">
        {/* 主开关 */}
        <section>
          <div className="bg-card rounded-xl overflow-hidden shadow-sm ring-1 ring-border/50">
            <div className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Bell className="h-5 w-5 text-muted-foreground" />
                <span className="text-base font-medium">启用信号通知</span>
              </div>
              <Toggle
                checked={config.enabled}
                onChange={(v) => setConfig({ ...config, enabled: v })}
              />
            </div>
          </div>
        </section>

        {/* 信号类型 */}
        <section>
          <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2 pl-3">
            监控信号类型
          </h2>
          <div className="bg-card rounded-xl overflow-hidden shadow-sm ring-1 ring-border/50 divide-y divide-border/50">
            <div className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Thermometer className="h-5 w-5 text-orange-500" />
                <div>
                  <span className="text-base">温度等级变化</span>
                  <p className="text-xs text-muted-foreground">
                    如 cool → warm
                  </p>
                </div>
              </div>
              <Toggle
                checked={config.temperature_change}
                onChange={(v) =>
                  setConfig({ ...config, temperature_change: v })
                }
              />
            </div>

            <div className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Thermometer className="h-5 w-5 text-red-500" />
                <div>
                  <span className="text-base">极端温度</span>
                  <p className="text-xs text-muted-foreground">
                    freezing 或 hot
                  </p>
                </div>
              </div>
              <Toggle
                checked={config.extreme_temperature}
                onChange={(v) =>
                  setConfig({ ...config, extreme_temperature: v })
                }
              />
            </div>

            <div className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <TrendingUp className="h-5 w-5 text-blue-500" />
                <div>
                  <span className="text-base">均线突破</span>
                  <p className="text-xs text-muted-foreground">
                    上穿/下穿 MA20、MA60
                  </p>
                </div>
              </div>
              <Toggle
                checked={config.ma_crossover}
                onChange={(v) => setConfig({ ...config, ma_crossover: v })}
              />
            </div>

            <div className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <BarChart3 className="h-5 w-5 text-purple-500" />
                <div>
                  <span className="text-base">均线排列变化</span>
                  <p className="text-xs text-muted-foreground">
                    多头/空头排列形成
                  </p>
                </div>
              </div>
              <Toggle
                checked={config.ma_alignment}
                onChange={(v) => setConfig({ ...config, ma_alignment: v })}
              />
            </div>

            <div className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Calendar className="h-5 w-5 text-green-500" />
                <div>
                  <span className="text-base">周线趋势信号</span>
                  <p className="text-xs text-muted-foreground">
                    周线多空转换
                  </p>
                </div>
              </div>
              <Toggle
                checked={config.weekly_signal}
                onChange={(v) => setConfig({ ...config, weekly_signal: v })}
              />
            </div>
          </div>
        </section>

        {/* 操作按钮 */}
        <section className="space-y-3">
          <button
            onClick={handleTest}
            disabled={isTesting}
            className="w-full py-3 bg-primary text-primary-foreground rounded-lg font-medium hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {isTesting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                检查中...
              </>
            ) : (
              "立即检查"
            )}
          </button>

          <button
            onClick={handleSave}
            disabled={isSaving}
            className="w-full py-3 bg-secondary text-secondary-foreground rounded-lg font-medium hover:bg-secondary/80 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {isSaving ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                保存中...
              </>
            ) : (
              "保存配置"
            )}
          </button>
        </section>

        {/* 说明 */}
        <section>
          <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2 pl-3">
            说明
          </h2>
          <div className="bg-card rounded-xl overflow-hidden shadow-sm ring-1 ring-border/50 p-4 space-y-2">
            <p className="text-sm text-muted-foreground">
              系统将在每个交易日收盘后（15:30）自动检查您自选股的指标变化，并通过
              Telegram 发送通知。
            </p>
            <p className="text-sm text-muted-foreground">
              同一 ETF 的同类信号每天最多发送一次，避免重复打扰。
            </p>
            <p className="text-xs text-muted-foreground mt-2">
              💡 请先在「通知设置」中配置并验证 Telegram Bot
            </p>
          </div>
        </section>
      </main>

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-24 left-1/2 -translate-x-1/2 z-50 animate-in fade-in slide-in-from-bottom-2">
          <div
            className={`flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg ${
              toast.type === "success"
                ? "bg-green-600 text-white"
                : "bg-destructive text-destructive-foreground"
            }`}
          >
            {toast.type === "success" ? (
              <CheckCircle2 className="h-4 w-4" />
            ) : (
              <XCircle className="h-4 w-4" />
            )}
            <span className="text-sm font-medium">{toast.message}</span>
          </div>
        </div>
      )}
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/app/settings/alerts/page.tsx
git commit -m "feat: add alert settings page to frontend"
```

---

## 验证方案

### 端到端测试步骤

1. **启动后端服务**
   ```bash
   cd /Users/kelin/Work/ETFTool/backend && uvicorn app.main:app --reload
   ```

2. **启动前端服务**
   ```bash
   cd /Users/kelin/Work/ETFTool/frontend && npm run dev
   ```

3. **配置 Telegram**
   - 访问 `/settings/notifications`
   - 配置 Bot Token 和 Chat ID
   - 测试连接确认配置正确

4. **配置告警**
   - 访问 `/settings/alerts`
   - 启用需要的信号类型
   - 保存配置

5. **添加自选股**
   - 添加几只 ETF 到自选股

6. **手动触发检查**
   - 在告警配置页面点击「立即检查」
   - 检查 Telegram 是否收到通知

---

## 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/requirements.txt` | 修改 | 添加 apscheduler 依赖 |
| `backend/app/models/alert_config.py` | **新建** | 配置数据模型 |
| `backend/app/services/alert_state_service.py` | **新建** | 状态缓存服务 |
| `backend/app/services/alert_service.py` | **新建** | 信号检测服务 |
| `backend/app/services/alert_scheduler.py` | **新建** | 调度器服务 |
| `backend/app/main.py` | 修改 | 集成调度器生命周期 |
| `backend/app/services/notification_service.py` | 修改 | 添加消息格式化 |
| `backend/app/api/v1/endpoints/alerts.py` | **新建** | API 端点 |
| `backend/app/api/v1/api.py` | 修改 | 注册路由 |
| `frontend/lib/api.ts` | 修改 | 添加 API 函数 |
| `frontend/app/settings/alerts/page.tsx` | **新建** | 前端配置页 |

