"""预测市场（Polymarket）信号源 —— 和传统量化最不一样的维度。

量化看的是后视的价格/指标；预测市场是市场用真金白银投出的、前视的'预期'。
priced-in 最难回答的是"市场预期是什么"，预测市场的价格直接把这个量给出来了。

流程：拆解标的驱动因素 → 逐个去 Polymarket 搜索 → 过滤掉已结算市场
→ LLM 匹配并打相关性分 → 用确定性公式聚合成一篮子信号。

聚合公式（可审计，不靠 LLM 拍）：
    aggregate_priced_in = Σ(P_i · r_i · c_i · h_i) / Σ(r_i · c_i · h_i)
其中
    P_i = 预测市场概率（该因素的定价程度，原始信号，不扭曲）
    r_i = 相关性（该驱动因素对标的有多重要，LLM 判断）
    c_i = 置信度（成交量 + 时间新鲜度 —— 这个测量有多可信）
    h_i = horizon-match（市场结算日期与用户持有期的匹配度）
"""
import asyncio
import json
import re
import statistics
from datetime import datetime, timezone

import httpx

from backend.agent.llm import complete_json
from backend.models.schemas import PredictionMarketBasket, PredictionMarketItem
from backend.services.market_data import ASSET_REGISTRY

PUBLIC_SEARCH = "https://gamma-api.polymarket.com/public-search"

# 成交量置信度阈值的下限（K 实际从候选市场的成交量分布动态算，这只是保底）
K_VOL_FLOOR = 5000.0
K_WK_FLOOR = 500.0

# horizon 分桶：按"距结算还有多少天"
HORIZON_BUCKETS = [("short", 90), ("mid", 365)]  # >365 即 long
# 同桶 1.0 / 相邻桶 0.4 / 隔桶 0.1
_HORIZON_MATCH = {
    ("short", "short"): 1.0, ("short", "mid"): 0.4, ("short", "long"): 0.1,
    ("mid", "short"): 0.4, ("mid", "mid"): 1.0, ("mid", "long"): 0.4,
    ("long", "short"): 0.1, ("long", "mid"): 0.4, ("long", "long"): 1.0,
}


def _decompose_drivers_sync(symbol: str, name: str, event_description: str) -> list[str]:
    """把标的的价格驱动因素 + 用户描述的事件，拆解成 2-4 个可检索的英文关键词。"""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    prompt = f"""资产: {name}({symbol})
用户描述的消息/事件: {event_description}
今天的日期: {today}

请把"影响 {name} 价格的关键驱动因素"拆解成 2-4 个可在预测市场（Polymarket）上检索的查询词。
要求：
- 每个查询词是英文、简短（2-4 个词）、指向一个具体的、可下注的**未来**事件
- **绝对不要在查询词里写具体年份**（尤其不要写过去的年份）。Polymarket 上活跃的是当前和未来的市场，
  带过时年份会搜不到。例如要写 "Fed rate cut" 而不是 "Fed rate cut 2024"
- 用通用、当下正在被讨论的措辞，让它能匹配到 Polymarket 上正在交易的市场
- 既要包含用户提到的那个事件，也要包含该标的其他重要的价格驱动因素
- 例：黄金 → ["Fed rate cut", "US recession", "Trump tariffs", "Bitcoin price"]
  例：英伟达 → ["NVIDIA stock price", "AI chip export China", "US-China trade deal"]

返回 JSON: {{"queries": ["...", "...", "..."]}}"""
    result = complete_json(prompt, "你是金融检索词拆解引擎，只返回 JSON。", 512)
    queries = result.get("queries", [])
    if not isinstance(queries, list):
        return []
    # 兜底：剥掉查询词里残留的 4 位年份（如 "Fed rate cut 2024" → "Fed rate cut"）
    cleaned = []
    for q in queries:
        q = re.sub(r"\b(19|20)\d{2}\b", "", str(q)).strip()
        q = re.sub(r"\s{2,}", " ", q)
        if q:
            cleaned.append(q)
    return cleaned[:4]


def _parse_prices(market: dict):
    outcomes = market.get("outcomes")
    prices = market.get("outcomePrices")
    if isinstance(outcomes, str):
        try:
            outcomes = json.loads(outcomes)
        except (json.JSONDecodeError, TypeError):
            outcomes = None
    if isinstance(prices, str):
        try:
            prices = json.loads(prices)
        except (json.JSONDecodeError, TypeError):
            prices = None
    return outcomes, prices


