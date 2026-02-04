# ETFTool 管理员系统设计文档

## 文档信息

- **创建日期**: 2026-02-04
- **版本**: v1.0
- **状态**: 设计中
- **作者**: Claude Sonnet 4.5

---

## 1. 背景与目标

### 1.1 背景

当前 ETFTool 已实现基础的用户认证系统（OAuth2 + JWT），支持用户注册、登录和个人设置管理。随着系统功能的扩展（如告警系统、监控指标等），需要引入管理员角色来控制特定权限，包括：

- 系统设置的访问和修改权限
- 监控信息的查看权限
- 用户管理权限
- 前端管理页面的访问控制

### 1.2 设计目标

1. **安全性优先**: 防止权限提升攻击，保护敏感操作
2. **简单实用**: 适合小型应用，避免过度设计
3. **渐进式部署**: 不影响现有用户系统，可逐步添加功能
4. **易于维护**: 清晰的权限模型，便于后续扩展

### 1.3 核心需求

| 需求 | 优先级 | 说明 |
|------|--------|------|
| 管理员角色定义 | P0 | 区分普通用户和管理员 |
| 首个管理员创建 | P0 | 安全的初始管理员创建方式 |
| 权限控制机制 | P0 | API 端点的权限验证 |
| 用户管理功能 | P1 | 管理员管理用户账户 |
| 系统设置控制 | P1 | 控制注册开关等全局设置 |
| 前端权限控制 | P1 | 管理员页面访问控制 |
| 操作审计日志 | P2 | 记录管理员关键操作 |

---

## 2. 现状分析

### 2.1 当前用户系统架构

**User 模型** (`backend/app/models/user.py`):
```python
class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

**认证流程**:
- OAuth2 Password Flow
- JWT Token 认证
- 密码哈希存储（bcrypt）

**现有端点**:
- `POST /api/v1/auth/register` - 用户注册
- `POST /api/v1/auth/token` - 用户登录
- `GET /api/v1/users/me` - 获取当前用户信息
- `PATCH /api/v1/users/me/settings` - 更新用户设置

### 2.2 存在的问题

| 问题 | 影响 | 优先级 |
|------|------|--------|
| 无角色区分 | 所有用户权限相同，无法保护敏感功能 | P0 |
| 注册无控制 | 任何人都可以注册，无法关闭注册 | P1 |
| 监控端点暴露 | 告警系统监控指标无访问控制 | P1 |
| 无用户管理 | 无法禁用用户或修改用户权限 | P1 |
| 缺少审计 | 无法追踪管理员操作 | P2 |

---

## 3. 设计方案

### 3.1 数据模型设计

#### 3.1.1 User 模型扩展

**方案对比**:

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| 布尔字段 `is_admin` | 简单直接，查询高效 | 不易扩展多角色 | 小型应用（推荐） |
| 字符串字段 `role` | 易于扩展角色 | 需要枚举验证 | 中型应用 |
| 独立角色表 | 灵活，支持多角色 | 复杂度高，查询慢 | 大型应用 |

**推荐方案**: 布尔字段 `is_admin`（当前需求简单，未来可迁移）

```python
# backend/app/models/user.py

class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # 新增字段
    is_admin: bool = Field(default=False, index=True)  # 管理员标识
    is_active: bool = Field(default=True, index=True)  # 账户激活状态
    updated_at: datetime = Field(default_factory=datetime.utcnow)  # 最后更新时间
```

**字段说明**:
- `is_admin`: 管理员标识，默认 False，添加索引提升查询性能
- `is_active`: 账户激活状态，允许管理员禁用用户而不删除数据
- `updated_at`: 记录最后更新时间，便于审计

#### 3.1.2 系统配置模型

```python
# backend/app/models/system_config.py (新文件)

from typing import Optional, Any
from datetime import datetime
from sqlmodel import Field, SQLModel, JSON

