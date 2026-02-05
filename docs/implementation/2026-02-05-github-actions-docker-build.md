# GitHub Actions Docker 多平台构建实现

## 实现日期
2026-02-05

## 实现目标
在 GitHub 上自动构建多平台 Docker 镜像（linux/amd64, linux/arm64）并推送到 DockerHub。

## 实现内容

### 1. 创建 GitHub Actions 工作流

**文件**: `.github/workflows/docker-build.yml`

**核心功能**:
- ✅ 多平台构建支持（linux/amd64, linux/arm64）
- ✅ 自动化触发机制（push to main, tags, PR）
- ✅ 智能标签策略（语义化版本）
- ✅ 构建缓存优化（GitHub Actions Cache）
- ✅ 自动创建 GitHub Release
- ✅ 构建摘要和验证

**触发方式**:
| 事件 | 触发条件 | 推送到 DockerHub |
|------|---------|-----------------|
| Push to main | 推送代码到 main 分支 | ✅ 是 |
| Tag | 创建版本标签 (v*.*.*)  | ✅ 是 |
| Pull Request | 创建或更新 PR | ❌ 否（仅构建验证）|
| Manual | 手动触发 | 可选 |

### 2. 创建配置指南

**文件**: `docs/deployment/github-actions-setup.md`

**内容包括**:
- DockerHub Token 创建步骤
- GitHub Secrets 配置说明
- 工作流验证方法
- 镜像使用指南
- 故障排查方案
- 安全最佳实践

### 3. 更新现有文档

**更新文件**:
- `docs/deployment/docker-guide.md` - 添加 CI/CD 章节
- `docs/README.md` - 添加新文档索引

## 技术实现

### 工作流架构

```yaml
触发器 → QEMU 设置 → Buildx 设置 → DockerHub 登录
  → 元数据提取 → 多平台构建 → 推送镜像
  → 生成摘要 → 验证清单 → 创建 Release
```

### 标签策略

使用 `docker/metadata-action@v5` 自动生成标签:

**Main 分支推送**:
```
yourname/etftool:main
yourname/etftool:latest
```

**版本标签 (v1.2.3)**:
```
yourname/etftool:v1.2.3
yourname/etftool:v1.2
yourname/etftool:v1
yourname/etftool:latest
```

**Pull Request**:
```
yourname/etftool:pr-123
```
(仅构建，不推送)

### 缓存策略

```yaml
cache-from: type=gha
cache-to: type=gha,mode=max
```

使用 GitHub Actions 缓存可以:
- 在不同工作流运行之间共享缓存
- 显著减少构建时间（首次 20-30 分钟 → 缓存后 5-10 分钟）
- 自动管理缓存生命周期

## 配置要求

### GitHub Secrets

需要在 GitHub 仓库中配置以下 Secrets:

1. **DOCKERHUB_USERNAME** - DockerHub 用户名
2. **DOCKERHUB_TOKEN** - DockerHub Access Token（非密码）

### DockerHub Token 权限

- Read
- Write
- Delete

## 使用方式

### 自动触发

```bash
# 推送到 main 分支 → 自动构建并推送 latest
git push origin main

# 创建版本标签 → 自动构建并推送版本镜像
git tag v1.0.0
git push origin v1.0.0
```

### 手动触发

1. 进入 GitHub Actions 页面
2. 选择 "Docker Multi-Platform Build" 工作流
3. 点击 "Run workflow"
4. 配置参数并运行

### 使用构建的镜像

```bash
# 拉取最新版本
docker pull yourname/etftool:latest

# 拉取特定版本
docker pull yourname/etftool:v1.0.0

# 运行容器
docker run -d \
  -p 3000:3000 \
  -v etftool-data:/app/backend/data \
  --name etftool \
  yourname/etftool:latest
```

## 验证清单

### 构建验证
- [x] 工作流文件语法正确
- [ ] 手动触发测试成功
- [ ] PR 构建测试成功
- [ ] Main 分支推送触发构建
- [ ] 版本标签触发构建

### 镜像验证
- [ ] DockerHub 上可以看到镜像
- [ ] 镜像包含两个平台（amd64, arm64）
- [ ] 可以在不同平台上成功拉取和运行
- [ ] 镜像标签符合预期

### 功能验证
- [ ] 容器启动成功
- [ ] 前端可访问（端口 3000）
- [ ] 后端 API 可访问（/api/v1/health）
- [ ] 数据持久化正常工作

## 成本估算

### GitHub Actions 免费额度
- 公共仓库: 2,000 分钟/月
- 预计使用: ~100 分钟/月（10 次构建 × 10 分钟）
- **结论**: 完全在免费额度内

### DockerHub 免费额度
- 无限公共仓库
- 200 次拉取/6 小时（匿名）
- 无限拉取（认证用户）
- **结论**: 足够使用

## 后续步骤

1. **配置 GitHub Secrets**
   - 创建 DockerHub Access Token
   - 在 GitHub 仓库中添加 Secrets

2. **测试工作流**
   - 手动触发测试
   - 创建测试 PR
   - 推送到 main 分支
   - 创建测试标签

3. **验证镜像**
   - 检查 DockerHub 镜像
   - 验证多架构支持
   - 测试镜像运行

4. **添加构建徽章**（可选）
   - 在 README.md 中添加构建状态徽章
   - 添加 Docker 镜像版本徽章

## 相关文档

- [GitHub Actions 配置指南](../deployment/github-actions-setup.md)
- [Docker 部署指南](../deployment/docker-guide.md)
- [Docker 多架构支持](../deployment/docker-multiarch-guide.md)

## 技术参考

- [Docker Build Push Action](https://github.com/docker/build-push-action)
- [Docker Metadata Action](https://github.com/docker/metadata-action)
- [GitHub Actions 文档](https://docs.github.com/en/actions)

---

**实现者**: Claude Sonnet 4.5
**文档版本**: 1.0
**最后更新**: 2026-02-05
