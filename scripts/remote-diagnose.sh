#!/bin/bash
# ETFTool 远程诊断脚本
# 用于快速检查远程服务器上的 ETFTool 容器状态
#
# 用法:
#   ./remote-diagnose.sh           # 使用默认服务器
#   ./remote-diagnose.sh prod      # 指定服务器名称
#   ./remote-diagnose.sh --list    # 列出所有可用服务器

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置文件路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$PROJECT_ROOT/.remote-config.json"

# 检查配置文件是否存在
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}错误: 配置文件不存在${NC}"
    echo -e "${YELLOW}请先创建配置文件:${NC}"
    echo "  cp .remote-config.template.json .remote-config.json"
    echo "  然后编辑 .remote-config.json 填写你的服务器信息"
    exit 1
fi

# 检查 jq 是否安装
if ! command -v jq &> /dev/null; then
    echo -e "${RED}错误: 需要安装 jq 来解析多服务器配置${NC}"
    echo -e "${YELLOW}安装方法:${NC}"
    echo "  macOS: brew install jq"
    echo "  Ubuntu/Debian: sudo apt-get install jq"
    echo "  CentOS/RHEL: sudo yum install jq"
    exit 1
fi

# 列出所有服务器
list_servers() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}可用的服务器列表${NC}"
    echo -e "${BLUE}========================================${NC}"

    DEFAULT_SERVER=$(jq -r '.default_server // "未设置"' "$CONFIG_FILE")
    echo -e "${YELLOW}默认服务器: $DEFAULT_SERVER${NC}"
    echo ""

    jq -r '.servers | to_entries[] | "\(.key)\t\(.value.server.description // "无描述")\t\(.value.server.hostname)"' "$CONFIG_FILE" | \
    while IFS=$'\t' read -r name desc hostname; do
        if [ "$name" = "$DEFAULT_SERVER" ]; then
            echo -e "${GREEN}* $name${NC} - $desc ($hostname)"
        else
        echo -e "  $name - $desc ($hostname)"
        fi
    done
    echo ""
    echo "用法: ./remote-diagnose.sh [服务器名称]"
}

# 处理命令行参数
if [ "$1" = "--list" ] || [ "$1" = "-l" ]; then
    list_servers
    exit 0
fi

# 确定要使用的服务器
if [ -n "$1" ]; then
    SERVER_NAME="$1"
else
    SERVER_NAME=$(jq -r '.default_server' "$CONFIG_FILE")
    if [ "$SERVER_NAME" = "null" ] || [ -z "$SERVER_NAME" ]; then
        echo -e "${RED}错误: 未指定服务器且配置文件中没有设置 default_server${NC}"
        echo -e "${YELLOW}请使用以下方式之一:${NC}"
        echo "  1. 指定服务器名称: ./remote-diagnose.sh prod"
        echo "  2. 查看可用服务器: ./remote-diagnose.sh --list"
        echo "  3. 在配置文件中设置 default_server"
        exit 1
    fi
fi

# 读取服务器配置
SERVER_CONFIG=$(jq -r ".servers.\"$SERVER_NAME\"" "$CONFIG_FILE")
if [ "$SERVER_CONFIG" = "null" ]; then
    echo -e "${RED}错误: 服务器 '$SERVER_NAME' 不存在${NC}"
    echo -e "${YELLOW}可用的服务器:${NC}"
    jq -r '.servers | keys[]' "$CONFIG_FILE" | sed 's/^/  /'
    exit 1
fi

# 提取配置信息
REMOTE_HOST=$(echo "$SERVER_CONFIG" | jq -r '.server.ssh_host')
CONTAINER_NAME=$(echo "$SERVER_CONFIG" | jq -r '.container.name')
SERVER_DESC=$(echo "$SERVER_CONFIG" | jq -r '.server.description // "无描述"')

# 验证配置
if [ -z "$REMOTE_HOST" ] || [ "$REMOTE_HOST" = "null" ] || [ -z "$CONTAINER_NAME" ] || [ "$CONTAINER_NAME" = "null" ]; then
    echo -e "${RED}错误: 服务器 '$SERVER_NAME' 的配置不完整${NC}"
    echo "请检查 $CONFIG_FILE 中的配置"
    exit 1
fi


echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}ETFTool 远程诊断工具${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}服务器: $SERVER_NAME ($SERVER_DESC)${NC}"
echo -e "${BLUE}SSH Host: $REMOTE_HOST${NC}"
echo -e "${BLUE}容器: $CONTAINER_NAME${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查 SSH 连接
echo -e "${YELLOW}[1/5] 检查 SSH 连接...${NC}"
if ssh -o ConnectTimeout=5 "$REMOTE_HOST" "echo 'SSH 连接成功'" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ SSH 连接正常${NC}"
else
    echo -e "${RED}✗ SSH 连接失败${NC}"
    echo -e "${YELLOW}请检查:${NC}"
    echo "  1. SSH 配置是否正确 (~/.ssh/config)"
    echo "  2. 网络连接是否正常"
    echo "  3. 服务器是否可访问"
    exit 1
fi
echo ""

# 查看容器状态
echo -e "${YELLOW}[2/5] 容器状态${NC}"
ssh "$REMOTE_HOST" "docker ps -a --filter name=$CONTAINER_NAME --format 'table {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}'"
echo ""

# 查看资源使用
echo -e "${YELLOW}[3/5] 资源使用情况${NC}"
ssh "$REMOTE_HOST" "docker stats $CONTAINER_NAME --no-stream --format 'table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}'"
echo ""

# 查看进程状态
echo -e "${YELLOW}[4/5] 进程状态${NC}"
if ssh "$REMOTE_HOST" "docker exec $CONTAINER_NAME supervisorctl status" 2>/dev/null; then
    :
else
    echo -e "${YELLOW}注意: 无法获取进程状态（可能是 supervisor socket 路径问题）${NC}"
fi
echo ""

# 查看最近日志
echo -e "${YELLOW}[5/5] 最近日志 (最后 20 行)${NC}"
ssh "$REMOTE_HOST" "docker logs $CONTAINER_NAME --tail 20"
echo ""

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}诊断完成！${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "更多命令："
echo "  查看实时日志: ssh $REMOTE_HOST \"docker logs $CONTAINER_NAME -f\""
echo "  进入容器: ssh $REMOTE_HOST \"docker exec -it $CONTAINER_NAME /bin/bash\""
echo "  重启容器: ssh $REMOTE_HOST \"docker restart $CONTAINER_NAME\""
echo ""
