# 远程调试配置 (Remote Debugging Configuration)

本文档提供 ETFTool 生产环境的远程调试方法和命令参考，供开发者和 AI 代理使用。

## ⚠️ 配置说明

**重要**: 本文档使用占位符，真实的服务器信息存储在本地配置文件中（不提交到 Git）。

### 首次配置步骤

1. **复制模板配置文件**:
   ```bash
   cp .remote-config.template.json .remote-config.json
   ```

2. **编辑配置文件**，填写你的真实服务器信息:
   ```json
   {
     "server": {
       "ssh_host": "your-server-alias",      // SSH config 中的别名
       "hostname": "your-server.example.com", // 服务器域名或 IP
       "user": "root",                        // SSH 用户名
       "description": "生产服务器描述"
     },
     "container": {
       "name": "etftool",                     // Docker 容器名称
       "image": "your-registry/etftool:latest",
       "port": "3000",
       "memory_limit": "256MiB"
     }
   }
   ```

3. **确保 SSH 配置正确**:
   在 `~/.ssh/config` 中添加服务器配置:
   ```
   Host your-server-alias
       HostName your-server.example.com
       User root
       Port 22
   ```

4. **验证配置**:
   ```bash
   ssh your-server-alias "echo 'SSH 连接成功'"
   ```

### AI 代理使用说明

当 AI 代理需要排查远程服务器问题时，会：
1. 读取项目根目录的 `.remote-config.json` 文件
2. 获取服务器连接信息（SSH host、容器名称等）
3. 使用 SSH 连接到远程服务器执行诊断命令

**注意**: `.remote-config.json` 已添加到 `.gitignore`，不会被提交到 Git 仓库。

## 服务器信息（占位符）

以下使用占位符表示，实际值从 `.remote-config.json` 读取：

- **SSH Host**: `${server.ssh_host}`
- **服务器地址**: `${server.hostname}`
- **用户**: `${server.user}`
- **容器名称**: `${container.name}`
- **容器镜像**: `${container.image}`
- **端口映射**: `${container.port}`

## Docker 容器架构

**容器架构**:
- 使用 Supervisor 管理三个进程：
  - `nextjs`: Next.js 前端服务
  - `fastapi`: FastAPI 后端服务
  - `nginx`: Nginx 反向代理

**其他相关容器**:
- `watchtower`: 自动更新容器
- `caddy`: 反向代理和 HTTPS

## 常用调试命令

以下命令使用 `$SSH_HOST` 和 `$CONTAINER_NAME` 作为占位符，实际使用时需要替换为真实值。

### 1. 查看容器状态
```bash
ssh $SSH_HOST "docker ps -a | grep $CONTAINER_NAME"
```

### 2. 查看实时日志
```bash
# 查看最近 100 行日志
ssh $SSH_HOST "docker logs $CONTAINER_NAME --tail 100"

# 实时跟踪日志
ssh $SSH_HOST "docker logs $CONTAINER_NAME -f"

# 查看特定时间范围的日志
ssh $SSH_HOST "docker logs $CONTAINER_NAME --since 1h"
```

### 3. 查看资源使用
```bash
# 查看 CPU、内存使用情况
ssh $SSH_HOST "docker stats $CONTAINER_NAME --no-stream"

# 持续监控
ssh $SSH_HOST "docker stats $CONTAINER_NAME"
```

### 4. 进入容器执行命令
```bash
# 进入容器 shell
ssh $SSH_HOST "docker exec -it $CONTAINER_NAME /bin/bash"

# 执行单个命令
ssh $SSH_HOST "docker exec $CONTAINER_NAME ls -la /app"

# 查看进程状态
ssh $SSH_HOST "docker exec $CONTAINER_NAME supervisorctl status"
```

### 5. 查看容器详细信息
```bash
# 查看环境变量
ssh $SSH_HOST "docker inspect $CONTAINER_NAME --format '{{json .Config.Env}}' | python3 -m json.tool"

# 查看挂载点
ssh $SSH_HOST "docker inspect $CONTAINER_NAME --format '{{json .Mounts}}' | python3 -m json.tool"

# 查看网络配置
ssh $SSH_HOST "docker inspect $CONTAINER_NAME --format '{{json .NetworkSettings}}' | python3 -m json.tool"
```

### 6. 重启容器
```bash
# 重启容器
ssh $SSH_HOST "docker restart $CONTAINER_NAME"

# 查看重启后的日志
ssh $SSH_HOST "docker logs $CONTAINER_NAME --tail 50"
```

