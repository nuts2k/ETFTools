# 多服务器远程调试配置指南

本指南说明如何配置和使用 ETFTools 的多服务器远程调试功能。

## 快速开始

### 1. 创建配置文件

```bash
cp .remote-config.template.json .remote-config.json
```

### 2. 编辑配置文件

编辑 `.remote-config.json`，添加你的服务器信息：

```json
{
  "default_server": "prod",
  "servers": {
    "prod": {
      "server": {
        "ssh_host": "your-prod-server",
        "hostname": "prod.example.com",
        "user": "root",
        "description": "生产服务器"
      },
      "container": {
        "name": "etftool",
        "image": "your-registry/etftool:latest",
        "port": "3000",
        "memory_limit": "256MiB"
      }
    },
    "staging": {
      "server": {
        "ssh_host": "your-staging-server",
        "hostname": "staging.example.com",
        "user": "root",
        "description": "测试服务器"
      },
      "container": {
        "name": "etftool-staging",
        "image": "your-registry/etftool:staging",
        "port": "3000",
        "memory_limit": "256MiB"
      }
    }
  }
}
```

### 3. 配置 SSH

在 `~/.ssh/config` 中添加服务器配置：

```
Host your-prod-server
    HostName prod.example.com
    User root
    Port 22
    IdentityFile ~/.ssh/id_rsa

Host your-staging-server
    HostName staging.example.com
    User root
    Port 22
    IdentityFile ~/.ssh/id_rsa
```

### 4. 验证配置

```bash
# 列出所有配置的服务器
./scripts/remote-diagnose.sh --list

# 测试 SSH 连接
ssh your-prod-server "echo 'SSH 连接成功'"
```

## 使用方法

### 诊断单个服务器

```bash
# 使用默认服务器
./scripts/remote-diagnose.sh

# 指定服务器名称
./scripts/remote-diagnose.sh prod
./scripts/remote-diagnose.sh staging
```

### 诊断所有服务器

```bash
# 批量检查所有服务器
./scripts/remote-diagnose-all.sh
```

### 列出所有服务器

```bash
./scripts/remote-diagnose.sh --list
```

## 配置结构说明

### 顶层字段

- `default_server`: 默认使用的服务器名称（不带参数运行脚本时使用）
- `servers`: 服务器配置对象，key 为服务器名称

### 服务器配置

每个服务器包含两部分配置：

**server** (服务器信息):
- `ssh_host`: SSH config 中的别名
- `hostname`: 服务器域名或 IP 地址
- `user`: SSH 用户名
- `description`: 服务器描述（用于显示）

**container** (容器信息):
- `name`: Docker 容器名称
- `image`: Docker 镜像名称
- `port`: 容器端口映射
- `memory_limit`: 容器内存限制

## 文档索引

- **完整配置文档**: [docs/deployment/remote-debug.md](docs/deployment/remote-debug.md)
- **配置示例**: [docs/deployment/multi-server-examples.md](docs/deployment/multi-server-examples.md)
- **快速参考**: [AGENTS.md](AGENTS.md) 第 3.1 节

## 主要特性

✅ **多服务器支持**: 在一个配置文件中管理多台服务器
✅ **默认服务器**: 设置常用服务器为默认，简化命令
✅ **批量诊断**: 一键检查所有服务器的健康状态
✅ **灵活切换**: 通过服务器名称快速切换目标服务器
✅ **详细信息**: 每个服务器可以添加描述，便于识别

## 常用命令

```bash
# 列出所有服务器
./scripts/remote-diagnose.sh --list

# 诊断默认服务器
./scripts/remote-diagnose.sh

# 诊断指定服务器
./scripts/remote-diagnose.sh prod

# 批量诊断所有服务器
./scripts/remote-diagnose-all.sh

# 查看实时日志
ssh your-server "docker logs etftool -f"

# 进入容器
ssh your-server "docker exec -it etftool /bin/bash"

# 重启容器
ssh your-server "docker restart etftool"
```

## 安全提醒

⚠️ `.remote-config.json` 包含敏感信息，已添加到 `.gitignore`
⚠️ 不要在公开文档中包含真实的服务器地址、域名等信息
⚠️ 使用模板文件 `.remote-config.template.json` 作为公开的配置示例
⚠️ 定期更新 SSH 密钥和服务器访问凭证

## 升级说明

如果你之前使用的是单服务器配置（旧版本），需要将配置迁移到新格式：

**旧格式**:
```json
{
  "server": {...},
  "container": {...}
}
```

**新格式**:
```json
{
  "default_server": "prod",
  "servers": {
    "prod": {
      "server": {...},
      "container": {...}
    }
  }
}
```

迁移步骤：
1. 备份现有的 `.remote-config.json`
2. 复制新的模板文件 `.remote-config.template.json`
3. 将旧配置迁移到新格式的 `servers.prod` 中
4. 设置 `default_server` 为 `"prod"`

---
**版本**: v2.0
**最后更新**: 2026-02-17
