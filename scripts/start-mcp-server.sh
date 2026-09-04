#!/bin/bash
# 观心 v2 MCP Server 启动脚本
# 启动供外部客户端调用的观心 MCP 网关

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
VENV_DIR="$BACKEND_DIR/.venv"
PYTHON_CMD=${1:-python3}

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1" >&2; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1" >&2; }

cd "$BACKEND_DIR"

# 激活虚拟环境
if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
elif [ -f "$VENV_DIR/Scripts/activate" ]; then
    source "$VENV_DIR/Scripts/activate"
fi

if [ -z "${GUANXIN_API_KEY:-}" ]; then
    log_warn "缺少 GUANXIN_API_KEY；请先从 /api/auth/api-keys 获取并导出"
    exit 2
fi

log_info "启动 MCP Server (guanxin gateway)..."
log_info "上游 API: ${GUANXIN_API_BASE_URL:-http://127.0.0.1:8000/api}"
log_info "MCP Server 通过 stdio 通信，无 HTTP 端口"

exec "$PYTHON_CMD" -m app.mcp.gateway_server
