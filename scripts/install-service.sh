#!/bin/bash
# 安裝 Telegram Bot 為 systemd 服務

set -e

SERVICE_NAME="telegram-bot"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# 取得實際使用者（不是 sudo 後的 root）
if [ -n "$SUDO_USER" ]; then
    ACTUAL_USER="$SUDO_USER"
else
    ACTUAL_USER="$(whoami)"
fi

# 取得 uv 路徑
UV_PATH="/home/${ACTUAL_USER}/.local/bin/uv"
if [ ! -f "$UV_PATH" ]; then
    UV_PATH="$(which uv 2>/dev/null || echo "")"
fi

if [ -z "$UV_PATH" ] || [ ! -f "$UV_PATH" ]; then
    echo "❌ 找不到 uv，請先安裝: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "正在安裝 ${SERVICE_NAME} 服務..."
echo "  使用者: ${ACTUAL_USER}"
echo "  專案目錄: ${PROJECT_DIR}"
echo "  uv 路徑: ${UV_PATH}"

# 建立 systemd service 檔案
sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=Telegram Bot
After=network.target

[Service]
Type=simple
User=${ACTUAL_USER}
WorkingDirectory=${PROJECT_DIR}
ExecStart=${UV_PATH} run python main.py
Restart=always
RestartSec=10
Environment=PATH=/home/${ACTUAL_USER}/.local/bin:/usr/local/bin:/usr/bin:/bin

[Install]
WantedBy=multi-user.target
EOF

# 重新載入 systemd
sudo systemctl daemon-reload

# 啟用並啟動服務
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo ""
echo "✅ 服務安裝完成！"
echo ""
echo "常用指令："
echo "  查看狀態: systemctl status ${SERVICE_NAME}"
echo "  查看日誌: journalctl -u ${SERVICE_NAME} -f"
echo "  重啟服務: sudo systemctl restart ${SERVICE_NAME}"
echo "  停止服務: sudo systemctl stop ${SERVICE_NAME}"
