# Telegram Bot

使用 Python + python-telegram-bot + Claude CLI 建立的智能 Telegram Bot，支援 AI 對話、圖片生成等功能。

## 功能特色

- **AI 對話**：整合 Claude CLI，支援智能對話
- **圖片生成**：透過 MCP 工具（nanobanana）生成圖片
- **即時通知**：AI 處理時顯示 Tool 執行狀態
- **權限控制**：用戶白名單、群組白名單
- **群組支援**：需 @Bot 或回覆 Bot 才會回應
- **服務管理**：支援 systemd 服務安裝

## 專案結構

```
telegram-bot/
├── main.py              # 主程式
├── services/
│   └── claude_agent.py  # Claude CLI 整合
├── scripts/
│   ├── start.sh             # 啟動腳本
│   ├── install-service.sh   # 安裝 systemd 服務
│   └── uninstall-service.sh # 卸載服務
├── .env                 # 環境變數（不納入版控）
├── .env.example         # 環境變數範例
├── .mcp.json            # MCP 工具配置（不納入版控）
├── .mcp.json.example    # MCP 配置範例
├── pyproject.toml       # 專案設定
└── README.md            # 本文件
```

## 快速開始

### 1. 建立 Telegram Bot

1. 在 Telegram 找 [@BotFather](https://t.me/BotFather)
2. 發送 `/newbot` 建立新 Bot
3. 記下 **Bot Token**
4. 發送 `/setprivacy` → 選擇 Bot → `Disable`（允許收到群組訊息）

### 2. 安裝依賴

```bash
cd telegram-bot

# 安裝 uv（如果還沒有）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安裝依賴
uv sync
```

### 3. 設定環境變數

```bash
cp .env.example .env
nano .env
```

編輯 `.env`：

```bash
# ============ Telegram 設定 ============

# Bot Token（必填）
TELEGRAM_BOT_TOKEN=your_bot_token_here

# 用戶白名單（選填，逗號分隔）
# 留空 = 允許所有人
ALLOWED_USER_IDS=123456789

# 管理員 ID（選填，Bot 啟動時會收到通知）
ADMIN_USER_ID=123456789

# 群組白名單（選填，逗號分隔）
# 留空 = 不允許任何群組
ALLOWED_GROUP_IDS=-1001234567890

# ============ AI 設定 ============

# 是否啟用 AI
AI_ENABLED=true

# AI 模型（opus, sonnet, haiku）
AI_MODEL=sonnet

# 是否顯示 Tool 執行通知
AI_NOTIFY_TOOLS=true

# System Prompt
AI_SYSTEM_PROMPT=你是一個友善的助手。請用繁體中文回答。

# 允許的工具（逗號分隔）
AI_ALLOWED_TOOLS=WebSearch,WebFetch,Read

# ============ MCP 工具設定 ============

# Nanobanana 圖片生成（使用 Gemini API）
NANOBANANA_GEMINI_API_KEY=your_gemini_api_key_here
NANOBANANA_MODEL=gemini-3-pro-image-preview
```

### 4. 設定 MCP 工具（選填）

如需使用圖片生成等 MCP 工具：

```bash
cp .mcp.json.example .mcp.json
nano .mcp.json
```

編輯 `.mcp.json`，將路徑改為你的專案路徑：

```json
{
  "mcpServers": {
    "nanobanana": {
      "command": "bash",
      "args": [
        "-c",
        "set -a && source /path/to/telegram-bot/.env && set +a && uvx nanobanana-py"
      ]
    }
  }
}
```

### 5. 啟動 Bot

```bash
# 手動啟動
./scripts/start.sh

# 或安裝為系統服務（開機自動啟動）
./scripts/install-service.sh
```

### 6. 取得 ID

- **用戶 ID**：私訊 Bot 發送 `/status`
- **群組 ID**：將 Bot 加入群組後發送 `/status`

## 服務管理

### 安裝服務

```bash
./scripts/install-service.sh
```

### 常用指令

```bash
# 查看狀態
sudo systemctl status telegram-bot

# 查看日誌
journalctl -u telegram-bot -f

# 重啟服務
sudo systemctl restart telegram-bot

# 停止服務
sudo systemctl stop telegram-bot
```

### 卸載服務

```bash
./scripts/uninstall-service.sh
```

## 可用指令

| 指令 | 說明 |
|------|------|
| `/start` | 開始使用 Bot |
| `/help` | 顯示幫助 |
| `/menu` | 顯示功能選單 |
| `/status` | 查看 Bot 狀態、用戶/群組 ID |
| `/ping` | 檢查 Bot 是否在線 |

## AI 功能

### 一般對話

直接發送訊息，Bot 會使用 Claude AI 回應。

### 圖片生成

發送類似以下訊息：
- 「畫一隻貓」
- 「生成一張日落風景圖」

Bot 會使用 nanobanana MCP 工具生成圖片並發送。

### 回覆上下文

回覆（Reply）Bot 或其他訊息時，AI 會看到被回覆的內容：
- **文字**：回覆的文字會作為上下文傳給 AI
- **圖片**：回覆的圖片會下載後傳給 AI 處理（例如「把這張圖變成黑白」）

### 網頁搜尋

發送類似以下訊息：
- 「今天台北天氣如何」
- 「搜尋 Python 教學」

Bot 會使用 WebSearch 工具搜尋並回答。AI 回應中的圖片網址（.jpg/.png 等）會自動下載並傳送給用戶。

## 群組使用

### 設定步驟

1. 關閉隱私模式（見上方「建立 Telegram Bot」步驟）
2. 將 Bot 加入群組
3. 發送 `/status` 取得群組 ID
4. 將群組 ID 加入 `.env` 的 `ALLOWED_GROUP_IDS`
5. 重啟 Bot

### 回應規則

- Bot 只在被 **@提及** 或 **回覆 Bot 訊息** 時回應
- 群組必須在白名單中

## 開發指南

### 新增指令

```python
async def my_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not check_permission(update, context):
        return
    await update.message.reply_text("Hello!")

# 在 main() 中註冊
application.add_handler(CommandHandler("mycommand", my_command))
```

### 新增 MCP 工具

1. 在 `.mcp.json` 中新增 server 配置
2. 工具會自動被 Claude CLI 發現並使用

## 技術棧

| 組件 | 用途 |
|------|------|
| Python 3.11+ | 程式語言 |
| python-telegram-bot 22.x | Telegram Bot API |
| Claude CLI | AI 對話處理 |
| nanobanana-py | 圖片生成（MCP 工具）|
| httpx | 圖片 URL 下載 |
| uv | 套件管理 |

## 參考資源

- [python-telegram-bot 文件](https://docs.python-telegram-bot.org/)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Claude CLI](https://docs.anthropic.com/en/docs/claude-cli)
- [nanobanana-py](https://pypi.org/project/nanobanana-py/)

## License

MIT