class SystemConfig(SQLModel, table=True):
    """系统配置表 - 存储全局设置"""
    __tablename__ = "system_config"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True, max_length=100)
    value: Any = Field(sa_type=JSON)  # JSON 格式存储
    description: Optional[str] = Field(default=None, max_length=500)
    updated_by: Optional[int] = Field(default=None, foreign_key="user.id")
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# 预定义配置键常量
class SystemConfigKeys:
    REGISTRATION_ENABLED = "registration_enabled"  # 注册开关
    MAX_WATCHLIST_ITEMS = "max_watchlist_items"    # 自选数量限制
    MAINTENANCE_MODE = "maintenance_mode"          # 维护模式
    ALERT_CHECK_ENABLED = "alert_check_enabled"    # 告警检查开关
```

**设计要点**:
- 使用 JSON 类型存储配置值，支持复杂数据结构
- 记录修改人和修改时间，便于审计
- 预定义配置键常量，避免硬编码

### 3.2 权限控制机制

#### 3.2.1 权限依赖函数

在 `backend/app/api/v1/endpoints/auth.py` 中添加权限验证依赖：

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

**依赖链**:
```
get_current_user (JWT验证)
    ↓
get_current_active_user (激活状态验证)
    ↓
get_current_admin_user (管理员权限验证)
```

#### 3.2.2 权限保护示例

```python
# 普通用户端点
@router.get("/users/me", response_model=UserRead)
def read_users_me(
    current_user: User = Depends(get_current_active_user)
):
    return current_user

# 管理员端点
@router.get("/admin/users", response_model=List[UserRead])
def list_all_users(
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin_user)
):
    return session.exec(select(User)).all()
```

### 3.3 首个管理员创建方案

#### 3.3.1 方案对比

| 方案 | 安全性 | 便利性 | 适用场景 | 推荐度 |
|------|--------|--------|----------|--------|
| 命令行脚本 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 服务器部署 | ✅ 推荐 |
| 环境变量初始化 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Docker 部署 | ✅ 推荐 |
| 首个注册用户 | ⭐⭐ | ⭐⭐⭐⭐⭐ | 个人使用 | ⚠️ 有风险 |
| API 端点创建 | ⭐ | ⭐⭐⭐ | - | ❌ 不推荐 |

**推荐方案**: 命令行脚本 + 环境变量初始化（双重保障）

#### 3.3.2 命令行脚本实现

```python
# backend/scripts/create_admin.py (新文件)

import sys
import getpass
from sqlmodel import Session, select
from app.core.database import engine
from app.models.user import User, UserCreate
from app.services.auth_service import AuthService

def create_admin():
    """创建管理员账户（交互式）"""
    print("=== ETFTool 管理员创建工具 ===\n")

    with Session(engine) as session:
        # 检查是否已有管理员
        statement = select(User).where(User.is_admin == True)
        existing_admins = session.exec(statement).all()

        if existing_admins:
            print(f"⚠️  当前已有 {len(existing_admins)} 个管理员:")
            for admin in existing_admins:
                print(f"   - {admin.username} (ID: {admin.id})")
            print()
            confirm = input("是否继续创建新管理员? (yes/no): ")
            if confirm.lower() != 'yes':
                print("操作已取消")
                return

        # 交互式输入
        print("\n请输入新管理员信息:")
        username = input("用户名: ").strip()

        if not username:
            print("❌ 用户名不能为空")
            sys.exit(1)

        # 检查用户名是否已存在
        existing_user = AuthService.get_user_by_username(session, username)
        if existing_user:
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

        # 创建管理员
        user_in = UserCreate(username=username, password=password)
        admin_user = AuthService.create_user(session, user_in)
        admin_user.is_admin = True
        session.add(admin_user)
        session.commit()

        print(f"\n✅ 管理员创建成功!")
        print(f"   用户名: {username}")
        print(f"   用户ID: {admin_user.id}")

if __name__ == "__main__":
    create_admin()
