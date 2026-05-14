"""用户创建的标的监控：增删查、定期刷新快照。
持有期在场景流前置确定，监控创建时即带 horizon，无需事后重分类。"""
import asyncio
import json
from datetime import datetime
from typing import Optional

from backend.models.database import get_db
from backend.models.schemas import Monitor, NewsImpactItem
from backend.services.market_data import ASSET_REGISTRY
from backend.services.news_impact import _analyze_related_news_sync, _clamp, _safe_news
from backend.services.signal_engine import signal_engine

HORIZON_LABELS = {"short": "短期", "mid": "中长线", "long": "长期"}


async def _build_snapshot(symbol: str) -> dict:
    """构建监控快照：价格影响消息（含定价程度）+ 综合信号。"""
    meta = ASSET_REGISTRY.get(symbol, {})
    name = meta.get("name", symbol)

    news_items = await _safe_news(symbol)
    headlines = [
        {"title": n.title, "source": n.source, "published_at": n.published_at.isoformat()}
        for n in news_items[:10]
    ]

    loop = asyncio.get_event_loop()
    news_task = loop.run_in_executor(None, _analyze_related_news_sync, symbol, name, headlines)
    signal_task = signal_engine.generate_signal(symbol)
    news_res, signal = await asyncio.gather(news_task, signal_task)

    news_list = []
    for item in news_res.get("news", []):
        idx = item.get("index", 0) - 1
        if 0 <= idx < len(headlines):
            h = headlines[idx]
            news_list.append({
                "title": h["title"],
                "source": h["source"],
                "published_at": h["published_at"],
                "impact_direction": item.get("impact_direction", "neutral"),
                "impact_summary": item.get("impact_summary", ""),
                "priced_in_pct": _clamp(item.get("priced_in_pct", 0.5)),
                "horizon": None,
            })

    return {
        "news": news_list,
        "signal_direction": signal.direction.value,
        "signal_priced_in": signal.priced_in_score,
        "overall_direction": news_res.get("overall_direction", "neutral"),
        "summary": news_res.get("summary", ""),
    }


def _row_to_monitor(row) -> Monitor:
    snapshot = json.loads(row["snapshot"]) if row["snapshot"] else {}
    meta = ASSET_REGISTRY.get(row["symbol"], {})
    return Monitor(
        id=str(row["id"]),
        symbol=row["symbol"],
        name=meta.get("name", row["symbol"]),
        thesis=row["thesis"] or "",
        direction=row["direction"] or "bullish",
        horizon=row["horizon"],
        refresh_interval_min=row["refresh_interval_min"],
        status=row["status"],
        created_at=str(row["created_at"]),
        last_refreshed_at=str(row["last_refreshed_at"]),
        news=[NewsImpactItem(**n) for n in snapshot.get("news", [])],
        signal_direction=snapshot.get("signal_direction"),
        signal_priced_in=snapshot.get("signal_priced_in"),
    )


class MonitorService:
    async def create_monitor(
        self, symbol: str, thesis: str, direction: str = "bullish",
        horizon: str = "mid", refresh_interval_min: int = 60,
    ) -> Monitor:
        snapshot = await _build_snapshot(symbol)
        db = await get_db()
        cursor = await db.execute(
            """INSERT INTO monitors
            (symbol, thesis, direction, horizon, refresh_interval_min, snapshot, last_refreshed_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (symbol, thesis, direction, horizon, refresh_interval_min,
             json.dumps(snapshot, ensure_ascii=False)),
        )
        await db.commit()
        return await self.get_monitor(cursor.lastrowid)

    async def list_monitors(self) -> list[Monitor]:
        db = await get_db()
        cursor = await db.execute("SELECT * FROM monitors ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [_row_to_monitor(r) for r in rows]

    async def get_monitor(self, monitor_id: int) -> Monitor:
        db = await get_db()
        cursor = await db.execute("SELECT * FROM monitors WHERE id = ?", (monitor_id,))
        row = await cursor.fetchone()
        if not row:
            raise ValueError(f"监控 {monitor_id} 不存在")
        return _row_to_monitor(row)

    async def get_latest_for_symbol(self, symbol: str) -> Optional[Monitor]:
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM monitors WHERE symbol = ? AND status = 'active' ORDER BY created_at DESC LIMIT 1",
            (symbol,),
        )
        row = await cursor.fetchone()
        return _row_to_monitor(row) if row else None

    async def refresh_monitor(self, monitor_id: int) -> Monitor:
        snapshot = await _build_snapshot_for_existing(monitor_id)
        db = await get_db()
        await db.execute(
            "UPDATE monitors SET snapshot = ?, last_refreshed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (json.dumps(snapshot, ensure_ascii=False), monitor_id),
        )
        await db.commit()
        return await self.get_monitor(monitor_id)


async def _build_snapshot_for_existing(monitor_id: int) -> dict:
    db = await get_db()
    cursor = await db.execute("SELECT symbol FROM monitors WHERE id = ?", (monitor_id,))
    row = await cursor.fetchone()
    if not row:
        raise ValueError(f"监控 {monitor_id} 不存在")
    return await _build_snapshot(row["symbol"])


monitor_service = MonitorService()
