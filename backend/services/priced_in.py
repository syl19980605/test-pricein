import asyncio
from datetime import datetime, timezone

import pandas as pd

from backend.agent.llm import complete_json
from backend.models.schemas import IndicatorSet, NewsItem
from backend.services.market_data import market_data_service
from backend.services.technical import technical_service


# 5-factor weights
W_TIME_DECAY = 0.15
W_PRICE_REACTION = 0.30
W_VOLUME_SPIKE = 0.20
W_INDICATOR_ALIGNMENT = 0.15
W_CONSENSUS_AI = 0.20


def _score_time_decay(news_items: list[NewsItem]) -> float:
    """新闻越旧，越可能已被定价。"""
    if not news_items:
        return 0.5
    now = datetime.now(timezone.utc)
    ages_hours = []
    for item in news_items:
        pub = item.published_at
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=timezone.utc)
        ages_hours.append((now - pub).total_seconds() / 3600)
    avg_age = sum(ages_hours) / len(ages_hours)
    # 0h -> 0.0, 48h -> ~0.7, 168h(7d) -> ~0.95
    return min(1.0, avg_age / 72.0)


def _score_price_reaction(price_df: pd.DataFrame) -> float:
    """近期价格已显著移动 => 反应可能已发生。"""
    if price_df.empty or len(price_df) < 6:
        return 0.5
    closes = price_df["Close"]
    recent_5d_change = abs((closes.iloc[-1] - closes.iloc[-6]) / closes.iloc[-6])
    # 移动 >5% => 反应明显
    return min(1.0, recent_5d_change / 0.05)


def _score_volume_spike(price_df: pd.DataFrame) -> float:
    """量能脉冲后回归常态 => 反应已完成。"""
    if price_df.empty or len(price_df) < 25:
        return 0.5
    volume = price_df["Volume"]
    avg_vol = volume.iloc[-25:-5].mean()
    if avg_vol == 0:
        return 0.5
    recent_peak = volume.iloc[-5:].max()
    latest = volume.iloc[-1]
    spiked = recent_peak > avg_vol * 1.5
    normalized = latest < avg_vol * 1.2
    if spiked and normalized:
        return 0.85
    if spiked and not normalized:
        return 0.4  # 还在反应中
    return 0.5


def _score_indicator_alignment(ind: IndicatorSet, price_df: pd.DataFrame) -> float:
    """指标已偏离中性区 => 方向已被反映。"""
    if ind.rsi_14 is None:
        return 0.5
    score = 0.5
    # RSI 偏离 50 越远，方向越可能已被定价
    rsi_deviation = abs(ind.rsi_14 - 50) / 50
    score = 0.3 + rsi_deviation * 0.5
    # MACD 柱状图显著 => 趋势已确立
    if ind.macd_histogram is not None and abs(ind.macd_histogram) > 0:
        if not price_df.empty and len(price_df) > 1:
            price_scale = price_df["Close"].iloc[-1]
            macd_strength = min(1.0, abs(ind.macd_histogram) / (price_scale * 0.01))
            score = min(1.0, score + macd_strength * 0.2)
    return min(1.0, score)


