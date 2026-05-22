#!/bin/bash
# up_rank_week_new 一键部署脚本
# 用法: ./deploy.sh

set -e

PROJECT_DIR="$HOME/Desktop/up_rank_week_new"
NODE="/Users/haijun/.workbuddy/binaries/node/versions/22.12.0/bin/node"
LOG_DIR="$PROJECT_DIR/logs"

cd "$PROJECT_DIR"

echo "=========================================="
echo "  充电UP主分析看板 - 更新部署"
echo "=========================================="
echo ""

# 1. 拉取最新代码
echo "[1/3] 拉取最新代码..."
git fetch origin main
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    echo "  已是最新版本，无需更新。"
    echo "  当前 commit: $LOCAL"
else
    echo "  发现新版本，正在更新..."
    git pull origin main
    echo "  更新完成。"
fi
echo ""

# 2. 重启静态服务
echo "[2/3] 重启服务..."

STATIC_PIDS=$(pgrep -f "node.*up_rank_week_new/static-server.js" 2>/dev/null || true)

if [ -n "$STATIC_PIDS" ]; then
    echo "  停止旧进程 (PID: $STATIC_PIDS)..."
    kill $STATIC_PIDS 2>/dev/null || true
    sleep 1
fi

mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

nohup "$NODE" static-server.js > "$LOG_DIR/static-server_$TIMESTAMP.log" 2>&1 &
echo "  static-server 已启动 (PID: $!)"
echo ""

# 3. 验证
echo "[3/3] 验证服务状态..."
sleep 2

if pgrep -f "node.*up_rank_week_new/static-server.js" > /dev/null; then
    echo "  static-server: 运行中 (端口 8082)"
    # 获取本机IP
    LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || echo "localhost")
    echo ""
    echo "=========================================="
    echo "  部署完成！"
    echo "  访问地址: http://${LOCAL_IP}:8081"
    echo "  最新 commit: $(git log --oneline -1)"
    echo "=========================================="
else
    echo "  static-server: 启动失败！"
    echo "  请检查日志: $LOG_DIR/static-server_$TIMESTAMP.log"
fi
