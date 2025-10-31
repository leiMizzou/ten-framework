#!/bin/bash
#
# TEN Agent 启动脚本
# 启动所有服务（Backend API、Frontend、Designer）
#

set -e

cd "$(dirname "$0")"

echo "🚀 启动 TEN Agent 服务..."
echo ""

# 启动 Docker 容器
echo "1️⃣ 启动 Docker 容器..."
docker-compose up -d

echo ""
echo "⏳ 等待容器启动..."
sleep 5

# 在容器中启动服务
echo ""
echo "2️⃣ 启动 Backend API (8080)..."
docker exec -d ten_agent_dev bash -c "cd /app/server && ./bin/api -tenapp_dir=/app/agents/examples/voice-assistant/tenapp > /tmp/api.log 2>&1"

echo ""
echo "3️⃣ 启动 TMAN Designer (49483)..."
docker exec -d ten_agent_dev bash -c "cd /app && tman designer > /tmp/tman.log 2>&1"

echo ""
echo "4️⃣ 启动 Frontend (3000)..."
docker exec -d ten_agent_dev bash -c "cd /app/playground && npm run dev > /tmp/playground.log 2>&1"

echo ""
echo "⏳ 等待服务启动..."
sleep 8

# 检查服务状态
echo ""
echo "✅ 检查服务状态..."
echo ""

API_STATUS=$(curl -s http://localhost:8080/health 2>/dev/null | grep -o '"msg":"ok"' || echo "not ready")
FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 2>/dev/null || echo "000")

if [ "$API_STATUS" = '"msg":"ok"' ]; then
    echo "✅ Backend API (8080): 运行中"
else
    echo "❌ Backend API (8080): 未就绪"
fi

if [ "$FRONTEND_STATUS" = "200" ]; then
    echo "✅ Frontend (3000): 运行中"
else
    echo "❌ Frontend (3000): 未就绪"
fi

echo ""
echo "📊 查看日志："
echo "  Backend API: docker exec ten_agent_dev tail -f /tmp/api.log"
echo "  Frontend:    docker exec ten_agent_dev tail -f /tmp/playground.log"
echo "  Designer:    docker exec ten_agent_dev tail -f /tmp/tman.log"
echo ""
echo "🌐 访问地址："
echo "  Frontend:  http://localhost:3000"
echo "  API:       http://localhost:8080"
echo "  Designer:  http://localhost:49483"
echo ""
echo "✅ 启动完成！"