def _yes_probability(market: dict):
    outcomes, prices = _parse_prices(market)
    if not prices:
        return None
    try:
        if outcomes and len(outcomes) == 2:
            for i, o in enumerate(outcomes):
                if str(o).lower() in ("yes", "true"):
                    return float(prices[i])
        return float(prices[0])
    except (TypeError, ValueError, IndexError):
        return None


def _days_to_resolution(end_date_str: str):
    if not end_date_str:
        return None
    try:
        end_dt = datetime.fromisoformat(str(end_date_str).replace("Z", "+00:00"))
        return (end_dt - datetime.now(timezone.utc)).total_seconds() / 86400
    except (ValueError, TypeError):
        return None


def _is_active_market(market: dict) -> bool:
    """只保留活跃、未结算的市场。public-search 也会返回已结算的旧市场。"""
    if market.get("closed") is True or market.get("active") is False:
        return False
    prob = _yes_probability(market)
    if prob is None or prob <= 0.02 or prob >= 0.98:
        return False  # 概率被钉死 = 已结算
    days = _days_to_resolution(market.get("endDate") or market.get("end_date"))
    if days is not None and days < 0:
        return False
    return True


def _bucket_by_days(days) -> str:
    if days is None:
        return "mid"  # 未知结算期 → 当作中性
    for bucket, threshold in HORIZON_BUCKETS:
        if days <= threshold:
            return bucket
    return "long"


def _horizon_match(end_date_str: str, user_horizon: str) -> float:
    """h_i：市场结算日期与用户持有期的匹配度。"""
    days = _days_to_resolution(end_date_str)
    market_bucket = _bucket_by_days(days)
    return _HORIZON_MATCH.get((user_horizon, market_bucket), 0.4)


def _confidence(volume: float, volume_1wk: float, k_vol: float, k_wk: float) -> float:
    """c_i：成交量置信度 × 时间新鲜度。
    - 成交量越大 → 这个市场价格越可信（真金白银越多）
    - 近一周成交量越大 → 价格越新鲜、不陈旧"""
    vol_conf = volume / (volume + k_vol) if (volume + k_vol) > 0 else 0.5
    fresh = volume_1wk / (volume_1wk + k_wk) if (volume_1wk + k_wk) > 0 else 0.5
    # 新鲜度调制：陈旧市场（近期无成交）置信度打到 4 折
    return round(vol_conf * (0.4 + 0.6 * fresh), 4)


def _sell_the_fact_risk(prob: float) -> str:
    if prob >= 0.65:
        return "high"
    if prob >= 0.4:
        return "medium"
    return "low"


