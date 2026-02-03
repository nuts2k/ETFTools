"""
加密工具模块

使用 Fernet 对称加密保护敏感信息（如 Telegram Bot Token）
"""

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
from app.core.config import settings


def get_encryption_key(secret_key: str, salt: str = None) -> bytes:
    """
    从 SECRET_KEY 派生加密密钥

    使用 PBKDF2 密钥派生函数，从应用的 SECRET_KEY 生成用于 Fernet 加密的密钥

    Args:
        secret_key: 应用的 SECRET_KEY
        salt: 加密 salt，如果不提供则使用配置中的默认值

    Returns:
        bytes: Base64 编码的加密密钥
    """
    if salt is None:
        salt = settings.ENCRYPTION_SALT

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt.encode(),
        iterations=100000,
    )
    return base64.urlsafe_b64encode(kdf.derive(secret_key.encode()))


def encrypt_token(token: str, secret_key: str) -> str:
    """
    加密 Bot Token

    Args:
        token: 明文 Token
        secret_key: 应用的 SECRET_KEY

    Returns:
        str: 加密后的 Token
    """
    key = get_encryption_key(secret_key)
    f = Fernet(key)
    return f.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str, secret_key: str) -> str:
    """
    解密 Bot Token

    Args:
        encrypted_token: 加密的 Token
        secret_key: 应用的 SECRET_KEY

    Returns:
        str: 解密后的明文 Token

    Raises:
        cryptography.fernet.InvalidToken: 如果 Token 无效或密钥错误
    """
    key = get_encryption_key(secret_key)
    f = Fernet(key)
    return f.decrypt(encrypted_token.encode()).decode()
