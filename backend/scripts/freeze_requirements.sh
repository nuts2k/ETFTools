#!/bin/bash
# 生成锁定版本的 requirements.txt
#
# 使用方式:
#   chmod +x scripts/freeze_requirements.sh
#   ./scripts/freeze_requirements.sh

set -e

echo "📦 正在生成 requirements.txt..."

# 切换到 backend 目录
cd "$(dirname "$0")/.." || exit 1

# 检查是否在虚拟环境中
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "⚠️  警告: 未检测到虚拟环境，将创建临时环境"
    
    # 创建临时虚拟环境
    python3 -m venv .venv_temp
    source .venv_temp/bin/activate
    
    # 安装依赖
    pip install --upgrade pip --quiet
    pip install -e ".[dev]" --quiet
    
    # 生成 requirements.txt
    pip freeze > requirements.txt
    
    # 清理临时环境
    deactivate
    rm -rf .venv_temp
else
    echo "ℹ️  使用当前虚拟环境: $VIRTUAL_ENV"
    pip freeze > requirements.txt
fi

echo "✅ requirements.txt 已生成"
echo "📋 包含 $(wc -l < requirements.txt | tr -d ' ') 个依赖包"