def _search_polymarket(query: str) -> list[dict]:
    """调 public-search 端点，把 events 里的 markets 拍平成候选列表。"""
    try:
        resp = httpx.get(
            PUBLIC_SEARCH,
            params={"q": query, "limit_per_type": 12},
            timeout=12,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []
    markets = []
    for ev in data.get("events", []):
        ev_title = ev.get("title", "")
        for m in ev.get("markets", []):
            if not _is_active_market(m):
                continue
            markets.append({
                "question": m.get("question") or ev_title,
                "probability": _yes_probability(m),
                "volume": float(m.get("volume") or 0),
                "volume_1wk": float(m.get("volume1wk") or 0),
                "end_date": m.get("endDate", ""),
                "slug": ev.get("slug") or m.get("slug", ""),
            })
    return markets


def _match_basket_sync(
    symbol: str, name: str, event_description: str, horizon: str, factor_candidates: dict
) -> dict:
    """一次 LLM 调用：匹配市场 + 打相关性分 + 写解读。数值聚合不交给 LLM。"""
    blocks = []
    flat = []
    gi = 0
    for factor, markets in factor_candidates.items():
        if not markets:
            blocks.append(f"【因素: {factor}】（未搜到活跃市场）")
            continue
        lines = []
        for m in markets[:8]:
            flat.append((gi, m))
            pct = round((m["probability"] or 0.5) * 100)
            lines.append(f"  {gi}. {m['question']} —— 当前概率 {pct}%")
            gi += 1
        blocks.append(f"【因素: {factor}】\n" + "\n".join(lines))
    listing = "\n".join(blocks)

    prompt = f"""资产: {name}({symbol})
用户描述的事件: {event_description}
用户的投资持有期: {horizon}（short=短期 / mid=中长线 / long=长期）

下面是按"价格驱动因素"分组、从 Polymarket 搜到的活跃预测市场（编号全局唯一）：
{listing}

请完成两件事：
1. 从每个因素下，挑出 1 个真正相关、且赌的是同一类具体事件的市场（不相关/方向阈值不符的不选）。
   每个因素最多选 1 个，可以不选。宁缺毋滥。
   对每个选中的市场，给一个 relevance（0~1）：这个驱动因素对 {name} 的价格到底有多重要、多核心。
2. summary：2-3 句中文，结合用户的「{horizon}」持有期，解释这一篮子预测市场对 {name} "已定价程度"的整体含义，
   点出哪些预期已充分定价（卖事实风险）、哪些还没。

返回 JSON:
{{
  "picks": [{{"index": <全局编号>, "factor": "<对应因素>", "relevance": <0~1>}}],
  "summary": "<中文解读>"
}}"""
    result = complete_json(prompt, "你是严谨的金融分析引擎，宁缺毋滥，只返回 JSON。", 1536)
    result["_flat"] = {gi: m for gi, m in flat}
    return result


class PredictionMarketService:
    async def find_basket(
        self, symbol: str, event_description: str, horizon: str = "mid"
    ) -> PredictionMarketBasket:
        meta = ASSET_REGISTRY.get(symbol, {})
        name = meta.get("name", symbol)
        loop = asyncio.get_event_loop()

        # 1) 拆解驱动因素
        queries = await loop.run_in_executor(
            None, _decompose_drivers_sync, symbol, name, event_description
        )
        if not queries:
            return PredictionMarketBasket(
                matched=False, horizon=horizon, reason="无法拆解出可检索的驱动因素"
            )

        # 2) 逐个因素去 Polymarket 搜索（并行）
        search_results = await asyncio.gather(
            *[loop.run_in_executor(None, _search_polymarket, q) for q in queries]
        )
        factor_candidates = {q: r for q, r in zip(queries, search_results)}
        all_candidates = [m for r in search_results for m in r]
        if not all_candidates:
            return PredictionMarketBasket(
                matched=False, horizon=horizon, factors_searched=queries,
                reason=f"已按 {len(queries)} 个驱动因素检索，但 Polymarket 上暂无对应的活跃市场",
            )

        # 3) K 从候选市场的成交量分布动态算（中位数，鲁棒）
        vols = [m["volume"] for m in all_candidates if m["volume"] > 0]
        wk_vols = [m["volume_1wk"] for m in all_candidates if m["volume_1wk"] > 0]
        k_vol = max(statistics.median(vols), K_VOL_FLOOR) if vols else K_VOL_FLOOR
        k_wk = max(statistics.median(wk_vols), K_WK_FLOOR) if wk_vols else K_WK_FLOOR

        # 4) LLM 匹配 + 打相关性分（数值聚合不交给 LLM）
        match = await loop.run_in_executor(
            None, _match_basket_sync, symbol, name, event_description, horizon, factor_candidates
        )
        flat = match.get("_flat", {})
        picks = match.get("picks", [])

        items = []
        for p in picks:
            try:
                gi = int(p.get("index"))
            except (TypeError, ValueError):
                continue
            m = flat.get(gi)
            if not m:
                continue
            prob = m.get("probability") or 0.5
            r_i = _clamp(p.get("relevance", 0.5))
            c_i = _confidence(m["volume"], m["volume_1wk"], k_vol, k_wk)
            h_i = _horizon_match(m["end_date"], horizon)
            weight = round(r_i * c_i * h_i, 4)
            items.append(PredictionMarketItem(
                factor=p.get("factor", ""),
                market_question=m["question"],
                probability=round(prob, 4),
                volume=m["volume"],
                end_date=m["end_date"],
                slug=m["slug"],
                sell_the_fact_risk=_sell_the_fact_risk(prob),
                relevance=round(r_i, 3),
                confidence=round(c_i, 3),
                horizon_match=round(h_i, 3),
                weight=weight,
            ))

        if not items:
            return PredictionMarketBasket(
                matched=False, horizon=horizon, factors_searched=queries,
                reason="检索到候选市场，但没有一个真正匹配该标的的驱动因素",
            )

        # 5) 确定性聚合：aggregate = Σ(P·r·c·h) / Σ(r·c·h)
        total_w = sum(i.weight for i in items)
        if total_w > 0:
            agg = sum(i.probability * i.weight for i in items) / total_w
            overall_conf = sum(i.confidence * i.weight for i in items) / total_w
        else:
            agg = sum(i.probability for i in items) / len(items)
            overall_conf = sum(i.confidence for i in items) / len(items)

        return PredictionMarketBasket(
            matched=True,
            horizon=horizon,
            factors_searched=queries,
            items=items,
            aggregate_priced_in=round(agg, 3),
            overall_confidence=round(overall_conf, 3),
            summary=match.get("summary", ""),
        )


def _clamp(v) -> float:
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return 0.5


prediction_market_service = PredictionMarketService()
