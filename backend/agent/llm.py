import json
import re
from typing import Optional

from anthropic import Anthropic

from backend.config import ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL, BOBBY_MODEL

# 模型名走配置，方便切换 Claude / MiMo 等 Anthropic 兼容模型
MODEL = BOBBY_MODEL

# 客户端超时。MiMo 是推理模型，但结构化调用关闭了 thinking 后 ~4s 完成；
# 90s 是充裕的安全网，避免某次慢调用按 SDK 默认 10 分钟卡死整条链。
CLIENT_TIMEOUT = 90.0

# 结构化分析调用（情绪打分、定价因子、推理生成）不需要扩展思考。
# MiMo 默认会输出大段 thinking，既慢又会吃光 max_tokens 导致 JSON 截断。
# {"type": "disabled"} 是 Anthropic 标准参数，对真 Claude 也安全。
NO_THINKING = {"type": "disabled"}

_client: Optional[Anthropic] = None


def get_client() -> Anthropic:
    global _client
    if _client is None:
        kwargs = {"api_key": ANTHROPIC_API_KEY, "timeout": CLIENT_TIMEOUT}
        # 指向 Anthropic 兼容端点（如 MiMo）时设置 base_url
        if ANTHROPIC_BASE_URL:
            kwargs["base_url"] = ANTHROPIC_BASE_URL
        _client = Anthropic(**kwargs)
    return _client


def _text_from_response(resp) -> str:
    """从响应中提取文本。MiMo 等模型会在 content 里先放 thinking 块，
    必须遍历找到 type=='text' 的块，不能直接取 content[0]。"""
    if not resp.content:
        return ""
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            return block.text
    return ""


def _extract_json(text: str) -> dict:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    else:
        brace = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if brace:
            text = brace.group(1)
    return json.loads(text)


def complete_json(prompt: str, system: str = "", max_tokens: int = 1024) -> dict:
    """One-shot completion that returns parsed JSON. Used by analysis services."""
    client = get_client()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        thinking=NO_THINKING,
        system=system or "You are a precise financial analysis engine. Always respond with valid JSON only.",
        messages=[{"role": "user", "content": prompt}],
    )
    text = _text_from_response(resp) or "{}"
    try:
        return _extract_json(text)
    except (json.JSONDecodeError, ValueError):
        return {}


def complete_text(prompt: str, system: str = "", max_tokens: int = 512) -> str:
    client = get_client()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        thinking=NO_THINKING,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return _text_from_response(resp)
