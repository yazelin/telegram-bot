#!/bin/bash
# Telegram Bot 啟動腳本
# 自動清理舊進程後啟動新 Bot

cd "$(dirname "$0")/.."

echo "正在停止舊的 Bot 進程..."
pkill -f "telegram-bot.*main.py" 2>/dev/null
pkill -f "python.*main.py.*telegram" 2>/dev/null

# 等待進程完全結束
sleep 2

echo "正在啟動 Bot..."
uv run python main.py