```

**使用方式**:
```bash
cd backend
python scripts/create_admin.py
```

#### 3.3.3 环境变量初始化

在应用启动时自动创建管理员（适合 Docker 部署）：

```python
# backend/app/core/init_admin.py (新文件)

import os
from sqlmodel import Session, select
from app.core.database import engine
from app.models.user import User, UserCreate
from app.services.auth_service import AuthService
import logging

logger = logging.getLogger(__name__)

def init_admin_from_env():
    """从环境变量初始化管理员账户"""
    admin_username = os.getenv("ADMIN_USERNAME")
    admin_password = os.getenv("ADMIN_PASSWORD")

    if not admin_username or not admin_password:
        logger.info("未设置 ADMIN_USERNAME 或 ADMIN_PASSWORD，跳过管理员初始化")
        return

    with Session(engine) as session:
        # 检查管理员是否已存在
        existing_user = AuthService.get_user_by_username(session, admin_username)

        if existing_user:
            if not existing_user.is_admin:
                # 用户存在但不是管理员，升级为管理员
                existing_user.is_admin = True
                session.add(existing_user)
                session.commit()
                logger.info(f"用户 '{admin_username}' 已升级为管理员")
            else:
                logger.info(f"管理员 '{admin_username}' 已存在")
            return

        # 创建新管理员
        user_in = UserCreate(username=admin_username, password=admin_password)
        admin_user = AuthService.create_user(session, user_in)
        admin_user.is_admin = True
        session.add(admin_user)
        session.commit()
        logger.info(f"管理员 '{admin_username}' 创建成功")
```

在 `backend/app/main.py` 的启动事件中调用：

```python
@app.on_event("startup")
async def startup_event():
    from app.core.init_admin import init_admin_from_env
    init_admin_from_env()
```

**Docker 环境变量配置**:
```yaml
# docker-compose.yml
services:
  backend:
    environment:
      - ADMIN_USERNAME=admin
      - ADMIN_PASSWORD=your_secure_password
```

### 3.4 系统配置服务

#### 3.4.1 配置服务实现

```python
# backend/app/services/system_config_service.py (新文件)

from typing import Any, Optional
from datetime import datetime
from sqlmodel import Session, select
from app.models.system_config import SystemConfig, SystemConfigKeys

class SystemConfigService:
    """系统配置服务"""

    @staticmethod
    def get_config(
        session: Session,
        key: str,
        default: Any = None
    ) -> Any:
        """获取系统配置"""
        statement = select(SystemConfig).where(SystemConfig.key == key)
        config = session.exec(statement).first()
        return config.value if config else default

    @staticmethod
    def set_config(
        session: Session,
        key: str,
        value: Any,
        user_id: int,
        description: Optional[str] = None
    ) -> SystemConfig:
        """设置系统配置"""
        statement = select(SystemConfig).where(SystemConfig.key == key)
        config = session.exec(statement).first()

        if config:
            config.value = value
            config.updated_by = user_id
            config.updated_at = datetime.utcnow()
            if description:
                config.description = description
        else:
            config = SystemConfig(
                key=key,
                value=value,
                updated_by=user_id,
                description=description
            )

        session.add(config)
        session.commit()
        session.refresh(config)
        return config

    @staticmethod
    def is_registration_enabled(session: Session) -> bool:
        """检查注册是否开放"""
        return SystemConfigService.get_config(
            session,
            SystemConfigKeys.REGISTRATION_ENABLED,
            default=True  # 默认开放
        )

    @staticmethod
    def get_max_watchlist_items(session: Session) -> int:
        """获取自选列表最大数量"""
        return SystemConfigService.get_config(
            session,
            SystemConfigKeys.MAX_WATCHLIST_ITEMS,
            default=100  # 默认 100
        )
