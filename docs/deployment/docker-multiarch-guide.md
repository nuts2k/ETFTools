# ETFTool 多架构 Docker 镜像构建指南

## 快速开始

### 1. 本地单平台构建（推荐用于开发测试）

```bash
# 构建 ARM64 镜像（Apple Silicon Mac）
./build-multiarch.sh --platform linux/arm64 --load

# 构建 AMD64 镜像（Intel/AMD 处理器）
./build-multiarch.sh --platform linux/amd64 --load
```

构建完成后，使用以下命令运行：

```bash
docker run -d \
  -p 3000:3000 \
  -v $(pwd)/data/etftool.db:/app/backend/etftool.db \
  -v $(pwd)/data/cache:/app/backend/cache \
  -e SECRET_KEY=your-secret-key \
  --name etftool \
  etftool:latest
```

### 2. 多平台构建并推送到 Docker Hub

```bash
# 登录 Docker Hub
docker login

# 构建并推送多架构镜像
./build-multiarch.sh \
  --registry docker.io/your-username \
  --tag latest \
  --push
```

### 3. 多平台构建并推送到私有仓库

```bash
# 登录私有仓库
docker login registry.example.com

# 构建并推送
./build-multiarch.sh \
  --registry registry.example.com/etftool \
  --tag v1.0.0 \
  --push
```

## 构建选项说明

| 选项 | 说明 | 示例 |
|------|------|------|
| `-p, --platform` | 目标平台 | `linux/amd64,linux/arm64` |
| `-t, --tag` | 镜像标签 | `latest`, `v1.0.0` |
| `-n, --name` | 镜像名称 | `etftool` |
| `-r, --registry` | 镜像仓库地址 | `docker.io/username` |
| `--push` | 构建后推送到仓库 | - |
| `--load` | 加载到本地 Docker | - |
| `-h, --help` | 显示帮助信息 | - |

## 注意事项

1. **单平台 vs 多平台**
   - 单平台构建速度快，适合本地开发测试
   - 多平台构建较慢（特别是跨架构模拟），适合生产部署

2. **--load 限制**
   - `--load` 只支持单平台构建
   - 多平台构建必须使用 `--push` 推送到镜像仓库

3. **构建时间**
   - ARM64 原生构建：5-10 分钟
   - AMD64 模拟构建（在 ARM Mac 上）：15-30 分钟
   - 多平台并行构建：15-30 分钟

## 验证多架构镜像

推送到仓库后，可以验证镜像是否包含多个架构：

```bash
docker buildx imagetools inspect docker.io/username/etftool:latest
```

输出应该显示：
```
MediaType: application/vnd.docker.distribution.manifest.list.v2+json
Platform:  linux/amd64
Platform:  linux/arm64
```

## 使用 docker-compose

如果使用 docker-compose，可以直接拉取多架构镜像：

```yaml
services:
  etftool:
    image: docker.io/username/etftool:latest
    ports:
      - "3000:3000"
    # ... 其他配置
```

Docker 会自动选择与当前平台匹配的镜像。

## 故障排查

### 问题：构建很慢

**原因：** 跨架构模拟（QEMU）性能开销

**解决方案：**
- 开发时只构建当前平台：`--platform linux/arm64 --load`
- 使用 CI/CD 在云端构建多平台镜像

### 问题：--load 失败

**错误信息：** `ERROR: docker exporter does not currently support exporting manifest lists`

**原因：** `--load` 不支持多平台

**解决方案：**
- 单平台构建：`--platform linux/amd64 --load`
- 或使用 `--push` 推送到仓库

### 问题：推送失败

**原因：** 未登录镜像仓库

**解决方案：**
```bash
docker login
# 或
docker login registry.example.com
```
