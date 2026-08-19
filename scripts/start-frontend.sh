#!/bin/bash
# 观心 v2 前端启动脚本

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/frontend-react"

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

cd "$FRONTEND_DIR"

# === 检查 node_modules ===
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    log_info "安装前端依赖..."
    npm install
fi

# === 检查 .env ===
if [ ! -f "$FRONTEND_DIR/.env" ]; then
    log_warn ".env 文件不存在，从 .env.example 创建..."
    if [ -f "$FRONTEND_DIR/.env.example" ]; then
        cp "$FRONTEND_DIR/.env.example" "$FRONTEND_DIR/.env"
    else
        echo "NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api" > "$FRONTEND_DIR/.env"
    fi
fi

# === 启动开发服务器 ===
log_info "启动前端开发服务器..."
log_info "前端页面: http://localhost:3000"

exec npx next dev --port 3000