```

#### 3.4.2 注册端点集成

修改 `backend/app/api/v1/endpoints/auth.py` 的注册端点：

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

### 3.5 管理员 API 端点

#### 3.5.1 用户管理端点

```python
# backend/app/api/v1/endpoints/admin.py (新文件)

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
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

    # 过滤条件
    if is_admin is not None:
        statement = statement.where(User.is_admin == is_admin)
    if is_active is not None:
        statement = statement.where(User.is_active == is_active)

    statement = statement.offset(skip).limit(limit)
    users = session.exec(statement).all()
    return users

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

    # 防止自己移除自己的管理员权限
    if user.id == admin.id:
        raise HTTPException(
            status_code=400,
            detail="Cannot modify your own admin status"
        )

    user.is_admin = not user.is_admin
    user.updated_at = datetime.utcnow()
    session.add(user)
    session.commit()

    return {
        "user_id": user.id,
        "username": user.username,
        "is_admin": user.is_admin,
        "message": f"User {'promoted to' if user.is_admin else 'demoted from'} admin"
    }

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

    # 防止禁用自己
    if user.id == admin.id:
        raise HTTPException(
            status_code=400,
            detail="Cannot disable your own account"
        )

    user.is_active = not user.is_active
    user.updated_at = datetime.utcnow()
    session.add(user)
    session.commit()

    return {
        "user_id": user.id,
        "username": user.username,
        "is_active": user.is_active,
        "message": f"User account {'activated' if user.is_active else 'deactivated'}"
    }
```

#### 3.5.2 系统配置管理端点

```python
# 继续在 backend/app/api/v1/endpoints/admin.py 中添加

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
        session,
        SystemConfigKeys.REGISTRATION_ENABLED,
        enabled,
        admin.id,
        description="用户注册开关"
    )
    return {
        "registration_enabled": enabled,
        "message": f"User registration {'enabled' if enabled else 'disabled'}"
    }

@router.post("/system/config/max-watchlist")
def set_max_watchlist(
    max_items: int = Query(..., ge=1, le=1000),
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin_user)
):
    """设置自选列表最大数量"""
    SystemConfigService.set_config(
        session,
        SystemConfigKeys.MAX_WATCHLIST_ITEMS,
        max_items,
        admin.id,
        description="自选列表最大数量限制"
    )
    return {
        "max_watchlist_items": max_items,
        "message": f"Max watchlist items set to {max_items}"
    }
```

#### 3.5.3 路由注册

在 `backend/app/api/v1/api.py` 中注册管理员路由：

```python
from app.api.v1.endpoints import admin

api_router.include_router(
    admin.router,
    prefix="/admin",
    tags=["admin"]
)
```

### 3.6 前端权限控制

#### 3.6.1 用户模型扩展

```typescript
// frontend/src/types/user.ts

export interface User {
  id: number;
  username: string;
  settings: Record<string, any>;
  created_at: string;
  is_admin: boolean;      // 新增
  is_active: boolean;     // 新增
}
```

#### 3.6.2 管理员路由守卫

```typescript
// frontend/src/middleware/adminGuard.ts (新文件)

import { User } from '@/types/user';

export function requireAdmin(user: User | null): void {
  if (!user) {
    throw new Error('Authentication required');
  }
  if (!user.is_admin) {
    throw new Error('Admin privileges required');
  }
}

export function isAdmin(user: User | null): boolean {
  return user?.is_admin === true;
}
```

#### 3.6.3 管理员页面示例

```typescript
// frontend/src/app/admin/page.tsx (新文件)

'use client';

import { useAuth } from '@/contexts/AuthContext';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { requireAdmin } from '@/middleware/adminGuard';

