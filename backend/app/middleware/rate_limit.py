from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from app.core.config import settings

# 创建限流器
# 如果配置中启用了速率限制，则应用限制；否则不应用
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200/minute"] if settings.ENABLE_RATE_LIMIT else [],
    enabled=settings.ENABLE_RATE_LIMIT
)

async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """
    自定义速率限制异常处理
    返回 JSON 格式的 429 错误
    """
    return JSONResponse(
        status_code=429,
        content={
            "detail": "请求过于频繁，请稍后再试",
            "error": "rate_limit_exceeded",
            "retry_after": str(exc.detail) if hasattr(exc, "detail") else "60s"
        }
    )
