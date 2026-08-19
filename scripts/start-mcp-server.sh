#!/bin/bash
# 观心 v2 MCP Server 启动脚本
# 启动内置的天气查询 MCP Server

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
VENV_DIR="$BACKEND_DIR/.venv"
PYTHON_CMD=${1:-python3}

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

cd "$BACKEND_DIR"

# 激活虚拟环境
if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
elif [ -f "$VENV_DIR/Scripts/activate" ]; then
    source "$VENV_DIR/Scripts/activate"
fi

log_info "启动 MCP Server (weather)..."
log_info "MCP Server 通过 stdio 通信，无 HTTP 端口"

exec python -m app.mcp.weather_server