export default function AdminPage() {
  const { user } = useAuth();
  const router = useRouter();

  useEffect(() => {
    try {
      requireAdmin(user);
    } catch (error) {
      router.push('/');
    }
  }, [user, router]);

  if (!user?.is_admin) {
    return null;
  }

  return (
    <div className="container mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">管理员控制台</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* 用户管理 */}
        <div className="border rounded-lg p-4">
          <h2 className="text-xl font-semibold mb-4">用户管理</h2>
          {/* 用户列表组件 */}
        </div>

        {/* 系统设置 */}
        <div className="border rounded-lg p-4">
          <h2 className="text-xl font-semibold mb-4">系统设置</h2>
          {/* 系统配置组件 */}
        </div>

        {/* 监控指标 */}
        <div className="border rounded-lg p-4">
          <h2 className="text-xl font-semibold mb-4">系统监控</h2>
          {/* 监控指标组件 */}
        </div>
      </div>
    </div>
  );
}
```

#### 3.6.4 条件渲染管理员入口

```typescript
// frontend/src/components/Navigation.tsx

import { useAuth } from '@/contexts/AuthContext';
import { isAdmin } from '@/middleware/adminGuard';

export function Navigation() {
  const { user } = useAuth();

  return (
    <nav>
      {/* 普通导航项 */}
      <Link href="/search">搜索</Link>
      <Link href="/watchlist">自选</Link>
      <Link href="/settings">设置</Link>

      {/* 管理员入口 */}
      {isAdmin(user) && (
        <Link href="/admin" className="text-red-500">
          管理员
        </Link>
      )}
    </nav>
  );
}
```

### 3.7 数据库迁移

#### 3.7.1 迁移脚本

```python
# backend/scripts/migrate_add_admin_fields.py (新文件)

