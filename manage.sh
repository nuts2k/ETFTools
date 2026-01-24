#!/bin/bash

# 配置变量
BACKEND_PORT=8000
FRONTEND_PORT=3000
PID_FILE=".services.pid"
BACKEND_LOG="backend/uvicorn.log"
FRONTEND_LOG="frontend/nextjs.log"

# 颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO] $1${NC}"
}

log_warn() {
    echo -e "${YELLOW}[WARN] $1${NC}"
}

log_error() {
    echo -e "${RED}[ERROR] $1${NC}"
}

# 检查并激活虚拟环境
activate_venv() {
    # 如果已经在一个虚拟环境中，直接使用
    if [ -n "$VIRTUAL_ENV" ]; then
        log_info "检测到已激活的虚拟环境: $VIRTUAL_ENV"
        return
    fi

    # 常见的虚拟环境目录名称
    VENV_DIRS=(".venv" "venv" "env" "backend/.venv" "backend/venv")
    
    for dir in "${VENV_DIRS[@]}"; do
        if [ -d "$dir" ]; then
            log_info "发现虚拟环境: $dir"
            if [ -f "$dir/bin/activate" ]; then
                source "$dir/bin/activate"
                return
            fi
        fi
    done

    log_warn "未发现标准虚拟环境目录，将使用系统默认 Python。"
}

# 安装依赖
install_dependencies() {
    log_info "检查并更新后端依赖..."
    # 确保 pip 可用
    if command -v pip &> /dev/null; then
        pip install -e ".[dev]" > /dev/null 2>&1
        if [ $? -eq 0 ]; then
            log_info "后端依赖安装成功"
        else
            log_error "后端依赖安装失败，请检查错误输出"
        fi
    else
        log_error "未找到 pip 命令，跳过后端依赖安装"
    fi

    log_info "检查并更新前端依赖..."
    if command -v npm &> /dev/null; then
        cd frontend
        npm install > /dev/null 2>&1
        if [ $? -eq 0 ]; then
            log_info "前端依赖安装成功"
        else
            log_error "前端依赖安装失败"
        fi
        cd ..
    else
        log_error "未找到 npm 命令，跳过前端依赖安装"
    fi
}

# 停止服务
stop_services() {
    log_info "正在停止服务..."

    # 1. 尝试通过 PID 文件停止
    if [ -f "$PID_FILE" ]; then
        while read pid; do
            if ps -p $pid > /dev/null 2>&1; then
                kill $pid
                log_info "已终止进程 PID: $pid"
            fi
        done < "$PID_FILE"
        rm "$PID_FILE"
    fi

    # 2. 兜底：通过端口清理残留进程
    # 清理后端端口
    BACKEND_PID=$(lsof -t -i:$BACKEND_PORT)
    if [ -n "$BACKEND_PID" ]; then
        log_warn "发现端口 $BACKEND_PORT 仍被占用 (PID: $BACKEND_PID)，强制终止..."
        kill -9 $BACKEND_PID 2>/dev/null
    fi

    # 清理前端端口
    FRONTEND_PID=$(lsof -t -i:$FRONTEND_PORT)
    if [ -n "$FRONTEND_PID" ]; then
        log_warn "发现端口 $FRONTEND_PORT 仍被占用 (PID: $FRONTEND_PID)，强制终止..."
        kill -9 $FRONTEND_PID 2>/dev/null
    fi
    
    log_info "所有服务已停止"
}

# 启动服务
start_services() {
    # 确保先停止旧服务
    stop_services

    # 激活环境
    activate_venv

    # 安装/更新依赖
    install_dependencies

    # 创建日志目录（如果不存在）
    touch "$BACKEND_LOG"
    touch "$FRONTEND_LOG"

    log_info "启动后端服务..."
    # 设置 PYTHONPATH 确保能找到 etftool 模块
    export PYTHONPATH=$PYTHONPATH:$(pwd)
    
    # 启动后端
    # 注意：这里使用 uvicorn 启动方式可能需要调整，根据 README 是 python -m etftool.main
    # 但 etftool.main 里可能直接运行了 uvicorn.run
    # 为了更好地控制，我们直接在后台运行
    nohup python -m etftool.main > "$BACKEND_LOG" 2>&1 &
    BACKEND_PID=$!
    echo $BACKEND_PID >> "$PID_FILE"
    log_info "后端已启动 (PID: $BACKEND_PID)，日志: $BACKEND_LOG"

    log_info "启动前端服务..."
    cd frontend
    nohup npm run dev > "../$FRONTEND_LOG" 2>&1 &
    FRONTEND_PID=$!
    cd ..
    echo $FRONTEND_PID >> "$PID_FILE"
    log_info "前端已启动 (PID: $FRONTEND_PID)，日志: $FRONTEND_LOG"

    log_info "服务启动完成！"
    echo -e "  - Backend: http://localhost:$BACKEND_PORT"
    echo -e "  - Frontend: http://localhost:$FRONTEND_PORT"
}

# 查看状态
check_status() {
    if [ -f "$PID_FILE" ]; then
        echo "当前运行的进程 PID:"
        cat "$PID_FILE"
        echo "-------------------"
    else
        echo "未找到 PID 文件 (可能是服务未启动)"
    fi

    echo "端口状态检查:"
    if lsof -i:$BACKEND_PORT > /dev/null; then
        echo -e "${GREEN}后端 (端口 $BACKEND_PORT): 运行中${NC}"
    else
        echo -e "${RED}后端 (端口 $BACKEND_PORT): 未运行${NC}"
    fi

    if lsof -i:$FRONTEND_PORT > /dev/null; then
        echo -e "${GREEN}前端 (端口 $FRONTEND_PORT): 运行中${NC}"
    else
        echo -e "${RED}前端 (端口 $FRONTEND_PORT): 未运行${NC}"
    fi
}

# 主逻辑
case "$1" in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        stop_services
        start_services
        ;;
    status)
        check_status
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
