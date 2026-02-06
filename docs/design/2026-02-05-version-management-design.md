# ETFTool 版本管理系统设计文档

## 文档信息

- **创建日期**: 2026-02-05
- **版本**: v1.0
- **状态**: 设计完成
- **作者**: Claude Sonnet 4.5

---

## 1. 背景与目标

### 1.1 背景

当前 ETFTool 应用缺乏统一的版本管理机制，存在以下问题：

- 版本号分散在多个文件中（`frontend/package.json`, `backend/pyproject.toml`）
- 前端设置页面硬编码版本号（`v0.1.0`）
- 后端 API 未暴露版本信息
- Docker 镜像构建未注入版本
- 无法追踪应用版本与代码变更的对应关系

随着应用功能的扩展和部署需求的增加，需要建立规范的版本管理体系。

### 1.2 设计目标

1. **单一数据源**: 建立版本号的唯一来源，避免多处维护导致不一致
2. **自动化**: 版本提取和注入过程自动化，减少人工错误
3. **可追溯**: 版本号与 Git 提交历史关联，便于问题定位
4. **标准化**: 遵循语义化版本规范（Semantic Versioning 2.0.0）
5. **易用性**: 提供简单的版本升级工具，降低发布复杂度

### 1.3 核心需求

| 需求 | 优先级 | 说明 |
|------|--------|------|
| 版本提取机制 | P0 | 从 Git 标签自动提取版本号 |
| 后端版本暴露 | P0 | API 端点返回版本信息 |
| 前端版本显示 | P0 | 动态获取并显示版本号 |
| Docker 版本注入 | P0 | 构建时注入版本到镜像 |
| CI/CD 集成 | P0 | GitHub Actions 自动化版本处理 |
| 版本升级工具 | P1 | 简化版本升级流程的脚本 |
| 版本管理文档 | P1 | 开发者指南和最佳实践 |

---

## 2. 现状分析

### 2.1 当前版本配置

**Frontend (Next.js)**
- 位置: `frontend/package.json`
- 当前版本: `0.1.0`
- 状态: 未被使用，仅作为 npm 包元数据

**Backend (FastAPI)**
- 位置: `backend/pyproject.toml`
- 当前版本: `0.1.0`
- 状态: 未被使用，仅作为 Python 包元数据

**Settings 页面**
- 位置: `frontend/app/settings/page.tsx` (line 233)
- 显示: `ETFTool v0.1.0 • Designed for Simplicity`
- 状态: 硬编码，需手动更新

### 2.2 存在的问题

| 问题 | 影响 | 优先级 |
|------|------|--------|
| 版本号分散 | 多处维护，容易不一致 | P0 |
| 硬编码版本 | 发布时容易遗漏更新 | P0 |
| 无 API 版本 | 无法通过接口查询版本 | P0 |
| Docker 无版本 | 无法识别镜像对应的代码版本 | P0 |
| 无版本工具 | 手动升级版本容易出错 | P1 |

### 2.3 现有基础设施

**优势**:
- ✅ GitHub Actions 工作流已支持语义化版本标签（`v*.*.*`）
- ✅ Docker 多平台构建流程完善
- ✅ 后端配置系统支持环境变量
- ✅ 前端支持构建时环境变量注入

**待完善**:
- ❌ 无版本提取脚本
- ❌ 后端配置未定义 VERSION 字段
- ❌ Health 端点未返回版本信息
- ❌ Dockerfile 未定义版本构建参数

---

## 3. 设计方案

### 3.1 版本管理策略对比

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **Git 标签** | 不可变、CI/CD 原生支持、与代码绑定 | 本地开发需回退机制 | 推荐（行业标准） |
| VERSION 文件 | 简单直观、易于读取 | 需手动维护、易遗忘 | 小型项目 |
| package.json | 前端原生支持 | 前后端需同步、易不一致 | 纯前端项目 |

**推荐方案**: **Git 标签作为单一数据源**

