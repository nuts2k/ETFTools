from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import threading
import logging
import requests

from app.core.config import settings
from app.core.cache import etf_cache
from app.core.database import create_db_and_tables
from app.services.akshare_service import ak_service
from app.api.v1.api import api_router

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 禁用系统代理 - 解决 Surge 等代理软件导致的连接问题
# AkShare 使用 requests 库，需要 monkey patch 来禁用代理
_original_request = requests.Session.request

def _patched_request(self, method, url, **kwargs):
    # 强制不使用代理
    if 'proxies' not in kwargs:
        kwargs['proxies'] = {'http': None, 'https': None}
    return _original_request(self, method, url, **kwargs)

requests.Session.request = _patched_request
logger.info("System proxy disabled for requests library.")

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    status = "ready" if etf_cache.is_initialized else "initializing"
    return {
        "message": "Welcome to ETFTool API",
        "status": status,
        "cache_size": len(etf_cache.get_etf_list())
    }

@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "ok", 
        "data_ready": etf_cache.is_initialized
    }

