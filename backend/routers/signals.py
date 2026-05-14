import json

from fastapi import APIRouter

from backend.models.database import get_db
from backend.services.market_data import ASSET_REGISTRY
from backend.services.signal_engine import signal_engine

router = APIRouter(tags=["signals"])


@router.get("/signals")
async def list_signals():
    """返回每个资产最新的一条已存储信号。"""
    db = await get_db()
    cursor = await db.execute(
        """SELECT s.* FROM signals s
        INNER JOIN (
            SELECT symbol, MAX(id) AS max_id FROM signals GROUP BY symbol
        ) latest ON s.id = latest.max_id
        ORDER BY s.created_at DESC"""
    )
    rows = await cursor.fetchall()
    result = []
    for r in rows:
        result.append({
            "symbol": r["symbol"],
            "direction": r["direction"],
            "confidence": r["confidence"],
            "technical_score": r["technical_score"],
            "sentiment_score": r["sentiment_score"],
            "priced_in_score": r["priced_in_score"],
            "reasoning": r["reasoning"],
            "key_factors": json.loads(r["key_factors"]) if r["key_factors"] else [],
            "triggered_at": r["created_at"],
        })
    return result


@router.get("/signals/{symbol}")
async def get_signal(symbol: str):
    """实时生成某个资产的信号。"""
    if symbol not in ASSET_REGISTRY:
        return {"error": f"未知资产: {symbol}"}
    signal = await signal_engine.generate_signal(symbol)
    return signal.model_dump(mode="json")
