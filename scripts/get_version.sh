#!/bin/bash
# ETFTool 版本提取脚本
# 从 Git 标签自动提取版本号

set -e

# 尝试从 Git 标签获取版本
if git describe --tags --exact-match 2>/dev/null; then
    # 场景 1: 在标签上，使用标签版本（如 v1.2.3）
    VERSION=$(git describe --tags --exact-match)
elif git describe --tags 2>/dev/null; then
    # 场景 2: 不在标签上，使用 git describe（如 v1.2.3-5-g1234abc）
    VERSION=$(git describe --tags --always)
else
    # 场景 3: 无标签，使用 dev-{commit-hash}
    VERSION="dev-$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
fi

# 移除 'v' 前缀（如果存在）
VERSION=${VERSION#v}

echo "$VERSION"
