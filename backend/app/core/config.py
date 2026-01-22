import os
from pydantic import BaseModel

class Settings(BaseModel):
    PROJECT_NAME: str = "ETFTool"
    API_V1_STR: str = "/api/v1"
    
    # 允许的前端来源
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ]

    class Config:
        case_sensitive = True

settings = Settings()
