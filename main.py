import os
import logging
from dotenv import load_dotenv
from datetime import datetime
import re
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot, InputFile
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from services.claude_agent import call_claude, ClaudeResponse

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

# AI 設定
AI_ENABLED = os.getenv("AI_ENABLED", "true").lower() == "true"
AI_MODEL = os.getenv("AI_MODEL", "sonnet")
AI_SYSTEM_PROMPT = os.getenv("AI_SYSTEM_PROMPT", """你是一個友善的 Telegram Bot 助手。
請用繁體中文回答，保持簡潔有禮。""")
AI_NOTIFY_TOOLS = os.getenv("AI_NOTIFY_TOOLS", "true").lower() == "true"
AI_ALLOWED_TOOLS = os.getenv("AI_ALLOWED_TOOLS", "WebSearch,WebFetch,Read")


def get_allowed_tools() -> list[str]:
    """取得允許的 AI 工具列表"""
    if not AI_ALLOWED_TOOLS:
        return []
    return [t.strip() for t in AI_ALLOWED_TOOLS.split(",") if t.strip()]

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

    # AI 狀態
    ai_status = "✅ 啟用" if AI_ENABLED else "❌ 停用"

    # 取得工具列表
    tools = get_allowed_tools()
    tools_str = ", ".join(tools) if tools else "無"

    status_text = (
        f"🤖 <b>Bot 狀態</b>\n\n"
        f"✅ Bot 運行中\n"
        f"👤 用戶: {user.first_name}\n"
        f"🆔 用戶 ID: <code>{user.id}</code>\n"
        f"\n<b>AI 設定</b>\n"
        f"🧠 AI: {ai_status}\n"
        f"📦 模型: {AI_MODEL}\n"
        f"🔔 Tool 通知: {'開' if AI_NOTIFY_TOOLS else '關'}\n"
        f"🔧 工具: {tools_str}\n"
    )

    # 如果在群組中，顯示群組資訊
    if chat.type != "private":
        group_allowed = "✅" if is_group_allowed(chat.id) else "❌"
        status_text += f"\n<b>群組資訊</b>\n"
        status_text += f"👥 群組: {chat.title}\n"
        status_text += f"🆔 群組 ID: <code>{chat.id}</code>\n"
        status_text += f"📋 白名單: {group_allowed}\n"

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

# 回覆圖片暫存目錄
REPLY_IMAGE_DIR = "/tmp/telegram-bot-cli/reply-images"
os.makedirs(REPLY_IMAGE_DIR, exist_ok=True)


async def get_reply_context(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str | None:
    """取得回覆訊息的上下文

    Returns:
        上下文字串，例如 "[回覆訊息: ...]\n" 或 "[回覆圖片: path]"
        如果沒有回覆則回傳 None
    """
    reply = update.message.reply_to_message
    if not reply:
        return None

    parts = []

    # 回覆的圖片
    if reply.photo:
        try:
            # 取得最大尺寸的圖片
            photo = reply.photo[-1]
            file = await context.bot.get_file(photo.file_id)

            # 下載到暫存目錄
            file_path = os.path.join(REPLY_IMAGE_DIR, f"{photo.file_unique_id}.jpg")
            await file.download_to_drive(file_path)

            parts.append(f"[回覆圖片: {file_path}]")
            logger.info(f"下載回覆圖片: {file_path}")
        except Exception as e:
            logger.warning(f"下載回覆圖片失敗: {e}")

    # 回覆的文字（圖片的 caption 或文字訊息）
    reply_text = reply.text or reply.caption
    if reply_text:
        # 截斷過長的文字
        if len(reply_text) > 500:
            reply_text = reply_text[:500] + "..."
        parts.append(f"[回覆訊息: {reply_text}]")

    return "\n".join(parts) if parts else None


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

    text = update.message.text or ""

    # 移除 @Bot 的部分
    if BOT_USERNAME:
        text = text.replace(f"@{BOT_USERNAME}", "").strip()

    logger.info(f"收到來自 {user.first_name} ({user.id}) 的訊息: {text}")

    # 處理回覆訊息的上下文
    reply_context = await get_reply_context(update, context)
    if reply_context:
        text = f"{reply_context}\n{text}"

    # 顯示「正在輸入...」提示
    await context.bot.send_chat_action(chat_id=chat.id, action=ChatAction.TYPING)

    # 使用 AI 處理或簡單處理
    if AI_ENABLED:
        response, image_paths = await process_message_with_ai(text, chat.id, context.bot)
    else:
        response = process_message_simple(text)
        image_paths = []

    # 發送圖片（如果有）
    for img_path in image_paths:
        try:
            with open(img_path, "rb") as img_file:
                await update.message.reply_photo(photo=img_file)
            logger.info(f"已發送圖片: {img_path}")
        except Exception as e:
            logger.error(f"發送圖片失敗 {img_path}: {e}")

    # 發送文字回應
    if response:
        await update.message.reply_text(response)


def extract_image_paths_from_tool_calls(tool_calls: list) -> list[str]:
    """從 tool_calls 中提取 nanobanana 生成的圖片路徑

    nanobanana 的 tool output 格式:
    [{"text": '{"success": true, "generatedFiles": [...]}', "type": "text"}]
    """
    import json

    generated_files = []

    if not tool_calls:
        return generated_files

    # nanobanana 工具名稱
    nanobanana_tools = {
        "mcp__nanobanana__generate_image",
        "mcp__nanobanana__edit_image",
    }

    for tc in tool_calls:
        if tc.name not in nanobanana_tools:
            continue

        try:
            output = tc.output
            if not output:
                continue

            # 解析 JSON
            if isinstance(output, str):
                output_data = json.loads(output)
            else:
                output_data = output

            # 格式1: [{"text": "{...}", "type": "text"}]
            if isinstance(output_data, list) and len(output_data) > 0:
                for item in output_data:
                    if item.get("type") == "text" and item.get("text"):
                        inner_data = json.loads(item["text"])
                        if inner_data.get("success") and inner_data.get("generatedFiles"):
                            generated_files.extend(inner_data["generatedFiles"])
            elif isinstance(output_data, dict):
                # 格式2: {"result": "{...json...}"}
                if "result" in output_data:
                    result_data = json.loads(output_data["result"])
                    if result_data.get("success") and result_data.get("generatedFiles"):
                        generated_files.extend(result_data["generatedFiles"])
                # 格式3: {"success": true, "generatedFiles": [...]}
                elif output_data.get("success") and output_data.get("generatedFiles"):
                    generated_files.extend(output_data["generatedFiles"])

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"解析 nanobanana 輸出失敗: {e}")

    # 去重複並過濾存在的檔案
    seen = set()
    unique_paths = []
    for p in generated_files:
        if p not in seen and os.path.exists(p):
            seen.add(p)
            unique_paths.append(p)

    return unique_paths


