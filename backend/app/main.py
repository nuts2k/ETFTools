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
from app.services.akshare_service import ak_service
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
    logger.info("Database initialized.")
    thread = threading.Thread(target=load_initial_data)
    thread.daemon = True
    thread.start()
    
    yield
    
    # Shutdown
    logger.info("Application shutting down...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# 注册速率限制器
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

# CORS Configuration
# 支持局域网访问（仅开发环境支持正则匹配）
allow_origin_regex = None
if settings.is_development:
    # 匹配局域网 IP (192.168.x.x, 10.x.x.x, 172.16-31.x.x) 和常用端口
    allow_origin_regex = r"http://(192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2[0-9]|3[0-1])\.\d+\.\d+):(3000|8000)"

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_origin_regex=allow_origin_regex
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    status = "ready" if etf_cache.is_initialized else "initializing"
    return {
        "message": "Welcome to ETFTool API",
        "status": status,
        "cache_size": len(etf_cache.get_etf_list()),
        "environment": settings.ENVIRONMENT
    }

@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "ok", 
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
