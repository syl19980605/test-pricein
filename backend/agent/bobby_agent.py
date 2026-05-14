import json
import re
import uuid
from typing import AsyncGenerator, Optional

from backend.agent.llm import get_client, MODEL
from backend.agent.prompts import SYSTEM_PROMPT
from backend.agent.tools import BOBBY_TOOLS
from backend.agent.tool_executor import execute_tool
from backend.models.database import get_db

MAX_TOOL_ROUNDS = 6

# 明确的"交易执行指令"关键词。命中这些词时，用户是要 Bobby 真的去开仓/平仓，
# 而不是分析 —— 此时强制走 manage_position，不再依赖 MiMo 在重历史下的工具选择。
_TRADE_VERBS = ("挂单", "开仓", "平仓", "做多", "做空", "建仓", "清仓")
_TRADE_BUY_SELL = re.compile(r"(帮我|模拟|给我).{0,6}(买入|卖出)")


def _is_trade_instruction(message: str) -> bool:
    """判断用户消息是否是明确的交易执行指令。"""
    if any(v in message for v in _TRADE_VERBS):
        return True
    # 「帮我买入」「模拟卖出」这类，且通常带止损/止盈/数量
    if _TRADE_BUY_SELL.search(message) and any(
        k in message for k in ("止损", "止盈", "股", "仓")
    ):
        return True
    return False


# 当检测到交易执行指令时，紧贴用户消息注入这条指令 —— 位置在上下文末尾，
# 不会被前面大段分析历史淹没。
_TRADE_DIRECTIVE = (
    "\n\n[系统指令：用户上面是明确的交易执行指令（已给出标的/方向/数量/止损止盈）。"
    "请立即调用 manage_position 工具执行 action=open，不要只做分析、不要只做口头确认。"
    "用户的明确指示本身就是确认。]"
)


