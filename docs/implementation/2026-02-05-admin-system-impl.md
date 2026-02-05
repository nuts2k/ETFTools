# 管理员系统实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现管理员系统的 P0（数据模型、权限控制、管理员创建）和 P1（系统配置服务、管理员 API、前端集成）功能。

**Architecture:**
- 后端：扩展 User 模型添加 `is_admin`/`is_active` 字段，新建 SystemConfig 模型，实现权限依赖函数链，创建管理员 API 端点
- 前端：扩展 User 类型定义，实现权限守卫，创建管理员页面框架

**Tech Stack:** FastAPI, SQLModel, SQLite, Next.js, TypeScript, Tailwind CSS

**设计文档:** `docs/design/2026-02-04-admin-system-design.md`

---

## Phase 1: 数据模型与迁移 (P0)

### Task 1: 扩展 User 模型

**Files:**
- Modify: `backend/app/models/user.py:9-12`
- Create: `backend/tests/models/__init__.py`
- Create: `backend/tests/models/test_user_model.py`

**Step 1: 创建测试目录**

```bash
mkdir -p backend/tests/models
touch backend/tests/models/__init__.py
```

**Step 2: 写失败测试**

创建 `backend/tests/models/test_user_model.py`：

```python
import pytest
from datetime import datetime
from app.models.user import User

def test_user_has_admin_fields():
    """验证 User 模型包含管理员相关字段"""
    user = User(
        username="testuser",
        hashed_password="hashed",
        is_admin=True,
        is_active=False
    )
    assert user.is_admin is True
    assert user.is_active is False

def test_user_admin_defaults():
    """验证 User 模型默认值"""
    user = User(
        username="testuser",
        hashed_password="hashed"
    )
    assert user.is_admin is False
    assert user.is_active is True
    assert user.updated_at is not None
```

**Step 3: 运行测试验证失败**

Run: `cd backend && python -m pytest tests/models/test_user_model.py -v`
Expected: FAIL - `TypeError: User.__init__() got an unexpected keyword argument 'is_admin'`

**Step 4: 实现 User 模型扩展**

修改 `backend/app/models/user.py` 的 User 类，添加三个字段：

```python
class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    # 新增管理员相关字段
    is_admin: bool = Field(default=False, index=True)
    is_active: bool = Field(default=True, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

同时更新 `UserRead` 类：

```python
class UserRead(UserBase):
    id: int
    created_at: datetime
    is_admin: bool
    is_active: bool
```

**Step 5: 运行测试验证通过**

Run: `cd backend && python -m pytest tests/models/test_user_model.py -v`
Expected: PASS

**Step 6: 提交**

```bash
git add backend/app/models/user.py backend/tests/models/
git commit -m "feat(user): add admin and active fields to User model"
```

---

### Task 2: 创建 SystemConfig 模型

**Files:**
- Create: `backend/app/models/system_config.py`
- Create: `backend/tests/models/test_system_config_model.py`

**Step 1: 写失败测试**

创建 `backend/tests/models/test_system_config_model.py`：

```python
import pytest
from app.models.system_config import SystemConfig, SystemConfigKeys

def test_system_config_model():
    """验证 SystemConfig 模型结构"""
    config = SystemConfig(
        key="test_key",
        value={"enabled": True},
        description="Test config"
    )
    assert config.key == "test_key"
    assert config.value == {"enabled": True}

def test_system_config_keys():
    """验证预定义配置键常量"""
    assert SystemConfigKeys.REGISTRATION_ENABLED == "registration_enabled"
    assert SystemConfigKeys.MAX_WATCHLIST_ITEMS == "max_watchlist_items"
```

**Step 2: 运行测试验证失败**

Run: `cd backend && python -m pytest tests/models/test_system_config_model.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'app.models.system_config'`

**Step 3: 实现 SystemConfig 模型**

创建 `backend/app/models/system_config.py`：

```python
from typing import Optional, Any
from datetime import datetime
from sqlmodel import Field, SQLModel, JSON

class SystemConfig(SQLModel, table=True):
    """系统配置表 - 存储全局设置"""
    __tablename__ = "system_config"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True, max_length=100)
    value: Any = Field(sa_type=JSON)
    description: Optional[str] = Field(default=None, max_length=500)
    updated_by: Optional[int] = Field(default=None, foreign_key="user.id")
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class SystemConfigKeys:
    """预定义配置键常量"""
    REGISTRATION_ENABLED = "registration_enabled"
    MAX_WATCHLIST_ITEMS = "max_watchlist_items"
    MAINTENANCE_MODE = "maintenance_mode"
    ALERT_CHECK_ENABLED = "alert_check_enabled"