class PricedInDetector:
    async def detect(
        self,
        symbol: str,
        news_items: list[NewsItem],
        price_df: pd.DataFrame,
        indicators: IndicatorSet,
    ) -> dict:
        time_score = _score_time_decay(news_items)
        price_score = _score_price_reaction(price_df)
        volume_score = _score_volume_spike(price_df)
        indicator_score = _score_indicator_alignment(indicators, price_df)
        consensus_score = await self._ai_consensus(symbol, news_items, price_df, indicators)

        final = (
            time_score * W_TIME_DECAY
            + price_score * W_PRICE_REACTION
            + volume_score * W_VOLUME_SPIKE
            + indicator_score * W_INDICATOR_ALIGNMENT
            + consensus_score * W_CONSENSUS_AI
        )

        return {
            "priced_in_probability": round(final, 3),
            "factors": {
                "time_decay": round(time_score, 3),
                "price_reaction": round(price_score, 3),
                "volume_spike": round(volume_score, 3),
                "indicator_alignment": round(indicator_score, 3),
                "ai_consensus": round(consensus_score, 3),
            },
        }

    async def detect_event(self, symbol: str, event_description: str) -> dict:
        """评估一个具体事件/消息是否已被定价。"""
        price_df, indicators, news_items = await asyncio.gather(
            market_data_service.get_price_history(symbol, "3mo"),
            technical_service.calculate_all(symbol),
            _safe_news(symbol),
        )

        base = await self.detect(symbol, news_items, price_df, indicators)

        # 针对具体事件，用 AI 单独评估
        event_score, reasoning = await asyncio.get_event_loop().run_in_executor(
            None, self._ai_event_assessment, symbol, event_description, price_df, indicators
        )

        # 事件评估与综合因子各占一半
        combined = round(base["priced_in_probability"] * 0.4 + event_score * 0.6, 3)
        return {
            "symbol": symbol,
            "event": event_description,
            "priced_in_probability": combined,
            "factors": base["factors"],
            "event_score": round(event_score, 3),
            "reasoning": reasoning,
        }

    async def _ai_consensus(
        self, symbol: str, news_items: list[NewsItem], price_df: pd.DataFrame, indicators: IndicatorSet
    ) -> float:
        if not news_items:
            return 0.5
        headlines = "\n".join(f"- {n.title}" for n in news_items[:8])
        recent_change = 0.0
        if not price_df.empty and len(price_df) > 6:
            closes = price_df["Close"]
            recent_change = round((closes.iloc[-1] - closes.iloc[-6]) / closes.iloc[-6] * 100, 2)

        prompt = f"""资产: {symbol}
近5日价格变动: {recent_change}%
RSI: {indicators.rsi_14}
近期新闻标题:
{headlines}

基于以上信息，估计市场参与者中有多大比例已经对这些消息采取了行动（即消息已被"定价"）。
返回 JSON: {{"priced_in": <0到1的小数>}}"""

        result = await asyncio.get_event_loop().run_in_executor(
            None, complete_json, prompt, "", 256
        )
        val = result.get("priced_in", 0.5)
        try:
            return max(0.0, min(1.0, float(val)))
        except (TypeError, ValueError):
            return 0.5

    def _ai_event_assessment(
        self, symbol: str, event: str, price_df: pd.DataFrame, indicators: IndicatorSet
    ) -> tuple[float, str]:
        recent_change = 0.0
        if not price_df.empty and len(price_df) > 6:
            closes = price_df["Close"]
            recent_change = round((closes.iloc[-1] - closes.iloc[-6]) / closes.iloc[-6] * 100, 2)

        prompt = f"""资产: {symbol}
待评估事件: {event}
该资产近5日价格变动: {recent_change}%
当前 RSI: {indicators.rsi_14}
当前 MACD 柱: {indicators.macd_histogram}

请评估这个事件是否已经被市场定价（反映在当前价格中）。考虑：
1. 事件是否是市场普遍预期的"旧闻"
2. 价格走势是否已经体现了该事件的影响
3. 技术指标是否已经反映了相应方向

返回 JSON: {{"priced_in": <0到1>, "reasoning": "<一句话中文理由>"}}"""

        result = complete_json(prompt, "", 384)
        score = result.get("priced_in", 0.5)
        try:
            score = max(0.0, min(1.0, float(score)))
        except (TypeError, ValueError):
            score = 0.5
        reasoning = result.get("reasoning", "无法获取分析理由。")
        return score, reasoning


async def _safe_news(symbol: str) -> list[NewsItem]:
    from backend.services.news_service import news_service
    try:
        return await news_service.get_news(symbol)
    except Exception:
        return []


priced_in_detector = PricedInDetector()
