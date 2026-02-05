# ETFTool 版本管理指南

## 版本策略

ETFTool 使用 **语义化版本 (Semantic Versioning 2.0.0)**，格式为 `MAJOR.MINOR.PATCH`。

### 版本号规则

- **MAJOR**: 不兼容的 API 变更、数据库迁移
- **MINOR**: 新功能、新 API 端点、性能改进
- **PATCH**: Bug 修复、安全补丁、文档更新

### 预发布版本

- **Alpha**: `v1.2.3-alpha.1` - 内部测试
- **Beta**: `v1.2.3-beta.1` - 公开测试
- **RC**: `v1.2.3-rc.1` - 发布候选

## 发布流程

### 1. 准备发布

```bash
# 确保在 main 分支且代码已同步
git checkout main
git pull origin main

# 运行测试
cd backend && pytest
cd ../frontend && npm test
```

### 2. 版本升级

```bash
# 升级补丁版本 (0.1.0 -> 0.1.1)
./scripts/bump_version.sh patch

# 升级次版本 (0.1.1 -> 0.2.0)
./scripts/bump_version.sh minor

# 升级主版本 (0.2.0 -> 1.0.0)
./scripts/bump_version.sh major
```

### 3. 更新 CHANGELOG

编辑 `CHANGELOG.md`，添加本次发布的详细变更说明。

### 4. 提交并推送

```bash
# 提交 CHANGELOG 变更
git add CHANGELOG.md
git commit -m "docs: update CHANGELOG for v0.1.1"

# 推送代码和标签
git push origin main
git push origin v0.1.1
```

### 5. 自动构建

GitHub Actions 会自动：
- 构建多平台 Docker 镜像
- 推送到 DockerHub
- 创建 GitHub Release

## 本地开发

本地开发时，版本号自动从 git 提取：

```bash
# 使用 manage.sh（自动注入版本）
./manage.sh start

# 查看当前版本
./scripts/get_version.sh
```

## 版本查询

### API 查询

```bash
# 查询后端版本
curl http://localhost:8000/api/v1/health | jq '.version'

# 查询根端点
curl http://localhost:8000/ | jq '.version'
```

### 前端查询

访问设置页面 (http://localhost:3000/settings) 查看版本号。

## Docker 部署

### 构建指定版本

```bash
docker build --build-arg APP_VERSION=1.0.0 -t etftool:1.0.0 .
```

### 查看容器版本

```bash
# 查看环境变量
docker exec <container-id> env | grep APP_VERSION

# 查看启动日志
docker logs <container-id> | grep "版本"
```

## 故障排查

### 版本显示为 "dev"

- 本地开发环境未打标签时的正常行为
- 如需测试特定版本，创建本地标签：`git tag v0.1.0-test`

### Docker 镜像版本不正确

```bash
# 检查构建参数
docker inspect <image> | grep APP_VERSION

# 重新构建
docker build --build-arg APP_VERSION=0.1.0 .
```

### 前端版本显示 "unknown"

- 检查后端 API 是否正常：`curl http://localhost:8000/api/v1/health`
- 检查环境变量：`echo $NEXT_PUBLIC_APP_VERSION`

---

**最后更新**: 2026-02-05
