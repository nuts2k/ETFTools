from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlmodel import Field, SQLModel, JSON

class UserBase(SQLModel):
    username: str = Field(index=True, unique=True)
    settings: Dict[str, Any] = Field(default_factory=dict, sa_type=JSON)

class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_admin: bool = Field(default=False, index=True)
    is_active: bool = Field(default=True, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class UserCreate(UserBase):
    password: str

class UserPasswordUpdate(SQLModel):
    old_password: str
    new_password: str

class UserRead(UserBase):
    id: int
    created_at: datetime
    is_admin: bool
    is_active: bool

class Watchlist(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    etf_code: str = Field(index=True)
    name: Optional[str] = Field(default=None)
    sort_order: int = Field(default=0, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
