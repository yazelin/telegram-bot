"""Claude CLI Agent 服務

使用 asyncio.subprocess 非同步呼叫 Claude CLI。
支援即時 Tool 通知回調。
"""

import asyncio
import json
import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

# Claude CLI 超時設定（秒）
DEFAULT_TIMEOUT = 180

# 工作目錄
WORKING_DIR = "/tmp/telegram-bot-cli"
os.makedirs(WORKING_DIR, exist_ok=True)

# 專案根目錄（用於找 .mcp.json）
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 預設允許的內建工具
DEFAULT_ALLOWED_TOOLS = ["WebSearch", "WebFetch", "Read"]


def _setup_mcp_config():
    """設定 MCP 配置檔（複製到工作目錄）"""
    src_mcp = os.path.join(PROJECT_DIR, ".mcp.json")
    dst_mcp = os.path.join(WORKING_DIR, ".mcp.json")

    if os.path.exists(src_mcp):
        shutil.copy2(src_mcp, dst_mcp)
        logger.debug(f"已複製 .mcp.json 到 {dst_mcp}")
    elif os.path.exists(dst_mcp):
        os.remove(dst_mcp)


# 初始化時設定 MCP
_setup_mcp_config()


def _find_claude_path() -> str:
    """尋找 Claude CLI 路徑"""
    claude_in_path = shutil.which("claude")
    if claude_in_path:
        return claude_in_path

    # 嘗試常見的 NVM 安裝路徑
    home = os.path.expanduser("~")
    nvm_paths = [
        f"{home}/.nvm/versions/node/v24.11.1/bin/claude",
        f"{home}/.nvm/versions/node/v22.11.0/bin/claude",
        f"{home}/.nvm/versions/node/v20.18.0/bin/claude",
    ]

    for path in nvm_paths:
        if os.path.exists(path):
            return path

    return "claude"


CLAUDE_PATH = _find_claude_path()

# 模型對應表
MODEL_MAP = {
    "claude-opus": "opus",
    "claude-sonnet": "sonnet",
    "claude-haiku": "haiku",
    "opus": "opus",
    "sonnet": "sonnet",
    "haiku": "haiku",
}


@dataclass
class ToolCall:
    """工具調用記錄"""
    id: str
    name: str
    input: dict
    output: str | None = None
    duration_ms: int | None = None


@dataclass
class ClaudeResponse:
    """Claude CLI 回應"""
    success: bool
    message: str
    error: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int | None = None
    output_tokens: int | None = None


# Tool 通知回調類型
ToolNotifyCallback = Callable[[str, dict], Awaitable[None]]


