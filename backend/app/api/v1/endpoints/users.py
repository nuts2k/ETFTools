from typing import Dict, Any
from fastapi import APIRouter, Depends, Body
from sqlmodel import Session
from app.core.database import get_session
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User, UserRead

router = APIRouter()

@router.get("/me", response_model=UserRead)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.patch("/me/settings", response_model=UserRead)
def update_user_settings(
    settings: Dict[str, Any] = Body(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # Update settings dictionary
    current_settings = current_user.settings or {}
    updated_settings = {**current_settings, **settings}
    
    current_user.settings = updated_settings
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user
