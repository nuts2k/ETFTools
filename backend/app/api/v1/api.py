from fastapi import APIRouter
from app.api.v1.endpoints import etf, auth, users, watchlist, notifications, alerts

api_router = APIRouter()
api_router.include_router(etf.router, prefix="/etf", tags=["etf"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(watchlist.router, prefix="/watchlist", tags=["watchlist"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])

