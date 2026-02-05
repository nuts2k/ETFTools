# 阶段一：安全加固详细设计

> **设计日期**: 2026-01-25  
> **目标**: 修复严重安全漏洞，建立安全配置基础设施  
> **优先级**: P0 - 立即执行  
> **预计工时**: 1-2 天

---

## 📋 目录

1. [设计背景](#设计背景)
2. [需求分析](#需求分析)
3. [技术设计](#技术设计)
4. [实施步骤](#实施步骤)
5. [验证清单](#验证清单)
6. [文件变更清单](#文件变更清单)

---

## 设计背景

### 问题现状

基于代码库质量分析，当前项目存在以下严重安全问题：

1. **SECRET_KEY 硬编码** (`backend/app/services/auth_service.py:10`)
   - 风险：JWT 可被伪造，用户会话可被劫持
   - 评级：🔴 CRITICAL

2. **CORS 配置过宽** (`backend/app/core/config.py:9`)
   - 当前：`["*"]` 允许所有来源
   - 风险：易受 CSRF 攻击
   - 评级：🔴 HIGH

3. **依赖声明不完整** (`pyproject.toml`)
   - 缺失：`pydantic-settings`, `bcrypt` 等包
   - 风险：部署失败，环境不一致
   - 评级：🟡 MEDIUM

4. **无速率限制**
   - 风险：易受 DDoS 和暴力破解攻击
   - 评级：🟡 MEDIUM

### 需求分析（头脑风暴结果）

通过与用户的讨论，明确了以下需求：

- **部署场景**: 本地开发为主，偶尔内网分享
- **局域网访问**: 需要支持手机/平板通过 192.168.x.x 访问
- **配置管理**: 使用 `.env` 文件 + Pydantic Settings
- **速率限制**: 关键端点优先（登录、注册），不影响开发体验
- **依赖管理**: 生成 `requirements.txt` 锁定版本

### 设计原则

1. **环境分离优先** - 通过环境变量区分开发/生产配置
2. **最小影响原则** - 改动集中在配置层，不修改业务逻辑
3. **渐进式防御** - 先保护关键端点，再逐步扩展
4. **开发友好** - 本地开发不受速率限制影响

---

## 需求分析

### 功能需求

| 需求 | 说明 | 优先级 |
|------|------|--------|
| FR1 | 支持通过环境变量配置 SECRET_KEY | P0 |
| FR2 | 支持本地访问（localhost + 127.0.0.1） | P0 |
| FR3 | 支持局域网 IP 访问（192.168.x.x） | P0 |
| FR4 | 为登录/注册端点添加速率限制 | P1 |
| FR5 | 为搜索端点添加速率限制 | P1 |
| FR6 | 提供配置模板和密钥生成工具 | P2 |

### 非功能需求

| 需求 | 说明 | 目标 |
|------|------|------|
| NFR1 | 配置验证 | 应用启动时检查必需配置，快速失败 |
| NFR2 | 环境一致性 | 通过 requirements.txt 确保部署环境一致 |
| NFR3 | 开发体验 | 开发环境可禁用速率限制，不影响调试 |
| NFR4 | 安全性提升 | 安全评分从 1/5 提升到 4/5 |

### 约束条件

- 不改变现有数据库结构
- 不影响前端代码（除 API 调用地址配置）
- 向后兼容现有功能
- 最小化第三方依赖引入

---

## 技术设计

### 架构变更

```
backend/
├── .env.example          # [新增] 环境变量模板
├── .env                  # [新增] 本地配置（git ignored）
├── requirements.txt      # [新增] 锁定依赖版本
├── scripts/
│   ├── generate_secret.py      # [新增] SECRET_KEY 生成工具
│   └── freeze_requirements.sh  # [新增] 依赖锁定脚本
├── app/
│   ├── core/
│   │   └── config.py     # [改进] 使用 Pydantic Settings
│   ├── middleware/
│   │   └── rate_limit.py # [新增] 速率限制中间件
│   ├── services/
│   │   └── auth_service.py # [改进] 移除硬编码 SECRET_KEY
│   ├── api/v1/endpoints/
│   │   ├── auth.py       # [改进] 应用速率限制
│   │   └── etf.py        # [改进] 应用速率限制
│   └── main.py           # [改进] CORS 配置和速率限制注册
```

---

### 设计 1: 环境变量管理

#### 1.1 配置文件 `.env.example`

```bash
# ============================================
# ETFTool 后端配置模板
# 使用说明: 复制此文件为 .env 并修改对应值
# ============================================

# 应用配置
PROJECT_NAME=ETFTool
API_V1_STR=/api/v1
ENVIRONMENT=development  # development | production

# 安全配置
# 生成新密钥: python scripts/generate_secret.py
SECRET_KEY=generate-a-random-secret-key-here-min-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080  # 7天

# CORS 配置
# 开发环境 - 支持本地和局域网访问
BACKEND_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
# 注意: 局域网 IP (192.168.x.x) 通过正则表达式自动支持

# 服务器配置
BACKEND_HOST=0.0.0.0  # 监听所有网卡，允许局域网访问
BACKEND_PORT=8000

# 数据库配置
DATABASE_URL=sqlite:///./etftool.db

# 缓存配置
CACHE_DIR=./cache
CACHE_TTL=3600

# 速率限制配置（可选）
ENABLE_RATE_LIMIT=false  # 开发环境建议 false，生产环境建议 true
```

#### 1.2 配置模型实现

**`backend/app/core/config.py`** (完整代码):

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Union
import os

class Settings(BaseSettings):
    """应用配置模型"""
    
    # 基础配置
    PROJECT_NAME: str = "ETFTool"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    
    # 安全配置
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080
    
    # CORS 配置
    BACKEND_CORS_ORIGINS: Union[str, List[str]]
    
    # 服务器配置
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    
    # 数据库配置
    DATABASE_URL: str = "sqlite:///./etftool.db"
    
    # 缓存配置
    CACHE_DIR: str = "./cache"
    CACHE_TTL: int = 3600
    
    # 速率限制配置
    ENABLE_RATE_LIMIT: bool = False
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )
    
    @property
    def is_development(self) -> bool:
        """判断是否为开发环境"""
        return self.ENVIRONMENT == "development"
    
    @property
    def cors_origins(self) -> List[str]:
        """处理 CORS 来源配置"""
        if isinstance(self.BACKEND_CORS_ORIGINS, str):
            if self.BACKEND_CORS_ORIGINS == "*":
                return ["*"]
            return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",")]
        return self.BACKEND_CORS_ORIGINS
    
    def validate_security_config(self) -> None:
        """启动时验证安全配置"""
        # SECRET_KEY 长度检查
        if len(self.SECRET_KEY) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        
        # CORS 安全检查
        if not self.is_development and "*" in self.cors_origins:
            raise ValueError("CORS cannot be '*' in production environment")
        
        if self.is_development and "*" in self.cors_origins:
            print("⚠️  WARNING: CORS set to '*' - convenient but not recommended")
        
        # 局域网访问提示
        if self.BACKEND_HOST == "0.0.0.0":
            print(f"ℹ️  Server listening on all interfaces (0.0.0.0:{self.BACKEND_PORT})")
            print(f"ℹ️  Accessible via LAN at http://<your-local-ip>:{self.BACKEND_PORT}")

# 创建全局配置实例并验证
settings = Settings()
settings.validate_security_config()
```

**设计要点**:
- ✅ 使用 `pydantic-settings` 自动从 `.env` 加载
- ✅ 支持类型验证和默认值
- ✅ 启动时验证配置有效性（快速失败）
- ✅ 区分开发/生产环境的安全策略

#### 1.3 密钥生成工具

**`backend/scripts/generate_secret.py`**:

```python
#!/usr/bin/env python3
"""生成安全的 SECRET_KEY"""

import secrets

if __name__ == "__main__":
    secret_key = secrets.token_urlsafe(32)
    print(f"SECRET_KEY={secret_key}")
    print("\n💡 将上面的内容添加到 .env 文件中")
```

**使用方式**:
```bash
python backend/scripts/generate_secret.py
# 复制输出到 .env 文件
```

---

### 设计 2: CORS 配置优化

#### 2.1 CORS 策略

**需求**: 支持本地开发 + 局域网访问，同时保持合理的安全性

**策略设计**:
- 明确列出：`localhost:3000`, `127.0.0.1:3000`
- 正则匹配：`192.168.x.x:3000` (局域网)
- 仅开发环境启用正则匹配
- 生产环境禁止 `*` 和正则匹配

#### 2.2 CORS 中间件实现

**`backend/app/main.py`** (CORS 相关部分):

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # 开发环境额外支持局域网 IP 正则匹配
    allow_origin_regex=r"http://(192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+):3000" if settings.is_development else None
)
```

**安全特性**:
- ✅ 明确的白名单（localhost + 127.0.0.1）
- ✅ 局域网支持通过正则（仅开发环境）
- ✅ 启用 `allow_credentials` 支持 Cookie
- ✅ 生产环境自动禁用宽松策略

#### 2.3 Uvicorn 服务器配置

**`backend/app/main.py`** (启动部分):

```python
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.BACKEND_HOST,  # 0.0.0.0 允许局域网访问
        port=settings.BACKEND_PORT,
        reload=settings.is_development
    )
```

---

### 设计 3: 认证服务安全加固

#### 3.1 移除硬编码密钥

**`backend/app/services/auth_service.py`** (修改部分):

```python
from typing import Optional
from datetime import datetime, timedelta, timezone
import bcrypt
from jose import jwt
from sqlmodel import Session, select
from app.models.user import User, UserCreate
from app.core.config import settings  # 导入配置

# ❌ 删除以下硬编码内容:
# SECRET_KEY = "your-secret-key-change-in-production"
# ALGORITHM = "HS256"
# ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

class AuthService:
    # ... verify_password 和 get_password_hash 保持不变 ...
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """创建 JWT 访问令牌"""
        to_encode = data.copy()
        
        # 计算过期时间（使用 timezone-aware datetime）
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES  # 从配置读取
            )
        
        to_encode.update({"exp": expire})
        
        # 使用配置中的密钥和算法
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,      # ✅ 从配置读取
            algorithm=settings.ALGORITHM  # ✅ 从配置读取
        )
        return encoded_jwt
    
    # ... 其他方法保持不变 ...
```

**关键变更**:
- ❌ 删除模块级别的 `SECRET_KEY` 等常量
- ✅ 从 `settings` 读取配置
- ✅ 使用 `datetime.now(timezone.utc)` 替代已废弃的 `utcnow()`

---

### 设计 4: 速率限制实现

#### 4.1 速率限制策略

**目标**: 保护关键端点，不影响开发体验

| 端点 | 限制规则 | 说明 |
|-----|---------|------|
| `/api/v1/auth/login` | 5次/分钟 | 防止暴力破解 |
| `/api/v1/auth/register` | 3次/小时 | 防止批量注册 |
| `/api/v1/etf/search` | 30次/分钟 | 防止接口滥用 |
| 其他端点 | 无限制 | 后续按需添加 |
| 开发环境 | 可禁用 | 通过 `ENABLE_RATE_LIMIT` 控制 |

#### 4.2 速率限制中间件

**`backend/app/middleware/rate_limit.py`** (新建文件):

```python
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from app.core.config import settings

# 创建限流器
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200/minute"] if settings.ENABLE_RATE_LIMIT else [],
    enabled=settings.ENABLE_RATE_LIMIT
)

# 自定义速率限制异常处理
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """速率限制触发时的响应"""
    return JSONResponse(
        status_code=429,
        content={
            "detail": "请求过于频繁，请稍后再试",
            "error": "rate_limit_exceeded",
            "retry_after": exc.detail  # 告知客户端何时可以重试
        }
    )
```

#### 4.3 应用到端点

**`backend/app/api/v1/endpoints/auth.py`** (修改):

```python
from fastapi import APIRouter, Depends, HTTPException, Request
from app.middleware.rate_limit import limiter

router = APIRouter()

@router.post("/login")
@limiter.limit("5/minute")  # 每分钟最多 5 次
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    # ... 现有登录逻辑 ...
    pass

@router.post("/register")
@limiter.limit("3/hour")  # 每小时最多 3 次
async def register(request: Request, user_in: UserCreate):
    # ... 现有注册逻辑 ...
    pass
```

**`backend/app/api/v1/endpoints/etf.py`** (修改):

```python
from app.middleware.rate_limit import limiter

@router.get("/search")
@limiter.limit("30/minute")  # 每分钟最多 30 次
async def search_etfs(request: Request, keyword: str):
    # ... 现有搜索逻辑 ...
    pass
```

#### 4.4 注册到主应用

**`backend/app/main.py`** (添加):

```python
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.middleware.rate_limit import limiter, rate_limit_handler

app = FastAPI(title=settings.PROJECT_NAME)
app.state.limiter = limiter

# 注册速率限制异常处理器
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
```

---

### 设计 5: 依赖管理

#### 5.1 完整依赖清单

**`backend/pyproject.toml`** (更新):

```toml
[project]
name = "etftool-backend"
version = "0.1.0"
description = "FastAPI backend for ETFTool"
requires-python = ">=3.9"
dependencies = [
    # Web 框架
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    
    # 数据源
    "akshare>=1.12.0,<2.0.0",  # 锁定大版本，API 变化频繁
    "pandas>=2.0.0",
    "numpy>=1.24.0",
    
    # 数据验证与配置
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",  # ✅ 新增
    "python-dotenv>=1.0.0",      # ✅ 新增
    
    # 缓存
    "cachetools>=5.3.0",
    "diskcache>=5.6.0",
    
    # 数据库
    "sqlmodel>=0.0.14",
    
    # 认证与安全
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
    "bcrypt>=4.1.0",             # ✅ 新增（passlib 依赖）
    "python-multipart>=0.0.6",
    
    # 速率限制
    "slowapi>=0.1.9",            # ✅ 新增
    
    # HTTP 客户端
    "requests>=2.31.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",         # ✅ 新增
    "pytest-asyncio>=0.21.0",    # ✅ 新增
    "ruff>=0.1.0",
    "mypy>=1.7.0",
    "httpx>=0.25.0",
    "ipython>=8.12.0",           # ✅ 新增
]

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[tool.ruff]
line-length = 88
target-version = "py39"

[tool.mypy]
strict = true
ignore_missing_imports = true
```

**变更说明**:
- ✅ 添加 `pydantic-settings` - 环境变量管理
- ✅ 添加 `python-dotenv` - .env 文件支持
- ✅ 添加 `bcrypt` - passlib 的依赖
- ✅ 添加 `slowapi` - 速率限制
- ✅ 为关键依赖（akshare）添加版本约束
- ✅ 添加测试相关依赖到 dev

#### 5.2 生成锁定版本

**`backend/scripts/freeze_requirements.sh`** (新建文件):

```bash
#!/bin/bash
# 生成锁定版本的 requirements.txt

set -e

echo "📦 正在生成 requirements.txt..."

# 切换到项目根目录
cd "$(dirname "$0")/.." || exit 1

# 检查是否在虚拟环境中
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "⚠️  警告: 未检测到虚拟环境，将创建临时环境"
    
    # 创建临时虚拟环境
    python3 -m venv .venv_temp
    source .venv_temp/bin/activate
    
    # 安装依赖
    pip install --upgrade pip
    pip install -e ".[dev]"
    
    # 生成 requirements.txt
    pip freeze > requirements.txt
    
    # 清理临时环境
    deactivate
    rm -rf .venv_temp
else
    echo "ℹ️  使用当前虚拟环境: $VIRTUAL_ENV"
    pip freeze > requirements.txt
fi

echo "✅ requirements.txt 已生成"
echo "📋 包含 $(wc -l < requirements.txt | tr -d ' ') 个依赖包"
```

**使用方式**:
```bash
chmod +x backend/scripts/freeze_requirements.sh
cd backend
./scripts/freeze_requirements.sh
```

---

## 实施步骤

### 准备工作

**检查点**:
- [ ] 确认当前在 `main` 分支或创建新的功能分支
- [ ] 备份现有数据库文件（如有重要数据）
- [ ] 停止正在运行的后端服务

### Step 1: 环境配置基础（15分钟）

```bash
# 1. 创建环境变量模板
# 2. 生成密钥工具
mkdir -p backend/scripts

# 3. 生成 SECRET_KEY
cd backend
python scripts/generate_secret.py
# 复制输出内容

# 4. 创建本地 .env
cp .env.example .env
# 编辑 .env，将生成的 SECRET_KEY 粘贴进去

# 5. 验证 .env 在 .gitignore 中
grep "backend/.env" ../.gitignore
```

### Step 2: 安装新依赖（10分钟）

```bash
cd backend

# 安装新依赖
pip install pydantic-settings python-dotenv slowapi

# 或者重新安装所有依赖
pip install -e .

# 验证安装
python -c "import pydantic_settings, dotenv, slowapi; print('✅ 所有依赖安装成功')"
```

### Step 3: 配置系统重构（20分钟）

```bash
# 1. 更新 config.py（参考设计 1.2 节）
# 2. 更新 auth_service.py（参考设计 3.1 节）

# 3. 验证配置加载
cd backend
python -c "from app.core.config import settings; print(f'Project: {settings.PROJECT_NAME}'); print(f'SECRET_KEY: {settings.SECRET_KEY[:10]}...')"
```

### Step 4: CORS 配置（10分钟）

```bash
# 更新 main.py 的 CORS 中间件（参考设计 2.2 节）
```

### Step 5: 速率限制（25分钟）

```bash
# 1. 创建中间件文件
mkdir -p backend/app/middleware
touch backend/app/middleware/__init__.py

# 2. 创建 rate_limit.py（参考设计 4.2 节）
# 3. 更新认证端点（参考设计 4.3 节）
# 4. 更新 ETF 端点
# 5. 注册到主应用
```

### Step 6: 依赖锁定（10分钟）

```bash
# 1. 更新 pyproject.toml（参考设计 5.1 节）
# 2. 创建 freeze_requirements.sh 脚本
chmod +x backend/scripts/freeze_requirements.sh

# 3. 生成 requirements.txt
cd backend
./scripts/freeze_requirements.sh
```

### Step 7: 测试验证（20分钟）

```bash
# 1. 启动后端服务
cd backend
python -m app.main

# 2. 测试配置加载
curl http://localhost:8000/docs

# 3. 测试 CORS
curl -H "Origin: http://localhost:3000" \
     -H "Access-Control-Request-Method: GET" \
     -X OPTIONS \
     http://localhost:8000/api/v1/etf/list \
     -v

# 4. 测试局域网访问
ifconfig | grep "inet " | grep -v 127.0.0.1
# 在其他设备访问 http://<your-ip>:8000/docs
```

---

## 验证清单

### 功能验证

- [ ] **配置加载**
  - [ ] `settings.SECRET_KEY` 从 .env 成功加载
  - [ ] `settings.is_development` 返回正确值
  - [ ] 配置验证在启动时执行

- [ ] **CORS 配置**
  - [ ] `http://localhost:3000` 允许访问
  - [ ] `http://127.0.0.1:3000` 允许访问
  - [ ] `http://192.168.x.x:3000` 允许访问（局域网）
  - [ ] 其他来源被拒绝

- [ ] **速率限制**
  - [ ] 登录端点 5 次/分钟生效（如果启用）
  - [ ] 注册端点 3 次/小时生效（如果启用）
  - [ ] 搜索端点 30 次/分钟生效（如果启用）
  - [ ] 开发环境可禁用（`ENABLE_RATE_LIMIT=false`）

- [ ] **认证功能**
  - [ ] JWT 生成使用新的 SECRET_KEY
  - [ ] 登录功能正常
  - [ ] 注册功能正常
  - [ ] Token 验证正常

- [ ] **局域网访问**
  - [ ] 后端监听 `0.0.0.0:8000`
  - [ ] 从其他设备可访问 `http://<ip>:8000/docs`
  - [ ] 前端可以调用后端 API

### 安全验证

- [ ] **密钥管理**
  - [ ] `auth_service.py` 中无硬编码 SECRET_KEY
  - [ ] `.env` 文件在 `.gitignore` 中
  - [ ] `.env.example` 不包含真实密钥
  - [ ] SECRET_KEY 长度 >= 32 字符

- [ ] **CORS 安全**
  - [ ] 生产环境不允许 `*`（已验证会抛异常）
  - [ ] 开发环境有警告提示
  - [ ] `allow_credentials=True` 与明确的 origins 配合

- [ ] **依赖安全**
  - [ ] 所有使用的包已声明在 `pyproject.toml`
  - [ ] `requirements.txt` 锁定版本
  - [ ] 无已知安全漏洞

---

## 预期改进效果

### 安全指标

| 指标 | 改进前 | 改进后 | 提升 |
|-----|-------|-------|------|
| **安全评分** | ⭐ (1/5) | ⭐⭐⭐⭐ (4/5) | +300% |
| SECRET_KEY 管理 | 硬编码 | 环境变量 | ✅ 已解决 |
| CORS 配置 | `["*"]` | 白名单+正则 | ✅ 已改进 |
| 依赖管理 | 缺失 | 全部声明 | ✅ 已修复 |
| 速率限制 | 无 | 关键端点已保护 | ✅ 已添加 |
| 配置验证 | 无 | 启动时检查 | ✅ 已实现 |

### 安全风险变化

| 风险类型 | 改进前等级 | 改进后等级 | 说明 |
|---------|----------|-----------|------|
| JWT 伪造 | 🔴 CRITICAL | 🟢 LOW | SECRET_KEY 可定期更换 |
| CSRF 攻击 | 🔴 HIGH | 🟡 MEDIUM | CORS 已限制 |
| 暴力破解 | 🟡 MEDIUM | 🟢 LOW | 登录端点已限流 |
| 部署失败 | 🟡 MEDIUM | 🟢 LOW | 依赖明确，版本锁定 |
| 配置错误 | 🟡 MEDIUM | 🟢 LOW | 启动时验证 |

---

## 文件变更清单

### 新增文件

- `backend/.env.example` - 环境变量模板
- `backend/.env` - 本地配置（git ignore）
- `backend/scripts/generate_secret.py` - 密钥生成工具
- `backend/scripts/freeze_requirements.sh` - 依赖锁定脚本
- `backend/app/middleware/__init__.py` - 中间件包初始化
- `backend/app/middleware/rate_limit.py` - 速率限制中间件
- `backend/requirements.txt` - 锁定依赖版本

### 修改文件

- `backend/app/core/config.py` - 配置系统重构
- `backend/app/services/auth_service.py` - 移除硬编码密钥
- `backend/app/main.py` - CORS 和速率限制配置
- `backend/pyproject.toml` - 添加新依赖
- `backend/app/api/v1/endpoints/auth.py` - 添加速率限制装饰器
- `backend/app/api/v1/endpoints/etf.py` - 添加速率限制装饰器

### 无需修改

- `backend/.gitignore` - 已包含 `.env` 配置
- `frontend/` - 前端代码（本阶段不涉及）
- 数据库模型 - 无需变更
- 业务逻辑 - 无需变更

---

## 故障排查

### 常见问题

**Q1: 启动时报错 `ValidationError: SECRET_KEY field required`**
```bash
# 原因: .env 文件不存在或 SECRET_KEY 未设置
# 解决:
cp backend/.env.example backend/.env
python backend/scripts/generate_secret.py
# 将输出添加到 .env
```

**Q2: CORS 错误，前端无法访问后端**
```bash
# 检查 CORS 配置
python -c "from app.core.config import settings; print(settings.cors_origins)"

# 检查前端请求的 Origin 头
# 确保在允许列表中或匹配正则表达式
```

**Q3: 速率限制未生效**
```bash
# 检查配置
python -c "from app.core.config import settings; print(settings.ENABLE_RATE_LIMIT)"

# 确认 limiter 已注册
python -c "from app.middleware.rate_limit import limiter; print(limiter.enabled)"
```

**Q4: 局域网无法访问**
```bash
# 确认后端监听 0.0.0.0
python -c "from app.core.config import settings; print(settings.BACKEND_HOST)"

# 获取本机 IP
ifconfig | grep "inet " | grep -v 127.0.0.1
```

---

## 成功标准

完成阶段一后，应满足以下所有条件：

1. ✅ **零硬编码密钥** - 代码库中无敏感信息
2. ✅ **配置验证通过** - 启动时自动检查配置有效性
3. ✅ **CORS 正确配置** - 支持本地和局域网，拒绝其他来源
4. ✅ **速率限制生效** - 关键端点有保护（可选启用）
5. ✅ **依赖完整** - 所有使用的包已声明且锁定版本
6. ✅ **功能无退化** - 所有现有功能正常工作
7. ✅ **安全评分达标** - 从 1/5 提升到 4/5

---

**设计文档版本**: 1.0  
**最后更新**: 2026-01-25  
**审核状态**: 已通过头脑风暴审核  
**实施状态**: 待实施
