#!/bin/bash

# Configuration
BACKEND_PORT=8000
FRONTEND_PORT=3000
PID_FILE=".services.pid"
BACKEND_LOG="backend/uvicorn.log"
FRONTEND_LOG="frontend/nextjs.log"

# Colors
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

# Determine Python Executable
setup_python_env() {
    # If already in a virtual env, use it
    if [[ -n "$VIRTUAL_ENV" ]]; then
        PYTHON_EXEC="python"
        log_info "Using active virtual environment: $VIRTUAL_ENV"
        return
    fi

    # Check common venv locations
    local venv_dirs=(".venv" "venv" "env" "backend/.venv" "backend/venv")
    for dir in "${venv_dirs[@]}"; do
        if [[ -f "$dir/bin/python" ]]; then
            PYTHON_EXEC="$dir/bin/python"
            log_info "Found virtual environment: $dir"
            return
        fi
    done

    # Fallback to system python
    PYTHON_EXEC="python3"
    log_warn "No virtual environment found. Using system $PYTHON_EXEC."
}

# Graceful Kill Function
safe_kill() {
    local pid=$1
    local name=$2
    
    if [[ -z "$pid" ]]; then return; fi

    if ps -p "$pid" > /dev/null 2>&1; then
        log_info "Stopping $name (PID: $pid)..."
        kill "$pid" # SIGTERM
        
        # Wait up to 5 seconds
        for i in {1..5}; do
            if ! ps -p "$pid" > /dev/null 2>&1; then
                return
            fi
            sleep 1
        done

        # Force kill if still running
        if ps -p "$pid" > /dev/null 2>&1; then
            log_warn "$name did not stop gracefully. Force killing..."
            kill -9 "$pid"
        fi
    fi
}

# Install Dependencies
install_dependencies() {
    local force=$1

    # Backend
    if [[ "$force" == "true" ]]; then
        log_info "Installing backend dependencies..."
        if "$PYTHON_EXEC" -m pip install -e ".[dev]" > /dev/null 2>&1; then
            log_info "Backend dependencies installed."
        else
            log_error "Backend dependency installation failed."
        fi
    else
        log_info "Skipping backend dependency installation (use --install to force)."
    fi

    # Frontend
    if [[ "$force" == "true" || ! -d "frontend/node_modules" ]]; then
        log_info "Installing frontend dependencies..."
        if command -v npm &> /dev/null; then
            (cd frontend && npm install > /dev/null 2>&1)
            if [[ $? -eq 0 ]]; then
                log_info "Frontend dependencies installed."
            else
                log_error "Frontend dependency installation failed."
            fi
        else
            log_error "npm not found."
        fi
    else
        log_info "Skipping frontend dependency installation (node_modules exists)."
    fi
}

stop_services() {
    log_info "Stopping services..."

    # 1. Stop by PID file
    if [[ -f "$PID_FILE" ]]; then
        while read pid; do
            safe_kill "$pid" "Process"
        done < "$PID_FILE"
        rm "$PID_FILE"
    fi

    # 2. Cleanup by port (fallback)
    if command -v lsof >/dev/null 2>&1; then
        local backend_pids=$(lsof -t -i:$BACKEND_PORT)
        if [[ -n "$backend_pids" ]]; then
            for pid in $backend_pids; do
                safe_kill "$pid" "Backend (Port $BACKEND_PORT)"
            done
        fi

        local frontend_pids=$(lsof -t -i:$FRONTEND_PORT)
        if [[ -n "$frontend_pids" ]]; then
            for pid in $frontend_pids; do
                safe_kill "$pid" "Frontend (Port $FRONTEND_PORT)"
            done
        fi
    else
        log_warn "lsof not found. Skipping port-based cleanup."
    fi
    
    log_info "All services stopped."
}

start_services() {
    local force_install=$1

    # Setup Environment
    setup_python_env
    
    # Install Dependencies
    install_dependencies "$force_install"

    # Stop existing services strictly BEFORE starting new ones to avoid port conflicts
    # But check if they are running first? No, just ensure clean slate.
    stop_services

    # Create log directories
    mkdir -p "$(dirname "$BACKEND_LOG")"
    mkdir -p "$(dirname "$FRONTEND_LOG")"

    log_info "Starting Backend..."
    export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$(pwd)"
    
    # Start Backend
    nohup "$PYTHON_EXEC" -m etftool.main > "$BACKEND_LOG" 2>&1 &
    BACKEND_PID=$!
    echo $BACKEND_PID >> "$PID_FILE"
    log_info "Backend started (PID: $BACKEND_PID). Logs: $BACKEND_LOG"

    log_info "Starting Frontend..."
    # Improved approach:
    cd frontend || { log_error "Frontend directory missing"; exit 1; }
    nohup npm run dev > "../$FRONTEND_LOG" 2>&1 &
    FRONTEND_PID=$!
    cd ..
    echo $FRONTEND_PID >> "$PID_FILE"
    log_info "Frontend started (PID: $FRONTEND_PID). Logs: $FRONTEND_LOG"

    log_info "Services are up!"
    echo -e "  - Backend: http://localhost:$BACKEND_PORT"
    echo -e "  - Frontend: http://localhost:$FRONTEND_PORT"
}

check_status() {
    echo "--- Process Status ---"
    if [[ -f "$PID_FILE" ]]; then
        while read pid; do
            if ps -p "$pid" > /dev/null 2>&1; then
                echo -e "PID $pid: ${GREEN}Running${NC}"
            else
                echo -e "PID $pid: ${RED}Not Running${NC}"
            fi
        done < "$PID_FILE"
    else
        echo "No PID file found."
    fi

    echo "--- Port Status ---"
    if command -v lsof >/dev/null 2>&1; then
        if lsof -i:$BACKEND_PORT > /dev/null; then
            echo -e "Backend ($BACKEND_PORT): ${GREEN}Active${NC}"
        else
            echo -e "Backend ($BACKEND_PORT): ${RED}Inactive${NC}"
        fi

        if lsof -i:$FRONTEND_PORT > /dev/null; then
            echo -e "Frontend ($FRONTEND_PORT): ${GREEN}Active${NC}"
        else
            echo -e "Frontend ($FRONTEND_PORT): ${RED}Inactive${NC}"
        fi
    else
        log_warn "lsof not found. Cannot check port status."
        echo -e "Backend ($BACKEND_PORT): ${YELLOW}Unknown${NC}"
        echo -e "Frontend ($FRONTEND_PORT): ${YELLOW}Unknown${NC}"
    fi
}

# Main Logic
case "$1" in
    start)
        INSTALL="command -v lsof"
        if [[ "$2" == "--install" ]]; then
            INSTALL="true"
        fi
        start_services "$INSTALL"
        ;;
    stop)
        stop_services
        ;;
    restart)
        INSTALL="command -v lsof"
        if [[ "$2" == "--install" ]]; then
            INSTALL="true"
        fi
        stop_services
        start_services "$INSTALL"
        ;;
    status)
        check_status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status} [--install]"
        exit 1
        ;;
esac
