import asyncio
from datetime import datetime

import pandas as pd

from backend.agent.llm import complete_json
from backend.models.schemas import IndicatorSet, NewsItem, Signal, SignalDirection
from backend.services.market_data import market_data_service
from backend.services.news_service import news_service
from backend.services.priced_in import priced_in_detector
from backend.services.technical import technical_service


def _score_technicals(ind: IndicatorSet, price_df: pd.DataFrame) -> tuple[float, list[str]]:
    """返回 (-1到1的技术评分, 关键因子列表)。"""
    if ind.rsi_14 is None or price_df.empty:
        return 0.0, []

    factors = []
    score = 0.0
    price = price_df["Close"].iloc[-1]

    # RSI (权重 0.20)
    if ind.rsi_14 < 30:
        score += 0.20
        factors.append(f"RSI 超卖 ({ind.rsi_14:.0f})")
    elif ind.rsi_14 > 70:
        score -= 0.20
        factors.append(f"RSI 超买 ({ind.rsi_14:.0f})")

    # MACD (权重 0.25)
    if ind.macd_histogram is not None:
        if ind.macd_histogram > 0:
            score += 0.25
            factors.append("MACD 柱状图为正")
        else:
            score -= 0.25
            factors.append("MACD 柱状图为负")

    # 均线位置 (权重 0.20)
    if ind.sma_50 is not None:
        if price > ind.sma_50:
            score += 0.20
            factors.append("价格在 SMA50 之上")
        else:
            score -= 0.20
            factors.append("价格在 SMA50 之下")

    # 布林带位置 (权重 0.15)
    if ind.bollinger_upper is not None and ind.bollinger_lower is not None:
        bb_range = ind.bollinger_upper - ind.bollinger_lower
        if bb_range > 0:
            bb_pos = (price - ind.bollinger_lower) / bb_range
            if bb_pos < 0.2:
                score += 0.15
                factors.append("贴近布林带下轨")
            elif bb_pos > 0.8:
                score -= 0.15
                factors.append("贴近布林带上轨")

    # 量能趋势 (权重 0.20)
    if len(price_df) >= 6:
        recent_up = price_df["Close"].iloc[-1] > price_df["Close"].iloc[-6]
        recent_vol = price_df["Volume"].iloc[-5:].mean()
        prior_vol = price_df["Volume"].iloc[-25:-5].mean() if len(price_df) >= 25 else recent_vol
        if prior_vol > 0 and recent_vol > prior_vol * 1.1:
            if recent_up:
                score += 0.20
                factors.append("放量上涨")
            else:
                score -= 0.20
                factors.append("放量下跌")

    return max(-1.0, min(1.0, score)), factors


def _score_sentiment_sync(symbol: str, news_items: list[NewsItem]) -> tuple[float, list[str]]:
    if not news_items:
        return 0.0, []
    headlines = "\n".join(f"{i+1}. {n.title}" for i, n in enumerate(news_items[:10]))
    prompt = f"""资产: {symbol}
近期新闻标题:
{headlines}

请分析整体新闻情绪对该资产的影响。
返回 JSON: {{"sentiment": <-1到1的小数>, "key_points": ["<关键利好/利空1>", "<关键利好/利空2>"]}}"""
    result = complete_json(prompt, "", 384)
    sentiment = result.get("sentiment", 0.0)
    try:
        sentiment = max(-1.0, min(1.0, float(sentiment)))
    except (TypeError, ValueError):
        sentiment = 0.0
    key_points = result.get("key_points", [])
    if not isinstance(key_points, list):
        key_points = []
    return sentiment, [str(p) for p in key_points[:3]]


def _score_to_direction(score: float) -> SignalDirection:
    if score >= 0.4:
        return SignalDirection.STRONG_BUY
    if score >= 0.15:
        return SignalDirection.BUY
    if score <= -0.4:
        return SignalDirection.STRONG_SELL
    if score <= -0.15:
        return SignalDirection.SELL
    return SignalDirection.NEUTRAL


def _generate_reasoning_sync(
    symbol: str,
    direction: SignalDirection,
    tech_score: float,
    sentiment_score: float,
    priced_in: float,
    factors: list[str],
) -> str:
    prompt = f"""资产: {symbol}
综合信号: {direction.value}
技术面评分: {tech_score:+.2f} (范围 -1~1)
情绪面评分: {sentiment_score:+.2f} (范围 -1~1)
已定价程度: {priced_in:.2f} (范围 0~1，越高说明消息越可能已反映在价格中)
关键因子: {', '.join(factors) if factors else '无'}

请用 2-3 句中文解释这个信号的推理逻辑。特别说明：如果已定价程度高，情绪面的影响应当被打折。
直接返回解释文字，不要 JSON。"""
    from backend.agent.llm import complete_text
    return complete_text(prompt, "你是一个简洁专业的投资分析助手。", 384)


class SignalEngine:
    async def generate_signal(self, symbol: str) -> Signal:
        """生成综合买卖信号（技术面 + 情绪面 + 5 因子定价检测）。
        预测市场篮子的融合由编排器（_analyze_asset）后处理，以便三个分析并行。"""
        price_df, indicators, news_items = await asyncio.gather(
            market_data_service.get_price_history(symbol, "3mo"),
            technical_service.calculate_all(symbol),
            _safe_news(symbol),
        )

        tech_score, tech_factors = _score_technicals(indicators, price_df)

        # 情绪打分 与 已定价检测 互相独立，并发执行以缩短关键路径
        loop = asyncio.get_event_loop()
        sentiment_task = loop.run_in_executor(
            None, _score_sentiment_sync, symbol, news_items
        )
        priced_in_task = priced_in_detector.detect(
            symbol, news_items, price_df, indicators
        )
        (sentiment_score, sentiment_factors), priced_in_result = await asyncio.gather(
            sentiment_task, priced_in_task
        )
        priced_in = priced_in_result["priced_in_probability"]

        # 已定价越高，情绪面影响越被削弱
        adjusted_sentiment = sentiment_score * (1 - priced_in * 0.7)
        raw_score = tech_score * 0.45 + adjusted_sentiment * 0.55

        direction = _score_to_direction(raw_score)
        all_factors = tech_factors + sentiment_factors

        reasoning = await asyncio.get_event_loop().run_in_executor(
            None,
            _generate_reasoning_sync,
            symbol,
            direction,
            tech_score,
            sentiment_score,
            priced_in,
            all_factors,
        )

        return Signal(
            symbol=symbol,
            direction=direction,
            confidence=round(min(1.0, abs(raw_score) * 1.5), 3),
            technical_score=round(tech_score, 3),
            sentiment_score=round(sentiment_score, 3),
            priced_in_score=round(priced_in, 3),
            reasoning=reasoning,
            triggered_at=datetime.utcnow(),
            key_factors=all_factors,
        )


async def _safe_news(symbol: str) -> list[NewsItem]:
    try:
        return await news_service.get_news(symbol)
    except Exception:
        return []


signal_engine = SignalEngine()
