from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import threading
import logging
import requests
import uvicorn

from app.core.config import settings
from app.core.cache import etf_cache
from app.core.database import create_db_and_tables
from app.core.share_history_database import create_share_history_tables
from app.core.init_admin import init_admin_from_env
from app.services.akshare_service import ak_service
from app.services.alert_scheduler import alert_scheduler
from app.services.fund_flow_collector import fund_flow_collector
from app.api.v1.api import api_router
from app.middleware.rate_limit import limiter, rate_limit_handler
from slowapi.errors import RateLimitExceeded

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_initial_data():
    """后台任务：加载全量 ETF 数据"""
    logger.info("Starting background data loading...")
    data = ak_service.fetch_all_etfs()
    if data:
        etf_cache.set_etf_list(data)
        logger.info("Initial data loaded into cache.")
    else:
        logger.warning("Failed to load initial data.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Application starting up...")
    create_db_and_tables()
    create_share_history_tables()
    logger.info("Database initialized.")
    init_admin_from_env()
    thread = threading.Thread(target=load_initial_data)
    thread.daemon = True
    thread.start()

    # 启动告警调度器
    alert_scheduler.start()
    logger.info("Alert scheduler started.")

    # 启动资金流向采集调度器
    fund_flow_collector.start()
    logger.info("Fund flow collector scheduler started.")

    yield

    # Shutdown
    alert_scheduler.stop()
    logger.info("Alert scheduler stopped.")
    fund_flow_collector.stop()
    logger.info("Fund flow collector scheduler stopped.")
    logger.info("Application shutting down...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# 注册速率限制器
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

# CORS Configuration - 环境感知
if settings.is_development:
    # 开发环境：启用 CORS（支持本地开发 + 局域网访问）
    # 匹配局域网 IP (192.168.x.x, 10.x.x.x, 172.16-31.x.x) 和常用端口
    allow_origin_regex = r"http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2[0-9]|3[0-1])\.\d+\.\d+):(3000|8000)"

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_origin_regex=allow_origin_regex
    )
    logger.info("✅ CORS enabled for development (local + LAN access)")
else:
    # 生产环境（Docker）：禁用 CORS
    # Nginx 反向代理确保同源，无需 CORS
    logger.info("✅ CORS disabled (production mode with Nginx reverse proxy)")

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {
        "message": "Welcome to ETFTool API",
        "version": settings.VERSION,
        "status": "ok"
    }

@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "ok",
        "version": settings.VERSION,
        "data_ready": etf_cache.is_initialized,
        "environment": settings.ENVIRONMENT
    }

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app", 
        host=settings.BACKEND_HOST, 
        port=settings.BACKEND_PORT, 
        reload=settings.is_development
    )
