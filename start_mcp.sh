#!/bin/bash

# MySQL MCP Server (SSE) 一键启动脚本

echo "========================================"
echo "MySQL MCP Server (SSE Mode)"
echo "========================================"
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到 Python"
    exit 1
fi

# 检查虚拟环境
if [ -d ".venv" ]; then
    echo "📦 使用虚拟环境..."
    source .venv/bin/activate
fi

# 检查依赖
echo "🔍 检查依赖..."
python3 -c "import mcp; import starlette; import uvicorn" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "📥 安装依赖..."
    pip install -r requirements.txt
fi

echo ""
echo "========================================"
echo "🚀 启动 SSE MCP 服务器..."
echo "========================================"
echo ""

# 启动 SSE 服务器
python3 mysql_mcp_server.py
