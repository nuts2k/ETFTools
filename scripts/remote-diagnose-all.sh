#!/bin/bash
# ETFTool 批量远程诊断脚本
# 用于快速检查所有远程服务器的 ETFTool 容器状态

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
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

# 获取所有服务器名称
SERVER_NAMES=$(jq -r '.servers | keys[]' "$CONFIG_FILE")

if [ -z "$SERVER_NAMES" ]; then
    echo -e "${RED}错误: 配置文件中没有定义任何服务器${NC}"
    exit 1
fi

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}ETFTool 批量远程诊断工具${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# 统计变量
TOTAL=0
SUCCESS=0
FAILED=0

# 遍历所有服务器
for SERVER_NAME in $SERVER_NAMES; do
    TOTAL=$((TOTAL + 1))

    # 读取服务器配置
    SERVER_CONFIG=$(jq -r ".servers.\"$SERVER_NAME\"" "$CONFIG_FILE")
    REMOTE_HOST=$(echo "$SERVER_CONFIG" | jq -r '.server.ssh_host')
    CONTAINER_NAME=$(echo "$SERVER_CONFIG" | jq -r '.container.name')
    SERVER_DESC=$(echo "$SERVER_CONFIG" | jq -r '.server.description // "无描述"')

    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}[$TOTAL] 服务器: $SERVER_NAME ($SERVER_DESC)${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    # 检查 SSH 连接
    echo -n "  SSH 连接: "
    if ssh -o ConnectTimeout=5 "$REMOTE_HOST" "echo 'OK'" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"

        # 检查容器状态
        echo -n "  容器状态: "
        CONTAINER_STATUS=$(ssh "$REMOTE_HOST" "docker ps --filter name=$CONTAINER_NAME --format '{{.Status}}'" 2>/dev/null || echo "")
        if [ -n "$CONTAINER_STATUS" ]; then
            if echo "$CONTAINER_STATUS" | grep -q "Up"; then
                echo -e "${GREEN}✓ 运行中${NC}"

                # 检查资源使用
                echo -n "  资源使用: "
                STATS=$(ssh "$REMOTE_HOST" "docker stats $CONTAINER_NAME --no-stream --format '{{.CPUPerc}}\t{{.MemPerc}}'" 2>/dev/null || echo "")
                if [ -n "$STATS" ]; then
                    CPU=$(echo "$STATS" | cut -f1)
                    MEM=$(echo "$STATS" | cut -f2)
                    echo -e "CPU: ${YELLOW}$CPU${NC}, 内存: ${YELLOW}$MEM${NC}"

                    # 检查进程状态
                    echo -n "  进程状态: "
                    PROC_STATUS=$(ssh "$REMOTE_HOST" "docker exec $CONTAINER_NAME supervisorctl status 2>/dev/null" || echo "")
                    if [ -n "$PROC_STATUS" ]; then
                        RUNNING_COUNT=$(echo "$PROC_STATUS" | grep -c "RUNNING" || echo "0")
                        TOTAL_COUNT=$(echo "$PROC_STATUS" | wc -l)
                        if [ "$RUNNING_COUNT" -eq "$TOTAL_COUNT" ]; then
                            echo -e "${GREEN}✓ $RUNNING_COUNT/$TOTAL_COUNT 进程运行中${NC}"
                            SUCCESS=$((SUCCESS + 1))
                        else
                            echo -e "${YELLOW}⚠ $RUNNING_COUNT/$TOTAL_COUNT 进程运行中${NC}"
                            FAILED=$((FAILED + 1))
                        fi
                    else
                        echo -e "${YELLOW}⚠ 无法获取进程状态${NC}"
                        FAILED=$((FAILED + 1))
                    fi
                else
                    echo -e "${YELLOW}⚠ 无法获取资源使用情况${NC}"
                    FAILED=$((FAILED + 1))
                fi
            else
                echo -e "${RED}✗ $CONTAINER_STATUS${NC}"
                FAILED=$((FAILED + 1))
            fi
        else
            echo -e "${RED}✗ 容器未运行${NC}"
            FAILED=$((FAILED + 1))
        fi
    else
        echo -e "${RED}✗ 连接失败${NC}"
        FAILED=$((FAILED + 1))
    fi

    echo ""
done

# 显示汇总
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}诊断汇总${NC}"
echo -e "${CYAN}========================================${NC}"
echo -e "总计: $TOTAL 台服务器"
echo -e "${GREEN}正常: $SUCCESS 台${NC}"
echo -e "${RED}异常: $FAILED 台${NC}"
echo ""

if [ $FAILED -gt 0 ]; then
    echo -e "${YELLOW}提示: 使用以下命令查看详细信息${NC}"
    echo "  ./scripts/remote-diagnose.sh [服务器名称]"
    exit 1
fi