def extract_image_urls(text: str) -> list[str]:
    """從文字中提取圖片 URL"""
    pattern = r'https?://[^\s\n\[\]()<>\"\']+\.(?:jpg|jpeg|png|gif|webp)(?:\?[^\s\n\[\]()<>\"\']*)?'
    urls = re.findall(pattern, text, re.IGNORECASE)
    # 去重
    seen = set()
    unique = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


async def download_image_from_url(url: str) -> str | None:
    """下載圖片 URL 到暫存目錄，回傳本地路徑"""
    download_dir = "/tmp/telegram-bot-cli/downloaded-images"
    os.makedirs(download_dir, exist_ok=True)

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                logger.warning(f"下載圖片失敗 HTTP {resp.status_code}: {url}")
                return None

            content_type = resp.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                logger.warning(f"非圖片內容 {content_type}: {url}")
                return None

            # 從 URL 取得副檔名
            ext = ".jpg"
            for e in [".png", ".gif", ".webp", ".jpeg"]:
                if e in url.lower():
                    ext = e
                    break

            import hashlib
            filename = hashlib.md5(url.encode()).hexdigest()[:12] + ext
            file_path = os.path.join(download_dir, filename)

            with open(file_path, "wb") as f:
                f.write(resp.content)

            logger.info(f"下載圖片成功: {url} -> {file_path}")
            return file_path

    except Exception as e:
        logger.warning(f"下載圖片異常: {url}: {e}")
        return None


def extract_image_paths_from_text(text: str) -> list[str]:
    """從文字中提取圖片路徑（備用方案）"""
    # 匹配常見的圖片路徑模式
    patterns = [
        r'/tmp/[^\s\n\[\]()]+\.(?:jpg|jpeg|png|gif|webp)',
        r'nanobanana-output/[^\s\n\[\]()]+\.(?:jpg|jpeg|png|gif|webp)',
    ]

    paths = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        paths.extend(matches)

    # 處理相對路徑
    result = []
    for path in paths:
        if path.startswith('/'):
            result.append(path)
        else:
            full_path = f"/tmp/telegram-bot-cli/{path}"
            result.append(full_path)

    # 去重複並過濾出實際存在的檔案
    seen = set()
    unique_paths = []
    for p in result:
        if p not in seen and os.path.exists(p):
            seen.add(p)
            unique_paths.append(p)
    return unique_paths


