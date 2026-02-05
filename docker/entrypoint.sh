#!/bin/bash
# ============================================
# ETFTool Docker 容器启动脚本
# ============================================
# 功能：
# 1. 检查并修复数据库文件权限
# 2. 初始化数据库（如果需要）
# 3. 启动 Supervisor 管理所有服务
# ============================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}[ETFTool]${NC} 容器启动中..."
echo -e "${BLUE}[ETFTool]${NC} 版本: ${APP_VERSION:-unknown}"
echo -e "${BLUE}[ETFTool]${NC} 环境: ${ENVIRONMENT}"

# 数据库文件路径
DB_FILE="/app/backend/etftool.db"

# 检查数据库文件
if [ -f "$DB_FILE" ]; then
    echo -e "${BLUE}[ETFTool]${NC} 检查数据库文件: $DB_FILE"

    # 检查文件大小
    DB_SIZE=$(stat -c%s "$DB_FILE" 2>/dev/null || stat -f%z "$DB_FILE" 2>/dev/null || echo "0")

    if [ "$DB_SIZE" -eq 0 ]; then
        echo -e "${YELLOW}[ETFTool]${NC} 数据库文件为空，将在首次访问时自动初始化"
    fi

    # 修复文件权限和所有权（确保 www-data 可以写入）
    if [ ! -w "$DB_FILE" ]; then
        echo -e "${YELLOW}[ETFTool]${NC} 修复数据库文件权限和所有权..."

        # 设置所有权为 www-data
        if chown www-data:www-data "$DB_FILE" 2>/dev/null; then
            echo -e "${GREEN}[ETFTool]${NC} 数据库文件所有权已设置为 www-data"
        else
            echo -e "${YELLOW}[ETFTool]${NC} 警告: 无法更改文件所有权，尝试修改权限..."
        fi

        # 设置权限为 660 (所有者和组可读写，其他用户无权限)
        if chmod 660 "$DB_FILE" 2>/dev/null; then
            echo -e "${GREEN}[ETFTool]${NC} 数据库文件权限已修复 (660)"
        else
            echo -e "${RED}[ETFTool]${NC} 错误: 无法修复数据库文件权限"
            exit 1
        fi
    else
        echo -e "${GREEN}[ETFTool]${NC} 数据库文件权限正常"
    fi
else
    echo -e "${YELLOW}[ETFTool]${NC} 数据库文件不存在，将在首次访问时自动创建"
fi

# 确保缓存和日志目录存在且权限正确
mkdir -p /app/backend/cache /app/backend/logs /var/log/supervisor
chown -R www-data:www-data /app/backend/cache /app/backend/logs /var/log/supervisor

echo -e "${GREEN}[ETFTool]${NC} 启动 Supervisor..."

# 启动 Supervisor
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
