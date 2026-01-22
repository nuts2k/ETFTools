from fastapi import APIRouter
from app.api.v1.endpoints import etf

api_router = APIRouter()
api_router.include_router(etf.router, prefix="/etf", tags=["etf"])