### 7. 查看数据库
```bash
# 进入容器并查看数据库
ssh $SSH_HOST "docker exec -it $CONTAINER_NAME sqlite3 /app/backend/etftool.db"

# 查看数据库文件大小
ssh $SSH_HOST "docker exec $CONTAINER_NAME ls -lh /app/backend/etftool.db"
```

## 常见问题排查流程

### 问题 1: 容器无法启动或反复重启
```bash
# 1. 查看容器状态
ssh $SSH_HOST "docker ps -a | grep $CONTAINER_NAME"

# 2. 查看启动日志
ssh $SSH_HOST "docker logs $CONTAINER_NAME --tail 100"

# 3. 检查资源限制
ssh $SSH_HOST "docker stats $CONTAINER_NAME --no-stream"

# 4. 查看容器配置
ssh $SSH_HOST "docker inspect $CONTAINER_NAME"
```

### 问题 2: 应用运行异常
```bash
# 1. 查看实时日志
ssh $SSH_HOST "docker logs $CONTAINER_NAME -f"

# 2. 检查进程状态
ssh $SSH_HOST "docker exec $CONTAINER_NAME supervisorctl status"

# 3. 查看错误日志
ssh $SSH_HOST "docker exec $CONTAINER_NAME cat /var/log/supervisor/fastapi-stderr.log"
ssh $SSH_HOST "docker exec $CONTAINER_NAME cat /var/log/supervisor/nextjs-stderr.log"

# 4. 检查数据库连接
ssh $SSH_HOST "docker exec $CONTAINER_NAME ls -la /app/backend/etftool.db"
```

### 问题 3: 性能问题
```bash
# 1. 查看资源使用
ssh $SSH_HOST "docker stats $CONTAINER_NAME"

# 2. 查看进程详情
ssh $SSH_HOST "docker exec $CONTAINER_NAME ps aux"

# 3. 查看磁盘使用
ssh $SSH_HOST "docker exec $CONTAINER_NAME df -h"

# 4. 查看缓存目录
ssh $SSH_HOST "docker exec $CONTAINER_NAME du -sh /app/backend/cache"
```

### 问题 4: 内存使用过高
```bash
# 1. 查看当前内存使用
ssh $SSH_HOST "docker stats $CONTAINER_NAME --no-stream"

# 2. 查看进程内存占用
ssh $SSH_HOST "docker exec $CONTAINER_NAME ps aux --sort=-%mem | head -10"

# 3. 清理缓存（如果需要）
ssh $SSH_HOST "docker exec $CONTAINER_NAME rm -rf /app/backend/cache/*"

# 4. 重启容器释放内存
ssh $SSH_HOST "docker restart $CONTAINER_NAME"
```

## AI 代理使用指南

当用户要求排查远程服务器问题时，AI 代理应该：

1. **读取配置**: 首先读取 `.remote-config.json` 获取服务器信息
2. **自动连接**: 使用配置中的 SSH host 连接，无需询问用户
3. **系统性排查**: 按照以下顺序检查：
   - 容器状态（是否运行、健康检查）
   - 资源使用（CPU、内存、磁盘）
   - 最近日志（查找错误信息）
   - 进程状态（Supervisor 管理的三个进程）
4. **主动分析**: 根据日志和状态信息，主动判断问题原因
5. **提供建议**: 给出具体的解决方案，而不仅仅是展示信息

## 快速诊断脚本

项目提供了快速诊断脚本 `scripts/remote-diagnose.sh`，会自动从配置文件读取服务器信息：

```bash
./scripts/remote-diagnose.sh
```

该脚本会检查：
- SSH 连接状态
- 容器运行状态
- 资源使用情况（CPU、内存）
- 进程状态
- 最近的日志

## 注意事项

⚠️ **内存限制**: 容器内存限制通常为 256MiB，如果使用率接近 100%，需要考虑：
- 增加内存限制
- 优化应用内存使用
- 清理缓存

⚠️ **时区配置**: 容器使用 `Asia/Shanghai` 时区，日志时间为北京时间

⚠️ **数据持久化**: 数据库文件位于 `/app/backend/etftool.db`，需要确保有适当的备份策略

⚠️ **自动更新**: Watchtower 容器会自动更新 etftool 镜像，可能导致意外重启

⚠️ **安全提醒**:
- 不要将 `.remote-config.json` 提交到 Git 仓库
- 不要在公开文档中包含真实的服务器地址、IP、域名等信息
- 定期更新 SSH 密钥和服务器访问凭证

---
**最后更新**: 2026-02-13
**维护者**: AI Agent (Claude Code)
