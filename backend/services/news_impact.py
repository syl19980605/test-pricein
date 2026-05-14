"""消息定价场景核心：分析一条新闻对标的的影响逻辑是否成立、是否已定价，
并从更大范围检索其他影响该标的价格的消息。"""
import asyncio
import json
from typing import Optional

from backend.agent.llm import complete_json
from backend.models.schemas import NewsImpactItem, NewsImpactResult
from backend.services.market_data import ASSET_REGISTRY, market_data_service
from backend.services.news_service import news_service
from backend.services.technical import technical_service


_HORIZON_LABEL = {"short": "短期（数天-数周）", "mid": "中长线（数月）", "long": "长期（一年以上）"}


def _analyze_user_thesis_sync(
    symbol: str, name: str, news_event: str, user_hypothesis: Optional[str], horizon: str,
    recent_change: float, rsi, macd_hist,
) -> dict:
    horizon_label = _HORIZON_LABEL.get(horizon, "中长线（数月）")
    has_hypothesis = bool(user_hypothesis and user_hypothesis.strip())

    if has_hypothesis:
        thesis_block = f"用户的判断：这对 {name} 是「{user_hypothesis}」\n"
        task = (
            f"1. 用户的影响逻辑是否成立？（这条消息是否真的会朝用户判断的方向、在用户的持有期内影响价格）"
        )
        verdict_hint = "<2-3句中文点评用户的判断逻辑，要结合其持有期、要具体>"
    else:
        thesis_block = "用户没有给出自己的判断方向 —— 请你自己评估这条消息的影响方向。\n"
        task = (
            f"1. 这条消息对 {name} 的影响方向是什么（利好/利空/中性）？影响逻辑是什么？"
        )
        verdict_hint = "<2-3句中文：你判断这条消息的影响方向及理由，结合持有期、要具体>"

    prompt = f"""资产 {name}({symbol}) 相关：

用户看到的消息/事件：{news_event}
{thesis_block}用户的投资持有期：{horizon_label}

当前市场数据：
- 近5日价格变动：{recent_change}%
- RSI(14)：{rsi}
- MACD 柱：{macd_hist}

请**站在用户的「{horizon_label}」持有期视角**评估：
{task}
2. 这条消息从当前价格看，对「{horizon_label}」的投资者而言已被定价的程度有多高？
   （注意：同一条消息，对短线和长线投资者的"已定价"判断可能不同 —— 短期催化剂对长线投资者可能是噪音，结构性变化对短线投资者可能还没反应）

返回 JSON：
{{
  "logic_verdict": "supports" 或 "partially" 或 "contradicts"（有用户判断时=是否成立；无用户判断时=你判断的把握度，supports=方向明确/contradicts=方向存疑）,
  "logic_assessment": "{verdict_hint}",
  "event_priced_in_pct": <0到1的小数>,
  "user_direction": "bullish" 或 "bearish"
}}"""
    return complete_json(prompt, "你是严谨的金融分析引擎，只返回 JSON。", 768)


def _analyze_related_news_sync(symbol: str, name: str, headlines: list[dict]) -> dict:
    if not headlines:
        return {"news": [], "overall_direction": "neutral", "summary": "近期未检索到显著影响该标的的消息。"}
    lines = "\n".join(
        f"{i+1}. [{h['source']}] {h['title']}" for i, h in enumerate(headlines)
    )
    prompt = f"""以下是近期检索到的、可能影响 {name}({symbol}) 价格的新闻标题：

{lines}

请逐条分析每条消息对 {name} 的价格影响，并给出整体判断。

返回 JSON：
{{
  "news": [
    {{
      "index": <对应上面的编号>,
      "impact_direction": "bullish" 或 "bearish" 或 "neutral",
      "impact_summary": "<一句话说明这条消息怎么影响价格>",
      "priced_in_pct": <0到1，这条消息已被市场定价的程度>
    }}
  ],
  "overall_direction": "bullish" 或 "bearish" 或 "neutral",
  "summary": "<2-3句中文总结当前消息面对该标的的整体影响>"
}}"""
    return complete_json(prompt, "你是严谨的金融分析引擎，只返回 JSON。", 2048)


class NewsImpactAnalyzer:
    async def analyze(
        self, symbol: str, news_event: str,
        user_hypothesis: Optional[str] = None, horizon: str = "mid",
    ) -> NewsImpactResult:
        """分析一条具体消息对标的的影响。
        user_hypothesis 可选 —— 用户没给判断方向时，由 LLM 自己评估方向。
        预测市场篮子不在这里编排（由 analyze_asset 统一负责），本方法只做
        消息逻辑评估 + 更大范围消息检索。"""
        meta = ASSET_REGISTRY.get(symbol, {})
        name = meta.get("name", symbol)

        price_df, indicators, news_items = await asyncio.gather(
            market_data_service.get_price_history(symbol, "3mo"),
            technical_service.calculate_all(symbol),
            _safe_news(symbol),
        )

        recent_change = 0.0
        if not price_df.empty and len(price_df) > 6:
            closes = price_df["Close"]
            recent_change = round((closes.iloc[-1] - closes.iloc[-6]) / closes.iloc[-6] * 100, 2)

        headlines = [
            {"title": n.title, "source": n.source, "published_at": n.published_at.isoformat()}
            for n in news_items[:10]
        ]

        loop = asyncio.get_event_loop()
        thesis_task = loop.run_in_executor(
            None, _analyze_user_thesis_sync, symbol, name, news_event, user_hypothesis, horizon,
            recent_change, indicators.rsi_14, indicators.macd_histogram,
        )
        related_task = loop.run_in_executor(
            None, _analyze_related_news_sync, symbol, name, headlines,
        )
        thesis_res, related_res = await asyncio.gather(thesis_task, related_task)

        event_priced_in = _clamp(thesis_res.get("event_priced_in_pct", 0.5))

        related_news = []
        for item in related_res.get("news", []):
            idx = item.get("index", 0) - 1
            src = headlines[idx]["source"] if 0 <= idx < len(headlines) else ""
            pub = headlines[idx]["published_at"] if 0 <= idx < len(headlines) else None
            title = headlines[idx]["title"] if 0 <= idx < len(headlines) else item.get("title", "")
            related_news.append(
                NewsImpactItem(
                    title=title,
                    source=src,
                    published_at=pub,
                    impact_direction=item.get("impact_direction", "neutral"),
                    impact_summary=item.get("impact_summary", ""),
                    priced_in_pct=_clamp(item.get("priced_in_pct", 0.5)),
                )
            )

        return NewsImpactResult(
            symbol=symbol,
            name=name,
            user_thesis=news_event,
            user_direction=thesis_res.get("user_direction", "bullish"),
            hypothesis_given=bool(user_hypothesis and user_hypothesis.strip()),
            horizon=horizon,
            logic_verdict=thesis_res.get("logic_verdict", "partially"),
            logic_assessment=thesis_res.get("logic_assessment", ""),
            event_priced_in_pct=event_priced_in,
            related_news=related_news,
            overall_direction=related_res.get("overall_direction", "neutral"),
            summary=related_res.get("summary", ""),
        )


def _clamp(v) -> float:
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return 0.5


async def _safe_news(symbol: str):
    try:
        return await news_service.get_news(symbol)
    except Exception:
        return []


news_impact_analyzer = NewsImpactAnalyzer()
