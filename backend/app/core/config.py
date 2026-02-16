"""
ETFTool 应用配置管理

使用 pydantic-settings 从环境变量和 .env 文件加载配置。
配置优先级: 环境变量 > .env 文件 > 默认值
"""

import os
from typing import List, Union
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置模型"""
    
    # 基础配置
    PROJECT_NAME: str = "ETFTool"
    VERSION: str = os.getenv("APP_VERSION", "dev")
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    
    # 安全配置
    SECRET_KEY: str
    ENCRYPTION_SALT: str = "etftool_telegram_salt"  # 加密 salt，建议在生产环境中修改
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7天
    
    # CORS 配置
    BACKEND_CORS_ORIGINS: Union[str, List[str]] = "http://localhost:3000,http://127.0.0.1:3000"
    
    # 服务器配置
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    
    # 数据库配置
    DATABASE_URL: str = "sqlite:///./etftool.db"
    
    # 缓存配置
    CACHE_DIR: str = "./cache"
    CACHE_TTL: int = 3600
    
    # 速率限制配置
    ENABLE_RATE_LIMIT: bool = False

    # 数据源配置
    HISTORY_DATA_SOURCES: List[str] = ["eastmoney", "ths_history"]
    BAOSTOCK_ENABLED: bool = False  # Baostock 不支持 ETF 基金，仅支持股票
    CIRCUIT_BREAKER_THRESHOLD: float = 0.1
    CIRCUIT_BREAKER_WINDOW: int = 10
    CIRCUIT_BREAKER_COOLDOWN: int = 300
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    @property
    def is_development(self) -> bool:
        """判断是否为开发环境"""
        return self.ENVIRONMENT == "development"
    
    @property
    def cors_origins(self) -> List[str]:
        """处理 CORS 来源配置，支持字符串和列表格式"""
        if isinstance(self.BACKEND_CORS_ORIGINS, str):
            if self.BACKEND_CORS_ORIGINS == "*":
                return ["*"]
            return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",")]
        return self.BACKEND_CORS_ORIGINS
    
    def validate_security_config(self) -> None:
        """启动时验证安全配置"""
        # SECRET_KEY 长度检查
        if len(self.SECRET_KEY) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters. "
                "Generate one using: python scripts/generate_secret.py"
            )

        # 生产环境下拒绝默认 SECRET_KEY
        default_keys = [
            "your-secret-key-here-change-in-production",
            "change-me-in-production",
            "insecure-secret-key",
            "default-secret-key"
        ]
        if not self.is_development and self.SECRET_KEY in default_keys:
            raise ValueError(
                "Cannot use default SECRET_KEY in production environment. "
                "Generate a secure key using: python scripts/generate_secret.py"
            )
        
        # CORS 安全检查
        if not self.is_development and "*" in self.cors_origins:
            raise ValueError(
                "CORS cannot be '*' in production environment. "
                "Please specify allowed origins explicitly."
            )
        
        if self.is_development and "*" in self.cors_origins:
            print("⚠️  WARNING: CORS set to '*' - convenient but not recommended for security")
        
        # 局域网访问提示
        if self.BACKEND_HOST == "0.0.0.0":
            print(f"ℹ️  Server listening on all interfaces (0.0.0.0:{self.BACKEND_PORT})")
            print(f"ℹ️  Accessible via LAN at http://<your-local-ip>:{self.BACKEND_PORT}")
        
        print(f"✅ Configuration validated (environment: {self.ENVIRONMENT})")


# 获取 .env 文件的绝对路径（相对于 backend 目录）
_env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")

# 创建全局配置实例
settings = Settings(_env_file=_env_file if os.path.exists(_env_file) else None)

# 启动时验证配置
settings.validate_security_config()