```

**Step 4: 运行测试验证通过**

Run: `cd backend && python -m pytest tests/models/test_system_config_model.py -v`
Expected: PASS

**Step 5: 提交**

```bash
git add backend/app/models/system_config.py backend/tests/models/test_system_config_model.py
git commit -m "feat(model): add SystemConfig model for global settings"
```

---

### Task 3: 创建数据库迁移脚本

**Files:**
- Create: `backend/scripts/migrate_add_admin_fields.py`

**Step 1: 创建迁移脚本**

创建 `backend/scripts/migrate_add_admin_fields.py`：

```python
"""
数据库迁移脚本：添加管理员相关字段到 User 表

使用方式：cd backend && python scripts/migrate_add_admin_fields.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, text
from app.core.database import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_column_exists(session: Session, table: str, column: str) -> bool:
    """检查列是否已存在"""
    result = session.exec(text(f"PRAGMA table_info({table})"))
    columns = [row[1] for row in result]
    return column in columns

def migrate():
    """添加管理员相关字段到 User 表"""
    logger.info("开始数据库迁移...")
    with Session(engine) as session:
        try:
            if not check_column_exists(session, "user", "is_admin"):
                session.exec(text("ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0"))
                logger.info("✅ 添加 is_admin 字段")
            else:
                logger.info("⏭️  is_admin 字段已存在")

            if not check_column_exists(session, "user", "is_active"):
                session.exec(text("ALTER TABLE user ADD COLUMN is_active BOOLEAN DEFAULT 1"))
                logger.info("✅ 添加 is_active 字段")
            else:
                logger.info("⏭️  is_active 字段已存在")

            if not check_column_exists(session, "user", "updated_at"):
                session.exec(text("ALTER TABLE user ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
                logger.info("✅ 添加 updated_at 字段")
            else:
                logger.info("⏭️  updated_at 字段已存在")

            session.commit()
            logger.info("✅ 数据库迁移完成")
        except Exception as e:
            session.rollback()
            logger.error(f"❌ 迁移失败: {e}")
            raise

if __name__ == "__main__":
    migrate()
```

**Step 2: 运行迁移脚本**

Run: `cd backend && python scripts/migrate_add_admin_fields.py`
Expected: 输出显示字段添加成功或已存在

**Step 3: 提交**

```bash
git add backend/scripts/migrate_add_admin_fields.py
git commit -m "feat(db): add migration script for admin fields"
```

---

## Phase 2: 权限控制与管理员创建 (P0)

### Task 4: 实现权限依赖函数

**Files:**
- Modify: `backend/app/api/v1/endpoints/auth.py:19-37`
- Create: `backend/tests/api/test_auth_dependencies.py`

**Step 1: 写失败测试**

创建 `backend/tests/api/test_auth_dependencies.py`：

```python
import pytest
from fastapi import HTTPException
from app.models.user import User

def test_get_current_active_user_disabled():
    """验证禁用用户被拒绝"""
    from app.api.v1.endpoints.auth import get_current_active_user
    user = User(username="test", hashed_password="hash", is_active=False)
    with pytest.raises(HTTPException) as exc_info:
        # 同步调用异步函数需要特殊处理，这里简化测试
        import asyncio
        asyncio.get_event_loop().run_until_complete(get_current_active_user(user))
    assert exc_info.value.status_code == 403

def test_get_current_admin_user_not_admin():
    """验证非管理员被拒绝"""
    from app.api.v1.endpoints.auth import get_current_admin_user
    user = User(username="test", hashed_password="hash", is_admin=False, is_active=True)
    with pytest.raises(HTTPException) as exc_info:
        import asyncio
        asyncio.get_event_loop().run_until_complete(get_current_admin_user(user))
    assert exc_info.value.status_code == 403
```

**Step 2: 运行测试验证失败**

Run: `cd backend && python -m pytest tests/api/test_auth_dependencies.py -v`
Expected: FAIL - `ImportError: cannot import name 'get_current_active_user'`

**Step 3: 实现权限依赖函数**

在 `backend/app/api/v1/endpoints/auth.py` 的 `get_current_user` 函数后添加：

```python
async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """验证用户是否激活"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    return current_user