from sqlmodel import Session, text
from app.core.database import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    """添加管理员相关字段到 User 表"""
    logger.info("开始数据库迁移...")

    with Session(engine) as session:
        try:
            # 添加 is_admin 字段
            session.exec(text(
                "ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0"
            ))
            logger.info("✅ 添加 is_admin 字段")

            # 添加 is_active 字段
            session.exec(text(
                "ALTER TABLE user ADD COLUMN is_active BOOLEAN DEFAULT 1"
            ))
            logger.info("✅ 添加 is_active 字段")

            # 添加 updated_at 字段
            session.exec(text(
                "ALTER TABLE user ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ))
            logger.info("✅ 添加 updated_at 字段")

            # 创建索引
            session.exec(text(
                "CREATE INDEX idx_user_is_admin ON user(is_admin)"
            ))
            logger.info("✅ 创建 is_admin 索引")

            session.exec(text(
                "CREATE INDEX idx_user_is_active ON user(is_active)"
            ))
            logger.info("✅ 创建 is_active 索引")

            session.commit()
            logger.info("✅ 数据库迁移完成")

        except Exception as e:
            session.rollback()
            logger.error(f"❌ 迁移失败: {e}")
            raise

if __name__ == "__main__":
    migrate()
```

**使用方式**:
```bash
cd backend
python scripts/migrate_add_admin_fields.py
```

#### 3.7.2 创建 SystemConfig 表

```python
# backend/scripts/create_system_config_table.py (新文件)

from sqlmodel import SQLModel
from app.core.database import engine
from app.models.system_config import SystemConfig
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_table():
    """创建 SystemConfig 表"""
    logger.info("创建 system_config 表...")
    SystemConfig.metadata.create_all(engine)
    logger.info("✅ system_config 表创建完成")

if __name__ == "__main__":
    create_table()
```

---

## 4. 实施计划

### 4.1 Phase 1: 数据模型与迁移 (P0)

**目标**: 建立管理员系统的数据基础

| 任务 | 工作量 | 依赖 | 验收标准 |
|------|--------|------|----------|
| 扩展 User 模型 | 小 | 无 | 字段定义完成 |
| 创建 SystemConfig 模型 | 小 | 无 | 模型定义完成 |
| 编写数据库迁移脚本 | 小 | User 模型 | 迁移脚本可执行 |
| 执行数据库迁移 | 小 | 迁移脚本 | 数据库字段添加成功 |
| 创建 SystemConfig 表 | 小 | SystemConfig 模型 | 表创建成功 |

### 4.2 Phase 2: 权限控制与管理员创建 (P0)

**目标**: 实现基础的权限验证和管理员账户创建

| 任务 | 工作量 | 依赖 | 验收标准 |
|------|--------|------|----------|
| 实现权限依赖函数 | 小 | User 模型 | 依赖函数可用 |
| 编写管理员创建脚本 | 中 | User 模型 | 脚本可创建管理员 |
| 实现环境变量初始化 | 小 | User 模型 | 启动时自动创建管理员 |
| 创建首个管理员 | 小 | 创建脚本 | 管理员账户可用 |
| 测试权限验证 | 小 | 权限依赖 | 权限控制生效 |

### 4.3 Phase 3: 系统配置服务 (P1)

**目标**: 实现系统配置的管理功能

| 任务 | 工作量 | 依赖 | 验收标准 |
|------|--------|------|----------|
| 实现 SystemConfigService | 中 | SystemConfig 模型 | 服务可用 |
| 集成注册开关 | 小 | SystemConfigService | 注册可控制 |
| 测试配置服务 | 小 | SystemConfigService | 配置读写正常 |

### 4.4 Phase 4: 管理员 API 端点 (P1)

**目标**: 提供管理员操作的 API 接口

| 任务 | 工作量 | 依赖 | 验收标准 |
|------|--------|------|----------|
| 实现用户管理端点 | 中 | 权限依赖 | API 可用 |
| 实现系统配置端点 | 中 | SystemConfigService | API 可用 |
| 注册管理员路由 | 小 | 管理员端点 | 路由可访问 |
| API 测试 | 中 | 所有端点 | 所有端点测试通过 |

### 4.5 Phase 5: 前端集成 (P1)

**目标**: 实现前端的管理员功能

| 任务 | 工作量 | 依赖 | 验收标准 |
|------|--------|------|----------|
| 扩展用户类型定义 | 小 | 无 | 类型定义完成 |
| 实现权限守卫 | 小 | 用户类型 | 守卫可用 |
| 创建管理员页面 | 大 | 权限守卫 | 页面可访问 |
| 实现用户管理界面 | 大 | 管理员 API | 界面可用 |
| 实现系统设置界面 | 中 | 管理员 API | 界面可用 |
| 添加管理员入口 | 小 | 管理员页面 | 入口可见 |

---

## 5. 风险评估与缓解

### 5.1 安全风险

| 风险 | 影响 | 可能性 | 缓解措施 |
|------|------|--------|----------|
| 权限提升攻击 | 高 | 中 | 严格的权限验证，防止自我提权 |
| 管理员账户泄露 | 高 | 低 | 强密码策略，定期审查管理员列表 |
| 环境变量泄露 | 高 | 低 | 不在代码中硬编码，使用 .env 文件 |
| JWT Token 劫持 | 中 | 中 | HTTPS 传输，短期 Token 过期时间 |
| SQL 注入 | 高 | 低 | 使用 SQLModel ORM，参数化查询 |

### 5.2 操作风险

| 风险 | 影响 | 可能性 | 缓解措施 |
|------|------|--------|----------|
| 误删管理员账户 | 高 | 中 | 防止删除自己，至少保留一个管理员 |
| 误禁用所有用户 | 中 | 低 | 批量操作需要二次确认 |
| 配置错误导致服务不可用 | 高 | 中 | 配置变更前备份，提供回滚机制 |
| 数据库迁移失败 | 高 | 低 | 迁移前备份数据库，提供回滚脚本 |

### 5.3 技术风险

| 风险 | 影响 | 可能性 | 缓解措施 |
|------|------|--------|----------|
| 数据库字段冲突 | 中 | 低 | 迁移前检查字段是否存在 |
| 前后端类型不一致 | 低 | 中 | 使用 TypeScript，定义清晰的接口 |
| 性能下降 | 低 | 低 | 添加索引，优化查询 |
| 向后兼容性问题 | 中 | 低 | 新字段使用默认值，不影响现有用户 |

---

## 6. 安全建议

### 6.1 管理员账户安全

1. **强密码策略**
   - 管理员密码长度至少 12 位
   - 包含大小写字母、数字和特殊字符
   - 定期更换密码（建议 90 天）

2. **账户保护**
   - 永远不要通过 API 创建首个管理员
   - 使用命令行脚本或环境变量初始化
   - 定期审查管理员列表，移除不再需要的账户

3. **操作审计**
   - 记录所有管理员操作（可选 P2 功能）
   - 包括：用户管理、权限变更、系统配置修改
   - 保留审计日志至少 90 天

### 6.2 权限控制最佳实践

1. **最小权限原则**
   - 默认用户无特权
   - 管理员权限显式授予
   - 避免创建过多管理员账户

2. **防止权限提升**
   - 管理员不能修改自己的权限
   - 管理员不能禁用自己的账户
   - 至少保留一个活跃的管理员账户

3. **二次确认**
   - 敏感操作需要二次确认（前端实现）
   - 包括：禁用用户、修改权限、删除数据

### 6.3 部署安全

1. **环境变量保护**
   ```bash
   # .env 文件权限设置
   chmod 600 .env

   # 不要将 .env 文件提交到版本控制
   echo ".env" >> .gitignore
   ```

2. **HTTPS 强制**
   - 生产环境必须使用 HTTPS
   - 防止 Token 在传输过程中被窃取

3. **定期安全审查**
   - 每月审查管理员列表
   - 检查异常登录记录
   - 更新依赖包，修复安全漏洞

---

## 7. 总结

### 7.1 设计优势

1. **简单实用**
   - 使用布尔字段 `is_admin`，简单直接
   - 适合小型应用，避免过度设计
   - 易于理解和维护

2. **安全可靠**
   - 多重权限验证机制
   - 防止权限提升攻击
   - 命令行脚本创建管理员，避免 API 暴露

3. **渐进式部署**
   - 不影响现有用户系统
   - 可以逐步添加功能
   - 向后兼容，新字段使用默认值

4. **易于扩展**
   - 清晰的权限模型
   - 可以轻松添加新的管理员功能
   - 未来可以迁移到更复杂的角色系统

### 7.2 核心功能清单

- ✅ 管理员角色定义（`is_admin` 字段）
- ✅ 账户激活状态控制（`is_active` 字段）
- ✅ 权限验证依赖函数
- ✅ 命令行管理员创建脚本
- ✅ 环境变量初始化管理员
- ✅ 系统配置服务（注册开关等）
- ✅ 用户管理 API（列表、详情、权限切换、激活切换）
- ✅ 系统配置 API（注册开关、自选数量限制）
- ✅ 前端权限守卫
- ✅ 管理员页面框架
- ✅ 数据库迁移脚本

### 7.3 后续扩展方向

1. **操作审计日志** (P2)
   - 记录管理员的所有操作
   - 包括操作时间、操作人、操作内容
   - 提供审计日志查询接口

2. **更细粒度的权限控制** (P3)
   - 引入角色系统（超级管理员、普通管理员）
   - 权限分组（用户管理、系统配置、监控查看）
   - 基于资源的访问控制

3. **管理员通知系统** (P2)
   - 系统异常自动通知管理员
   - 重要操作通知（如新用户注册）
   - 定期报告（用户统计、系统健康）

4. **前端管理界面完善** (P1)
   - 用户列表分页和搜索
   - 系统配置可视化编辑
   - 监控指标图表展示

### 7.4 建议实施顺序

**立即实施** (P0):
1. 数据模型扩展和迁移
2. 权限控制机制
3. 管理员创建脚本

**短期实施** (P1):
1. 系统配置服务
2. 管理员 API 端点
3. 前端基础集成

**中期规划** (P2):
1. 操作审计日志
2. 管理员通知系统
3. 前端界面完善

---

## 附录

### A. 相关文件清单

#### A.1 后端文件

| 文件路径 | 说明 | 状态 |
|---------|------|------|
| `backend/app/models/user.py` | User 模型（需修改） | 现有 |
| `backend/app/models/system_config.py` | SystemConfig 模型（新建） | 新增 |
| `backend/app/api/v1/endpoints/auth.py` | 认证端点（需修改） | 现有 |
| `backend/app/api/v1/endpoints/admin.py` | 管理员端点（新建） | 新增 |
| `backend/app/services/system_config_service.py` | 系统配置服务（新建） | 新增 |
| `backend/app/core/init_admin.py` | 管理员初始化（新建） | 新增 |
| `backend/scripts/create_admin.py` | 管理员创建脚本（新建） | 新增 |
| `backend/scripts/migrate_add_admin_fields.py` | 数据库迁移脚本（新建） | 新增 |
| `backend/scripts/create_system_config_table.py` | 创建配置表脚本（新建） | 新增 |

#### A.2 前端文件

| 文件路径 | 说明 | 状态 |
|---------|------|------|
| `frontend/src/types/user.ts` | User 类型定义（需修改） | 现有 |
| `frontend/src/middleware/adminGuard.ts` | 权限守卫（新建） | 新增 |
| `frontend/src/app/admin/page.tsx` | 管理员页面（新建） | 新增 |
| `frontend/src/components/Navigation.tsx` | 导航组件（需修改） | 现有 |

### B. API 端点清单

#### B.1 用户管理端点

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/api/v1/admin/users` | 管理员 | 获取用户列表 |
| GET | `/api/v1/admin/users/{user_id}` | 管理员 | 获取用户详情 |
| POST | `/api/v1/admin/users/{user_id}/toggle-admin` | 管理员 | 切换管理员权限 |
| POST | `/api/v1/admin/users/{user_id}/toggle-active` | 管理员 | 启用/禁用用户 |

#### B.2 系统配置端点

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/api/v1/admin/system/config` | 管理员 | 获取系统配置 |
| POST | `/api/v1/admin/system/config/registration` | 管理员 | 开启/关闭注册 |
| POST | `/api/v1/admin/system/config/max-watchlist` | 管理员 | 设置自选数量限制 |

### C. 数据库表结构

#### C.1 User 表变更

```sql
-- 新增字段
ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0;
ALTER TABLE user ADD COLUMN is_active BOOLEAN DEFAULT 1;
ALTER TABLE user ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- 新增索引
CREATE INDEX idx_user_is_admin ON user(is_admin);
CREATE INDEX idx_user_is_active ON user(is_active);
```

#### C.2 SystemConfig 表结构

```sql
CREATE TABLE system_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key VARCHAR(100) UNIQUE NOT NULL,
    value JSON NOT NULL,
    description VARCHAR(500),
    updated_by INTEGER,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (updated_by) REFERENCES user(id)
);

CREATE INDEX idx_system_config_key ON system_config(key);
```

### D. 环境变量配置

```bash
# .env 文件示例

# 管理员初始化（可选）
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password_here

# JWT 配置（现有）
SECRET_KEY=your_secret_key_here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### E. 变更历史

| 版本 | 日期 | 说明 | 作者 |
|------|------|------|------|
| v1.0 | 2026-02-04 | 初始版本，完整的管理员系统设计 | Claude Sonnet 4.5 |

### F. 参考资料

1. **FastAPI 安全最佳实践**
   - https://fastapi.tiangolo.com/tutorial/security/

2. **OAuth2 with Password Flow**
   - https://fastapi.tiangolo.com/tutorial/security/simple-oauth2/

3. **SQLModel 文档**
   - https://sqlmodel.tiangolo.com/

4. **OWASP 权限管理指南**
   - https://owasp.org/www-project-web-security-testing-guide/

---

**文档结束**