**理由**:
1. Git 标签不可变，与特定 commit 绑定，可追溯性强
2. GitHub Actions 可直接提取标签，无需额外配置
3. 自然集成 GitHub Releases，便于发布管理
4. 避免手动同步多个文件，减少人为错误
5. 行业标准做法（Kubernetes、Docker、Go 等项目）

### 3.2 语义化版本规范

采用 **Semantic Versioning 2.0.0** 标准：`MAJOR.MINOR.PATCH`

**版本升级规则**:

| 类型 | 场景 | 示例 |
|------|------|------|
| **MAJOR** | 不兼容的 API 变更、数据库迁移、架构重构 | `1.0.0` → `2.0.0` |
| **MINOR** | 新功能、新 API 端点、性能改进 | `1.0.0` → `1.1.0` |
| **PATCH** | Bug 修复、安全补丁、文档更新 | `1.0.0` → `1.0.1` |

**预发布版本**:
- **Alpha**: `v1.2.3-alpha.1` - 内部测试，不稳定
- **Beta**: `v1.2.3-beta.1` - 功能完整，公开测试
- **RC**: `v1.2.3-rc.1` - 发布候选，最终测试

### 3.3 版本提取机制

**核心逻辑** (`scripts/get_version.sh`):

```bash
#!/bin/bash
# 1. 如果在标签上 → 使用标签版本（如 v1.2.3）
if git describe --tags --exact-match 2>/dev/null; then
    VERSION=$(git describe --tags --exact-match)
# 2. 如果不在标签上 → 使用 git describe（如 v1.2.3-5-g1234abc）
elif git describe --tags 2>/dev/null; then
    VERSION=$(git describe --tags --always)
# 3. 如果无标签 → 使用 dev-{commit-hash}
else
    VERSION="dev-$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
fi
# 移除 'v' 前缀
VERSION=${VERSION#v}
echo "$VERSION"
```

**版本格式示例**:
- 标签发布: `1.2.3`
- 开发版本: `1.2.3-5-g1234abc` (距离标签 5 个提交)
- 无标签: `dev-a1b2c3d`

### 3.4 系统架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                     Git Repository                          │
│                   (Single Source of Truth)                  │
│                     Tags: v1.0.0, v1.1.0                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ├─────────────────┬─────────────────┐
                         ▼                 ▼                 ▼
              ┌──────────────────┐  ┌──────────────┐  ┌──────────────┐
              │  Local Dev       │  │  Docker      │  │  CI/CD       │
              │  (manage.sh)     │  │  Build       │  │  (GitHub)    │
              └────────┬─────────┘  └──────┬───────┘  └──────┬───────┘
                       │                   │                  │
                       │ get_version.sh    │ Build Arg        │ Extract Tag
                       ▼                   ▼                  ▼
              ┌──────────────────┐  ┌──────────────┐  ┌──────────────┐
              │  APP_VERSION     │  │  APP_VERSION │  │  APP_VERSION │
              │  (env var)       │  │  (env var)   │  │  (build arg) │
              └────────┬─────────┘  └──────┬───────┘  └──────┬───────┘
                       │                   │                  │
                       └───────────────────┴──────────────────┘
                                           │
                       ┌───────────────────┴───────────────────┐
                       ▼                                       ▼
              ┌──────────────────┐                   ┌──────────────────┐
              │  Backend         │                   │  Frontend        │
              │  config.VERSION  │◄──────────────────│  getVersion()    │
              │  /api/v1/health  │      API Call     │  Settings Page   │
              └──────────────────┘                   └──────────────────┘
```

---

## 4. 详细设计

### 4.1 后端集成

#### 4.1.1 配置模型扩展

**文件**: `backend/app/core/config.py`

```python
class Settings(BaseSettings):
    """应用配置模型"""

    # 基础配置
    PROJECT_NAME: str = "ETFTool"
    VERSION: str = os.getenv("APP_VERSION", "dev")  # 新增
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    # ... 其他配置
```

**说明**:
- 从环境变量 `APP_VERSION` 读取版本
- 默认值为 `"dev"`，适用于未设置环境变量的场景
- 全局单例，所有模块可访问

#### 4.1.2 API 端点更新

**文件**: `backend/app/main.py`

**Health 端点**:
```python
@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "ok",
        "version": settings.VERSION,  # 新增
        "data_ready": etf_cache.is_initialized,
        "environment": settings.ENVIRONMENT
    }
