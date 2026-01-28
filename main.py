import os
import logging
from dotenv import load_dotenv
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# 載入環境變數
load_dotenv()

# 設定日誌
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# 從環境變數取得設定
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_IDS = os.getenv("ALLOWED_USER_IDS", "")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID", "")
ALLOWED_GROUP_IDS = os.getenv("ALLOWED_GROUP_IDS", "")

# Bot 用戶名（啟動時會自動取得）
BOT_USERNAME = None
# Bot 啟動時間
BOT_START_TIME = None


def get_admin_id() -> int | None:
    """取得管理員 ID"""
    if ADMIN_USER_ID:
        try:
            return int(ADMIN_USER_ID.strip())
        except ValueError:
            return None
    return None


def get_allowed_users() -> set[int]:
    """取得允許的用戶 ID 列表"""
    if not ALLOWED_USER_IDS:
        return set()
    return {int(uid.strip()) for uid in ALLOWED_USER_IDS.split(",") if uid.strip()}


def get_allowed_groups() -> set[int]:
    """取得允許的群組 ID 列表"""
    if not ALLOWED_GROUP_IDS:
        return set()
    return {int(gid.strip()) for gid in ALLOWED_GROUP_IDS.split(",") if gid.strip()}


def is_user_allowed(user_id: int) -> bool:
    """檢查用戶是否被允許使用 bot"""
    allowed = get_allowed_users()
    # 如果沒有設定白名單，則允許所有人
    if not allowed:
        return True
    return user_id in allowed


def is_group_allowed(chat_id: int) -> bool:
    """檢查群組是否被允許使用 bot"""
    allowed = get_allowed_groups()
    # 如果沒有設定群組白名單，則不允許任何群組
    if not allowed:
        return False
    return chat_id in allowed


def is_private_chat(update: Update) -> bool:
    """檢查是否為私人對話"""
    return update.effective_chat.type == "private"


