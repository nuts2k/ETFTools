# 多服务器配置使用示例

本文档提供多服务器远程调试配置的实际使用示例和最佳实践。

## 配置示例

### 示例 1: 生产 + 测试环境

适用于有独立生产和测试服务器的场景：

```json
{
  "default_server": "prod",
  "servers": {
    "prod": {
      "server": {
        "ssh_host": "prod-server",
        "hostname": "prod.example.com",
        "user": "root",
        "description": "生产服务器 - 主站"
      },
      "container": {
        "name": "etftool",
        "image": "registry.example.com/etftool:latest",
        "port": "3000",
        "memory_limit": "512MiB"
      }
    },
    "staging": {
      "server": {
        "ssh_host": "staging-server",
        "hostname": "staging.example.com",
        "user": "root",
        "description": "测试服务器 - 预发布环境"
      },
      "container": {
        "name": "etftool-staging",
        "image": "registry.example.com/etftool:staging",
        "port": "3000",
        "memory_limit": "256MiB"
      }
    }
  }
}
```

### 示例 2: 多区域部署

适用于多地域部署的场景：

```json
{
  "default_server": "cn-east",
  "servers": {
    "cn-east": {
      "server": {
        "ssh_host": "server-cn-east",
        "hostname": "cn-east.example.com",
        "user": "root",
        "description": "华东节点 - 主服务器"
      },
      "container": {
        "name": "etftool",
        "image": "registry.example.com/etftool:latest",
        "port": "3000",
        "memory_limit": "512MiB"
      }
    },
    "cn-south": {
      "server": {
        "ssh_host": "server-cn-south",
        "hostname": "cn-south.example.com",
        "user": "root",
        "description": "华南节点 - 备用服务器"
      },
      "container": {
        "name": "etftool",
        "image": "registry.example.com/etftool:latest",
        "port": "3000",
        "memory_limit": "512MiB"
      }
    },
    "cn-north": {
      "server": {
        "ssh_host": "server-cn-north",
        "hostname": "cn-north.example.com",
        "user": "root",
        "description": "华北节点 - 备用服务器"
      },
      "container": {
        "name": "etftool",
        "image": "registry.example.com/etftool:latest",
        "port": "3000",
        "memory_limit": "512MiB"
      }
    }
  }
}
```

### 示例 3: 开发 + 测试 + 生产

完整的三环境配置：

```json
{
  "default_server": "prod",
  "servers": {
    "dev": {
      "server": {
        "ssh_host": "dev-server",
        "hostname": "dev.example.com",
        "user": "developer",
        "description": "开发服务器 - 功能测试"
      },
      "container": {
        "name": "etftool-dev",
        "image": "registry.example.com/etftool:dev",
        "port": "3000",
        "memory_limit": "256MiB"
      }
    },
    "staging": {
      "server": {
        "ssh_host": "staging-server",
        "hostname": "staging.example.com",
        "user": "root",
        "description": "测试服务器 - 集成测试"
      },
      "container": {
        "name": "etftool-staging",
        "image": "registry.example.com/etftool:staging",
        "port": "3000",
        "memory_limit": "256MiB"
      }
    },
    "prod": {
      "server": {
        "ssh_host": "prod-server",
        "hostname": "prod.example.com",
        "user": "root",
        "description": "生产服务器 - 正式环境"
      },
      "container": {
        "name": "etftool",
        "image": "registry.example.com/etftool:latest",
        "port": "3000",
        "memory_limit": "512MiB"
      }
    }
  }
}
```

## 使用场景

### 场景 1: 日常巡检

每天检查所有服务器的健康状态：

```bash
# 快速检查所有服务器
./scripts/remote-diagnose-all.sh

# 如果发现异常，深入排查
./scripts/remote-diagnose.sh prod
```

### 场景 2: 部署后验证

部署新版本后，验证所有服务器是否正常：

```bash
# 1. 检查所有服务器状态
./scripts/remote-diagnose-all.sh

# 2. 查看生产服务器的详细日志
./scripts/remote-diagnose.sh prod

# 3. 对比测试和生产环境
./scripts/remote-diagnose.sh staging
./scripts/remote-diagnose.sh prod
```

### 场景 3: 故障排查

当用户报告问题时，快速定位问题服务器：

```bash
# 1. 列出所有服务器
./scripts/remote-diagnose.sh --list

# 2. 批量检查，找出异常服务器
./scripts/remote-diagnose-all.sh

# 3. 深入排查异常服务器
./scripts/remote-diagnose.sh [异常服务器名称]

# 4. 查看实时日志
ssh [ssh_host] "docker logs [container_name] -f"
```

### 场景 4: 性能对比

对比不同服务器的性能表现：

```bash
# 查看所有服务器的资源使用情况
for server in prod staging backup; do
  echo "=== $server ==="
  ssh $(jq -r ".servers.$server.server.ssh_host" .remote-config.json) \
    "docker stats $(jq -r ".servers.$server.container.name" .remote-config.json) --no-stream"
done
```

