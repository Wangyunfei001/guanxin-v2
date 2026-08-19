#!/bin/bash
# 观心 v2 一键启动脚本
# 用法: ./scripts/start.sh [backend|frontend|all]

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend-react"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# === 环境检查 ===
check_python() {
    if command -v python3.11 &> /dev/null; then
        echo "python3.11"
    elif command -v python3 &> /dev/null; then
        local version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null)
        local major=$(echo $version | cut -d. -f1)
        local minor=$(echo $version | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
            echo "python3"
        else
            log_error "Python 版本过低: $version (需要 3.11+)"
            return 1
        fi
    else
        log_error "未找到 Python 3.11+"
        return 1
    fi
}

check_node() {
    if command -v node &> /dev/null; then
        local version=$(node -v 2>/dev/null | sed 's/v//')
        local major=$(echo $version | cut -d. -f1)
        if [ "$major" -ge 18 ]; then
            echo "node"
        else
            log_error "Node.js 版本过低: $version (需要 18+)"
            return 1
        fi
    else
        log_error "未找到 Node.js 18+"
        return 1
    fi
}

# === 主逻辑 ===
TARGET=${1:-all}

log_info "观心 v2 启动脚本"
log_info "目标: $TARGET"
log_info "项目根目录: $PROJECT_ROOT"

if [ "$TARGET" = "backend" ] || [ "$TARGET" = "all" ]; then
    log_info "启动后端服务..."
    PYTHON_CMD=$(check_python) || exit 1
    log_info "Python: $PYTHON_CMD"
    bash "$PROJECT_ROOT/scripts/start-backend.sh" "$PYTHON_CMD" &
    BACKEND_PID=$!
    log_info "后端 PID: $BACKEND_PID"
fi

if [ "$TARGET" = "frontend" ] || [ "$TARGET" = "all" ]; then
    log_info "启动前端服务..."
    NODE_CMD=$(check_node) || exit 1
    log_info "Node: $NODE_CMD"
    bash "$PROJECT_ROOT/scripts/start-frontend.sh" &
    FRONTEND_PID=$!
    log_info "前端 PID: $FRONTEND_PID"
fi

# 等待子进程
if [ "$TARGET" = "all" ]; then
    log_info "后端和前端服务已启动"
    log_info "后端 API: http://localhost:8000"
    log_info "API 文档: http://localhost:8000/docs"
    log_info "前端页面: http://localhost:3000"
    log_info "按 Ctrl+C 停止所有服务"

    # 捕获退出信号
    trap 'kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; log_info "服务已停止"; exit 0' INT TERM

    wait
fi