async def get_current_admin_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """验证用户是否为管理员"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user
```

**Step 4: 运行测试验证通过**

Run: `cd backend && python -m pytest tests/api/test_auth_dependencies.py -v`
Expected: PASS

**Step 5: 提交**

```bash
git add backend/app/api/v1/endpoints/auth.py backend/tests/api/test_auth_dependencies.py
git commit -m "feat(auth): add permission dependency functions"
```

---

### Task 5: 创建管理员创建脚本

**Files:**
- Create: `backend/scripts/create_admin.py`

**Step 1: 创建脚本**

创建 `backend/scripts/create_admin.py`：

```python
"""
管理员创建脚本（交互式）

使用方式：cd backend && python scripts/create_admin.py
"""
import sys
import os
import getpass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select
from app.core.database import engine
from app.models.user import User, UserCreate
from app.services.auth_service import AuthService

def create_admin():
    print("=== ETFTool 管理员创建工具 ===\n")
    with Session(engine) as session:
        # 检查现有管理员
        existing = session.exec(select(User).where(User.is_admin == True)).all()
        if existing:
            print(f"⚠️  当前已有 {len(existing)} 个管理员:")
            for admin in existing:
                print(f"   - {admin.username} (ID: {admin.id})")
            confirm = input("\n是否继续创建? (yes/no): ")
            if confirm.lower() != 'yes':
                print("操作已取消")
                return

        username = input("\n用户名: ").strip()
        if not username:
            print("❌ 用户名不能为空")
            sys.exit(1)

        if AuthService.get_user_by_username(session, username):
            print(f"❌ 用户名 '{username}' 已存在")
            sys.exit(1)

        password = getpass.getpass("密码: ")
        password_confirm = getpass.getpass("确认密码: ")
        if password != password_confirm:
            print("❌ 密码不匹配")
            sys.exit(1)
        if len(password) < 6:
            print("❌ 密码长度至少 6 位")
            sys.exit(1)

        user_in = UserCreate(username=username, password=password)
        admin_user = AuthService.create_user(session, user_in)
        admin_user.is_admin = True
        session.add(admin_user)
        session.commit()
        print(f"\n✅ 管理员创建成功! 用户名: {username}, ID: {admin_user.id}")

if __name__ == "__main__":
    create_admin()
```

**Step 2: 测试脚本可执行**

Run: `cd backend && python -c "from scripts.create_admin import create_admin; print('Import OK')"`
Expected: `Import OK`

**Step 3: 提交**

```bash
git add backend/scripts/create_admin.py
git commit -m "feat(admin): add interactive admin creation script"
```

---

### Task 6: 实现环境变量初始化管理员

**Files:**
- Create: `backend/app/core/init_admin.py`
- Modify: `backend/app/main.py:32-45`

**Step 1: 创建初始化模块**

创建 `backend/app/core/init_admin.py`：

```python
"""从环境变量初始化管理员账户"""
import os
import logging
from sqlmodel import Session
from app.core.database import engine
from app.models.user import UserCreate
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

def init_admin_from_env():
    admin_username = os.getenv("ADMIN_USERNAME")
    admin_password = os.getenv("ADMIN_PASSWORD")
    if not admin_username or not admin_password:
        logger.info("未设置 ADMIN_USERNAME/ADMIN_PASSWORD，跳过管理员初始化")
        return

    with Session(engine) as session:
        existing = AuthService.get_user_by_username(session, admin_username)
        if existing:
            if not existing.is_admin:
                existing.is_admin = True
                session.add(existing)
                session.commit()
                logger.info(f"用户 '{admin_username}' 已升级为管理员")
            else:
                logger.info(f"管理员 '{admin_username}' 已存在")
            return

        user_in = UserCreate(username=admin_username, password=admin_password)
        admin_user = AuthService.create_user(session, user_in)
        admin_user.is_admin = True
        session.add(admin_user)
        session.commit()
        logger.info(f"管理员 '{admin_username}' 创建成功")
```

**Step 2: 集成到应用启动**

在 `backend/app/main.py` 的 lifespan 函数中，`create_db_and_tables()` 后添加：

```python
from app.core.init_admin import init_admin_from_env
init_admin_from_env()
```

**Step 3: 提交**

```bash
git add backend/app/core/init_admin.py backend/app/main.py
git commit -m "feat(admin): add env-based admin initialization on startup"
```

---

## Phase 3: 系统配置服务 (P1)

### Task 7: 实现 SystemConfigService

**Files:**
- Create: `backend/app/services/system_config_service.py`
- Create: `backend/tests/services/test_system_config_service.py`

**Step 1: 写失败测试**

创建 `backend/tests/services/test_system_config_service.py`：

```python
import pytest
from sqlmodel import Session, SQLModel, create_engine
from app.models.system_config import SystemConfig, SystemConfigKeys
from app.services.system_config_service import SystemConfigService

@pytest.fixture
def test_session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

def test_get_config_default(test_session):
    """测试获取不存在的配置返回默认值"""
    result = SystemConfigService.get_config(test_session, "nonexistent", default="default")
    assert result == "default"

def test_set_and_get_config(test_session):
    """测试设置和获取配置"""
    SystemConfigService.set_config(test_session, "test_key", {"enabled": True}, user_id=1)
    result = SystemConfigService.get_config(test_session, "test_key")
    assert result == {"enabled": True}

def test_is_registration_enabled_default(test_session):
    """测试注册开关默认值"""
    assert SystemConfigService.is_registration_enabled(test_session) is True
```

**Step 2: 运行测试验证失败**

Run: `cd backend && python -m pytest tests/services/test_system_config_service.py -v`
Expected: FAIL - `ModuleNotFoundError`

**Step 3: 实现 SystemConfigService**

创建 `backend/app/services/system_config_service.py`：

```python
from typing import Any, Optional
from datetime import datetime
from sqlmodel import Session, select
from app.models.system_config import SystemConfig, SystemConfigKeys

class SystemConfigService:
    @staticmethod
    def get_config(session: Session, key: str, default: Any = None) -> Any:
        config = session.exec(select(SystemConfig).where(SystemConfig.key == key)).first()
        return config.value if config else default

    @staticmethod
    def set_config(session: Session, key: str, value: Any, user_id: int, description: str = None) -> SystemConfig:
        config = session.exec(select(SystemConfig).where(SystemConfig.key == key)).first()
        if config:
            config.value = value
            config.updated_by = user_id
            config.updated_at = datetime.utcnow()
            if description:
                config.description = description
        else:
            config = SystemConfig(key=key, value=value, updated_by=user_id, description=description)
        session.add(config)
        session.commit()
        session.refresh(config)
        return config

    @staticmethod
    def is_registration_enabled(session: Session) -> bool:
        return SystemConfigService.get_config(session, SystemConfigKeys.REGISTRATION_ENABLED, default=True)

    @staticmethod
    def get_max_watchlist_items(session: Session) -> int:
        return SystemConfigService.get_config(session, SystemConfigKeys.MAX_WATCHLIST_ITEMS, default=100)
```

**Step 4: 运行测试验证通过**

Run: `cd backend && python -m pytest tests/services/test_system_config_service.py -v`
Expected: PASS

**Step 5: 提交**

```bash
git add backend/app/services/system_config_service.py backend/tests/services/test_system_config_service.py
git commit -m "feat(service): add SystemConfigService for global settings"
```

---

### Task 8: 集成注册开关到注册端点

**Files:**
- Modify: `backend/app/api/v1/endpoints/auth.py:39-49`

**Step 1: 修改注册端点**

在 `backend/app/api/v1/endpoints/auth.py` 的 `register` 函数开头添加注册开关检查：

```python
@router.post("/register", response_model=UserRead)
@limiter.limit("3/hour")
def register(
    request: Request,
    user_in: UserCreate,
    session: Session = Depends(get_session)
):
    # 检查注册是否开放
    from app.services.system_config_service import SystemConfigService
    if not SystemConfigService.is_registration_enabled(session):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User registration is currently disabled"
        )

    db_user = AuthService.get_user_by_username(session, user_in.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    return AuthService.create_user(session, user_in)
```

**Step 2: 提交**

```bash
git add backend/app/api/v1/endpoints/auth.py
git commit -m "feat(auth): integrate registration toggle into register endpoint"
```

---

## Phase 4: 管理员 API 端点 (P1)

### Task 9: 创建管理员用户管理端点

**Files:**
- Create: `backend/app/api/v1/endpoints/admin.py`
- Modify: `backend/app/api/v1/api.py`

**Step 1: 创建管理员端点文件**

创建 `backend/app/api/v1/endpoints/admin.py`：

```python
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select
from app.models.user import User, UserRead
from app.core.database import get_session
from app.api.v1.endpoints.auth import get_current_admin_user

router = APIRouter()

@router.get("/users", response_model=List[UserRead])
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    is_admin: Optional[bool] = Query(None),
    is_active: Optional[bool] = Query(None),
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin_user)
):
    """获取用户列表（仅管理员）"""
    statement = select(User)
    if is_admin is not None:
        statement = statement.where(User.is_admin == is_admin)
    if is_active is not None:
        statement = statement.where(User.is_active == is_active)
    return session.exec(statement.offset(skip).limit(limit)).all()

@router.get("/users/{user_id}", response_model=UserRead)
def get_user(
    user_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin_user)
):
    """获取用户详情（仅管理员）"""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
```

**Step 2: 注册路由**

在 `backend/app/api/v1/api.py` 添加：

```python
from app.api.v1.endpoints import admin
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
```

**Step 3: 提交**

```bash
git add backend/app/api/v1/endpoints/admin.py backend/app/api/v1/api.py
git commit -m "feat(admin): add user list and detail endpoints"
```

---

### Task 10: 添加用户权限切换端点

**Files:**
- Modify: `backend/app/api/v1/endpoints/admin.py`

**Step 1: 添加权限切换端点**

在 `backend/app/api/v1/endpoints/admin.py` 添加：

```python
@router.post("/users/{user_id}/toggle-admin")
def toggle_admin_status(
    user_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin_user)
):
    """切换用户管理员权限"""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot modify your own admin status")
    user.is_admin = not user.is_admin
    user.updated_at = datetime.utcnow()
    session.add(user)
    session.commit()
    return {"user_id": user.id, "is_admin": user.is_admin}

@router.post("/users/{user_id}/toggle-active")
def toggle_user_active(
    user_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin_user)
):
    """启用/禁用用户账户"""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot disable your own account")
    user.is_active = not user.is_active
    user.updated_at = datetime.utcnow()
    session.add(user)
    session.commit()
    return {"user_id": user.id, "is_active": user.is_active}
```

**Step 2: 提交**

```bash
git add backend/app/api/v1/endpoints/admin.py
git commit -m "feat(admin): add toggle-admin and toggle-active endpoints"
```

---

### Task 11: 添加系统配置管理端点

**Files:**
- Modify: `backend/app/api/v1/endpoints/admin.py`

**Step 1: 添加配置端点**

在 `backend/app/api/v1/endpoints/admin.py` 添加：

```python
from app.services.system_config_service import SystemConfigService
from app.models.system_config import SystemConfigKeys

@router.get("/system/config")
def get_system_config(
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin_user)
):
    """获取系统配置（仅管理员）"""
    return {
        "registration_enabled": SystemConfigService.is_registration_enabled(session),
        "max_watchlist_items": SystemConfigService.get_max_watchlist_items(session),
    }

@router.post("/system/config/registration")
def toggle_registration(
    enabled: bool,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin_user)
):
    """开启/关闭用户注册"""
    SystemConfigService.set_config(
        session, SystemConfigKeys.REGISTRATION_ENABLED, enabled, admin.id
    )
    return {"registration_enabled": enabled}

@router.post("/system/config/max-watchlist")
def set_max_watchlist(
    max_items: int = Query(..., ge=1, le=1000),
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin_user)
):
    """设置自选列表最大数量"""
    SystemConfigService.set_config(
        session, SystemConfigKeys.MAX_WATCHLIST_ITEMS, max_items, admin.id
    )
    return {"max_watchlist_items": max_items}
```

**Step 2: 提交**

```bash
git add backend/app/api/v1/endpoints/admin.py
git commit -m "feat(admin): add system config management endpoints"
```

---

## Phase 5: 前端集成 (P1)

### Task 12: 扩展前端 User 类型

**Files:**
- Modify: `frontend/lib/auth-context.tsx:7-10`

**Step 1: 更新 User 接口**

修改 `frontend/lib/auth-context.tsx` 中的 User 接口：

```typescript
interface User {
  id: number
  username: string
  settings: Record<string, any>
  is_admin: boolean
  is_active: boolean
}
```

**Step 2: 提交**

```bash
git add frontend/lib/auth-context.tsx
git commit -m "feat(frontend): extend User type with admin fields"
```

---

### Task 13: 创建权限守卫

**Files:**
- Create: `frontend/lib/admin-guard.ts`

**Step 1: 创建守卫文件**

创建 `frontend/lib/admin-guard.ts`：

```typescript
interface User {
  is_admin?: boolean
}

export function isAdmin(user: User | null): boolean {
  return user?.is_admin === true
}

export function requireAdmin(user: User | null): void {
  if (!user) {
    throw new Error('Authentication required')
  }
  if (!user.is_admin) {
    throw new Error('Admin privileges required')
  }
}
```

**Step 2: 提交**

```bash
git add frontend/lib/admin-guard.ts
git commit -m "feat(frontend): add admin guard utilities"
```

---

### Task 14: 创建管理员页面框架

**Files:**
- Create: `frontend/app/admin/page.tsx`

**Step 1: 创建管理员页面**

创建 `frontend/app/admin/page.tsx`：

```tsx
"use client"

import { useAuth } from "@/lib/auth-context"
import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"
import { isAdmin } from "@/lib/admin-guard"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Users, Settings, Shield } from "lucide-react"

export default function AdminPage() {
  const { user, isLoading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!isLoading && !isAdmin(user)) {
      router.push("/")
    }
  }, [user, isLoading, router])

  if (isLoading || !isAdmin(user)) {
    return null
  }

  return (
    <div className="container mx-auto p-4 pb-20">
      <h1 className="text-2xl font-bold mb-6 flex items-center gap-2">
        <Shield className="h-6 w-6" />
        管理员控制台
      </h1>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="h-5 w-5" />
              用户管理
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">管理用户账户和权限</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Settings className="h-5 w-5" />
              系统设置
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">配置系统全局设置</p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
```

**Step 2: 提交**

```bash
git add frontend/app/admin/page.tsx
git commit -m "feat(frontend): add admin page framework"
```

---

### Task 15: 添加管理员入口到设置页

**Files:**
- Modify: `frontend/app/settings/page.tsx`

**Step 1: 添加管理员入口**

在 `frontend/app/settings/page.tsx` 中，为管理员用户添加入口链接：

```tsx
// 在设置页面的适当位置添加（需要先导入）
import { isAdmin } from "@/lib/admin-guard"
import { Shield } from "lucide-react"

// 在 JSX 中添加条件渲染
{isAdmin(user) && (
  <Link href="/admin" className="flex items-center gap-3 p-4 rounded-lg border hover:bg-accent">
    <Shield className="h-5 w-5 text-red-500" />
    <div>
      <div className="font-medium">管理员控制台</div>
      <div className="text-sm text-muted-foreground">用户管理、系统设置</div>
    </div>
  </Link>
)}
```

**Step 2: 提交**

```bash
git add frontend/app/settings/page.tsx
git commit -m "feat(frontend): add admin entry in settings page"
```

---

## Phase 6: 文档更新

### Task 16: 更新 AGENTS.md 文档

**Files:**
- Modify: `AGENTS.md`

**Step 1: 更新 API 接口速查表**

在 `AGENTS.md` 第 6 节添加管理员 API：

```markdown
| `/admin/users` | GET | 获取用户列表（管理员） |
| `/admin/users/{id}` | GET | 获取用户详情（管理员） |
| `/admin/users/{id}/toggle-admin` | POST | 切换管理员权限 |
| `/admin/users/{id}/toggle-active` | POST | 启用/禁用用户 |
| `/admin/system/config` | GET | 获取系统配置 |
| `/admin/system/config/registration` | POST | 开关用户注册 |
```

**Step 2: 更新核心代码导航**

在第 5 节添加：

```markdown
| **管理员端点** | `backend/app/api/v1/endpoints/admin.py` | 用户管理、系统配置 |
| **系统配置** | `backend/app/services/system_config_service.py` | 全局配置服务 |
```

**Step 3: 提交**

```bash
git add AGENTS.md
git commit -m "docs: update AGENTS.md with admin API endpoints"
```

---

## 任务总结

| Phase | 任务数 | 说明 |
|-------|--------|------|
| Phase 1 | 3 | 数据模型与迁移 |
| Phase 2 | 3 | 权限控制与管理员创建 |
| Phase 3 | 2 | 系统配置服务 |
| Phase 4 | 3 | 管理员 API 端点 |
| Phase 5 | 4 | 前端集成 |
| Phase 6 | 1 | 文档更新 |

**总计: 16 个任务**

## 验证清单

完成所有任务后，执行以下验证：

1. **后端测试**: `cd backend && python -m pytest -v`
2. **前端构建**: `cd frontend && npm run build`
3. **迁移脚本**: `cd backend && python scripts/migrate_add_admin_fields.py`
4. **创建管理员**: `cd backend && python scripts/create_admin.py`
5. **API 测试**: 启动服务后测试 `/api/v1/admin/users` 端点

---

**文档创建日期**: 2026-02-05
**设计文档**: `docs/design/2026-02-04-admin-system-design.md`