```

**Root 端点**:
```python
@app.get("/")
async def root():
    status = "ready" if etf_cache.is_initialized else "initializing"
    return {
        "message": "Welcome to ETFTool API",
        "version": settings.VERSION,  # 新增
        "status": status,
        "cache_size": len(etf_cache.get_etf_list()),
        "environment": settings.ENVIRONMENT
    }
```

### 4.2 前端集成

#### 4.2.1 Settings 页面版本显示

**文件**: `frontend/app/settings/page.tsx`

```typescript
export default function SettingsPage() {
  // ... 其他代码

  return (
    <div>
      {/* ... 其他内容 */}
      <div className="py-8 text-center">
        <p className="text-xs text-muted-foreground/50">
          ETFTool v{process.env.NEXT_PUBLIC_APP_VERSION || "dev"} • Designed for Simplicity
        </p>
      </div>
    </div>
  );
}
```

**说明**:
- 直接读取构建时注入的环境变量 `NEXT_PUBLIC_APP_VERSION`，无需异步请求
- Next.js 在构建时将 `NEXT_PUBLIC_*` 变量内联为字符串字面量，版本号同步可用，无闪烁
- 未设置环境变量时回退显示 `"dev"`

### 4.3 Docker 集成

#### 4.3.1 Dockerfile 更新

**文件**: `Dockerfile`

```dockerfile
# 定义构建参数（顶部）
ARG APP_VERSION=dev

# Stage 1: Frontend Builder
FROM node:20-alpine AS frontend-builder
ARG APP_VERSION
ENV NEXT_PUBLIC_APP_VERSION=${APP_VERSION}
# ... 构建步骤

