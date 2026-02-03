from fastapi import APIRouter
from app.api.v1.endpoints import etf, auth, users, watchlist, notifications

api_router = APIRouter()
api_router.include_router(etf.router, prefix="/etf", tags=["etf"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(watchlist.router, prefix="/watchlist", tags=["watchlist"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])