async def call_claude(
    prompt: str,
    model: str = "sonnet",
    system_prompt: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    on_tool_start: ToolNotifyCallback | None = None,
    on_tool_end: ToolNotifyCallback | None = None,
    allowed_tools: list[str] | None = None,
) -> ClaudeResponse:
    """非同步呼叫 Claude CLI

    Args:
        prompt: 使用者訊息
        model: 模型名稱（opus, sonnet, haiku）
        system_prompt: System prompt 內容（可選）
        timeout: 超時秒數
        on_tool_start: Tool 開始執行時的回調 (tool_name, input)
        on_tool_end: Tool 執行完成時的回調 (tool_name, result)
        allowed_tools: 允許使用的工具列表（預設為 DEFAULT_ALLOWED_TOOLS）

    Returns:
        ClaudeResponse: 回應結果
    """
    cli_model = MODEL_MAP.get(model, model)

    # 確保 MCP 配置是最新的
    _setup_mcp_config()

    # 使用預設或指定的工具列表
    tools = allowed_tools if allowed_tools is not None else DEFAULT_ALLOWED_TOOLS

    # 建立命令
    cmd = [
        CLAUDE_PATH, "-p",
        "--model", cli_model,
        "--output-format", "stream-json",
        "--verbose",
    ]

    # 添加允許的工具（使用 --permission-mode bypassPermissions 跳過互動確認）
    if tools:
        tools_str = ",".join(tools)
        cmd.extend([
            "--tools", tools_str,
            "--allowedTools", tools_str,
            "--permission-mode", "bypassPermissions",
        ])

    if system_prompt:
        cmd.extend(["--system-prompt", system_prompt])

    cmd.append(prompt)

    logger.debug(f"Claude CLI 命令: {' '.join(cmd[:5])}...")

    proc = None
    stdout_lines: list[tuple[float, str]] = []
    start_time = time.time()

    # 追蹤 tool 執行
    pending_tools: dict[str, tuple[float, ToolCall]] = {}  # id -> (start_time, tool_call)
    completed_tools: list[ToolCall] = []

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=WORKING_DIR,
            limit=10 * 1024 * 1024,
        )

        logger.debug(f"子進程已啟動，pid={proc.pid}")

        # 邊讀邊處理 stdout
        async def read_and_process_stdout():
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break

                timestamp = time.time()
                line_str = line.decode("utf-8")
                stdout_lines.append((timestamp, line_str))

                # 即時解析 JSON
                try:
                    event = json.loads(line_str)
                    await process_event(event, timestamp)
                except json.JSONDecodeError:
                    pass

        async def process_event(event: dict, timestamp: float):
            """處理 stream-json 事件"""
            event_type = event.get("type")

            if event_type == "assistant":
                message = event.get("message", {})
                contents = message.get("content", [])

                for content in contents:
                    if content.get("type") == "tool_use":
                        # Tool 開始執行
                        tool_id = content.get("id", "")
                        tool_name = content.get("name", "")
                        tool_input = content.get("input", {})

                        tool_call = ToolCall(
                            id=tool_id,
                            name=tool_name,
                            input=tool_input,
                        )
                        pending_tools[tool_id] = (timestamp, tool_call)

                        # 回調通知
                        if on_tool_start:
                            try:
                                await on_tool_start(tool_name, tool_input)
                            except Exception as e:
                                logger.warning(f"on_tool_start 回調失敗: {e}")

            elif event_type == "user":
                message = event.get("message", {})
                contents = message.get("content", [])

                for content in contents:
                    if content.get("type") == "tool_result":
                        tool_id = content.get("tool_use_id", "")

                        if tool_id in pending_tools:
                            start_ts, tool_call = pending_tools.pop(tool_id)
                            tool_call.output = content.get("content", "")
                            tool_call.duration_ms = int((timestamp - start_ts) * 1000)
                            completed_tools.append(tool_call)

                            # 回調通知
                            if on_tool_end:
                                try:
                                    await on_tool_end(tool_call.name, {
                                        "output": tool_call.output[:200] if tool_call.output else None,
                                        "duration_ms": tool_call.duration_ms,
                                    })
                                except Exception as e:
                                    logger.warning(f"on_tool_end 回調失敗: {e}")

        async def read_stderr():
            return await proc.stderr.read()

        # 等待完成
        try:
            stderr_result = await asyncio.wait_for(
                asyncio.gather(read_and_process_stdout(), read_stderr()),
                timeout=timeout,
            )
            stderr = stderr_result[1].decode("utf-8").strip() if stderr_result[1] else ""
        except asyncio.TimeoutError:
            logger.warning(f"Claude CLI 超時！已執行 {time.time() - start_time:.1f}s")
            if proc:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5)
                except asyncio.TimeoutError:
                    proc.kill()

            return ClaudeResponse(
                success=False,
                message=_extract_text_from_lines(stdout_lines),
                error=f"請求超時（{timeout} 秒）",
                tool_calls=completed_tools,
            )

        await proc.wait()

        # 解析最終結果
        result_text, input_tokens, output_tokens = _parse_final_result(stdout_lines)

        if proc.returncode != 0:
            return ClaudeResponse(
                success=False,
                message="",
                error=stderr or f"Claude CLI 執行失敗 (code: {proc.returncode})",
            )

        return ClaudeResponse(
            success=True,
            message=result_text,
            tool_calls=completed_tools,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    except FileNotFoundError:
        return ClaudeResponse(
            success=False,
            message="",
            error="找不到 Claude CLI，請確認已安裝",
        )
    except Exception as e:
        return ClaudeResponse(
            success=False,
            message="",
            error=f"呼叫 Claude CLI 時發生錯誤: {str(e)}",
        )


def _extract_text_from_lines(lines: list[tuple[float, str]]) -> str:
    """從 stream-json 行中提取文字回應"""
    result_text = ""
    for _, line in lines:
        try:
            event = json.loads(line)
            if event.get("type") == "assistant":
                for content in event.get("message", {}).get("content", []):
                    if content.get("type") == "text":
                        text = content.get("text", "")
                        if text:
                            if result_text:
                                result_text += "\n"
                            result_text += text
            elif event.get("type") == "result":
                if not result_text and event.get("result"):
                    result_text = event.get("result", "")
        except json.JSONDecodeError:
            pass
    return result_text


def _parse_final_result(lines: list[tuple[float, str]]) -> tuple[str, int | None, int | None]:
    """解析最終結果和 token 統計"""
    result_text = _extract_text_from_lines(lines)
    input_tokens = None
    output_tokens = None

    for _, line in lines:
        try:
            event = json.loads(line)
            if event.get("type") == "result":
                usage = event.get("usage", {})
                base_input = usage.get("input_tokens") or 0
                cache_creation = usage.get("cache_creation_input_tokens") or 0
                cache_read = usage.get("cache_read_input_tokens") or 0
                input_tokens = base_input + cache_creation + cache_read
                output_tokens = usage.get("output_tokens")
                break
        except json.JSONDecodeError:
            pass

    return result_text, input_tokens, output_tokens
