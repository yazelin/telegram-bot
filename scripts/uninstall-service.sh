#!/bin/bash
# 卸載 Telegram Bot systemd 服務

set -e

SERVICE_NAME="telegram-bot"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "正在卸載 ${SERVICE_NAME} 服務..."

# 停止服務
sudo systemctl stop "$SERVICE_NAME" 2>/dev/null || true

# 禁用服務
sudo systemctl disable "$SERVICE_NAME" 2>/dev/null || true

# 刪除 service 檔案
if [ -f "$SERVICE_FILE" ]; then
    sudo rm "$SERVICE_FILE"
    echo "已刪除 ${SERVICE_FILE}"
fi

# 重新載入 systemd
sudo systemctl daemon-reload

echo ""
echo "✅ 服務已卸載！"
