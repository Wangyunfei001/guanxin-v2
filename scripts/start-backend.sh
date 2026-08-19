#!/bin/bash
# 观心 v2 后端启动脚本

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
PYTHON_CMD=${1:-python3}
VENV_DIR="$BACKEND_DIR/.venv"

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

cd "$BACKEND_DIR"

# === 创建虚拟环境 ===
if [ ! -d "$VENV_DIR" ]; then
    log_info "创建 Python 虚拟环境..."
    "$PYTHON_CMD" -m venv "$VENV_DIR"
fi

# 激活虚拟环境
if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
elif [ -f "$VENV_DIR/Scripts/activate" ]; then
    source "$VENV_DIR/Scripts/activate"
else
    log_error "无法激活虚拟环境"
    exit 1
fi

log_info "Python: $(python --version)"
log_info "虚拟环境: $VENV_DIR"

# === 安装依赖 ===
log_info "检查并安装依赖..."
pip install --quiet -e ".[dev]" 2>/dev/null || pip install --quiet -e . 2>/dev/null || {
    log_warn "pip install -e 失败，尝试直接安装核心依赖..."
    pip install --quiet fastapi uvicorn pydantic pydantic-settings python-multipart \
        python-jose passlib chromadb langchain langchain-openai langgraph mcp httpx
}

# === 检查 .env ===
if [ ! -f "$BACKEND_DIR/.env" ]; then
    log_warn ".env 文件不存在，从 .env.example 创建..."
    cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
    log_warn "请编辑 backend/.env 配置 OPENAI_API_KEY"
fi

# === 创建数据目录 ===
mkdir -p "$BACKEND_DIR/data/chroma" "$BACKEND_DIR/data/uploads"

# === 启动服务 ===
log_info "启动后端服务..."
log_info "API: http://localhost:8000"
log_info "文档: http://localhost:8000/docs"

exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