async def process_message_with_ai(text: str, chat_id: int, bot: Bot) -> tuple[str, list[str]]:
    """使用 Claude AI 處理訊息

    Returns:
        tuple[str, list[str]]: (回應文字, 圖片路徑列表)
    """
    # Tool 通知訊息 ID（用於更新同一條訊息）
    notify_message_id = None
    tool_status_lines = []

    async def on_tool_start(tool_name: str, tool_input: dict):
        """Tool 開始執行時的回調"""
        nonlocal notify_message_id, tool_status_lines

        if not AI_NOTIFY_TOOLS:
            return

        # 格式化輸入參數（簡短顯示）
        input_str = ""
        if tool_input:
            # 只顯示前幾個參數
            items = list(tool_input.items())[:2]
            input_str = ", ".join(f"{k}={repr(v)[:30]}" for k, v in items)
            if len(tool_input) > 2:
                input_str += ", ..."

        status_line = f"🔧 <code>{tool_name}</code>"
        if input_str:
            status_line += f"\n   └ {input_str}"
        status_line += "\n   ⏳ 執行中..."

        tool_status_lines.append({"name": tool_name, "status": "running", "line": status_line})

        # 組合所有 tool 狀態
        full_text = "🤖 <b>AI 處理中</b>\n\n" + "\n\n".join(t["line"] for t in tool_status_lines)

        try:
            if notify_message_id is None:
                msg = await bot.send_message(
                    chat_id=chat_id,
                    text=full_text,
                    parse_mode="HTML",
                )
                notify_message_id = msg.message_id
            else:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=notify_message_id,
                    text=full_text,
                    parse_mode="HTML",
                )
        except Exception as e:
            logger.warning(f"發送 tool 通知失敗: {e}")

    async def on_tool_end(tool_name: str, result: dict):
        """Tool 執行完成時的回調"""
        nonlocal tool_status_lines

        if not AI_NOTIFY_TOOLS:
            return

        duration_ms = result.get("duration_ms", 0)
        duration_str = f"{duration_ms}ms" if duration_ms < 1000 else f"{duration_ms/1000:.1f}s"

        # 更新對應 tool 的狀態
        for tool in tool_status_lines:
            if tool["name"] == tool_name and tool["status"] == "running":
                # 更新為完成狀態
                tool["status"] = "done"
                tool["line"] = tool["line"].replace("⏳ 執行中...", f"✅ 完成 ({duration_str})")
                break

        # 更新訊息
        full_text = "🤖 <b>AI 處理中</b>\n\n" + "\n\n".join(t["line"] for t in tool_status_lines)

        try:
            if notify_message_id:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=notify_message_id,
                    text=full_text,
                    parse_mode="HTML",
                )
        except Exception as e:
            logger.warning(f"更新 tool 通知失敗: {e}")

    # 呼叫 Claude
    result: ClaudeResponse = await call_claude(
        prompt=text,
        model=AI_MODEL,
        system_prompt=AI_SYSTEM_PROMPT,
        on_tool_start=on_tool_start,
        on_tool_end=on_tool_end,
        allowed_tools=get_allowed_tools(),
    )

    # 刪除 tool 通知訊息（如果有）
    if notify_message_id and AI_NOTIFY_TOOLS:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=notify_message_id)
        except Exception as e:
            logger.warning(f"刪除 tool 通知失敗: {e}")

    if result.success:
        response = result.message

        # Debug: 記錄 tool_calls 資訊
        if result.tool_calls:
            for tc in result.tool_calls:
                logger.info(f"Tool: {tc.name}, output 長度: {len(tc.output) if tc.output else 0}, output 前200字: {(tc.output or '')[:200]}")

        # 從 tool_calls 提取圖片路徑（優先）
        image_paths = extract_image_paths_from_tool_calls(result.tool_calls)

        # 備用：從回應文字提取本地圖片路徑
        if not image_paths:
            image_paths = extract_image_paths_from_text(response)

        # 從回應文字提取圖片 URL 並下載
        image_urls = extract_image_urls(response)
        if image_urls:
            logger.info(f"偵測到 {len(image_urls)} 個圖片 URL，開始下載...")
            for url in image_urls[:5]:  # 最多下載 5 張
                local_path = await download_image_from_url(url)
                if local_path:
                    image_paths.append(local_path)

        if image_paths:
            logger.info(f"提取到 {len(image_paths)} 張圖片: {image_paths}")

        # 如果有 tool 調用，附加統計
        if result.tool_calls:
            tool_summary = "\n".join(
                f"• {t.name} ({t.duration_ms}ms)" for t in result.tool_calls
            )
            response += f"\n\n📊 使用了 {len(result.tool_calls)} 個工具:\n{tool_summary}"
    else:
        response = f"❌ AI 處理失敗: {result.error}"
        image_paths = []

    return response, image_paths


def process_message_simple(text: str) -> str:
    """簡單的訊息處理（不使用 AI）"""
    text_lower = text.lower()

    if "你好" in text or "hello" in text_lower or "hi" in text_lower:
        return "你好！有什麼我可以幫助你的嗎？ 😊"

    if "謝謝" in text or "thank" in text_lower:
        return "不客氣！隨時為你服務！ 🙏"

    if "時間" in text or "time" in text_lower:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"🕐 現在時間: {now}"

    return f"📝 收到你的訊息：\n「{text}」\n\n（AI 未啟用）"


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
