#!/bin/bash

# MySQL MCP Server (SSE) Linux后台启动脚本

echo "========================================"
echo "MySQL MCP Server (SSE Mode) - Linux"
echo "========================================"
echo ""

# 日志目录
LOG_DIR="/data02/bss/logs"
LOG_FILE="${LOG_DIR}/mysql_mcp_server.log"
PID_FILE="${LOG_DIR}/mysql_mcp_server.pid"

# 创建日志目录
if [ ! -d "$LOG_DIR" ]; then
    echo "📁 创建日志目录: $LOG_DIR"
    mkdir -p "$LOG_DIR"
    if [ $? -ne 0 ]; then
        echo "❌ 错误: 无法创建日志目录 $LOG_DIR"
        exit 1
    fi
fi

# 检查是否已有进程在运行
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "⚠️  服务已在运行 (PID: $OLD_PID)"
        echo "如需重启，请先执行: kill $OLD_PID"
        exit 1
    else
        echo "🧹 清理过期的PID文件"
        rm -f "$PID_FILE"
    fi
fi

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
echo "🚀 后台启动 SSE MCP 服务器..."
echo "========================================"
echo ""
echo "📝 日志文件: $LOG_FILE"
echo "📋 PID文件: $PID_FILE"
echo ""

# 后台启动服务器
nohup python3 mysql_mcp_server.py >> "$LOG_FILE" 2>&1 &
SERVER_PID=$!

# 保存PID
echo $SERVER_PID > "$PID_FILE"

# 等待一下确保服务启动
sleep 2

# 检查进程是否还在运行
if ps -p $SERVER_PID > /dev/null 2>&1; then
    echo "✅ 服务启动成功！"
    echo "   PID: $SERVER_PID"
    echo ""
    echo "📌 管理命令:"
    echo "   查看日志: tail -f $LOG_FILE"
    echo "   停止服务: kill $SERVER_PID"
    echo "   查看进程: ps -p $SERVER_PID"
else
    echo "❌ 服务启动失败，请查看日志："
    echo "   tail -n 50 $LOG_FILE"
    rm -f "$PID_FILE"
    exit 1
fi

echo ""
echo "========================================"
