#!/bin/bash
# ETFTool 远程诊断脚本
# 用于快速检查远程服务器上的 ETFTool 容器状态

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

# 读取配置文件
if ! command -v jq &> /dev/null; then
    echo -e "${YELLOW}警告: 未安装 jq，使用简单的 grep 解析配置${NC}"
    REMOTE_HOST=$(grep -o '"ssh_host"[[:space:]]*:[[:space:]]*"[^"]*"' "$CONFIG_FILE" | cut -d'"' -f4)
    CONTAINER_NAME=$(grep -o '"name"[[:space:]]*:[[:space:]]*"[^"]*"' "$CONFIG_FILE" | tail -1 | cut -d'"' -f4)
else
    REMOTE_HOST=$(jq -r '.server.ssh_host' "$CONFIG_FILE")
    CONTAINER_NAME=$(jq -r '.container.name' "$CONFIG_FILE")
fi

# 验证配置
if [ -z "$REMOTE_HOST" ] || [ -z "$CONTAINER_NAME" ]; then
    echo -e "${RED}错误: 配置文件格式不正确${NC}"
    echo "请检查 $CONFIG_FILE 的内容"
    exit 1
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}ETFTool 远程诊断工具${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}服务器: $REMOTE_HOST${NC}"
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
