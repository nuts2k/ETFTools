from typing import Any, Optional
from datetime import datetime
from sqlmodel import Session, select
from app.models.system_config import SystemConfig, SystemConfigKeys


class SystemConfigService:
    @staticmethod
    def get_config(session: Session, key: str, default: Any = None) -> Any:
        config = session.exec(select(SystemConfig).where(SystemConfig.key == key)).first()
        return config.value if config else default

    @staticmethod
    def set_config(session: Session, key: str, value: Any, user_id: int, description: str = None) -> SystemConfig:
        config = session.exec(select(SystemConfig).where(SystemConfig.key == key)).first()
        if config:
            config.value = value
            config.updated_by = user_id
            config.updated_at = datetime.utcnow()
            if description:
                config.description = description
        else:
            config = SystemConfig(key=key, value=value, updated_by=user_id, description=description)
        session.add(config)
        session.commit()
        session.refresh(config)
        return config

    @staticmethod
    def is_registration_enabled(session: Session) -> bool:
        return SystemConfigService.get_config(session, SystemConfigKeys.REGISTRATION_ENABLED, default=True)

    @staticmethod
    def get_max_watchlist_items(session: Session) -> int:
        return SystemConfigService.get_config(session, SystemConfigKeys.MAX_WATCHLIST_ITEMS, default=100)
