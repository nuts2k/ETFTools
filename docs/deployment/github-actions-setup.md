# GitHub Actions Docker 构建配置指南

## 概述

本项目已配置 GitHub Actions 自动化工作流，用于构建和推送多平台 Docker 镜像（linux/amd64, linux/arm64）。

## 工作流文件

- **位置**: `.github/workflows/docker-build.yml`
- **名称**: Docker Multi-Platform Build

## 触发方式

| 事件 | 触发条件 | 行为 | 推送到 DockerHub |
|------|---------|------|-----------------|
| Push to main | 推送代码到 main 分支 | 构建并推送 | ✅ 是 |
| Tag | 创建版本标签 (v*.*.*)  | 构建、推送、创建 Release | ✅ 是 |
| Pull Request | 创建或更新 PR | 仅构建验证 | ❌ 否 |
| Manual | 手动触发 | 可自定义 | 可选 |

## 配置步骤

### 步骤 1: 创建 DockerHub Access Token

1. 访问 [DockerHub Security Settings](https://hub.docker.com/settings/security)
2. 点击 **"New Access Token"**
3. 配置 Token:
   - **Token Description**: `GitHub Actions - ETFTools`
   - **Access permissions**: `Read, Write, Delete`
4. 点击 **"Generate"**
5. **重要**: 立即复制生成的 Token（只显示一次）

### 步骤 2: 配置 GitHub Secrets

1. 进入 GitHub 仓库页面
2. 点击 **Settings** → **Secrets and variables** → **Actions**
3. 点击 **"New repository secret"** 添加以下 Secrets:

#### Secret 1: DOCKERHUB_USERNAME
- **Name**: `DOCKERHUB_USERNAME`
- **Value**: 你的 DockerHub 用户名（例如: `yourname`）

#### Secret 2: DOCKERHUB_TOKEN
- **Name**: `DOCKERHUB_TOKEN`
- **Value**: 步骤 1 中复制的 Access Token

### 步骤 3: 验证配置

配置完成后，可以通过以下方式验证:

#### 方法 1: 手动触发测试
1. 进入 **Actions** 页面
2. 选择 **"Docker Multi-Platform Build"** 工作流
3. 点击 **"Run workflow"**
4. 配置参数:
   - **Branch**: `main`
   - **Custom tag**: `test` (可选)
   - **Push to DockerHub**: `false` (首次测试建议不推送)
5. 点击 **"Run workflow"** 开始构建

#### 方法 2: 创建测试 PR
1. 创建新分支并提交小改动
2. 创建 Pull Request
3. 查看 Actions 页面，验证工作流自动触发
4. 确认构建成功（不会推送到 DockerHub）

#### 方法 3: 推送到 main 分支
1. 合并 PR 到 main 分支
2. 查看 Actions 页面，验证工作流自动触发
3. 确认构建成功并推送到 DockerHub
4. 访问 DockerHub 验证镜像存在

## 生成的镜像标签

### Main 分支推送
```
yourname/etftool:main
yourname/etftool:latest
```

### 版本标签 (例如: v1.2.3)
```
yourname/etftool:v1.2.3
yourname/etftool:v1.2
yourname/etftool:v1
yourname/etftool:latest
```

### Pull Request
```
yourname/etftool:pr-123
```
(仅构建，不推送)

## 使用构建的镜像

### 拉取最新版本
```bash
docker pull yourname/etftool:latest
```

### 拉取特定版本
```bash
docker pull yourname/etftool:v1.2.3
```

### 运行容器
```bash
docker run -d \
  -p 3000:3000 \
  -v etftool-data:/app/backend/data \
  --name etftool \
  yourname/etftool:latest
```

### 验证多架构支持
```bash
docker buildx imagetools inspect yourname/etftool:latest
```

应该显示:
```
Platform: linux/amd64
Platform: linux/arm64
```

## 发布新版本

### 创建版本标签
```bash
# 创建标签
git tag v1.0.0

# 推送标签到 GitHub
git push origin v1.0.0
```

### 自动化流程
1. GitHub Actions 自动触发构建
2. 构建多平台镜像（amd64 + arm64）
3. 推送到 DockerHub（多个标签）
4. 自动创建 GitHub Release

## 构建时间和成本

### 构建时间
- **首次构建**: 20-30 分钟
- **缓存命中后**: 5-10 分钟

### GitHub Actions 免费额度
- **公共仓库**: 2,000 分钟/月
- **预计使用**: ~100 分钟/月（10 次构建 × 10 分钟）
- **结论**: 完全在免费额度内

### DockerHub 免费额度
- 无限公共仓库
- 200 次拉取/6 小时（匿名）
- 无限拉取（认证用户）

## 故障排除

### 问题 1: 认证失败
**错误信息**: `Error: Cannot perform an interactive login from a non TTY device`

**解决方案**:
1. 检查 GitHub Secrets 是否正确配置
2. 验证 DOCKERHUB_TOKEN 是 Access Token（不是密码）
3. 确认 Token 权限包含 Read, Write, Delete
4. 检查 Token 是否过期

### 问题 2: 构建超时
**错误信息**: `Error: The operation was canceled.`

**解决方案**:
1. 检查网络连接
2. 考虑增加 `timeout-minutes` 配置
3. 检查 `.dockerignore` 是否排除了大文件

### 问题 3: 多平台构建失败
**错误信息**: `ERROR: failed to solve: process "/bin/sh -c ..." did not complete successfully`

**解决方案**:
1. 验证 QEMU 设置正确
2. 检查基础镜像是否支持目标平台
3. 查看详细构建日志定位问题

### 问题 4: 缓存问题
**症状**: 构建时间异常长，缓存未命中

**解决方案**:
1. 检查 GitHub Actions 缓存大小限制（10GB）
2. 手动清除缓存（Actions 页面 → Caches）
3. 尝试更改缓存 scope

## 本地构建脚本

GitHub Actions 工作流不影响本地开发。你仍然可以使用本地构建脚本:

```bash
# 本地单平台构建（快速测试）
./build-multiarch.sh --platform linux/amd64 --load

# 本地多平台构建并推送
./build-multiarch.sh --registry docker.io/yourname --push
```

## 工作流配置详情

### 环境变量
```yaml
env:
  REGISTRY_IMAGE: ${{ secrets.DOCKERHUB_USERNAME }}/etftool
```

### 缓存策略
```yaml
cache-from: type=gha
cache-to: type=gha,mode=max
```

使用 GitHub Actions 缓存可以:
- 在不同工作流运行之间共享缓存
- 显著减少构建时间
- 自动管理缓存生命周期

### 并发控制
```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

避免同一分支/PR 的重复构建。

## 安全最佳实践

1. **使用 Access Token**: 不要使用 DockerHub 密码
2. **最小权限原则**: Token 只授予必要的权限
3. **定期轮换**: 定期更新 Access Token
4. **监控使用**: 定期检查 DockerHub 访问日志
5. **保护 Secrets**: 不要在日志中打印 Secrets

## 参考资源

- [Docker Build Push Action](https://github.com/docker/build-push-action)
- [Docker Metadata Action](https://github.com/docker/metadata-action)
- [GitHub Actions 文档](https://docs.github.com/en/actions)
- [DockerHub 文档](https://docs.docker.com/docker-hub/)

## 下一步

配置完成后，建议:

1. ✅ 执行手动触发测试
2. ✅ 创建测试 PR 验证构建
3. ✅ 推送到 main 分支验证推送
4. ✅ 创建测试标签验证版本发布
5. ✅ 在 README.md 中添加构建状态徽章

## 构建状态徽章

在 `README.md` 中添加以下徽章:

```markdown
[![Docker Build](https://github.com/yourname/ETFTools/actions/workflows/docker-build.yml/badge.svg)](https://github.com/yourname/ETFTools/actions/workflows/docker-build.yml)
[![Docker Image](https://img.shields.io/docker/v/yourname/etftool?label=docker&logo=docker)](https://hub.docker.com/r/yourname/etftool)
```

记得将 `yourname` 替换为你的 GitHub 用户名和 DockerHub 用户名。
