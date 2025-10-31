#!/bin/bash
#
# TEN Agent 重启脚本
# 先停止再启动所有服务
#

set -e

cd "$(dirname "$0")"

echo "🔄 重启 TEN Agent 服务..."
echo ""

# 停止服务
echo "【步骤 1/2】停止服务"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
./stop.sh

echo ""
echo "⏳ 等待 3 秒..."
sleep 3
echo ""

# 启动服务
echo "【步骤 2/2】启动服务"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
./start.sh

echo ""
echo "✅ 重启完成！"