## SSH 配置最佳实践

### 使用 SSH 密钥认证

在 `~/.ssh/config` 中配置密钥：

```
Host prod-server
    HostName prod.example.com
    User root
    Port 22
    IdentityFile ~/.ssh/id_rsa_prod
    ServerAliveInterval 60
    ServerAliveCountMax 3

Host staging-server
    HostName staging.example.com
    User root
    Port 22
    IdentityFile ~/.ssh/id_rsa_staging
    ServerAliveInterval 60
    ServerAliveCountMax 3
```

### 使用跳板机

如果服务器需要通过跳板机访问：

```
Host jumpbox
    HostName jumpbox.example.com
    User admin
    IdentityFile ~/.ssh/id_rsa_jumpbox

Host prod-server
    HostName 10.0.1.100
    User root
    ProxyJump jumpbox
    IdentityFile ~/.ssh/id_rsa_prod

Host staging-server
    HostName 10.0.1.101
    User root
    ProxyJump jumpbox
    IdentityFile ~/.ssh/id_rsa_staging
```

### 使用 SSH 别名简化命令

```
Host prod
    HostName prod.example.com
    User root
    IdentityFile ~/.ssh/id_rsa_prod

Host staging
    HostName staging.example.com
    User root
    IdentityFile ~/.ssh/id_rsa_staging
```

然后在 `.remote-config.json` 中使用简短的别名：

```json
{
  "servers": {
    "prod": {
      "server": {
        "ssh_host": "prod",  // 使用 SSH 别名
        ...
      }
    }
  }
}
```

## 自动化巡检

### 使用 cron 定时检查

创建巡检脚本 `scripts/health-check.sh`：

```bash
#!/bin/bash
# 健康检查脚本，用于 cron 定时任务

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/var/log/etftool-health-check.log"

echo "[$(date)] 开始健康检查" >> "$LOG_FILE"

if "$SCRIPT_DIR/remote-diagnose-all.sh" >> "$LOG_FILE" 2>&1; then
    echo "[$(date)] 所有服务器正常" >> "$LOG_FILE"
else
    echo "[$(date)] 发现异常服务器，请检查日志" >> "$LOG_FILE"
    # 可以在这里添加告警通知（邮件、钉钉、企业微信等）
fi
```

添加到 crontab：

```bash
# 每小时检查一次
0 * * * * /path/to/ETFTools/scripts/health-check.sh

# 每天早上 9 点检查
0 9 * * * /path/to/ETFTools/scripts/health-check.sh
```

## 安全建议

1. **限制 SSH 访问**:
   - 使用密钥认证，禁用密码登录
   - 配置防火墙规则，只允许特定 IP 访问
   - 定期轮换 SSH 密钥

2. **配置文件安全**:
   - 确保 `.remote-config.json` 权限为 600 (只有所有者可读写)
   - 不要将配置文件提交到 Git 仓库
   - 定期审查配置文件内容

3. **日志审计**:
   - 记录所有远程操作日志
   - 定期检查异常登录和操作
   - 使用集中式日志管理系统

4. **最小权限原则**:
   - 为不同环境使用不同的 SSH 用户
   - 生产环境使用只读用户进行诊断
   - 需要修改时再切换到管理员用户

## 故障排查清单

当服务器出现问题时，按以下顺序检查：

- [ ] SSH 连接是否正常
- [ ] 容器是否在运行
- [ ] 资源使用是否正常（CPU < 80%, 内存 < 90%）
- [ ] 进程状态是否正常（所有进程都在运行）
- [ ] 最近日志是否有错误信息
- [ ] 磁盘空间是否充足
- [ ] 网络连接是否正常
- [ ] 数据库文件是否存在且可访问
- [ ] 缓存目录是否过大
- [ ] 是否有 OOM (Out of Memory) 错误

## 常见问题

### Q: 如何添加新服务器？

A: 编辑 `.remote-config.json`，在 `servers` 对象中添加新的服务器配置：

```json
{
  "servers": {
    "existing-server": {...},
    "new-server": {
      "server": {...},
      "container": {...}
    }
  }
}
```

### Q: 如何更改默认服务器？

A: 修改 `.remote-config.json` 中的 `default_server` 字段：

```json
{
  "default_server": "new-default-server",
  "servers": {...}
}
```

### Q: 如何临时禁用某个服务器？

A: 可以在服务器配置中添加 `disabled` 字段（需要脚本支持），或者直接注释掉该服务器配置。

### Q: 脚本报错 "jq: command not found"？

A: 需要安装 jq 工具：
- macOS: `brew install jq`
- Ubuntu/Debian: `sudo apt-get install jq`
- CentOS/RHEL: `sudo yum install jq`

---
**最后更新**: 2026-02-17
**维护者**: AI Agent (Claude Code)
