# Telegram Bot 範例專案

一個使用 Python + python-telegram-bot 建立的 Telegram Bot 範例專案，展示基本的 Bot 開發模式，包含指令處理、按鈕互動、權限控制等功能。

## 功能特色

- **指令處理**：`/start`、`/help`、`/menu`、`/status`、`/ping`
- **互動式按鈕**：使用 InlineKeyboardButton 建立選單
- **權限控制**：
  - 用戶白名單（私人對話）
  - 群組白名單（群組對話）
- **群組支援**：需 @Bot 或回覆 Bot 才會回應（避免打擾）
- **訊息處理**：可擴展的訊息處理邏輯（預留 AI 整合接口）
- **在線狀態**：
  - `/ping` 快速檢測 Bot 是否在線
  - 啟動時自動通知管理員
  - 處理訊息時顯示「正在輸入...」提示

## 專案結構

```
telegram-bot/
├── main.py           # 主程式（所有邏輯）
├── .env              # 環境變數（不納入版控）
├── .env.example      # 環境變數範例
├── .gitignore        # Git 忽略設定
├── pyproject.toml    # 專案設定（uv 套件管理）
├── uv.lock           # 依賴鎖定檔
└── README.md         # 本文件
```

## 快速開始

### 1. 建立 Bot

1. 在 Telegram 中找到 [@BotFather](https://t.me/BotFather)
2. 發送 `/newbot` 建立新 Bot
3. 記下取得的 **Bot Token**

### 2. 安裝專案

```bash
# 進入專案目錄
cd ~/SDD/telegram-bot

# 複製環境變數範例
cp .env.example .env

# 編輯 .env，填入 Bot Token
nano .env
```

### 3. 設定環境變數

編輯 `.env` 檔案：

```bash
# 必填：Bot Token
TELEGRAM_BOT_TOKEN=your_bot_token_here

# 選填：用戶白名單（私人對話限制）
# 留空 = 允許所有人
ALLOWED_USER_IDS=123456789,987654321

# 選填：管理員 ID（Bot 啟動時會收到通知）
ADMIN_USER_ID=123456789

# 選填：群組白名單
# 留空 = 不允許任何群組
ALLOWED_GROUP_IDS=-1001234567890
```

### 4. 啟動 Bot

```bash
uv run main.py
```

### 5. 取得 ID

- **用戶 ID**：私訊 Bot 發送 `/status`
- **群組 ID**：將 Bot 加入群組後發送 `/status`

## 程式碼架構說明

### main.py 結構

```python
# ============ 環境設定 ============
# - 載入 .env
# - 設定日誌
# - 讀取環境變數

# ============ 權限控制函式 ============
# - get_admin_id()           # 取得管理員 ID
# - get_allowed_users()      # 取得用戶白名單
# - get_allowed_groups()     # 取得群組白名單
# - is_user_allowed()        # 檢查用戶權限
# - is_group_allowed()       # 檢查群組權限
# - is_mentioned()           # 檢查是否被 @提及
# - check_permission()       # 統一權限檢查

# ============ 指令處理 ============
# - start()                  # /start 指令
# - help_command()           # /help 指令
# - menu_command()           # /menu 指令
# - status_command()         # /status 指令
# - ping_command()           # /ping 指令（檢測在線）

# ============ 訊息處理 ============
# - handle_message()         # 處理文字訊息
# - process_message()        # 訊息處理邏輯（可擴展）

# ============ 按鈕回調處理 ============
# - button_callback()        # 統一處理按鈕點擊
# - show_main_menu()         # 顯示主選單
# - show_menu_inline()       # 顯示功能選單
# - show_about()             # 顯示關於
# - show_settings()          # 顯示設定
# - show_help_inline()       # 顯示幫助
# - handle_task()            # 處理任務按鈕

# ============ 錯誤處理 ============
# - error_handler()          # 統一錯誤處理

# ============ 主程式 ============
# - post_init()              # Bot 啟動後初始化（通知管理員）
# - main()                   # 程式入口
```

## 開發指南

### 新增指令

1. 建立指令處理函式：

```python
async def my_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """處理 /mycommand 指令"""
    # 權限檢查
    if not check_permission(update, context):
        return

    # 你的邏輯
    await update.message.reply_text("Hello!")
```

2. 在 `main()` 中註冊：

```python
application.add_handler(CommandHandler("mycommand", my_command))
```

### 新增按鈕

1. 在適當位置建立按鈕：

```python
keyboard = [
    [InlineKeyboardButton("按鈕文字", callback_data="my_action")],
]
reply_markup = InlineKeyboardMarkup(keyboard)
await update.message.reply_text("選擇：", reply_markup=reply_markup)
```

2. 在 `button_callback()` 中處理：

```python
elif callback_data == "my_action":
    await my_action_handler(query)
```

### 整合 AI 處理

修改 `process_message()` 函式：

```python
def process_message(text: str) -> str:
    """處理用戶訊息的核心邏輯"""

    # 呼叫 AI API（範例）
    # response = call_ai_api(text)
    # return response

    # 或整合 ching-tech-os 的 AI 服務
    # response = await ai_service.process(text)
    # return response

    return f"收到：{text}"
```

### 新增任務處理

修改 `handle_task()` 函式：

```python
async def handle_task(query, callback_data: str) -> None:
    """處理任務按鈕"""
    task_num = callback_data.split("_")[1]

    if task_num == "1":
        # 任務 1 的邏輯
        result = "任務 1 完成"
    elif task_num == "2":
        # 任務 2 的邏輯
        result = "任務 2 完成"
    else:
        result = "未知任務"

    await query.edit_message_text(result)
```

## 群組使用注意事項

### 關閉隱私模式

預設情況下，Bot 在群組中只能收到 `/command` 指令。若要讓 Bot 收到所有訊息（包含 @提及）：

1. 找 [@BotFather](https://t.me/BotFather)
2. 發送 `/setprivacy`
3. 選擇你的 Bot
4. 選擇 `Disable`
5. **重新將 Bot 移出並加回群組**（設定才會生效）

### 群組中的回應規則

- Bot 只會在被 **@提及** 或 **回覆 Bot 訊息** 時回應
- 群組必須在 `ALLOWED_GROUP_IDS` 白名單中
- `/status` 指令可在任何群組中使用（方便取得群組 ID）

## 整合到 ching-tech-os

此專案設計為可輕鬆整合到 ching-tech-os 系統。整合步驟：

### 方法一：作為獨立 Service

將程式碼重構為 service 模組，放入 ching-tech-os：

```
backend/src/ching_tech_os/
├── services/
│   ├── telegram.py          # 訊息處理（參考 linebot.py）
│   └── telegram_ai.py       # AI 整合（參考 linebot_ai.py）
├── api/
│   └── telegram_router.py   # Webhook API
└── models/
    └── telegram.py          # 資料模型
```

### 方法二：使用 Webhook

改用 Webhook 模式，由 FastAPI 接收 Telegram 更新：

```python
# telegram_router.py
@router.post("/webhook")
async def telegram_webhook(request: Request):
    update = Update.de_json(await request.json(), bot)
    await application.process_update(update)
    return {"ok": True}
```

### 環境變數整合

在 ching-tech-os 的 `config.py` 中新增：

```python
# Telegram Bot
telegram_bot_token: str = _get_env("TELEGRAM_BOT_TOKEN", required=True)
telegram_allowed_users: str = _get_env("TELEGRAM_ALLOWED_USER_IDS", "")
telegram_allowed_groups: str = _get_env("TELEGRAM_ALLOWED_GROUP_IDS", "")
```

## 技術棧

| 組件 | 版本 | 用途 |
|------|------|------|
| Python | 3.11+ | 程式語言 |
| python-telegram-bot | 22.x | Telegram Bot API |
| python-dotenv | 1.x | 環境變數管理 |
| uv | - | 套件管理 |

## 參考資源

- [python-telegram-bot 文件](https://docs.python-telegram-bot.org/)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [ching-tech-os Line Bot 實現](../ching-tech-os/backend/src/ching_tech_os/services/linebot.py)

## License

MIT
