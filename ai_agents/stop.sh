#!/bin/bash
#
# TEN Agent 停止脚本
# 停止所有服务并关闭容器
#

set -e

cd "$(dirname "$0")"

echo "🛑 停止 TEN Agent 服务..."
echo ""

# 停止容器内的进程
echo "1️⃣ 停止容器内的服务..."
docker exec ten_agent_dev pkill -f "bin/api" 2>/dev/null || echo "  API 已停止或未运行"
docker exec ten_agent_dev pkill -f "tman designer" 2>/dev/null || echo "  Designer 已停止或未运行"
docker exec ten_agent_dev pkill -f "next dev" 2>/dev/null || echo "  Frontend 已停止或未运行"

echo ""
echo "2️⃣ 停止 Docker 容器..."
docker-compose stop

echo ""
echo "✅ 所有服务已停止！"
echo ""
echo "💡 提示："
echo "  重新启动: ./start.sh"
echo "  完全清理: docker-compose down"