def is_mentioned(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """檢查訊息是否有 @提及 Bot"""
    message = update.message
    if not message:
        return False

    # 檢查是否為回覆 Bot 的訊息
    if message.reply_to_message and message.reply_to_message.from_user:
        if message.reply_to_message.from_user.id == context.bot.id:
            return True

    # 檢查訊息中是否有 @Bot
    if message.entities:
        for entity in message.entities:
            if entity.type == "mention":
                mention_text = message.text[entity.offset:entity.offset + entity.length]
                if BOT_USERNAME and mention_text.lower() == f"@{BOT_USERNAME.lower()}":
                    return True

    # 也檢查文字中是否直接包含 @username（備用方案）
    if message.text and BOT_USERNAME:
        if f"@{BOT_USERNAME.lower()}" in message.text.lower():
            return True

    return False


def check_permission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """統一檢查權限（用戶 + 群組）"""
    user = update.effective_user
    chat = update.effective_chat

    # 檢查用戶權限
    if not is_user_allowed(user.id):
        return False

    # 私人對話直接允許
    if chat.type == "private":
        return True

    # 群組對話檢查群組白名單
    return is_group_allowed(chat.id)


# ============ 指令處理 ============


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """處理 /start 指令"""
    if not check_permission(update, context):
        return

    user = update.effective_user
    keyboard = [
        [
            InlineKeyboardButton("📋 功能選單", callback_data="menu"),
            InlineKeyboardButton("ℹ️ 關於", callback_data="about"),
        ],
        [
            InlineKeyboardButton("⚙️ 設定", callback_data="settings"),
            InlineKeyboardButton("❓ 幫助", callback_data="help"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"你好 {user.first_name}！👋\n\n"
        "我是你的智能助手 Bot，可以幫你處理各種日常事務。\n\n"
        "請選擇下方按鈕或直接輸入訊息：",
        reply_markup=reply_markup,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """處理 /help 指令"""
    if not check_permission(update, context):
        return

    help_text = """
📖 **使用說明**

**可用指令：**
/start - 開始使用 Bot
/help - 顯示此幫助訊息
/menu - 顯示功能選單
/status - 查看 Bot 狀態
/ping - 檢查 Bot 是否在線

**功能說明：**
• 直接輸入文字訊息，Bot 會進行處理後回應
• 使用按鈕快速存取常用功能
• 未來可整合 AI 處理日常事務

有問題請聯繫管理員！
"""
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """處理 /menu 指令"""
    if not check_permission(update, context):
        return
    await show_main_menu(update, context)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """處理 /status 指令 (只檢查用戶權限，方便取得群組 ID)"""
    user = update.effective_user
    if not is_user_allowed(user.id):
        return

    chat = update.effective_chat

    status_text = (
        f"🤖 <b>Bot 狀態</b>\n\n"
        f"✅ Bot 運行中\n"
        f"👤 用戶: {user.first_name}\n"
        f"🆔 用戶 ID: <code>{user.id}</code>\n"
    )

    # 如果在群組中，顯示群組資訊
    if chat.type != "private":
        group_allowed = "✅" if is_group_allowed(chat.id) else "❌"
        status_text += f"👥 群組: {chat.title}\n"
        status_text += f"🆔 群組 ID: <code>{chat.id}</code>\n"
        status_text += f"📋 群組白名單: {group_allowed}\n"

    await update.message.reply_text(status_text, parse_mode="HTML")


async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """處理 /ping 指令 - 快速檢查 Bot 是否在線"""
    # 計算運行時間
    if BOT_START_TIME:
        uptime = datetime.now() - BOT_START_TIME
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{hours}h {minutes}m {seconds}s"
    else:
        uptime_str = "未知"

    await update.message.reply_text(
        f"🟢 Pong! Bot 運行中\n"
        f"⏱️ 已運行: {uptime_str}"
    )


# ============ 訊息處理 ============


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """處理一般文字訊息"""
    user = update.effective_user
    chat = update.effective_chat

    # 檢查用戶權限
    if not is_user_allowed(user.id):
        return

    # 群組中必須 @Bot 或回覆 Bot 才會回應
    if chat.type != "private":
        # 檢查群組是否在白名單
        if not is_group_allowed(chat.id):
            return
        # 檢查是否有 @提及 Bot
        if not is_mentioned(update, context):
            return

    text = update.message.text

    # 移除 @Bot 的部分
    if BOT_USERNAME:
        text = text.replace(f"@{BOT_USERNAME}", "").strip()

    logger.info(f"收到來自 {user.first_name} ({user.id}) 的訊息: {text}")

    # 顯示「正在輸入...」提示
    await context.bot.send_chat_action(chat_id=chat.id, action=ChatAction.TYPING)

    # 這裡可以加入訊息處理邏輯
    # 例如：呼叫 AI API、執行特定任務等
    processed_response = process_message(text)

    await update.message.reply_text(processed_response)


def process_message(text: str) -> str:
    """
    處理用戶訊息的核心邏輯
    未來可以在這裡整合 AI 處理
    """
    # 簡單的示範處理
    text_lower = text.lower()

    if "你好" in text or "hello" in text_lower or "hi" in text_lower:
        return "你好！有什麼我可以幫助你的嗎？ 😊"

    if "謝謝" in text or "thank" in text_lower:
        return "不客氣！隨時為你服務！ 🙏"

    if "時間" in text or "time" in text_lower:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"🕐 現在時間: {now}"

    # 預設回應 - 未來可替換為 AI 回應
    return f"📝 收到你的訊息：\n「{text}」\n\n（這裡未來可以接入 AI 處理）"


# ============ 按鈕回調處理 ============


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """處理按鈕點擊回調"""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    if not is_user_allowed(user.id):
        await query.edit_message_text("抱歉，你沒有權限使用此 Bot。")
        return

    callback_data = query.data

    if callback_data == "menu":
        await show_menu_inline(query)
    elif callback_data == "about":
        await show_about(query)
    elif callback_data == "settings":
        await show_settings(query)
    elif callback_data == "help":
        await show_help_inline(query)
    elif callback_data == "back":
        await show_main_menu_inline(query)
    elif callback_data.startswith("task_"):
        await handle_task(query, callback_data)
    else:
        await query.edit_message_text(f"未知的操作: {callback_data}")


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """顯示主選單"""
    keyboard = [
        [
            InlineKeyboardButton("📋 功能選單", callback_data="menu"),
            InlineKeyboardButton("ℹ️ 關於", callback_data="about"),
        ],
        [
            InlineKeyboardButton("⚙️ 設定", callback_data="settings"),
            InlineKeyboardButton("❓ 幫助", callback_data="help"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("請選擇功能：", reply_markup=reply_markup)


async def show_main_menu_inline(query) -> None:
    """內聯顯示主選單"""
    keyboard = [
        [
            InlineKeyboardButton("📋 功能選單", callback_data="menu"),
            InlineKeyboardButton("ℹ️ 關於", callback_data="about"),
        ],
        [
            InlineKeyboardButton("⚙️ 設定", callback_data="settings"),
            InlineKeyboardButton("❓ 幫助", callback_data="help"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("請選擇功能：", reply_markup=reply_markup)


async def show_menu_inline(query) -> None:
    """顯示功能選單"""
    keyboard = [
        [
            InlineKeyboardButton("📝 任務 1", callback_data="task_1"),
            InlineKeyboardButton("📊 任務 2", callback_data="task_2"),
        ],
        [
            InlineKeyboardButton("🔔 任務 3", callback_data="task_3"),
            InlineKeyboardButton("📅 任務 4", callback_data="task_4"),
        ],
        [InlineKeyboardButton("◀️ 返回", callback_data="back")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "📋 **功能選單**\n\n選擇要執行的任務：",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )


async def show_about(query) -> None:
    """顯示關於資訊"""
    keyboard = [[InlineKeyboardButton("◀️ 返回", callback_data="back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "ℹ️ **關於此 Bot**\n\n"
        "版本: 1.0.0\n"
        "用途: 日常事務處理助手\n"
        "技術: Python + python-telegram-bot\n\n"
        "未來功能:\n"
        "• AI 對話整合\n"
        "• 自動化任務\n"
        "• 提醒功能",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )


async def show_settings(query) -> None:
    """顯示設定頁面"""
    keyboard = [[InlineKeyboardButton("◀️ 返回", callback_data="back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "⚙️ **設定**\n\n" "目前沒有可用的設定項目。\n" "未來版本將加入更多自訂選項。",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )


async def show_help_inline(query) -> None:
    """內聯顯示幫助"""
    keyboard = [[InlineKeyboardButton("◀️ 返回", callback_data="back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "❓ **幫助**\n\n"
        "**指令:**\n"
        "/start - 開始\n"
        "/help - 幫助\n"
        "/menu - 選單\n"
        "/status - 狀態\n"
        "/ping - 檢測在線\n\n"
        "直接輸入訊息即可與 Bot 互動！",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )


async def handle_task(query, callback_data: str) -> None:
    """處理任務按鈕"""
    task_num = callback_data.split("_")[1]
    keyboard = [[InlineKeyboardButton("◀️ 返回選單", callback_data="menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # 這裡可以根據不同任務執行不同邏輯
    await query.edit_message_text(
        f"🔄 正在執行任務 {task_num}...\n\n"
        f"（這裡可以加入實際的任務處理邏輯）\n\n"
        f"✅ 任務 {task_num} 完成！",
        reply_markup=reply_markup,
    )


# ============ 錯誤處理 ============


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """處理錯誤"""
    logger.error(f"發生錯誤: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text("抱歉，發生了錯誤。請稍後再試。")


# ============ 主程式 ============


async def post_init(application: Application) -> None:
    """Bot 啟動後的初始化"""
    global BOT_USERNAME, BOT_START_TIME
    bot = await application.bot.get_me()
    BOT_USERNAME = bot.username
    BOT_START_TIME = datetime.now()
    logger.info(f"Bot 用戶名: @{BOT_USERNAME}")

    # 通知管理員 Bot 已啟動
    admin_id = get_admin_id()
    if admin_id:
        try:
            await application.bot.send_message(
                chat_id=admin_id,
                text=(
                    f"🟢 <b>Bot 已上線</b>\n\n"
                    f"🤖 @{BOT_USERNAME}\n"
                    f"🕐 {BOT_START_TIME.strftime('%Y-%m-%d %H:%M:%S')}"
                ),
                parse_mode="HTML",
            )
            logger.info(f"已通知管理員 {admin_id} Bot 啟動")
        except Exception as e:
            logger.warning(f"無法通知管理員: {e}")


def main() -> None:
    """啟動 Bot"""
    if not BOT_TOKEN:
        logger.error("請設定 TELEGRAM_BOT_TOKEN 環境變數！")
        print("錯誤: 請在 .env 檔案中設定 TELEGRAM_BOT_TOKEN")
        return

    # 建立 Application
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # 註冊指令處理器
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("ping", ping_command))

    # 註冊按鈕回調處理器
    application.add_handler(CallbackQueryHandler(button_callback))

    # 註冊訊息處理器 (放在最後)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # 註冊錯誤處理器
    application.add_error_handler(error_handler)

    # 啟動 Bot
    logger.info("Bot 啟動中...")
    print("🤖 Bot 已啟動！按 Ctrl+C 停止。")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
