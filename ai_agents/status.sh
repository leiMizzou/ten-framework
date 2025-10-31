#!/bin/bash
#
# TEN Agent 状态检查脚本
# 检查所有服务的运行状态
#

cd "$(dirname "$0")"

echo "📊 TEN Agent 服务状态"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 检查 Docker 容器
echo "🐳 Docker 容器状态："
CONTAINER_STATUS=$(docker ps --filter "name=ten_agent_dev" --format "{{.Status}}" 2>/dev/null || echo "Not running")
if [ "$CONTAINER_STATUS" != "Not running" ]; then
    echo "  ✅ ten_agent_dev: $CONTAINER_STATUS"
else
    echo "  ❌ ten_agent_dev: 未运行"
    echo ""
    echo "💡 启动容器: docker-compose up -d"
    exit 1
fi

echo ""

# 检查服务进程
echo "⚙️  服务进程状态："
docker exec ten_agent_dev ps aux | grep -E "(bin/api|tman designer|next dev)" | grep -v grep | while read line; do
    if echo "$line" | grep -q "bin/api"; then
        echo "  ✅ Backend API 运行中 (PID: $(echo $line | awk '{print $2}'))"
    elif echo "$line" | grep -q "tman designer"; then
        echo "  ✅ TMAN Designer 运行中 (PID: $(echo $line | awk '{print $2}'))"
    elif echo "$line" | grep -q "next dev"; then
        echo "  ✅ Frontend 运行中 (PID: $(echo $line | awk '{print $2}'))"
    fi
done

echo ""

# 检查 HTTP 服务
echo "🌐 HTTP 服务状态："

API_HEALTH=$(curl -s http://localhost:8080/health 2>/dev/null | grep -o '"msg":"ok"' || echo "")
if [ "$API_HEALTH" = '"msg":"ok"' ]; then
    echo "  ✅ Backend API (8080): 正常响应"
else
    echo "  ❌ Backend API (8080): 无响应或错误"
fi

FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 2>/dev/null || echo "000")
if [ "$FRONTEND_STATUS" = "200" ]; then
    echo "  ✅ Frontend (3000): 正常响应"
else
    echo "  ❌ Frontend (3000): 无响应 (HTTP $FRONTEND_STATUS)"
fi

DESIGNER_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:49483 2>/dev/null || echo "000")
if [ "$DESIGNER_STATUS" = "200" ] || [ "$DESIGNER_STATUS" = "301" ] || [ "$DESIGNER_STATUS" = "302" ]; then
    echo "  ✅ Designer (49483): 正常响应"
else
    echo "  ⚠️  Designer (49483): 可能未启动 (HTTP $DESIGNER_STATUS)"
fi

echo ""

# 显示最近的日志
echo "📝 最近的日志 (最后 5 行)："
echo ""
echo "  Backend API:"
docker exec ten_agent_dev tail -5 /tmp/api.log 2>/dev/null | sed 's/^/    /' || echo "    (无日志)"
echo ""

echo "  Frontend:"
docker exec ten_agent_dev tail -5 /tmp/playground.log 2>/dev/null | sed 's/^/    /' || echo "    (无日志)"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💡 常用命令："
echo "  查看完整日志: docker exec ten_agent_dev tail -f /tmp/api.log"
echo "  启动服务:    ./start.sh"
echo "  停止服务:    ./stop.sh"
echo "  重启服务:    ./restart.sh"
