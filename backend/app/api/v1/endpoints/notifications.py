"""
通知相关 API 端点
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from sqlalchemy.orm.attributes import flag_modified
from pydantic import BaseModel, validator
from datetime import datetime
import re

from app.core.database import get_session
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.services.notification_service import TelegramNotificationService
from app.core.encryption import encrypt_token, decrypt_token
from app.core.config import settings


router = APIRouter()


class TelegramConfig(BaseModel):
    """Telegram 配置模型"""
    enabled: bool
    botToken: str
    chatId: str

    @validator('botToken')
    def validate_bot_token(cls, v):
        """验证 Bot Token 格式"""
        if v == "***SAVED***":
            return v
        # Telegram Bot Token 格式: 数字:字母数字-_
        if not re.match(r'^\d+:[A-Za-z0-9_-]+$', v):
            raise ValueError('Bot Token 格式不正确，应为: 数字:字母数字-_')
        return v

    @validator('chatId')
    def validate_chat_id(cls, v):
        """验证 Chat ID 格式"""
        # Chat ID 可以是纯数字或 @username
        if not (v.lstrip('-').isdigit() or (v.startswith('@') and len(v) > 1)):
            raise ValueError('Chat ID 格式不正确，应为数字或 @username')
        return v


@router.post("/telegram/config")
async def save_telegram_config(
    config: TelegramConfig,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    保存 Telegram 配置

    加密 Bot Token 并存储到用户设置中
    如果 botToken 为 ***SAVED***，则保持原有 token 不变
    """
    # 获取当前设置
    current_settings = current_user.settings or {}
    current_telegram = current_settings.get("telegram", {})

    # 判断是否需要更新 token
    if config.botToken == "***SAVED***":
        # 保持原有的加密 token
        encrypted_token = current_telegram.get("botToken", "")
        if not encrypted_token:
            raise HTTPException(status_code=400, detail="未找到已保存的 Bot Token")
    else:
        # 加密新的 Bot Token
        encrypted_token = encrypt_token(config.botToken, settings.SECRET_KEY)

    # 更新用户设置
    current_settings["telegram"] = {
        "enabled": config.enabled,
        "botToken": encrypted_token,
        "chatId": config.chatId,
        "verified": current_telegram.get("verified", False) if config.botToken == "***SAVED***" else False,
        "lastTestAt": current_telegram.get("lastTestAt") if config.botToken == "***SAVED***" else None
    }

    current_user.settings = current_settings
    flag_modified(current_user, "settings")  # 标记 JSON 字段已修改
    session.add(current_user)
    session.commit()

    return {"message": "配置已保存"}


@router.get("/telegram/config")
def get_telegram_config(current_user: User = Depends(get_current_user)):
    """
    获取 Telegram 配置

    返回配置时用特殊标记替代 Bot Token，避免前端误传
    """
    telegram_config = current_user.settings.get("telegram", {}) if current_user.settings else {}

    if telegram_config.get("botToken"):
        # 返回特殊标记，表示已保存 token
        telegram_config["botToken"] = "***SAVED***"

    return telegram_config


@router.post("/telegram/test")
async def test_telegram_config(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    测试 Telegram 连接

    发送测试消息验证配置是否正确，成功后更新验证状态
    """
    telegram_config = current_user.settings.get("telegram", {}) if current_user.settings else {}

    if not telegram_config.get("botToken") or not telegram_config.get("chatId"):
        raise HTTPException(status_code=400, detail="请先配置 Telegram Bot")

    # 解密 Token
    bot_token = decrypt_token(telegram_config["botToken"], settings.SECRET_KEY)
    chat_id = telegram_config["chatId"]

    # 测试连接
    result = await TelegramNotificationService.test_connection(bot_token, chat_id)

    if result["success"]:
        # 更新验证状态（使用与 save_telegram_config 一致的模式）
        current_settings = current_user.settings or {}
        current_telegram = current_settings.get("telegram", {})

        current_settings["telegram"] = {
            **current_telegram,
            "verified": True,
            "lastTestAt": datetime.utcnow().isoformat()
        }

        current_user.settings = current_settings
        flag_modified(current_user, "settings")  # 标记 JSON 字段已修改
        session.add(current_user)
        session.commit()

    return result


@router.delete("/telegram/config")
def delete_telegram_config(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    删除 Telegram 配置

    从用户设置中移除 Telegram 配置
    """
    current_settings = current_user.settings or {}
    if "telegram" in current_settings:
        del current_settings["telegram"]
        current_user.settings = current_settings
        flag_modified(current_user, "settings")  # 标记 JSON 字段已修改
        session.add(current_user)
        session.commit()

    return {"message": "配置已删除"}