class BobbyAgent:
    async def chat(
        self, message: str, conversation_id: Optional[str] = None,
        action: Optional[dict] = None,
    ) -> AsyncGenerator[dict, None]:
        conversation_id = conversation_id or str(uuid.uuid4())
        yield {"type": "conversation_id", "conversation_id": conversation_id}

        # 结构化 action 路径：ask 按钮点击 → 确定性执行工具，不经过 MiMo 工具选择
        if action and action.get("tool"):
            async for chunk in self._run_action(conversation_id, message, action):
                yield chunk
            return

        history = await self._load_history(conversation_id)

        # 交易执行指令：发给 MiMo 的消息追加强制指令（历史里仍存干净的原始消息）
        force_trade = _is_trade_instruction(message)
        sent_message = message + _TRADE_DIRECTIVE if force_trade else message
        messages = history + [{"role": "user", "content": sent_message}]
        await self._save_message(conversation_id, "user", message)

        client = get_client()
        full_text = ""
        emitted_cards = []

        for round_idx in range(MAX_TOOL_ROUNDS):
            tool_uses = []
            assistant_blocks = []
            current_text = ""

            stream_kwargs = dict(
                model=MODEL,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=BOBBY_TOOLS,
                messages=messages,
            )
            # 仅首轮：交易指令时强制走 manage_position（tool_choice 作辅助手段）
            if force_trade and round_idx == 0:
                stream_kwargs["tool_choice"] = {"type": "tool", "name": "manage_position"}

            with client.messages.stream(**stream_kwargs) as stream:
                for event in stream:
                    if event.type == "content_block_start":
                        if event.content_block.type == "tool_use":
                            tool_uses.append({
                                "id": event.content_block.id,
                                "name": event.content_block.name,
                                "input_json": "",
                            })
                    elif event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            current_text += event.delta.text
                            full_text += event.delta.text
                            yield {"type": "text", "content": event.delta.text}
                        elif event.delta.type == "input_json_delta":
                            if tool_uses:
                                tool_uses[-1]["input_json"] += event.delta.partial_json

                final_message = stream.get_final_message()
                assistant_blocks = final_message.content
                stop_reason = final_message.stop_reason

            messages.append({"role": "assistant", "content": assistant_blocks})

            if stop_reason != "tool_use" or not tool_uses:
                break

            # 执行所有工具
            tool_results = []
            for tu in tool_uses:
                try:
                    args = json.loads(tu["input_json"]) if tu["input_json"] else {}
                except json.JSONDecodeError:
                    args = {}
                yield {"type": "tool_call", "tool": tu["name"], "args": args}

                outcome = await execute_tool(tu["name"], args)
                result_data = outcome.get("result", {})

                for card in outcome.get("cards", []):
                    emitted_cards.append(card)
                    yield {"type": "card", "card": card}

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu["id"],
                    "content": json.dumps(result_data, ensure_ascii=False, default=str),
                })

            messages.append({"role": "user", "content": tool_results})

        await self._save_message(
            conversation_id, "assistant", full_text,
            metadata={"cards": emitted_cards} if emitted_cards else None,
        )
        yield {"type": "done"}

    async def _run_action(
        self, conversation_id: str, message: str, action: dict
    ) -> AsyncGenerator[dict, None]:
        """确定性 action 路径：直接执行指定工具（不经过 MiMo 工具选择），
        然后让 MiMo 仅用自然语言解读结果、引导下一步。"""
        tool = action["tool"]
        args = action.get("args", {})
        await self._save_message(conversation_id, "user", message)

        yield {"type": "tool_call", "tool": tool, "args": args}
        outcome = await execute_tool(tool, args)
        result_data = outcome.get("result", {})
        emitted_cards = []
        for card in outcome.get("cards", []):
            emitted_cards.append(card)
            yield {"type": "card", "card": card}

        # MiMo 仅做解读 —— 不带 tools，只能输出文字，可靠
        history = await self._load_history(conversation_id)
        result_summary = json.dumps(result_data, ensure_ascii=False, default=str)[:1200]
        narrate_prompt = (
            f"{message}\n\n[系统：已确定性执行工具 `{tool}`，结果如下：\n{result_summary}\n"
            f"结果卡片已展示给用户。请用 2-3 句中文简要解读这个结果，并引导用户进入下一步。"
            f"不要重复罗列卡片里的所有数字。]"
        )
        messages = history + [{"role": "user", "content": narrate_prompt}]

        client = get_client()
        full_text = ""
        with client.messages.stream(
            model=MODEL, max_tokens=1024, system=SYSTEM_PROMPT, messages=messages,
        ) as stream:
            for event in stream:
                if event.type == "content_block_delta" and event.delta.type == "text_delta":
                    full_text += event.delta.text
                    yield {"type": "text", "content": event.delta.text}

        await self._save_message(
            conversation_id, "assistant", full_text,
            metadata={"cards": emitted_cards} if emitted_cards else None,
        )
        yield {"type": "done"}

    async def _load_history(self, conversation_id: str) -> list[dict]:
        db = await get_db()
        cursor = await db.execute(
            "SELECT role, content FROM chat_messages WHERE conversation_id = ? ORDER BY id ASC LIMIT 20",
            (conversation_id,),
        )
        rows = await cursor.fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    async def _save_message(
        self, conversation_id: str, role: str, content: str, metadata: Optional[dict] = None
    ):
        db = await get_db()
        await db.execute(
            "INSERT INTO chat_messages (conversation_id, role, content, metadata) VALUES (?, ?, ?, ?)",
            (conversation_id, role, content,
             json.dumps(metadata, ensure_ascii=False) if metadata else None),
        )
        await db.commit()

    async def get_history(self, conversation_id: str) -> list[dict]:
        db = await get_db()
        cursor = await db.execute(
            "SELECT role, content, metadata, created_at FROM chat_messages WHERE conversation_id = ? ORDER BY id ASC",
            (conversation_id,),
        )
        rows = await cursor.fetchall()
        result = []
        for r in rows:
            result.append({
                "role": r["role"],
                "content": r["content"],
                "metadata": json.loads(r["metadata"]) if r["metadata"] else None,
                "timestamp": r["created_at"],
            })
        return result


bobby_agent = BobbyAgent()