# Stage 3: Runtime Environment
FROM python:3.11-slim
ARG APP_VERSION
ENV APP_VERSION=${APP_VERSION}
ENV ENVIRONMENT=production
# ... 运行时配置
```

**说明**:
- `ARG APP_VERSION=dev`: 定义构建参数，默认值 `dev`
- Frontend: 通过 `NEXT_PUBLIC_APP_VERSION` 注入到构建产物
- Backend: 通过 `APP_VERSION` 环境变量在运行时读取

#### 4.3.2 Entrypoint 脚本更新

**文件**: `docker/entrypoint.sh`

```bash
#!/bin/bash
echo -e "${BLUE}[ETFTool]${NC} 容器启动中..."
echo -e "${BLUE}[ETFTool]${NC} 版本: ${APP_VERSION:-unknown}"
echo -e "${BLUE}[ETFTool]${NC} 环境: ${ENVIRONMENT}"
# ... 其他启动逻辑
```

### 4.4 CI/CD 集成

#### 4.4.1 GitHub Actions 工作流

**文件**: `.github/workflows/docker-build.yml`

**新增步骤**:
```yaml
- name: Extract version from git
  id: version
  run: |
    if [[ "${{ github.ref }}" == refs/tags/v* ]]; then
      # 标签发布: 使用标签版本（移除 'v' 前缀）
      VERSION=${GITHUB_REF#refs/tags/v}
    elif [[ "${{ github.ref }}" == refs/heads/main ]]; then
      # Main 分支: 使用 main-{hash}
      VERSION="main-$(git rev-parse --short HEAD)"
    else
      # 其他分支: 使用 {branch}-{hash}
      VERSION="${GITHUB_REF_NAME}-$(git rev-parse --short HEAD)"
    fi
    echo "version=$VERSION" >> $GITHUB_OUTPUT
    echo "Version: $VERSION"
```

**更新构建步骤**:
```yaml
- name: Build and push Docker image
  uses: docker/build-push-action@v5
  with:
    context: .
    file: ./Dockerfile
    platforms: linux/amd64,linux/arm64
    push: ${{ github.event_name != 'pull_request' }}
    tags: ${{ steps.meta.outputs.tags }}
    labels: ${{ steps.meta.outputs.labels }}
    build-args: |
      BUILDKIT_INLINE_CACHE=1
      APP_VERSION=${{ steps.version.outputs.version }}
```

### 4.5 开发者工具

#### 4.5.1 版本升级脚本

**文件**: `scripts/bump_version.sh` (新建)

**功能**:
1. 读取当前最新 Git 标签
2. 根据参数升级版本（major/minor/patch）
3. 更新 CHANGELOG.md
4. 创建新的 Git 标签
5. 提示后续操作

**用法**:
```bash
./scripts/bump_version.sh patch  # 0.1.0 → 0.1.1
./scripts/bump_version.sh minor  # 0.1.1 → 0.2.0
./scripts/bump_version.sh major  # 0.2.0 → 1.0.0
```

#### 4.5.2 本地开发脚本更新

**文件**: `manage.sh`

**新增逻辑**:
```bash
# 提取版本
if [ -f "$SCRIPT_DIR/scripts/get_version.sh" ]; then
    VERSION=$("$SCRIPT_DIR/scripts/get_version.sh")
    export APP_VERSION="$VERSION"
    export NEXT_PUBLIC_APP_VERSION="$VERSION"
    echo "ETFTool version: $VERSION"
fi
```

---

## 5. 实施步骤

### Phase 1: 核心脚本开发
1. 创建 `scripts/get_version.sh` - 版本提取脚本
2. 创建 `scripts/bump_version.sh` - 版本升级脚本
3. 添加执行权限: `chmod +x scripts/*.sh`

### Phase 2: 后端集成
1. 修改 `backend/app/core/config.py` - 添加 VERSION 字段
2. 修改 `backend/app/main.py` - 更新 health 和 root 端点

### Phase 3: 前端集成
1. 创建 `frontend/lib/api.ts` - API 客户端
2. 修改 `frontend/app/settings/page.tsx` - 动态获取版本

### Phase 4: Docker 集成
1. 修改 `Dockerfile` - 添加 APP_VERSION 构建参数
2. 修改 `docker/entrypoint.sh` - 添加版本日志

### Phase 5: CI/CD 集成
1. 修改 `.github/workflows/docker-build.yml` - 版本提取和注入

### Phase 6: 开发工具集成
1. 修改 `manage.sh` - 启动时注入版本

### Phase 7: 文档完善
1. 创建 `docs/development/versioning-guide.md` - 版本管理指南
2. 更新 `AGENTS.md` - 添加版本管理配置说明

---

## 6. 验证方案

### 6.1 本地开发测试

```bash
# 1. 启动服务
./manage.sh start

# 2. 检查后端版本
curl http://localhost:8000/api/v1/health | jq '.version'
# 预期: "dev-a1b2c3d" 或类似格式

# 3. 检查前端（访问设置页面）
open http://localhost:3000/settings
# 预期: 显示 "ETFTool vdev-a1b2c3d • Designed for Simplicity"
```

### 6.2 Docker 构建测试

```bash
# 1. 构建测试镜像
docker build --build-arg APP_VERSION=0.1.0-test -t etftool:test .

# 2. 运行容器
docker run -d -p 3000:3000 --name etftool-test etftool:test

# 3. 验证版本
curl http://localhost:3000/api/v1/health | jq '.version'
# 预期: "0.1.0-test"

# 4. 清理
docker stop etftool-test && docker rm etftool-test
```

### 6.3 Git 标签测试

```bash
# 1. 创建测试标签
git tag v0.1.0-test

# 2. 提取版本
./scripts/get_version.sh
# 预期输出: "0.1.0-test"

# 3. 删除测试标签
git tag -d v0.1.0-test
```

### 6.4 版本升级测试

```bash
# 1. 测试版本升级脚本
./scripts/bump_version.sh patch

# 2. 检查 CHANGELOG.md 是否更新
cat CHANGELOG.md | head -20

# 3. 检查 Git 标签是否创建
git tag -l | tail -5
```

### 6.5 CI/CD 测试

```bash
# 1. 创建并推送测试标签
git tag v0.1.1-rc.1
git push origin v0.1.1-rc.1

# 2. 监控 GitHub Actions 工作流
# 访问: https://github.com/{username}/ETFTools/actions

# 3. 检查 Docker 镜像
docker pull {username}/etftool:0.1.1-rc.1
docker inspect {username}/etftool:0.1.1-rc.1 | grep APP_VERSION

# 4. 清理测试标签
git tag -d v0.1.1-rc.1
git push origin :refs/tags/v0.1.1-rc.1
```

---

## 7. 发布流程

### 7.1 首次发布（v0.1.0）

实施完成后，建议创建第一个正式版本：

```bash
# 1. 确保所有变更已提交
git add .
git commit -m "feat: implement version management system"

# 2. 创建初始版本标签
git tag -a v0.1.0 -m "Initial release with version management"

# 3. 推送代码和标签
git push origin main
git push origin v0.1.0

# 4. GitHub Actions 将自动构建并发布
```

### 7.2 后续发布流程

```bash
# 1. 准备发布（确保在 main 分支）
git checkout main
git pull origin main

# 2. 运行测试
cd backend && pytest
cd ../frontend && npm test

# 3. 升级版本
./scripts/bump_version.sh patch  # 或 minor/major

# 4. 编辑 CHANGELOG.md，添加发布说明

# 5. 提交并推送
git add CHANGELOG.md
git commit -m "docs: update CHANGELOG for v0.1.1"
git push origin main
git push origin v0.1.1

# 6. 等待 CI/CD 自动构建和发布
```

---

## 8. 注意事项

### 8.1 开发环境

- 本地开发时，未打标签的版本显示为 `dev-{hash}`，这是正常行为
- 如需测试特定版本，可创建本地标签: `git tag v0.1.0-test`

### 8.2 文档同步

根据 `AGENTS.md` 第 4.6 节规定：
- 代码变更必须同步更新相关文档
- 文档更新与代码变更必须在同一个 commit 中提交

### 8.3 脚本权限

新建的 shell 脚本需要添加执行权限：
```bash
chmod +x scripts/get_version.sh
chmod +x scripts/bump_version.sh
```

### 8.4 环境变量

确保以下环境变量正确设置：
- 本地开发: `APP_VERSION`, `NEXT_PUBLIC_APP_VERSION`
- Docker: `APP_VERSION` (构建参数和运行时环境变量)
- CI/CD: 通过 GitHub Actions 自动设置

### 8.5 API 兼容性

Health 端点添加 `version` 字段不会破坏现有客户端：
- 新字段为可选，旧客户端可忽略
- 不影响现有功能的正常运行

---

## 9. 后续优化（可选）

### 9.1 功能增强

- 在前端其他位置显示版本（如页脚、关于页面）
- 添加版本变更通知功能（新版本发布时提示用户）
- 集成自动化 CHANGELOG 生成工具（如 conventional-changelog）
- 添加版本回滚脚本

### 9.2 监控与分析

- 在后端日志中记录版本信息
- 在错误报告中包含版本号
- 统计不同版本的使用情况

### 9.3 多环境支持

- 开发环境: `dev-{hash}`
- 测试环境: `{version}-rc.{n}`
- 生产环境: `{version}`

---

## 10. 参考资料

- [Semantic Versioning 2.0.0](https://semver.org/)
- [Git Tagging](https://git-scm.com/book/en/v2/Git-Basics-Tagging)
- [Docker Build Arguments](https://docs.docker.com/engine/reference/builder/#arg)
- [GitHub Actions - Context and Expression Syntax](https://docs.github.com/en/actions/learn-github-actions/contexts)

---

**最后更新**: 2026-02-05
