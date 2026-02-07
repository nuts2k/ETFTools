# Docker 镜像瘦身优化

## Context

当前 Docker 镜像体积较大，主要原因：
1. **运行时安装完整 Node.js**：通过 NodeSource apt 仓库安装 Node.js 20.x（~200MB+），还需 gnupg 等工具
2. **开发依赖打入生产镜像**：requirements.txt 包含 pytest、mypy、ruff、ipython、coverage 等开发工具（~50-100MB）
3. **基础镜像 `python:3.11-slim`**：~150MB，包含完整 Python 运行时

## 优化方案

### 优化 1：用 node:20-alpine 的二进制替代 apt 安装 Node.js

**当前做法（Stage 3，约 15 行）：**
```
RUN apt-get update && apt-get install -y \
    nginx supervisor curl ca-certificates gnupg \
    && curl ... nodesource ... gpg ... \
    && apt-get update && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*
```

**优化后：** 从 Stage 1 的 `node:20-alpine` 直接复制 Node.js 二进制文件，省去 NodeSource 仓库、gnupg 等。

```dockerfile
# 在 Stage 3 中：
COPY --from=frontend-builder /usr/local/bin/node /usr/local/bin/node

# apt-get 只需安装 nginx、supervisor、curl、ca-certificates
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx supervisor curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
```

**节省：** ~150-200MB（去掉 apt Node.js + gnupg + 第二次 apt-get update 的缓存）

### 优化 2：分离生产/开发依赖

**当前做法：** 单一 `requirements.txt` 包含所有依赖。

**优化后：** 创建 `requirements-dev.txt`，将开发依赖移出 `requirements.txt`。

从 `requirements.txt` 移除的包（移入 `requirements-dev.txt`）：
- `coverage==7.10.7`
- `ipython==8.18.1`（及其依赖：asttokens, decorator, executing, jedi, matplotlib-inline, parso, pexpect, prompt_toolkit, ptyprocess, pure_eval, Pygments, stack-data, traitlets, wcwidth）
- `mypy==1.19.1`（及其依赖：mypy_extensions, pathspec, tomli）
- `pytest==8.4.2`（及其依赖：iniconfig, pluggy, exceptiongroup）
- `pytest-asyncio==1.2.0`
- `pytest-cov==7.0.0`
- `ruff==0.14.14`

**节省：** ~50-80MB

### 优化 3：基础镜像改用 `python:3.11-slim` → `debian:bookworm-slim` + 手动装 Python

**不采用此方案。** `python:3.11-slim` 已经基于 `debian:bookworm-slim`，手动安装 Python 反而更复杂且不一定更小。当前基础镜像选择合理。

## 修改文件清单

1. **`Dockerfile`** — Stage 3 运行时依赖安装改为从 alpine 复制 node 二进制
2. **`backend/requirements.txt`** — 移除开发依赖
3. **`backend/requirements-dev.txt`** — 新建，包含开发依赖

## 详细改动

### 1. Dockerfile 修改

**Stage 3 运行时依赖安装**（替换第 60-72 行）：

```dockerfile
# 从前端构建阶段复制 Node.js 二进制
COPY --from=frontend-builder /usr/local/bin/node /usr/local/bin/node

# 安装运行时依赖（不再需要 gnupg 和 NodeSource）
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    supervisor \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*
```

### 2. requirements.txt 移除的包

```
coverage, ipython, jedi, asttokens, decorator, executing,
matplotlib-inline, parso, pexpect, prompt_toolkit, ptyprocess,
pure_eval, Pygments, stack-data, traitlets, wcwidth,
mypy, mypy_extensions, pathspec, tomli,
pytest, pytest-asyncio, pytest-cov, iniconfig, pluggy,
ruff
```

### 3. requirements-dev.txt（新建）

```
-r requirements.txt
coverage==7.10.7
ipython==8.18.1
mypy==1.19.1
mypy_extensions==1.1.0
pytest==8.4.2
pytest-asyncio==1.2.0
pytest-cov==7.0.0
ruff==0.14.14
```

只列顶层开发包，其传递依赖由 pip 自动解析安装。`requirements.txt` 中移除所有仅被开发包依赖的传递包。

## 验证

1. **本地构建测试：** `docker build -t etftool:slim .`
2. **镜像大小对比：** `docker images etftool` 对比优化前后
3. **容器运行测试：** `docker run -p 3000:3000 etftool:slim`，验证前后端均正常
4. **开发环境验证：** `pip install -r requirements-dev.txt` 确保开发依赖仍可安装
5. **单元测试：** `cd frontend && npx vitest run`
6. **后端测试：** 在开发环境 `pip install -r requirements-dev.txt && pytest`
